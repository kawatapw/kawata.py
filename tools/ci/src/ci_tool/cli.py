"""CLI application using typer."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ci_tool.config import Config
from ci_tool.context import Context
from ci_tool.storage.file_backend import FileStorageBackend

app = typer.Typer(
    name="ci",
    help="CI orchestration tool",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


def get_config() -> Config:
    """Load config, handling errors gracefully."""
    try:
        return Config.load()
    except Exception as e:
        err_console.print(f"[red]Error loading config:[/red] {e}")
        raise typer.Exit(1) from e


def get_context() -> Context:
    """Detect runtime context."""
    return Context.detect()


@app.command()
def init(
    project_root: Annotated[
        Path, typer.Option("--root", help="Project root directory")
    ] = Path.cwd(),
) -> None:
    """Scaffold [tool.ci] in pyproject.toml with all defaults."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        err_console.print(f"[red]No pyproject.toml found at {pyproject}[/red]")
        raise typer.Exit(1)

    config = Config.load(project_root)
    default_toml = config.generate_default_toml()

    # Check if [tool.ci] already exists
    content = pyproject.read_text()
    if "[tool.ci]" in content:
        err_console.print("[yellow][tool.ci] section already exists.[/yellow]")
        err_console.print("Append this to your existing section or remove it first:")
        console.print(default_toml)
        raise typer.Exit(0)

    # Append [tool.ci] section
    with open(pyproject, "a") as f:
        f.write("\n" + default_toml + "\n")

    console.print("[green]Added [tool.ci] section to pyproject.toml[/green]")


@app.command()
def config_cmd(
    project_root: Annotated[
        Path, typer.Option("--root", help="Project root directory")
    ] = Path.cwd(),
) -> None:
    """Show resolved configuration."""
    cfg = Config.load(project_root)
    console.print(f"[bold]Storage backend:[/bold] {cfg.storage_backend}")
    console.print(f"[bold]File storage dir:[/bold] {cfg.file_storage.directory}")
    console.print(
        f"[bold]Summary:[/bold] jobs={cfg.summary.include_jobs}, "
        f"timing={cfg.summary.include_timing}"
    )
    console.print(
        f"[bold]Comment:[/bold] enabled={cfg.comment.enabled}, "
        f"update={cfg.comment.update_existing}"
    )
    console.print(
        f"[bold]Jobs configured:[/bold] {', '.join(cfg.jobs.keys()) or 'none'}"
    )


@app.command()
def doctor() -> None:
    """Validate setup: check commands, parsers, storage."""
    ctx = get_context()
    cfg = get_config()
    issues: list[str] = []

    # Check storage directory
    storage_dir = Path(cfg.file_storage.directory)
    if not storage_dir.exists():
        issues.append(f"Storage directory does not exist: {storage_dir}")
    elif not os.access(storage_dir, os.W_OK):
        issues.append(f"Storage directory is not writable: {storage_dir}")

    # Check job commands
    for name, job in cfg.jobs.items():
        if not job.command:
            issues.append(f"Job '{name}' has no command")
        else:
            cmd = job.command.split()[0]
            if not shutil.which(cmd):
                issues.append(f"Job '{name}': command '{cmd}' not found in PATH")

    # Check report directories
    for name, job in cfg.jobs.items():
        if job.report:
            report_dir = Path(job.report).parent
            if not report_dir.exists():
                issues.append(
                    f"Job '{name}': report directory does not exist: {report_dir}"
                )

    if issues:
        err_console.print("[red]Issues found:[/red]")
        for issue in issues:
            err_console.print(f"  - {issue}")
        raise typer.Exit(1)
    else:
        console.print("[green]All checks passed[/green]")


