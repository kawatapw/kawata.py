"""Tests for file storage backend."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime

import pytest
from ci_tool.storage.file_backend import FileStorageBackend
from ci_tool.storage.models import JobResult
from ci_tool.storage.models import JobStatus
from ci_tool.storage.models import WorkflowState


class TestFileStorageBackend:
    def test_save_and_load_state(self, tmp_path: pytest.TempPathFactory) -> None:
        storage = FileStorageBackend(directory=str(tmp_path / "ci-data"))

        state = WorkflowState(
            run_id="test-1",
            commit_sha="abc123",
            repository="owner/repo",
            branch="main",
            actor="testuser",
            started_at=datetime.now(UTC),
            jobs={
                "test": JobResult(
                    name="test",
                    status=JobStatus.PASS,
                    duration_seconds=10.0,
                    summary_line="all passed",
                ),
            },
        )

        storage.save_state(state)
        loaded = storage.load_state("test-1")

        assert loaded is not None
        assert loaded.run_id == "test-1"
        assert loaded.commit_sha == "abc123"
        assert "test" in loaded.jobs
        assert loaded.jobs["test"].status == JobStatus.PASS

    def test_load_nonexistent(self, tmp_path: pytest.TempPathFactory) -> None:
        storage = FileStorageBackend(directory=str(tmp_path / "ci-data"))
        assert storage.load_state("nonexistent") is None

    def test_list_runs(self, tmp_path: pytest.TempPathFactory) -> None:
        storage = FileStorageBackend(directory=str(tmp_path / "ci-data"))

        for i in range(3):
            state = WorkflowState(
                run_id=f"run-{i}",
                commit_sha=f"sha-{i}",
                repository="owner/repo",
                branch="main",
                actor="test",
                started_at=datetime.now(UTC),
            )
            storage.save_state(state)

        runs = storage.list_runs(limit=10)
        assert len(runs) == 3

    def test_cleanup(self, tmp_path: pytest.TempPathFactory) -> None:
        storage = FileStorageBackend(directory=str(tmp_path / "ci-data"))

        for i in range(5):
            state = WorkflowState(
                run_id=f"run-{i}",
                commit_sha=f"sha-{i}",
                repository="owner/repo",
                branch="main",
                actor="test",
                started_at=datetime.now(UTC),
            )
            storage.save_state(state)

        removed = storage.cleanup(keep_last=2)
        assert removed == 3
        assert len(storage.list_runs(limit=10)) == 2
