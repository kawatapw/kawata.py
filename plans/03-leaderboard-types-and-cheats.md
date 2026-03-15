# Leaderboard Types & Cheat System Plan

## Overview
Implement a multi-leaderboard system with different restriction types (Cheats, Legit, No Timewarp, No Aim Assist) and a comprehensive cheat definition system that allows per-season rule overrides.

## Key Design Decisions
- **Leaderboard types**: Different leaderboards with specific mod/cheat restrictions
- **Cheat definitions**: Formal system for defining cheats with versions and configurations
- **Season-specific rules**: Cheat rules can be overridden per season
- **Score validation**: Scores validated against leaderboard type restrictions
- **Passive filtering**: Scores submitted normally, filtered based on restrictions

## Database Schema

### leaderboard_types Table
```sql
CREATE TABLE leaderboard_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(32) NOT NULL,
    description VARCHAR(256) DEFAULT NULL,
    mod_restrictions JSON DEFAULT NULL COMMENT 'JSON object defining mod restrictions',
    cheat_restrictions JSON DEFAULT NULL COMMENT 'JSON object defining cheat restrictions',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### Pre-populated Data
```sql
INSERT INTO leaderboard_types (name, description, mod_restrictions, cheat_restrictions, is_default) VALUES
('Cheats', 'Default leaderboard with no restrictions', NULL, NULL, TRUE),
('Legit', 'No cheats allowed', NULL, '{"allow_cheats": false}', FALSE),
('No Timewarp', 'Timewarp disabled', '{"disallow_mods": ["TIMWARP"]}', NULL, FALSE),
('No Aim Assist', 'Aim assist disabled', NULL, '{"disallow_cheats": ["AIM_ASSIST"]}', FALSE);
```

### cheat_definitions Table
```sql
CREATE TABLE cheat_definitions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    category ENUM('timewarp', 'aimassist', 'relax', 'autopilot', 'flashlight', 'other') NOT NULL,
    description VARCHAR(256) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### cheat_versions Table
```sql
CREATE TABLE cheat_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cheat_id INT NOT NULL,
    version_name VARCHAR(32) NOT NULL,
    client_identifier VARCHAR(64) NOT NULL COMMENT 'Identifier for the client implementation',
    default_config JSON NOT NULL COMMENT 'Default configuration values for this version',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_cheat_version (cheat_id, version_name),
    INDEX idx_cheat_id (cheat_id),
    INDEX idx_client_identifier (client_identifier),
    FOREIGN KEY (cheat_id) REFERENCES cheat_definitions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### season_cheat_rules Table
```sql
CREATE TABLE season_cheat_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    season_id INT NOT NULL,
    cheat_id INT NOT NULL,
    allowed BOOLEAN NOT NULL DEFAULT TRUE,
    min_value DECIMAL(10,4) DEFAULT NULL COMMENT 'Minimum allowed value',
    max_value DECIMAL(10,4) DEFAULT NULL COMMENT 'Maximum allowed value',
    config_overrides JSON DEFAULT NULL COMMENT 'Season-specific config overrides',
    UNIQUE KEY idx_season_cheat (season_id, cheat_id),
    INDEX idx_season_id (season_id),
    INDEX idx_cheat_id (cheat_id),
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
    FOREIGN KEY (cheat_id) REFERENCES cheat_definitions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### Modifications to scores Table
```sql
ALTER TABLE scores
    ADD COLUMN leaderboard_type_id INT NOT NULL DEFAULT 1 AFTER userid,
    ADD INDEX idx_leaderboard_type_id (leaderboard_type_id),
    ADD FOREIGN KEY (leaderboard_type_id) REFERENCES leaderboard_types(id) ON DELETE RESTRICT;
```

## Restriction Format

### Mod Restrictions
```json
{
    "disallow_mods": ["TIMWARP", "FLASHLIGHT"],
    "allow_mods": ["HIDDEN", "HARDROCK"]
}
```

