# Phase 3 — Job Runner

## Scope

Job execution engine with DAG-based dependency resolution and parallel execution. This is the `ci run` command's core — it reads job definitions from config, resolves dependencies, runs jobs concurrently where possible, and collects results.

## 1. Design Principles

1. **DAG-based execution** — Jobs declare `depends_on`. The runner builds a dependency graph and executes in topological order.
2. **Parallel by default** — Independent jobs run concurrently using `asyncio.TaskGroup`.
3. **Fail-fast with `allow_failure`** — Jobs that fail block dependents, unless `allow_failure: true`.
4. **Timeout support** — Each job has a configurable timeout. Hanging jobs are killed.
5. **Structured output** — Results are typed `JobResult` objects, not raw exit codes.

## 2. Runner Models

### `src/ci_tool/runner/models.py`

```python
"""Models for job execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ci_tool.storage.models import JobStatus


class RunMode(str, Enum):
    PARALLEL = "parallel"
    SERIAL = "serial"


@dataclass
class JobRunConfig:
    """Runtime config for a single job execution."""
    name: str
    command: str
    report_path: str = ""
    parser_name: str = ""
    depends_on: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 600
    allow_failure: bool = False
    working_dir: str = "."


@dataclass
class JobRunResult:
    """Result of executing a single job."""
    name: str
    status: JobStatus
    exit_code: int = -1
    duration_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    report_path: str = ""
    parser_name: str = ""
    error_message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    timed_out: bool = False
    skipped: bool = False
    skip_reason: str = ""

    @property
    def success(self) -> bool:
        return self.status == JobStatus.PASS


@dataclass
class RunResult:
    """Result of a complete `ci run` execution."""
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    jobs: dict[str, JobRunResult] = field(default_factory=dict)
    overall_status: JobStatus = JobStatus.PENDING
    total_duration_seconds: float = 0.0

    @property
    def failed_jobs(self) -> list[JobRunResult]:
        return [j for j in self.jobs.values() if j.status == JobStatus.FAIL]

    @property
    def passed_jobs(self) -> list[JobRunResult]:
        return [j for j in self.jobs.values() if j.status == JobStatus.PASS]
```

## 3. DAG Resolution

### `src/ci_tool/runner/__init__.py`

```python
"""Job runner with DAG-based parallelism."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

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
from ci_tool.storage.models import WorkflowState


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
                    raise ValueError(
                        f"Job '{name}' depends on unknown job '{dep}'"
                    )

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
                name for name, job in remaining.items()
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
                report=jc.report,
                parser=jc.parser,
                depends_on=jc.depends_on,
                env=jc.env,
                timeout_seconds=jc.timeout_seconds,
                allow_failure=jc.allow_failure,
                working_dir=str(self.context.project_root),
            )

        return configs

    async def run(
        self, job_names: list[str] | None = None
    ) -> RunResult:
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
                    self._execute_job(name, job_configs[name], run_result)
                    for name in level
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Serial mode: run one at a time
                results = []
                for name in level:
                    result = await self._execute_job(
                        name, job_configs[name], run_result
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
                from ci_tool.storage.models import JobResult as WfJobResult
                state.jobs[result.name] = WfJobResult(
                    name=result.name,
                    status=result.status,
                    duration_seconds=result.duration_seconds,
                    summary_line=self._job_summary_line(result),
                    report_path=result.report_path,
                    parser_name=result.parser_name,
                    error_message=result.error_message,
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
                for remaining_level in levels[levels.index(level) + 1:]:
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
        run_result.overall_status = (
            JobStatus.PASS if all_pass else JobStatus.FAIL
        )

        # Update final state
        state.completed_at = run_result.completed_at
        state.total_duration_seconds = run_result.total_duration_seconds
        from ci_tool.storage.models import OverallStatus
        state.overall_status = (
            OverallStatus.PASS if all_pass else OverallStatus.FAIL
        )
        self.storage.save_state(state)

        return run_result

    async def _execute_job(
        self,
        name: str,
        config: JobRunConfig,
        run_result: RunResult,
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
                if dep_result.status == JobStatus.FAIL and not config.allow_failure:
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
                result.error_message = (
                    f"Job timed out after {config.timeout_seconds}s"
                )

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
```

