# Score Hunts System Plan

## Overview
Implement a passive score hunt system where scores submitted normally are filtered based on hunt conditions to determine winners.

## Key Design Decisions
- **Passive tracking**: Scores submitted normally, filtered for hunt conditions
- **Multiple concurrent hunts**: Configurable max per mode (e.g., 3-5 active hunts)
- **Restriction-based**: Mods, cheats, timewarp, aim assist limits
- **Point system**: 1st place = 3pts, 2nd = 2pts, 3rd = 1pt
- **Retroactive filtering**: Winners determined by filtering existing scores
- **Badge rewards**: Winners receive cosmetic badges

## Database Schema

### score_hunts Table
```sql
CREATE TABLE score_hunts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(512) DEFAULT NULL,
    map_id INT NOT NULL,
    mode TINYINT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    status ENUM('draft', 'active', 'completed', 'cancelled') NOT NULL DEFAULT 'draft',
    max_participants INT DEFAULT NULL COMMENT 'NULL means unlimited',
    created_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_map_id (map_id),
    INDEX idx_mode (mode),
    INDEX idx_status (status),
    INDEX idx_start_time (start_time),
    INDEX idx_end_time (end_time),
    INDEX idx_created_by (created_by),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### score_hunt_restrictions Table
```sql
CREATE TABLE score_hunt_restrictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hunt_id INT NOT NULL,
    restriction_type ENUM('mod', 'cheat', 'timewarp', 'aimassist', 'custom') NOT NULL,
    restriction_value VARCHAR(128) NOT NULL COMMENT 'Value for the restriction (e.g., mod name, cheat type)',
    is_allowed BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'TRUE = allowed, FALSE = disallowed',
    INDEX idx_hunt_id (hunt_id),
    INDEX idx_restriction_type (restriction_type),
    FOREIGN KEY (hunt_id) REFERENCES score_hunts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### score_hunt_submissions Table
```sql
CREATE TABLE score_hunt_submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hunt_id INT NOT NULL,
    user_id INT NOT NULL,
    score_id BIGINT UNSIGNED NOT NULL,
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    validation_notes VARCHAR(256) DEFAULT NULL,
    INDEX idx_hunt_id (hunt_id),
    INDEX idx_user_id (user_id),
    INDEX idx_score_id (score_id),
    INDEX idx_is_valid (is_valid),
    FOREIGN KEY (hunt_id) REFERENCES score_hunts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (score_id) REFERENCES scores(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### score_hunt_results Table
```sql
CREATE TABLE score_hunt_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hunt_id INT NOT NULL,
    user_id INT NOT NULL,
    placement INT NOT NULL COMMENT '1=1st, 2=2nd, 3=3rd',
    score_value BIGINT UNSIGNED NOT NULL,
    points_awarded INT NOT NULL DEFAULT 0,
    awarded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_hunt_placement (hunt_id, placement),
    INDEX idx_hunt_id (hunt_id),
    INDEX idx_user_id (user_id),
    FOREIGN KEY (hunt_id) REFERENCES score_hunts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### score_hunt_points Table
```sql
CREATE TABLE score_hunt_points (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    total_points INT NOT NULL DEFAULT 0,
    season_id INT DEFAULT NULL,
    last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_user_season (user_id, season_id),
    INDEX idx_user_id (user_id),
    INDEX idx_season_id (season_id),
    INDEX idx_total_points (total_points),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## Restriction Types

### Mod Restrictions
```json
{
    "restriction_type": "mod",
    "restriction_value": "HIDDEN",
    "is_allowed": true
}
```

### Cheat Restrictions
```json
{
    "restriction_type": "cheat",
    "restriction_value": "TIMWARP",
    "is_allowed": false
}
```

### Timewarp Restrictions
```json
{
    "restriction_type": "timewarp",
    "restriction_value": "120",
    "is_allowed": true
}
```

### Aim Assist Restrictions
```json
{
    "restriction_type": "aimassist",
    "restriction_value": "0",
    "is_allowed": true
}
```

## Code Changes

### New Repository
File: [`app/repositories/score_hunts.py`](app/repositories/score_hunts.py)

```python
# Hunts
async def create_hunt(
    name: str,
    description: str,
    map_id: int,
    mode: int,
    start_time: datetime,
    end_time: datetime,
    created_by: int,
    max_participants: int | None = None,
) -> ScoreHunt: ...
async def fetch_hunt(
    id: int | None = None, status: str | None = None, mode: int | None = None
) -> ScoreHunt | None: ...
async def fetch_active_hunts(mode: int | None = None) -> list[ScoreHunt]: ...
async def fetch_hunts(
    page: int | None = None, page_size: int | None = None
) -> list[ScoreHunt]: ...
async def update_hunt_status(id: int, status: str) -> ScoreHunt | None: ...