### Cheat Restrictions
```json
{
    "allow_cheats": false,
    "disallow_cheats": ["AIM_ASSIST", "TIMWARP"],
    "max_timewarp_percent": 100,
    "max_aim_assist_strength": 0
}
```

## Code Changes

### New Repository
File: [`app/repositories/leaderboard_types.py`](app/repositories/leaderboard_types.py)

```python
async def create(
    name: str,
    description: str | None = None,
    mod_restrictions: dict | None = None,
    cheat_restrictions: dict | None = None,
    is_default: bool = False,
) -> LeaderboardType: ...

async def fetch_one(id: int | None = None, name: str | None = None, is_default: bool | None = None) -> LeaderboardType | None: ...

async def fetch_default() -> LeaderboardType | None: ...

async def fetch_many() -> list[LeaderboardType]: ...

async def validate_score(leaderboard_type_id: int, mods: int, cheat_values: dict | None) -> bool: ...
```

### New Repository
File: [`app/repositories/cheats.py`](app/repositories/cheats.py)

```python
# Cheat Definitions
async def create_definition(name: str, category: str, description: str | None = None) -> CheatDefinition: ...
async def fetch_definition(id: int | None = None, name: str | None = None) -> CheatDefinition | None: ...
async def fetch_definitions(category: str | None = None) -> list[CheatDefinition]: ...

# Cheat Versions
async def create_version(cheat_id: int, version_name: str, client_identifier: str, default_config: dict) -> CheatVersion: ...
async def fetch_versions(cheat_id: int) -> list[CheatVersion]: ...

# Season Cheat Rules
async def create_rule(season_id: int, cheat_id: int, allowed: bool = True, min_value: float | None = None, max_value: float | None = None, config_overrides: dict | None = None) -> SeasonCheatRule: ...
async def fetch_rules(season_id: int) -> list[SeasonCheatRule]: ...
async def get_effective_config(season_id: int, cheat_id: int) -> dict: ...
```

### Score Validation
```python
# In app/repositories/scores.py
async def validate_for_leaderboard(
    leaderboard_type_id: int,
    mods: int,
    cheat_values: dict | None,
    season_id: int | None = None,
) -> tuple[bool, str | None]:
    """Validate score against leaderboard type restrictions."""
    # Check mod restrictions
    # Check cheat restrictions
    # Check season-specific cheat rules
    # Return (is_valid, reason)
```

### Commands
```python
@command(Privileges.UNRESTRICTED)
async def leaderboard_list(ctx: Context) -> str | None:
    """List all available leaderboard types."""

@command(Privileges.UNRESTRICTED)
async def leaderboard_info(ctx: Context) -> str | None:
    """Show info about a specific leaderboard type."""
```

## Implementation Steps

1. **Create database tables**
   - Create `leaderboard_types` table
   - Pre-populate with default types
   - Create `cheat_definitions` table
   - Create `cheat_versions` table
   - Create `season_cheat_rules` table
   - Add `leaderboard_type_id` to `scores` table

2. **Create repositories**
   - Create [`app/repositories/leaderboard_types.py`](app/repositories/leaderboard_types.py)
   - Create [`app/repositories/cheats.py`](app/repositories/cheats.py)

3. **Implement score validation**
   - Add validation logic for leaderboard types
   - Integrate with score submission
   - Add season-specific cheat rule checking

4. **Create commands**
   - Implement leaderboard list/info commands
   - Add cheat management commands (admin)

5. **Integrate with API**
   - Add leaderboard type filtering to score endpoints
   - Add cheat definition management endpoints

## Testing Checklist
- [ ] Leaderboard types created correctly
- [ ] Score validation works for each type
- [ ] Cheat definitions can be created/managed
- [ ] Season cheat rules override defaults
- [ ] Scores rejected when violating restrictions
- [ ] Leaderboard filtering works correctly
