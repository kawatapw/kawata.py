# Phase 2 — Core Bot Infrastructure

## Scope

Set up the Hikari bot with gateway connection, error handling, reconnection logic, and graceful shutdown. This is the foundation that all other Discord features build upon.

## 1. Dependencies

### 1.1 Update `pyproject.toml`

Add to `[project.dependencies]`:

```toml
"hikari>=2.0.0",
"hikari-lightbulb>=2.0.0",
"cryptography>=41.0.0",
```

## 2. Bot Initialization

### 2.1 `app/discord/__init__.py`

```python
"""Discord integration module using Hikari."""

from __future__ import annotations

from app.discord.bot import DiscordBot
from app.discord.constants import NotificationType
from app.discord.encryption import EncryptionManager


__all__ = [
    "DiscordBot",
    "NotificationType",
    "EncryptionManager",
]
```

### 2.2 `app/discord/constants.py`

```python
"""Discord module constants."""

from __future__ import annotations

import enum


class NotificationType(enum.Enum):
    """Types of notifications that can be sent to Discord."""

    # Map notifications
    MAP_RANKED = "map_ranked"
    MAP_QUALIFIED = "map_qualified"
    MAP_LOVED = "map_loved"
    MAP_RESET = "map_reset"

    # GitHub notifications
    GITHUB_PUSH = "github_push"
    GITHUB_PR = "github_pr"
    GITHUB_WORKFLOW = "github_workflow"

    # Announcements
    ANNOUNCEMENT_MAINTENANCE = "announcement_maintenance"
    ANNOUNCEMENT_EVENT = "announcement_event"
    ANNOUNCEMENT_UPDATE = "announcement_update"
    ANNOUNCEMENT_SEASON = "announcement_season"

    # Admin actions
    ADMIN_RESTRICT = "admin_restrict"
    ADMIN_UNRESTRICT = "admin_unrestrict"
    ADMIN_SILENCE = "admin_silence"
    ADMIN_UNSILENCE = "admin_unsilence"


# Default colors for notification types
NOTIFICATION_COLORS: dict[NotificationType, int] = {
    # Map statuses
    NotificationType.MAP_RANKED: 0x00FF00,      # Green
    NotificationType.MAP_QUALIFIED: 0x00FFFF,    # Cyan
    NotificationType.MAP_LOVED: 0xFF69B4,        # Pink
    NotificationType.MAP_RESET: 0xFF0000,        # Red

    # GitHub
    NotificationType.GITHUB_PUSH: 0x454EC1,      # Purple
    NotificationType.GITHUB_PR: 0x454EC1,        # Purple
    NotificationType.GITHUB_WORKFLOW: 0x454EC1,  # Purple

    # Announcements
    NotificationType.ANNOUNCEMENT_MAINTENANCE: 0xFFA500,  # Orange
    NotificationType.ANNOUNCEMENT_EVENT: 0x00FF00,        # Green
    NotificationType.ANNOUNCEMENT_UPDATE: 0x00BFFF,       # Deep Sky Blue
    NotificationType.ANNOUNCEMENT_SEASON: 0xFFD700,       # Gold

    # Admin
    NotificationType.ADMIN_RESTRICT: 0xFF0000,     # Red
    NotificationType.ADMIN_UNRESTRICT: 0x00FF00,   # Green
    NotificationType.ADMIN_SILENCE: 0xFFA500,      # Orange
    NotificationType.ADMIN_UNSILENCE: 0x00FF00,    # Green
}

# Status emojis
STATUS_EMOJIS: dict[str, str] = {
    "success": "✅",
    "failure": "❌",
    "pending": "⏳",
    "running": "🔄",
    "cancelled": "🚫",
    "skipped": "⏭️",
}

# Game mode icons (osu! specific)
MODE_EMOJIS: dict[int, str] = {
    0: "⭕",  # osu!
    1: "🥁",  # Taiko
    2: "🍎",  # Catch
    3: "🎹",  # Mania
}

# Difficulty rating colors (based on star rating)
def get_difficulty_color(stars: float) -> int:
    """Get color based on star rating."""
    if stars < 2.0:
        return 0x00FF00      # Easy - Green
    elif stars < 2.7:
        return 0x00FFFF      # Normal - Cyan
    elif stars < 4.0:
        return 0xFFFF00      # Hard - Yellow
    elif stars < 5.3:
        return 0xFF8800      # Insane - Orange
    elif stars < 6.5:
        return 0xFF0000      # Expert - Red
    else:
        return 0xFF00FF      # Expert+ - Magenta
```

### 2.3 `app/discord/bot.py`

