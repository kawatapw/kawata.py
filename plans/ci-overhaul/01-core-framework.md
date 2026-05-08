# Phase 1 — Core Framework

## Scope

CLI layer, configuration system, context detection, storage abstraction, and shared data models. This is the foundation everything else builds on.

## 1. Package Setup

### `tools/ci/pyproject.toml`

```toml
[project]
name = "ci-tool"
version = "1.0.0"
description = "CI orchestration tool"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "pydantic>=2.0",
    "jinja2>=3.0",
    "httpx>=0.27",
    "rich>=13.0",
]

[project.scripts]
ci = "ci_tool.cli:app"

[tool.ruff]
target-version = "py311"

[tool.mypy]
strict = true
```

## 2. Data Models

### `src/ci_tool/storage/models.py`

```python
"""Core data models for CI state, results, and reports."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime


class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class OverallStatus(enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"


@dataclass
class JobResult:
    name: str
    status: JobStatus
    duration_seconds: float = 0.0
    summary_line: str = ""          # e.g. "142 passed, 3 failed"
    report_path: str = ""
    parser_name: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str = ""


@dataclass
class WorkflowState:
    run_id: str
    commit_sha: str
    repository: str
    branch: str
    actor: str
    started_at: datetime
    completed_at: datetime | None = None
    jobs: dict[str, JobResult] = field(default_factory=dict)
    overall_status: OverallStatus = OverallStatus.PASS
    total_duration_seconds: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)
```

### `src/ci_tool/context.py`

```python
"""Runtime environment detection."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Context:
    """Immutable runtime context.

    Works in GitHub Actions and locally. GitHub-specific fields are
    empty strings when not in GA.
    """
    # GitHub context
    commit_sha: str = ""
    workflow_name: str = ""
    job_name: str = ""
    run_id: str = ""
    run_number: str = ""
    repository: str = ""
    actor: str = ""
    branch: str = ""
    event_name: str = ""
    ref: str = ""

    # Derived
    run_url: str = ""
    is_github_actions: bool = False

    # Local context
    is_interactive: bool = False
    step_summary_path: str = ""
    project_root: Path = field(default_factory=Path.cwd)

    @classmethod
    def detect(cls) -> Context:
        """Build context from environment variables."""
        run_id = os.getenv("GITHUB_RUN_ID", "")
        repository = os.getenv("GITHUB_REPOSITORY", "")
        commit_sha = os.getenv("GITHUB_SHA", "")

        run_url = ""
        if repository and run_id:
            run_url = f"https://github.com/{repository}/actions/runs/{run_id}"

        return cls(
            commit_sha=commit_sha,
            workflow_name=os.getenv("GITHUB_WORKFLOW", ""),
            job_name=os.getenv("GITHUB_JOB", ""),
            run_id=run_id,
            run_number=os.getenv("GITHUB_RUN_NUMBER", ""),
            repository=repository,
            actor=os.getenv("GITHUB_ACTOR", ""),
            branch=os.getenv("GITHUB_REF_NAME", ""),
            event_name=os.getenv("GITHUB_EVENT_NAME", ""),
            ref=os.getenv("GITHUB_REF", ""),
            run_url=run_url,
            is_github_actions=bool(run_id),
            is_interactive=sys.stdin.isatty(),
            step_summary_path=os.getenv("GITHUB_STEP_SUMMARY", ""),
            project_root=Path.cwd(),
        )
```

## 3. Configuration System

### `src/ci_tool/config.py`

