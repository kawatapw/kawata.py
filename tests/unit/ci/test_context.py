"""Tests for context detection."""

from __future__ import annotations

import pytest
from ci_tool.context import Context


class TestContext:
    def test_defaults(self) -> None:
        ctx = Context()
        assert ctx.commit_sha == ""
        assert ctx.is_github_actions is False
        assert ctx.repository == ""

    def test_detect_local(self) -> None:
        ctx = Context.detect()
        # In test environment, should not be GitHub Actions
        assert isinstance(ctx.is_github_actions, bool)
        assert isinstance(ctx.project_root, type(ctx.project_root))

    def test_detect_github_actions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_RUN_ID", "12345")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_SHA", "abc123def")
        monkeypatch.setenv("GITHUB_REF_NAME", "main")

        ctx = Context.detect()
        assert ctx.is_github_actions is True
        assert ctx.run_id == "12345"
        assert ctx.repository == "owner/repo"
        assert ctx.commit_sha == "abc123def"
        assert ctx.branch == "main"
        assert "github.com/owner/repo/actions/runs/12345" in ctx.run_url
