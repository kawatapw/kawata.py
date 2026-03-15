# Clans Overhaul Plan

## Overview
Expand the basic clans system into a full-featured clan system with management features, stats tracking, and clan wars.

## Key Design Decisions
- **No separate score table for wars**: Filter existing scores by clan members during war timeframe
- **Smart stats aggregation**: Real-time updates with batching when activity exceeds threshold
- **Configurable max members**: Default 10, can be increased with donations
- **Clan roles**: Owner, Officer, Member with different permissions
- **Clan cosmetics**: Clans can have their own cosmetics that members can display

## Database Schema

### Modifications to clans Table
```sql
ALTER TABLE clans
    ADD COLUMN description TEXT DEFAULT NULL AFTER owner,
    ADD COLUMN icon VARCHAR(1024) DEFAULT NULL AFTER description,
    ADD COLUMN banner VARCHAR(1024) DEFAULT NULL AFTER icon,
    ADD COLUMN background VARCHAR(1024) DEFAULT NULL AFTER banner,
    ADD COLUMN flag VARCHAR(1024) DEFAULT NULL AFTER background,
    ADD COLUMN max_members INT NOT NULL DEFAULT 10 AFTER flag,
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE AFTER max_members,
    MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP;
```

### clan_stats Table
```sql
CREATE TABLE clan_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clan_id INT NOT NULL,
    mode TINYINT NOT NULL,
    total_pp BIGINT UNSIGNED NOT NULL DEFAULT 0,
    total_score BIGINT UNSIGNED NOT NULL DEFAULT 0,
    total_plays INT UNSIGNED NOT NULL DEFAULT 0,
    avg_acc FLOAT(6,3) NOT NULL DEFAULT 0.000,
    member_count INT UNSIGNED NOT NULL DEFAULT 0,
    last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_clan_mode (clan_id, mode),
    INDEX idx_clan_id (clan_id),
    INDEX idx_mode (mode),
    INDEX idx_total_pp (total_pp),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### clan_season_stats Table
```sql
CREATE TABLE clan_season_stats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clan_id INT NOT NULL,
    season_id INT NOT NULL,
    mode TINYINT NOT NULL,
    total_pp BIGINT UNSIGNED NOT NULL DEFAULT 0,
    total_score BIGINT UNSIGNED NOT NULL DEFAULT 0,
    total_plays INT UNSIGNED NOT NULL DEFAULT 0,
    avg_acc FLOAT(6,3) NOT NULL DEFAULT 0.000,
    member_count INT UNSIGNED NOT NULL DEFAULT 0,
    last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_clan_season_mode (clan_id, season_id, mode),
    INDEX idx_clan_id (clan_id),
    INDEX idx_season_id (season_id),
    INDEX idx_mode (mode),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### clan_invites Table
