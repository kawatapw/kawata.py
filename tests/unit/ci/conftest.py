"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_storage(tmp_path: Path):
    from ci_tool.storage.file_backend import FileStorageBackend

    return FileStorageBackend(directory=str(tmp_path / "ci-data"))


@pytest.fixture
def base_context():
    from ci_tool.context import Context

    return Context.detect()
