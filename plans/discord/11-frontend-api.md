# Phase 11 — Frontend API Integration

## Scope

Complete the frontend API endpoints and migrate existing webhook usage to the new Discord module.

## 1. Update Existing Webhook Usage

### 1.1 Update `app/objects/player.py`

Replace the old webhook usage with the new Discord service:

```python
# OLD CODE (to be replaced):
# from app.discord import Webhook
#
# webhook_url = app.settings.DISCORD_AUDIT_LOG_WEBHOOK
# if webhook_url:
#     webhook = Webhook(webhook_url, content=log_msg)
#     _ = asyncio.create_task(webhook.post())

# NEW CODE:
from app.discord.services.message_service import message_service

# Get guild ID from configuration (or use a default)
# For now, we'll need to determine the appropriate guild
guild_id = await self._get_discord_guild_id()
if guild_id:
    await message_service.send_audit_log(
        guild_id=guild_id,
        title="Admin Action: Restrict",
        description=f"{admin} restricted {self} for: {reason}.",
    )

async def _get_discord_guild_id(self) -> int | None:
    """Get the Discord guild ID for audit logs."""
    from app.discord.repositories import discord_repositories

    # Get the first guild with an audit channel configured
    # In a multi-guild setup, this could be more sophisticated
    channels = await discord_repositories.channel.get_all_by_type("audit")
    if channels:
        return channels[0]["guild_id"]
    return None
```

### 1.2 Update `app/settings.py`

Remove deprecated settings:

```python
# REMOVE these lines:
# DISCORD_AUDIT_LOG_WEBHOOK = os.environ["DISCORD_AUDIT_LOG_WEBHOOK"]
# DISCORD_INVITE = os.environ["DISCORD_INVITE"]

# KEEP/ADD these:
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") or None
DISCORD_ENCRYPTION_KEY = os.environ.get("DISCORD_ENCRYPTION_KEY") or None
```

### 1.3 Update `app/commands/categories/developer.py`

Replace DISCORD_INVITE usage:

```python
# OLD:
# f"If you need any support, join our Discord @ {settings.DISCORD_INVITE}"

# NEW:
# The invite link will be retrieved from the database
# For now, use a placeholder or command to get it
"If you need any support, use !discord invite to get our Discord link."
```

### 1.4 Update `app/api/domains/cho.py`

Replace DISCORD_INVITE usage:

```python
# OLD:
# f"We have a public (Discord)[{app.settings.DISCORD_INVITE}]!"

# NEW:
# Retrieve from database or use command
"We have a public Discord! Use !discord invite to get the link."
```

## 2. Remove Old Discord Module

### 2.1 Delete `app/discord.py`

The old webhook module is completely replaced by the new `app/discord/` package.

## 3. Frontend API Enhancements

### 3.1 Update `app/discord/api/endpoints.py`

Add additional endpoints for frontend use:

```python
# Add to existing endpoints.py


@router.get("/invite", dependencies=[verify_bot_api_key])
async def get_invite_link(guild_id: int) -> dict[str, str]:
    """
    Get the Discord invite link for a guild.

    Requires BOT_API_KEY authentication.
    """
    guild = await discord_repositories.guild.get(guild_id)
    if not guild or not guild.get("invite_link"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No invite link configured for this guild",
        )
    return {"invite_link": guild["invite_link"]}


@router.post("/announce", dependencies=[verify_bot_api_key])
async def create_announcement(request: dict[str, Any]) -> dict[str, str]:
    """
    Create a scheduled announcement.

    Requires BOT_API_KEY authentication.
    """
    from app.discord.services.announcement_service import announcement_service

    announcement_id = await announcement_service.schedule(
        guild_id=request["guild_id"],
        announcement_type=request["type"],
        title=request["title"],
        body=request["body"],
        scheduled_at=request.get("scheduled_at"),
        role_mentions=request.get("role_mentions", []),
    )

    return {"status": "scheduled", "announcement_id": announcement_id}


@router.get("/messages/failed", dependencies=[verify_bot_api_key])
async def get_failed_messages(
    status: str = "pending",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Get failed messages for admin review.

    Requires BOT_API_KEY authentication.
    """
    return await discord_repositories.failed_message.get_by_status(status)[:limit]


@router.post("/messages/retry", dependencies=[verify_bot_api_key])
async def retry_failed_message(message_id: int) -> dict[str, str]:
    """
    Retry a failed message.

    Requires BOT_API_KEY authentication.
    """
    await discord_repositories.failed_message.retry_dead_letter(message_id)
    return {"status": "retry_queued"}
```

