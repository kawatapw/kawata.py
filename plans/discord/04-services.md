# Phase 4 — Discord Services Layer

## Scope

Implement the core Discord service layer for sending messages, embeds, and managing the failed message queue with retry logic.

## 1. Message Service

### 1.1 `app/discord/services/__init__.py`

```python
"""Discord services."""

from __future__ import annotations

from app.discord.services.message_service import MessageService


__all__ = ["MessageService"]
```

### 1.2 `app/discord/services/message_service.py`

```python
"""Discord message sending service."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from typing import TypedDict

import hikari
import lightbulb

from app.discord.bot import discord_bot
from app.discord.constants import NOTIFICATION_COLORS
from app.discord.constants import NotificationType
from app.discord.repositories import discord_repositories
from app.logging import Ansi
from app.logging import log


class EmbedField(TypedDict):
    """Discord embed field structure."""

    name: str
    value: str
    inline: bool


class MessagePayload(TypedDict, total=False):
    """Message payload structure."""

    content: str
    embeds: list[dict[str, Any]]
    components: list[dict[str, Any]]


class MessageService:
    """Service for sending messages to Discord channels."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._retry_task: asyncio.Task | None = None
        self._is_processing: bool = False

    async def start(self) -> None:
        """Start the message queue processor."""
        if not self._is_processing:
            self._is_processing = True
            self._retry_task = asyncio.create_task(self._process_retry_queue())
            log("Message service started", Ansi.LGREEN)

    async def stop(self) -> None:
        """Stop the message queue processor."""
        self._is_processing = False
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        log("Message service stopped", Ansi.LYELLOW)

    async def send(
        self,
        channel_id: int,
        content: str | None = None,
        *,
        embed: hikari.Embed | None = None,
        embeds: list[hikari.Embed] | None = None,
        components: list[hikari.api.ComponentBuilder] | None = None,
        guild_id: int | None = None,
        message_type: NotificationType | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int | None:
        """
        Send a message to a Discord channel.

        Args:
            channel_id: Discord channel ID.
            content: Message content text.
            embed: Single embed to attach.
            embeds: Multiple embeds to attach.
            components: Interactive components to attach.
            guild_id: Guild ID for tracking.
            message_type: Type of notification for tracking.
            metadata: Additional metadata to store.

        Returns:
            Message ID if successful, None otherwise.
        """
        bot = discord_bot.bot
        if not bot or not discord_bot.is_connected:
            log("Bot not connected, queuing message for retry", Ansi.LYELLOW)
            await self._queue_message(
                channel_id=channel_id,
                content=content,
                embed=embed,
                embeds=embeds,
                components=components,
            )
            return None

        try:
            # Build message
            message_builder = bot.rest.fetch_message if False else bot.rest.send_message

            kwargs: dict[str, Any] = {"channel": channel_id}
            if content:
                kwargs["content"] = content
            if embed:
                kwargs["embed"] = embed
            if embeds:
                kwargs["embeds"] = embeds
            if components:
                kwargs["components"] = components

            # Send message
            message = await bot.rest.send_message(**kwargs)

            # Track message if needed
            if guild_id and message_type:
                await discord_repositories.message.create(
                    message_id=message.id,
                    channel_id=channel_id,
                    guild_id=guild_id,
                    message_type=message_type.value,
                    metadata=metadata,
                )

            log(f"Message sent to channel {channel_id}", Ansi.LGREEN)
            return message.id

        except hikari.ForbiddenError:
            log(f"Forbidden: Cannot send message to channel {channel_id}", Ansi.LRED)
            return None
        except hikari.NotFoundError:
            log(f"Channel {channel_id} not found", Ansi.LRED)
            return None
        except hikari.RateLimitError as exc:
            log(f"Rate limited, retrying after {exc.retry_after}s", Ansi.LYELLOW)
            await self._queue_message(
                channel_id=channel_id,
                content=content,
                embed=embed,
                embeds=embeds,
                components=components,
            )
            return None
        except Exception as exc:
            log(f"Failed to send message: {exc}", Ansi.LRED)
            await self._queue_failed_message(
                channel_id=channel_id,
                guild_id=guild_id or 0,
                message_data={
                    "content": content,
                    "embed": self._embed_to_dict(embed) if embed else None,
                    "embeds": [self._embed_to_dict(e) for e in embeds] if embeds else None,
                },
                error=str(exc),
            )
            return None

    async def edit_message(
        self,
        channel_id: int,
        message_id: int,
        content: str | None = None,
        *,
        embed: hikari.Embed | None = None,
        embeds: list[hikari.Embed] | None = None,
        components: list[hikari.api.ComponentBuilder] | None = None,
    ) -> bool:
        """
        Edit an existing Discord message.

        Args:
            channel_id: Discord channel ID.
            message_id: Message ID to edit.
            content: New message content.
            embed: New embed.
            embeds: New embeds.
            components: New components.

        Returns:
            True if successful, False otherwise.
        """
        bot = discord_bot.bot
        if not bot or not discord_bot.is_connected:
            return False

        try:
            kwargs: dict[str, Any] = {}
            if content is not None:
                kwargs["content"] = content
            if embed:
                kwargs["embed"] = embed
            if embeds:
                kwargs["embeds"] = embeds
            if components:
                kwargs["components"] = components

            await bot.rest.edit_message(channel_id, message_id, **kwargs)
            return True

        except hikari.NotFoundError:
            log(f"Message {message_id} not found, may have been deleted", Ansi.LYELLOW)
            return False
        except hikari.ForbiddenError:
            log(f"Forbidden: Cannot edit message {message_id}", Ansi.LRED)
            return False
        except Exception as exc:
            log(f"Failed to edit message: {exc}", Ansi.LRED)
            return False

    async def delete_message(self, channel_id: int, message_id: int) -> bool:
        """
        Delete a Discord message.

        Args:
            channel_id: Discord channel ID.
            message_id: Message ID to delete.

        Returns:
            True if successful, False otherwise.
        """
        bot = discord_bot.bot
        if not bot or not discord_bot.is_connected:
            return False

        try:
            await bot.rest.delete_message(channel_id, message_id)
            return True
        except hikari.NotFoundError:
            return True  # Already deleted
        except Exception as exc:
            log(f"Failed to delete message: {exc}", Ansi.LRED)
            return False

    async def send_ephemeral(
        self,
        interaction: hikari.ComponentInteraction | hikari.CommandInteraction,
        content: str | None = None,
        *,
        embed: hikari.Embed | None = None,
        embeds: list[hikari.Embed] | None = None,
        components: list[hikari.api.ComponentBuilder] | None = None,
    ) -> None:
        """
        Send an ephemeral message (only visible to the interacting user).

        Args:
            interaction: The interaction to respond to.
            content: Message content.
            embed: Embed to attach.
            embeds: Embeds to attach.
            components: Components to attach.
        """
        bot = discord_bot.bot
        if not bot:
            return

        kwargs: dict[str, Any] = {
            "flags": hikari.MessageFlag.EPHEMERAL,
        }
        if content:
            kwargs["content"] = content
        if embed:
            kwargs["embed"] = embed
        if embeds:
            kwargs["embeds"] = embeds
        if components:
            kwargs["components"] = components

        try:
            if isinstance(interaction, hikari.ComponentInteraction):
                await interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE,
                    **kwargs,
                )
            else:
                await interaction.create_initial_response(**kwargs)
        except Exception as exc:
            log(f"Failed to send ephemeral message: {exc}", Ansi.LRED)

    async def send_audit_log(
        self,
        guild_id: int,
        title: str,
        description: str,
        *,
        fields: list[EmbedField] | None = None,
        color: int | None = None,
    ) -> int | None:
        """
        Send an audit log message to the configured audit channel.

        Args:
            guild_id: Guild ID.
            title: Embed title.
            description: Embed description.
            fields: Optional embed fields.
            color: Optional embed color.

        Returns:
            Message ID if successful, None otherwise.
        """
        # Get audit channel for guild
        channel_config = await discord_repositories.channel.get_by_type(
            guild_id=guild_id,
            channel_type="audit",
        )
        if not channel_config:
            log(f"No audit channel configured for guild {guild_id}", Ansi.LYELLOW)
            return None

        # Build embed
        if color is None:
            color = NOTIFICATION_COLORS.get(NotificationType.ADMIN_RESTRICT, 0xFF0000)

        embed = hikari.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=hikari.utcnow(),
        )

        if fields:
            for field in fields:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", False),
                )

        return await self.send(
            channel_id=channel_config["id"],
            embed=embed,
            guild_id=guild_id,
            message_type=NotificationType.ADMIN_RESTRICT,
        )

    async def send_fallback_notification(
        self,
        webhook_url: str,
        content: str,
    ) -> bool:
        """
        Send a notification via fallback webhook.

        Args:
            webhook_url: Webhook URL.
            content: Message content.

        Returns:
            True if successful, False otherwise.
        """
        from app.state import services

        try:
            response = await services.http_client.post(
                webhook_url,
                json={"content": content},
                headers={"Content-Type": "application/json"},
            )
            return response.status_code == 204
        except Exception as exc:
            log(f"Failed to send fallback notification: {exc}", Ansi.LRED)
            return False

    def create_embed(
        self,
        title: str | None = None,
        description: str | None = None,
        *,
        color: int | None = None,
        fields: list[EmbedField] | None = None,
        footer: str | None = None,
        footer_icon: str | None = None,
        image: str | None = None,
        thumbnail: str | None = None,
        author: str | None = None,
        author_icon: str | None = None,
        author_url: str | None = None,
        timestamp: hikari.UndefinedNoneOr[hikari.SearchableUndefined] = hikari.UNDEFINED,
    ) -> hikari.Embed:
        """
        Create a Discord embed.

        Args:
            title: Embed title.
            description: Embed description.
            color: Embed color.
            fields: Embed fields.
            footer: Footer text.
            footer_icon: Footer icon URL.
            image: Image URL.
            thumbnail: Thumbnail URL.
            author: Author name.
            author_icon: Author icon URL.
            author_url: Author URL.
            timestamp: Timestamp.

        Returns:
            Constructed embed.
        """
        embed = hikari.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=timestamp,
        )

        if fields:
            for field in fields:
                embed.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", False),
                )

        if footer:
            embed.set_footer(text=footer, icon=footer_icon)
        if image:
            embed.set_image(image)
        if thumbnail:
            embed.set_thumbnail(thumbnail)
        if author:
            embed.set_author(name=author, icon=author_icon, url=author_url)

        return embed

    async def _queue_message(
        self,
        channel_id: int,
        content: str | None = None,
        embed: hikari.Embed | None = None,
        embeds: list[hikari.Embed] | None = None,
        components: list[hikari.api.ComponentBuilder] | None = None,
    ) -> None:
        """Queue a message for retry."""
        await self._queue.put({
            "channel_id": channel_id,
            "content": content,
            "embed": embed,
            "embeds": embeds,
            "components": components,
            "attempts": 0,
            "next_retry": time.time() + 1,
        })

    async def _queue_failed_message(
        self,
        channel_id: int,
        guild_id: int,
        message_data: dict[str, Any],
        error: str,
    ) -> None:
        """Store a failed message in the database."""
        await discord_repositories.failed_message.create(
            channel_id=channel_id,
            guild_id=guild_id,
            message_data=message_data,
            last_error=error,
        )

    async def _process_retry_queue(self) -> None:
        """Process the retry queue."""
        while self._is_processing:
            try:
                # Check for messages to retry
                if not self._queue.empty():
                    message = await self._queue.get()
                    if time.time() >= message["next_retry"]:
                        await self.send(
                            channel_id=message["channel_id"],
                            content=message.get("content"),
                            embed=message.get("embed"),
                            embeds=message.get("embeds"),
                            components=message.get("components"),
                        )
                    else:
                        # Put back in queue
                        await self._queue.put(message)

                # Check database for failed messages
                await self._retry_failed_messages()

                await asyncio.sleep(5)  # Check every 5 seconds

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log(f"Error in retry queue processor: {exc}", Ansi.LRED)
                await asyncio.sleep(10)

    async def _retry_failed_messages(self) -> None:
        """Retry failed messages from database."""
        failed = await discord_repositories.failed_message.get_pending()
        for msg in failed:
            if msg["retry_count"] >= msg["max_retries"]:
                await discord_repositories.failed_message.mark_dead_letter(msg["id"])
                continue

            # Exponential backoff
            retry_delay = 2 ** msg["retry_count"]
            if time.time() >= msg["created_at"].timestamp() + retry_delay:
                success = await self.send(
                    channel_id=msg["channel_id"],
                    content=msg["message_data"].get("content"),
                )
                if success:
                    await discord_repositories.failed_message.mark_success(msg["id"])
                else:
                    await discord_repositories.failed_message.increment_retry(
                        msg["id"],
                        error="Retry failed",
                    )

    def _embed_to_dict(self, embed: hikari.Embed) -> dict[str, Any]:
        """Convert embed to dictionary for storage."""
        data: dict[str, Any] = {}
        if embed.title:
            data["title"] = embed.title
        if embed.description:
            data["description"] = embed.description
        if embed.color:
            data["color"] = int(embed.color)
        if embed.fields:
            data["fields"] = [
                {"name": f.name, "value": f.value, "inline": f.is_inline}
                for f in embed.fields
            ]
        return data


# Global instance
message_service = MessageService()
```

