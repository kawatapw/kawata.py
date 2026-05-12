"""Summary renderer — generates markdown from run results."""

from __future__ import annotations

from pathlib import Path

from ci_tool.config import Config
from ci_tool.output.models import SummaryData
from ci_tool.parsers.models import ParsedResult
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
            parsed_results: dict of parser name -> ParsedResult for jobs that produced
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
