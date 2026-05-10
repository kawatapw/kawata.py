# Phase 1 — Database Schema

## Scope

Create all database tables for the Discord module, add migrations to existing migration files, and create repository base classes.

## 1. Migration Files

### 1.1 Update `migrations/base.sql`

Add the following tables to `migrations/base.sql` under a new version comment:

```sql
-- v{next_version} - Discord integration module

-- Guild configurations
CREATE TABLE IF NOT EXISTS discord_guilds (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    fallback_webhook TEXT NOT NULL,
    invite_link VARCHAR(255) DEFAULT NULL,
    bot_status VARCHAR(128) DEFAULT 'Watching osu! rankings',
    notification_defaults JSON DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Channel configurations
CREATE TABLE IF NOT EXISTS discord_channels (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    guild_id BIGINT UNSIGNED NOT NULL,
    channel_type ENUM('audit', 'announcements', 'map_rank', 'github', 'general') NOT NULL,
    notification_types JSON DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES discord_guilds(id) ON DELETE CASCADE,
    UNIQUE KEY unique_guild_channel (guild_id, channel_type)
);

-- User account linking
CREATE TABLE IF NOT EXISTS discord_users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    osu_user_id INT UNSIGNED NOT NULL,
    discord_user_id BIGINT UNSIGNED NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    linked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (osu_user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_discord_user (discord_user_id),
    INDEX idx_osu_user (osu_user_id)
);

-- Message tracking
CREATE TABLE IF NOT EXISTS discord_messages (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    channel_id BIGINT UNSIGNED NOT NULL,
    guild_id BIGINT UNSIGNED NOT NULL,
    message_type ENUM('map_rank', 'github_push', 'github_pr', 'announcement') NOT NULL,
    metadata JSON DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES discord_guilds(id) ON DELETE CASCADE,
    INDEX idx_type_active (message_type, is_active)
);

-- Interactive components
CREATE TABLE IF NOT EXISTS discord_components (
    id VARCHAR(64) NOT NULL PRIMARY KEY,
    component_type ENUM('button', 'select', 'role_select') NOT NULL,
    message_id BIGINT UNSIGNED NOT NULL,
    channel_id BIGINT UNSIGNED NOT NULL,
    guild_id BIGINT UNSIGNED NOT NULL,
    data JSON NOT NULL,
    expires_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES discord_messages(id) ON DELETE CASCADE,
    INDEX idx_expires (expires_at)
);

-- Message templates
CREATE TABLE IF NOT EXISTS discord_templates (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    guild_id BIGINT UNSIGNED DEFAULT NULL,
    template_type ENUM('map_rank', 'github', 'announcement', 'custom') NOT NULL,
    template_data JSON NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES discord_guilds(id) ON DELETE CASCADE,
    UNIQUE KEY unique_guild_template (guild_id, name)
);

-- GitHub repository configurations
CREATE TABLE IF NOT EXISTS discord_repos (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    repo_owner VARCHAR(128) NOT NULL,
    repo_name VARCHAR(128) NOT NULL,
    guild_id BIGINT UNSIGNED NOT NULL,
    channel_id BIGINT UNSIGNED NOT NULL,
    webhook_secret TEXT NOT NULL,
    events JSON NOT NULL,
    branch_filter JSON DEFAULT NULL,
    job_filter JSON DEFAULT NULL,
    commit_limit INT UNSIGNED DEFAULT 10,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES discord_guilds(id) ON DELETE CASCADE,
    UNIQUE KEY unique_repo (repo_owner, repo_name, guild_id)
);

-- Failed message queue
CREATE TABLE IF NOT EXISTS discord_failed_messages (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    channel_id BIGINT UNSIGNED NOT NULL,
    guild_id BIGINT UNSIGNED NOT NULL,
    message_data JSON NOT NULL,
    retry_count INT UNSIGNED NOT NULL DEFAULT 0,
    max_retries INT UNSIGNED NOT NULL DEFAULT 5,
    last_error TEXT DEFAULT NULL,
    next_retry_at TIMESTAMP NULL DEFAULT NULL,
    status ENUM('pending', 'retrying', 'failed', 'dead_letter') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status_retry (status, next_retry_at)
);
```

### 1.2 Update `migrations/migrations.sql`

Add migration entry following the existing pattern:

