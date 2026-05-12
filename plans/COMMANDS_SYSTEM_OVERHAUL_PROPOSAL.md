# Commands System Overhaul Proposal

## Executive Summary

This document proposes a comprehensive overhaul of the bancho.py commands system to address critical pain points in both user experience and developer experience. The current monolithic `app/commands.py` file (3022+ lines) has become unmaintainable and lacks modern command system features.

## Current State Analysis

### File Structure Issues
- **Single massive file**: 3022+ lines in one file
- **Poor organization**: Commands scattered across 9 categories in one file
- **Tight coupling**: Commands directly access global state and repositories
- **Inconsistent registration**: Multiple patterns (`@command`, `mp_commands.add`, etc.)

### User Experience Issues
- Basic help system with no filtering or rich formatting
- No command discovery by category or privilege level
- No command examples or detailed usage information
- Generic error messages without helpful suggestions
- No way to see what commands are available for current privileges

### Developer Experience Issues
- **Navigation**: Hard to find commands in monolithic file
- **Testing**: Commands hard to test in isolation
- **Maintenance**: Changes risk breaking unrelated commands
- **Extensibility**: No clean way to add new command categories
- **Documentation**: No auto-generation of command docs
- **Validation**: Each command manually validates arguments
- **Dependencies**: No DI framework, direct global state access

## Proposed Architecture

### 1. Modular File Structure

```
app/commands/
├── __init__.py                 # Command registry and processor
├── base.py                     # Base classes and decorators
├── context.py                  # Enhanced context with DI
├── validation.py               # Argument validation framework
├── help.py                     # Rich help system
├── categories/
│   ├── __init__.py
│   ├── user.py                 # User commands (roll, recent, top, etc.)
│   ├── nominator.py            # Nominator commands (map, request, etc.)
│   ├── moderator.py            # Moderator commands (silence, notes, etc.)
│   ├── administrator.py        # Administrator commands (restrict, alert, etc.)
│   ├── developer.py            # Developer commands (debug, reload, py, etc.)
│   ├── multiplayer.py          # Multiplayer commands (mp_*)
│   ├── mappool.py              # Mappool commands (pool_*)
│   ├── clan.py                 # Clan commands (clan_*)
│   └── season.py               # Season commands (season_*)
└── tests/
    ├── test_commands.py
    └── test_validation.py
```

### 2. Improved Command Registration API

#### Current (Inconsistent):
```python
# Regular commands
@command(Privileges.UNRESTRICTED)
async def roll(ctx: Context) -> str | None:
    """Roll an n-sided die."""
    ...

# Command sets
mp_commands = CommandSet("mp", "Multiplayer commands.")
@mp_commands.add(Privileges.UNRESTRICTED)
async def mp_start(ctx: Context, match: Match) -> str | None:
    """Start the match."""
    ...
```

#### Proposed (Consistent):
```python
from app.commands.base import command, CommandCategory

# All commands use same decorator pattern
@command(
    triggers=["roll"],
    privileges=Privileges.UNRESTRICTED,
    category=CommandCategory.USER,
    aliases=["dice"],
    examples=["!roll 100", "!roll 6"],
    description="Roll an n-sided die.",
)
async def roll(ctx: Context, sides: int = 100) -> str:
    """Roll an n-sided die where n is the number you write (100 default)."""
    if sides == 0:
        return "Roll what?"
    points = random.randrange(0, sides)
    return f"{ctx.player.name} rolls {points} points!"

# Multiplayer commands with namespace
@command(
    triggers=["start", "st"],
    privileges=Privileges.UNRESTRICTED,
    category=CommandCategory.MULTIPLAYER,
    namespace="mp",
    examples=["!mp start", "!mp start 30", "!mp start force"],
    description="Start the current multiplayer match.",
)
async def mp_start(ctx: Context, match: Match, mode: str = "normal") -> str:
    """Start the current multiplayer match."""
    ...
```

### 3. Enhanced Context with Dependency Injection

#### Current:
```python
@dataclass
class Context:
    player: Player
    trigger: str
    args: Sequence[str]
    recipient: Channel | Player
```

#### Proposed:
```python
@dataclass
class Context:
    """Enhanced context with dependency injection."""
    player: Player
    trigger: str
    args: Sequence[str]
    recipient: Channel | Player

    # Dependency injection
    database: Database
    cache: Cache
    settings: Settings
    state: State

    # Command metadata
    command: 'Command'
    raw_message: str

    # Helper methods
    async def get_player(self, name: str) -> Player | None:
        """Get player by name with caching."""
        return await self.state.sessions.players.from_cache_or_sql(name=name)

    def reply(self, message: str, hidden: bool = False) -> CommandResponse:
        """Create a response."""
        return CommandResponse(resp=message, hidden=hidden)
```