@app.command()
def summary(
    directory: Annotated[
        str, typer.Option("--dir", help="Directory containing report files")
    ] = "reports",
    output: Annotated[
        str, typer.Option("--output", help="Output file (default: stdout/step summary)")
    ] = "",
    fmt: Annotated[
        str, typer.Option("--format", help="Output format: markdown, json")
    ] = "markdown",
) -> None:
    """Parse existing reports and generate summary."""

    cfg = get_config()
    ctx = get_context()

    # Load parsers
    from ci_tool.parsers import registry

    registry.load_builtin_parsers()

    # Scan directory for report files
    report_dir = Path(directory)
    if not report_dir.exists():
        err_console.print(f"[red]Directory not found: {directory}[/red]")
        raise typer.Exit(1)

    from ci_tool.output.summary import SummaryRenderer

    renderer = SummaryRenderer(config=cfg)

    # Build a synthetic RunResult from report files
    from ci_tool.runner.models import JobRunResult, JobStatus, RunResult
    from datetime import datetime, timezone

    run_result = RunResult(
        run_id="summary",
        started_at=datetime.now(timezone.utc),
    )

    parsed_results: dict = {}

    for report_file in sorted(report_dir.iterdir()):
        if report_file.is_file():
            try:
                content = report_file.read_text(encoding="utf-8")
                parser = registry.detect(str(report_file), content)
                result = parser.parse(content, str(report_file))
                job_name = report_file.stem
                run_result.jobs[job_name] = JobRunResult(
                    name=job_name,
                    status=JobStatus.FAIL if result.has_failures else JobStatus.PASS,
                    report_path=str(report_file),
                    parser_name=parser.name,
                )
                parsed_results[job_name] = result
            except Exception:
                continue

    # Add context info
    from ci_tool.output.models import SummaryData

    data = SummaryData.from_run_result(
        run_result,
        parsed_results,
        max_failures=cfg.summary.max_failures_shown,
        max_snippet_lines=cfg.summary.max_code_snippet_lines,
        include_snippets=cfg.comment.include_code_snippets,
    )
    data.commit_sha = ctx.commit_sha
    data.commit_short = ctx.commit_sha[:7] if ctx.commit_sha else ""
    data.branch = ctx.branch
    data.repository = ctx.repository
    data.run_url = ctx.run_url
    data.event_name = ctx.event_name

    markdown = renderer.render(run_result, parsed_results)

    # Write output
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(markdown)
    elif ctx.step_summary_path:
        Path(ctx.step_summary_path).parent.mkdir(parents=True, exist_ok=True)
        Path(ctx.step_summary_path).write_text(markdown)
    else:
        print(markdown)


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

    from ci_tool.runner import JobRunner, RunMode
    from ci_tool.runner.models import JobStatus

    mode = RunMode.PARALLEL if parallel else RunMode.SERIAL
    runner = JobRunner(cfg, ctx, storage, mode=mode)

    console.print(
        f"[bold]CI Run[/bold] — {len(job_names or cfg.jobs)} job(s), mode={mode.value}"
    )

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

    # Generate summary
    if show_summary:
        from ci_tool.parsers import registry
        from ci_tool.output.summary import SummaryRenderer, parse_reports_for_run

        registry.load_builtin_parsers()
        renderer = SummaryRenderer(config=cfg)
        parsed = parse_reports_for_run(run_result)

        markdown = renderer.render(run_result, parsed)

        if ctx.step_summary_path:
            Path(ctx.step_summary_path).parent.mkdir(parents=True, exist_ok=True)
            Path(ctx.step_summary_path).write_text(markdown)
            console.print("[green]Summary written to step summary[/green]")
        else:
            print(markdown)

    # Post comment
    if post_comment:
        asyncio.run(_post_comment(cfg, ctx, storage, run_result))

    # Exit with appropriate code
    if run_result.overall_status == JobStatus.FAIL:
        raise typer.Exit(1)


async def _post_comment(
    cfg: Config,
    ctx: Context,
    storage: FileStorageBackend,
    run_result: RunResult,
) -> None:
    """Post PR comment with results."""
    from ci_tool.github.comments import PRCommentManager
    from ci_tool.parsers import registry
    from ci_tool.output.summary import SummaryRenderer, parse_reports_for_run

    if not cfg.comment.enabled:
        console.print("[yellow]PR comments disabled in config[/yellow]")
        return

    async with PRCommentManager() as mgr:
        pr = await mgr.find_pr_for_commit(ctx.commit_sha)
        if pr is None:
            err_console.print("[red]Could not determine PR number[/red]")
            return

        registry.load_builtin_parsers()
        renderer = SummaryRenderer(config=cfg)
        parsed = parse_reports_for_run(run_result)
        body = renderer.render(run_result, parsed)

        result = await mgr.post_or_update_comment(pr, body)
        if result:
            console.print(f"[green]Posted comment to PR #{pr}[/green]")
        else:
            err_console.print("[red]Failed to post comment[/red]")


