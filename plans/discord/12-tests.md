# Phase 12 — Tests

## Scope

Create comprehensive unit tests with mocking for the Discord module and integration tests for webhook endpoints.

## 1. Test Structure

```
tests/
├── unit/
│   └── discord/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_encryption.py
│       ├── test_repositories.py
│       ├── test_message_service.py
│       ├── test_component_service.py
│       ├── test_template_renderer.py
│       ├── test_account_linking.py
│       └── test_map_notifications.py
└── integration/
    └── discord/
        ├── __init__.py
        ├── conftest.py
        └── test_webhook_endpoints.py
```

## 2. Unit Test Configuration

### 2.1 `tests/unit/discord/conftest.py`

```python
"""Unit test configuration for Discord module."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch


@pytest.fixture
def mock_database():
    """Mock database for repository tests."""
    with patch("app.discord.repositories.database") as mock:
        mock.fetch_one = AsyncMock(return_value=None)
        mock.fetch_all = AsyncMock(return_value=[])
        mock.execute = AsyncMock(return_value=1)
        yield mock


@pytest.fixture
def mock_bot():
    """Mock Hikari bot for service tests."""
    with patch("app.discord.services.message_service.discord_bot") as mock:
        mock.bot = MagicMock()
        mock.is_connected = True
        mock.bot.rest = MagicMock()
        mock.bot.rest.send_message = AsyncMock(
            return_value=MagicMock(id=123456789)
        )
        mock.bot.rest.edit_message = AsyncMock(return_value=MagicMock())
        mock.bot.rest.delete_message = AsyncMock(return_value=None)
        yield mock


@pytest.fixture
def mock_encryption():
    """Mock encryption manager."""
    with patch("app.discord.repositories.get_encryption_manager") as mock:
        manager = MagicMock()
        manager.encrypt = MagicMock(side_effect=lambda x: f"enc:{x}")
        manager.decrypt = MagicMock(side_effect=lambda x: x.replace("enc:", ""))
        mock.return_value = manager
        yield manager


@pytest.fixture
def sample_guild_config():
    """Sample guild configuration."""
    return {
        "id": 123456789,
        "fallback_webhook": "https://discord.com/api/webhooks/test",
        "invite_link": "https://discord.gg/test",
        "bot_status": "Watching osu! rankings",
        "notification_defaults": {},
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }


@pytest.fixture
def sample_channel_config():
    """Sample channel configuration."""
    return {
        "id": 987654321,
        "guild_id": 123456789,
        "channel_type": "map_rank",
        "notification_types": ["map_ranked", "map_qualified"],
        "is_active": True,
        "created_at": "2024-01-01T00:00:00",
    }


@pytest.fixture
def sample_beatmap_set():
    """Sample beatmap set data."""
    return {
        "id": 12345,
        "title": "Test Map",
        "artist": "Test Artist",
        "creator": "Test Mapper",
        "bpm": 180,
    }


@pytest.fixture
def sample_difficulties():
    """Sample difficulty data."""
    return [
        {
            "id": 1,
            "name": "Easy",
            "mode": 0,
            "stars": 1.5,
            "cs": 2.0,
            "ar": 3.0,
            "hp": 4.0,
            "bpm": 180,
            "length": 120,
            "max_combo": 500,
        },
        {
            "id": 2,
            "name": "Hard",
            "mode": 0,
            "stars": 4.2,
            "cs": 4.0,
            "ar": 8.0,
            "hp": 6.0,
            "bpm": 180,
            "length": 150,
            "max_combo": 1200,
        },
    ]
```

## 3. Encryption Tests

### 3.1 `tests/unit/discord/test_encryption.py`

