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
            # TOML [tool.ci.storage.file] nests as {"storage": {"file": {...}}}
            inner = file_storage_raw.get("file", file_storage_raw)
            if isinstance(inner, dict):
                file_storage = FileStorageConfig(
                    **{
                        k: v
                        for k, v in inner.items()
                        if k in FileStorageConfig.__dataclass_fields__
                    }
                )
            else:
                file_storage = FileStorageConfig()
        else:
            file_storage = FileStorageConfig()

        summary = SummaryConfig(
            **{
                k: v
                for k, v in raw.get("summary", {}).items()
                if k in SummaryConfig.__dataclass_fields__
            }
        )
        comment = CommentConfig(
            **{
                k: v
                for k, v in raw.get("comment", {}).items()
                if k in CommentConfig.__dataclass_fields__
            }
        )

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
            "# Directory for state and results",
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
