# Phase 3 — Encryption Utilities

## Scope

Implement AES-256-GCM encryption for sensitive database fields (webhook URLs, API tokens, etc.) with transparent encryption/decryption on read/write operations.

## 1. Encryption Manager

### 1.1 `app/discord/encryption.py`

```python
"""AES-256-GCM encryption utilities for sensitive data."""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

if TYPE_CHECKING:
    from app import settings


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""


class EncryptionManager:
    """Manages AES-256-GCM encryption for sensitive fields."""

    def __init__(self, key: str | None = None) -> None:
        """
        Initialize encryption manager.

        Args:
            key: 32-byte hex string for AES-256 key.
                 If None, loads from settings.
        """
        if key is None:
            from app import settings
            key = settings.DISCORD_ENCRYPTION_KEY

        if not key:
            raise EncryptionError("Encryption key not configured")

        # Decode hex key to bytes
        try:
            self._key = bytes.fromhex(key)
        except ValueError:
            # If not hex, hash it to get 32 bytes
            self._key = hashlib.sha256(key.encode()).digest()

        if len(self._key) != 32:
            raise EncryptionError("Encryption key must be 32 bytes for AES-256")

        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.

        Args:
            plaintext: String to encrypt.

        Returns:
            Base64-encoded string containing nonce + ciphertext + tag.
        """
        if not plaintext:
            return plaintext

        try:
            # Generate random nonce (12 bytes for GCM)
            import os
            nonce = os.urandom(12)

            # Encrypt
            ciphertext = self._aesgcm.encrypt(
                nonce,
                plaintext.encode("utf-8"),
                None,  # No additional authenticated data
            )

            # Combine nonce + ciphertext and encode
            combined = nonce + ciphertext
            return base64.b64encode(combined).decode("ascii")

        except Exception as exc:
            raise EncryptionError(f"Encryption failed: {exc}") from exc

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt encrypted string.

        Args:
            encrypted: Base64-encoded string from encrypt().

        Returns:
            Decrypted plaintext string.
        """
        if not encrypted:
            return encrypted

        try:
            # Decode base64
            combined = base64.b64decode(encrypted.encode("ascii"))

            # Extract nonce (first 12 bytes) and ciphertext
            nonce = combined[:12]
            ciphertext = combined[12:]

            # Decrypt
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)

            return plaintext.decode("utf-8")

        except Exception as exc:
            raise EncryptionError(f"Decryption failed: {exc}") from exc

    def encrypt_dict_fields(self, data: dict, fields: list[str]) -> dict:
        """
        Encrypt specific fields in a dictionary.

        Args:
            data: Dictionary with data to encrypt.
            fields: List of field names to encrypt.

        Returns:
            New dictionary with specified fields encrypted.
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.encrypt(str(result[field]))
        return result

    def decrypt_dict_fields(self, data: dict, fields: list[str]) -> dict:
        """
        Decrypt specific fields in a dictionary.

        Args:
            data: Dictionary with encrypted fields.
            fields: List of field names to decrypt.

        Returns:
            New dictionary with specified fields decrypted.
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.decrypt(str(result[field]))
        return result


# Global encryption manager instance
_encryption_manager: EncryptionManager | None = None


def get_encryption_manager() -> EncryptionManager:
    """Get or create the global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


def encrypt(plaintext: str) -> str:
    """Convenience function to encrypt a string."""
    return get_encryption_manager().encrypt(plaintext)


def decrypt(encrypted: str) -> str:
    """Convenience function to decrypt a string."""
    return get_encryption_manager().decrypt(encrypted)
```

## 2. Encrypted Repository Mixin

### 2.1 `app/discord/repositories/__init__.py` (Update)

Add encrypted repository mixin:

```python
"""Discord module repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.discord.encryption import decrypt, encrypt

if TYPE_CHECKING:
    from app.discord.repositories.guild_repo import GuildRepo
    from app.discord.repositories.channel_repo import ChannelRepo
    from app.discord.repositories.user_repo import UserRepo
    from app.discord.repositories.message_repo import MessageRepo
    from app.discord.repositories.component_repo import ComponentRepo
    from app.discord.repositories.template_repo import TemplateRepo
    from app.discord.repositories.repo_repo import RepoRepo


class EncryptedRepoMixin:
    """Mixin for repositories that handle encrypted fields."""

    # Override in subclasses to specify which fields are encrypted
    encrypted_fields: list[str] = []

    def _encrypt_row(self, row: dict | None) -> dict | None:
        """Encrypt sensitive fields in a row before storing."""
        if row is None:
            return None
        return self._encrypt_fields(row)

    def _decrypt_row(self, row: dict | None) -> dict | None:
        """Decrypt sensitive fields in a row after fetching."""
        if row is None:
            return None
        return self._decrypt_fields(row)

    def _encrypt_fields(self, data: dict) -> dict:
        """Encrypt specified fields in a dictionary."""
        result = data.copy()
        for field in self.encrypted_fields:
            if field in result and result[field]:
                result[field] = encrypt(str(result[field]))
        return result

    def _decrypt_fields(self, data: dict) -> dict:
        """Decrypt specified fields in a dictionary."""
        result = data.copy()
        for field in self.encrypted_fields:
            if field in result and result[field]:
                result[field] = decrypt(str(result[field]))
        return result


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

## 3. Update Repositories for Encryption

### 3.1 `app/discord/repositories/guild_repo.py` (Update)

```python
"""Guild repository for discord_guilds table."""

from __future__ import annotations

from typing import TypedDict

from app.discord.repositories import EncryptedRepoMixin
from app.state.services import database


class GuildConfig(TypedDict):
    id: int
    fallback_webhook: str
    invite_link: str | None
    bot_status: str
    notification_defaults: dict | None
    created_at: str
    updated_at: str