```python
"""Tests for encryption utilities."""

from __future__ import annotations

import pytest

from app.discord.encryption import EncryptionManager
from app.discord.encryption import EncryptionError


class TestEncryptionManager:
    """Tests for EncryptionManager."""

    def test_init_with_valid_key(self):
        """Test initialization with valid hex key."""
        key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        manager = EncryptionManager(key)
        assert manager._key == bytes.fromhex(key)

    def test_init_with_short_key(self):
        """Test initialization with short key (gets hashed)."""
        manager = EncryptionManager("short_key")
        assert len(manager._key) == 32

    def test_init_without_key(self):
        """Test initialization without key raises error."""
        with pytest.raises(EncryptionError):
            EncryptionManager(None)

    def test_encrypt_decrypt(self):
        """Test encryption and decryption roundtrip."""
        manager = EncryptionManager("test_key")
        plaintext = "Hello, World!"

        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)

        assert encrypted != plaintext
        assert decrypted == plaintext

    def test_encrypt_empty_string(self):
        """Test encryption of empty string."""
        manager = EncryptionManager("test_key")
        assert manager.encrypt("") == ""

    def test_decrypt_empty_string(self):
        """Test decryption of empty string."""
        manager = EncryptionManager("test_key")
        assert manager.decrypt("") == ""

    def test_encrypt_produces_different_ciphertext(self):
        """Test that encryption produces different ciphertext each time."""
        manager = EncryptionManager("test_key")
        plaintext = "Same plaintext"

        encrypted1 = manager.encrypt(plaintext)
        encrypted2 = manager.encrypt(plaintext)

        # Should be different due to random nonce
        assert encrypted1 != encrypted2

        # But both should decrypt to same plaintext
        assert manager.decrypt(encrypted1) == plaintext
        assert manager.decrypt(encrypted2) == plaintext

    def test_encrypt_dict_fields(self):
        """Test encryption of dictionary fields."""
        manager = EncryptionManager("test_key")
        data = {
            "public": "visible",
            "secret": "hidden",
            "another_secret": "also hidden",
        }

        encrypted = manager.encrypt_dict_fields(data, ["secret", "another_secret"])

        assert encrypted["public"] == "visible"
        assert encrypted["secret"] != "hidden"
        assert encrypted["another_secret"] != "also hidden"

    def test_decrypt_dict_fields(self):
        """Test decryption of dictionary fields."""
        manager = EncryptionManager("test_key")
        plaintext = "secret_value"
        encrypted_value = manager.encrypt(plaintext)

        data = {
            "public": "visible",
            "secret": encrypted_value,
        }

        decrypted = manager.decrypt_dict_fields(data, ["secret"])

        assert decrypted["public"] == "visible"
        assert decrypted["secret"] == plaintext

    def test_decrypt_invalid_data(self):
        """Test decryption of invalid data raises error."""
        manager = EncryptionManager("test_key")

        with pytest.raises(EncryptionError):
            manager.decrypt("invalid_base64!!!")
```

## 4. Repository Tests

### 4.1 `tests/unit/discord/test_repositories.py`

```python
"""Tests for Discord repositories."""

from __future__ import annotations

import pytest

from app.discord.repositories.guild_repo import GuildRepo
from app.discord.repositories.channel_repo import ChannelRepo
from app.discord.repositories.user_repo import UserRepo


class TestGuildRepo:
    """Tests for GuildRepo."""

    @pytest.mark.asyncio
    async def test_get_guild(self, mock_database, mock_encryption, sample_guild_config):
        """Test getting guild configuration."""
        mock_database.fetch_one.return_value = {
            **sample_guild_config,
            "fallback_webhook": "enc:" + sample_guild_config["fallback_webhook"],
        }

        repo = GuildRepo()
        result = repo.get(123456789)

        assert result is not None
        assert result["id"] == 123456789
        assert result["fallback_webhook"] == sample_guild_config["fallback_webhook"]
        mock_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_guild_not_found(self, mock_database, mock_encryption):
        """Test getting non-existent guild."""
        mock_database.fetch_one.return_value = None

        repo = GuildRepo()
        result = repo.get(999999999)

        assert result is None

    @pytest.mark.asyncio
    async def test_create_guild(self, mock_database, mock_encryption):
        """Test creating guild configuration."""
        repo = GuildRepo()
        await repo.create(123456789, "https://discord.com/api/webhooks/test")

        mock_database.execute.assert_called_once()
        call_args = mock_database.execute.call_args
        assert "123456789" in str(call_args)

    @pytest.mark.asyncio
    async def test_update_guild(self, mock_database, mock_encryption):
        """Test updating guild configuration."""
        repo = GuildRepo()
        await repo.update(123456789, bot_status="New Status")

        mock_database.execute.assert_called_once()


class TestChannelRepo:
    """Tests for ChannelRepo."""

    @pytest.mark.asyncio
    async def test_get_by_type(self, mock_database, sample_channel_config):
        """Test getting channel by type."""
        mock_database.fetch_one.return_value = sample_channel_config

        repo = ChannelRepo()
        result = repo.get_by_type(123456789, "map_rank")

        assert result is not None
        assert result["channel_type"] == "map_rank"

    @pytest.mark.asyncio
    async def test_get_by_guild(self, mock_database, sample_channel_config):
        """Test getting all channels for a guild."""
        mock_database.fetch_all.return_value = [sample_channel_config]

        repo = ChannelRepo()
        results = repo.get_by_guild(123456789)

        assert len(results) == 1
        assert results[0]["guild_id"] == 123456789


class TestUserRepo:
    """Tests for UserRepo."""

    @pytest.mark.asyncio
    async def test_get_by_osu(self, mock_database):
        """Test getting Discord links for osu! user."""
        mock_database.fetch_all.return_value = [
            {
                "id": 1,
                "osu_user_id": 100,
                "discord_user_id": 123456789,
                "is_primary": True,
                "linked_at": "2024-01-01T00:00:00",
            }
        ]

        repo = UserRepo()
        results = repo.get_by_osu(100)

        assert len(results) == 1
        assert results[0]["discord_user_id"] == 123456789

    @pytest.mark.asyncio
    async def test_create_link(self, mock_database):
        """Test creating user link."""
        repo = UserRepo()
        await repo.create(100, 123456789, is_primary=True)

        mock_database.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_primary(self, mock_database):
        """Test setting primary link."""
        repo = UserRepo()
        await repo.set_primary(1, 100)

        # Should call execute twice: unset all, then set one
        assert mock_database.execute.call_count == 2
```

