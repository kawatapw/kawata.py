# Seasons System Plan

## Overview

Implement a flexible seasons system that uses datetime-based filtering rather than storing season_id on scores. Seasons support multiple schedule types including a unique International Fixed Calendar system. **Seasons are an optional feature** enabled via the `server_data` table.

## Key Design Decisions

- **Datetime-based filtering**: Seasons filter scores by `play_time` datetime range, no `season_id` column on scores table
- **Season stats in existing table**: Add `season_id` column to existing `stats` table (not a separate table)
- **Modular schedule type system**: Schedule types are implemented as separate modules in `app/schedule_types/`, making the system extensible with new season types
- **Multiple schedule types**: Manual, custom intervals, world seasons, half-year, third-year, quarter-year, and International Fixed Calendar (all implemented as separate modules)
- **Single active season type**: Only 1 season type is active/displayed by default, but all season types are viewable
- **New Year's Day special**: 1-day season with top 3 players earning a badge (deferred to cosmetics overhaul)
- **Optional feature**: Seasons enabled/disabled via `server_data` table entry
- **Player preference storage**: Players can toggle between all-time and seasonal views, stored in users table
- **Default display mode**: Server can configure default view (all-time or seasonal) via `server_data`
- **Migration-based deployment**: Database changes applied via `migrations.sql` with version comments
- **Score submission unchanged**: Scores submit normally without season_id; only active season stats updated on submit
- **Periodic stat updates**: Non-active seasons updated periodically via background task
- **On-the-fly stat aggregation**: Individual user stats calculated on-the-fly via full aggregation query; clan/multi-user stats aggregated periodically
- **Seasonal rules system**: Deferred to next overhaul (extended cheat support)
- **Extensible architecture**: New schedule types can be added by creating new modules without modifying core system code
- **Hybrid caching**: Redis for leaderboards, player object caching for individual stats

## Feature Toggle & Configuration

Seasons are enabled/disabled and configured via the `server_data` table:

```sql
-- Enable seasons
INSERT INTO server_data (type, value) VALUES ('seasons_enabled', '1')
ON DUPLICATE KEY UPDATE value = '1';

-- Disable seasons
UPDATE server_data SET value = '0' WHERE type = 'seasons_enabled';

-- Set default display mode (all_time or seasonal)
INSERT INTO server_data (type, value) VALUES ('seasons_default_mode', 'all_time')
ON DUPLICATE KEY UPDATE value = 'all_time';

-- Set active season type ID (the season type displayed by default)
INSERT INTO server_data (type, value) VALUES ('seasons_active_type_id', '1')
ON DUPLICATE KEY UPDATE value = '1';
```

When seasons are disabled:

- All season-related commands are hidden/unavailable
- API endpoints return all-time stats (no season filtering)
- Background task for season scheduling is skipped
- Leaderboard queries ignore season filtering
- Player preference for seasonal view is ignored

### Active Season Type

A server can define multiple season types (e.g., monthly, quarterly, yearly), but only **one season type is active/displayed by default**. The active season type is what users see when they view seasonal stats. Users can still view other season types through explicit selection.

**Default value**: `seasons_active_type_id` = 1 (first schedule type created)

**Example configuration**:

- Server has monthly and yearly season types defined
- `seasons_active_type_id` = 2 (yearly season type)
- Users see yearly season stats by default
- Users can still view monthly season stats by selecting a specific month

### Player View Preferences

Players can toggle between all-time and seasonal views. This preference is stored in the `users` table (similar to `preferred_mode`):

```sql
-- Add season preference column to users table
ALTER TABLE users ADD COLUMN preferred_lb_view ENUM('all_time', 'seasonal') NOT NULL DEFAULT 'all_time';
```

```python
# In app/objects/player.py
class Player:
    # ... existing fields ...
    preferred_lb_view: str = "all_time"  # "all_time" or "seasonal"
```

**Commands for players**:

- `!seasons` - Toggle between all-time and seasonal view
- `!seasons <season_id>` - View specific season stats
- `!seasons all` - Switch to all-time view

**API endpoints** (additive, non-breaking):

- `POST /api/v2/players/{id}/season-preference` - Update player's season view preference
- `GET /api/v2/players/{id}/season-preference` - Get player's current preference

## Database Migration

Database changes are applied via the `migrations.sql` file with version comments. When the server starts and detects a version change, it applies the SQL in the migrations file to update the database.

**Migration version**: v5.3.2

**Migration file format** (`migrations/migrations.sql`):

