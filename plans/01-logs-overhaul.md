# Logs Table Overhaul Plan

## Overview

Redesign the logs table to avoid MySQL reserved words and add support for advanced logging with severity levels and categories.

## Current Issues

- Column names use MySQL reserved words: `mod`, `target`, `action`, `type`
- Limited log categorization
- No severity levels for filtering important logs

## Database Changes

### Migration Script

File: [`migrations/001_logs_table_overhaul.sql`](migrations/001_logs_table_overhaul.sql)

```sql
-- Rename columns to avoid reserved words
ALTER TABLE logs 
    CHANGE COLUMN `mod` `actor_id` INT NOT NULL COMMENT 'User ID of the person performing the action',
    CHANGE COLUMN `target` `target_id` INT NOT NULL COMMENT 'User ID or resource ID being acted upon',
    CHANGE COLUMN `action` `action_type` VARCHAR(32) NOT NULL COMMENT 'Type of action performed',
    CHANGE COLUMN `reason` `details` VARCHAR(2048) CHARSET utf8mb4 DEFAULT NULL COMMENT 'Additional details about the action',
    CHANGE COLUMN `type` `log_type` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '0=player-to-player, 1=player-to-map, 2=system, 3=admin';

-- Add new columns for advanced logging
ALTER TABLE logs
    ADD COLUMN `severity` ENUM('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') NOT NULL DEFAULT 'INFO' AFTER `details`,
    ADD COLUMN `source` VARCHAR(64) DEFAULT NULL COMMENT 'Source system/module that generated the log' AFTER `severity`;

-- Add indexes for new columns
ALTER TABLE logs
    ADD INDEX `idx_actor_id` (`actor_id`),
    ADD INDEX `idx_target_id` (`target_id`),
    ADD INDEX `idx_action_type` (`action_type`),
    ADD INDEX `idx_severity` (`severity`),
    ADD INDEX `idx_log_type` (`log_type`);
```

### New Schema

```sql
CREATE TABLE logs (
    id VARCHAR(64) NOT NULL PRIMARY KEY,
    actor_id INT NOT NULL COMMENT 'User ID of the person performing the action',
    target_id INT NOT NULL COMMENT 'User ID or resource ID being acted upon',
    action_type VARCHAR(32) NOT NULL COMMENT 'Type of action performed',
    details VARCHAR(2048) CHARSET utf8mb4 DEFAULT NULL COMMENT 'Additional details about the action',
    severity ENUM('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') NOT NULL DEFAULT 'INFO',
    source VARCHAR(64) DEFAULT NULL COMMENT 'Source system/module that generated the log',
    time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    log_type TINYINT(1) NOT NULL DEFAULT 0 COMMENT '0=player-to-player, 1=player-to-map, 2=system, 3=admin',
    INDEX idx_actor_id (actor_id),
    INDEX idx_target_id (target_id),
    INDEX idx_action_type (action_type),
    INDEX idx_severity (severity),
    INDEX idx_time (time),
    INDEX idx_log_type (log_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## Code Changes

### Repository Updates

File: [`app/repositories/logs.py`](app/repositories/logs.py)

**Current API:**

```python
async def create(
    _from: int,
    to: int,
    action: str,
    msg: str,
    type: int = 0,
) -> Log:
```

**New API:**

```python
async def create(
    actor_id: int,
    target_id: int,
    action_type: str,
    details: str,
    severity: int = 1,  # INFO
    source: str | None = None,
    log_type: int = 0,
) -> Log:
```

### Code References to Update

Search for all `logs_repo.create` calls and update parameter names:

1. [`app/commands.py:830`](app/commands.py:830) - Note command
2. [`app/objects/player.py:571`](app/objects/player.py:571) - Restrict action
3. [`app/objects/player.py:605`](app/objects/player.py:605) - Unrestrict action
4. [`app/objects/player.py:648`](app/objects/player.py:648) - Silence action
5. [`app/objects/player.py:676`](app/objects/player.py:676) - Unsilence action

### Severity Levels

```python
class LogSeverity:
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4
```

### Log Categories (source field)

- `AUTH` - Authentication events
- `SCORE` - Score submission events
- `ADMIN` - Administrative actions
- `CLAN` - Clan-related events
- `SYSTEM` - System events
- `API` - API access logs

## Implementation Steps

1. **Create migration script** ✅ (Already done)
2. **Update [`app/repositories/logs.py`](app/repositories/logs.py)**
   - Rename column references in `LogTable` class
   - Update `READ_PARAMS` tuple
   - Update `Log` TypedDict
   - Update `create()` function signature and implementation
3. **Update code references**
   - Search for all `logs_repo.create` calls
   - Update parameter names to match new API
4. **Add severity and source to existing calls**
   - Add appropriate severity levels to existing log calls
   - Add source categorization to existing log calls
5. **Test migration**
   - Run migration on test database
   - Verify all existing logs are preserved
   - Test new logging functionality

## Testing Checklist

- [ ] Migration runs without errors
- [ ] Existing logs are preserved after migration
- [ ] New logs can be created with new schema
- [ ] Severity filtering works correctly
- [ ] Source categorization works correctly
- [ ] All code references updated and working