```python
"""Hikari bot initialization and lifecycle management."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import hikari
import lightbulb

from app.discord.repositories import discord_repositories
from app.logging import Ansi
from app.logging import log

if TYPE_CHECKING:
    from app.discord.services.message_service import MessageService


class DiscordBot:
    """Discord bot manager with Hikari gateway connection."""

    def __init__(self) -> None:
        self._bot: lightbulb.BotApp | None = None
        self._message_service: MessageService | None = None
        self._reconnect_attempts: int = 0
        self._max_reconnect_attempts: int = 5
        self._is_shutting_down: bool = False

    @property
    def is_connected(self) -> bool:
        """Check if bot is connected to Discord."""
        return (
            self._bot is not None
            and self._bot.is_alive
        )

    @property
    def bot(self) -> lightbulb.BotApp | None:
        """Get the bot instance."""
        return self._bot

    async def initialize(self) -> None:
        """Initialize the bot with configuration from database."""
        from app import settings

        if not settings.DISCORD_BOT_TOKEN:
            log("Discord bot token not configured, skipping initialization", Ansi.LYELLOW)
            return

        # Create bot instance
        self._bot = lightbulb.BotApp(
            token=settings.DISCORD_BOT_TOKEN,
            intents=hikari.Intents.ALL_UNPRIVILEGED | hikari.Intents.MESSAGE_CONTENT,
            default_enabled_guilds=(),  # Will be set from database
        )

        # Register event handlers
        self._register_events()

        # Load extensions (for future slash commands)
        # self._bot.load_extensions_from("app/discord/commands/")

        log("Discord bot initialized", Ansi.LGREEN)

    def _register_events(self) -> None:
        """Register Discord event handlers."""
        if not self._bot:
            return

        self._bot.listen(hikari.StartingEvent)(self._on_starting)
        self._bot.listen(hikari.StartedEvent)(self._on_started)
        self._bot.listen(hikari.StoppingEvent)(self._on_stopping)
        self._bot.listen(hikari.StoppedEvent)(self._on_stopped)
        self._bot.listen(hikari.ShardReadyEvent)(self._on_shard_ready)
        self._bot.listen(hikari.GuildJoinEvent)(self._on_guild_join)
        self._bot.listen(hikari.GuildLeaveEvent)(self._on_guild_leave)

    async def start(self) -> None:
        """Start the bot connection."""
        if not self._bot:
            await self.initialize()

        if not self._bot:
            return

        self._is_shutting_down = False
        self._reconnect_attempts = 0

        try:
            # Run bot in background
            await self._bot.start()
        except hikari.ComponentStateConflictError:
            log("Discord bot is already running", Ansi.LYELLOW)
        except Exception as exc:
            log(f"Failed to start Discord bot: {exc}", Ansi.LRED)
            await self._handle_connection_error()

    async def stop(self) -> None:
        """Stop the bot gracefully."""
        if not self._bot or not self.is_connected:
            return

        self._is_shutting_down = True
        log("Stopping Discord bot...", Ansi.LYELLOW)

        try:
            await self._bot.close()
        except Exception as exc:
            log(f"Error stopping Discord bot: {exc}", Ansi.LRED)

        log("Discord bot stopped", Ansi.LGREEN)

    async def _handle_connection_error(self) -> None:
        """Handle connection errors with reconnection logic."""
        if self._is_shutting_down:
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > self._max_reconnect_attempts:
            log(
                f"Discord bot failed to connect after {self._max_reconnect_attempts} attempts",
                Ansi.LRED,
            )
            await self._notify_admins_connection_lost()
            return

        # Exponential backoff: 1s, 2s, 4s, 8s, 16s
        delay = 2 ** (self._reconnect_attempts - 1)
        log(
            f"Discord bot reconnecting in {delay}s (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})",
            Ansi.LYELLOW,
        )

        await asyncio.sleep(delay)
        await self.start()

    async def _notify_admins_connection_lost(self) -> None:
        """Notify admins that bot connection is lost."""
        # Use fallback webhook if available
        from app.discord.services.message_service import MessageService
        service = MessageService()

        # Get all guilds with fallback webhooks
        guilds = await discord_repositories.guild.get_all()
        for guild_config in guilds:
            if guild_config.get("fallback_webhook"):
                await service.send_fallback_notification(
                    guild_config["fallback_webhook"],
                    "⚠️ Discord bot connection lost. Some features may be unavailable.",
                )

    # Event handlers

    async def _on_starting(self, event: hikari.StartingEvent) -> None:
        """Handle bot starting event."""
        log("Discord bot starting...", Ansi.LCYAN)

    async def _on_started(self, event: hikari.StartedEvent) -> None:
        """Handle bot started event."""
        self._reconnect_attempts = 0
        log("Discord bot connected successfully", Ansi.LGREEN)

        # Set bot status from database
        await self._update_presence()

    async def _on_stopping(self, event: hikari.StoppingEvent) -> None:
        """Handle bot stopping event."""
        log("Discord bot stopping...", Ansi.LYELLOW)

    async def _on_stopped(self, event: hikari.StoppedEvent) -> None:
        """Handle bot stopped event."""
        if not self._is_shutting_down:
            log("Discord bot disconnected unexpectedly", Ansi.LRED)
            await self._handle_connection_error()

    async def _on_shard_ready(self, event: hikari.ShardReadyEvent) -> None:
        """Handle shard ready event."""
        log(f"Discord shard {event.shard.id} ready", Ansi.LGREEN)

    async def _on_guild_join(self, event: hikari.GuildJoinEvent) -> None:
        """Handle bot joining a guild."""
        log(f"Joined guild: {event.guild.name} ({event.guild.id})", Ansi.LGREEN)

        # Create default guild config
        await discord_repositories.guild.create(
            guild_id=event.guild.id,
            fallback_webhook="",  # Will be configured by admin
        )

    async def _on_guild_leave(self, event: hikari.GuildLeaveEvent) -> None:
        """Handle bot leaving a guild."""
        log(f"Left guild: {event.guild_id}", Ansi.LYELLOW)

        # Optionally deactivate guild config instead of deleting
        # await discord_repositories.guild.update(event.guild_id, is_active=False)

    async def _update_presence(self) -> None:
        """Update bot presence from database configuration."""
        if not self._bot:
            return

        # Get primary guild's bot status (or use default)
        # For now, use a default status
        activity = hikari.Activity(
            name="osu! rankings",
            type=hikari.ActivityType.WATCHING,
        )

        await self._bot.update_presence(
            activity=activity,
            status=hikari.Status.ONLINE,
        )


# Global bot instance
discord_bot = DiscordBot()
```