```sql
# 5.3.2
-- Add seasons system tables
CREATE TABLE season_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(256) DEFAULT NULL,
    schedule_type ENUM('manual', 'custom', 'seasonal', 'half_year', 'third_year', 'quarter_year', 'ifc_sched') NOT NULL,
    config JSON NOT NULL COMMENT 'Schedule-specific configuration',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE seasons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    schedule_id INT DEFAULT NULL COMMENT 'FK to season_schedules, NULL for manual seasons',
    start_date DATETIME NOT NULL,
    end_date DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    end_calculated BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Whether final stats have been calculated for ended season',
    awards_badges BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Whether this season awards badges (reserved for future use)',
    description VARCHAR(256) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_schedule_id (schedule_id),
    INDEX idx_start_date (start_date),
    INDEX idx_end_date (end_date),
    INDEX idx_is_active (is_active),
    FOREIGN KEY (schedule_id) REFERENCES season_schedules(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE season_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    season_id INT NOT NULL,
    config_key VARCHAR(64) NOT NULL,
    config_value TEXT DEFAULT NULL,
    UNIQUE KEY idx_season_key (season_id, config_key),
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Modify stats table to add season_id (nullable with unique constraint)
ALTER TABLE stats ADD COLUMN season_id INT NULL DEFAULT NULL;
ALTER TABLE stats ADD UNIQUE KEY idx_season_unique (id, mode, season_id);
ALTER TABLE stats ADD INDEX idx_season_id (season_id);

-- Add season preference column to users table
ALTER TABLE users ADD COLUMN preferred_lb_view ENUM('all_time', 'seasonal') NOT NULL DEFAULT 'all_time';

-- Add recommended indexes for scores table
CREATE INDEX idx_scores_season_filter ON scores (play_time, status, mode);
CREATE INDEX idx_scores_user_season ON scores (userid, play_time, mode);

-- Add default season configuration
INSERT INTO server_data (type, value) VALUES ('seasons_enabled', '0');
INSERT INTO server_data (type, value) VALUES ('seasons_default_mode', 'all_time');
INSERT INTO server_data (type, value) VALUES ('seasons_active_type_id', '1');
```

## Database Schema

### season_schedules Table

```sql
CREATE TABLE season_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(256) DEFAULT NULL,
    schedule_type ENUM('manual', 'custom', 'seasonal', 'half_year', 'third_year', 'quarter_year', 'ifc_sched') NOT NULL,
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
    end_calculated BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Whether final stats have been calculated for ended season',
    awards_badges BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Whether this season awards badges (reserved for future use)',
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

### Modified stats Table

Add `season_id` column to existing `stats` table as a nullable column with a unique constraint (preserving the original primary key):

```sql
ALTER TABLE stats ADD COLUMN season_id INT NULL DEFAULT NULL;
ALTER TABLE stats ADD UNIQUE KEY idx_season_unique (id, mode, season_id);
ALTER TABLE stats ADD INDEX idx_season_id (season_id);
```

**Benefits**:

- No data duplication
- Simpler queries (no JOINs needed)
- Easier to maintain consistency
- Can query all-time stats with `WHERE season_id IS NULL`
- Preserves existing primary key structure for backward compatibility
- Unique constraint ensures no duplicate stats for the same player/mode/season combination

## Score Submission & Stat Updates

### Score Submission Flow

Scores are submitted normally without any season_id. The score submission process remains unchanged:

1. Player submits score via [`app/api/domains/osu.py`](app/api/domains/osu.py)
2. Score is inserted into `scores` table with `play_time` datetime
3. Normal stat updates occur for all-time stats in `stats` table (where `season_id IS NULL`)

### Season Stat Updates

**On score submit**: Only the **active season** (configured via `seasons_active_type_id`) has its stats updated immediately. This keeps score submission fast and reduces load.

**Periodic updates**: All other configured seasons (non-active seasons) have their stats updated periodically via background task. This keeps non-active seasons reasonably up-to-date without impacting score submission performance.

**Season end calculation**: Once a season has had its "end calculation" done (`end_calculated = TRUE`), it is no longer updated.

```python
# In app/api/domains/osu.py (score submission)
async def submit_score(...):
    # ... existing score submission logic ...

    # Update all-time stats (existing logic)
    await stats_repo.partial_update(
        player_id=user_id,
        mode=mode,
        # ... stat updates ...
    )

    # Update ONLY the active season stats on score submit
    # Errors are logged but do not fail the score submission
    if seasons_enabled:
        try:
            active_season = await seasons_repo.fetch_active_season_by_type()
            if active_season and active_season.start_date <= play_time < active_season.end_date:
                try:
                    await stats_repo.partial_update(
                        player_id=user_id,
                        mode=mode,
                        season_id=active_season.id,
                        # ... same stat updates ...
                    )
                except Exception as e:
                    log(
                        f"Failed to update active season stats for season {active_season.id}: {e}",
                        Ansi.LRED,
                        level=logLevel.ERROR,
                    )
        except Exception as e:
            log(
                f"Failed to fetch active season for time {play_time}: {e}",
                Ansi.LRED,
                level=logLevel.ERROR,
            )