```sql
# v{next_version}

-- Discord integration module tables
CREATE TABLE IF NOT EXISTS discord_guilds (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    fallback_webhook TEXT NOT NULL,
    invite_link VARCHAR(255) DEFAULT NULL,
    bot_status VARCHAR(128) DEFAULT 'Watching osu! rankings',
    notification_defaults JSON DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- (Repeat all tables from base.sql with IF NOT EXISTS)
```

## 2. Repository Models

### 2.1 `app/discord/repositories/__init__.py`

```python
"""Discord module repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.discord.repositories.guild_repo import GuildRepo
    from app.discord.repositories.channel_repo import ChannelRepo
    from app.discord.repositories.user_repo import UserRepo
    from app.discord.repositories.message_repo import MessageRepo
    from app.discord.repositories.component_repo import ComponentRepo
    from app.discord.repositories.template_repo import TemplateRepo
    from app.discord.repositories.repo_repo import RepoRepo


class DiscordRepositories:
    """Container for all Discord repository instances."""

    def __init__(self) -> None:
        self.guild = GuildRepo()
        self.channel = ChannelRepo()
        self.user = UserRepo()
        self.message = MessageRepo()
        self.component = ComponentRepo()
        self.template = TemplateRepo()
        self.repo = RepoRepo()


discord_repositories = DiscordRepositories()
```

### 2.2 `app/discord/repositories/guild_repo.py`

```python
"""Guild repository for discord_guilds table."""

from __future__ import annotations

from typing import TypedDict

from app.state.services import database


class GuildConfig(TypedDict):
    id: int
    fallback_webhook: str
    invite_link: str | None
    bot_status: str
    notification_defaults: dict | None
    created_at: str
    updated_at: str


class GuildRepo:
    """Repository for guild configurations."""

    async def get(self, guild_id: int) -> GuildConfig | None:
        """Get guild configuration by ID."""
        query = """
            SELECT id, fallback_webhook, invite_link, bot_status,
                   notification_defaults, created_at, updated_at
            FROM discord_guilds
            WHERE id = :guild_id
        """
        return await database.fetch_one(query, {"guild_id": guild_id})

    async def create(self, guild_id: int, fallback_webhook: str) -> None:
        """Create a new guild configuration."""
        query = """
            INSERT INTO discord_guilds (id, fallback_webhook)
            VALUES (:guild_id, :fallback_webhook)
            ON DUPLICATE KEY UPDATE fallback_webhook = :fallback_webhook
        """
        await database.execute(query, {
            "guild_id": guild_id,
            "fallback_webhook": fallback_webhook,
        })

    async def update(self, guild_id: int, **kwargs: object) -> None:
        """Update guild configuration."""
        allowed = {"fallback_webhook", "invite_link", "bot_status", "notification_defaults"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        query = f"UPDATE discord_guilds SET {set_clause} WHERE id = :guild_id"
        await database.execute(query, {"guild_id": guild_id, **updates})

    async def delete(self, guild_id: int) -> None:
        """Delete guild configuration (cascades to channels, etc.)."""
        query = "DELETE FROM discord_guilds WHERE id = :guild_id"
        await database.execute(query, {"guild_id": guild_id})
```

### 2.3 `app/discord/repositories/channel_repo.py`

```python
"""Channel repository for discord_channels table."""

from __future__ import annotations

from typing import TypedDict

from app.state.services import database


class ChannelConfig(TypedDict):
    id: int
    guild_id: int
    channel_type: str
    notification_types: list[str] | None
    is_active: bool
    created_at: str


class ChannelRepo:
    """Repository for channel configurations."""

    async def get(self, channel_id: int) -> ChannelConfig | None:
        """Get channel configuration by ID."""
        query = """
            SELECT id, guild_id, channel_type, notification_types,
                   is_active, created_at
            FROM discord_channels
            WHERE id = :channel_id
        """
        return await database.fetch_one(query, {"channel_id": channel_id})

    async def get_by_type(self, guild_id: int, channel_type: str) -> ChannelConfig | None:
        """Get channel configuration by guild and type."""
        query = """
            SELECT id, guild_id, channel_type, notification_types,
                   is_active, created_at
            FROM discord_channels
            WHERE guild_id = :guild_id AND channel_type = :channel_type
        """
        return await database.fetch_one(query, {
            "guild_id": guild_id,
            "channel_type": channel_type,
        })

    async def get_by_guild(self, guild_id: int) -> list[ChannelConfig]:
        """Get all channel configurations for a guild."""
        query = """
            SELECT id, guild_id, channel_type, notification_types,
                   is_active, created_at
            FROM discord_channels
            WHERE guild_id = :guild_id AND is_active = TRUE
        """
        return await database.fetch_all(query, {"guild_id": guild_id})

    async def create(
        self,
        channel_id: int,
        guild_id: int,
        channel_type: str,
        notification_types: list[str] | None = None,
    ) -> None:
        """Create a new channel configuration."""
        query = """
            INSERT INTO discord_channels (id, guild_id, channel_type, notification_types)
            VALUES (:channel_id, :guild_id, :channel_type, :notification_types)
            ON DUPLICATE KEY UPDATE
                channel_type = :channel_type,
                notification_types = :notification_types,
                is_active = TRUE
        """
        await database.execute(query, {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "channel_type": channel_type,
            "notification_types": notification_types,
        })

    async def update(self, channel_id: int, **kwargs: object) -> None:
        """Update channel configuration."""
        allowed = {"channel_type", "notification_types", "is_active"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        query = f"UPDATE discord_channels SET {set_clause} WHERE id = :channel_id"
        await database.execute(query, {"channel_id": channel_id, **updates})

    async def delete(self, channel_id: int) -> None:
        """Delete channel configuration."""
        query = "DELETE FROM discord_channels WHERE id = :channel_id"
        await database.execute(query, {"channel_id": channel_id})
```