## 2. Failed Message Repository

### 2.1 `app/discord/repositories/failed_message_repo.py`

```python
"""Failed message repository for discord_failed_messages table."""

from __future__ import annotations

from typing import TypedDict

from app.state.services import database


class FailedMessage(TypedDict):
    id: int
    channel_id: int
    guild_id: int
    message_data: dict
    retry_count: int
    max_retries: int
    last_error: str | None
    next_retry_at: str | None
    status: str
    created_at: str
    updated_at: str


class FailedMessageRepo:
    """Repository for failed message queue."""

    async def get(self, message_id: int) -> FailedMessage | None:
        """Get failed message by ID."""
        query = """
            SELECT id, channel_id, guild_id, message_data, retry_count,
                   max_retries, last_error, next_retry_at, status,
                   created_at, updated_at
            FROM discord_failed_messages
            WHERE id = :message_id
        """
        return await database.fetch_one(query, {"message_id": message_id})

    async def get_pending(self) -> list[FailedMessage]:
        """Get pending failed messages ready for retry."""
        query = """
            SELECT id, channel_id, guild_id, message_data, retry_count,
                   max_retries, last_error, next_retry_at, status,
                   created_at, updated_at
            FROM discord_failed_messages
            WHERE status IN ('pending', 'retrying')
              AND (next_retry_at IS NULL OR next_retry_at <= NOW())
            ORDER BY created_at ASC
            LIMIT 10
        """
        return await database.fetch_all(query)

    async def get_by_status(self, status: str) -> list[FailedMessage]:
        """Get failed messages by status."""
        query = """
            SELECT id, channel_id, guild_id, message_data, retry_count,
                   max_retries, last_error, next_retry_at, status,
                   created_at, updated_at
            FROM discord_failed_messages
            WHERE status = :status
            ORDER BY created_at DESC
        """
        return await database.fetch_all(query, {"status": status})

    async def create(
        self,
        channel_id: int,
        guild_id: int,
        message_data: dict,
        last_error: str | None = None,
        max_retries: int = 5,
    ) -> None:
        """Create a new failed message record."""
        query = """
            INSERT INTO discord_failed_messages
                (channel_id, guild_id, message_data, last_error, max_retries)
            VALUES
                (:channel_id, :guild_id, :message_data, :last_error, :max_retries)
        """
        await database.execute(query, {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "message_data": message_data,
            "last_error": last_error,
            "max_retries": max_retries,
        })

    async def increment_retry(self, message_id: int, error: str | None = None) -> None:
        """Increment retry count and update error."""
        query = """
            UPDATE discord_failed_messages
            SET retry_count = retry_count + 1,
                last_error = :error,
                next_retry_at = DATE_ADD(NOW(), INTERVAL :delay SECOND),
                status = 'retrying'
            WHERE id = :message_id
        """
        # Exponential backoff delay
        delay_query = """
            SELECT POW(2, retry_count) as delay
            FROM discord_failed_messages
            WHERE id = :message_id
        """
        delay_row = await database.fetch_one(delay_query, {"message_id": message_id})
        delay = delay_row["delay"] if delay_row else 30

        await database.execute(query, {
            "message_id": message_id,
            "error": error,
            "delay": delay,
        })

    async def mark_success(self, message_id: int) -> None:
        """Mark failed message as successfully sent."""
        query = "DELETE FROM discord_failed_messages WHERE id = :message_id"
        await database.execute(query, {"message_id": message_id})

    async def mark_dead_letter(self, message_id: int) -> None:
        """Mark failed message as dead letter (max retries exceeded)."""
        query = """
            UPDATE discord_failed_messages
            SET status = 'dead_letter'
            WHERE id = :message_id
        """
        await database.execute(query, {"message_id": message_id})

    async def retry_dead_letter(self, message_id: int) -> None:
        """Reset a dead letter message for retry."""
        query = """
            UPDATE discord_failed_messages
            SET status = 'pending',
                retry_count = 0,
                next_retry_at = NOW()
            WHERE id = :message_id AND status = 'dead_letter'
        """
        await database.execute(query, {"message_id": message_id})

    async def delete_old(self, days: int = 7) -> int:
        """Delete old resolved/failed messages."""
        query = """
            DELETE FROM discord_failed_messages
            WHERE status IN ('dead_letter')
              AND updated_at < DATE_SUB(NOW(), INTERVAL :days DAY)
        """
        result = await database.execute(query, {"days": days})
        return result or 0
```

## 3. Update Repositories Init

### 3.1 `app/discord/repositories/__init__.py` (Update)

```python
"""Discord module repositories."""

from __future__ import annotations

from app.discord.repositories.failed_message_repo import FailedMessageRepo


class DiscordRepositories:
    """Container for all Discord repository instances."""

    def __init__(self) -> None:
        # ... existing repos ...
        self.failed_message = FailedMessageRepo()


discord_repositories = DiscordRepositories()
```

## 4. Commit Message

```
feat(discord): add message service with retry logic

- Implement MessageService for sending messages, embeds, components
- Add ephemeral message support for interactive responses
- Add audit log message helper
- Add fallback webhook notification support
- Implement FailedMessageRepo for retry queue
- Add exponential backoff retry logic
- Add message queue processor background task
```