```

### Periodic Stat Updates for Non-Active Seasons

Non-active seasons are updated periodically via background task to keep stats reasonably current:

```python
# In app/bg_loops.py
async def update_non_active_season_stats(interval: int = 300) -> None:
    """Periodically update stats for non-active seasons.

    Args:
        interval: Update interval in seconds (default: 300 seconds / 5 minutes)
    """
    while True:
        seasons_enabled = await app.state.services.database.fetch_val(
            "SELECT value FROM server_data WHERE type = 'seasons_enabled'"
        )

        if seasons_enabled != '1':
            await asyncio.sleep(interval)
            continue

        # Get all seasons that are currently active (within their date range)
        # but are NOT the active season type
        active_season_type_id = await app.state.services.database.fetch_val(
            "SELECT value FROM server_data WHERE type = 'seasons_active_type_id'"
        )

        current_time = datetime.now()
        non_active_seasons = await seasons_repo.fetch_non_active_seasons(
            active_season_type_id=int(active_season_type_id) if active_season_type_id else None,
            current_time=current_time,
        )

        for season in non_active_seasons:
            # Skip seasons that have had their end calculation done
            if season.end_calculated:
                continue

            # Update stats for this season
            await seasons_repo.update_season_stats(season.id)

        await asyncio.sleep(interval)
```

### Stat Aggregation Strategy

- **Individual user stats**: Calculated on-the-fly via full aggregation query (SUM, COUNT, etc.) on scores within season date range
- **Clan/multi-user stats**: Aggregated periodically via background task (high volume)
- **Leaderboard stats**: Cached in Redis for all-time and active season type with TTL
- **Non-active season stats**: Updated periodically via background task (not on every score submit)

### Caching Strategy

**Hybrid approach**:

1. **Redis caching for leaderboards**: Season leaderboards cached with TTL (5 minutes for active season, 15 minutes for historical seasons)
2. **Player object caching for individual stats**: Follow existing player object caching pattern

```python
# Redis caching for leaderboards
async def get_season_leaderboard(season_id: int, mode: int, page: int = 1) -> list[PlayerStats]:
    cache_key = f"leaderboard:season:{season_id}:mode:{mode}:page:{page}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Query database
    results = await stats_repo.fetch_many(
        season_id=season_id,
        mode=mode,
        page=page,
        page_size=50
    )

    # Cache with TTL (5 minutes for active, 15 minutes for historical)
    ttl = 300 if is_active_season(season_id) else 900
    await redis.setex(cache_key, ttl, json.dumps(results))

    return results
```

```python
# Player object caching for individual stats (existing pattern)
class Player:
    # ... existing fields ...
    preferred_lb_view: str = "all_time"

    # Cache for individual stats (all-time and active season)
    _stats_cache: dict[str, Stat] = {}

    def get_cached_stats(self, season_id: int | None = None) -> Stat | None:
        """Get cached stats for a specific season or all-time."""
        cache_key = f"stats_{season_id or 'alltime'}"
        return self._stats_cache.get(cache_key)

    def set_cached_stats(self, stats: Stat, season_id: int | None = None) -> None:
        """Cache stats for a specific season or all-time."""
        cache_key = f"stats_{season_id or 'alltime'}"
        self._stats_cache[cache_key] = stats
```

## Performance Optimization Options

When implementing the seasons system, consider these performance optimization strategies based on your server's scale and requirements:

### Recommended Approach by Server Size

**Small servers (< 100K scores)**:

- Use indexes only
- Query scores table directly with datetime filtering
- Simple and maintainable

**Medium servers (100K - 10M scores)**:

- Use Redis query result caching
- Cache season leaderboards with 5-minute TTL
- Monitor query performance

**Large servers (10M+ scores)**:

- Use Redis query result caching
- Implement background refresh for cached data
- Monitor query performance and adjust TTL as needed

### Implementation Notes

1. **Start simple**: Begin with indexes and direct queries. Add optimizations only when needed.
2. **Monitor first**: Use slow query logs and performance metrics to identify bottlenecks.
3. **Incremental improvements**: Add one optimization at a time and measure impact.
4. **Consider your use case**: If most players view current season stats, optimize for that. If historical data is rarely accessed, optimize differently.

## Index Recommendations

Based on the datetime-based filtering approach, the following indexes are recommended:

### scores Table Indexes

```sql
-- Composite index for season filtering (play_time + status + mode)
CREATE INDEX idx_scores_season_filter ON scores (play_time, status, mode);

