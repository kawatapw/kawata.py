# Sessions System Plan

## Overview
Implement a sessions system that allows players to create mini-profiles with goals, track progress, and showcase achievements. Sessions integrate with cross-server leaderboards.

## Key Design Decisions
- **Scores count globally**: Session scores count toward both session AND global/seasonal leaderboards
- **One active session**: Only one active session per user at a time
- **Configurable max sessions**: Default 5 sessions per user
- **Goal types**: PP, Rank, Score, Custom, Server Rank
- **Cross-server integration**: Sessions can target external server leaderboards
- **Unlimited duration**: Sessions have no time limit (only quantity limit)

## Database Schema

### sessions Table
```sql
CREATE TABLE sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(256) DEFAULT NULL,
    goal_type ENUM('pp', 'rank', 'score', 'custom', 'server_rank') NOT NULL,
    goal_value VARCHAR(128) DEFAULT NULL COMMENT 'Target value for the goal',
    goal_server INT DEFAULT NULL COMMENT 'FK to external_servers for cross-server goals',
    start_date DATETIME NOT NULL,
    end_date DATETIME DEFAULT NULL COMMENT 'NULL means unlimited duration',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_is_active (is_active),
    INDEX idx_goal_type (goal_type),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### session_stats Table
```sql
CREATE TABLE session_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    mode TINYINT NOT NULL,
    tscore BIGINT UNSIGNED NOT NULL DEFAULT 0,
    rscore BIGINT UNSIGNED NOT NULL DEFAULT 0,
    pp INT UNSIGNED NOT NULL DEFAULT 0,
    plays INT UNSIGNED NOT NULL DEFAULT 0,
    playtime INT UNSIGNED NOT NULL DEFAULT 0,
    acc FLOAT(6,3) NOT NULL DEFAULT 0.000,
    max_combo INT UNSIGNED NOT NULL DEFAULT 0,
    total_hits INT UNSIGNED NOT NULL DEFAULT 0,
    replay_views INT UNSIGNED NOT NULL DEFAULT 0,
    xh_count INT UNSIGNED NOT NULL DEFAULT 0,
    x_count INT UNSIGNED NOT NULL DEFAULT 0,
    sh_count INT UNSIGNED NOT NULL DEFAULT 0,
    s_count INT UNSIGNED NOT NULL DEFAULT 0,
    a_count INT UNSIGNED NOT NULL DEFAULT 0,
    UNIQUE KEY idx_session_mode (session_id, mode),
    INDEX idx_session_id (session_id),
    INDEX idx_mode (mode),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### session_scores Table
```sql
CREATE TABLE session_scores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    score_id BIGINT UNSIGNED NOT NULL,
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_session_score (session_id, score_id),
    INDEX idx_session_id (session_id),
    INDEX idx_score_id (score_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (score_id) REFERENCES scores(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### external_servers Table
```sql
CREATE TABLE external_servers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    api_url VARCHAR(256) NOT NULL,
    api_key VARCHAR(128) DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_sync DATETIME DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### external_leaderboard_cache Table
```sql
CREATE TABLE external_leaderboard_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    server_id INT NOT NULL,
    user_id VARCHAR(64) NOT NULL COMMENT 'External user identifier',
    mode TINYINT NOT NULL,
    pp INT UNSIGNED NOT NULL DEFAULT 0,
    rank INT UNSIGNED DEFAULT NULL,
    last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_server_user_mode (server_id, user_id, mode),
    INDEX idx_server_id (server_id),
    INDEX idx_mode (mode),
    INDEX idx_pp (pp),
    INDEX idx_rank (rank),
    FOREIGN KEY (server_id) REFERENCES external_servers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## Goal Types

### PP Goal
```json
{
    "goal_type": "pp",
    "goal_value": "10000"
}
```
Track progress toward a target PP value.

### Rank Goal
```json
{
    "goal_type": "rank",
    "goal_value": "1"
}
```
Track progress toward a target global rank.

### Score Goal
```json
{
    "goal_type": "score",
    "goal_value": "1000000000"
}
```
Track progress toward a target total score.

### Custom Goal
```json
{
    "goal_type": "custom",
    "goal_value": "Get 100 S ranks"
}
```
Custom goal with user-defined description.

### Server Rank Goal
```json
{
    "goal_type": "server_rank",
    "goal_value": "1",
    "goal_server": 1
}
```
Track progress toward a rank on an external server.

## Code Changes

### New Repository
File: [`app/repositories/sessions.py`](app/repositories/sessions.py)

```python
# Sessions
async def create_session(user_id: int, name: str, description: str, goal_type: str, goal_value: str, goal_server: int | None = None) -> Session: ...
async def fetch_session(id: int | None = None, user_id: int | None = None, is_active: bool | None = None) -> Session | None: ...
async def fetch_active_session(user_id: int) -> Session | None: ...
async def fetch_user_sessions(user_id: int, page: int | None = None, page_size: int | None = None) -> list[Session]: ...
async def activate_session(id: int) -> Session | None: ...
async def deactivate_session(id: int) -> Session | None: ...
async def update_session(id: int, **kwargs) -> Session | None: ...