# Restrictions
async def add_restriction(
    hunt_id: int, restriction_type: str, restriction_value: str, is_allowed: bool = True
) -> ScoreHuntRestriction: ...
async def fetch_restrictions(hunt_id: int) -> list[ScoreHuntRestriction]: ...
async def validate_score(
    hunt_id: int, mods: int, cheat_values: dict | None
) -> tuple[bool, str | None]: ...


# Submissions
async def record_submission(
    hunt_id: int,
    user_id: int,
    score_id: int,
    is_valid: bool = True,
    validation_notes: str | None = None,
) -> ScoreHuntSubmission: ...
async def fetch_submissions(
    hunt_id: int, user_id: int | None = None, is_valid: bool | None = None
) -> list[ScoreHuntSubmission]: ...


# Results
async def record_result(
    hunt_id: int, user_id: int, placement: int, score_value: int, points_awarded: int
) -> ScoreHuntResult: ...
async def fetch_results(hunt_id: int) -> list[ScoreHuntResult]: ...
async def determine_winners(hunt_id: int) -> list[ScoreHuntResult]: ...


# Points
async def award_points(
    user_id: int, points: int, season_id: int | None = None
) -> None: ...
async def fetch_points(user_id: int, season_id: int | None = None) -> int: ...
async def fetch_leaderboard(
    season_id: int | None = None, limit: int = 10
) -> list[dict]: ...
```

### Commands
```python
@command(Privileges.ADMINISTRATOR)
async def hunt_create(ctx: Context) -> str | None:
    """Create a new score hunt."""


@command(Privileges.ADMINISTRATOR)
async def hunt_start(ctx: Context) -> str | None:
    """Start a score hunt."""


@command(Privileges.ADMINISTRATOR)
async def hunt_end(ctx: Context) -> str | None:
    """End a score hunt and determine winners."""


@command(Privileges.UNRESTRICTED)
async def hunt_list(ctx: Context) -> str | None:
    """List active score hunts."""


@command(Privileges.UNRESTRICTED)
async def hunt_info(ctx: Context) -> str | None:
    """Show info about a score hunt."""


@command(Privileges.UNRESTRICTED)
async def hunt_leaderboard(ctx: Context) -> str | None:
    """Show score hunt leaderboard."""
```

### Background Task
```python
# In app/bg_loops.py
async def process_score_hunts() -> None:
    """Process score hunts - identify valid submissions and determine winners."""
    # Runs every 5 minutes
    # Finds active hunts
    # Identifies valid score submissions
    # Records submissions
    # For ended hunts, determines winners
    # Awards points and badges
```

## Score Validation Logic

```python
async def validate_score_for_hunt(
    hunt_id: int, score: Score
) -> tuple[bool, str | None]:
    """Validate a score against hunt restrictions."""
    restrictions = await fetch_restrictions(hunt_id)

    for restriction in restrictions:
        if restriction["restriction_type"] == "mod":
            if restriction["is_allowed"]:
                if not (score.mods & get_mod_value(restriction["restriction_value"])):
                    return False, f"Mod {restriction['restriction_value']} required"
            else:
                if score.mods & get_mod_value(restriction["restriction_value"]):
                    return False, f"Mod {restriction['restriction_value']} not allowed"

        elif restriction["restriction_type"] == "cheat":
            cheat_values = get_cheat_values(score)
            if restriction["is_allowed"]:
                if restriction["restriction_value"] not in cheat_values:
                    return False, f"Cheat {restriction['restriction_value']} required"
            else:
                if restriction["restriction_value"] in cheat_values:
                    return (
                        False,
                        f"Cheat {restriction['restriction_value']} not allowed",
                    )

        # ... other restriction types

    return True, None
```

## Implementation Steps

1. **Create database tables**
   - Create score_hunts table
   - Create score_hunt_restrictions table
   - Create score_hunt_submissions table
   - Create score_hunt_results table
   - Create score_hunt_points table

2. **Create repository**
   - Create [`app/repositories/score_hunts.py`](app/repositories/score_hunts.py)
   - Implement all CRUD operations

3. **Implement score validation**
   - Create restriction validation logic
   - Integrate with score submission

4. **Create background task**
   - Implement passive score tracking
   - Implement winner determination
   - Implement point awarding

5. **Create commands**
   - Implement hunt management commands
   - Implement hunt info/leaderboard commands

6. **Integrate with cosmetics**
   - Create hunt winner badges
   - Implement badge awarding

## Testing Checklist
- [ ] Hunts can be created with restrictions
- [ ] Score validation works correctly
- [ ] Valid submissions are identified
- [ ] Winners determined correctly
- [ ] Points awarded correctly
- [ ] Badges awarded to winners
- [ ] Multiple concurrent hunts work
- [ ] Hunt status transitions work
- [ ] Leaderboard displays correctly