-- Composite index for user season stats (userid + play_time + mode)
CREATE INDEX idx_scores_user_season ON scores (userid, play_time, mode);

-- Composite index for leaderboard queries (map_md5 + status + mode + play_time)
CREATE INDEX idx_scores_leaderboard_season ON scores (map_md5, status, mode, play_time);
```

### stats Table Indexes

```sql
-- Index for season-specific stats queries
CREATE INDEX idx_stats_season ON stats (season_id, mode, pp);

-- Index for all-time stats queries
CREATE INDEX idx_stats_alltime ON stats (id, mode) WHERE season_id IS NULL;
```

**Note**: The `WHERE season_id IS NULL` partial index may not be supported by all MySQL versions. If not supported, use a regular index on `(id, mode)`.

## Season Transitions

### Automatic Season Transitions

Seasons are automatic based on the season type schedule. When a season ends:

1. Background task detects season end time has passed
2. Final stats are calculated and stored for the ending season (`end_calculated = TRUE`)
3. New season is automatically created based on schedule type
4. New season becomes active
5. Rewards are distributed (if applicable, deferred to cosmetics overhaul)

### Edge Case: Score During Transition

If a player submits a score during a season transition:

- The score counts for the **old season** based on its `play_time`
- Stats are updated for the old season
- The new season starts fresh with no scores until its start_time

**Implementation**:

```python
# In seasons repository
async def fetch_seasons_containing_time(play_time: datetime) -> list[Season]:
    """Fetch all seasons that contain the given play_time."""
    select_stmt = (
        select(*SEASON_READ_PARAMS)
        .where(SeasonsTable.start_date <= play_time)
        .where(SeasonsTable.end_date > play_time)
    )
    return await app.state.services.database.fetch_all(select_stmt)
```

## API Response Format

When seasons are enabled, API responses include season information:

### Score Response with Season Info

```json
{
    "id": 12345,
    "map_md5": "abc123...",
    "score": 1000000,
    "pp": 100.5,
    "play_time": "2024-03-15T12:00:00Z",
    "season": {
        "id": 1,
        "name": "Spring 2024",
        "type": "seasonal",
        "start_date": "2024-03-20T00:00:00Z",
        "end_date": "2024-06-20T23:59:59Z"
    }
}
```

### Player Stats Response with Season Info

```json
{
    "id": 12345,
    "mode": 0,
    "pp": 1000.5,
    "plays": 500,
    "season": {
        "id": 1,
        "name": "Spring 2024",
        "type": "seasonal"
    }
}
```

## Rewards System (Deferred)

**Note**: Rewards (badges, prizes) are deferred to the cosmetics system overhaul. The `awards_badges` field is reserved for future use.

## Schedule Types

The seasons system uses a modular, extensible architecture for schedule types. Each module acts as a **configuration provider** that extends the seasons system with new scheduling methods, configuration options, and date calculation logic.

### Architecture Overview

Schedule type modules are implemented as Python modules in `app/schedule_types/`. Each module implements a common interface and can be registered with the system.

**Key Benefits**:

- **Extensible**: New scheduling methods can be added by creating a new module
- **Maintainable**: Each module encapsulates related scheduling logic
- **Configurable**: Modules can define custom configuration schemas and validation
- **Testable**: Each module can be tested independently
- **Composable**: Modules can provide multiple scheduling methods or configuration options

### Built-in Schedule Type Modules

#### Manual Module

The manual module provides basic manual season management with no automatic scheduling.

**Schedule Types Provided**:

- `manual` - Admin manually starts/ends seasons

**Configuration Schema**:

```json
{
    "type": "manual"
}
```

**Features**:

- No automatic scheduling
- Admin controls season start/end via commands
- Simplest schedule type with minimal configuration

#### Standard Calendar Module

The standard calendar module provides all scheduling methods based on the standard Gregorian calendar.

**Schedule Types Provided**:

- `custom` - Configurable interval with flexible units (days, weeks, months)
- `half_year` - 2 seasons per year (January-June, July-December)
- `third_year` - 3 seasons per year (January-April, May-August, September-December)
- `quarter_year` - 4 seasons per year (Q1, Q2, Q3, Q4)

**Configuration Schema**:

```json
{
    "schedule_type": "custom",
    "interval": {
        "value": 30,
        "unit": "days"
    },
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-12-31T23:59:59Z",
    "auto_start": true,
    "auto_end": true
}
```

```json
{
    "schedule_type": "half_year",
    "start_month": 1,
    "timezone": "UTC"
}
```

```json
{
    "schedule_type": "third_year",
    "start_month": 1,
    "timezone": "UTC"
}
```

```json
{
    "schedule_type": "quarter_year",
    "start_month": 1,
    "timezone": "UTC"
}
```

**Module Features**:

- Provides multiple scheduling methods in a single module
- Handles all standard calendar-based date calculations
- Supports configurable start months for alignment
- Timezone-aware date calculations
- Flexible interval configuration (days, weeks, months)

#### Seasonal Module

The seasonal module provides scheduling based on astronomical world seasons (spring, summer, fall, winter).

**Schedule Types Provided**:

- `seasonal` - World seasons based on equinoxes and solstices

**Configuration Schema**:

```json
{
    "timezone": "UTC",
    "hemisphere": "northern"
}
```

**Season Definitions** (Northern Hemisphere):

- Spring: March 20 - June 20
- Summer: June 21 - September 22
- Fall: September 23 - December 20
- Winter: December 21 - March 19

**Season Definitions** (Southern Hemisphere):

- Spring: September 23 - December 20
- Summer: December 21 - March 19
- Fall: March 20 - June 20
- Winter: June 21 - September 22

**Module Features**:

- Calculates season dates based on astronomical events
- Supports both Northern and Southern hemispheres
- Timezone-aware date calculations
- Automatic season name generation (e.g., "Spring 2024")

#### International Fixed Calendar Module

The International Fixed Calendar module provides scheduling based on a custom 28-day month calendar system.

**Schedule Types Provided**:

- `ifc_sched` - Custom 28-day month calendar system

**Configuration Schema**:

```json
{
    "month_length": 28,
    "months_per_season": 4,
    "special_month": 13,
    "new_years_day": true,
    "timezone": "UTC"
}
```

**Calendar Structure**:

- 13 months of 28 days = 364 days
- New Year's Day is separate (day 365)
- Seasons: Every 4 months (3 seasons of 4 months + 1 special month)
- New Year's Day: 1-day special seasonal event (badge awarding deferred)

**Module Features**:

- Calculates season dates based on 28-day month structure
- Handles the special 13th month
- Manages New Year's Day as a special event
- Timezone-aware date calculations
- Configurable month length and seasons per year

### Module Interface

Each schedule type module must implement the `ScheduleTypeProvider` interface:

```python
# app/schedule_types/base.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

