# Server Upgrades Master Plan

## Overview
This directory contains the detailed implementation plans for all server upgrades. Each plan is in a separate file for easy refinement and implementation.

## Plan Files

### Phase 1: Foundation
1. **[Logs Table Overhaul](01-logs-overhaul.md)** - Rename columns, add severity/source
2. **[Seasons System](02-seasons-system.md)** - Datetime-based season filtering with multiple schedule types
3. **[Leaderboard Types & Cheats](03-leaderboard-types-and-cheats.md)** - Multi-leaderboard system with cheat definitions

### Phase 2: Clans Overhaul
4. **[Clans Overhaul](04-clans-overhaul.md)** - Full clan system with wars, invites, stats

### Phase 3: Cosmetics & Donor
5. **[Cosmetics System](05-cosmetics-system.md)** - Flexible property-based cosmetics for users, clans, system
6. **[Donor System](06-donor-system.md)** - Multi-tier donor system with Stripe integration

### Phase 4: Score Hunts
7. **[Score Hunts System](07-score-hunts-system.md)** - Passive score hunt system with restrictions

### Phase 5: Sessions
8. **[Sessions System](08-sessions-system.md)** - Mini-profiles with goals and cross-server integration

### Phase 6: API & Migration
9. **[API & Migration](09-api-and-migration.md)** - All API endpoints and migration scripts

## Architecture Documents
- **[Database Schema](database-schema.md)** - Complete database schema reference
- **[Migration Script](../migrations/001_logs_table_overhaul.sql)** - Logs table migration

## Implementation Order
1. Phase 1: Foundation (Logs, Seasons, Leaderboard Types, Cheats)
2. Phase 2: Clans Overhaul
3. Phase 3: Cosmetics & Donor
4. Phase 4: Score Hunts
5. Phase 5: Sessions
6. Phase 6: API & Migration

## Key Design Decisions
- **Seasons**: Datetime-based filtering (no season_id on scores table)
- **Clan Wars**: Filter existing scores by clan members (no separate score table)
- **Cosmetics**: Property-based system with external image URLs
- **Score Hunts**: Passive tracking with retroactive filtering
- **Sessions**: Scores count toward both session AND global leaderboards
- **Donor**: Modular payment provider interface with Stripe as primary