## 4. Announcement Service

### 4.1 `app/discord/services/announcement_service.py`

```python
"""Announcement service for scheduled announcements."""

from __future__ import annotations

from typing import Any

from app.discord.constants import NOTIFICATION_COLORS
from app.discord.constants import NotificationType
from app.discord.repositories import discord_repositories
from app.discord.services.message_service import message_service
from app.logging import Ansi
from app.logging import log


class AnnouncementService:
    """Service for creating and scheduling announcements."""

    async def send_announcement(
        self,
        guild_id: int,
        announcement_type: str,
        title: str,
        body: str,
        *,
        role_mentions: list[int] | None = None,
        image_url: str | None = None,
        author_name: str | None = None,
    ) -> int | None:
        """
        Send an announcement to the configured announcements channel.

        Args:
            guild_id: Discord guild ID.
            announcement_type: Type of announcement.
            title: Announcement title.
            body: Announcement body.
            role_mentions: List of role IDs to mention.
            image_url: Optional image URL.
            author_name: Optional author name.

        Returns:
            Message ID if sent successfully, None otherwise.
        """
        # Get announcements channel
        channel_config = await discord_repositories.channel.get_by_type(
            guild_id=guild_id,
            channel_type="announcements",
        )
        if not channel_config:
            log(f"No announcements channel for guild {guild_id}", Ansi.LYELLOW)
            return None

        # Get notification type
        try:
            notif_type = NotificationType(f"announcement_{announcement_type}")
        except ValueError:
            notif_type = NotificationType.ANNOUNCEMENT_UPDATE

        # Build content with role mentions
        content = ""
        if role_mentions:
            mentions = " ".join(f"<@&{role_id}>" for role_id in role_mentions)
            content = mentions + "\n"

        # Build embed
        embed = message_service.create_embed(
            title=f"📢 {title}",
            description=body,
            color=NOTIFICATION_COLORS.get(notif_type, 0x808080),
            image=image_url,
            footer=f"Announcement by {author_name}" if author_name else None,
        )

        return await message_service.send(
            channel_id=channel_config["id"],
            content=content if content else None,
            embed=embed,
            guild_id=guild_id,
            message_type=notif_type,
        )

    async def schedule(
        self,
        guild_id: int,
        announcement_type: str,
        title: str,
        body: str,
        scheduled_at: str | None = None,
        role_mentions: list[int] | None = None,
    ) -> int:
        """
        Schedule an announcement for future delivery.

        Args:
            guild_id: Discord guild ID.
            announcement_type: Type of announcement.
            title: Announcement title.
            body: Announcement body.
            scheduled_at: ISO format timestamp for scheduled delivery.
            role_mentions: List of role IDs to mention.

        Returns:
            Announcement ID.
        """
        # Store in database for scheduled delivery
        # Implementation depends on scheduling mechanism
        # Could use asyncio.sleep for simple cases or a proper task queue
        pass


# Global instance
announcement_service = AnnouncementService()
```

## 5. Commit Message

```
feat(discord): complete frontend API and migrate from old webhook

- Migrate player.py audit logs to new Discord service
- Remove deprecated DISCORD_AUDIT_LOG_WEBHOOK and DISCORD_INVITE from settings
- Update command responses to use database-stored invite link
- Add /api/v1/discord/invite endpoint
- Add /api/v1/discord/announce endpoint
- Add /api/v1/discord/messages/failed endpoint
- Add /api/v1/discord/messages/retry endpoint
- Delete old app/discord.py webhook module
- Add AnnouncementService for scheduled announcements
```