class ScheduleTypeProvider(ABC):
    """Base class for schedule type provider modules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider module."""
        pass

    @property
    @abstractmethod
    def schedule_types(self) -> list[str]:
        """List of schedule type identifiers this module provides."""
        pass

    @abstractmethod
    def get_config_schema(self, schedule_type: str) -> dict[str, Any]:
        """Get the JSON schema for a specific schedule type.

        Args:
            schedule_type: The schedule type identifier

        Returns:
            JSON schema dict for the schedule type configuration
        """
        pass

    @abstractmethod
    def calculate_next_season(
        self,
        schedule_type: str,
        current_time: datetime,
        config: dict[str, Any],
    ) -> tuple[datetime, datetime]:
        """Calculate the start and end dates for the next season.

        Args:
            schedule_type: The schedule type identifier
            current_time: The current datetime
            config: The schedule configuration from the database

        Returns:
            A tuple of (start_date, end_date) for the next season
        """
        pass

    @abstractmethod
    def get_season_name(
        self,
        schedule_type: str,
        start_date: datetime,
        config: dict[str, Any],
    ) -> str:
        """Generate a name for the season based on its start date.

        Args:
            schedule_type: The schedule type identifier
            start_date: The start date of the season
            config: The schedule configuration from the database

        Returns:
            A human-readable name for the season
        """
        pass

    @abstractmethod
    def validate_config(
        self,
        schedule_type: str,
        config: dict[str, Any],
    ) -> bool:
        """Validate the schedule configuration.

        Args:
            schedule_type: The schedule type identifier
            config: The schedule configuration to validate

        Returns:
            True if the configuration is valid, False otherwise
        """
        pass
```

### Extending with Custom Modules

New schedule type modules can be created by implementing the `ScheduleTypeProvider` interface.

**Registering a Custom Module**

```python
# app/schedule_types/__init__.py
from app.schedule_types.manual import ManualScheduleProvider
from app.schedule_types.standard_calendar import StandardCalendarProvider
from app.schedule_types.seasonal import SeasonalScheduleProvider
from app.schedule_types.international_fixed_calendar import IFCScheduleProvider

# Registry of all available schedule type providers
SCHEDULE_PROVIDERS: dict[str, type[ScheduleTypeProvider]] = {
    "manual": ManualScheduleProvider,
    "standard_calendar": StandardCalendarProvider,
    "seasonal": SeasonalScheduleProvider,
    "ifc_sched": IFCScheduleProvider,
}