```python
"""Configuration loading, validation, and models."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileStorageConfig:
    directory: str = ".ci-data"


@dataclass
class SummaryConfig:
    include_jobs: bool = True
    include_timing: bool = True
    include_artifacts: bool = True
    max_failures_shown: int = 5
    max_code_snippet_lines: int = 8


@dataclass
class CommentConfig:
    enabled: bool = True
    update_existing: bool = True
    include_job_table: bool = True
    include_failures: bool = True
    include_code_snippets: bool = True


@dataclass
class JobConfig:
    """A single job definition for `ci run`."""
    name: str
    command: str
    report: str = ""
    parser: str = ""
    depends_on: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 600
    allow_failure: bool = False


@dataclass
class Config:
    """Root configuration."""
    storage_backend: str = "file"
    file_storage: FileStorageConfig = field(default_factory=FileStorageConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    comment: CommentConfig = field(default_factory=CommentConfig)
    jobs: dict[str, JobConfig] = field(default_factory=dict)
    custom: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, project_root: Path | None = None) -> Config:
        """Load config from pyproject.toml with sensible defaults.

        Priority: pyproject.toml [tool.ci] > defaults
        """
        root = project_root or Path.cwd()
        pyproject = root / "pyproject.toml"

        raw: dict[str, Any] = {}
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                raw = data.get("tool", {}).get("ci", {})

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: dict[str, Any]) -> Config:
        """Build Config from a raw dictionary (from TOML)."""
        file_storage_raw = raw.get("storage", {})
        if isinstance(file_storage_raw, dict):
            file_storage = FileStorageConfig(**{
                k: v for k, v in file_storage_raw.items()
                if k in FileStorageConfig.__dataclass_fields__
            })
        else:
            file_storage = FileStorageConfig()

        summary = SummaryConfig(**{
            k: v for k, v in raw.get("summary", {}).items()
            if k in SummaryConfig.__dataclass_fields__
        })
        comment = CommentConfig(**{
            k: v for k, v in raw.get("comment", {}).items()
            if k in CommentConfig.__dataclass_fields__
        })

        jobs: dict[str, JobConfig] = {}
        for name, job_raw in raw.get("jobs", {}).items():
            if isinstance(job_raw, dict):
                jobs[name] = JobConfig(
                    name=name,
                    command=job_raw.get("command", ""),
                    report=job_raw.get("report", ""),
                    parser=job_raw.get("parser", ""),
                    depends_on=job_raw.get("depends_on", []),
                    env=job_raw.get("env", {}),
                    timeout_seconds=job_raw.get("timeout_seconds", 600),
                    allow_failure=job_raw.get("allow_failure", False),
                )

        known_keys = {"storage", "summary", "comment", "jobs"}
        custom = {k: v for k, v in raw.items() if k not in known_keys}

        return cls(
            storage_backend=raw.get("storage_backend", "file"),
            file_storage=file_storage,
            summary=summary,
            comment=comment,
            jobs=jobs,
            custom=custom,
        )

    def generate_default_toml(self) -> str:
        """Generate a default [tool.ci] TOML string for `ci init`."""
        lines = [
            "[tool.ci]",
            '# Storage backend: "file"',
            'storage_backend = "file"',
            "",
            "[tool.ci.storage.file]",
            '# Directory for state and results',
            'directory = ".ci-data"',
            "",
            "[tool.ci.summary]",
            "include_jobs = true",
            "include_timing = true",
            "include_artifacts = true",
            "max_failures_shown = 5",
            "max_code_snippet_lines = 8",
            "",
            "[tool.ci.comment]",
            "enabled = true",
            "update_existing = true",
            "include_job_table = true",
            "include_failures = true",
            "include_code_snippets = true",
            "",
            "[tool.ci.jobs]",
            "# Define jobs for `ci run`",
            "# [tool.ci.jobs.test]",
            '# command = "uv run pytest tests/ --junit-xml=reports/junit.xml"',
            '# report = "reports/junit.xml"',
            '# parser = "pytest"',
        ]
        return "\n".join(lines)
```

## 4. Storage Abstraction

### `src/ci_tool/storage/__init__.py`

```python
"""Storage backend abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ci_tool.storage.models import WorkflowState


class StorageBackend(ABC):
    """Abstract storage for workflow state and results.

    Implementations must be thread-safe for parallel job execution.
    """

    @abstractmethod
    def save_state(self, state: WorkflowState) -> None:
        """Persist workflow state."""

    @abstractmethod
    def load_state(self, run_id: str) -> WorkflowState | None:
        """Load workflow state by run ID."""

    @abstractmethod
    def save_job_result(self, run_id: str, result: WorkflowState) -> None:
        """Save/update a single job result within workflow state."""

    @abstractmethod
    def list_runs(self, limit: int = 10) -> list[str]:
        """List recent run IDs, newest first."""

    @abstractmethod
    def cleanup(self, keep_last: int = 30) -> int:
        """Remove old runs. Returns count of removed entries."""
```