# Session Stats
async def create_session_stats(session_id: int, mode: int) -> SessionStat: ...
async def fetch_session_stats(session_id: int, mode: int | None = None) -> list[SessionStat]: ...
async def update_session_stats(session_id: int, mode: int, **kwargs) -> SessionStat | None: ...

# Session Scores
async def add_session_score(session_id: int, score_id: int) -> SessionScore: ...
async def fetch_session_scores(session_id: int) -> list[SessionScore]: ...

# Progress Tracking
async def calculate_progress(session_id: int) -> dict: ...
async def check_goal_completion(session_id: int) -> bool: ...
```

### External Servers Repository
File: [`app/repositories/external_servers.py`](app/repositories/external_servers.py)

```python
async def create_server(name: str, api_url: str, api_key: str | None = None) -> ExternalServer: ...
async def fetch_server(id: int | None = None, name: str | None = None) -> ExternalServer | None: ...
async def fetch_active_servers() -> list[ExternalServer]: ...
async def update_server(id: int, **kwargs) -> ExternalServer | None: ...

async def sync_leaderboard(server_id: int) -> None: ...
async def fetch_external_rank(server_id: int, user_id: str, mode: int) -> int | None: ...
async def fetch_cached_leaderboard(server_id: int, mode: int, limit: int = 50) -> list[dict]: ...
```

### Commands
```python
@command(Privileges.UNRESTRICTED)
async def session_create(ctx: Context) -> str | None:
    """Create a new session with a goal."""

@command(Privileges.UNRESTRICTED)
async def session_start(ctx: Context) -> str | None:
    """Activate a session."""

@command(Privileges.UNRESTRICTED)
async def session_end(ctx: Context) -> str | None:
    """Deactivate current session."""

@command(Privileges.UNRESTRICTED)
async def session_list(ctx: Context) -> str | None:
    """List your sessions."""

@command(Privileges.UNRESTRICTED)
async def session_info(ctx: Context) -> str | None:
    """Show session details and progress."""

@command(Privileges.UNRESTRICTED)
async def session_goal(ctx: Context) -> str | None:
    """Update session goal."""

# External Servers
@command(Privileges.ADMINISTRATOR)
async def server_add(ctx: Context) -> str | None:
    """Add an external server for cross-server leaderboards."""

@command(Privileges.UNRESTRICTED)
async def server_list(ctx: Context) -> str | None:
    """List available external servers."""

@command(Privileges.ADMINISTRATOR)
async def server_sync(ctx: Context) -> str | None:
    """Sync external server leaderboards."""
```

## Implementation Steps

1. **Create database tables**
   - Create sessions table
   - Create session_stats table
   - Create session_scores table
   - Create external_servers table
   - Create external_leaderboard_cache table

2. **Create repositories**
   - Create [`app/repositories/sessions.py`](app/repositories/sessions.py)
   - Create [`app/repositories/external_servers.py`](app/repositories/external_servers.py)

3. **Implement session logic**
   - Session creation with goal setting
   - Session activation/deactivation
   - Progress tracking
   - Goal completion detection

4. **Integrate with score submission**
   - Update active session stats when score submitted
   - Record score in session_scores

5. **Implement external server integration**
   - API client for external servers
   - Leaderboard caching
   - Periodic sync

6. **Create commands**
   - Session management commands
   - External server commands

7. **Add profile display**
   - Show active session on profile
   - Show session history
   - Show progress toward goals

## Testing Checklist
- [ ] Sessions can be created with goals
- [ ] Only one active session at a time
- [ ] Max sessions enforced
- [ ] Session stats update with score submission
- [ ] Progress tracking works
- [ ] Goal completion detected
- [ ] External servers can be added
- [ ] Leaderboard sync works
- [ ] Cross-server goals work
- [ ] Profile display works
