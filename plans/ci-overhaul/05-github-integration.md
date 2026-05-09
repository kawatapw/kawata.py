# Phase 5 — GitHub Integration

## Scope

GitHub API client for PR comments, check runs, and repository context. The `ci comment` command uses this to post and update PR comments with the CI summary.

## 1. Design Principles

1. **Find-or-create pattern** — On each run, look for an existing bot comment and update it. Never spam new comments.
2. **Graceful degradation** — If GitHub API is unavailable (no token, network error), log a warning and continue.
3. **Identifiable comments** — Bot comments include a hidden marker so they can be found and updated.
4. **Check runs** — Optionally create/update GitHub check runs for better PR status visibility.

## 2. GitHub API Client

### `src/ci_tool/github/__init__.py`

```python
"""GitHub API client."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class GitHubConfig:
    """Configuration for GitHub API access."""
    token: str = ""
    api_url: str = "https://api.github.com"
    repository: str = ""  # owner/repo

    @classmethod
    def from_environment(cls) -> GitHubConfig:
        """Build config from environment variables."""
        return cls(
            token=os.getenv("GITHUB_TOKEN", "") or os.getenv("INPUT_GITHUB_TOKEN", ""),
            api_url=os.getenv("GITHUB_API_URL", "https://api.github.com"),
            repository=os.getenv("GITHUB_REPOSITORY", ""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.token and self.repository)


class GitHubClient:
    """Async GitHub API client using httpx."""

    def __init__(self, config: GitHubConfig | None = None) -> None:
        self.config = config or GitHubConfig.from_environment()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.api_url,
                headers={
                    "Authorization": f"Bearer {self.config.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "ci-tool/1.0",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Make an API request, returning JSON response or None on error."""
        if not self.config.is_configured:
            return None

        client = await self._get_client()
        try:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            import sys
            print(
                f"GitHub API error: {e.response.status_code} {e.response.text}",
                file=sys.stderr,
            )
            return None
        except httpx.RequestError as e:
            import sys
            print(f"GitHub API request failed: {e}", file=sys.stderr)
            return None

    async def get_pull_requests_for_commit(
        self, sha: str
    ) -> list[dict[str, Any]]:
        """Find PRs associated with a commit SHA."""
        result = await self._request(
            "GET",
            f"/repos/{self.config.repository}/commits/{sha}/pulls",
        )
        return result or []

    async def create_check_run(
        self,
        name: str,
        head_sha: str,
        status: str = "in_progress",
        conclusion: str | None = None,
        output: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Create a GitHub check run."""
        data: dict[str, Any] = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
        }
        if conclusion:
            data["conclusion"] = conclusion
        if output:
            data["output"] = output

        return await self._request(
            "POST",
            f"/repos/{self.config.repository}/check-runs",
            json=data,
        )

    async def update_check_run(
        self,
        check_run_id: int,
        status: str,
        conclusion: str | None = None,
        output: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update an existing check run."""
        data: dict[str, Any] = {"status": status}
        if conclusion:
            data["conclusion"] = conclusion
        if output:
            data["output"] = output

        return await self._request(
            "PATCH",
            f"/repos/{self.config.repository}/check-runs/{check_run_id}",
            json=data,
        )
```

## 3. PR Comment Manager

### `src/ci_tool/github/comments.py`

```python
"""PR comment management — find, create, and update bot comments."""

from __future__ import annotations

import sys
from typing import Any

from ci_tool.github import GitHubClient, GitHubConfig


# Hidden marker to identify our bot comments
COMMENT_MARKER = "<!-- ci-tool-comment -->"
COMMENT_HEADER = f"{COMMENT_MARKER}\n## CI Results\n\n"


class PRCommentManager:
    """Manages PR comments for CI summaries.

    Uses a find-or-create pattern: on each run, looks for an existing
    comment with our marker and updates it. If none exists, creates one.
    """

    def __init__(self, client: GitHubClient | None = None) -> None:
        self.client = client or GitHubClient()

    async def __aenter__(self) -> PRCommentManager:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.client.close()

    async def post_or_update_comment(
        self,
        pr_number: int,
        body: str,
    ) -> dict[str, Any] | None:
        """Post a new comment or update existing one.

        Args:
            pr_number: PR number to comment on.
            body: Comment body markdown (without marker — we add it).

        Returns:
            API response dict, or None if API call failed.
        """
        full_body = COMMENT_HEADER + body

        # Check for existing comment
        existing = await self._find_existing_comment(pr_number)

        if existing:
            return await self._update_comment(existing["id"], full_body)
        else:
            return await self._create_comment(pr_number, full_body)

    async def _find_existing_comment(
        self, pr_number: int
    ) -> dict[str, Any] | None:
        """Find our existing bot comment on a PR."""
        page = 1
        while True:
            comments = await self.client._request(
                "GET",
                f"/repos/{self.client.config.repository}/issues/{pr_number}/comments",
                params={"per_page": 100, "page": page},
            )

            if not comments:
                break

            for comment in comments:
                if COMMENT_MARKER in (comment.get("body", "") or ""):
                    return comment

            if len(comments) < 100:
                break
            page += 1

        return None

    async def _create_comment(
        self, pr_number: int, body: str
    ) -> dict[str, Any] | None:
        """Create a new comment on a PR."""
        return await self.client._request(
            "POST",
            f"/repos/{self.client.config.repository}/issues/{pr_number}/comments",
            json={"body": body},
        )

    async def _update_comment(
        self, comment_id: int, body: str
    ) -> dict[str, Any] | None:
        """Update an existing comment."""
        return await self.client._request(
            "PATCH",
            f"/repos/{self.client.config.repository}/issues/comments/{comment_id}",
            json={"body": body},
        )

    async def find_pr_for_commit(
        self, sha: str
    ) -> int | None:
        """Find the PR number associated with a commit SHA."""
        prs = await self.client.get_pull_requests_for_commit(sha)
        if prs:
            return prs[0].get("number")
        return None
```

