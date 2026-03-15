# Seasons System Plan

## Overview
Implement a flexible seasons system that uses datetime-based filtering rather than storing season_id on scores. Seasons support multiple schedule types including a unique 28-day calendar system.

## Key Design Decisions
- **Datetime-based filtering**: Seasons filter scores by `play_time` datetime range, no `season_id` column on scores table
- **Aggregated stats**: Season stats are calculated and stored in `season_stats` table (not computed on-the-fly)
- **Multiple schedule types**: Manual, custom intervals, world seasons, half-year, third-year, quarter-year, and 28-day calendar
- **Single active season**: Only 1 active season awards badges/prizes, but all seasons are viewable
- **New Year's Day special**: 1-day season with top 3 players earning a badge

## Database Schema

### season_schedules Table
```sql
CREATE TABLE season_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(256) DEFAULT NULL,
    schedule_type ENUM('manual', 'custom', 'seasonal', 'half_year', 'third_year', 'quarter_year', '28day_calendar') NOT NULL,
    config JSON NOT NULL COMMENT 'Schedule-specific configuration',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### seasons Table
```sql
CREATE TABLE seasons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    schedule_id INT DEFAULT NULL COMMENT 'FK to season_schedules, NULL for manual seasons',
    start_date DATETIME NOT NULL,
    end_date DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    awards_badges BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Whether this season awards badges (e.g., New Year''s Day)',
    description VARCHAR(256) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_schedule_id (schedule_id),
    INDEX idx_start_date (start_date),
    INDEX idx_end_date (end_date),
    INDEX idx_is_active (is_active),
    FOREIGN KEY (schedule_id) REFERENCES season_schedules(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### season_config Table
```sql
CREATE TABLE season_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    season_id INT NOT NULL,
    config_key VARCHAR(64) NOT NULL,
    config_value TEXT DEFAULT NULL,
    UNIQUE KEY idx_season_key (season_id, config_key),
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### season_stats Table
```sql
CREATE TABLE season_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    season_id INT NOT NULL,
    user_id INT NOT NULL,
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
    UNIQUE KEY idx_season_user_mode (season_id, user_id, mode),
    INDEX idx_season_id (season_id),
    INDEX idx_user_id (user_id),
    INDEX idx_mode (mode),
    INDEX idx_pp (pp),
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## Schedule Types

### Manual
- Admin manually starts/ends seasons
- No automatic scheduling

### Custom
- Configurable interval in days (e.g., every 30 days)
- Auto-start new season when previous ends

### Seasonal (World Seasons)
- Spring: March 20 - June 20
- Summer: June 21 - September 22
- Fall: September 23 - December 20
- Winter: December 21 - March 19

### Half Year
- 2 seasons per year
- January-June, July-December

### Third Year
- 3 seasons per year
- January-April, May-August, September-December

### Quarter Year
- 4 seasons per year
- Q1: January-March, Q2: April-June, Q3: July-September, Q4: October-December

### 28-Day Calendar
- 13 months of 28 days = 364 days
- New Year's Day is separate (day 365)
- Seasons: Every 4 months (3 seasons of 4 months + 1 special month)
- New Year's Day: 1-day special seasonal event (top 3 players get badge)

## Schedule Configuration Examples

### Custom (30 days)
```json
{
    "interval_days": 30,
    "auto_start": true
}
```

### 28-Day Calendar
```json
{
    "month_length": 28,
    "months_per_season": 4,
    "special_month": 13,
    "new_years_day": true
}
```

## Code Changes

### New Repository
File: [`app/repositories/seasons.py`](app/repositories/seasons.py)

```python
async def create(
    name: str,
    schedule_id: int | None,
    start_date: datetime,
    end_date: datetime,
    awards_badges: bool = False,
    description: str | None = None,
) -> Season: ...

async def fetch_one(id: int | None = None, name: str | None = None, is_active: bool | None = None) -> Season | None: ...

async def fetch_active() -> Season | None: ...

async def fetch_many(page: int | None = None, page_size: int | None = None) -> list[Season]: ...

async def partial_update(id: int, **kwargs) -> Season | None: ...

async def activate(id: int) -> Season | None: ...

async def deactivate(id: int) -> Season | None: ...

async def calculate_stats(season_id: int, user_id: int, mode: int) -> SeasonStat: ...

async def fetch_stats(season_id: int, user_id: int | None = None, mode: int | None = None) -> list[SeasonStat]: ...
```

### Season Management Commands
```python
@command(Privileges.ADMINISTRATOR)
async def season_create(ctx: Context) -> str | None:
    """Create a new season."""

@command(Privileges.ADMINISTRATOR)
async def season_start(ctx: Context) -> str | None:
    """Start/activate a season."""

@command(Privileges.ADMINISTRATOR)
async def season_end(ctx: Context) -> str | None:
    """End/deactivate a season."""

@command(Privileges.UNRESTRICTED)
async def season_list(ctx: Context) -> str | None:
    """List all seasons."""

@command(Privileges.ADMINISTRATOR)
async def season_schedule(ctx: Context) -> str | None:
    """Manage season schedules."""
```

### Background Task
```python
# In app/bg_loops.py
async def check_season_schedules() -> None:
    """Check and auto-start/end seasons based on schedule configuration."""
    # Runs every minute
    # Checks for seasons that should start/end
    # Calculates final stats for ending seasons
    # Awards badges for special seasons (New Year's Day)
```

### Leaderboard Filtering
```python
# In app/repositories/scores.py
async def fetch_many(
    map_md5: str | None = None,
    mode: int | None = None,
    status: int | None = None,
    user_id: int | None = None,
    season_id: int | None = None,  # NEW
    leaderboard_type_id: int | None = None,  # NEW
) -> list[Score]:
    # Filter by play_time within season date range
    # Filter by leaderboard_type_id
```

## Implementation Steps

1. **Create database tables**
   - Create `season_schedules` table
   - Create `seasons` table
   - Create `season_config` table
   - Create `season_stats` table

2. **Create repository**
   - Create [`app/repositories/seasons.py`](app/repositories/seasons.py)
   - Implement CRUD operations
   - Implement stats calculation

3. **Implement schedule types**
   - Create schedule type handlers
   - Implement 28-day calendar logic
   - Implement auto-scheduling background task

4. **Create commands**
   - Implement season management commands
   - Add season filtering to leaderboard commands

5. **Integrate with scores**
   - Add season filtering to score queries
   - Implement season stats aggregation

6. **Testing**
   - Test all schedule types
   - Test season activation/deactivation
   - Test stats calculation
   - Test leaderboard filtering

## Testing Checklist
- [ ] All schedule types work correctly
- [ ] 28-day calendar calculates correctly
- [ ] New Year's Day special season works
- [ ] Season stats aggregate correctly
- [ ] Leaderboard filtering by season works
- [ ] Background task auto-starts/ends seasons
- [ ] Only one active season at a time
- [ ] All seasons are viewable even when not active