### `src/ci_tool/storage/file_backend.py`

```python
"""File-based JSON storage backend."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ci_tool.storage import StorageBackend
from ci_tool.storage.models import (
    JobResult,
    JobStatus,
    OverallStatus,
    WorkflowState,
)


def _serialize(obj: Any) -> Any:
    """JSON serializer for our types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Cannot serialize {type(obj)}")


def _deserialize_state(data: dict[str, Any]) -> WorkflowState:
    """Reconstruct WorkflowState from a JSON dict."""
    jobs = {}
    for name, jdata in data.get("jobs", {}).items():
        jobs[name] = JobResult(
            name=jdata["name"],
            status=JobStatus(jdata["status"]),
            duration_seconds=jdata.get("duration_seconds", 0),
            summary_line=jdata.get("summary_line", ""),
            report_path=jdata.get("report_path", ""),
            parser_name=jdata.get("parser_name", ""),
            error_message=jdata.get("error_message", ""),
        )

    return WorkflowState(
        run_id=data["run_id"],
        commit_sha=data.get("commit_sha", ""),
        repository=data.get("repository", ""),
        branch=data.get("branch", ""),
        actor=data.get("actor", ""),
        started_at=datetime.fromisoformat(data["started_at"]),
        completed_at=(
            datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None
        ),
        jobs=jobs,
        overall_status=OverallStatus(data.get("overall_status", "pass")),
        total_duration_seconds=data.get("total_duration_seconds", 0),
        metadata=data.get("metadata", {}),
    )


class FileStorageBackend(StorageBackend):
    """Stores each workflow run as a single JSON file."""

    def __init__(self, directory: str = ".ci-data") -> None:
        self.base_dir = Path(directory)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.base_dir / f"run-{run_id}.json"

    def save_state(self, state: WorkflowState) -> None:
        data = {
            "run_id": state.run_id,
            "commit_sha": state.commit_sha,
            "repository": state.repository,
            "branch": state.branch,
            "actor": state.actor,
            "started_at": state.started_at,
            "completed_at": state.completed_at,
            "overall_status": state.overall_status.value,
            "total_duration_seconds": state.total_duration_seconds,
            "metadata": state.metadata,
            "jobs": {
                name: {
                    "name": j.name,
                    "status": j.status.value,
                    "duration_seconds": j.duration_seconds,
                    "summary_line": j.summary_line,
                    "report_path": j.report_path,
                    "parser_name": j.parser_name,
                    "error_message": j.error_message,
                }
                for name, j in state.jobs.items()
            },
        }
        self._path(state.run_id).write_text(
            json.dumps(data, indent=2, default=_serialize)
        )

    def load_state(self, run_id: str) -> WorkflowState | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return _deserialize_state(data)

    def save_job_result(self, run_id: str, state: WorkflowState) -> None:
        # For file backend, saving a job result is the same as saving state
        self.save_state(state)

    def list_runs(self, limit: int = 10) -> list[str]:
        files = sorted(self.base_dir.glob("run-*.json"), reverse=True)
        return [f.stem.removeprefix("run-") for f in files[:limit]]

    def cleanup(self, keep_last: int = 30) -> int:
        files = sorted(self.base_dir.glob("run-*.json"), reverse=True)
        removed = 0
        for f in files[keep_last:]:
            f.unlink()
            removed += 1
        return removed


import enum  # noqa: E402 — needed for _serialize
```

## 5. CLI Layer

### `src/ci_tool/cli.py`