def get_schedule_provider(provider_name: str) -> ScheduleTypeProvider | None:
    """Get a schedule type provider instance by name."""
    provider_class = SCHEDULE_PROVIDERS.get(provider_name)
    if provider_class:
        return provider_class()
    return None

def get_provider_for_schedule_type(schedule_type: str) -> ScheduleTypeProvider | None:
    """Get the provider that handles a specific schedule type."""
    for provider_class in SCHEDULE_PROVIDERS.values():
        provider = provider_class()
        if schedule_type in provider.schedule_types:
            return provider
    return None
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

async def fetch_active_season_by_type() -> Season | None:
    """Fetch the active season for the configured active season type."""

async def fetch_non_active_seasons(
    active_season_type_id: int | None,
    current_time: datetime,
) -> list[Season]:
    """Fetch all seasons that are currently active but not the active season type."""

async def fetch_many(page: int | None = None, page_size: int | None = None) -> list[Season]: ...

async def partial_update(id: int, **kwargs) -> Season | None: ...

async def activate(id: int) -> Season | None: ...

async def deactivate(id: int) -> Season | None: ...

async def fetch_active_schedules() -> list[SeasonSchedule]:
    """Fetch all schedules that need checking for season transitions."""

async def create_schedule(
    name: str,
    schedule_type: str,
    config: dict[str, Any],
    description: str | None = None,
    is_default: bool = False,
) -> SeasonSchedule:
    """Create a new season schedule with validation."""

async def calculate_stats(season_id: int, user_id: int, mode: int) -> SeasonStat:
    """Calculate stats for a user in a season by aggregating scores."""

async def fetch_stats(season_id: int, user_id: int | None = None, mode: int | None = None) -> list[SeasonStat]: ...

async def fetch_seasons_containing_time(play_time: datetime) -> list[Season]: ...

async def update_season_stats(season_id: int) -> None:
    """Update stats for a season (used for periodic updates of non-active seasons)."""
```

### Modified Stats Repository

File: [`app/repositories/stats.py`](app/repositories/stats.py)

```python
# Add season_id parameter to all relevant functions
async def fetch_one(player_id: int, mode: int, season_id: int | None = None) -> Stat | None: ...

async def fetch_many(
    player_id: int | None = None,
    mode: int | None = None,
    season_id: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Stat]: ...

async def partial_update(
    player_id: int,
    mode: int,
    season_id: int | None = None,
    **kwargs
) -> Stat | None: ...

async def fetch_count(
    player_id: int | None = None,
    mode: int | None = None,
    season_id: int | None = None,
) -> int: ...
```

### Modified Scores Repository

File: [`app/repositories/scores.py`](app/repositories/scores.py)

```python
async def fetch_many(
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
    season_id: int | None = None,  # NEW
    page: int | None = None,
    page_size: int | None = None,
) -> list[Score]:
    # When season_id is provided, JOIN with seasons table and filter by play_time within date range
```

### Season Management Commands

File: [`app/commands.py`](app/commands.py)

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

@command(Privileges.UNRESTRICTED)
async def seasons(ctx: Context) -> str | None:
    """Toggle between all-time and seasonal view."""

@command(Privileges.UNRESTRICTED)
async def seasons_all(ctx: Context) -> str | None:
    """Switch to all-time view."""
```

### Background Tasks

File: [`app/bg_loops.py`](app/bg_loops.py)

