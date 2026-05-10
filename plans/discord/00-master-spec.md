# Discord Integration Module — Master Specification

## 1. Vision

Replace the existing basic webhook system with a full-featured Discord bot integration that provides:

- **Interactive map rank notifications** — Dropdown selectors for difficulty information
- **GitHub integration** — Consolidated commit messages with real-time job status updates
- **Server announcements** — Configurable announcement types with scheduling
- **Account linking** — Link osu! accounts to Discord accounts (both directions)
- **Extensible foundation** — Easy to add new notification types and features

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (Admin Panel)                         │
│                        POST /api/v1/discord/send                            │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                            FastAPI Endpoints                                │
│  POST /api/v1/discord/webhook/github  │  GET /api/v1/discord/health         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                          Discord Service Layer                              │
│  message_service.py  │  component_service.py  │  webhook_service.py         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                        Hikari Bot (Gateway Connection)                      │
│  Event Handling  │  Interaction Handling  │  Connection Management          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                            Repository Layer                                 │
│  guild  │  channel  │  user  │  message  │  component  │  template  │  repo │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                              MySQL Database                                 │
│  discord_guilds  │  discord_channels  │  discord_users  │  discord_messages │
│  discord_components  │  discord_templates  │  discord_repos                 │
│  discord_failed_messages                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility |
|-------|---------------|
| **API** | Receive external requests (GitHub webhooks, frontend calls), validate auth |
| **Services** | Business logic for sending messages, processing webhooks, managing components |
| **Bot** | Discord gateway connection, event handling, interaction processing |
| **Repositories** | Database operations, encrypted field handling |
| **Database** | Persistent storage with encrypted sensitive fields |

## 3. Key Features

### 3.1 Map Rank Notifications

**Flow:**
1. Map status changes (ranked/qualified/loved)
2. Bot posts message to configured channel with:
   - Map title, artist, creator
   - Status change indicator (old → new)
   - Difficulty icons with mode colors for changed diffs
   - Dropdown selector with difficulty names and star ratings
3. User selects difficulty from dropdown
4. Bot sends ephemeral message with:
   - Star rating, CS/AR/OD/HP values
   - Max combo, length, BPM
   - Mapper notes if available

**Configuration:**
- Per-guild channel selection
- Configurable notification types (ranked only, qualified, loved, etc.)
- Persistent dropdown (no timeout, survives bot restart)

### 3.2 GitHub Integration

**Flow:**
1. GitHub webhook receives push/PR events
2. Bot posts consolidated message with:
   - All commits (truncated if too many/long)
   - Commit messages fetched from GitHub API (full text)
   - Job status indicators (✅❌🔄)
   - Links to workflow runs
3. Message updates in real-time as jobs complete
4. User clicks job button → ephemeral message with job summary

**Configuration:**
- Per-repository configuration
- Branch filters (only notify for certain branches)
- Job filters (only notify for certain workflow names)
- Commit count limits
- Configurable events (push, PR, workflow_run, etc.)

### 3.3 Server Announcement

**Types:**
- Maintenance (scheduled downtime)
- Events (tournaments, contests)
- Updates (new features, changes)
- Season winners
- Custom

**Features:**
- Configurable colors and icons per type
- Role ping support (@everyone, @here, custom roles)
- Scheduling (post at specific time)
- Template system with variables

### 3.4 Account Linking

**Flow (In-game → Discord):**
1. User types `!link` in-game
2. Bot generates unique code
3. User enters code in Discord via `/link` command
4. Accounts linked in database

**Flow (Discord → In-game):**
1. User types `/link` in Discord
2. Bot generates unique code
3. User enters code in-game via `!link` command
4. Accounts linked in database

**Features:**
- Multiple Discord accounts per osu! account
- Primary account designation for notifications
- Link/unlink commands both directions

## 4. Database Schema

### 4.1 discord_guilds

