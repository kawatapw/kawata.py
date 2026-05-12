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
