"""Aggregate report builder."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ci_tool.config import Config
from ci_tool.context import Context
from ci_tool.storage.file_backend import FileStorageBackend
from ci_tool.storage.models import OverallStatus

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