```sql
CREATE TABLE discord_guilds (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    fallback_webhook TEXT NOT NULL,  -- Encrypted
    invite_link VARCHAR(255) DEFAULT NULL,
    bot_status VARCHAR(128) DEFAULT 'Watching osu! rankings',
    notification_defaults JSON DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 4.2 discord_channels

```sql
CREATE TABLE discord_channels (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    guild_id BIGINT UNSIGNED NOT NULL,
    channel_type ENUM('audit', 'announcements', 'map_rank', 'github', 'general') NOT NULL,
    notification_types JSON DEFAULT NULL,  -- Array of enabled notification types
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES discord_guilds(id) ON DELETE CASCADE,
    UNIQUE KEY unique_guild_channel (guild_id, channel_type)
);
```

### 4.3 discord_users

```sql
CREATE TABLE discord_users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    osu_user_id INT UNSIGNED NOT NULL,
    discord_user_id BIGINT UNSIGNED NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    linked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (osu_user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_discord_user (discord_user_id),
    INDEX idx_osu_user (osu_user_id)
);
```

### 4.4 discord_messages

```sql
CREATE TABLE discord_messages (
    id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    channel_id BIGINT UNSIGNED NOT NULL,
    guild_id BIGINT UNSIGNED NOT NULL,
    message_type ENUM('map_rank', 'github_push', 'github_pr', 'announcement') NOT NULL,
    metadata JSON DEFAULT NULL,  -- Type-specific data (commit_sha, map_id, etc.)
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES discord_guilds(id) ON DELETE CASCADE,
    INDEX idx_type_active (message_type, is_active)
);
```

### 4.5 discord_components

```sql
CREATE TABLE discord_components (
    id VARCHAR(64) NOT NULL PRIMARY KEY,  -- Custom ID
    component_type ENUM('button', 'select', 'role_select') NOT NULL,
    message_id BIGINT UNSIGNED NOT NULL,
    channel_id BIGINT UNSIGNED NOT NULL,
    guild_id BIGINT UNSIGNED NOT NULL,
    data JSON NOT NULL,  -- Component-specific data
    expires_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES discord_messages(id) ON DELETE CASCADE,
    INDEX idx_expires (expires_at)
);
```

### 4.6 discord_templates

```sql
CREATE TABLE discord_templates (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    guild_id BIGINT UNSIGNED DEFAULT NULL,  -- NULL = global default
    template_type ENUM('map_rank', 'github', 'announcement', 'custom') NOT NULL,
    template_data JSON NOT NULL,  -- Template structure with variables
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES discord_guilds(id) ON DELETE CASCADE,
    UNIQUE KEY unique_guild_template (guild_id, name)
);
```

### 4.7 discord_repos

```sql
CREATE TABLE discord_repos (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    repo_owner VARCHAR(128) NOT NULL,
    repo_name VARCHAR(128) NOT NULL,
    guild_id BIGINT UNSIGNED NOT NULL,
    channel_id BIGINT UNSIGNED NOT NULL,
    webhook_secret TEXT NOT NULL,  -- Encrypted
    events JSON NOT NULL,  -- ['push', 'pull_request', 'workflow_run']
    branch_filter JSON DEFAULT NULL,  -- ['main', 'develop'] or NULL for all
    job_filter JSON DEFAULT NULL,  -- ['test', 'build'] or NULL for all
    commit_limit INT UNSIGNED DEFAULT 10,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES discord_guilds(id) ON DELETE CASCADE,
    UNIQUE KEY unique_repo (repo_owner, repo_name, guild_id)
);
```

### 4.8 discord_failed_messages

```sql
CREATE TABLE discord_failed_messages (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    channel_id BIGINT UNSIGNED NOT NULL,
    guild_id BIGINT UNSIGNED NOT NULL,
    message_data JSON NOT NULL,  -- Full message payload
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

## 5. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Discord library | `hikari>=2.0.0` | Modern, actively maintained, async-first |
| Command framework | `hikari-lightbulb>=2.0.0` | For future slash commands |
| Encryption | `cryptography>=41.0.0` | AES-256-GCM for sensitive fields |
| Database | Existing `databases` library | Consistent with project |
| HTTP client | Existing `httpx` | Already used for external requests |

## 6. Configuration

### 6.1 Environment Variables

```env
# Required
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_ENCRYPTION_KEY=32_byte_hex_key_for_aes_256
```

### 6.2 Database Configuration

All other configuration stored in database:
- Guild settings (fallback webhook, invite link, bot status)
- Channel mappings (which channel for which notification type)
- GitHub repo configurations
- Message templates

## 7. Error Handling & Recovery

### 7.1 Bot Connection

- Auto-reconnect with exponential backoff
- Max 5 reconnection attempts before giving up
- Admin notification to configured channel on disconnect
- Health check endpoint for monitoring

### 7.2 Message Failures

- Failed messages stored in `discord_failed_messages`
- Exponential backoff retry (1s, 2s, 4s, 8s, 16s...)
- After max retries → dead letter queue
- Admin notification for dead letter messages
- Retry from admin panel (future feature)

### 7.3 Fallback Webhook

- Global fallback webhook URL stored encrypted in database
- Used when Discord bot is unavailable
- Sends basic text notifications (no embeds/components)

## 8. Migration Strategy

### 8.1 Removed Settings

- `DISCORD_AUDIT_LOG_WEBHOOK` — Replaced by channel config + fallback webhook
- `DISCORD_INVITE` — Moved to `discord_guilds.invite_link`

### 8.2 Code Migration

| File | Change |
|------|--------|
| `app/discord.py` | Completely replaced by `app/discord/` package |
| `app/objects/player.py` | Webhook calls → `message_service.send_audit_log()` |
| `app/commands/categories/developer.py` | `DISCORD_INVITE` → database query |
| `app/api/domains/cho.py` | `DISCORD_INVITE` → database query |

### 8.3 Migration Steps

1. Add new tables to `migrations/migrations.sql` and `migrations/base.sql`
2. Create `app/discord/` package with all modules
3. Update `app/settings.py` to remove old vars, add new ones
4. Update all files that use old webhook system
5. Remove `app/discord.py`

## 9. Security Considerations

- All sensitive data encrypted at rest (AES-256-GCM)
- Webhook signature verification for GitHub
- BOT_API_KEY authentication for frontend API endpoints
- No sensitive data in logs
- Rate limiting on user-facing commands

## 10. Future Extensibility

The architecture supports adding:
- New notification types (register in constants, add handler)
- Slash commands (via Lightbulb)
- Reaction roles
- Custom webhook receivers (Patreon, etc.)
- User preference system
- Analytics/statistics
