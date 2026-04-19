# Cosmetics System Plan

## Overview
Implement a flexible, property-based cosmetics system that supports multiple cosmetic types across user, clan, and system scopes.

## Key Design Decisions
- **Property-based system**: Cosmetics defined by key-value properties, not hardcoded types
- **Three scopes**: User, Clan, and System cosmetics
- **External storage**: All images stored as URLs (external storage)
- **User opt-out**: Users can opt out of system cosmetics
- **Clan cosmetics**: Enabled by default, users choose which to display
- **Condition-based assignment**: Cosmetics unlocked based on conditions (donate, win hunt, etc.)

## Database Schema

### cosmetic_categories Table
```sql
CREATE TABLE cosmetic_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(32) NOT NULL COMMENT 'badge/overlay/username_style/banner/avatar_frame/profile_background/effect',
    render_type ENUM('html', 'css', 'image', 'animation') NOT NULL,
    owner_type ENUM('user', 'clan', 'system') NOT NULL COMMENT 'Who can own this cosmetic type',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### Pre-populated Categories
```sql
INSERT INTO cosmetic_categories (name, render_type, owner_type) VALUES
('badge', 'image', 'user'),
('overlay', 'animation', 'system'),
('username_style', 'css', 'user'),
('banner', 'image', 'user'),
('avatar_frame', 'image', 'user'),
('profile_background', 'image', 'user'),
('effect', 'animation', 'system'),
('clan_badge', 'image', 'clan'),
('clan_banner', 'image', 'clan'),
('clan_background', 'image', 'clan');
```

### cosmetics Table
```sql
CREATE TABLE cosmetics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(256) DEFAULT NULL,
    rarity ENUM('common', 'uncommon', 'rare', 'epic', 'legendary') NOT NULL DEFAULT 'common',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category_id (category_id),
    INDEX idx_rarity (rarity),
    INDEX idx_is_active (is_active),
    FOREIGN KEY (category_id) REFERENCES cosmetic_categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### cosmetic_properties Table
