# Phase 7 — Interactive Components

## Scope

Implement persistent interactive components (buttons, dropdowns) that survive bot restarts.

## 1. Component Service

### 1.1 `app/discord/services/component_service.py`

```python
"""Interactive component management service."""

from __future__ import annotations

import secrets
from typing import Any

import hikari

from app.discord.repositories import discord_repositories
from app.logging import Ansi
from app.logging import log


class ComponentService:
    """Service for creating and managing interactive components."""

    def __init__(self) -> None:
        self._custom_id_prefix = "dc"  # Discord component prefix

    def generate_custom_id(
        self,
        component_type: str,
        action: str,
        **params: Any,
    ) -> str:
        """
        Generate a unique custom ID for a component.

        Args:
            component_type: Type of component (map, github, etc.)
            action: Action identifier
            **params: Additional parameters to encode.

        Returns:
            Unique custom ID string.
        """
        # Format: dc:{type}:{action}:{random}:{param1}:{param2}:...
        parts = [self._custom_id_prefix, component_type, action]

        # Add random suffix for uniqueness
        parts.append(secrets.token_urlsafe(8))

        # Add params
        for key, value in params.items():
            parts.append(f"{key}={value}")

        return ":".join(parts)

    def parse_custom_id(self, custom_id: str) -> dict[str, str]:
        """
        Parse a custom ID into its components.

        Args:
            custom_id: The custom ID to parse.

        Returns:
            Dictionary with type, action, and params.
        """
        parts = custom_id.split(":")
        if len(parts) < 3:
            return {"type": "", "action": "", "params": {}}

        result = {
            "type": parts[1],
            "action": parts[2],
            "params": {},
        }

        # Parse params (key=value pairs)
        for part in parts[3:]:
            if "=" in part:
                key, value = part.split("=", 1)
                result["params"][key] = value

        return result

    async def create_select_menu(
        self,
        custom_id: str,
        placeholder: str,
        options: list[hikari.SelectOption],
        min_values: int = 1,
        max_values: int = 1,
    ) -> hikari.api.TextSelectMenuBuilder:
        """
        Create a text select menu (dropdown).

        Args:
            custom_id: Unique custom ID.
            placeholder: Placeholder text.
            options: List of select options.
            min_values: Minimum selections.
            max_values: Maximum selections.

        Returns:
            Select menu builder.
        """
        # Discord limits: 25 options max, 100 char custom_id
        if len(custom_id) > 100:
            log(f"Custom ID too long: {custom_id}", Ansi.LRED)
            custom_id = custom_id[:100]

        return (
            hikari.impl.TextSelectMenuBuilder(
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=min_values,
                max_values=min_values,
            )
            .add_options(options[:25])  # Discord limit
            .build()
        )

    async def create_button(
        self,
        custom_id: str | None = None,
        label: str = "",
        style: hikari.ButtonStyle = hikari.ButtonStyle.PRIMARY,
        emoji: str | None = None,
        url: str | None = None,
        disabled: bool = False,
    ) -> hikari.api.ButtonBuilder:
        """
        Create a button component.

        Args:
            custom_id: Custom ID (not needed for link buttons).
            label: Button label.
            style: Button style.
            emoji: Button emoji.
            url: URL for link buttons.
            disabled: Whether button is disabled.

        Returns:
            Button builder.
        """
        if url:
            # Link button
            return hikari.impl.LinkButtonBuilder(
                url=url,
                label=label,
                emoji=emoji,
            )

        # Interactive button
        return hikari.impl.InteractiveButtonBuilder(
            custom_id=custom_id or "",
            style=style,
            label=label,
            emoji=emoji,
            is_disabled=disabled,
        )

    async def register_component(
        self,
        custom_id: str,
        component_type: str,
        message_id: int,
        channel_id: int,
        guild_id: int,
        data: dict[str, Any],
        expires_at: str | None = None,
    ) -> None:
        """
        Register a component in the database for persistence.

        Args:
            custom_id: Component custom ID.
            component_type: Type of component.
            message_id: Associated message ID.
            channel_id: Channel ID.
            guild_id: Guild ID.
            data: Component-specific data.
            expires_at: Optional expiration timestamp.
        """
        await discord_repositories.component.create(
            custom_id=custom_id,
            component_type=component_type,
            message_id=message_id,
            channel_id=channel_id,
            guild_id=guild_id,
            data=data,
            expires_at=expires_at,
        )

    async def get_component(self, custom_id: str) -> dict[str, Any] | None:
        """
        Get component data by custom ID.

        Args:
            custom_id: Component custom ID.

        Returns:
            Component data or None if not found/expired.
        """
        return await discord_repositories.component.get(custom_id)

    async def create_difficulty_dropdown(
        self,
        map_id: int,
        difficulties: list[dict[str, Any]],
        message_id: int,
        channel_id: int,
        guild_id: int,
    ) -> hikari.api.TextSelectMenuBuilder:
        """
        Create a difficulty selection dropdown for a map.

        Args:
            map_id: Beatmap set ID.
            difficulties: List of difficulty info dicts.
            message_id: Message ID to register.
            channel_id: Channel ID.
            guild_id: Guild ID.

        Returns:
            Select menu builder.
        """
        custom_id = self.generate_custom_id(
            "map",
            "diff_select",
            map_id=map_id,
        )

        options = []
        for diff in difficulties:
            # Format: ⭕ Diff Name ⭐ 4.5
            mode_emoji = self._get_mode_emoji(diff.get("mode", 0))
            stars = diff.get("stars", 0)
            name = diff.get("name", "Unknown")

            option = hikari.SelectOption(
                label=f"{mode_emoji} {name}",
                value=str(diff.get("id", 0)),
                description=f"⭐ {stars:.2f} • CS{diff.get('cs', 0)} AR{diff.get('ar', 0)}",
                emoji=None,
            )
            options.append(option)

        # Register component
        await self.register_component(
            custom_id=custom_id,
            component_type="select",
            message_id=message_id,
            channel_id=channel_id,
            guild_id=guild_id,
            data={
                "map_id": map_id,
                "difficulties": difficulties,
            },
        )

        return await self.create_select_menu(
            custom_id=custom_id,
            placeholder="Select a difficulty to view details...",
            options=options,
        )

    async def create_job_dropdown(
        self,
        run_id: int,
        jobs: list[dict[str, Any]],
        message_id: int,
        channel_id: int,
        guild_id: int,
    ) -> hikari.api.TextSelectMenuBuilder:
        """
        Create a job selection dropdown for GitHub workflow.

        Args:
            run_id: Workflow run ID.
            jobs: List of job info dicts.
            message_id: Message ID to register.
            channel_id: Channel ID.
            guild_id: Guild ID.

        Returns:
            Select menu builder.
        """
        custom_id = self.generate_custom_id(
            "github",
            "job_select",
            run_id=run_id,
        )

        options = []
        for job in jobs:
            status_emoji = self._get_status_emoji(job.get("status", ""))
            name = job.get("name", "Unknown")

            option = hikari.SelectOption(
                label=name,
                value=str(job.get("id", 0)),
                description=f"{status_emoji} {job.get('conclusion', job.get('status', ''))}",
            )
            options.append(option)

        # Register component
        await self.register_component(
            custom_id=custom_id,
            component_type="select",
            message_id=message_id,
            channel_id=channel_id,
            guild_id=guild_id,
            data={
                "run_id": run_id,
                "jobs": jobs,
            },
        )

        return await self.create_select_menu(
            custom_id=custom_id,
            placeholder="Select a job to view summary...",
            options=options,
        )

    def _get_mode_emoji(self, mode: int) -> str:
        """Get emoji for game mode."""
        emojis = {0: "⭕", 1: "🥁", 2: "🍎", 3: "🎹"}
        return emojis.get(mode, "⭕")

    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for job status."""
        emojis = {
            "success": "✅",
            "failure": "❌",
            "cancelled": "🚫",
            "skipped": "⏭️",
            "in_progress": "🔄",
            "queued": "⏳",
            "pending": "⏳",
        }
        return emojis.get(status, "❓")


# Global instance
component_service = ComponentService()
```