## 4. CLI Integration

The `ci comment` command in `cli.py`:

```python
# In cli.py — add the comment command

@app.command()
def comment(
    pr_number: Annotated[
        int | None, typer.Option("--pr", help="PR number (auto-detected if not provided)")
    ] = None,
    run_id: Annotated[
        str | None, typer.Option("--run-id", help="Run ID to comment about")
    = None,
) -> None:
    """Post/update PR comment with CI summary."""
    import asyncio

    cfg = get_config()
    ctx = get_context()
    storage = FileStorageBackend(cfg.file_storage.directory)

    if not cfg.comment.enabled:
        console.print("[yellow]PR comments disabled in config[/yellow]")
        return

    async def _post() -> None:
        async with PRCommentManager() as mgr:
            # Find PR number
            pr = pr_number
            if pr is None and ctx.is_github_actions:
                pr = await mgr.find_pr_for_commit(ctx.commit_sha)

            if pr is None:
                err_console.print("[red]Could not determine PR number[/red]")
                raise typer.Exit(1)

            # Load run state
            rid = run_id or ctx.run_id
            state = storage.load_state(rid)
            if state is None:
                err_console.print(f"[red]No state found for run: {rid}[/red]")
                raise typer.Exit(1)

            # Build summary
            from ci_tool.output.summary import SummaryRenderer
            renderer = SummaryRenderer(config=cfg)

            # Build a RunResult from state for rendering
            from ci_tool.runner.models import JobRunResult, RunResult, JobStatus
            from ci_tool.storage.models import JobStatus as WfJobStatus

            status_map = {
                WfJobStatus.PASS: JobStatus.PASS,
                WfJobStatus.FAIL: JobStatus.FAIL,
                WfJobStatus.SKIPPED: JobStatus.SKIPPED,
            }

            run_result = RunResult(
                run_id=state.run_id,
                started_at=state.started_at,
                completed_at=state.completed_at,
                total_duration_seconds=state.total_duration_seconds,
            )
            for name, j in state.jobs.items():
                run_result.jobs[name] = JobRunResult(
                    name=name,
                    status=status_map.get(j.status, JobStatus.FAIL),
                    duration_seconds=j.duration_seconds,
                    summary_line=j.summary_line,
                    report_path=j.report_path,
                    parser_name=j.parser_name,
                )

            # Parse reports for detailed results
            from ci_tool.output.summary import parse_reports_for_run
            parsed = parse_reports_for_run(run_result)

            body = renderer.render(run_result, parsed)

            result = await mgr.post_or_update_comment(pr, body)
            if result:
                console.print(f"[green]Posted comment to PR #{pr}[/green]")
            else:
                err_console.print("[red]Failed to post comment[/red]")
                raise typer.Exit(1)

    asyncio.run(_post())
```

## 5. Tests

### `tests/test_github.py`

```python
"""Tests for GitHub integration."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from ci_tool.github import GitHubClient, GitHubConfig
from ci_tool.github.comments import PRCommentManager, COMMENT_MARKER


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
    async def test_create_new_comment(
        self, client: GitHubClient
    ) -> None:
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
    async def test_update_existing_comment(
        self, client: GitHubClient
    ) -> None:
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
    async def test_find_pr_for_commit(
        self, client: GitHubClient
    ) -> None:
        route = respx.get(
            "https://api.github.com/repos/owner/repo/commits/abc123/pulls",
        ).mock(return_value=Response(200, json=[{"number": 7}]))

        mgr = PRCommentManager(client)
        pr = await mgr.find_pr_for_commit("abc123")

        assert pr == 7

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_pr_for_commit(
        self, client: GitHubClient
    ) -> None:
        route = respx.get(
            "https://api.github.com/repos/owner/repo/commits/abc123/pulls",
        ).mock(return_value=Response(200, json=[]))

        mgr = PRCommentManager(client)
        pr = await mgr.find_pr_for_commit("abc123")

        assert pr is None
