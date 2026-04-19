# API Endpoints & Migration Plan

## Overview
Create v2 API endpoints for all new features and implement data migration scripts.

## API Endpoints

### Seasons API
```
GET /api/v2/seasons - List all seasons
GET /api/v2/seasons/{id} - Get season details
POST /api/v2/seasons - Create season (admin)
PUT /api/v2/seasons/{id} - Update season (admin)
DELETE /api/v2/seasons/{id} - Delete season (admin)
GET /api/v2/seasons/active - Get active season
POST /api/v2/seasons/{id}/activate - Activate season (admin)
POST /api/v2/seasons/{id}/deactivate - Deactivate season (admin)
```

### Sessions API
```
GET /api/v2/sessions - List user's sessions
GET /api/v2/sessions/{id} - Get session details
POST /api/v2/sessions - Create session
PUT /api/v2/sessions/{id} - Update session
DELETE /api/v2/sessions/{id} - Delete session
POST /api/v2/sessions/{id}/activate - Activate session
POST /api/v2/sessions/{id}/deactivate - Deactivate session
GET /api/v2/sessions/{id}/progress - Get session progress
```

### Leaderboard Types API
```
GET /api/v2/leaderboard-types - List all leaderboard types
GET /api/v2/leaderboard-types/{id} - Get leaderboard type details
POST /api/v2/leaderboard-types - Create leaderboard type (admin)
PUT /api/v2/leaderboard-types/{id} - Update leaderboard type (admin)
DELETE /api/v2/leaderboard-types/{id} - Delete leaderboard type (admin)
```

### Cosmetics API
```
GET /api/v2/cosmetics/categories - List cosmetic categories
GET /api/v2/cosmetics - List all cosmetics
GET /api/v2/cosmetics/{id} - Get cosmetic details
POST /api/v2/cosmetics - Create cosmetic (admin)
PUT /api/v2/cosmetics/{id} - Update cosmetic (admin)
DELETE /api/v2/cosmetics/{id} - Delete cosmetic (admin)
GET /api/v2/cosmetics/user/{user_id} - Get user's cosmetics
POST /api/v2/cosmetics/{id}/equip - Equip cosmetic
POST /api/v2/cosmetics/{id}/unequip - Unequip cosmetic
GET /api/v2/cosmetics/clan/{clan_id} - Get clan's cosmetics
```

### Score Hunts API
```
GET /api/v2/score-hunts - List all score hunts
GET /api/v2/score-hunts/{id} - Get score hunt details
POST /api/v2/score-hunts - Create score hunt (admin)
PUT /api/v2/score-hunts/{id} - Update score hunt (admin)
DELETE /api/v2/score-hunts/{id} - Delete score hunt (admin)
POST /api/v2/score-hunts/{id}/start - Start score hunt (admin)
POST /api/v2/score-hunts/{id}/end - End score hunt (admin)
GET /api/v2/score-hunts/{id}/leaderboard - Get hunt leaderboard
GET /api/v2/score-hunts/{id}/submissions - Get hunt submissions
```

### Clan Wars API
```
GET /api/v2/clan-wars - List all clan wars
GET /api/v2/clan-wars/{id} - Get clan war details
POST /api/v2/clan-wars - Create clan war challenge
PUT /api/v2/clan-wars/{id} - Update clan war
POST /api/v2/clan-wars/{id}/accept - Accept clan war
POST /api/v2/clan-wars/{id}/decline - Decline clan war
GET /api/v2/clan-wars/{id}/scores - Get war scores
GET /api/v2/clan-wars/{id}/results - Get war results
```

### Cheats API
```
GET /api/v2/cheats/definitions - List cheat definitions
GET /api/v2/cheats/definitions/{id} - Get cheat definition
POST /api/v2/cheats/definitions - Create cheat definition (admin)
PUT /api/v2/cheats/definitions/{id} - Update cheat definition (admin)
DELETE /api/v2/cheats/definitions/{id} - Delete cheat definition (admin)
GET /api/v2/cheats/versions/{cheat_id} - Get cheat versions
POST /api/v2/cheats/versions - Create cheat version (admin)
GET /api/v2/cheats/rules/{season_id} - Get season cheat rules
POST /api/v2/cheats/rules - Create season cheat rule (admin)
```

