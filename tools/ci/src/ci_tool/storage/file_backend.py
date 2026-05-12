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
    if isinstance(obj, JobStatus):
        return obj.value
    if isinstance(obj, OverallStatus):
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