```sql
CREATE TABLE cosmetic_properties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cosmetic_id INT NOT NULL,
    property_key VARCHAR(64) NOT NULL COMMENT 'e.g., image_url, css_class, animation, color, font',
    property_value TEXT NOT NULL,
    property_type ENUM('string', 'int', 'bool', 'css', 'url') NOT NULL DEFAULT 'string',
    UNIQUE KEY idx_cosmetic_key (cosmetic_id, property_key),
    INDEX idx_cosmetic_id (cosmetic_id),
    FOREIGN KEY (cosmetic_id) REFERENCES cosmetics(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### user_cosmetics Table
```sql
CREATE TABLE user_cosmetics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    cosmetic_id INT NOT NULL,
    source ENUM('donation', 'event', 'achievement', 'manual', 'scorehunt', 'season') NOT NULL,
    acquired_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_user_cosmetic (user_id, cosmetic_id),
    INDEX idx_user_id (user_id),
    INDEX idx_cosmetic_id (cosmetic_id),
    INDEX idx_source (source),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (cosmetic_id) REFERENCES cosmetics(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### user_equipped_cosmetics Table
```sql
CREATE TABLE user_equipped_cosmetics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    cosmetic_id INT NOT NULL,
    slot VARCHAR(32) NOT NULL COMMENT 'badge_1, badge_2, overlay, banner, avatar_frame, profile_background, username_style',
    equipped_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_user_slot (user_id, slot),
    INDEX idx_user_id (user_id),
    INDEX idx_cosmetic_id (cosmetic_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (cosmetic_id) REFERENCES cosmetics(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### clan_cosmetics Table
```sql
CREATE TABLE clan_cosmetics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clan_id INT NOT NULL,
    cosmetic_id INT NOT NULL,
    acquired_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_clan_cosmetic (clan_id, cosmetic_id),
    INDEX idx_clan_id (clan_id),
    INDEX idx_cosmetic_id (cosmetic_id),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (cosmetic_id) REFERENCES cosmetics(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### clan_equipped_cosmetics Table
```sql
CREATE TABLE clan_equipped_cosmetics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clan_id INT NOT NULL,
    cosmetic_id INT NOT NULL,
    slot VARCHAR(32) NOT NULL COMMENT 'badge, banner, background, icon, flag',
    equipped_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_clan_slot (clan_id, slot),
    INDEX idx_clan_id (clan_id),
    INDEX idx_cosmetic_id (cosmetic_id),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (cosmetic_id) REFERENCES cosmetics(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### system_cosmetics Table
```sql
CREATE TABLE system_cosmetics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cosmetic_id INT NOT NULL,
    start_date DATETIME NOT NULL,
    end_date DATETIME DEFAULT NULL COMMENT 'NULL means permanent',
    trigger_type ENUM('season_start', 'season_end', 'holiday', 'event', 'manual') NOT NULL,
    season_id INT DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX idx_cosmetic_id (cosmetic_id),
    INDEX idx_start_date (start_date),
    INDEX idx_end_date (end_date),
    INDEX idx_trigger_type (trigger_type),
    INDEX idx_season_id (season_id),
    FOREIGN KEY (cosmetic_id) REFERENCES cosmetics(id) ON DELETE CASCADE,
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### user_system_cosmetics_optout Table
```sql
CREATE TABLE user_system_cosmetics_optout (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    system_cosmetic_id INT NOT NULL,
    opted_out_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_user_system_cosmetic (user_id, system_cosmetic_id),
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (system_cosmetic_id) REFERENCES system_cosmetics(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## Cosmetic Property Examples

### Badge
```json
{
    "image_url": "https://cdn.example.com/badges/donor.png",
    "css_class": "donor-badge",
    "hover_text": "Donor Badge"
}
```

### Username Style
```json
{
    "color": "#FFD700",
    "font_weight": "bold",
    "text_shadow": "0 0 10px #FFD700",
    "animation": "glow"
}
```

### Overlay (Snowfall)
```json
{
    "animation": "snowfall",
    "particle_count": 50,
    "speed": "slow",
    "opacity": 0.7
}
```

### Banner
```json
{
    "image_url": "https://cdn.example.com/banners/winter.png",
    "height": "100px",
    "css_class": "winter-banner"
}
```

## Code Changes

### New Repository
File: [`app/repositories/cosmetics.py`](app/repositories/cosmetics.py)

```python
# Categories
async def create_category(
    name: str, render_type: str, owner_type: str
) -> CosmeticCategory: ...
async def fetch_category(
    id: int | None = None, name: str | None = None
) -> CosmeticCategory | None: ...
async def fetch_categories(owner_type: str | None = None) -> list[CosmeticCategory]: ...


# Cosmetics
async def create(
    category_id: int, name: str, description: str | None = None, rarity: str = "common"
) -> Cosmetic: ...
async def fetch_one(
    id: int | None = None, name: str | None = None
) -> Cosmetic | None: ...
async def fetch_many(
    category_id: int | None = None, rarity: str | None = None
) -> list[Cosmetic]: ...


# Properties
async def set_property(
    cosmetic_id: int, key: str, value: str, type: str = "string"
) -> CosmeticProperty: ...
async def get_properties(cosmetic_id: int) -> list[CosmeticProperty]: ...
async def delete_property(cosmetic_id: int, key: str) -> bool: ...


# User Cosmetics
async def grant_user_cosmetic(
    user_id: int, cosmetic_id: int, source: str
) -> UserCosmetic: ...
async def fetch_user_cosmetics(
    user_id: int, source: str | None = None
) -> list[UserCosmetic]: ...
async def equip_user_cosmetic(
    user_id: int, cosmetic_id: int, slot: str
) -> UserEquippedCosmetic | None: ...
async def unequip_user_cosmetic(user_id: int, slot: str) -> bool: ...
async def fetch_equipped_user_cosmetics(user_id: int) -> list[UserEquippedCosmetic]: ...


# Clan Cosmetics
async def grant_clan_cosmetic(clan_id: int, cosmetic_id: int) -> ClanCosmetic: ...
async def fetch_clan_cosmetics(clan_id: int) -> list[ClanCosmetic]: ...
async def equip_clan_cosmetic(
    clan_id: int, cosmetic_id: int, slot: str
) -> ClanEquippedCosmetic | None: ...
async def unequip_clan_cosmetic(clan_id: int, slot: str) -> bool: ...


# System Cosmetics
async def activate_system_cosmetic(
    cosmetic_id: int,
    start_date: datetime,
    end_date: datetime | None,
    trigger_type: str,
    season_id: int | None = None,
) -> SystemCosmetic: ...
async def fetch_active_system_cosmetics() -> list[SystemCosmetic]: ...
async def opt_out_system_cosmetic(user_id: int, system_cosmetic_id: int) -> bool: ...
async def is_opted_out(user_id: int, system_cosmetic_id: int) -> bool: ...
```

### Commands
```python
@command(Privileges.UNRESTRICTED)
async def cosmetics_list(ctx: Context) -> str | None:
    """List your available cosmetics."""


@command(Privileges.UNRESTRICTED)
async def cosmetics_equip(ctx: Context) -> str | None:
    """Equip a cosmetic."""


@command(Privileges.UNRESTRICTED)
async def cosmetics_unequip(ctx: Context) -> str | None:
    """Unequip a cosmetic."""


@command(Privileges.UNRESTRICTED)
async def cosmetics_preview(ctx: Context) -> str | None:
    """Preview a cosmetic."""


@command(Privileges.ADMINISTRATOR)
async def cosmetics_grant(ctx: Context) -> str | None:
    """Grant a cosmetic to a user."""


@command(Privileges.ADMINISTRATOR)
async def cosmetics_revoke(ctx: Context) -> str | None:
    """Revoke a cosmetic from a user."""
```

## Implementation Steps

1. **Create database tables**
   - Create cosmetic_categories table
   - Pre-populate with default categories
   - Create cosmetics table
   - Create cosmetic_properties table
   - Create user_cosmetics table
   - Create user_equipped_cosmetics table
   - Create clan_cosmetics table
   - Create clan_equipped_cosmetics table
   - Create system_cosmetics table
   - Create user_system_cosmetics_optout table

2. **Create repository**
   - Create [`app/repositories/cosmetics.py`](app/repositories/cosmetics.py)
   - Implement all CRUD operations

3. **Migrate existing badges**
   - Create migration script
   - Convert existing badges to new system
   - Preserve user badge assignments

4. **Implement cosmetic types**
   - Badge rendering
   - Username style rendering
   - Overlay rendering
   - Banner rendering
   - Avatar frame rendering
   - Profile background rendering

5. **Create equipping system**
   - Implement equip/unequip logic
   - Add slot validation
   - Add display logic to profiles

6. **Implement condition-based assignment**
   - Create condition evaluation system
   - Implement automatic assignment
   - Implement automatic removal

7. **Create commands**
   - Implement cosmetic management commands

## Testing Checklist
- [ ] All cosmetic types can be created
- [ ] Properties can be set and retrieved
- [ ] User cosmetics can be granted and equipped
- [ ] Clan cosmetics work correctly
- [ ] System cosmetics activate/deactivate correctly
- [ ] User opt-out works
- [ ] Condition-based assignment works
- [ ] Existing badges migrated correctly
- [ ] Rendering works for all cosmetic types
