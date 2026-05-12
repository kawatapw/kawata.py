"""Tests for job runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from ci_tool.config import Config
from ci_tool.config import JobConfig
from ci_tool.context import Context
from ci_tool.runner import DependencyGraph
from ci_tool.runner import JobRunner
from ci_tool.runner.models import JobRunConfig
from ci_tool.runner.models import JobStatus
from ci_tool.runner.models import RunMode
from ci_tool.storage.file_backend import FileStorageBackend


class TestDependencyGraph:
    def test_no_dependencies(self) -> None:
        jobs = {
            "a": JobRunConfig(name="a", command="echo a"),
            "b": JobRunConfig(name="b", command="echo b"),
        }
        graph = DependencyGraph(jobs)
        levels = graph.execution_levels()
        assert len(levels) == 1
        assert set(levels[0]) == {"a", "b"}

    def test_linear_chain(self) -> None:
        jobs = {
            "a": JobRunConfig(name="a", command="echo a"),
            "b": JobRunConfig(name="b", command="echo b", depends_on=["a"]),
            "c": JobRunConfig(name="c", command="echo c", depends_on=["b"]),
        }
        graph = DependencyGraph(jobs)
        levels = graph.execution_levels()
        assert len(levels) == 3
        assert levels[0] == ["a"]
        assert levels[1] == ["b"]
        assert levels[2] == ["c"]

    def test_diamond(self) -> None:
        jobs = {
            "build": JobRunConfig(name="build", command="echo build"),
            "test": JobRunConfig(
                name="test", command="echo test", depends_on=["build"]
            ),
            "lint": JobRunConfig(
                name="lint", command="echo lint", depends_on=["build"]
            ),
            "deploy": JobRunConfig(
                name="deploy", command="echo deploy", depends_on=["test", "lint"]
            ),
        }
        graph = DependencyGraph(jobs)
        levels = graph.execution_levels()
        assert len(levels) == 3
        assert levels[0] == ["build"]
        assert set(levels[1]) == {"test", "lint"}
        assert levels[2] == ["deploy"]

    def test_missing_dependency(self) -> None:
        jobs = {
            "a": JobRunConfig(name="a", command="echo a", depends_on=["missing"]),
        }
        with pytest.raises(ValueError, match="unknown job"):
            DependencyGraph(jobs)

    def test_circular_dependency(self) -> None:
        jobs = {
            "a": JobRunConfig(name="a", command="echo a", depends_on=["b"]),
            "b": JobRunConfig(name="b", command="echo b", depends_on=["a"]),
        }
        with pytest.raises(ValueError, match="Circular"):
            DependencyGraph(jobs)


class TestJobRunner:
    @pytest.fixture
    def tmp_storage(self, tmp_path: Path) -> FileStorageBackend:
        return FileStorageBackend(directory=str(tmp_path / "ci-data"))

    @pytest.fixture
    def base_context(self) -> Context:
        ctx = Context.detect()
        return ctx

    @pytest.mark.asyncio
    async def test_run_simple_job(
        self, tmp_storage: FileStorageBackend, base_context: Context
    ) -> None:
        config = Config()
        config.jobs["hello"] = JobConfig(
            name="hello",
            command="echo hello",
        )
        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.SERIAL)
        result = await runner.run()

        assert "hello" in result.jobs
        assert result.jobs["hello"].status == JobStatus.PASS
        assert result.jobs["hello"].exit_code == 0
        assert result.overall_status == JobStatus.PASS

    @pytest.mark.asyncio
    async def test_run_failing_job(
        self, tmp_storage: FileStorageBackend, base_context: Context
    ) -> None:
        config = Config()
        config.jobs["fail"] = JobConfig(
            name="fail",
            command="exit 1",
        )
        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.SERIAL)
        result = await runner.run()

        assert result.jobs["fail"].status == JobStatus.FAIL
        assert result.overall_status == JobStatus.FAIL

    @pytest.mark.asyncio
    async def test_dependency_blocks_on_failure(
        self, tmp_storage: FileStorageBackend, base_context: Context
    ) -> None:
        config = Config()
        config.jobs["first"] = JobConfig(name="first", command="exit 1")
        config.jobs["second"] = JobConfig(
            name="second", command="echo should not run", depends_on=["first"]
        )
        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.SERIAL)
        result = await runner.run()

        assert result.jobs["first"].status == JobStatus.FAIL
        assert result.jobs["second"].status == JobStatus.SKIPPED
        assert result.jobs["second"].skipped is True

    @pytest.mark.asyncio
    async def test_parallel_execution(
        self, tmp_storage: FileStorageBackend, base_context: Context
    ) -> None:
        config = Config()
        config.jobs["a"] = JobConfig(name="a", command="sleep 0.1 && echo a")
        config.jobs["b"] = JobConfig(name="b", command="sleep 0.1 && echo b")
        config.jobs["c"] = JobConfig(name="c", command="sleep 0.1 && echo c")

        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.PARALLEL)
        result = await runner.run()

        # All should pass
        for name in ["a", "b", "c"]:
            assert result.jobs[name].status == JobStatus.PASS

        # Total time should be ~0.1s (parallel), not ~0.3s (serial)
        assert result.total_duration_seconds < 0.25

    @pytest.mark.asyncio
    async def test_allow_failure(
        self, tmp_storage: FileStorageBackend, base_context: Context
    ) -> None:
        config = Config()
        config.jobs["flaky"] = JobConfig(
            name="flaky", command="exit 1", allow_failure=True
        )
        config.jobs["after"] = JobConfig(
            name="after", command="echo ok", depends_on=["flaky"]
        )
        runner = JobRunner(config, base_context, tmp_storage, mode=RunMode.SERIAL)
        result = await runner.run()

        # flaky should be marked PASS (allowed failure)
        assert result.jobs["flaky"].status == JobStatus.PASS
        # after should still run
        assert result.jobs["after"].status == JobStatus.PASS
        # overall should pass
        assert result.overall_status == JobStatus.PASS
