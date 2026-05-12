# Phase 8 — Map Rank Notifications

## Scope

Implement map rank status change notifications with interactive difficulty dropdown.

## 1. Map Notification Service

### 1.1 `app/discord/services/map_notification_service.py`

```python
"""Map rank notification service."""

from __future__ import annotations

from typing import Any

from app.discord.constants import NOTIFICATION_COLORS
from app.discord.constants import NotificationType
from app.discord.repositories import discord_repositories
from app.discord.services.component_service import component_service
from app.discord.services.message_service import message_service
from app.logging import Ansi
from app.logging import log


class MapNotificationService:
    """Service for sending map rank notifications."""

    # Status name mapping
    STATUS_NAMES = {
        -2: "WIP",
        -1: "Pending",
        0: "Graveyard",
        1: "Ranked",
        2: "Approved",
        3: "Qualified",
        4: "Loved",
    }

    # Status to notification type mapping
    STATUS_TO_TYPE = {
        1: NotificationType.MAP_RANKED,
        3: NotificationType.MAP_QUALIFIED,
        4: NotificationType.MAP_LOVED,
    }

    async def notify_map_status_change(
        self,
        guild_id: int,
        beatmap_set: dict[str, Any],
        old_status: int,
        new_status: int,
        changed_diffs: list[dict[str, Any]] | None = None,
    ) -> int | None:
        """
        Send a map status change notification.

        Args:
            guild_id: Discord guild ID.
            beatmap_set: Beatmap set data from database.
            old_status: Previous ranked status.
            new_status: New ranked status.
            changed_diffs: List of difficulties that changed status.

        Returns:
            Message ID if sent successfully, None otherwise.
        """
        # Get notification type
        notification_type = self.STATUS_TO_TYPE.get(new_status)
        if not notification_type:
            log(f"No notification type for status {new_status}", Ansi.LYELLOW)
            return None

        # Get map rank channel for guild
        channel_config = await discord_repositories.channel.get_by_type(
            guild_id=guild_id,
            channel_type="map_rank",
        )
        if not channel_config:
            log(f"No map rank channel configured for guild {guild_id}", Ansi.LYELLOW)
            return None

        # Build embed
        embed = self._build_embed(
            beatmap_set=beatmap_set,
            old_status=old_status,
            new_status=new_status,
            changed_diffs=changed_diffs or [],
            notification_type=notification_type,
        )

        # Build components (difficulty dropdown)
        components = []
        if changed_diffs:
            dropdown = await component_service.create_difficulty_dropdown(
                map_id=beatmap_set["id"],
                difficulties=changed_diffs,
                message_id=0,  # Will be updated after sending
                channel_id=channel_config["id"],
                guild_id=guild_id,
            )
            components.append(dropdown)

        # Send message
        message_id = await message_service.send(
            channel_id=channel_config["id"],
            embed=embed,
            components=components,
            guild_id=guild_id,
            message_type=notification_type,
            metadata={
                "map_id": beatmap_set["id"],
                "old_status": old_status,
                "new_status": new_status,
            },
        )

        # Update component with actual message ID
        if message_id and components:
            for component in components:
                if hasattr(component, "custom_id"):
                    await discord_repositories.component.update_message_id(
                        custom_id=component.custom_id,
                        message_id=message_id,
                    )

        return message_id

    def _build_embed(
        self,
        beatmap_set: dict[str, Any],
        old_status: int,
        new_status: int,
        changed_diffs: list[dict[str, Any]],
        notification_type: NotificationType,
    ) -> Any:
        """Build the notification embed."""
        import hikari

        status_emoji = self._get_status_emoji(new_status)
        old_status_name = self.STATUS_NAMES.get(old_status, "Unknown")
        new_status_name = self.STATUS_NAMES.get(new_status, "Unknown")

        # Build title
        title = f"{status_emoji} Map {new_status_name}: {beatmap_set['title']}"

        # Build description
        description = f"By **{beatmap_set['artist']}** — Mapped by **{beatmap_set['creator']}**"

        # Build color
        color = NOTIFICATION_COLORS.get(notification_type, 0x808080)

        # Build embed
        embed = hikari.Embed(
            title=title,
            description=description,
            color=color,
            url=f"https://osu.ppy.sh/s/{beatmap_set['id']}",
            timestamp=hikari.utcnow(),
        )

        # Set thumbnail (map cover)
        cover_url = f"https://assets.ppy.sh/beatmaps/{beatmap_set['id']}/covers/card.jpg"
        embed.set_thumbnail(cover_url)

        # Add status change field
        embed.add_field(
            name="Status",
            value=f"`{old_status_name}` → `{new_status_name}`",
            inline=True,
        )

        # Add BPM field
        embed.add_field(
            name="BPM",
            value=str(beatmap_set.get("bpm", 0)),
            inline=True,
        )

        # Add field count field
        embed.add_field(
            name="Difficulties",
            value=str(len(changed_diffs)),
            inline=True,
        )

        # Add difficulty icons if changed_diffs provided
        if changed_diffs:
            diff_icons = self._build_difficulty_icons(changed_diffs)
            embed.add_field(
                name="Changed Difficulties",
                value=diff_icons,
                inline=False,
            )

        # Set footer
        embed.set_footer(f"Beatmap Set ID: {beatmap_set['id']}")

        return embed

    def _build_difficulty_icons(self, difficulties: list[dict[str, Any]]) -> str:
        """Build a string of difficulty icons with mode colors."""
        icons = []
        for diff in difficulties:
            mode = diff.get("mode", 0)
            stars = diff.get("stars", 0)
            name = diff.get("name", "Unknown")

            # Get mode emoji
            mode_emojis = {0: "⭕", 1: "🥁", 2: "🍎", 3: "🎹"}
            mode_emoji = mode_emojis.get(mode, "⭕")

            # Get difficulty color indicator (using colored circles)
            if stars < 2.0:
                color_indicator = "🟢"
            elif stars < 2.7:
                color_indicator = "🔵"
            elif stars < 4.0:
                color_indicator = "🟡"
            elif stars < 5.3:
                color_indicator = "🟠"
            elif stars < 6.5:
                color_indicator = "🔴"
            else:
                color_indicator = "🟣"

            icons.append(f"{mode_emoji} {color_indicator} {name} (⭐{stars:.2f})")

        return "\n".join(icons) if icons else "None"

    def _get_status_emoji(self, status: int) -> str:
        """Get emoji for ranked status."""
        emojis = {
            1: "🟢",  # Ranked
            2: "✅",  # Approved
            3: "🔵",  # Qualified
            4: "💖",  # Loved
        }
        return emojis.get(status, "❓")


# Global instance
map_notification_service = MapNotificationService()
```

