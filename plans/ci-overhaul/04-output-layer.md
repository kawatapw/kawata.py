# Phase 4 — Output Layer

## Scope

Summary renderer, report builder, and Jinja2 templates. This layer takes parsed results and workflow state, then produces concise, collapsible markdown output for GitHub step summaries and PR comments.

## 1. Design Principles

1. **Concise by default** — Job status table at top. Failures in collapsible sections. No redundant info.
2. **Code snippets in context** — When parsers provide code snippets, render them in collapsible sections with line numbers.
3. **Configurable verbosity** — `max_failures_shown` and `max_code_snippet_lines` control detail level.
4. **Template-driven** — All markdown output goes through Jinja2 templates. Easy to customize.
5. **Dual output** — Same renderer produces both step summary and PR comment content.

## 2. Output Models

### `src/ci_tool/output/models.py`

```python
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

            jobs.append(JobSummary(
                name=name,
                status=jr.status,
                duration_seconds=jr.duration_seconds,
                summary_line=cls._build_summary_line(jr, parsed.get(name)),
                parsed_result=parsed.get(name),
                error_message=jr.error_message,
                skipped=jr.skipped,
                skip_reason=jr.skip_reason,
            ))

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
    def _build_summary_line(
        jr: JobRunResult, parsed: ParsedResult | None
    ) -> str:
        if jr.skipped:
            return jr.skip_reason or "skipped"
        if parsed and parsed.summary_line():
            return parsed.summary_line()
        if jr.status == JobStatus.PASS:
            return "passed"
        if jr.error_message:
            return jr.error_message
        return f"failed (exit {jr.exit_code})"
```

## 3. Summary Renderer

### `src/ci_tool/output/summary.py`

```python
"""Summary renderer — generates markdown from run results."""

from __future__ import annotations

from pathlib import Path

from ci_tool.config import Config
from ci_tool.output.models import JobSummary, SummaryData
from ci_tool.parsers.models import ParsedResult, Severity
from ci_tool.runner.models import RunResult

from jinja2 import Environment, FileSystemLoader


class SummaryRenderer:
    """Renders CI run results into concise markdown summaries."""

    def __init__(
        self,
        template_dir: str | Path | None = None,
        config: Config | None = None,
    ) -> None:
        self.config = config or Config()

        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=False,  # We render markdown, not HTML
        )
        self.template = self.env.get_template("summary.md.j2")

    def render(
        self,
        run_result: RunResult,
        parsed_results: dict[str, ParsedResult] | None = None,
    ) -> str:
        """Render a complete summary from run results.

        Args:
            run_result: The result of `ci run`.
            dict of parser name -> ParsedResult for jobs that produced
            parseable reports.

        Returns:
            Markdown string.
        """
        data = SummaryData.from_run_result(
            run_result,
            parsed_results,
            max_failures=self.config.summary.max_failures_shown,
            max_snippet_lines=self.config.summary.max_code_snippet_lines,
            include_snippets=self.config.comment.include_code_snippets,
        )
        return self.template.render(data=data)

    def render_and_write(
        self,
        run_result: RunResult,
        parsed_results: dict[str, ParsedResult] | None = None,
        output_path: str | Path | None = None,
    ) -> str:
        """Render summary and write to file/stdout.

        If output_path is None and GITHUB_STEP_SUMMARY is set, writes there.
        Otherwise prints to stdout.
        """
        markdown = self.render(run_result, parsed_results)

        if output_path is None:
            import os
            output_path = os.getenv("GITHUB_STEP_SUMMARY")

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            # Write mode (not append) to avoid duplicates
            Path(output_path).write_text(markdown)
        else:
            print(markdown)

        return markdown


def parse_reports_for_run(
    run_result: RunResult,
) -> dict[str, ParsedResult]:
    """Parse all report files from a run result.

    For each job that has a report path, try to find and parse the report.
    Returns a dict of job_name -> ParsedResult.
    """
    from ci_tool.parsers import registry

    results: dict[str, ParsedResult] = {}

    for name, jr in run_result.jobs.items():
        if not jr.report_path:
            continue

        report_path = Path(jr.report_path)
        if not report_path.exists():
            # Try relative to cwd
            report_path = Path.cwd() / jr.report_path

        if not report_path.exists():
            continue

        try:
            content = report_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Use explicit parser or auto-detect
        try:
            if jr.parser_name:
                parser = registry.get(jr.parser_name)
            else:
                parser = registry.detect(str(report_path), content)
            results[name] = parser.parse(content, str(report_path))
        except Exception:
            # If parsing fails, skip — the job result already has exit code info
            continue

    return results
```

