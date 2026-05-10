# Discord Integration Module — Agent Guide

## Purpose

This plan implements a full Discord bot integration using Hikari (with Lightbulb for future commands) to replace the existing basic webhook system. The module provides interactive notifications, GitHub integration, map rank notifications, and a foundation for future Discord features.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Endpoints                         │
│  POST /api/v1/discord/webhook/github  │  POST /api/v1/discord/send │
│  GET  /api/v1/discord/health                                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Discord Service Layer                        │
│  message_service.py  │  component_service.py  │  webhook_service.py │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    Hikari Bot (Gateway)                           │
│  Event Handling  │  Interaction Handling  │  Connection Mgmt     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Repository Layer                             │
│  guild_repo  │  channel_repo  │  user_repo  │  message_repo       │
│  component_repo  │  template_repo  │  repo_repo (GitHub)          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                        MySQL Database                             │
│  discord_guilds  │  discord_channels  │  discord_users            │
│  discord_messages  │  discord_components  │  discord_templates     │
│  discord_repos  │  discord_failed_messages                        │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Principles

1. **Modular structure** — Split into focused files, not monolithic modules
2. **Event-driven** — Use asyncio.Event for internal communication
3. **Encrypted storage** — AES-256-GCM for sensitive fields (tokens, webhooks)
4. **Graceful degradation** — Fallback webhook if bot is unavailable
5. **Persistent interactions** — Components stored in DB, survive restarts
6. **Per-guild configuration** — Each guild configures its own channels/settings

## File Structure

```
app/discord/
├── __init__.py              # Public exports
├── bot.py                   # Hikari bot initialization & lifecycle
├── encryption.py            # AES-256-GCM encryption utilities
├── constants.py             # Colors, icons, notification types
├── components.py            # Reusable UI component builders
├── templates.py             # Message template rendering
├── services/
│   ├── __init__.py
│   ├── message_service.py   # Send messages, embeds, components
│   ├── component_service.py # Interactive component management
│   ├── webhook_service.py   # Webhook processing (GitHub)
│   └── health_service.py    # Health monitoring
├── repositories/
│   ├── __init__.py
│   ├── guild_repo.py        # discord_guilds table
│   ├── channel_repo.py      # discord_channels table
│   ├── user_repo.py         # discord_users table
│   ├── message_repo.py      # discord_messages table
│   ├── component_repo.py    # discord_components table
│   ├── template_repo.py     # discord_templates table
│   └── repo_repo.py         # discord_repos table (GitHub configs)
└── api/
    ├── __init__.py
    └── endpoints.py         # FastAPI router
```

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `DISCORD_BOT_TOKEN` | Bot authentication token | Yes |
| `DISCORD_ENCRYPTION_KEY` | AES-256 key for DB encryption (32 bytes hex) | Yes |

## Database Tables

| Table | Purpose |
|-------|---------|
| `discord_guilds` | Guild configurations (fallback webhook, invite link, bot status) |
| `discord_channels` | Channel configurations (type, notification types) |
| `discord_users` | Account linking (osu_user_id ↔ discord_user_id) |
| `discord_messages` | Message tracking for updates (GitHub, etc.) |
| `discord_components` | Persistent interactive components |
| `discord_templates` | Message templates with variables |
| `discord_repos` | GitHub repository configurations |
| `discord_failed_messages` | Failed message queue with retry logic |

## Implementation Phases

| Phase | File | Description |
|-------|------|-------------|
| 1 | `01-database-schema.md` | Database tables and migrations |
| 2 | `02-core-bot.md` | Hikari bot setup, connection handling |
| 3 | `03-encryption.md` | Encryption utilities |
| 4 | `04-services.md` | Discord service layer |
| 5 | `05-webhook-api.md` | Webhook receiver endpoints |
| 6 | `06-templates.md` | Message template system |
| 7 | `07-components.md` | Interactive components persistence |
| 8 | `08-map-notifications.md` | Map rank notifications |
| 9 | `09-github-integration.md` | GitHub webhook integration |
| 10 | `10-account-linking.md` | Discord-Osu account linking |
| 11 | `11-frontend-api.md` | Frontend API endpoints |
| 12 | `12-tests.md` | Unit and integration tests |

## Migration from Old System

The existing `app/discord.py` (basic webhook) will be completely replaced:
- `DISCORD_AUDIT_LOG_WEBHOOK` removed from settings
- `DISCORD_INVITE` moved to database
- Webhook calls in `player.py` migrated to new service layer
- All new features use the new module

## Key Libraries

- `hikari>=2.0.0` — Discord API library
- `hikari-lightbulb>=2.0.0` — Command framework (for future use)
- `cryptography>=41.0.0` — AES-256-GCM encryption

## Coding Standards

- Follow existing project patterns (see AGENTS.md in root)
- Use `from __future__ import annotations` in all files
- TypedDict for database row representations
- Pydantic models for API request/response
- Async throughout (no sync DB calls)
- Proper docstrings on all public functions
- Log using `app.logging` with appropriate Ansi colors

## Error Handling

- All Discord API calls should have retry logic with exponential backoff
- Failed messages go to `discord_failed_messages` table
- Bot disconnects trigger admin notification to configured channel
- Graceful shutdown handling for bot cleanup

## Testing Strategy

- Unit tests with mocked Hikari API for most components
- Integration tests for webhook endpoints (signature verification)
- Test files in `tests/unit/discord/` and `tests/integration/discord/`
