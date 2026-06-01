"""Job runner with DAG-based parallelism."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

from ci_tool.config import Config
from ci_tool.context import Context
from ci_tool.runner.models import (
    JobRunConfig,
    JobRunResult,
    JobStatus,
    RunResult,
    RunMode,
)
from ci_tool.storage.file_backend import FileStorageBackend
from ci_tool.storage.models import JobResult as WfJobResult
from ci_tool.storage.models import OverallStatus, WorkflowState


class DependencyGraph:
    """Resolves job execution order from dependency declarations."""

    def __init__(self, jobs: dict[str, JobRunConfig]) -> None:
        self.jobs = jobs
        self._validate()

    def _validate(self) -> None:
        """Check for missing dependencies and cycles."""
        # Check all deps exist
        for name, job in self.jobs.items():
            for dep in job.depends_on:
                if dep not in self.jobs:
                    raise ValueError(f"Job '{name}' depends on unknown job '{dep}'")

        # Check for cycles using DFS
        visited: set[str] = set()
        in_stack: set[str] = set()

        def visit(n: str) -> None:
            if n in in_stack:
                raise ValueError(f"Circular dependency detected involving '{n}'")
            if n in visited:
                return
            in_stack.add(n)
            for dep in self.jobs[n].depends_on:
                visit(dep)
            in_stack.remove(n)
            visited.add(n)

        for name in self.jobs:
            visit(name)

    def execution_levels(self) -> list[list[str]]:
        """Return jobs grouped by execution level.

        Level 0: jobs with no dependencies.
        Level 1: jobs whose dependencies are all in level 0.
        etc.

        Jobs in the same level can run in parallel.
        """
        remaining = dict(self.jobs)
        levels: list[list[str]] = []
        completed: set[str] = set()

        while remaining:
            # Find jobs whose deps are all satisfied
            ready = [
                name
                for name, job in remaining.items()
                if all(d in completed for d in job.depends_on)
            ]
            if not ready:
                # Should not happen after cycle check
                raise ValueError("Cannot resolve dependencies")

            levels.append(ready)
            for name in ready:
                completed.add(name)
                del remaining[name]

        return levels


class JobRunner:
    """Executes jobs with DAG-based parallelism."""

    def __init__(
        self,
        config: Config,
        context: Context,
        storage: FileStorageBackend,
        mode: RunMode = RunMode.PARALLEL,
    ) -> None:
        self.config = config
        self.context = context
        self.storage = storage
        self.mode = mode
        self._run_id = self._generate_run_id()

    def _generate_run_id(self) -> str:
        """Generate a unique run ID."""
        if self.context.is_github_actions and self.context.run_id:
            return self.context.run_id
        return f"local-{uuid.uuid4().hex[:8]}"

    def _build_job_configs(
        self, job_names: list[str] | None = None
    ) -> dict[str, JobRunConfig]:
        """Build runtime job configs from configuration."""
        configs: dict[str, JobRunConfig] = {}
        names = job_names or list(self.config.jobs.keys())

        for name in names:
            if name not in self.config.jobs:
                raise ValueError(
                    f"Unknown job: '{name}'. "
                    f"Available: {', '.join(self.config.jobs.keys())}"
                )
            jc = self.config.jobs[name]
            configs[name] = JobRunConfig(
                name=name,
                command=jc.command,
                report_path=jc.report,
                parser_name=jc.parser,
                depends_on=jc.depends_on,
                env=jc.env,
                timeout_seconds=jc.timeout_seconds,
                allow_failure=jc.allow_failure,
                working_dir=str(self.context.project_root),
            )

        return configs

    async def run(self, job_names: list[str] | None = None) -> RunResult:
        """Run jobs respecting dependency graph.

        Args:
            job_names: Specific jobs to run. None = all configured jobs.

        Returns:
            RunResult with all job results.
        """
        job_configs = self._build_job_configs(job_names)
        graph = DependencyGraph(job_configs)
        levels = graph.execution_levels()

        run_result = RunResult(
            run_id=self._run_id,
            started_at=datetime.now(timezone.utc),
        )

        # Initialize workflow state
        state = WorkflowState(
            run_id=self._run_id,
            commit_sha=self.context.commit_sha,
            repository=self.context.repository,
            branch=self.context.branch,
            actor=self.context.actor,
            started_at=run_result.started_at,
        )

        all_pass = True

        for level in levels:
            if self.mode == RunMode.PARALLEL:
                # Run all jobs in this level concurrently
                tasks = [
                    self._execute_job(name, job_configs[name], run_result, job_configs)
                    for name in level
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Serial mode: run one at a time
                results = []
                for name in level:
                    result = await self._execute_job(
                        name, job_configs[name], run_result, job_configs
                    )
                    results.append(result)

            # Check results and update state
            for result in results:
                if isinstance(result, Exception):
                    # This shouldn't happen with return_exceptions=True
                    # but handle it gracefully
                    continue

                run_result.jobs[result.name] = result

                # Update workflow state
                state.jobs[result.name] = WfJobResult(
                    name=result.name,
                    status=result.status,
                    duration_seconds=result.duration_seconds,
                    summary_line=self._job_summary_line(result),
                    report_path=result.report_path,
                    parser_name=result.parser_name,
                    error_message=result.error_message,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )

                # Check if we should stop (a required job failed)
                job_config = job_configs[result.name]
                if result.status == JobStatus.FAIL and not job_config.allow_failure:
                    all_pass = False

            # Save intermediate state
            self.storage.save_state(state)

            # If any required job failed, skip remaining levels
            if not all_pass:
                # Mark remaining jobs as skipped
                for remaining_level in levels[levels.index(level) + 1 :]:
                    for name in remaining_level:
                        skip_result = JobRunResult(
                            name=name,
                            status=JobStatus.SKIPPED,
                            skipped=True,
                            skip_reason="Dependency failed",
                        )
                        run_result.jobs[name] = skip_result
                break

        # Finalize
        run_result.completed_at = datetime.now(timezone.utc)
        run_result.total_duration_seconds = (
            run_result.completed_at - run_result.started_at
        ).total_seconds()
        run_result.overall_status = JobStatus.PASS if all_pass else JobStatus.FAIL

        # Update final state
        state.completed_at = run_result.completed_at
        state.total_duration_seconds = run_result.total_duration_seconds
        state.overall_status = OverallStatus.PASS if all_pass else OverallStatus.FAIL
        self.storage.save_state(state)

        return run_result

    async def _execute_job(
        self,
        name: str,
        config: JobRunConfig,
        run_result: RunResult,
        job_configs: dict[str, JobRunConfig],
    ) -> JobRunResult:
        """Execute a single job as a subprocess."""
        result = JobRunResult(
            name=name,
            status=JobStatus.RUNNING,
            report_path=config.report_path,
            parser_name=config.parser_name,
            started_at=datetime.now(timezone.utc),
        )

        # Check if any dependency failed (for skip detection)
        for dep_name in config.depends_on:
            if dep_name in run_result.jobs:
                dep_result = run_result.jobs[dep_name]
                dep_config = job_configs[dep_name]
                # Skip only if dependency failed AND doesn't allow failure
                if dep_result.status == JobStatus.FAIL and not dep_config.allow_failure:
                    result.status = JobStatus.SKIPPED
                    result.skipped = True
                    result.skip_reason = f"Dependency '{dep_name}' failed"
                    result.completed_at = datetime.now(timezone.utc)
                    return result

        # Prepare environment
        env = os.environ.copy()
        env.update(config.env)

        try:
            proc = await asyncio.create_subprocess_shell(
                config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=config.working_dir,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=config.timeout_seconds,
                )
                result.stdout = stdout_bytes.decode("utf-8", errors="replace")
                result.stderr = stderr_bytes.decode("utf-8", errors="replace")
                result.exit_code = proc.returncode or 0
                result.timed_out = False

            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                result.exit_code = -1
                result.timed_out = True
                result.error_message = f"Job timed out after {config.timeout_seconds}s"

        except Exception as e:
            result.exit_code = -1
            result.error_message = str(e)

        result.completed_at = datetime.now(timezone.utc)
        result.duration_seconds = (
            result.completed_at - result.started_at
        ).total_seconds()

        # Determine status
        if result.timed_out:
            result.status = JobStatus.FAIL
        elif result.exit_code == 0:
            result.status = JobStatus.PASS
        elif config.allow_failure:
            result.status = JobStatus.PASS  # Allowed failure = don't fail the run
            result.error_message = f"exit code {result.exit_code} (allowed)"
        else:
            result.status = JobStatus.FAIL

        return result

    def _job_summary_line(self, result: JobRunResult) -> str:
        """Generate a one-line summary for a job result."""
        if result.skipped:
            return "skipped"
        if result.timed_out:
            return f"timed out after {result.duration_seconds:.0f}s"
        if result.status == JobStatus.PASS:
            return f"passed in {result.duration_seconds:.1f}s"
        return f"failed (exit {result.exit_code}) in {result.duration_seconds:.1f}s"
