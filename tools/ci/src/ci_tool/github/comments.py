"""PR comment management — find, create, and update bot comments."""

from __future__ import annotations

from typing import Any

from ci_tool.github import GitHubClient

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

    async def _find_existing_comment(self, pr_number: int) -> dict[str, Any] | None:
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

    async def _create_comment(self, pr_number: int, body: str) -> dict[str, Any] | None:
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

    async def find_pr_for_commit(self, sha: str) -> int | None:
        """Find the PR number associated with a commit SHA."""
        prs = await self.client.get_pull_requests_for_commit(sha)
        if prs:
            return prs[0].get("number")
        return None
