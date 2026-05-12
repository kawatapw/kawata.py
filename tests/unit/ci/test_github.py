"""Tests for GitHub integration."""

from __future__ import annotations

import pytest
import respx
from ci_tool.github import GitHubClient
from ci_tool.github import GitHubConfig
from ci_tool.github.comments import COMMENT_MARKER
from ci_tool.github.comments import PRCommentManager
from httpx import Response


@pytest.fixture
def github_config() -> GitHubConfig:
    return GitHubConfig(
        token="test-token",
        api_url="https://api.github.com",
        repository="owner/repo",
    )


@pytest.fixture
def client(github_config: GitHubConfig) -> GitHubClient:
    return GitHubClient(github_config)


class TestGitHubConfig:
    def test_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "env-owner/env-repo")

        config = GitHubConfig.from_environment()
        assert config.token == "env-token"
        assert config.repository == "env-owner/env-repo"
        assert config.is_configured is True

    def test_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

        config = GitHubConfig.from_environment()
        assert config.is_configured is False


class TestPRCommentManager:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_new_comment(self, client: GitHubClient) -> None:
        # Mock: no existing comments
        route_existing = respx.get(
            "https://api.github.com/repos/owner/repo/issues/42/comments",
        ).mock(return_value=Response(200, json=[]))

        # Mock: create comment
        route_create = respx.post(
            "https://api.github.com/repos/owner/repo/issues/42/comments",
        ).mock(return_value=Response(201, json={"id": 123, "body": "test"}))

        mgr = PRCommentManager(client)
        result = await mgr.post_or_update_comment(42, "test body")

        assert result is not None
        assert result["id"] == 123
        assert route_create.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_existing_comment(self, client: GitHubClient) -> None:
        # Mock: existing comment with marker
        existing_comment = {
            "id": 99,
            "body": f"{COMMENT_MARKER}\nold content",
        }
        route_existing = respx.get(
            "https://api.github.com/repos/owner/repo/issues/42/comments",
        ).mock(return_value=Response(200, json=[existing_comment]))

        # Mock: update comment
        route_update = respx.patch(
            "https://api.github.com/repos/owner/repo/issues/comments/99",
        ).mock(return_value=Response(200, json={"id": 99}))

        mgr = PRCommentManager(client)
        result = await mgr.post_or_update_comment(42, "new body")

        assert result is not None
        assert route_update.called

        # Verify the update included the marker
        update_body = route_update.calls[0].request.content
        assert COMMENT_MARKER.encode() in update_body

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_pr_for_commit(self, client: GitHubClient) -> None:
        route = respx.get(
            "https://api.github.com/repos/owner/repo/commits/abc123/pulls",
        ).mock(return_value=Response(200, json=[{"number": 7}]))

        mgr = PRCommentManager(client)
        pr = await mgr.find_pr_for_commit("abc123")

        assert pr == 7

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_pr_for_commit(self, client: GitHubClient) -> None:
        route = respx.get(
            "https://api.github.com/repos/owner/repo/commits/abc123/pulls",
        ).mock(return_value=Response(200, json=[]))

        mgr = PRCommentManager(client)
        pr = await mgr.find_pr_for_commit("abc123")

        assert pr is None