## 4. CLI Integration

The `ci run` command in `cli.py` should be updated to use the runner:

```python
# In cli.py — replace the placeholder run command

@app.command()
def run(
    job_names: Annotated[
        list[str] | None, typer.Argument(help="Jobs to run (default: all)")
    ] = None,
    parallel: Annotated[
        bool, typer.Option("--parallel/--serial", help="Execution mode")
    ] = True,
    show_summary: Annotated[
        bool, typer.Option("--summary/--no-summary", help="Generate summary after run")
    ] = True,
    post_comment: Annotated[
        bool, typer.Option("--comment/--no-comment", help="Post PR comment")
    ] = False,
) -> None:
    """Run configured jobs with DAG parallelism, then summarize."""
    import asyncio

    cfg = get_config()
    ctx = get_context()
    storage = FileStorageBackend(cfg.file_storage.directory)
    mode = RunMode.PARALLEL if parallel else RunMode.SERIAL

    runner = JobRunner(cfg, ctx, storage, mode=mode)

    console.print(f"[bold]CI Run[/bold] — {len(job_names or cfg.jobs)} job(s), mode={mode.value}")

    run_result = asyncio.run(runner.run(job_names))

    # Print results table
    table = Table(title="Job Results")
    table.add_column("Job", style="bold")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    table.add_column("Summary")

    for name, result in run_result.jobs.items():
        status_style = {
            JobStatus.PASS: "green",
            JobStatus.FAIL: "red",
            JobStatus.SKIPPED: "yellow",
        }.get(result.status, "white")

        status_icon = {
            JobStatus.PASS: "✅",
            JobStatus.FAIL: "❌",
            JobStatus.SKIPPED: "⏭️",
        }.get(result.status, "❓")

        table.add_row(
            name,
            f"[{status_style}]{status_icon} {result.status.value}[/{status_style}]",
            f"{result.duration_seconds:.1f}s",
            runner._job_summary_line(result),
        )

    console.print(table)

    if show_summary:
        # Phase 4 will implement this
        console.print("\n[yellow]Summary generation — implemented in Phase 4[/yellow]")

    if post_comment:
        console.print("[yellow]PR comment — implemented in Phase 5[/yellow]")

    # Exit with appropriate code
    if run_result.overall_status == JobStatus.FAIL:
        raise typer.Exit(1)
```

## 5. Tests

### `tests/test_runner.py`