### 4. Command Metadata Structure

```python
@dataclass
class Command:
    """Complete command metadata."""
    name: str                           # Primary trigger
    triggers: list[str]                 # All triggers (including aliases)
    callback: Callable[[Context], Awaitable[str | None]]
    privileges: Privileges
    category: CommandCategory
    namespace: str | None = None        # For grouped commands (mp, pool, clan)

    # Documentation
    description: str | None = None
    detailed_help: str | None = None
    examples: list[str] = field(default_factory=list)
    usage: str | None = None

    # Configuration
    hidden: bool = False
    enabled: bool = True
    deprecated: bool = False
    deprecation_message: str | None = None

    # Validation
    validators: list[Callable] = field(default_factory=list)
    arg_parser: Callable | None = None

    # Metadata
    author: str | None = None
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)

    # Pipeline
    pre_hooks: list[Callable] = field(default_factory=list)
    post_hooks: list[Callable] = field(default_factory=list)
```

### 5. Validation Framework

```python
from app.commands.validation import validate, Argument

# Built-in validators
@command(
    triggers=["silence"],
    privileges=Privileges.MODERATOR,
    validators=[
        validate.arg_count(min=3, max=3),
        validate.player_exists(arg_index=0),
        validate.duration(arg_index=1),
        validate.reason(arg_index=2),
    ],
)
async def silence(ctx: Context, player: Player, duration: str, reason: str) -> str:
    """Silence a player."""
    # Validation already performed by framework
    await player.silence(ctx.player, parse_duration(duration), reason)
    return f"{player} was silenced."

# Custom validators
def validate_not_staff(player: Player) -> None:
    if player.priv & Privileges.STAFF:
        raise ValidationError("Cannot manage staff members")

@command(
    triggers=["restrict"],
    privileges=Privileges.ADMINISTRATOR,
    validators=[
        validate.player_exists(arg_index=0),
        validate_not_staff(arg_index=0),
        validate.reason(arg_index=1),
    ],
)
```

### 6. Rich Help System

```python
# Command help with rich formatting
@command(
    triggers=["top"],
    privileges=Privileges.UNRESTRICTED,
    category=CommandCategory.USER,
    description="Show top 10 scores for a player.",
    detailed_help="""
Shows the top 10 scores for a player in a specific game mode.

Usage:
  !top <mode> [player]

Examples:
  !top std                    # Your top 10 standard scores
  !top rx!taiko playername    # Another player's relax taiko scores

Modes:
  std, taiko, catch, mania
  rx!std, rx!taiko, rx!catch, rx!mania (relax)
  ap!std, ap!taiko, ap!catch, ap!mania (autopilot)
""",
    examples=[
        "!top std",
        "!top rx!taiko playername",
    ],
)
async def top(ctx: Context, mode: str, player: str | None = None) -> str:
    """Show top 10 scores."""
    ...
```

### 7. Command Pipeline (Middleware)

```python
# Pre-execution hooks
async def require_bot_dm(ctx: Context) -> None:
    """Ensure command is used in DM with bot."""
    if ctx.recipient is not ctx.state.sessions.bot:
        raise CommandError("This command can only be used in DM with bot.")

async def require_last_np(ctx: Context) -> None:
    """Ensure player has recently /np'd a map."""
    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        raise CommandError("Please /np a map first!")

# Apply hooks to command
@command(
    triggers=["with", "w"],
    privileges=Privileges.UNRESTRICTED,
    pre_hooks=[require_bot_dm, require_last_np],
)
async def _with(ctx: Context, *args: str) -> str:
    """Calculate performance with custom mods."""
    # Hooks already executed
    ...
```

### 8. Command Discovery and Filtering

```python
class CommandRegistry:
    """Central command registry with discovery methods."""

    def get_by_trigger(self, trigger: str) -> Command | None:
        """Get command by trigger."""
        ...

    def get_by_category(self, category: CommandCategory) -> list[Command]:
        """Get all commands in a category."""
        ...

    def get_by_privilege(self, privilege: Privileges) -> list[Command]:
        """Get all commands available to a privilege level."""
        ...

    def get_available(self, player: Player) -> list[Command]:
        """Get all commands available to a player."""
        ...

    def search(self, query: str, player: Player | None = None) -> list[Command]:
        """Search commands by name/description."""
        ...

    def generate_docs(self) -> str:
        """Generate markdown documentation for all commands."""
        ...
```

### 9. Testing Support