## 5. Service Tests

### 5.1 `tests/unit/discord/test_message_service.py`

```python
"""Tests for message service."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from unittest.mock import patch

from app.discord.services.message_service import MessageService


class TestMessageService:
    """Tests for MessageService."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_bot):
        """Test successful message send."""
        service = MessageService()
        message_id = await service.send(
            channel_id=987654321,
            content="Test message",
        )

        assert message_id == 123456789
        mock_bot.bot.rest.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self):
        """Test message send when bot not connected."""
        with patch("app.discord.services.message_service.discord_bot") as mock:
            mock.is_connected = False
            mock.bot = None

            service = MessageService()
            message_id = await service.send(
                channel_id=987654321,
                content="Test message",
            )

            # Should queue message and return None
            assert message_id is None

    @pytest.mark.asyncio
    async def test_edit_message_success(self, mock_bot):
        """Test successful message edit."""
        service = MessageService()
        result = await service.edit_message(
            channel_id=987654321,
            message_id=123456789,
            content="Updated message",
        )

        assert result is True
        mock_bot.bot.rest.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_message_success(self, mock_bot):
        """Test successful message delete."""
        service = MessageService()
        result = await service.delete_message(
            channel_id=987654321,
            message_id=123456789,
        )

        assert result is True
        mock_bot.bot.rest.delete_message.assert_called_once()

    def test_create_embed(self):
        """Test embed creation."""
        service = MessageService()
        embed = service.create_embed(
            title="Test Title",
            description="Test Description",
            color=0xFF0000,
            fields=[
                {"name": "Field 1", "value": "Value 1", "inline": True},
            ],
            footer="Test Footer",
        )

        assert embed.title == "Test Title"
        assert embed.description == "Test Description"
        assert embed.color == 0xFF0000
        assert len(embed.fields) == 1
        assert embed.footer.text == "Test Footer"
```

### 5.2 `tests/unit/discord/test_component_service.py`

```python
"""Tests for component service."""

from __future__ import annotations

import pytest

from app.discord.services.component_service import ComponentService


class TestComponentService:
    """Tests for ComponentService."""

    def test_generate_custom_id(self):
        """Test custom ID generation."""
        service = ComponentService()
        custom_id = service.generate_custom_id("map", "diff_select", map_id=123)

        assert custom_id.startswith("dc:map:diff_select:")
        assert "map_id=123" in custom_id

    def test_parse_custom_id(self):
        """Test custom ID parsing."""
        service = ComponentService()
        custom_id = "dc:map:diff_select:abc123:map_id=123"

        parsed = service.parse_custom_id(custom_id)

        assert parsed["type"] == "map"
        assert parsed["action"] == "diff_select"
        assert parsed["params"]["map_id"] == "123"

    def test_parse_invalid_custom_id(self):
        """Test parsing invalid custom ID."""
        service = ComponentService()
        parsed = service.parse_custom_id("invalid")

        assert parsed["type"] == ""
        assert parsed["action"] == ""

    @pytest.mark.asyncio
    async def test_create_difficulty_dropdown(self, mock_database):
        """Test creating difficulty dropdown."""
        service = ComponentService()
        difficulties = [
            {"id": 1, "name": "Easy", "mode": 0, "stars": 1.5, "cs": 2, "ar": 3},
            {"id": 2, "name": "Hard", "mode": 0, "stars": 4.2, "cs": 4, "ar": 8},
        ]

        dropdown = await service.create_difficulty_dropdown(
            map_id=123,
            difficulties=difficulties,
            message_id=0,
            channel_id=987654321,
            guild_id=123456789,
        )

        assert dropdown is not None
        assert len(dropdown.options) == 2
```

## 6. Integration Tests

### 6.1 `tests/integration/discord/conftest.py`