### External Servers API
```
GET /api/v2/external-servers - List external servers
GET /api/v2/external-servers/{id} - Get external server details
POST /api/v2/external-servers - Add external server (admin)
PUT /api/v2/external-servers/{id} - Update external server (admin)
DELETE /api/v2/external-servers/{id} - Delete external server (admin)
POST /api/v2/external-servers/{id}/sync - Sync external server (admin)
GET /api/v2/external-servers/{id}/leaderboard - Get external leaderboard
```

### Donor API
```
GET /api/v2/donor/tiers - List donor tiers
GET /api/v2/donor/tiers/{id} - Get donor tier details
POST /api/v2/donor/tiers - Create donor tier (admin)
PUT /api/v2/donor/tiers/{id} - Update donor tier (admin)
DELETE /api/v2/donor/tiers/{id} - Delete donor tier (admin)
GET /api/v2/donor/subscriptions - List user's subscriptions
POST /api/v2/donor/subscribe - Create subscription
POST /api/v2/donor/cancel - Cancel subscription
GET /api/v2/donor/history - Get donation history
POST /api/v2/donor/webhook/stripe - Stripe webhook
```

## Migration Scripts

### 1. Logs Migration
File: `migrations/001_logs_table_overhaul.sql`
- Rename columns to avoid reserved words
- Add severity and source columns
- Add indexes

### 2. Seasons Migration
File: `migrations/002_seasons_system.sql`
- Create season_schedules table
- Create seasons table
- Create season_config table
- Create season_stats table
- Add season_id to scores table (for reference only, not used for filtering)
- Add leaderboard_type_id to scores table

### 3. Leaderboard Types Migration
File: `migrations/003_leaderboard_types.sql`
- Create leaderboard_types table
- Pre-populate with default types

### 4. Cheats Migration
File: `migrations/004_cheats_system.sql`
- Create cheat_definitions table
- Create cheat_versions table
- Create season_cheat_rules table

### 5. Clans Migration
File: `migrations/005_clans_overhaul.sql`
- Add new columns to clans table
- Create clan_stats table
- Create clan_season_stats table
- Create clan_invites table
- Create clan_join_requests table
- Create clan_wars table
- Create clan_war_results table

### 6. Cosmetics Migration
File: `migrations/006_cosmetics_system.sql`
- Create cosmetic_categories table
- Create cosmetics table
- Create cosmetic_properties table
- Create user_cosmetics table
- Create user_equipped_cosmetics table
- Create clan_cosmetics table
- Create clan_equipped_cosmetics table
- Create system_cosmetics table
- Create user_system_cosmetics_optout table
- Migrate existing badges to new system

### 7. Donor Migration
File: `migrations/007_donor_system.sql`
- Create donor_tiers table
- Create donor_subscriptions table
- Create donation_history table
- Create payment_providers table
- Pre-populate donor tiers

### 8. Score Hunts Migration
File: `migrations/008_score_hunts.sql`
- Create score_hunts table
- Create score_hunt_restrictions table
- Create score_hunt_submissions table
- Create score_hunt_results table
- Create score_hunt_points table

### 9. Sessions Migration
File: `migrations/009_sessions_system.sql`
- Create sessions table
- Create session_stats table
- Create session_scores table
- Create external_servers table
- Create external_leaderboard_cache table

## Testing Strategy

### Unit Tests
- Test all repository functions
- Test all API endpoints
- Test all command handlers
- Test all background tasks

### Integration Tests
- Test season activation/deactivation
- Test score submission with season/leaderboard filtering
- Test clan war flow
- Test score hunt flow
- Test session creation and progress tracking
- Test cosmetic equipping/unequipping
- Test donor subscription flow

### Migration Tests
- Test all migration scripts on test database
- Verify data integrity after migration
- Test rollback procedures

## Implementation Order

1. **Phase 1: Foundation**
   - Logs migration
   - Seasons migration
   - Leaderboard types migration
   - Cheats migration

2. **Phase 2: Core Features**
   - Clans migration
   - Cosmetics migration
   - Donor migration

3. **Phase 3: Advanced Features**
   - Score hunts migration
   - Sessions migration

4. **Phase 4: API & Testing**
   - Create all API endpoints
   - Write all tests
   - Run migration tests
   - Deploy to staging

## Testing Checklist
- [ ] All migrations run successfully
- [ ] All API endpoints work correctly
- [ ] All commands work correctly
- [ ] All background tasks work correctly
- [ ] Data integrity maintained after migration
- [ ] Performance acceptable with new schema
- [ ] All tests pass
