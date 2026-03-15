# Logs Table Overhaul Plan

## Overview

Replace the current `logs` table with the `admin_v2_logs` design from the other dev's branch. This design uses cleaner column names, auto-increment IDs, and proper indexes.

## Current Issues

- Column names use MySQL reserved words: `mod`, `target`, `action`, `type`
- Uses SHA256 hash as primary key (unnecessary complexity)
- Limited indexes for query performance
- Inconsistent naming conventions

## New Table Design (from admin_v2_logs)

```sql
CREATE TABLE IF NOT EXISTS logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    from_id     INT NOT NULL COMMENT 'moderator user id',
    to_id       INT NOT NULL COMMENT 'target user or map id',
    action      VARCHAR(32) NOT NULL,
    msg         VARCHAR(2048) CHARACTER SET utf8mb3 DEFAULT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action_type TINYINT NOT NULL DEFAULT 0 COMMENT '0=user, 1=map, 2=badge',
    INDEX idx_logs_action (action),
    INDEX idx_logs_to_id (to_id),
    INDEX idx_logs_from_id (from_id),
    INDEX idx_logs_created (created_at),
    INDEX idx_logs_type_created (action_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Migration Script

File: `migrations/001_logs_table_overhaul.sql`

```sql
-- Logs Table Overhaul Migration
-- Transforms the existing logs table to use the admin_v2_logs design

