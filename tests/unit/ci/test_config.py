"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

from ci_tool.config import Config


class TestConfig:
    def test_defaults(self) -> None:
        cfg = Config()
        assert cfg.storage_backend == "file"
        assert cfg.file_storage.directory == ".ci-data"
        assert cfg.summary.include_jobs is True
        assert cfg.summary.max_failures_shown == 5
        assert cfg.comment.enabled is True

    def test_load_defaults_when_no_pyproject(self, tmp_path: Path) -> None:
        cfg = Config.load(project_root=tmp_path)
        assert cfg.storage_backend == "file"
        assert len(cfg.jobs) == 0

    def test_load_from_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """[tool.ci]
storage_backend = "file"

[tool.ci.storage.file]
directory = ".custom-ci-data"

[tool.ci.summary]
max_failures_shown = 10

[tool.ci.jobs.test]
command = "uv run pytest"
report = "reports/junit.xml"
parser = "pytest"

[tool.ci.jobs.lint]
command = "uv run ruff check ."
"""
        )
        cfg = Config.load(project_root=tmp_path)
        assert cfg.file_storage.directory == ".custom-ci-data"
        assert cfg.summary.max_failures_shown == 10
        assert "test" in cfg.jobs
        assert cfg.jobs["test"].command == "uv run pytest"
        assert cfg.jobs["test"].parser == "pytest"
        assert "lint" in cfg.jobs

    def test_generate_default_toml(self) -> None:
        cfg = Config()
        toml_str = cfg.generate_default_toml()
        assert "[tool.ci]" in toml_str
        assert "storage_backend" in toml_str
        assert "[tool.ci.jobs]" in toml_str