## 2. Bot Interaction Handler

### 2.1 `app/discord/bot.py` (Update)

Add interaction handler to the bot:

```python
def _register_events(self) -> None:
    """Register Discord event handlers."""
    # ... existing events ...
    self._bot.listen(hikari.InteractionCreateEvent)(self._on_interaction)


async def _on_interaction(self, event: hikari.InteractionCreateEvent) -> None:
    """Handle Discord interactions (button clicks, dropdown selections)."""
    interaction = event.interaction

    if isinstance(interaction, hikari.ComponentInteraction):
        await self._handle_component_interaction(interaction)


async def _handle_component_interaction(
    self,
    interaction: hikari.ComponentInteraction,
) -> None:
    """Handle component interactions."""
    from app.discord.services.component_service import component_service

    # Parse custom ID
    parsed = component_service.parse_custom_id(interaction.custom_id)
    component_type = parsed["type"]
    action = parsed["action"]

    # Get component data from database
    component_data = await component_service.get_component(interaction.custom_id)
    if not component_data:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            "This component has expired or is no longer available.",
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    # Dispatch to appropriate handler
    if component_type == "map" and action == "diff_select":
        await self._handle_map_diff_select(interaction, component_data)
    elif component_type == "github" and action == "job_select":
        await self._handle_github_job_select(interaction, component_data)


async def _handle_map_diff_select(
    self,
    interaction: hikari.ComponentInteraction,
    component_data: dict[str, Any],
) -> None:
    """Handle map difficulty selection."""
    from app.discord.services.message_service import message_service

    # Get selected difficulty
    selected_id = interaction.values[0]
    difficulties = component_data["data"].get("difficulties", [])

    # Find the selected difficulty
    selected_diff = None
    for diff in difficulties:
        if str(diff.get("id")) == selected_id:
            selected_diff = diff
            break

    if not selected_diff:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            "Difficulty not found.",
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    # Build ephemeral response with difficulty details
    mode_emoji = self._get_mode_emoji(selected_diff.get("mode", 0))
    stars = selected_diff.get("stars", 0)

    embed = message_service.create_embed(
        title=f"{mode_emoji} {selected_diff.get('name', 'Unknown')}",
        color=self._get_difficulty_color(stars),
        fields=[
            {"name": "⭐ Star Rating", "value": f"{stars:.2f}", "inline": True},
            {"name": "🎯 Circle Size (CS)", "value": str(selected_diff.get("cs", 0)), "inline": True},
            {"name": "🏃 Approach Rate (AR)", "value": str(selected_diff.get("ar", 0)), "inline": True},
            {"name": "💧 Drain (HP)", "value": str(selected_diff.get("hp", 0)), "inline": True},
            {"name": "🎵 BPM", "value": str(selected_diff.get("bpm", 0)), "inline": True},
            {"name": "🔗 Max Combo", "value": str(selected_diff.get("max_combo", 0)), "inline": True},
            {"name": "📏 Length", "value": self._format_length(selected_diff.get("length", 0)), "inline": True},
        ],
    )

    await interaction.create_initial_response(
        hikari.ResponseType.MESSAGE_CREATE,
        embed=embed,
        flags=hikari.MessageFlag.EPHEMERAL,
    )


async def _handle_github_job_select(
    self,
    interaction: hikari.ComponentInteraction,
    component_data: dict[str, Any],
) -> None:
    """Handle GitHub job selection."""
    from app.discord.services.message_service import message_service

    # Get selected job
    selected_id = interaction.values[0]
    jobs = component_data["data"].get("jobs", [])

    # Find the selected job
    selected_job = None
    for job in jobs:
        if str(job.get("id")) == selected_id:
            selected_job = job
            break

    if not selected_job:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            "Job not found.",
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    # Build ephemeral response with job summary
    status_emoji = self._get_status_emoji(selected_job.get("status", ""))

    embed = message_service.create_embed(
        title=f"{status_emoji} {selected_job.get('name', 'Unknown Job')}",
        description=selected_job.get("summary", "No summary available."),
        color=0x454EC1,
        fields=[
            {"name": "Status", "value": selected_job.get("status", "Unknown"), "inline": True},
            {"name": "Conclusion", "value": selected_job.get("conclusion", "N/A"), "inline": True},
            {"name": "Duration", "value": selected_job.get("duration", "Unknown"), "inline": True},
        ],
    )

    # Add link to job if available
    if selected_job.get("url"):
        embed.add_field(
            name="Link",
            value=f"[View on GitHub]({selected_job['url']})",
            inline=False,
        )

    await interaction.create_initial_response(
        hikari.ResponseType.MESSAGE_CREATE,
        embed=embed,
        flags=hikari.MessageFlag.EPHEMERAL,
    )


def _get_mode_emoji(self, mode: int) -> str:
    """Get emoji for game mode."""
    emojis = {0: "⭕", 1: "🥁", 2: "🍎", 3: "🎹"}
    return emojis.get(mode, "⭕")


def _get_difficulty_color(self, stars: float) -> int:
    """Get color based on star rating."""
    if stars < 2.0:
        return 0x00FF00
    elif stars < 2.7:
        return 0x00FFFF
    elif stars < 4.0:
        return 0xFFFF00
    elif stars < 5.3:
        return 0xFF8800
    elif stars < 6.5:
        return 0xFF0000
    else:
        return 0xFF00FF


def _format_length(self, seconds: int) -> str:
    """Format length in seconds to mm:ss."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"
```

## 3. Commit Message

```
feat(discord): add interactive component persistence

- Implement ComponentService for creating buttons and dropdowns
- Add custom ID generation with embedded parameters
- Store components in database for persistence across restarts
- Add difficulty dropdown for map notifications
- Add job dropdown for GitHub workflow notifications
- Handle component interactions with ephemeral responses
```