## 3. Integration with Main Application

### 3.1 Update `main.py`

Add Discord bot startup/shutdown to the main application:

```python
# In startup sequence
from app.discord.bot import discord_bot
await discord_bot.start()

# In shutdown sequence
await discord_bot.stop()
```

### 3.2 Update `app/settings.py`

Add new environment variables:

```python
# Discord bot configuration
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN") or None
DISCORD_ENCRYPTION_KEY = os.environ.get("DISCORD_ENCRYPTION_KEY") or None

# Remove old webhook settings (deprecated)
# DISCORD_AUDIT_LOG_WEBHOOK = ...
# DISCORD_INVITE = ...
```

## 4. Health Check Model

### 4.1 `app/discord/services/health_service.py`

```python
"""Health check service for Discord bot."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BotHealth:
    """Bot health status information."""

    is_connected: bool = False
    uptime_seconds: float = 0.0
    guild_count: int = 0
    message_queue_size: int = 0
    last_error: str | None = None
    last_error_time: datetime | None = None
    reconnect_attempts: int = 0
    shard_id: int | None = None


class HealthService:
    """Service for monitoring bot health."""

    def __init__(self) -> None:
        self._start_time: float = time.time()
        self._health: BotHealth = BotHealth()

    @property
    def health(self) -> BotHealth:
        """Get current health status."""
        self._health.uptime_seconds = time.time() - self._start_time
        return self._health

    def update_connection_status(self, connected: bool, guild_count: int = 0) -> None:
        """Update connection status."""
        self._health.is_connected = connected
        self._health.guild_count = guild_count

    def record_error(self, error: str) -> None:
        """Record an error."""
        self._health.last_error = error
        self._health.last_error_time = datetime.utcnow()

    def update_queue_size(self, size: int) -> None:
        """Update message queue size."""
        self._health.message_queue_size = size

    def to_dict(self) -> dict:
        """Convert health to dictionary."""
        return {
            "is_connected": self._health.is_connected,
            "uptime_seconds": self._health.uptime_seconds,
            "guild_count": self._health.guild_count,
            "message_queue_size": self._health.message_queue_size,
            "last_error": self._health.last_error,
            "last_error_time": (
                self._health.last_error_time.isoformat()
                if self._health.last_error_time
                else None
            ),
            "reconnect_attempts": self._health.reconnect_attempts,
        }


# Global instance
health_service = HealthService()
```

## 5. Commit Message

```
feat(discord): add core bot infrastructure with Hikari

- Initialize Hikari bot with Lightbulb command framework
- Add connection management with exponential backoff reconnection
- Implement graceful shutdown handling
- Add health monitoring service
- Register event handlers for guild join/leave, shard ready
- Add constants for notification types, colors, and emojis
- Update settings.py with new environment variables
- Remove deprecated DISCORD_AUDIT_LOG_WEBHOOK and DISCORD_INVITE
```