```python
async def check_season_schedules(interval: int = 60) -> None:
    """Check and auto-start/end seasons based on schedule configuration.

    Args:
        interval: Check interval in seconds (default: 60 seconds)
    """
    while True:
        try:
            # Check if seasons are enabled via server_data
            seasons_enabled = await app.state.services.database.fetch_val(
                "SELECT value FROM server_data WHERE type = 'seasons_enabled'"
            )

            if seasons_enabled != '1':
                await asyncio.sleep(interval)
                continue

            # Get all schedules that need checking
            schedules = await seasons_repo.fetch_active_schedules()

            for schedule in schedules:
                # Get the provider for this schedule type
                provider = get_provider_for_schedule_type(schedule.schedule_type)
                if not provider:
                    log(
                        f"No provider found for schedule type: {schedule.schedule_type}",
                        Ansi.LRED,
                        level=logLevel.ERROR,
                    )
                    continue

                # Check if a new season should start
                current_time = datetime.now()
                start_date, end_date = provider.calculate_next_season(
                    schedule.schedule_type,
                    current_time,
                    schedule.config,
                )

                # Create new season if needed
                # ... (implementation details)

        except Exception as e:
            log(
                f"Error in check_season_schedules: {e}",
                Ansi.LRED,
                level=logLevel.ERROR,
            )

        await asyncio.sleep(interval)

async def update_non_active_season_stats(interval: int = 300) -> None:
    """Periodically update stats for non-active seasons.

    Args:
        interval: Update interval in seconds (default: 300 seconds / 5 minutes)
    """
    while True:
        try:
            seasons_enabled = await app.state.services.database.fetch_val(
                "SELECT value FROM server_data WHERE type = 'seasons_enabled'"
            )

            if seasons_enabled != '1':
                await asyncio.sleep(interval)
                continue

            # Get all seasons that are currently active (within their date range)
            # but are NOT the active season type
            active_season_type_id = await app.state.services.database.fetch_val(
                "SELECT value FROM server_data WHERE type = 'seasons_active_type_id'"
            )

            current_time = datetime.now()
            non_active_seasons = await seasons_repo.fetch_non_active_seasons(
                active_season_type_id=int(active_season_type_id) if active_season_type_id else None,
                current_time=current_time,
            )

            for season in non_active_seasons:
                # Skip seasons that have had their end calculation done
                if season.end_calculated:
                    continue

                # Update stats for this season with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        await seasons_repo.update_season_stats(season.id)
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            log(
                                f"Failed to update stats for season {season.id} after {max_retries} attempts: {e}",
                                Ansi.LRED,
                                level=logLevel.ERROR,
                            )
                        else:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff

        except Exception as e:
            log(
                f"Error in update_non_active_season_stats: {e}",
                Ansi.LRED,
                level=logLevel.ERROR,
            )

        await asyncio.sleep(interval)
```

**Error Handling Features**:

- Try-catch blocks around all database operations
- Retry logic with exponential backoff for failed season stat updates
- Comprehensive error logging with context
- Tasks continue running even if individual operations fail

**Configuration**: The intervals can be configured via `server_data`:

```sql
INSERT INTO server_data (type, value) VALUES ('seasons_check_interval', '60')
ON DUPLICATE KEY UPDATE value = '60';

INSERT INTO server_data (type, value) VALUES ('seasons_stats_update_interval', '300')
ON DUPLICATE KEY UPDATE value = '300';
```

### API Endpoints

**Non-Breaking Design**: All API changes are additive with optional parameters. Existing API consumers will continue to work without modification. New season-related parameters default to `None` (all-time stats) when not provided.

File: [`app/api/v2/seasons.py`](app/api/v2/seasons.py) (new file)

```python
@router.get("/seasons")
async def get_seasons(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Season]] | Failure: ...

@router.get("/seasons/{season_id}")
async def get_season(season_id: int) -> Success[Season] | Failure: ...

@router.get("/seasons/{season_id}/stats")
async def get_season_stats(
    season_id: int,
    mode: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[SeasonStats]] | Failure: ...
```

File: [`app/api/v2/players.py`](app/api/v2/players.py) (modified)

```python
@router.get("/players/{player_id}/stats/{mode}")
async def get_player_mode_stats(
    player_id: int,
    mode: int,
    season_id: int | None = None,  # NEW
) -> Success[PlayerStats] | Failure: ...

@router.get("/players/{player_id}/stats")
async def get_player_stats(
    player_id: int,
    season_id: int | None = None,  # NEW
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[PlayerStats]] | Failure: ...

@router.post("/players/{player_id}/season-preference")
async def update_season_preference(
    player_id: int,
    mode: str,  # "all_time" or "seasonal"
    season_id: int | None = None,
) -> Success[dict] | Failure: ...

@router.get("/players/{player_id}/season-preference")
async def get_season_preference(
    player_id: int,
) -> Success[dict] | Failure: ...
```

File: [`app/api/v2/scores.py`](app/api/v2/scores.py) (modified)

```python
@router.get("/scores")
async def get_all_scores(
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
    season_id: int | None = None,  # NEW
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Score]] | Failure: ...
```

### Pydantic Models

File: [`app/api/v2/models/seasons.py`](app/api/v2/models/seasons.py) (new file)

```python
class Season(BaseModel):
    id: int
    name: str
    schedule_id: int | None
    start_date: datetime
    end_date: datetime
    is_active: bool
    awards_badges: bool
    description: str | None
    created_at: datetime

class SeasonStats(BaseModel):
    season_id: int
    user_id: int
    mode: int
    tscore: int
    rscore: int
    pp: float
    plays: int
    playtime: int
    acc: float
    max_combo: int
    total_hits: int
    replay_views: int
    xh_count: int
    x_count: int
    sh_count: int
    s_count: int
    a_count: int

class SeasonInfo(BaseModel):
    id: int
    name: str
    type: str
    start_date: datetime
    end_date: datetime
```

File: [`app/api/v2/models/scores.py`](app/api/v2/models/scores.py) (modified)