```python
"""Tests for job runner."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ci_tool.config import Config, JobConfig
from ci_tool.context import Context
from ci_tool.runner import DependencyGraph, JobRunner
from ci_tool.runner.models import JobRunConfig, JobStatus, RunMode
from ci_tool.storage.file_backend import FileStorageBackend


class TestDependencyGraph:
    def test_no_dependencies(self) -> None:
        jobs = {
            "a": JobRunConfig(name="a", command="echo a"),
            "b": JobRunConfig(name="b", command="echo b"),
        }
        graph = DependencyGraph(jobs)
        levels = graph.execution_levels()
        assert len(levels) == 1
        assert set(levels[0]) == {"a", "b"}

    def test_linear_chain(self) -> None:
        jobs = {
            "a": JobRunConfig(name="a", command="echo a"),
            "b": JobRunConfig(name="b", command="echo b", depends_on=["a"]),
            "c": JobRunConfig(name="c", command="echo c", depends_on=["b"]),
        }
        graph = DependencyGraph(jobs)
        levels = graph.execution_levels()
        assert len(levels) == 3
        assert levels[0] == ["a"]
        assert levels[1] == ["b"]
        assert levels[2] == ["c"]

    def test_diamond(self) -> None:
        jobs = {
            "build": JobRunConfig(name="build", command="echo build"),
            "test": JobRunConfig(name="test", command="echo test", depends_on=["build"]),
            "lint": JobRunConfig(name="lint", command="echo lint", depends_on=["build"]),
            "deploy": JobRunConfig(name="deploy", command="echo deploy", depends_on=["test", "lint"]),
        }
        graph = DependencyGraph(jobs)
        levels = graph.execution_levels()
        assert len(levels) == 3
        assert levels[0] == ["build"]
        assert set(levels[1]) == {"test", "lint"}
        assert levels[2] == ["deploy"]

    def test_missing_dependency(self) -> None:
        jobs = {
            "a": JobRunConfig(name="a", command="echo a", depends_on=["missing"]),
        }
        with pytest.raises(ValueError, match="unknown job"):
            DependencyGraph(jobs)

    def test_circular_dependency(self) -> None:
        jobs = {
            "a": JobRunConfig(name="a", command="echo a", depends_on=["b"]),
            "b": JobRunConfig(name="b", command="echo b", depends_on=["a"]),
        }
        with pytest.raises(ValueError, match="Circular"):
            DependencyGraph(jobs)


class TestJobRunner:
    @pytest.fixture
    def tmp_storage(self, tmp_path: Path) -> FileStorageBackend:
        return FileStorageBackend(directory=str(tmp_path / "ci-data"))

    @pytest.fixture
    def base_context(self) -> Context:
        ctx = Context.detect()
        return ctx

    @pytest.mark.asyncio
    async def test_run_simple_job(self, tmp_storage: FileStorageBackend, base_context: Context) -> None:
        config = Config()
        config.jobs["hello"] = JobConfig(
            name="hello",
            command="echo hello",
        )
        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.SERIAL)
        result = await runner.run()

        assert "hello" in result.jobs
        assert result.jobs["hello"].status == JobStatus.PASS
        assert result.jobs["hello"].exit_code == 0
        assert result.overall_status == JobStatus.PASS

    @pytest.mark.asyncio
    async def test_run_failing_job(self, tmp_storage: FileStorageBackend, base_context: Context) -> None:
        config = Config()
        config.jobs["fail"] = JobConfig(
            name="fail",
            command="exit 1",
        )
        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.SERIAL)
        result = await runner.run()

        assert result.jobs["fail"].status == JobStatus.FAIL
        assert result.overall_status == JobStatus.FAIL

    @pytest.mark.asyncio
    async def test_dependency_blocks_on_failure(self, tmp_storage: FileStorageBackend, base_context: Context) -> None:
        config = Config()
        config.jobs["first"] = JobConfig(name="first", command="exit 1")
        config.jobs["second"] = JobConfig(
            name="second", command="echo should not run", depends_on=["first"]
        )
        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.SERIAL)
        result = await runner.run()

        assert result.jobs["first"].status == JobStatus.FAIL
        assert result.jobs["second"].status == JobStatus.SKIPPED
        assert result.jobs["second"].skipped is True

    @pytest.mark.asyncio
    async def test_parallel_execution(self, tmp_storage: FileStorageBackend, base_context: Context) -> None:
        config = Config()
        config.jobs["a"] = JobConfig(name="a", command="sleep 0.1 && echo a")
        config.jobs["b"] = JobConfig(name="b", command="sleep 0.1 && echo b")
        config.jobs["c"] = JobConfig(name="c", command="sleep 0.1 && echo c")

        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.PARALLEL)
        result = await runner.run()

        # All should pass
        for name in ["a", "b", "c"]:
            assert result.jobs[name].status == JobStatus.PASS

        # Total time should be ~0.1s (parallel), not ~0.3s (serial)
        assert result.total_duration_seconds < 0.25

    @pytest.mark.asyncio
    async def test_allow_failure(self, tmp_storage: FileStorageBackend, base_context: Context) -> None:
        config = Config()
        config.jobs["flaky"] = JobConfig(
            name="flaky", command="exit 1", allow_failure=True
        )
        config.jobs["after"] = JobConfig(
            name="after", command="echo ok", depends_on=["flaky"]
        )
        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.SERIAL)
        result = await runner.run()

        # flaky should be marked PASS (allowed failure)
        assert result.jobs["flaky"].status == JobStatus.PASS
        # after should still run
        assert result.jobs["after"].status == JobStatus.PASS
        # overall should pass
        assert result.overall_status == JobStatus.PASS