### 2.4 `app/discord/repositories/user_repo.py`

```python
"""User repository for discord_users table."""

from __future__ import annotations

from typing import TypedDict

from app.state.services import database


class UserLink(TypedDict):
    id: int
    osu_user_id: int
    discord_user_id: int
    is_primary: bool
    linked_at: str


class UserRepo:
    """Repository for Discord-osu! account linking."""

    async def get_by_osu(self, osu_user_id: int) -> list[UserLink]:
        """Get all Discord links for an osu! user."""
        query = """
            SELECT id, osu_user_id, discord_user_id, is_primary, linked_at
            FROM discord_users
            WHERE osu_user_id = :osu_user_id
            ORDER BY is_primary DESC, linked_at ASC
        """
        return await database.fetch_all(query, {"osu_user_id": osu_user_id})

    async def get_by_discord(self, discord_user_id: int) -> UserLink | None:
        """Get user link by Discord user ID."""
        query = """
            SELECT id, osu_user_id, discord_user_id, is_primary, linked_at
            FROM discord_users
            WHERE discord_user_id = :discord_user_id
        """
        return await database.fetch_one(query, {"discord_user_id": discord_user_id})

    async def get_primary(self, osu_user_id: int) -> UserLink | None:
        """Get primary Discord link for an osu! user."""
        query = """
            SELECT id, osu_user_id, discord_user_id, is_primary, linked_at
            FROM discord_users
            WHERE osu_user_id = :osu_user_id AND is_primary = TRUE
        """
        return await database.fetch_one(query, {"osu_user_id": osu_user_id})

    async def create(self, osu_user_id: int, discord_user_id: int, is_primary: bool = False) -> None:
        """Create a new user link."""
        query = """
            INSERT INTO discord_users (osu_user_id, discord_user_id, is_primary)
            VALUES (:osu_user_id, :discord_user_id, :is_primary)
        """
        await database.execute(query, {
            "osu_user_id": osu_user_id,
            "discord_user_id": discord_user_id,
            "is_primary": is_primary,
        })

    async def set_primary(self, link_id: int, osu_user_id: int) -> None:
        """Set a link as primary (unsets others)."""
        # Unset all primary for this user
        await database.execute(
            "UPDATE discord_users SET is_primary = FALSE WHERE osu_user_id = :osu_user_id",
            {"osu_user_id": osu_user_id},
        )
        # Set the specified link as primary
        await database.execute(
            "UPDATE discord_users SET is_primary = TRUE WHERE id = :link_id",
            {"link_id": link_id},
        )

    async def delete(self, link_id: int) -> None:
        """Delete a user link."""
        query = "DELETE FROM discord_users WHERE id = :link_id"
        await database.execute(query, {"link_id": link_id})

    async def delete_by_discord(self, discord_user_id: int) -> None:
        """Delete all links for a Discord user."""
        query = "DELETE FROM discord_users WHERE discord_user_id = :discord_user_id"
        await database.execute(query, {"discord_user_id": discord_user_id})
```

### 2.5 `app/discord/repositories/message_repo.py`

