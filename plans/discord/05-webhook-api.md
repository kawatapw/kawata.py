# Phase 5 — Webhook API Endpoints

## Scope

Create FastAPI endpoints for receiving webhooks (GitHub) and sending messages from the frontend admin panel.

## 1. API Router

### 1.1 `app/discord/api/__init__.py`

```python
"""Discord API endpoints."""

from __future__ import annotations

from app.discord.api.endpoints import router


__all__ = ["router"]
```

### 1.2 `app/discord/api/endpoints.py`

```python
"""Discord API endpoints for webhooks and frontend integration."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from typing import TypedDict

from fastapi import APIRouter
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import status

from app import settings
from app.discord.repositories import discord_repositories
from app.discord.services.health_service import health_service
from app.discord.services.message_service import message_service
from app.logging import Ansi
from app.logging import log


router = APIRouter(prefix="/api/v1/discord", tags=["discord"])


# Request/Response models


class SendMessageRequest(TypedDict):
    """Request to send a Discord message."""

    channel_id: int
    content: str | None
    embed: dict[str, Any] | None
    components: list[dict[str, Any]] | None
    message_type: str | None
    metadata: dict[str, Any] | None


class SendNotificationRequest(TypedDict):
    """Request to send a typed notification."""

    notification_type: str
    guild_id: int
    data: dict[str, Any]


class HealthResponse(TypedDict):
    """Health check response."""

    is_connected: bool
    uptime_seconds: float
    guild_count: int
    message_queue_size: int
    last_error: str | None
    last_error_time: str | None
    reconnect_attempts: int


# Authentication


async def verify_bot_api_key(x_api_key: str = Header(...)) -> None:
    """Verify the BOT_API_KEY for admin API access."""
    if x_api_key != settings.BOT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


# Endpoints


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
) -> dict[str, str]:
    """
    Receive GitHub webhook events.
    
    Handles push, pull_request, and workflow_run events.
    Verifies webhook signature for security.
    """
    body = await request.body()

    # Get repo config from database
    payload = json.loads(body)
    repo_info = payload.get("repository", {})
    repo_owner = repo_info.get("owner", {}).get("login")
    repo_name = repo_info.get("name")

    if not repo_owner or not repo_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload: missing repository info",
        )

    # Find matching repo config
    # We need to check all guilds that have this repo configured
    repo_configs = await discord_repositories.repo.get_by_repo_all_guilds(
        owner=repo_owner,
        name=repo_name,
    )

    if not repo_configs:
        return {"status": "ignored", "reason": "repo not configured"}

    # Verify signature for each matching config
    for repo_config in repo_configs:
        webhook_secret = repo_config["webhook_secret"]
        if _verify_signature(body, x_hub_signature_256 or "", webhook_secret):
            # Process the event
            await _process_github_event(
                event_type=x_github_event or "",
                payload=payload,
                repo_config=repo_config,
            )
            return {"status": "processed"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid signature",
    )


@router.post("/send", dependencies=[verify_bot_api_key])
async def send_message(request: SendMessageRequest) -> dict[str, Any]:
    """
    Send a message to a Discord channel.
    
    Requires BOT_API_KEY authentication.
    Used by frontend admin panel.
    """
    message_id = await message_service.send(
        channel_id=request["channel_id"],
        content=request.get("content"),
        guild_id=request.get("guild_id"),
        message_type=request.get("message_type"),
        metadata=request.get("metadata"),
    )

    if message_id:
        return {"status": "sent", "message_id": message_id}
    else:
        return {"status": "queued", "message_id": None}


@router.post("/notify", dependencies=[verify_bot_api_key])
async def send_notification(request: SendNotificationRequest) -> dict[str, str]:
    """
    Send a typed notification to Discord.
    
    Requires BOT_API_KEY authentication.
    Dispatches to appropriate handler based on notification_type.
    """
    from app.discord.constants import NotificationType

    try:
        notification_type = NotificationType(request["notification_type"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid notification type: {request['notification_type']}",
        )

    # Dispatch to appropriate handler
    handler = _get_notification_handler(notification_type)
    if handler:
        await handler(
            guild_id=request["guild_id"],
            data=request["data"],
        )
        return {"status": "sent"}
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Handler not implemented for {notification_type}",
        )


@router.get("/health", dependencies=[verify_bot_api_key])
async def health_check() -> HealthResponse:
    """
    Get Discord bot health status.
    
    Requires BOT_API_KEY authentication.
    """
    return health_service.to_dict()


# Helper functions


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not signature or not secret:
        return False

    # Signature format: sha256=<hex>
    expected = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected)


async def _process_github_event(
    event_type: str,
    payload: dict[str, Any],
    repo_config: dict[str, Any],
) -> None:
    """Process a GitHub webhook event."""
    from app.discord.services.webhook_service import webhook_service

    # Check if event type is enabled
    enabled_events = repo_config.get("events", [])
    if event_type not in enabled_events:
        return

    # Check branch filter for push events
    if event_type == "push":
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "")
        branch_filter = repo_config.get("branch_filter")
        if branch_filter and branch not in branch_filter:
            return

    # Process based on event type
    if event_type == "push":
        await webhook_service.handle_push(
            payload=payload,
            repo_config=repo_config,
        )
    elif event_type == "pull_request":
        await webhook_service.handle_pull_request(
            payload=payload,
            repo_config=repo_config,
        )
    elif event_type == "workflow_run":
        await webhook_service.handle_workflow_run(
            payload=payload,
            repo_config=repo_config,
        )
    elif event_type == "workflow_job":
        await webhook_service.handle_workflow_job(
            payload=payload,
            repo_config=repo_config,
        )
    else:
        log(f"Unhandled GitHub event type: {event_type}", Ansi.LYELLOW)


def _get_notification_handler(notification_type: NotificationType):
    """Get the handler for a notification type."""
    from app.discord.constants import NotificationType

    handlers = {
        # Map notifications
        NotificationType.MAP_RANKED: _handle_map_rank_notification,
        NotificationType.MAP_QUALIFIED: _handle_map_rank_notification,
        NotificationType.MAP_LOVED: _handle_map_rank_notification,
        # Announcements
        NotificationType.ANNOUNCEMENT_MAINTENANCE: _handle_announcement,
        NotificationType.ANNOUNCEMENT_EVENT: _handle_announcement,
        NotificationType.ANNOUNCEMENT_UPDATE: _handle_announcement,
        NotificationType.ANNOUNCEMENT_SEASON: _handle_announcement,
        # Admin actions
        NotificationType.ADMIN_RESTRICT: _handle_admin_action,
        NotificationType.ADMIN_UNRESTRICT: _handle_admin_action,
        NotificationType.ADMIN_SILENCE: _handle_admin_action,
        NotificationType.ADMIN_UNSILENCE: _handle_admin_action,
    }

    return handlers.get(notification_type)


async def _handle_map_rank_notification(guild_id: int, data: dict[str, Any]) -> None:
    """Handle map rank notification."""
    # Will be implemented in Phase 8
    pass


async def _handle_announcement(guild_id: int, data: dict[str, Any]) -> None:
    """Handle announcement notification."""
    # Will be implemented in Phase 6 (templates)
    pass


async def _handle_admin_action(guild_id: int, data: dict[str, Any]) -> None:
    """Handle admin action notification."""
    from app.discord.constants import NotificationType

    action = data.get("action")
    admin_name = data.get("admin_name")
    target_name = data.get("target_name")
    reason = data.get("reason", "No reason provided")

    # Map action to notification type
    action_to_type = {
        "restrict": NotificationType.ADMIN_RESTRICT,
        "unrestrict": NotificationType.ADMIN_UNRESTRICT,
        "silence": NotificationType.ADMIN_SILENCE,
        "unsilence": NotificationType.ADMIN_UNSILENCE,
    }

    notification_type = action_to_type.get(action)
    if not notification_type:
        return

    await message_service.send_audit_log(
        guild_id=guild_id,
        title=f"Admin Action: {action.capitalize()}",
        description=f"**{admin_name}** {action}ed **{target_name}**",
        fields=[{"name": "Reason", "value": reason, "inline": False}],
    )
```

