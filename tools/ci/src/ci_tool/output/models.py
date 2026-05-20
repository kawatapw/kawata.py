"""Models for output rendering."""

from __future__ import annotations

from dataclasses import dataclass, field

from ci_tool.parsers.models import ParsedResult
from ci_tool.runner.models import JobRunResult, RunResult
from ci_tool.storage.models import JobStatus


@dataclass
class JobSummary:
    """Processed summary for a single job, ready for rendering."""

    name: str
    status: JobStatus
    duration_seconds: float
    summary_line: str
    parsed_result: ParsedResult | None = None
    error_message: str = ""
    stderr: str = ""
    stdout: str = ""
    skipped: bool = False
    skip_reason: str = ""

    @property
    def status_icon(self) -> str:
        return {
            JobStatus.PASS: "✅",
            JobStatus.FAIL: "❌",
            JobStatus.SKIPPED: "⏭️",
            JobStatus.RUNNING: "🔄",
            JobStatus.PENDING: "⏳",
        }.get(self.status, "❓")

    @property
    def status_text(self) -> str:
        return {
            JobStatus.PASS: "PASS",
            JobStatus.FAIL: "FAIL",
            JobStatus.SKIPPED: "SKIP",
        }.get(self.status, self.status.value.upper())


@dataclass
class SummaryData:
    """Complete data for rendering a CI summary."""

    # Run info
    run_id: str = ""
    commit_sha: str = ""
    commit_short: str = ""
    branch: str = ""
    repository: str = ""
    run_url: str = ""
    event_name: str = ""

    # Timing
    total_duration_seconds: float = 0.0
    started_at: str = ""

    # Jobs
    jobs: list[JobSummary] = field(default_factory=list)

    # Overall
    overall_status: JobStatus = JobStatus.PASS
    total_passed: int = 0
    total_failed: int = 0
    total_skipped: int = 0

    # Config
    max_failures_shown: int = 5
    max_code_snippet_lines: int = 8
    include_code_snippets: bool = True

    @property
    def overall_icon(self) -> str:
        if self.overall_status == JobStatus.PASS:
            return "✅"
        if self.overall_status == JobStatus.FAIL:
            return "❌"
        return "⚠️"

    @property
    def overall_text(self) -> str:
        if self.overall_status == JobStatus.PASS:
            return "PASS"
        if self.overall_status == JobStatus.FAIL:
            return "FAIL"
        return "PARTIAL"

    @property
    def failed_jobs(self) -> list[JobSummary]:
        return [j for j in self.jobs if j.status == JobStatus.FAIL]

    @property
    def has_failures(self) -> bool:
        return len(self.failed_jobs) > 0

    @classmethod
    def from_run_result(
        cls,
        run_result: RunResult,
        parsed_results: dict[str, ParsedResult] | None = None,
        max_failures: int = 5,
        max_snippet_lines: int = 8,
        include_snippets: bool = True,
    ) -> SummaryData:
        """Build SummaryData from a RunResult and optional parsed results."""
        parsed = parsed_results or {}

        jobs = []
        passed = failed = skipped = 0
        for name, jr in run_result.jobs.items():
            if jr.status == JobStatus.PASS:
                passed += 1
            elif jr.status == JobStatus.FAIL:
                failed += 1
            elif jr.status == JobStatus.SKIPPED:
                skipped += 1

            jobs.append(
                JobSummary(
                    name=name,
                    status=jr.status,
                    duration_seconds=jr.duration_seconds,
                    summary_line=cls._build_summary_line(jr, parsed.get(name)),
                    parsed_result=parsed.get(name),
                    error_message=jr.error_message,
                    stderr=jr.stderr,
                    stdout=jr.stdout,
                    skipped=jr.skipped,
                    skip_reason=jr.skip_reason,
                )
            )

        overall = JobStatus.PASS if failed == 0 else JobStatus.FAIL

        return cls(
            run_id=run_result.run_id,
            total_duration_seconds=run_result.total_duration_seconds,
            jobs=jobs,
            overall_status=overall,
            total_passed=passed,
            total_failed=failed,
            total_skipped=skipped,
            max_failures_shown=max_failures,
            max_code_snippet_lines=max_snippet_lines,
            include_code_snippets=include_snippets,
        )

    @staticmethod
    def _build_summary_line(jr: JobRunResult, parsed: ParsedResult | None) -> str:
        if jr.skipped:
            return jr.skip_reason or "skipped"
        if parsed and parsed.summary_line():
            return parsed.summary_line()
        if jr.status == JobStatus.PASS:
            return "passed"
        # Build error message from available sources
        parts = []
        if jr.error_message:
            parts.append(jr.error_message)
        if jr.exit_code and jr.exit_code != 0:
            parts.append(f"exit code {jr.exit_code}")
        # Look for actual error lines in stderr (lines containing "error", "failed", etc.)
        if jr.stderr:
            stderr_lines = jr.stderr.strip().split("\n")
            for line in stderr_lines:
                line_lower = line.lower()
                if any(
                    kw in line_lower
                    for kw in [
                        "error",
                        "failed",
                        "returned a non-zero code",
                        "caused by",
                    ]
                ):
                    parts.append(f"stderr: {line[:150]}")
                    break
            else:
                # No error line found, use first line
                first_line = stderr_lines[0][:100] if stderr_lines else ""
                if first_line:
                    parts.append(f"stderr: {first_line}")
        # Include first line of stdout if available
        if jr.stdout:
            stdout_line = jr.stdout.strip().split("\n")[0][:100]
            if stdout_line:
                parts.append(f"stdout: {stdout_line}")
        return "; ".join(parts) if parts else "failed"