```python
"""Message repository for discord_messages table."""

from __future__ import annotations

from typing import TypedDict

from app.state.services import database


class MessageRecord(TypedDict):
    id: int
    channel_id: int
    guild_id: int
    message_type: str
    metadata: dict | None
    is_active: bool
    created_at: str
    updated_at: str


class MessageRepo:
    """Repository for Discord message tracking."""

    async def get(self, message_id: int) -> MessageRecord | None:
        """Get message record by Discord message ID."""
        query = """
            SELECT id, channel_id, guild_id, message_type, metadata,
                   is_active, created_at, updated_at
            FROM discord_messages
            WHERE id = :message_id
        """
        return await database.fetch_one(query, {"message_id": message_id})

    async def get_active_by_type(
        self,
        guild_id: int,
        message_type: str,
        metadata_filter: dict | None = None,
    ) -> list[MessageRecord]:
        """Get active messages by type and optional metadata filter."""
        query = """
            SELECT id, channel_id, guild_id, message_type, metadata,
                   is_active, created_at, updated_at
            FROM discord_messages
            WHERE guild_id = :guild_id
              AND message_type = :message_type
              AND is_active = TRUE
        """
        params: dict[str, object] = {
            "guild_id": guild_id,
            "message_type": message_type,
        }

        if metadata_filter:
            for key, value in metadata_filter.items():
                query += f" AND JSON_EXTRACT(metadata, '$.{key}') = :{key}"
                params[key] = value

        return await database.fetch_all(query, params)

    async def create(
        self,
        message_id: int,
        channel_id: int,
        guild_id: int,
        message_type: str,
        metadata: dict | None = None,
    ) -> None:
        """Create a new message record."""
        query = """
            INSERT INTO discord_messages (id, channel_id, guild_id, message_type, metadata)
            VALUES (:message_id, :channel_id, :guild_id, :message_type, :metadata)
        """
        await database.execute(query, {
            "message_id": message_id,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "message_type": message_type,
            "metadata": metadata,
        })

    async def update_metadata(self, message_id: int, metadata: dict) -> None:
        """Update message metadata."""
        query = """
            UPDATE discord_messages
            SET metadata = JSON_MERGE_PATCH(metadata, :metadata)
            WHERE id = :message_id
        """
        await database.execute(query, {
            "message_id": message_id,
            "metadata": metadata,
        })

    async def deactivate(self, message_id: int) -> None:
        """Deactivate a message record."""
        query = "UPDATE discord_messages SET is_active = FALSE WHERE id = :message_id"
        await database.execute(query, {"message_id": message_id})

    async def delete_old(self, days: int = 30) -> int:
        """Delete inactive messages older than specified days."""
        query = """
            DELETE FROM discord_messages
            WHERE is_active = FALSE
              AND updated_at < DATE_SUB(NOW(), INTERVAL :days DAY)
        """
        result = await database.execute(query, {"days": days})
        return result or 0
```

### 2.6 `app/discord/repositories/component_repo.py`

```python
"""Component repository for discord_components table."""

from __future__ import annotations

from typing import TypedDict

from app.state.services import database


class ComponentRecord(TypedDict):
    id: str
    component_type: str
    message_id: int
    channel_id: int
    guild_id: int
    data: dict
    expires_at: str | None
    created_at: str


class ComponentRepo:
    """Repository for interactive component persistence."""

    async def get(self, custom_id: str) -> ComponentRecord | None:
        """Get component by custom ID."""
        query = """
            SELECT id, component_type, message_id, channel_id, guild_id,
                   data, expires_at, created_at
            FROM discord_components
            WHERE id = :custom_id
              AND (expires_at IS NULL OR expires_at > NOW())
        """
        return await database.fetch_one(query, {"custom_id": custom_id})

    async def get_by_message(self, message_id: int) -> list[ComponentRecord]:
        """Get all components for a message."""
        query = """
            SELECT id, component_type, message_id, channel_id, guild_id,
                   data, expires_at, created_at
            FROM discord_components
            WHERE message_id = :message_id
              AND (expires_at IS NULL OR expires_at > NOW())
        """
        return await database.fetch_all(query, {"message_id": message_id})

    async def create(
        self,
        custom_id: str,
        component_type: str,
        message_id: int,
        channel_id: int,
        guild_id: int,
        data: dict,
        expires_at: str | None = None,
    ) -> None:
        """Create a new component record."""
        query = """
            INSERT INTO discord_components
                (id, component_type, message_id, channel_id, guild_id, data, expires_at)
            VALUES
                (:custom_id, :component_type, :message_id, :channel_id, :guild_id, :data, :expires_at)
            ON DUPLICATE KEY UPDATE
                data = :data,
                expires_at = :expires_at
        """
        await database.execute(query, {
            "custom_id": custom_id,
            "component_type": component_type,
            "message_id": message_id,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "data": data,
            "expires_at": expires_at,
        })

    async def delete(self, custom_id: str) -> None:
        """Delete a component record."""
        query = "DELETE FROM discord_components WHERE id = :custom_id"
        await database.execute(query, {"custom_id": custom_id})

    async def delete_by_message(self, message_id: int) -> None:
        """Delete all components for a message."""
        query = "DELETE FROM discord_components WHERE message_id = :message_id"
        await database.execute(query, {"message_id": message_id})

    async def cleanup_expired(self) -> int:
        """Delete expired components."""
        query = "DELETE FROM discord_components WHERE expires_at IS NOT NULL AND expires_at <= NOW()"
        result = await database.execute(query)
        return result or 0
```