class GuildRepo(EncryptedRepoMixin):
    """Repository for guild configurations."""

    encrypted_fields = ["fallback_webhook"]

    async def get(self, guild_id: int) -> GuildConfig | None:
        """Get guild configuration by ID."""
        query = """
            SELECT id, fallback_webhook, invite_link, bot_status,
                   notification_defaults, created_at, updated_at
            FROM discord_guilds
            WHERE id = :guild_id
        """
        row = await database.fetch_one(query, {"guild_id": guild_id})
        return self._decrypt_row(row)

    async def create(self, guild_id: int, fallback_webhook: str) -> None:
        """Create a new guild configuration."""
        # Encrypt webhook before storing
        encrypted_webhook = self._encrypt_fields({
            "fallback_webhook": fallback_webhook
        })["fallback_webhook"]

        query = """
            INSERT INTO discord_guilds (id, fallback_webhook)
            VALUES (:guild_id, :fallback_webhook)
            ON DUPLICATE KEY UPDATE fallback_webhook = :fallback_webhook
        """
        await database.execute(query, {
            "guild_id": guild_id,
            "fallback_webhook": encrypted_webhook,
        })

    async def update(self, guild_id: int, **kwargs: object) -> None:
        """Update guild configuration."""
        allowed = {"fallback_webhook", "invite_link", "bot_status", "notification_defaults"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        # Encrypt sensitive fields
        updates = self._encrypt_fields(updates)

        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        query = f"UPDATE discord_guilds SET {set_clause} WHERE id = :guild_id"
        await database.execute(query, {"guild_id": guild_id, **updates})

    async def delete(self, guild_id: int) -> None:
        """Delete guild configuration (cascades to channels, etc.)."""
        query = "DELETE FROM discord_guilds WHERE id = :guild_id"
        await database.execute(query, {"guild_id": guild_id})

    async def get_all(self) -> list[GuildConfig]:
        """Get all guild configurations."""
        query = """
            SELECT id, fallback_webhook, invite_link, bot_status,
                   notification_defaults, created_at, updated_at
            FROM discord_guilds
        """
        rows = await database.fetch_all(query)
        return [self._decrypt_row(row) for row in rows]
```

### 3.2 `app/discord/repositories/repo_repo.py` (Update)

```python
"""Repository for discord_repos table (GitHub configurations)."""

from __future__ import annotations

from typing import TypedDict

from app.discord.repositories import EncryptedRepoMixin
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


class RepoRepo(EncryptedRepoMixin):
    """Repository for GitHub repository configurations."""

    encrypted_fields = ["webhook_secret"]

    async def get(self, repo_id: int) -> RepoConfig | None:
        """Get repo configuration by ID."""
        query = """
            SELECT id, repo_owner, repo_name, guild_id, channel_id,
                   webhook_secret, events, branch_filter, job_filter,
                   commit_limit, is_active, created_at, updated_at
            FROM discord_repos
            WHERE id = :repo_id
        """
        row = await database.fetch_one(query, {"repo_id": repo_id})
        return self._decrypt_row(row)

    async def get_by_repo(self, owner: str, name: str, guild_id: int) -> RepoConfig | None:
        """Get repo configuration by owner/name/guild."""
        query = """
            SELECT id, repo_owner, repo_name, guild_id, channel_id,
                   webhook_secret, events, branch_filter, job_filter,
                   commit_limit, is_active, created_at, updated_at
            FROM discord_repos
            WHERE repo_owner = :owner AND repo_name = :name AND guild_id = :guild_id
        """
        row = await database.fetch_one(query, {
            "owner": owner,
            "name": name,
            "guild_id": guild_id,
        })
        return self._decrypt_row(row)

    async def get_by_guild(self, guild_id: int) -> list[RepoConfig]:
        """Get all repo configurations for a guild."""
        query = """
            SELECT id, repo_owner, repo_name, guild_id, channel_id,
                   webhook_secret, events, branch_filter, job_filter,
                   commit_limit, is_active, created_at, updated_at
            FROM discord_repos
            WHERE guild_id = :guild_id AND is_active = TRUE
        """
        rows = await database.fetch_all(query, {"guild_id": guild_id})
        return [self._decrypt_row(row) for row in rows]

    async def get_by_channel(self, channel_id: int) -> list[RepoConfig]:
        """Get all repo configurations for a channel."""
        query = """
            SELECT id, repo_owner, repo_name, guild_id, channel_id,
                   webhook_secret, events, branch_filter, job_filter,
                   commit_limit, is_active, created_at, updated_at
            FROM discord_repos
            WHERE channel_id = :channel_id AND is_active = TRUE
        """
        rows = await database.fetch_all(query, {"channel_id": channel_id})
        return [self._decrypt_row(row) for row in rows]

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
        # Encrypt webhook secret before storing
        encrypted_secret = self._encrypt_fields({
            "webhook_secret": webhook_secret
        })["webhook_secret"]

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
            "webhook_secret": encrypted_secret,
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

        # Encrypt sensitive fields
        updates = self._encrypt_fields(updates)

        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        query = f"UPDATE discord_repos SET {set_clause} WHERE id = :repo_id"
        await database.execute(query, {"repo_id": repo_id, **updates})

    async def delete(self, repo_id: int) -> None:
        """Delete a repo configuration."""
        query = "DELETE FROM discord_repos WHERE id = :repo_id"
        await database.execute(query, {"repo_id": repo_id})
```

## 4. Commit Message

```
feat(discord): add AES-256-GCM encryption for sensitive fields

- Implement EncryptionManager with AES-256-GCM
- Add EncryptedRepoMixin for transparent encryption/decryption
- Update GuildRepo and RepoRepo to encrypt sensitive fields
- Encrypt fallback_webhook and webhook_secret in database
- Add convenience encrypt/decrypt functions
```
