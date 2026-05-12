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
    summary_line: str = ""  # e.g. "142 passed, 3 failed"
    report_path: str = ""
    parser_name: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str = ""
    stdout: str = ""
    stderr: str = ""


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