## 4. Report Builder

### `src/ci_tool/output/report.py`

```python
"""Aggregate report builder."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ci_tool.config import Config
from ci_tool.context import Context
from ci_tool.output.models import SummaryData
from ci_tool.storage.file_backend import FileStorageBackend
from ci_tool.storage.models import OverallStatus, WorkflowState

from jinja2 import Environment, FileSystemLoader


class ReportBuilder:
    """Builds aggregate reports from stored workflow state."""

    def __init__(
        self,
        storage: FileStorageBackend,
        config: Config | None = None,
        template_dir: str | Path | None = None,
    ) -> None:
        self.storage = storage
        self.config = config or Config()

        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=False,
        )
        self.template = self.env.get_template("report.md.j2")

    def build_report(
        self,
        run_id: str,
        context: Context | None = None,
    ) -> str:
        """Build an aggregate report for a run."""
        state = self.storage.load_state(run_id)
        if state is None:
            return f"# CI Report\n\nNo data found for run: {run_id}"

        # Calculate summary
        total = len(state.jobs)
        passed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.PASS)
        failed = sum(1 for j in state.jobs.values() if j.status == OverallStatus.FAIL)

        return self.template.render(
            state=state,
            total=total,
            passed=passed,
            failed=failed,
            success_rate=(passed / total * 100) if total > 0 else 0,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def build_and_save(
        self,
        run_id: str,
        context: Context | None = None,
    ) -> str:
        """Build report and save to storage."""
        report = self.build_report(run_id, context)

        report_path = Path(self.storage.base_dir) / f"report-{run_id}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report)

        return report
```

## 5. Templates

### `src/ci_tool/output/templates/summary.md.j2`

```jinja2
## CI Summary

| Job | Status | Duration | Summary |
|-----|--------|----------|---------|
{% for job in jobs %}
| {{ job.name }} | {{ job.status_icon }} {{ job.status_text }} | {{ "%.1f"|format(job.duration_seconds) }}s | {{ job.summary_line }} |
{% endfor %}

{% if commit_short %}
**Commit:** `{{ commit_short }}`{% if branch %} | **Branch:** {{ branch }}{% endif %} | **Duration:** {{ "%.1f"|format(total_duration_seconds) }}s | **Overall:** {{ overall_icon }} {{ overall_text }}
{% else %}
**Duration:** {{ "%.1f"|format(total_duration_seconds) }}s | **Overall:** {{ overall_icon }} {{ overall_text }}
{% endif %}

{% for job in failed_jobs %}
{% if job.parsed_result and job.parsed_result.has_issues %}
<details><summary>{{ job.status_icon }} {{ job.name }} — {{ job.parsed_result.summary_line() }}</summary>

{% for issue in job.parsed_result.issues[:data.max_failures_shown] %}
**`{{ issue.file_path }}:{{ issue.line_number }}`** — {{ issue.message }}
{% if issue.code_snippet and data.include_code_snippets %}
{{ issue.code_snippet.render(max_lines=data.max_code_snippet_lines) }}
{% endif %}

{% endfor %}
{% if job.parsed_result.issues|length > data.max_failures_shown %}
*... and {{ job.parsed_result.issues|length - data.max_failures_shown }} more*
{% endif %}

</details>
{% elif job.error_message %}
<details><summary>{{ job.status_icon }} {{ job.name }} — error</summary>

```
{{ job.error_message }}
```

</details>
{% endif %}
{% endfor %}

{% if run_url %}
[View full run details]({{ run_url }})
{% endif %}
```

### `src/ci_tool/output/templates/report.md.j2`

```jinja2
# CI Report — Run {{ state.run_id }}

**Commit:** `{{ state.commit_sha[:7] }}` | **Branch:** {{ state.branch }} | **Duration:** {{ "%.1f"|format(state.total_duration_seconds) }}s

## Results

| Job | Status | Duration | Summary |
|-----|--------|----------|---------|
{% for name, job in state.jobs.items() %}
| {{ name }} | {{ job.status.value }} | {{ "%.1f"|format(job.duration_seconds) }}s | {{ job.summary_line }} |
{% endfor %}

## Summary

- **Total Jobs:** {{ total }}
- **Passed:** {{ passed }}
- **Failed:** {{ failed }}
- **Success Rate:** {{ "%.1f"|format(success_rate) }}%

---
*Generated at {{ generated_at }}*
```