```python
"""Integration test configuration for Discord webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def webhook_secret():
    """Test webhook secret."""
    return "test_webhook_secret"


@pytest.fixture
def github_signature(webhook_secret):
    """Generate GitHub webhook signature."""
    def _generate(payload: dict) -> str:
        body = json.dumps(payload).encode()
        signature = hmac.new(
            webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"
    return _generate


@pytest.fixture
def sample_push_payload():
    """Sample GitHub push payload."""
    return {
        "ref": "refs/heads/main",
        "before": "abc123",
        "after": "def456",
        "repository": {
            "id": 12345,
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "owner": {
                "login": "owner",
            },
            "html_url": "https://github.com/owner/test-repo",
        },
        "pusher": {
            "name": "testuser",
            "email": "test@example.com",
        },
        "commits": [
            {
                "id": "abc123def456",
                "message": "Test commit message",
                "author": {
                    "name": "Test Author",
                    "email": "author@example.com",
                },
                "url": "https://github.com/owner/test-repo/commit/abc123def456",
                "timestamp": "2024-01-01T00:00:00Z",
            }
        ],
        "compare": "https://github.com/owner/test-repo/compare/abc123...def456",
    }
```

### 6.2 `tests/integration/discord/test_webhook_endpoints.py`

```python
"""Integration tests for Discord webhook endpoints."""

from __future__ import annotations

import pytest
from fastapi import status

from app import settings


class TestGitHubWebhook:
    """Tests for GitHub webhook endpoint."""

    def test_webhook_without_signature(self, client: TestClient, sample_push_payload):
        """Test webhook request without signature."""
        response = client.post(
            "/api/v1/discord/webhook/github",
            json=sample_push_payload,
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-id",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_webhook_with_invalid_signature(
        self,
        client: TestClient,
        sample_push_payload,
    ):
        """Test webhook request with invalid signature."""
        response = client.post(
            "/api/v1/discord/webhook/github",
            json=sample_push_payload,
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": "sha256=invalid_signature",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_webhook_with_valid_signature(
        self,
        client: TestClient,
        webhook_secret,
        sample_push_payload,
        github_signature,
    ):
        """Test webhook request with valid signature."""
        # Configure webhook secret in test settings
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(settings, "DISCORD_WEBHOOK_SECRET", webhook_secret)

            signature = github_signature(sample_push_payload)

            response = client.post(
                "/api/v1/discord/webhook/github",
                json=sample_push_payload,
                headers={
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "test-delivery-id",
                    "X-Hub-Signature-256": signature,
                },
            )

            # Should return 200 or 404 if repo not configured
            assert response.status_code in [
                status.HTTP_200_OK,
                status.HTTP_404_NOT_FOUND,
            ]

    def test_webhook_ignored_event(
        self,
        client: TestClient,
        webhook_secret,
        github_signature,
    ):
        """Test webhook with ignored event type."""
        payload = {"action": "opened", "repository": {"name": "test"}}
        signature = github_signature(payload)

        response = client.post(
            "/api/v1/discord/webhook/github",
            json=payload,
            headers={
                "X-GitHub-Event": "issues",  # Not configured event
                "X-GitHub-Delivery": "test-delivery-id",
                "X-Hub-Signature-256": signature,
            },
        )

        # Should be ignored
        assert response.status_code == status.HTTP_200_OK


class TestSendMessage:
    """Tests for send message endpoint."""

    def test_send_without_auth(self, client: TestClient):
        """Test send without API key."""
        response = client.post(
            "/api/v1/discord/send",
            json={
                "channel_id": 123456789,
                "content": "Test message",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_send_with_invalid_auth(self, client: TestClient):
        """Test send with invalid API key."""
        response = client.post(
            "/api/v1/discord/send",
            json={
                "channel_id": 123456789,
                "content": "Test message",
            },
            headers={"X-API-Key": "invalid_key"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_send_with_valid_auth(
        self,
        client: TestClient,
        mock_bot,
    ):
        """Test send with valid API key."""
        response = client.post(
            "/api/v1/discord/send",
            json={
                "channel_id": 123456789,
                "content": "Test message",
            },
            headers={"X-API-Key": settings.BOT_API_KEY},
        )

        assert response.status_code == status.HTTP_200_OK


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_without_auth(self, client: TestClient):
        """Test health check without API key."""
        response = client.get("/api/v1/discord/health")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_health_with_auth(self, client: TestClient):
        """Test health check with API key."""
        response = client.get(
            "/api/v1/discord/health",
            headers={"X-API-Key": settings.BOT_API_KEY},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "is_connected" in data
        assert "uptime_seconds" in data
        assert "guild_count" in data
```

## 7. Commit Message

```
test(discord): add comprehensive unit and integration tests

- Add unit tests for EncryptionManager
- Add unit tests for all repository classes
- Add unit tests for MessageService
- Add unit tests for ComponentService
- Add integration tests for GitHub webhook endpoint
- Add integration tests for send message endpoint
- Add integration tests for health check endpoint
- Add test fixtures and mocks for Discord API
- Test signature verification for webhooks
```