```python
"""CLI application using typer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ci_tool.config import Config
from ci_tool.context import Context

app = typer.Typer(
    name="ci",
    help="CI orchestration tool",
    no_args_is_help=True,
    add_completion=False,
)
console = Console(stderr=True)
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
def config(
    project_root: Annotated[
        Path, typer.Option("--root", help="Project root directory")
    ] = Path.cwd(),
) -> None:
    """Show resolved configuration."""
    cfg = Config.load(project_root)
    console.print(f"[bold]Storage backend:[/bold] {cfg.storage_backend}")
    console.print(f"[bold]File storage dir:[/bold] {cfg.file_storage.directory}")
    console.print(f"[bold]Summary:[/bold] jobs={cfg.summary.include_jobs}, "
                  f"timing={cfg.summary.include_timing}")
    console.print(f"[bold]Comment:[/bold] enabled={cfg.comment.enabled}, "
                  f"update={cfg.comment.update_existing}")
    console.print(f"[bold]Jobs configured:[/bold] {', '.join(cfg.jobs.keys()) or 'none'}")


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


# Import these here to avoid circular imports at module level
import os  # noqa: E402
import shutil  # noqa: E402


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
    """Parse existing reports and generate summary.

    This command is implemented in Phase 4 (output layer).
    Placeholder here for CLI structure.
    """
    console.print("[yellow]summary command — implemented in Phase 4[/yellow]")


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
    """Run configured jobs with DAG parallelism, then summarize.

    This command is implemented in Phase 3 (job runner) + Phase 4 (output).
    Placeholder here for CLI structure.
    """
    console.print("[yellow]run command — implemented in Phase 3[/yellow]")


@app.command()
def report() -> None:
    """Aggregate all job results into final report.

    This command is implemented in Phase 4 (output layer).
    """
    console.print("[yellow]report command — implemented in Phase 4[/yellow]")


@app.command()
def comment() -> None:
    """Post/update PR comment with summary.

    This command is implemented in Phase 5 (GitHub integration).
    """
    console.print("[yellow]comment command — implemented in Phase 5[/yellow]")
```

### `src/ci_tool/__main__.py`

```python
"""Entry point for `python -m ci_tool`."""

from ci_tool.cli import app

if __name__ == "__main__":
    app()
```

## 6. Tests

### `tests/conftest.py`

```python
"""Shared test fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
    return tmp_path


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear GitHub environment variables for consistent testing."""
    for key in [
        "GITHUB_SHA", "GITHUB_WORKFLOW", "GITHUB_JOB", "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER", "GITHUB_REPOSITORY", "GITHUB_ACTOR",
        "GITHUB_REF_NAME", "GITHUB_EVENT_NAME", "GITHUB_REF",
        "GITHUB_STEP_SUMMARY",
    ]:
        monkeypatch.delenv(key, raising=False)
```

### `tests/test_config.py`

```python
"""Tests for configuration system."""

from __future__ import annotations

from ci_tool.config import Config


def test_default_config() -> None:
    """Config with no pyproject.toml should use all defaults."""
    cfg = Config.load()
    assert cfg.storage_backend == "file"
    assert cfg.file_storage.directory == ".ci-data"
    assert cfg.summary.include_jobs is True
    assert cfg.summary.max_failures_shown == 5
    assert cfg.comment.enabled is True
    assert cfg.jobs == {}


def test_load_from_pyproject(tmp_project: Path) -> None:
    """Config should load from [tool.ci] in pyproject.toml."""
    pyproject = tmp_project / "pyproject.toml"
    pyproject.write_text("""\
[project]
name = "test"
version = "0.1.0"

[tool.ci]
storage_backend = "file"

[tool.ci.storage.file]
directory = "custom-data"

[tool.ci.summary]
max_failures_shown = 10

[tool.ci.jobs.test]
command = "pytest"
report = "junit.xml"
parser = "pytest"
""")
    cfg = Config.load(tmp_project)
    assert cfg.file_storage.directory == "custom-data"
    assert cfg.summary.max_failures_shown == 10
    assert "test" in cfg.jobs
    assert cfg.jobs["test"].command == "pytest"
    assert cfg.jobs["test"].parser == "pytest"


def test_generate_default_toml() -> None:
    """Generated TOML should be valid and contain all sections."""
    cfg = Config()
    toml_str = cfg.generate_default_toml()
    assert "[tool.ci]" in toml_str
    assert "storage_backend" in toml_str
    assert "[tool.ci.summary]" in toml_str
    assert "[tool.ci.comment]" in toml_str
    assert "[tool.ci.jobs]" in toml_str
```

### `tests/test_context.py`