-- Step 1: Create new table with the desired schema
CREATE TABLE IF NOT EXISTS logs_new (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    from_id     INT NOT NULL COMMENT 'moderator user id',
    to_id       INT NOT NULL COMMENT 'target user or map id',
    action      VARCHAR(32) NOT NULL,
    msg         VARCHAR(2048) CHARACTER SET utf8mb3 DEFAULT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action_type TINYINT NOT NULL DEFAULT 0 COMMENT '0=user, 1=map, 2=badge',
    INDEX idx_logs_action (action),
    INDEX idx_logs_to_id (to_id),
    INDEX idx_logs_from_id (from_id),
    INDEX idx_logs_created (created_at),
    INDEX idx_logs_type_created (action_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Step 2: Copy data from old table to new table
-- Note: The old table uses SHA256 hash as id, new table uses auto-increment
-- We preserve the order by time to maintain chronological sequence
INSERT INTO logs_new (from_id, to_id, action, msg, created_at, action_type)
SELECT
    CAST(`mod` AS SIGNED) as from_id,
    CAST(`target` AS SIGNED) as to_id,
    `action`,
    `reason` as msg,
    `time` as created_at,
    CAST(`type` AS SIGNED) as action_type
FROM logs
ORDER BY `time` ASC;

-- Step 3: Drop the old table
DROP TABLE IF EXISTS logs;

-- Step 4: Rename the new table to logs
RENAME TABLE logs_new TO logs;
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
    from_id: int,
    to_id: int,
    action: str,
    msg: str,
    action_type: int = 0,
) -> Log:
```

### Schema Changes

**Current LogTable class:**
```python
class LogTable(Base):
    __tablename__ = "logs"

    id = Column("id", Text, nullable=False, primary_key=True)
    mod = Column("mod", Integer, nullable=False)
    target = Column("target", Integer, nullable=False)
    action = Column("action", String(32), nullable=False)
    reason = Column("reason", String(2048, collation="utf8"), nullable=True)
    time = Column("time", DateTime, nullable=False, onupdate=func.now())
    type = Column("type", TinyInt, nullable=False, default=False)
```

**New LogTable class:**
```python
class LogTable(Base):
    __tablename__ = "logs"

    id = Column("id", Integer, primary_key=True, autoincrement=True)
    from_id = Column("from_id", Integer, nullable=False)
    to_id = Column("to_id", Integer, nullable=False)
    action = Column("action", String(32), nullable=False)
    msg = Column("msg", String(2048, collation="utf8"), nullable=True)
    created_at = Column("created_at", DateTime, nullable=False, server_default=func.now())
    action_type = Column("action_type", TinyInt, nullable=False, default=0)
```

**Current READ_PARAMS:**
```python
READ_PARAMS = (
    LogTable.id,
    LogTable.mod.label("from"),
    LogTable.target.label("to"),
    LogTable.action,
    LogTable.reason.label("msg"),
    LogTable.time,
    LogTable.type,
)
```

**New READ_PARAMS:**
```python
READ_PARAMS = (
    LogTable.id,
    LogTable.from_id,
    LogTable.to_id,
    LogTable.action,
    LogTable.msg,
    LogTable.created_at,
    LogTable.action_type,
)
```

**Current Log TypedDict:**
```python
class Log(TypedDict):
    id: str
    _from: int
    to: int
    action: str
    msg: str | None
    time: datetime
    type: bool
```

**New Log TypedDict:**
```python
class Log(TypedDict):
    id: int
    from_id: int
    to_id: int
    action: str
    msg: str | None
    created_at: datetime
    action_type: int
```

**Current create() function:**
```python
async def create(
    _from: int,
    to: int,
    action: str,
    msg: str,
    type: int = 0,
) -> Log:
    """Create a new log entry in the database."""
    
    # Generate a unique hash for the log entry
    log_content = f"{_from}{to}{action}{msg}{type}"
    log_hash = hashlib.sha256(log_content.encode()).hexdigest()

    insert_stmt = insert(LogTable).values(
        {
            "id": log_hash,
            "mod": _from,
            "target": to,
            "action": action,
            "reason": msg,
            "time": func.now(),
            "type": type,
        },
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(LogTable.id == log_hash)
    log = await app.state.services.database.fetch_one(select_stmt)
    assert log is not None
    return cast(Log, log)
```

**New create() function:**
```python
async def create(
    from_id: int,
    to_id: int,
    action: str,
    msg: str,
    action_type: int = 0,
) -> Log:
    """Create a new log entry in the database."""
    
    insert_stmt = insert(LogTable).values(
        {
            "from_id": from_id,
            "to_id": to_id,
            "action": action,
            "msg": msg,
            "created_at": func.now(),
            "action_type": action_type,
        },
    )
    result = await app.state.services.database.execute(insert_stmt)
    
    # Get the auto-generated id
    log_id = result.lastrowid

    select_stmt = select(*READ_PARAMS).where(LogTable.id == log_id)
    log = await app.state.services.database.fetch_one(select_stmt)
    assert log is not None
    return cast(Log, log)
```

### Code References to Update

Search for all `logs_repo.create` calls and update parameter names:

1. [`app/commands.py:830`](app/commands.py:830) - Note command
   ```python
   # Current:
   await logs_repo.create(
       _from=ctx.player.id,
       to=target.id,
       action="note",
       msg=" ".join(ctx.args[1:]),
       type=3,
   )
   
   # New:
   await logs_repo.create(
       from_id=ctx.player.id,
       to_id=target.id,
       action="note",
       msg=" ".join(ctx.args[1:]),
       action_type=3,
   )
   ```

2. [`app/objects/player.py:571`](app/objects/player.py:571) - Restrict action
   ```python
   # Current:
   await logs_repo.create(
       _from=admin.id,
       to=self.id,
       action="restrict",
       msg=reason,
   )
   
   # New:
   await logs_repo.create(
       from_id=admin.id,
       to_id=self.id,
       action="restrict",
       msg=reason,
   )
   ```

3. [`app/objects/player.py:605`](app/objects/player.py:605) - Unrestrict action
   ```python
   # Current:
   await logs_repo.create(
       _from=admin.id,
       to=self.id,
       action="unrestrict",
       msg=reason,
   )
   
   # New:
   await logs_repo.create(
       from_id=admin.id,
       to_id=self.id,
       action="unrestrict",
       msg=reason,
   )
   ```

4. [`app/objects/player.py:648`](app/objects/player.py:648) - Silence action
   ```python
   # Current:
   await logs_repo.create(
       _from=admin.id,
       to=self.id,
       action="silence",
       msg=reason,
   )
   
   # New:
   await logs_repo.create(
       from_id=admin.id,
       to_id=self.id,
       action="silence",
       msg=reason,
   )
   ```

5. [`app/objects/player.py:676`](app/objects/player.py:676) - Unsilence action
   ```python
   # Current:
   await logs_repo.create(
       _from=admin.id,
       to=self.id,
       action="unsilence",
       msg=reason,
   )
   
   # New:
   await logs_repo.create(
       from_id=admin.id,
       to_id=self.id,
       action="unsilence",
       msg=reason,
   )
   ```

## Implementation Steps

1. **Create migration script** - Transform logs table to new schema
2. **Update [`app/repositories/logs.py`](app/repositories/logs.py)**
   - Update `LogTable` class with new column names
   - Update `READ_PARAMS` tuple
   - Update `Log` TypedDict
   - Update `create()` function signature and implementation
   - Remove hashlib import (no longer needed)
3. **Update code references**
   - Update all `logs_repo.create` calls with new parameter names
4. **Update [`migrations/base.sql`](migrations/base.sql)**
   - Replace old logs table definition with new schema
5. **Test migration**
   - Run migration on test database
   - Verify all existing logs are preserved
   - Test new logging functionality

## Testing Checklist

- [ ] Migration runs without errors
- [ ] Existing logs are preserved after migration (with new integer IDs)
- [ ] New logs can be created with new schema
- [ ] All code references updated and working
- [ ] Indexes are created correctly
- [ ] Query performance is improved with new indexes