## 2. Integration with Existing Map Code

### 2.1 Update map status change handlers

Find where map status changes are processed and add notification trigger:

```python
# In the map status change handler (to be located in existing code)
async def on_map_status_change(
    beatmap_set_id: int,
    old_status: int,
    new_status: int,
) -> None:
    """Handle map status change and send Discord notification."""
    from app.discord.services.map_notification_service import map_notification_service

    # Fetch beatmap set data
    beatmap_set = await BeatmapSet.from_bsid(beatmap_set_id)
    if not beatmap_set:
        return

    # Get difficulties that changed status
    changed_diffs = []
    for beatmap in beatmap_set.maps:
        if beatmap.status == new_status:
            changed_diffs.append({
                "id": beatmap.id,
                "name": beatmap.version,
                "mode": beatmap.mode,
                "stars": beatmap.diff,
                "cs": beatmap.cs,
                "ar": beatmap.ar,
                "hp": beatmap.hp,
                "bpm": beatmap.bpm,
                "length": beatmap.total_length,
                "max_combo": beatmap.max_combo,
            })

    # Get all guilds with map rank notifications enabled
    guilds = await discord_repositories.channel.get_all_by_type("map_rank")
    for guild_channel in guilds:
        await map_notification_service.notify_map_status_change(
            guild_id=guild_channel["guild_id"],
            beatmap_set={
                "id": beatmap_set.id,
                "title": beatmap_set.title,
                "artist": beatmap_set.artist,
                "creator": beatmap_set.creator,
                "bpm": beatmap_set.bpm,
            },
            old_status=old_status,
            new_status=new_status,
            changed_diffs=changed_diffs,
        )
```

## 3. Commit Message

```
feat(discord): add map rank notifications

- Implement MapNotificationService for status change notifications
- Add embed builder with map info and difficulty icons
- Add mode-colored difficulty indicators
- Integrate with existing map status change handlers
- Support for Ranked, Qualified, and Loved notifications
```