```sql
CREATE TABLE clan_invites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clan_id INT NOT NULL,
    user_id INT NOT NULL,
    invited_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'accepted', 'rejected') NOT NULL DEFAULT 'pending',
    UNIQUE KEY idx_clan_user (clan_id, user_id),
    INDEX idx_clan_id (clan_id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (invited_by) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### clan_join_requests Table
```sql
CREATE TABLE clan_join_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clan_id INT NOT NULL,
    user_id INT NOT NULL,
    message VARCHAR(512) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'accepted', 'rejected') NOT NULL DEFAULT 'pending',
    UNIQUE KEY idx_clan_user (clan_id, user_id),
    INDEX idx_clan_id (clan_id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### clan_wars Table
```sql
CREATE TABLE clan_wars (
    id INT AUTO_INCREMENT PRIMARY KEY,
    challenger_clan_id INT NOT NULL,
    defender_clan_id INT NOT NULL,
    map_id INT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    status ENUM('pending', 'active', 'completed', 'cancelled') NOT NULL DEFAULT 'pending',
    winner_clan_id INT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_challenger (challenger_clan_id),
    INDEX idx_defender (defender_clan_id),
    INDEX idx_map_id (map_id),
    INDEX idx_status (status),
    INDEX idx_start_time (start_time),
    INDEX idx_end_time (end_time),
    FOREIGN KEY (challenger_clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (defender_clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (winner_clan_id) REFERENCES clans(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### clan_war_results Table
```sql
CREATE TABLE clan_war_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    war_id INT NOT NULL,
    clan_id INT NOT NULL,
    total_score BIGINT UNSIGNED NOT NULL DEFAULT 0,
    avg_acc FLOAT(6,3) NOT NULL DEFAULT 0.000,
    best_score BIGINT UNSIGNED NOT NULL DEFAULT 0,
    participant_count INT UNSIGNED NOT NULL DEFAULT 0,
    UNIQUE KEY idx_war_clan (war_id, clan_id),
    INDEX idx_war_id (war_id),
    INDEX idx_clan_id (clan_id),
    FOREIGN KEY (war_id) REFERENCES clan_wars(id) ON DELETE CASCADE,
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## Clan Roles

### Role Hierarchy
- **Owner** (3): Full control, can disband clan, transfer ownership
- **Officer** (2): Can invite/kick members, manage settings
- **Member** (1): Basic membership

### Role Permissions
```python
class ClanPermissions:
    INVITE_MEMBERS = [ClanPrivileges.Owner, ClanPrivileges.Officer]
    KICK_MEMBERS = [ClanPrivileges.Owner, ClanPrivileges.Officer]
    MANAGE_SETTINGS = [ClanPrivileges.Owner, ClanPrivileges.Officer]
    DISBAND_CLAN = [ClanPrivileges.Owner]
    TRANSFER_OWNERSHIP = [ClanPrivileges.Owner]
    VIEW_WAR_HISTORY = [ClanPrivileges.Owner, ClanPrivileges.Officer, ClanPrivileges.Member]
```

## Code Changes

### Repository Updates
File: [`app/repositories/clans.py`](app/repositories/clans.py)

**New Functions:**
```python
async def create(
    name: str,
    tag: str,
    owner: int,
    description: str | None = None,
    icon: str | None = None,
    banner: str | None = None,
    background: str | None = None,
    flag: str | None = None,
    max_members: int = 10,
) -> Clan: ...

async def fetch_one(id: int | None = None, name: str | None = None, tag: str | None = None, owner: int | None = None) -> Clan | None: ...

async def fetch_many(page: int | None = None, page_size: int | None = None) -> list[Clan]: ...

async def partial_update(id: int, **kwargs) -> Clan | None: ...

async def delete_one(id: int) -> Clan | None: ...

# Clan Stats
async def calculate_stats(clan_id: int, mode: int) -> ClanStat: ...
async def fetch_stats(clan_id: int, mode: int | None = None) -> list[ClanStat]: ...
async def update_stats(clan_id: int) -> None: ...  # Smart batching

# Clan Invites
async def create_invite(clan_id: int, user_id: int, invited_by: int) -> ClanInvite: ...
async def fetch_invite(id: int | None = None, clan_id: int | None = None, user_id: int | None = None) -> ClanInvite | None: ...
async def accept_invite(id: int) -> ClanInvite | None: ...
async def reject_invite(id: int) -> ClanInvite | None: ...

# Clan Join Requests
async def create_join_request(clan_id: int, user_id: int, message: str | None = None) -> ClanJoinRequest: ...
async def fetch_join_request(id: int | None = None, clan_id: int | None = None, user_id: int | None = None) -> ClanJoinRequest | None: ...
async def accept_join_request(id: int) -> ClanJoinRequest | None: ...
async def reject_join_request(id: int) -> ClanJoinRequest | None: ...

# Clan Wars
async def create_war(challenger_clan_id: int, defender_clan_id: int, map_id: int, start_time: datetime, end_time: datetime) -> ClanWar: ...
async def fetch_war(id: int | None = None, clan_id: int | None = None, status: str | None = None) -> ClanWar | None: ...
async def accept_war(id: int) -> ClanWar | None: ...
async def decline_war(id: int) -> ClanWar | None: ...
async def calculate_war_results(war_id: int) -> list[ClanWarResult]: ...
async def fetch_war_scores(war_id: int, clan_id: int) -> list[Score]: ...  # Filter existing scores
```

### Commands
```python
# Clan Management
@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_invite(ctx: Context) -> str | None:
    """Invite a player to your clan."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_kick(ctx: Context) -> str | None:
    """Kick a member from your clan."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_promote(ctx: Context) -> str | None:
    """Promote a member to officer."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_demote(ctx: Context) -> str | None:
    """Demote an officer to member."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_settings(ctx: Context) -> str | None:
    """Manage clan settings (description, icons, etc.)."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_requests(ctx: Context) -> str | None:
    """View pending join requests."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_accept(ctx: Context) -> str | None:
    """Accept a join request."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_reject(ctx: Context) -> str | None:
    """Reject a join request."""

# Clan Wars
@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_war_challenge(ctx: Context) -> str | None:
    """Challenge another clan to a war."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_war_accept(ctx: Context) -> str | None:
    """Accept a war challenge."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_war_decline(ctx: Context) -> str | None:
    """Decline a war challenge."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_war_status(ctx: Context) -> str | None:
    """View current war status."""

@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_war_history(ctx: Context) -> str | None:
    """View war history."""
```

### Background Task
```python
# In app/bg_loops.py
async def update_clan_stats() -> None:
    """Update clan stats with smart batching."""
    # Runs every 5 minutes
    # Checks activity threshold
    # Batches updates if activity > threshold
    # Updates clan_stats and clan_season_stats
```

## Implementation Steps

1. **Expand clans table**
   - Add new columns to clans table
   - Create clan_stats table
   - Create clan_season_stats table

2. **Create invite/request system**
   - Create clan_invites table
   - Create clan_join_requests table
   - Implement invite/request logic

3. **Implement clan roles**
   - Define role hierarchy
   - Implement permission checks
   - Update existing commands

4. **Create clan wars**
   - Create clan_wars table
   - Create clan_war_results table
   - Implement war challenge system
   - Implement score filtering for wars

5. **Implement stats aggregation**
   - Create smart batching system
   - Implement real-time updates
   - Add background task

6. **Create commands**
   - Implement all clan management commands
   - Implement clan war commands

## Testing Checklist
- [ ] Clan creation with new fields works
- [ ] Invite system works correctly
- [ ] Join request system works correctly
- [ ] Role permissions enforced correctly
- [ ] Clan wars can be created and completed
- [ ] War scores filtered correctly
- [ ] Stats aggregation works with batching
- [ ] Max members enforced
- [ ] Donation-based upgrades work