## 2. Update Repo Repo for Multi-Guild Lookup

### 2.1 `app/discord/repositories/repo_repo.py` (Add method)

```python
async def get_by_repo_all_guilds(
    self,
    owner: str,
    name: str,
) -> list[RepoConfig]:
    """Get all repo configurations for a repo across all guilds."""
    query = """
        SELECT id, repo_owner, repo_name, guild_id, channel_id,
               webhook_secret, events, branch_filter, job_filter,
               commit_limit, is_active, created_at, updated_at
        FROM discord_repos
        WHERE repo_owner = :owner AND repo_name = :name AND is_active = TRUE
    """
    rows = await database.fetch_all(query, {"owner": owner, "name": name})
    return [self._decrypt_row(row) for row in rows]
```

## 3. Register Router in Main API

### 3.1 Update `app/api/init_api.py`

```python
# Add to existing imports
from app.discord.api import router as discord_router

# Add router to app
app.include_router(discord_router)
```

## 4. Commit Message

```
feat(discord): add webhook API endpoints

- Add GitHub webhook receiver with signature verification
- Add /api/v1/discord/send endpoint for frontend
- Add /api/v1/discord/notify for typed notifications
- Add /api/v1/discord/health for monitoring
- Add BOT_API_KEY authentication for admin endpoints
- Add event dispatch system for different notification types
```