## 6. Tests

### `tests/test_output/test_summary.py`

```python
"""Tests for summary rendering."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ci_tool.output.models import JobSummary, SummaryData
from ci_tool.parsers.models import Issue, ParsedResult, Severity
from ci_tool.runner.models import JobRunResult, JobStatus, RunResult


class TestSummaryData:
    def test_from_run_result_all_pass(self) -> None:
        run = RunResult(
            run_id="test-1",
            started_at=datetime.now(timezone.utc),
            jobs={
                "test": JobRunResult(
                    name="test", status=JobStatus.PASS, duration_seconds=10.0
                ),
                "lint": JobRunResult(
                    name="lint", status=JobStatus.PASS, duration_seconds=5.0
                ),
            },
        )
        data = SummaryData.from_run_result(run)
        assert data.overall_status == JobStatus.PASS
        assert data.total_passed == 2
        assert data.total_failed == 0
        assert not data.has_failures

    def test_from_run_result_with_failures(self) -> None:
        run = RunResult(
            run_id="test-2",
            started_at=datetime.now(timezone.utc),
            jobs={
                "test": JobRunResult(
                    name="test", status=JobStatus.PASS, duration_seconds=10.0
                ),
                "lint": JobRunResult(
                    name="lint", status=JobStatus.FAIL, duration_seconds=5.0,
                    exit_code=1
                ),
            },
        )
        data = SummaryData.from_run_result(run)
        assert data.overall_status == JobStatus.FAIL
        assert data.total_passed == 1
        assert data.total_failed == 1
        assert data.has_failures
        assert len(data.failed_jobs) == 1

    def test_from_run_result_with_parsed_results(self) -> None:
        run = RunResult(
            run_id="test-3",
            started_at=datetime.now(timezone.utc),
            jobs={
                "test": JobRunResult(
                    name="test", status=JobStatus.FAIL, duration_seconds=10.0,
                    exit_code=1, report_path="junit.xml", parser_name="pytest"
                ),
            },
        )
        parsed = {
            "test": ParsedResult(
                parser_name="pytest",
                file_path="junit.xml",
                total=10,
                failed=2,
                passed=8,
                issues=[
                    Issue(
                        file_path="tests/test_a.py",
                        line_number=42,
                        severity=Severity.ERROR,
                        message="AssertionError: expected 1, got 2",
                    ),
                    Issue(
                        file_path="tests/test_b.py",
                        line_number=10,
                        severity=Severity.ERROR,
                        message="ValueError: invalid input",
                    ),
                ],
            ),
        }
        data = SummaryData.from_run_result(run, parsed)
        test_job = data.jobs[0]
        assert test_job.parsed_result is not None
        assert test_job.parsed_result.total == 10
        assert "2 failed" in test_job.summary_line


class TestSummaryRenderer:
    def test_render_basic(self, tmp_path: Path) -> None:
        from ci_tool.output.summary import SummaryRenderer

        # Create template dir
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "summary.md.j2").write_text(
            "{% for job in data.jobs %}"
            "{{ job.name }}: {{ job.status_text }} | "
            "{% endfor %}"
            "Overall: {{ data.overall_text }}"
        )

        renderer = SummaryRenderer(template_dir=template_dir)
        run = RunResult(
            run_id="test",
            started_at=datetime.now(timezone.utc),
            jobs={
                "a": JobRunResult(name="a", status=JobStatus.PASS, duration_seconds=1.0),
                "b": JobRunResult(name="b", status=JobStatus.FAIL, duration_seconds=2.0, exit_code=1),
            },
        )

        output = renderer.render(run)
        assert "a: PASS" in output
        assert "b: FAIL" in output
        assert "Overall: FAIL" in output

    def test_render_writes_to_step_summary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ci_tool.output.summary import SummaryRenderer

        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "summary.md.j2").write_text("test summary")

        summary_file = tmp_path / "step-summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        renderer = SummaryRenderer(template_dir=template_dir)
        run = RunResult(
            run_id="test",
            started_at=datetime.now(timezone.utc),
            jobs={},
        )

        renderer.render_and_write(run)
        assert summary_file.exists()
        assert summary_file.read_text() == "test summary"
