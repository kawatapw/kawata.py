# Phase 6 — Message Template System

## Scope

Implement a flexible message template system with variable substitution, default templates, and per-guild overrides.

## 1. Template Service

### 1.1 `app/discord/templates.py`

```python
"""Message template system with variable substitution."""

from __future__ import annotations

import re
from typing import Any
from typing import TypedDict

import hikari

from app.discord.constants import NOTIFICATION_COLORS
from app.discord.constants import NotificationType
from app.discord.repositories import discord_repositories
from app.logging import Ansi
from app.logging import log


class TemplateContext(TypedDict, total=False):
    """Context variables for template rendering."""

    # Common
    title: str
    description: str
    color: int
    timestamp: str

    # Map notifications
    map_title: str
    map_artist: str
    map_creator: str
    map_url: str
    map_cover_url: str
    old_status: str
    new_status: str
    difficulties: list[dict[str, Any]]

    # GitHub notifications
    repo_owner: str
    repo_name: str
    repo_url: str
    branch: str
    commits: list[dict[str, Any]]
    pusher_name: str
    pusher_url: str
    compare_url: str
    workflow_name: str
    workflow_url: str
    jobs: list[dict[str, Any]]

    # Announcements
    announcement_type: str
    announcement_title: str
    announcement_body: str
    author_name: str
    author_url: str
    image_url: str

    # Admin actions
    admin_name: str
    admin_url: str
    target_name: str
    target_url: str
    action: str
    reason: str


class RenderedMessage(TypedDict):
    """Rendered message ready to send."""

    content: str | None
    embed: dict[str, Any] | None
    components: list[dict[str, Any]] | None


class TemplateRenderer:
    """Renders message templates with variable substitution."""

    # Pattern for variable substitution: {variable_name}
    VAR_PATTERN = re.compile(r"\{(\w+)\}")

    def __init__(self) -> None:
        self._default_templates: dict[str, dict[str, Any]] = {}
        self._load_default_templates()

    def _load_default_templates(self) -> None:
        """Load default templates."""
        self._default_templates = {
            "map_ranked": {
                "embed": {
                    "title": "🟢 Map Ranked: {map_title}",
                    "description": "By **{map_artist}** — Mapped by **{map_creator}**",
                    "color": NOTIFICATION_COLORS[NotificationType.MAP_RANKED],
                    "thumbnail": "{map_cover_url}",
                    "fields": [
                        {"name": "Status", "value": "{old_status} → {new_status}", "inline": True},
                    ],
                },
                "components": [
                    {
                        "type": "select",
                        "custom_id": "map_diff_select:{map_id}",
                        "placeholder": "Select a difficulty...",
                        "options": "{difficulty_options}",
                    }
                ],
            },
            "map_qualified": {
                "embed": {
                    "title": "🔵 Map Qualified: {map_title}",
                    "description": "By **{map_artist}** — Mapped by **{map_creator}**",
                    "color": NOTIFICATION_COLORS[NotificationType.MAP_QUALIFIED],
                    "thumbnail": "{map_cover_url}",
                    "fields": [
                        {"name": "Status", "value": "{old_status} → {new_status}", "inline": True},
                    ],
                },
                "components": [
                    {
                        "type": "select",
                        "custom_id": "map_diff_select:{map_id}",
                        "placeholder": "Select a difficulty...",
                        "options": "{difficulty_options}",
                    }
                ],
            },
            "map_loved": {
                "embed": {
                    "title": "💖 Map Loved: {map_title}",
                    "description": "By **{map_artist}** — Mapped by **{map_creator}**",
                    "color": NOTIFICATION_COLORS[NotificationType.MAP_LOVED],
                    "thumbnail": "{map_cover_url}",
                    "fields": [
                        {"name": "Status", "value": "{old_status} → {new_status}", "inline": True},
                    ],
                },
                "components": [
                    {
                        "type": "select",
                        "custom_id": "map_diff_select:{map_id}",
                        "placeholder": "Select a difficulty...",
                        "options": "{difficulty_options}",
                    }
                ],
            },
            "github_push": {
                "embed": {
                    "title": "📦 Push to {repo_owner}/{repo_name}",
                    "description": "{commit_summary}",
                    "color": NOTIFICATION_COLORS[NotificationType.GITHUB_PUSH],
                    "fields": [
                        {"name": "Branch", "value": "`{branch}`", "inline": True},
                        {"name": "Commits", "value": "{commit_count}", "inline": True},
                        {"name": "Pusher", "value": "[{pusher_name}]({pusher_url})", "inline": True},
                    ],
                },
                "components": [
                    {
                        "type": "button",
                        "style": "link",
                        "label": "View on GitHub",
                        "url": "{compare_url}",
                    }
                ],
            },
            "github_workflow": {
                "embed": {
                    "title": "⚙️ Workflow: {workflow_name}",
                    "description": "{job_summary}",
                    "color": NOTIFICATION_COLORS[NotificationType.GITHUB_WORKFLOW],
                    "fields": [
                        {"name": "Repository", "value": "[{repo_owner}/{repo_name}]({repo_url})", "inline": True},
                        {"name": "Status", "value": "{workflow_status}", "inline": True},
                    ],
                },
                "components": [
                    {
                        "type": "select",
                        "custom_id": "github_job_select:{run_id}",
                        "placeholder": "View job summary...",
                        "options": "{job_options}",
                    }
                ],
            },
            "announcement_maintenance": {
                "embed": {
                    "title": "🔧 {announcement_title}",
                    "description": "{announcement_body}",
                    "color": NOTIFICATION_COLORS[NotificationType.ANNOUNCEMENT_MAINTENANCE],
                    "image": "{image_url}",
                    "footer": "Posted by {author_name}",
                },
            },
            "announcement_event": {
                "embed": {
                    "title": "🎉 {announcement_title}",
                    "description": "{announcement_body}",
                    "color": NOTIFICATION_COLORS[NotificationType.ANNOUNCEMENT_EVENT],
                    "image": "{image_url}",
                    "footer": "Posted by {author_name}",
                },
            },
            "announcement_update": {
                "embed": {
                    "title": "📢 {announcement_title}",
                    "description": "{announcement_body}",
                    "color": NOTIFICATION_COLORS[NotificationType.ANNOUNCEMENT_UPDATE],
                    "image": "{image_url}",
                    "footer": "Posted by {author_name}",
                },
            },
            "admin_restrict": {
                "embed": {
                    "title": "🔴 User Restricted",
                    "description": "**{admin_name}** restricted **{target_name}**",
                    "color": NOTIFICATION_COLORS[NotificationType.ADMIN_RESTRICT],
                    "fields": [
                        {"name": "Reason", "value": "{reason}", "inline": False},
                    ],
                },
            },
            "admin_unrestrict": {
                "embed": {
                    "title": "🟢 User Unrestricted",
                    "description": "**{admin_name}** unrestricted **{target_name}**",
                    "color": NOTIFICATION_COLORS[NotificationType.ADMIN_UNRESTRICT],
                    "fields": [
                        {"name": "Reason", "value": "{reason}", "inline": False},
                    ],
                },
            },
        }

    async def render(
        self,
        template_name: str,
        context: TemplateContext,
        guild_id: int | None = None,
    ) -> RenderedMessage:
        """
        Render a template with the given context.

        Args:
            template_name: Name of the template to render.
            context: Variables to substitute.
            guild_id: Guild ID for guild-specific template override.

        Returns:
            Rendered message with content, embed, and components.
        """
        # Try guild-specific template first
        template = None
        if guild_id:
            template = await discord_repositories.template.get(
                name=template_name,
                guild_id=guild_id,
            )

        # Fall back to default template
        if not template:
            template_data = self._default_templates.get(template_name)
            if not template_data:
                log(f"Template not found: {template_name}", Ansi.LRED)
                return {"content": None, "embed": None, "components": None}
        else:
            template_data = template["template_data"]

        # Render the template
        return self._render_template_data(template_data, context)

    def _render_template_data(
        self,
        template_data: dict[str, Any],
        context: TemplateContext,
    ) -> RenderedMessage:
        """Render template data with context variables."""
        result: RenderedMessage = {
            "content": None,
            "embed": None,
            "components": None,
        }

        # Render content
        if "content" in template_data:
            result["content"] = self._substitute_variables(
                template_data["content"],
                context,
            )

        # Render embed
        if "embed" in template_data:
            result["embed"] = self._render_embed(
                template_data["embed"],
                context,
            )

        # Render components
        if "components" in template_data:
            result["components"] = self._render_components(
                template_data["components"],
                context,
            )

        return result

    def _render_embed(
        self,
        embed_template: dict[str, Any],
        context: TemplateContext,
    ) -> dict[str, Any]:
        """Render an embed template."""
        embed: dict[str, Any] = {}

        # Simple string fields
        for key in ("title", "description", "thumbnail", "image", "footer", "url"):
            if key in embed_template:
                value = self._substitute_variables(embed_template[key], context)
                if value:
                    embed[key] = value

        # Color
        if "color" in embed_template:
            color = embed_template["color"]
            if isinstance(color, str):
                color = self._substitute_variables(color, context)
                if color:
                    embed[
