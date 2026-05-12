"""Tests for summary rendering."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

import pytest
from ci_tool.output.models import SummaryData
from ci_tool.parsers.models import Issue
from ci_tool.parsers.models import ParsedResult
from ci_tool.parsers.models import Severity
from ci_tool.runner.models import JobRunResult
from ci_tool.runner.models import JobStatus
from ci_tool.runner.models import RunResult


class TestSummaryData:
    def test_from_run_result_all_pass(self) -> None:
        run = RunResult(
            run_id="test-1",
            started_at=datetime.now(UTC),
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
            started_at=datetime.now(UTC),
            jobs={
                "test": JobRunResult(
                    name="test", status=JobStatus.PASS, duration_seconds=10.0
                ),
                "lint": JobRunResult(
                    name="lint",
                    status=JobStatus.FAIL,
                    duration_seconds=5.0,
                    exit_code=1,
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
            started_at=datetime.now(UTC),
            jobs={
                "test": JobRunResult(
                    name="test",
                    status=JobStatus.FAIL,
                    duration_seconds=10.0,
                    exit_code=1,
                    report_path="junit.xml",
                    parser_name="pytest",
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
            started_at=datetime.now(UTC),
            jobs={
                "a": JobRunResult(
                    name="a", status=JobStatus.PASS, duration_seconds=1.0
                ),
                "b": JobRunResult(
                    name="b", status=JobStatus.FAIL, duration_seconds=2.0, exit_code=1
                ),
            },
        )

        output = renderer.render(run)
        assert "a: PASS" in output
        assert "b: FAIL" in output
        assert "Overall: FAIL" in output

    def test_render_writes_to_step_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ci_tool.output.summary import SummaryRenderer

        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        (template_dir / "summary.md.j2").write_text("test summary")

        summary_file = tmp_path / "step-summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        renderer = SummaryRenderer(template_dir=template_dir)
        run = RunResult(
            run_id="test",
            started_at=datetime.now(UTC),
            jobs={},
        )

        renderer.render_and_write(run)
        assert summary_file.exists()
        assert summary_file.read_text() == "test summary"