### 2.7 `app/discord/repositories/template_repo.py`

```python
"""Template repository for discord_templates table."""

from __future__ import annotations

from typing import TypedDict

from app.state.services import database


class TemplateRecord(TypedDict):
    id: int
    name: str
    guild_id: int | None
    template_type: str
    template_data: dict
    is_default: bool
    created_at: str
    updated_at: str


class TemplateRepo:
    """Repository for message templates."""

    async def get(self, name: str, guild_id: int | None = None) -> TemplateRecord | None:
        """Get template by name, preferring guild-specific over global."""
        query = """
            SELECT id, name, guild_id, template_type, template_data,
                   is_default, created_at, updated_at
            FROM discord_templates
            WHERE name = :name
              AND (guild_id = :guild_id OR guild_id IS NULL)
            ORDER BY guild_id IS NULL ASC
            LIMIT 1
        """
        return await database.fetch_one(query, {
            "name": name,
            "guild_id": guild_id,
        })

    async def get_by_type(
        self,
        template_type: str,
        guild_id: int | None = None,
    ) -> list[TemplateRecord]:
        """Get all templates of a type."""
        query = """
            SELECT id, name, guild_id, template_type, template_data,
                   is_default, created_at, updated_at
            FROM discord_templates
            WHERE template_type = :template_type
              AND (guild_id = :guild_id OR guild_id IS NULL)
            ORDER BY guild_id IS NULL ASC, name ASC
        """
        return await database.fetch_all(query, {
            "template_type": template_type,
            "guild_id": guild_id,
        })

    async def get_default(self, template_type: str) -> TemplateRecord | None:
        """Get default template for a type."""
        query = """
            SELECT id, name, guild_id, template_type, template_data,
                   is_default, created_at, updated_at
            FROM discord_templates
            WHERE template_type = :template_type AND is_default = TRUE
            LIMIT 1
        """
        return await database.fetch_one(query, {"template_type": template_type})

    async def create(
        self,
        name: str,
        template_type: str,
        template_data: dict,
        guild_id: int | None = None,
        is_default: bool = False,
    ) -> None:
        """Create a new template."""
        query = """
            INSERT INTO discord_templates (name, guild_id, template_type, template_data, is_default)
            VALUES (:name, :guild_id, :template_type, :template_data, :is_default)
        """
        await database.execute(query, {
            "name": name,
            "guild_id": guild_id,
            "template_type": template_type,
            "template_data": template_data,
            "is_default": is_default,
        })

    async def update(self, template_id: int, **kwargs: object) -> None:
        """Update template."""
        allowed = {"name", "template_data", "is_default"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        query = f"UPDATE discord_templates SET {set_clause} WHERE id = :template_id"
        await database.execute(query, {"template_id": template_id, **updates})

    async def set_default(self, template_id: int, template_type: str) -> None:
        """Set template as default for its type."""
        # Unset current default
        await database.execute(
            "UPDATE discord_templates SET is_default = FALSE WHERE template_type = :template_type",
            {"template_type": template_type},
        )
        # Set new default
        await database.execute(
            "UPDATE discord_templates SET is_default = TRUE WHERE id = :template_id",
            {"template_id": template_id},
        )

    async def delete(self, template_id: int) -> None:
        """Delete a template."""
        query = "DELETE FROM discord_templates WHERE id = :template_id"
        await database.execute(query, {"template_id": template_id})
```

### 2.8 `app/discord/repositories/repo_repo.py`

