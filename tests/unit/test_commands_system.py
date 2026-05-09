"""
Tests for the new commands system.

This file tests the command registration, execution, and help system.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from app.commands import CommandRegistry
from app.commands.base import Command
from app.commands.base import CommandCategory
from app.commands.base import CommandMetadata
from app.commands.base import moderator_command
from app.commands.base import user_command
from app.commands.context import Context
from app.commands.validation import ValidationError
from app.commands.validation import validate
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED | Privileges.MODERATOR
    player.is_online = True
    player.recent_score = None
    return player


@pytest.fixture
def mock_database():
    """Create a mock database."""
    database = AsyncMock()
    return database


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = Mock()
    return cache


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.COMMAND_PREFIX = "!"
    settings.DOMAIN = "osu.test"
    return settings


@pytest.fixture
def mock_state():
    """Create mock state."""
    state = Mock()
    state.sessions = Mock()
    state.sessions.players = Mock()
    state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)
    state.sessions.bot = Mock()
    return state


@pytest.fixture
def registry():
    """Create a command registry for testing."""
    return CommandRegistry()


class TestCommandRegistration:
    """Test command registration functionality."""

    def test_register_simple_command(self, registry):
        """Test registering a simple command."""

        @user_command(
            name="test",
            description="A test command.",
        )
        async def test_cmd(ctx: Context) -> str:
            return "test result"

        registry.register(test_cmd)

        # Verify command is registered
        cmd = registry.get_by_trigger("test")
        assert cmd is not None
        assert cmd.metadata.name == "test"
        assert cmd.metadata.description == "A test command."

    def test_register_command_with_triggers(self, registry):
        """Test registering command with multiple triggers."""

        @user_command(
            name="roll",
            triggers=["roll", "dice"],
            description="Roll a die.",
        )
        async def roll_cmd(ctx: Context) -> str:
            return "rolled"

        registry.register(roll_cmd)

        # Verify both triggers work
        assert registry.get_by_trigger("roll") is not None
        assert registry.get_by_trigger("dice") is not None

    def test_register_command_with_namespace(self, registry):
        """Test registering command with namespace."""

        @moderator_command(
            name="start",
            namespace="mp",
            description="Start a match.",
        )
        async def mp_start_cmd(ctx: Context) -> str:
            return "started"

        registry.register(mp_start_cmd)

        # Verify namespace registration
        # Commands with namespace are registered as "namespace_trigger"
        assert registry.get_by_trigger("mp_start") is not None
        assert registry.get_by_namespace("mp", "start") is not None

    def test_duplicate_trigger_raises_error(self, registry):
        """Test that duplicate triggers raise an error."""

        @user_command(name="test1", description="Test 1")
        async def cmd1(ctx: Context) -> str:
            return "test1"

        @user_command(name="test2", triggers=["test1"], description="Test 2")
        async def cmd2(ctx: Context) -> str:
            return "test2"

        registry.register(cmd1)

        with pytest.raises(
            ValueError, match="Command with trigger 'test1' already registered"
        ):
            registry.register(cmd2)


class TestCommandExecution:
    """Test command execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_command(
        self,
        registry,
        mock_player,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test executing a command."""

        @user_command(
            name="test",
            description="A test command.",
        )
        async def test_cmd(ctx: Context) -> str:
            return f"Hello, {ctx.player.name}!"

        registry.register(test_cmd)

        result = await registry.execute(
            player=mock_player,
            recipient=mock_player,
            message="!test",
            database=mock_database,
            cache=mock_cache,
            settings=mock_settings,
            state=mock_state,
        )

        assert result is not None
        assert result.resp == "Hello, TestPlayer!"
        assert result.hidden is False

    @pytest.mark.asyncio
    async def test_execute_command_with_args(
        self,
        registry,
        mock_player,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test executing command with arguments."""

        @user_command(
            name="echo",
            description="Echo arguments.",
        )
        async def echo_cmd(ctx: Context) -> str:
            return " ".join(ctx.args)

        registry.register(echo_cmd)

        result = await registry.execute(
            player=mock_player,
            recipient=mock_player,
            message="!echo hello world",
            database=mock_database,
            cache=mock_cache,
            settings=mock_settings,
            state=mock_state,
        )

        assert result is not None
        assert result.resp == "hello world"

    @pytest.mark.asyncio
    async def test_execute_namespace_command(
        self,
        registry,
        mock_player,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test executing namespace command."""

        @moderator_command(
            name="start",
            namespace="mp",
            description="Start a match.",
        )
        async def mp_start_cmd(ctx: Context) -> str:
            return "Match started!"

        registry.register(mp_start_cmd)

        result = await registry.execute(
            player=mock_player,
            recipient=mock_player,
            message="!mp start",
            database=mock_database,
            cache=mock_cache,
            settings=mock_settings,
            state=mock_state,
        )

        assert result is not None
        assert result.resp == "Match started!"

    @pytest.mark.asyncio
    async def test_execute_command_with_validation(
        self,
        registry,
        mock_player,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test executing command with argument validation."""

        @user_command(
            name="roll",
            description="Roll a die.",
            validators=[validate.numeric(arg_index=0, min_value=1, integer_only=True)],
        )
        async def roll_cmd(ctx: Context) -> str:
            return f"Rolled {ctx.args[0]}"

        registry.register(roll_cmd)

        # Test valid input
        result = await registry.execute(
            player=mock_player,
            recipient=mock_player,
            message="!roll 6",
            database=mock_database,
            cache=mock_cache,
            settings=mock_settings,
            state=mock_state,
        )

        assert result is not None
        assert result.resp == "Rolled 6"

        # Test invalid input
        result = await registry.execute(
            player=mock_player,
            recipient=mock_player,
            message="!roll 0",
            database=mock_database,
            cache=mock_cache,
            settings=mock_settings,
            state=mock_state,
        )

        assert result is not None
        assert "Validation error" in result.resp

    @pytest.mark.asyncio
    async def test_execute_nonexistent_command(
        self,
        registry,
        mock_player,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test executing nonexistent command returns None."""
        result = await registry.execute(
            player=mock_player,
            recipient=mock_player,
            message="!nonexistent",
            database=mock_database,
            cache=mock_cache,
            settings=mock_settings,
            state=mock_state,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_command_without_permission(
        self,
        registry,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test executing command without proper permissions."""

        @moderator_command(
            name="modonly",
            description="Moderator only command.",
        )
        async def mod_cmd(ctx: Context) -> str:
            return "mod result"

        registry.register(mod_cmd)

        # Create a player with only UNRESTRICTED privileges (no MODERATOR)
        player = Mock()
        player.name = "RegularPlayer"
        player.id = 2
        player.priv = Privileges.UNRESTRICTED
        player.is_online = True
        player.recent_score = None

        result = await registry.execute(
            player=player,
            recipient=player,
            message="!modonly",
            database=mock_database,
            cache=mock_cache,
            settings=mock_settings,
            state=mock_state,
        )

        assert result is not None
        assert "permission" in result.resp.lower()


class TestCommandHelp:
    """Test command help system."""

    def test_generate_general_help(self, registry, mock_player):
        """Test generating general help."""

        @user_command(
            name="test",
            description="A test command.",
        )
        async def test_cmd(ctx: Context) -> str:
            return "test"

        registry.register(test_cmd)

        help_msg = registry.generate_help(mock_player)

        assert "Command Help System" in help_msg
        assert "test" in help_msg
        assert "A test command." in help_msg

    def test_generate_category_help(self, registry, mock_player):
        """Test generating category-specific help."""

        @user_command(
            name="test1",
            description="Test command 1.",
        )
        async def test1_cmd(ctx: Context) -> str:
            return "test1"

        @user_command(
            name="test2",
            description="Test command 2.",
        )
        async def test2_cmd(ctx: Context) -> str:
            return "test2"

        registry.register(test1_cmd)
        registry.register(test2_cmd)

        help_msg = registry.generate_help(mock_player, category=CommandCategory.USER)

        assert "User Commands" in help_msg
        assert "test1" in help_msg
        assert "test2" in help_msg

    def test_generate_command_help(self, registry, mock_player):
        """Test generating command-specific help."""

        @user_command(
            name="test",
            description="A test command.",
            usage="!test <arg>",
            examples=["!test hello", "!test world"],
        )
        async def test_cmd(ctx: Context) -> str:
            return "test"

        registry.register(test_cmd)

        help_msg = registry.generate_help(mock_player, search_query="test")

        assert "test" in help_msg
        assert "A test command." in help_msg
        assert "!test hello" in help_msg


class TestValidationFramework:
    """Test the validation framework."""

    @pytest.mark.asyncio
    async def test_arg_count_validator(self):
        """Test argument count validation."""
        from app.commands.validation import ArgCountValidator

        validator = ArgCountValidator(min_count=2, max_count=3)

        # Create mock context
        ctx = Mock()
        ctx.args = ["arg1", "arg2"]

        # Should pass
        await validator(ctx)

        # Should fail - too few
        ctx.args = ["arg1"]
        with pytest.raises(ValidationError):
            await validator(ctx)

        # Should fail - too many
        ctx.args = ["arg1", "arg2", "arg3", "arg4"]
        with pytest.raises(ValidationError):
            await validator(ctx)

    @pytest.mark.asyncio
    async def test_numeric_validator(self):
        """Test numeric validation."""
        from app.commands.validation import NumericValidator

        validator = NumericValidator(
            arg_index=0, min_value=1, max_value=100, integer_only=True
        )

        # Create mock context
        ctx = Mock()
        ctx.args = ["50"]

        # Should pass
        await validator(ctx)

        # Should fail - not a number
        ctx.args = ["abc"]
        with pytest.raises(ValidationError):
            await validator(ctx)

        # Should fail - out of range
        ctx.args = ["0"]
        with pytest.raises(ValidationError):
            await validator(ctx)

        ctx.args = ["101"]
        with pytest.raises(ValidationError):
            await validator(ctx)

    @pytest.mark.asyncio
    async def test_choice_validator(self):
        """Test choice validation."""
        from app.commands.validation import ChoiceValidator

        validator = ChoiceValidator(
            arg_index=0, choices=["on", "off"], case_sensitive=False
        )

        # Create mock context
        ctx = Mock()
        ctx.args = ["on"]

        # Should pass
        await validator(ctx)

        # Should fail - invalid choice
        ctx.args = ["maybe"]
        with pytest.raises(ValidationError):
            await validator(ctx)


class TestCommandMetadata:
    """Test command metadata structure."""

    def test_command_metadata_creation(self):
        """Test creating command metadata."""
        metadata = CommandMetadata(
            name="test",
            triggers=["test", "t"],
            category=CommandCategory.USER,
            description="A test command.",
            usage="!test <arg>",
            examples=["!test hello"],
            hidden=True,
        )

        assert metadata.name == "test"
        assert metadata.triggers == ["test", "t"]
        assert metadata.category == CommandCategory.USER
        assert metadata.description == "A test command."
        assert metadata.usage == "!test <arg>"
        assert metadata.examples == ["!test hello"]
        assert metadata.hidden is True

    def test_command_creation(self):
        """Test creating a command."""

        async def callback(ctx: Context) -> str:
            return "test"

        metadata = CommandMetadata(
            name="test",
            triggers=["test"],
            category=CommandCategory.USER,
        )

        command = Command(
            metadata=metadata,
            callback=callback,
            privileges=Privileges.UNRESTRICTED,
        )

        assert command.metadata.name == "test"
        assert command.privileges == Privileges.UNRESTRICTED
        assert command.callback == callback


class TestCommandBuilder:
    """Test the command builder pattern."""

    def test_builder_pattern(self):
        """Test building command using builder pattern."""
        from app.commands.base import CommandBuilder

        async def callback(ctx: Context) -> str:
            return "test"

        builder = CommandBuilder("test", CommandCategory.USER)
        builder.trigger("test", "t")
        builder.privileges(Privileges.UNRESTRICTED)
        builder.description("A test command.")
        builder.examples("!test hello", "!test world")
        builder.hidden(True)

        command = builder.build(callback)

        assert command.metadata.name == "test"
        assert command.metadata.triggers == ["test", "t"]
        assert command.metadata.description == "A test command."
        assert command.metadata.hidden is True
        assert command.callback == callback


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