```python
"""Tests for context detection."""

from __future__ import annotations

import os

from ci_tool.context import Context


def test_local_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Context outside GitHub Actions should have empty GitHub fields."""
    for key in ["GITHUB_RUN_ID", "GITHUB_SHA", "GITHUB_REPOSITORY"]:
        monkeypatch.delenv(key, raising=False)

    ctx = Context.detect()
    assert ctx.is_github_actions is False
    assert ctx.run_id == ""
    assert ctx.commit_sha == ""
    assert ctx.run_url == ""


def test_github_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Context in GitHub Actions should populate all fields."""
    monkeypatch.setenv("GITHUB_SHA", "abc123def")
    monkeypatch.setenv("GITHUB_WORKFLOW", "CI Pipeline")
    monkeypatch.setenv("GITHUB_JOB", "test")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "42")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_ACTOR", "developer")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")

    ctx = Context.detect()
    assert ctx.is_github_actions is True
    assert ctx.commit_sha == "abc123def"
    assert ctx.run_id == "12345"
    assert ctx.repository == "owner/repo"
    assert ctx.run_url == "https://github.com/owner/repo/actions/runs/12345"
```

### `tests/test_storage.py`

```python
"""Tests for file storage backend."""

from __future__ import annotations

from datetime import datetime

from ci_tool.storage.file_backend import FileStorageBackend
from ci_tool.storage.models import (
    JobResult,
    JobStatus,
    OverallStatus,
    WorkflowState,
)


def test_save_and_load(tmp_path: Path) -> None:
    """Should round-trip state through JSON."""
    backend = FileStorageBackend(directory=str(tmp_path / "ci-data"))
    state = WorkflowState(
        run_id="test-123",
        commit_sha="abc123",
        repository="owner/repo",
        branch="main",
        actor="dev",
        started_at=datetime(2025, 1, 1, 12, 0, 0),
        jobs={
            "test": JobResult(
                name="test",
                status=JobStatus.PASS,
                duration_seconds=45.0,
                summary_line="142 passed",
            ),
        },
    )
    backend.save_state(state)
    loaded = backend.load_state("test-123")

    assert loaded is not None
    assert loaded.run_id == "test-123"
    assert loaded.commit_sha == "abc123"
    assert "test" in loaded.jobs
    assert loaded.jobs["test"].status == JobStatus.PASS


def test_load_missing(tmp_path: Path) -> None:
    """Loading a non-existent run should return None."""
    backend = FileStorageBackend(directory=str(tmp_path / "ci-data"))
    assert backend.load_state("nonexistent") is None


def test_list_runs(tmp_path: Path) -> None:
    """Should list run IDs newest first."""
    backend = FileStorageBackend(directory=str(tmp_path / "ci-data"))
    for rid in ["run-a", "run-b", "run-c"]:
        state = WorkflowState(
            run_id=rid,
            commit_sha="abc",
            repository="r",
            branch="b",
            actor="a",
            started_at=datetime(2025, 1, 1),
        )
        backend.save_state(state)

    runs = backend.list_runs()
    assert len(runs) == 3
    # Should be sorted newest first (by file mtime)
    assert runs[0] == "run-c"


def test_cleanup(tmp_path: Path) -> None:
    """Should remove old runs, keeping the most recent."""
    backend = FileStorageBackend(directory=str(tmp_path / "ci-data"))
    for rid in ["run-1", "run-2", "run-3", "run-4", "run-5"]:
        state = WorkflowState(
            run_id=rid,
            commit_sha="abc",
            repository="r",
            branch="b",
            actor="a",
            started_at=datetime(2025, 1, 1),
        )
        backend.save_state(state)

    removed = backend.cleanup(keep_last=3)
    assert removed == 2
    remaining = backend.list_runs(limit=10)
    assert len(remaining) == 3
```

## 7. Implementation Notes

- Use `typer` with `Annotated` types for all CLI options (modern typer style).
- Use `rich` for terminal output — tables, colored status, progress indicators.
- All dataclasses use `frozen=True` where immutability is desired (like `Context`).
- The storage backend uses a single JSON file per run — simple, debuggable, no DB needed.
- Config loading uses stdlib `tomllib` (Python 3.11+) — no external dependency for TOML parsing.
- The `ci init` command appends to existing `pyproject.toml` without overwriting other sections.
- The `ci doctor` command checks: storage writability, job command availability, report directory existence.