```python
"""Repository for discord_repos table (GitHub configurations)."""

from __future__ import annotations

from typing import TypedDict

from app.state.services import database


class RepoConfig(TypedDict):
    id: int
    repo_owner: str
    repo_name: str
    guild_id: int
    channel_id: int
    webhook_secret: str
    events: list[str]
    branch_filter: list[str] | None
    job_filter: list[str] | None
    commit_limit: int
    is_active: bool
    created_at: str
    updated_at: str


class RepoRepo:
    """Repository for GitHub repository configurations."""

    async def get(self, repo_id: int) -> RepoConfig | None:
        """Get repo configuration by ID."""
        query = """
            SELECT id, repo_owner, repo_name, guild_id, channel_id,
                   webhook_secret, events, branch_filter, job_filter,
                   commit_limit, is_active, created_at, updated_at
            FROM discord_repos
            WHERE id = :repo_id
        """
        return await database.fetch_one(query, {"repo_id": repo_id})

    async def get_by_repo(self, owner: str, name: str, guild_id: int) -> RepoConfig | None:
        """Get repo configuration by owner/name/guild."""
        query = """
            SELECT id, repo_owner, repo_name, guild_id, channel_id,
                   webhook_secret, events, branch_filter, job_filter,
                   commit_limit, is_active, created_at, updated_at
            FROM discord_repos
            WHERE repo_owner = :owner AND repo_name = :name AND guild_id = :guild_id
        """
        return await database.fetch_one(query, {
            "owner": owner,
            "name": name,
            "guild_id": guild_id,
        })

    async def get_by_guild(self, guild_id: int) -> list[RepoConfig]:
        """Get all repo configurations for a guild."""
        query = """
            SELECT id, repo_owner, repo_name, guild_id, channel_id,
                   webhook_secret, events, branch_filter, job_filter,
                   commit_limit, is_active, created_at, updated_at
            FROM discord_repos
            WHERE guild_id = :guild_id AND is_active = TRUE
        """
        return await database.fetch_all(query, {"guild_id": guild_id})

    async def get_by_channel(self, channel_id: int) -> list[RepoConfig]:
        """Get all repo configurations for a channel."""
        query = """
            SELECT id, repo_owner, repo_name, guild_id, channel_id,
                   webhook_secret, events, branch_filter, job_filter,
                   commit_limit, is_active, created_at, updated_at
            FROM discord_repos
            WHERE channel_id = :channel_id AND is_active = TRUE
        """
        return await database.fetch_all(query, {"channel_id": channel_id})

    async def create(
        self,
        repo_owner: str,
        repo_name: str,
        guild_id: int,
        channel_id: int,
        webhook_secret: str,
        events: list[str],
        branch_filter: list[str] | None = None,
        job_filter: list[str] | None = None,
        commit_limit: int = 10,
    ) -> None:
        """Create a new repo configuration."""
        query = """
            INSERT INTO discord_repos
                (repo_owner, repo_name, guild_id, channel_id, webhook_secret,
                 events, branch_filter, job_filter, commit_limit)
            VALUES
                (:repo_owner, :repo_name, :guild_id, :channel_id, :webhook_secret,
                 :events, :branch_filter, :job_filter, :commit_limit)
        """
        await database.execute(query, {
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "guild_id": guild_id,
            "channel_id": channel_id,
            "webhook_secret": webhook_secret,
            "events": events,
            "branch_filter": branch_filter,
            "job_filter": job_filter,
            "commit_limit": commit_limit,
        })

    async def update(self, repo_id: int, **kwargs: object) -> None:
        """Update repo configuration."""
        allowed = {
            "channel_id", "webhook_secret", "events", "branch_filter",
            "job_filter", "commit_limit", "is_active",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        query = f"UPDATE discord_repos SET {set_clause} WHERE id = :repo_id"
        await database.execute(query, {"repo_id": repo_id, **updates})

    async def delete(self, repo_id: int) -> None:
        """Delete a repo configuration."""
        query = "DELETE FROM discord_repos WHERE id = :repo_id"
        await database.execute(query, {"repo_id": repo_id})
```

## 3. Commit Message

```
feat(discord): add database schema for Discord integration module

- Add 8 new tables: discord_guilds, discord_channels, discord_users,
  discord_messages, discord_components, discord_templates, discord_repos,
  discord_failed_messages
- Create repository classes for all tables with typed returns
- Add migrations to migrations.sql and base.sql
- Support for encrypted fields, JSON metadata, and cascading deletes
```
