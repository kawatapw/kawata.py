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

    async def get_pull_requests_for_commit(self, sha: str) -> list[dict[str, Any]]:
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