@app.command()
def report(
    run_id: Annotated[
        str | None, typer.Option("--run-id", help="Run ID (default: latest)")
    ] = None,
) -> None:
    """Aggregate all job results into final report."""
    cfg = get_config()
    ctx = get_context()
    storage = FileStorageBackend(cfg.file_storage.directory)

    from ci_tool.output.report import ReportBuilder

    builder = ReportBuilder(storage, config=cfg)

    if run_id is None:
        runs = storage.list_runs(limit=1)
        if not runs:
            err_console.print("[red]No runs found[/red]")
            raise typer.Exit(1)
        run_id = runs[0]

    report_md = builder.build_report(run_id, ctx)
    print(report_md)


@app.command()
def comment(
    pr_number: Annotated[
        int | None,
        typer.Option("--pr", help="PR number (auto-detected if not provided)"),
    ] = None,
    run_id: Annotated[
        str | None, typer.Option("--run-id", help="Run ID to comment about")
    ] = None,
) -> None:
    """Post/update PR comment with CI summary."""
    import asyncio

    cfg = get_config()
    ctx = get_context()
    storage = FileStorageBackend(cfg.file_storage.directory)

    if not cfg.comment.enabled:
        console.print("[yellow]PR comments disabled in config[/yellow]")
        return

    async def _post() -> None:
        from ci_tool.github.comments import PRCommentManager
        from ci_tool.output.summary import SummaryRenderer, parse_reports_for_run
        from ci_tool.runner.models import JobRunResult, RunResult, JobStatus
        from ci_tool.storage.models import JobStatus as WfJobStatus

        async with PRCommentManager() as mgr:
            pr = pr_number
            if pr is None and ctx.is_github_actions:
                pr = await mgr.find_pr_for_commit(ctx.commit_sha)

            if pr is None:
                err_console.print("[red]Could not determine PR number[/red]")
                raise typer.Exit(1)

            # Load run state
            rid = run_id or ctx.run_id
            if not rid:
                runs = storage.list_runs(limit=1)
                if not runs:
                    err_console.print("[red]No runs found[/red]")
                    raise typer.Exit(1)
                rid = runs[0]

            state = storage.load_state(rid)
            if state is None:
                err_console.print(f"[red]No state found for run: {rid}[/red]")
                raise typer.Exit(1)

            status_map = {
                WfJobStatus.PASS: JobStatus.PASS,
                WfJobStatus.FAIL: JobStatus.FAIL,
                WfJobStatus.SKIPPED: JobStatus.SKIPPED,
            }

            run_result = RunResult(
                run_id=state.run_id,
                started_at=state.started_at,
                completed_at=state.completed_at,
                total_duration_seconds=state.total_duration_seconds,
            )
            for name, j in state.jobs.items():
                run_result.jobs[name] = JobRunResult(
                    name=name,
                    status=status_map.get(j.status, JobStatus.FAIL),
                    duration_seconds=j.duration_seconds,
                    summary_line=j.summary_line,
                    report_path=j.report_path,
                    parser_name=j.parser_name,
                    error_message=j.error_message,
                    stdout=j.stdout,
                    stderr=j.stderr,
                )

            from ci_tool.parsers import registry

            registry.load_builtin_parsers()
            renderer = SummaryRenderer(config=cfg)
            parsed = parse_reports_for_run(run_result)
            body = renderer.render(run_result, parsed)

            result = await mgr.post_or_update_comment(pr, body)
            if result:
                console.print(f"[green]Posted comment to PR #{pr}[/green]")
            else:
                err_console.print("[red]Failed to post comment[/red]")
                raise typer.Exit(1)

    asyncio.run(_post())