```python
# Commands are easily testable
@pytest.mark.asyncio
async def test_roll_command():
    """Test roll command."""
    # Create mock context
    ctx = Context(
        player=MockPlayer(name="TestPlayer"),
        trigger="roll",
        args=["6"],
        recipient=MockChannel(),
        database=MockDatabase(),
        cache=MockCache(),
        settings=MockSettings(),
        state=MockState(),
        command=roll_command,
        raw_message="!roll 6",
    )

    # Execute command
    result = await roll(ctx, sides=6)

    # Assert result
    assert "TestPlayer rolls" in result
    assert "points!" in result

# Integration tests
async def test_silence_command_integration():
    """Test silence command with real database."""
    # Setup
    player = await create_test_player()
    target = await create_test_player()

    # Execute
    result = await silence_command(
        Context(...),
        player=target,
        duration="10m",
        reason="Test silence",
    )

    # Assert
    assert f"{target} was silenced" in result
    assert target.silenced
```

### 10. Documentation Generation

```python
# Auto-generate documentation
registry = CommandRegistry()
docs = registry.generate_docs()

# Generates markdown like:
"""
# Command Reference

## User Commands
### !roll
Roll an n-sided die.

**Usage:** !roll [sides]
**Privileges:** UNRESTRICTED
**Examples:**
  !roll        # Roll 100-sided die
  !roll 6      # Roll 6-sided die

### !recent
Show information about your most recent score.

**Usage:** !recent [player]
**Privileges:** UNRESTRICTED
**Examples:**
  !recent              # Your recent score
  !recent playername   # Another player's recent score

## Multiplayer Commands
### !mp start
Start the current multiplayer match.

**Usage:** !mp start [force|seconds|cancel]
**Privileges:** UNRESTRICTED
**Examples:**
  !mp start          # Start when ready
  !mp start force    # Start immediately
  !mp start 30       # Start in 30 seconds
"""
```

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
1. Create new directory structure
2. Implement base classes (`Command`, `Context`, `CommandRegistry`)
3. Implement validation framework
4. Create `__init__.py` with command registration

### Phase 2: Command Migration (Week 3-4)
1. Migrate user commands to `categories/user.py`
2. Migrate nominator commands to `categories/nominator.py`
3. Migrate moderator commands to `categories/moderator.py`
4. Migrate administrator commands to `categories/administrator.py`

### Phase 3: Advanced Commands (Week 5-6)
1. Migrate developer commands to `categories/developer.py`
2. Migrate multiplayer commands to `categories/multiplayer.py`
3. Migrate mappool commands to `categories/mappool.py`
4. Migrate clan commands to `categories/clan.py`
5. Migrate season commands to `categories/season.py`

### Phase 4: Enhanced Features (Week 7-8)
1. Implement rich help system
2. Add command pipeline/middleware
3. Implement command discovery methods
4. Add documentation generation
5. Create comprehensive tests

### Phase 5: Polish & Deployment (Week 9-10)
1. Performance optimization
2. Migration of existing command processor
3. Documentation
4. Code review and testing
5. Deployment with backward compatibility

## Benefits

### For Users
- ✅ Rich, formatted help with examples
- ✅ Command discovery by category
- ✅ Better error messages with suggestions
- ✅ Consistent command syntax
- ✅ Detailed usage information

### For Developers
- ✅ Modular, maintainable codebase
- ✅ Consistent command registration
- ✅ Built-in validation framework
- ✅ Easy testing support
- ✅ Dependency injection
- ✅ Auto-generated documentation
- ✅ Command pipeline for cross-cutting concerns
- ✅ Type safety with modern Python

### For Operations
- ✅ Easier debugging
- ✅ Better error tracking
- ✅ Command versioning
- ✅ Easy feature flags
- ✅ Performance monitoring

## Backward Compatibility

The new system will maintain backward compatibility:
1. Old command processor will remain functional during migration
2. Commands can be migrated incrementally
3. No breaking changes to existing command syntax
4. Graceful degradation for unmigrated commands

## Success Metrics

- **Code Quality**: Reduce commands.py from 3022+ lines to ~100 lines (registry only)
- **Test Coverage**: Achieve 80%+ test coverage for command system
- **Developer Experience**: Reduce time to add new commands by 50%
- **User Satisfaction**: Improve help system usability metrics
- **Maintainability**: Reduce bug reports related to commands by 30%

## Conclusion

This overhaul will transform the commands system from a monolithic, hard-to-maintain codebase into a modern, modular, and developer-friendly system. The proposed architecture addresses all identified pain points while providing a foundation for future enhancements.

The investment in this overhaul will pay dividends through:
- Faster feature development
- Fewer bugs
- Better user experience
- Easier maintenance
- Improved testability