```python
class Score(BaseModel):
    # ... existing fields ...
    season: SeasonInfo | None = None  # NEW
```

## Implementation Steps

### Phase 1: Database Schema & Migration

1. Create migration entry in `migrations/migrations.sql` with version comment `# 5.3.2`
2. Create `season_schedules` table
3. Create `seasons` table (with `end_calculated` field)
4. Create `season_config` table
5. Modify `stats` table to add `season_id` column (nullable with unique constraint)
6. Modify `users` table to add `preferred_lb_view` column
7. Add recommended indexes for performance
8. Insert default `server_data` entries for seasons configuration

### Phase 2: Schedule Type Provider System

1. Create `app/schedule_types/` directory
2. Create [`app/schedule_types/__init__.py`](app/schedule_types/__init__.py) with provider registry and helper functions
3. Create [`app/schedule_types/base.py`](app/schedule_types/base.py) with `ScheduleTypeProvider` abstract base class
4. Create built-in schedule type provider modules:
   - [`app/schedule_types/manual.py`](app/schedule_types/manual.py) - Manual season management
   - [`app/schedule_types/standard_calendar.py`](app/schedule_types/standard_calendar.py) - Standard calendar methods (custom, half_year, third_year, quarter_year)
   - [`app/schedule_types/seasonal.py`](app/schedule_types/seasonal.py) - World seasons (spring, summer, fall, winter)
   - [`app/schedule_types/international_fixed_calendar.py`](app/schedule_types/international_fixed_calendar.py) - International Fixed Calendar system
5. Implement `get_schedule_provider()` function for retrieving provider instances
6. Implement `get_provider_for_schedule_type()` function for finding providers by schedule type
7. Add configuration validation logic using provider schemas

### Phase 3: Repository Layer

1. Create [`app/repositories/seasons.py`](app/repositories/seasons.py)
2. Update [`app/repositories/stats.py`](app/repositories/stats.py) for season support
3. Update [`app/repositories/scores.py`](app/repositories/scores.py) for season filtering

### Phase 4: API Layer

1. Create [`app/api/v2/seasons.py`](app/api/v2/seasons.py)
2. Update [`app/api/v2/players.py`](app/api/v2/players.py) with season parameters
3. Update [`app/api/v2/scores.py`](app/api/v2/scores.py) with season filtering
4. Create [`app/api/v2/models/seasons.py`](app/api/v2/models/seasons.py)
5. Update [`app/api/v2/models/scores.py`](app/api/v2/models/scores.py) with season info

### Phase 5: Background Tasks & State Management

1. Add `check_season_schedules()` task to [`app/bg_loops.py`](app/bg_loops.py) with schedule type handler integration
2. Add `update_non_active_season_stats()` task to [`app/bg_loops.py`](app/bg_loops.py)
3. Add season preference to player object in [`app/objects/player.py`](app/objects/player.py)

### Phase 6: Commands

1. Add season management commands to [`app/commands.py`](app/commands.py)
2. Add command visibility check based on `seasons_enabled` server_data

### Phase 7: Integration

1. Update score submission logic in [`app/api/domains/osu.py`](app/api/domains/osu.py) to only update active season stats
2. Update player profile display in [`app/objects/player.py`](app/objects/player.py)
3. Add season-aware leaderboard caching (Redis) for all-time and active season
4. Update leaderboard queries to respect player's season preference

### Phase 8: Testing (Future Implementation)

**Note**: Comprehensive testing will be handled in a separate phase after core implementation is complete.

**Test areas to cover**:

- All schedule types work correctly
- International Fixed Calendar calculates correctly
- Season stats aggregate correctly
- Leaderboard filtering by season works
- Background task auto-starts/ends seasons
- Only one active season type at a time
- All season types are viewable even when not active
- Seasons can be enabled/disabled via server_data
- API endpoints work with and without season_id
- Commands are hidden when seasons disabled
- Performance is acceptable with season filtering
- Player can toggle between all-time and seasonal views
- Player preference persists across sessions
- Default display mode is configurable via server_data
- Migration applies correctly on version change
- Score submission only updates active season stats
- Non-active seasons updated periodically via background task
- Score during transition counts for correct season
- API responses include season information when enabled
- Indexes improve query performance for season filtering
- Season stat update failures don't fail score submission
- Leaderboard stats are cached in Redis with TTL
- Background task intervals are configurable

**Test files to create** (when testing phase begins):

- `tests/unit/test_seasons.py` - Unit tests for season logic
- `tests/integration/test_seasons_api.py` - Integration tests for API endpoints
- `tests/integration/test_seasons_stats.py` - Integration tests for stat updates
- Modify existing tests in `tests/` to include season parameters
