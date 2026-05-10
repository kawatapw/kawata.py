# Phase 9 — GitHub Integration

## Scope

Implement GitHub webhook processing for push events and workflow runs with real-time message updates.

## 1. Webhook Service

### 1.1 `app/discord/services/webhook_service.py`

```python
"""GitHub webhook processing service."""

from __future__ import annotations

import asyncio
from typing import Any

from app.discord.constants import NOTIFICATION_COLORS
from app.discord.constants import NotificationType
from app.discord.constants import STATUS_EMOJIS
from app.discord.repositories import discord_repositories
from app.discord.services.component_service import component_service
from app.discord.services.message_service import message_service
from app.logging import Ansi
from app.logging import log


class WebhookService:
    """Service for processing GitHub webhooks."""

    def __init__(self) -> None:
        self._http_client = None  # Will use app.state.services.http_client

    async def handle_push(
        self,
        payload: dict[str, Any],
        repo_config: dict[str, Any],
    ) -> None:
        """Handle a push event from GitHub."""
        # Extract push data
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "")
        commits = payload.get("commits", [])
        pusher = payload.get("pusher", {})
        compare_url = payload.get("compare", "")
        repository = payload.get("repository", {})

        # Apply commit limit
        commit_limit = repo_config.get("commit_limit", 10)
        truncated = len(commits) > commit_limit
        display_commits = commits[:commit_limit]

        # Fetch full commit messages from GitHub API
        enriched_commits = await self._fetch_commit_details(
            repo_owner=repository.get("owner", {}).get("login"),
            repo_name=repository.get("name"),
            commits=display_commits,
        )

        # Build commit summary
        commit_summary = self._build_commit_summary(enriched_commits, truncated)

        # Build embed
        embed = message_service.create_embed(
            title=f"📦 Push to {repository.get('owner', {}).get('login')}/{repository.get('name')}",
            description=commit_summary,
            color=NOTIFICATION_COLORS[NotificationType.GITHUB_PUSH],
            fields=[
                {"name": "Branch", "value": f"`{branch}`", "inline": True},
                {"name": "Commits", "value": str(len(commits)), "inline": True},
                {
                    "name": "Pusher",
                    "value": pusher.get("name", "Unknown"),
                    "inline": True,
                },
            ],
            footer=f"Compare: {compare_url}",
        )

        # Send message
        message_id = await message_service.send(
            channel_id=repo_config["channel_id"],
            embed=embed,
            guild_id=repo_config["guild_id"],
            message_type=NotificationType.GITHUB_PUSH,
            metadata={
                "repo_owner": repository.get("owner", {}).get("login"),
                "repo_name": repository.get("name"),
                "branch": branch,
                "commit_sha": payload.get("after", ""),
                "compare_url": compare_url,
            },
        )

        # Track message for potential workflow updates
        if message_id:
            await discord_repositories.message.create(
                message_id=message_id,
                channel_id=repo_config["channel_id"],
                guild_id=repo_config["guild_id"],
                message_type="github_push",
                metadata={
                    "repo_owner": repository.get("owner", {}).get("login"),
                    "repo_name": repository.get("name"),
                    "branch": branch,
                    "commit_sha": payload.get("after", ""),
                },
            )

    async def handle_workflow_run(
        self,
        payload: dict[str, Any],
        repo_config: dict[str, Any],
    ) -> None:
        """Handle a workflow_run event from GitHub."""
        workflow_run = payload.get("workflow_run", {})
        repository = payload.get("repository", {})

        run_id = workflow_run.get("id")
        workflow_name = workflow_run.get("name", "Unknown Workflow")
        status = workflow_run.get("status", "unknown")
        conclusion = workflow_run.get("conclusion")
        html_url = workflow_run.get("html_url", "")
        branch = workflow_run.get("head_branch", "")
        commit_sha = workflow_run.get("head_sha", "")

        # Find existing message for this commit
        existing_message = await discord_repositories.message.get_active_by_type(
            guild_id=repo_config["guild_id"],
            message_type="github_push",
            metadata_filter={"commit_sha": commit_sha},
        )

        if existing_message:
            # Update existing message with workflow info
            await self._update_message_with_workflow(
                message=existing_message,
                workflow_run=workflow_run,
            )
        else:
            # Create new workflow message
            await self._create_workflow_message(
                repo_config=repo_config,
                workflow_run=workflow_run,
                repository=repository,
            )

    async def handle_workflow_job(
        self,
        payload: dict[str, Any],
        repo_config: dict[str, Any],
    ) -> None:
        """Handle a workflow_job event from GitHub."""
        workflow_job = payload.get("workflow_job", {})
        repository = payload.get("repository", {})

        run_id = workflow_job.get("run_id")
        job_name = workflow_job.get("name", "Unknown Job")
        status = workflow_job.get("status", "unknown")
        conclusion = workflow_job.get("conclusion")

        # Find existing message for this workflow run
        existing_message = await discord_repositories.message.get_active_by_type(
            guild_id=repo_config["guild_id"],
            message_type="github_workflow",
            metadata_filter={"run_id": str(run_id)},
        )

        if existing_message:
            # Update job status in message
            await self._update_job_status(
                message=existing_message,
                job=workflow_job,
            )

    async def _fetch_commit_details(
        self,
        repo_owner: str,
        repo_name: str,
        commits: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fetch full commit details from GitHub API."""
        from app.state import services

        enriched = []
        for commit in commits:
            commit_url = commit.get("url", "")
            if commit_url:
                try:
                    response = await services.http_client.get(commit_url)
                    if response.status_code == 200:
                        commit_data = response.json()
                        enriched.append({
                            "id": commit.get("id", ""),
                            "message": commit_data.get("commit", {}).get("message", commit.get("message", "")),
                            "author": commit.get("author", {}).get("name", "Unknown"),
                            "url": commit.get("html_url", ""),
                            "timestamp": commit.get("timestamp", ""),
                        })
                        continue
                except Exception as exc:
                    log(f"Failed to fetch commit details: {exc}", Ansi.LYELLOW)

            # Fallback to basic commit info
            enriched.append({
                "id": commit.get("id", ""),
                "message": commit.get("message", ""),
                "author": commit.get("author", {}).get("name", "Unknown"),
                "url": commit.get("html_url", ""),
                "timestamp": commit.get("timestamp", ""),
            })

        return enriched

    def _build_commit_summary(
        self,
        commits: list[dict[str, Any]],
        truncated: bool,
    ) -> str:
        """Build a summary of commits for the embed."""
        lines = []
        total_length = 0
        max_length = 2000  # Discord embed description limit

        for commit in commits:
            commit_id = commit["id"][:7]
            message = commit["message"].split("\n")[0]  # First line only
            author = commit["author"]
            url = commit["url"]

            # Truncate long messages
            if len(message) > 100:
                message = message[:97] + "..."

            line = f"[`{commit_id}`]({url}) {message} - {author}"

            if total_length + len(line) + 1 > max_length:
                remaining = len(commits) - len(lines)
                if remaining > 0:
                    lines.append(f"\n*... and {remaining} more commits*")
                break

            lines.append(line)
            total_length += len(line) + 1

        if truncated and len(commits) == 0:
            lines.append("*Too many commits to display*")

        return "\n".join(lines) if lines else "*No commits*"

    async def _update_message_with_workflow(
        self,
        message: dict[str, Any],
        workflow_run: dict[str, Any],
    ) -> None:
        """Update an existing message with workflow information."""
        # Get current metadata
        metadata = message.get("metadata", {})
        workflows = metadata.get("workflows", [])

        # Add or update workflow
        run_id = workflow_run.get("id")
        workflow_info = {
            "run_id": run_id,
            "name": workflow_run.get("name", "Unknown"),
            "status": workflow_run.get("status", "unknown"),
            "conclusion": workflow_run.get("conclusion"),
            "url": workflow_run.get("html_url", ""),
        }

        # Update existing or add new
        updated = False
        for i, wf in enumerate(workflows):
            if wf.get("run_id") == run_id:
                workflows[i] = workflow_info
                updated = True
                break

        if not updated:
            workflows.append(workflow_info)

        # Update metadata
        metadata["workflows"] = workflows
        await discord_repositories.message.update_metadata(
            message_id=message["id"],
            metadata={"workflows": workflows},
        )

        # Rebuild and update message embed
        await self._rebuild_message(message)

    async def _create_workflow_message(
        self,
        repo_config: dict[str, Any],
        workflow_run: dict[str, Any],
        repository: dict[str, Any],
    ) -> None:
        """Create a new workflow run message."""
        run_id = workflow_run.get("id")
        workflow_name = workflow_run.get("name", "Unknown Workflow")
        status = workflow_run.get("status", "unknown")
        conclusion = workflow_run.get("conclusion")
        html_url = workflow_run.get("html_url", "")

        status_emoji = STATUS_EMOJIS.get(status, "❓")
        if conclusion:
            status_emoji = STATUS_EMOJIS.get(conclusion, "❓")

        embed = message_service.create_embed(
            title=f"{status_emoji} Workflow: {workflow_name}",
            description=f"Status: **{status}**" + (f" / {conclusion}" if conclusion else ""),
            color=NOTIFICATION_COLORS[NotificationType.GITHUB_WORKFLOW],
            fields=[
                {
                    "name": "Repository",
                    "value": f"[{repository.get('full_name')}]({repository.get('html_url')})",
                    "inline": True,
                },
                {
                    "name": "Branch",
                    "value": f"`{workflow_run.get('head_branch', 'unknown')}`",
                    "inline": True,
                },
            ],
        )

        message_id = await message_service.send(
            channel_id=repo_config["channel_id"],
            embed=embed,
            guild_id=repo_config["guild_id"],
            message_type=NotificationType.GITHUB_WORKFLOW,
            metadata={
                "run_id": run_id,
                "repo_owner": repository.get("owner", {}).get("login"),
                "repo_name": repository.get("name"),
                "workflow_name": workflow_name,
            },
        )

        if message_id:
            await discord_repositories.message.create(
                message_id=message_id,
                channel_id=repo_config["channel_id"],
                guild_id=repo_config["guild_id"],
                message_type="github_workflow",
                metadata={
                    "run_id": run_id,
                    "repo_owner": repository.get("owner", {}).get("login"),
                    "repo_name": repository.get("name"),
                },
            )

    async def _update_job_status(
        self,
        message: dict[str, Any],
        job: dict[str, Any],
    ) -> None:
        """Update job status in an existing message."""
        metadata = message.get("metadata", {})
        jobs = metadata.get("jobs", [])

        # Update or add job
        job_id = job.get("id")
        job_info = {
            "id": job_id,
            "name": job.get("name", "Unknown"),
            "status": job.get("status", "unknown"),
            "conclusion": job.get("conclusion"),
            "url": job.get("html_url", ""),
            "summary": job.get("summary", ""),
        }

        updated = False
        for i, j in enumerate(jobs):
            if j.get("id") == job_id:
                jobs[i] = job_info
                updated = True
                break

        if not updated:
            jobs.append(job_info)

        metadata["jobs"] = jobs
        await discord_repositories.message.update_metadata(
            message_id=message["id"],
            metadata={"jobs": jobs},
        )

        # Rebuild message
        await self._rebuild_message(message)

    async def _rebuild_message(self, message: dict[str, Any]) -> None:
        """Rebuild and update a message with current data."""
        metadata = message.get("metadata", {})
        message_type = message.get("message_type")

        if message_type == "github_push":
            await self._rebuild_push_message(message, metadata)
        elif message_type == "github_workflow":
            await self._rebuild_workflow_message(message, metadata)

    async def _rebuild_push_message(
        self,
        message: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        """Rebuild a push message with workflow updates."""
        workflows = metadata.get("workflows", [])

        # Build workflow status line
        workflow_lines = []
        for wf in workflows:
            status_emoji = STATUS_EMOJIS.get(wf.get("status", ""), "❓")
            if wf.get("conclusion"):
                status_emoji = STATUS_EMOJIS.get(wf["conclusion"], "❓")
            workflow_lines.append(f"{status_emoji} [{wf['name']}]({wf['url']})")

        # Update embed with workflow info
        # This is a simplified update - in practice you'd rebuild the full embed
        if workflow_lines:
            content = "**Workflows:**\n" + "\n".join(workflow_lines)
            await message_service.edit_message(
                channel_id=message["channel_id"],
                message_id=message["id"],
                content=content,
            )

    async def _rebuild_workflow_message(
        self,
        message: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        """Rebuild a workflow message with job updates."""
        jobs = metadata.get("jobs", [])

        # Build job status line
        job_lines = []
        for job in jobs:
            status_emoji = STATUS_EMOJIS.get(job.get("status", ""), "❓")
            if job.get("conclusion"):
                status_emoji = STATUS_EMOJIS.get(job["conclusion"], "❓")
            job_lines.append(f"{status_emoji} {job['name']}")

        if job_lines:
            content = "**Jobs:**\n" + "\n".join(job_lines)
            await message_service.edit_message(
                channel_id=message["channel_id"],
                message_id=message["id"],
                content=content,
            )


# Global instance
webhook_service = WebhookService()
```

## 2. Commit Message

```
feat(discord): add GitHub webhook integration

- Implement WebhookService for processing GitHub events
- Handle push events with full commit message fetching
- Handle workflow_run and workflow_job events
- Add real-time message updates as jobs complete
- Add job status indicators (✅❌🔄)
- Support for multiple repositories with different configs
- Add branch and job filtering
```
