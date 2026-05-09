"""
Tests for command base classes and decorators.

Covers Command, CommandMetadata, CommandBuilder, and convenience decorators.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from app.commands.base import Command
from app.commands.base import CommandBuilder
from app.commands.base import CommandCategory
from app.commands.base import CommandError
from app.commands.base import CommandMetadata
from app.commands.base import CommandValidator
from app.commands.base import ValidationError
from app.commands.base import administrator_command
from app.commands.base import clan_command
from app.commands.base import command
from app.commands.base import developer_command
from app.commands.base import mappool_command
from app.commands.base import moderator_command
from app.commands.base import multiplayer_command
from app.commands.base import nominator_command
from app.commands.base import season_command
from app.commands.base import user_command
from app.commands.context import Context
from app.constants.privileges import Privileges


class TestCommandMetadata:
    """Test CommandMetadata dataclass."""

    def test_minimal_metadata(self):
        """Test creating minimal command metadata."""
        metadata = CommandMetadata(
            name="test",
            triggers=["test"],
            category=CommandCategory.USER,
        )
        assert metadata.name == "test"
        assert metadata.triggers == ["test"]
        assert metadata.category == CommandCategory.USER
        assert metadata.namespace is None
        assert metadata.description is None
        assert metadata.hidden is False
        assert metadata.enabled is True
        assert metadata.deprecated is False
        assert metadata.validators == []
        assert metadata.pre_hooks == []
        assert metadata.post_hooks == []

    def test_full_metadata(self):
        """Test creating command metadata with all fields."""
        pre_hook = AsyncMock()
        post_hook = AsyncMock()
        validator = Mock(spec=CommandValidator)

        metadata = CommandMetadata(
            name="test",
            triggers=["test", "t"],
            category=CommandCategory.USER,
            namespace="ns",
            description="Test command",
            detailed_help="Detailed help text",
            examples=["!test", "!t"],
            usage="!test [args]",
            hidden=True,
            enabled=False,
            deprecated=True,
            deprecation_message="Use !newcommand instead",
            validators=[validator],
            pre_hooks=[pre_hook],
            post_hooks=[post_hook],
        )

        assert metadata.name == "test"
        assert metadata.triggers == ["test", "t"]
        assert metadata.category == CommandCategory.USER
        assert metadata.namespace == "ns"
        assert metadata.description == "Test command"
        assert metadata.detailed_help == "Detailed help text"
        assert metadata.examples == ["!test", "!t"]
        assert metadata.usage == "!test [args]"
        assert metadata.hidden is True
        assert metadata.enabled is False
        assert metadata.deprecated is True
        assert metadata.deprecation_message == "Use !newcommand instead"
        assert metadata.validators == [validator]
        assert metadata.pre_hooks == [pre_hook]
        assert metadata.post_hooks == [post_hook]


class TestCommand:
    """Test Command dataclass."""

    def test_command_creation(self):
        """Test creating a valid command."""
        callback = AsyncMock(return_value="result")
        metadata = CommandMetadata(
            name="test",
            triggers=["test"],
            category=CommandCategory.USER,
        )
        cmd = Command(
            metadata=metadata,
            callback=callback,
            privileges=Privileges.UNRESTRICTED,
        )
        assert cmd.metadata == metadata
        assert cmd.callback == callback
        assert cmd.privileges == Privileges.UNRESTRICTED

    def test_command_empty_triggers_raises(self):
        """Test that Command with empty triggers raises ValueError."""
        callback = AsyncMock()
        metadata = CommandMetadata(
            name="test",
            triggers=[],  # Empty triggers
            category=CommandCategory.USER,
        )
        with pytest.raises(ValueError, match="must have at least one trigger"):
            Command(
                metadata=metadata,
                callback=callback,
                privileges=Privileges.UNRESTRICTED,
            )

    def test_command_empty_name_raises(self):
        """Test that Command with empty name raises ValueError."""
        callback = AsyncMock()
        metadata = CommandMetadata(
            name="",  # Empty name
            triggers=["test"],
            category=CommandCategory.USER,
        )
        with pytest.raises(ValueError, match="must have a name"):
            Command(
                metadata=metadata,
                callback=callback,
                privileges=Privileges.UNRESTRICTED,
            )


class TestCommandBuilder:
    """Test CommandBuilder fluent API."""

    def test_builder_minimal(self):
        """Test building a command with minimal configuration."""
        builder = CommandBuilder("test", CommandCategory.USER)
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.name == "test"
        assert cmd.metadata.triggers == ["test"]
        assert cmd.metadata.category == CommandCategory.USER
        assert cmd.privileges == 0

    def test_builder_with_triggers(self):
        """Test builder with multiple triggers."""
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.trigger("test", "t", "testing")
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.triggers == ["test", "t", "testing"]

    def test_builder_with_privileges(self):
        """Test builder with privileges."""
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.privileges(Privileges.MODERATOR)
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.privileges == Privileges.MODERATOR

    def test_builder_with_description(self):
        """Test builder with description."""
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.description("Test description")
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.description == "Test description"

    def test_builder_with_detailed_help(self):
        """Test builder with detailed help."""
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.detailed_help("Detailed help text")
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.detailed_help == "Detailed help text"

    def test_builder_with_examples(self):
        """Test builder with examples."""
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.examples("!test", "!t arg")
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.examples == ["!test", "!t arg"]

    def test_builder_with_usage(self):
        """Test builder with usage."""
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.usage("!test [args]")
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.usage == "!test [args]"

    def test_builder_with_hidden(self):
        """Test builder with hidden flag."""
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.hidden(True)
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.hidden is True

    def test_builder_with_namespace(self):
        """Test builder with namespace."""
        builder = CommandBuilder("test", CommandCategory.MULTIPLAYER)
        builder.namespace("mp")
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.namespace == "mp"

    def test_builder_with_validator(self):
        """Test builder with validator."""
        validator = Mock(spec=CommandValidator)
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.validator(validator)
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.validators == [validator]

    def test_builder_with_pre_hook(self):
        """Test builder with pre-hook."""
        pre_hook = AsyncMock()
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.pre_hook(pre_hook)
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.pre_hooks == [pre_hook]

    def test_builder_with_post_hook_two_params(self):
        """Test builder with post-hook that takes two parameters."""
        post_hook = AsyncMock()
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.post_hook(post_hook)
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.post_hooks == [post_hook]

    def test_builder_fluent_chaining(self):
        """Test that builder methods return self for chaining."""
        builder = CommandBuilder("test", CommandCategory.USER)
        result = (
            builder.trigger("test", "t")
            .privileges(Privileges.MODERATOR)
            .description("Test")
            .examples("!test")
            .usage("!test [args]")
            .hidden(True)
            .namespace("ns")
        )
        assert result is builder

    def test_builder_multiple_validators(self):
        """Test builder with multiple validators."""
        v1 = Mock(spec=CommandValidator)
        v2 = Mock(spec=CommandValidator)
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.validator(v1).validator(v2)
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.validators == [v1, v2]

    def test_builder_multiple_hooks(self):
        """Test builder with multiple hooks."""
        h1 = AsyncMock()
        h2 = AsyncMock()
        builder = CommandBuilder("test", CommandCategory.USER)
        builder.pre_hook(h1).pre_hook(h2)
        callback = AsyncMock(return_value="result")
        cmd = builder.build(callback)

        assert cmd.metadata.pre_hooks == [h1, h2]


class TestCommandDecorator:
    """Test the @command decorator."""

    def test_command_decorator_basic(self):
        """Test basic command decorator."""

        @command(name="test", category=CommandCategory.USER)
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.name == "test"
        assert test_cmd.metadata.triggers == ["test"]
        assert test_cmd.metadata.category == CommandCategory.USER
        assert test_cmd.privileges == 0

    def test_command_decorator_with_triggers(self):
        """Test command decorator with custom triggers."""

        @command(
            name="test",
            category=CommandCategory.USER,
            triggers=["test", "t", "testing"],
        )
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.triggers == ["test", "t", "testing"]

    def test_command_decorator_with_privileges(self):
        """Test command decorator with privileges."""

        @command(
            name="test",
            category=CommandCategory.USER,
            privileges_level=Privileges.MODERATOR,
        )
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.privileges == Privileges.MODERATOR

    def test_command_decorator_with_all_options(self):
        """Test command decorator with all options."""
        pre_hook = AsyncMock()
        post_hook = AsyncMock()
        validator = Mock(spec=CommandValidator)

        @command(
            name="test",
            category=CommandCategory.USER,
            privileges_level=Privileges.MODERATOR,
            triggers=["test", "t"],
            description="Test command",
            detailed_help="Detailed help",
            examples=["!test"],
            usage="!test [args]",
            hidden=True,
            namespace="ns",
            validators=[validator],
            pre_hooks=[pre_hook],
            post_hooks=[post_hook],
        )
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.name == "test"
        assert test_cmd.metadata.triggers == ["test", "t"]
        assert test_cmd.privileges == Privileges.MODERATOR
        assert test_cmd.metadata.description == "Test command"
        assert test_cmd.metadata.detailed_help == "Detailed help"
        assert test_cmd.metadata.examples == ["!test"]
        assert test_cmd.metadata.usage == "!test [args]"
        assert test_cmd.metadata.hidden is True
        assert test_cmd.metadata.namespace == "ns"
        assert test_cmd.metadata.validators == [validator]
        assert test_cmd.metadata.pre_hooks == [pre_hook]
        assert test_cmd.metadata.post_hooks == [post_hook]


class TestConvenienceDecorators:
    """Test convenience decorators for different command categories."""

    def test_user_command_decorator(self):
        """Test user_command decorator sets correct privileges."""

        @user_command(name="test")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.USER
        assert test_cmd.privileges == Privileges.UNRESTRICTED

    def test_nominator_command_decorator(self):
        """Test nominator_command decorator sets correct privileges."""

        @nominator_command(name="test")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.NOMINATOR
        assert test_cmd.privileges == Privileges.NOMINATOR

    def test_moderator_command_decorator(self):
        """Test moderator_command decorator sets correct privileges."""

        @moderator_command(name="test")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.MODERATOR
        assert test_cmd.privileges == Privileges.MODERATOR

    def test_administrator_command_decorator(self):
        """Test administrator_command decorator sets correct privileges."""

        @administrator_command(name="test")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.ADMINISTRATOR
        assert test_cmd.privileges == Privileges.ADMINISTRATOR

    def test_developer_command_decorator(self):
        """Test developer_command decorator sets correct privileges."""

        @developer_command(name="test")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.DEVELOPER
        assert test_cmd.privileges == Privileges.DEVELOPER

    def test_multiplayer_command_decorator(self):
        """Test multiplayer_command decorator sets namespace."""

        @multiplayer_command(name="start")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.MULTIPLAYER
        assert test_cmd.metadata.namespace == "mp"

    def test_mappool_command_decorator(self):
        """Test mappool_command decorator sets namespace."""

        @mappool_command(name="create")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.MAPPOOL
        assert test_cmd.metadata.namespace == "pool"

    def test_clan_command_decorator(self):
        """Test clan_command decorator sets namespace."""

        @clan_command(name="create")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.CLAN
        assert test_cmd.metadata.namespace == "clan"

    def test_season_command_decorator(self):
        """Test season_command decorator sets namespace."""

        @season_command(name="create")
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.category == CommandCategory.SEASON
        assert test_cmd.metadata.namespace == "season"

    def test_convenience_decorators_with_extra_options(self):
        """Test convenience decorators accept additional options."""

        @user_command(name="test", description="Test", hidden=True)
        async def test_cmd(ctx: Context) -> str:
            return "result"

        assert test_cmd.metadata.description == "Test"
        assert test_cmd.metadata.hidden is True


class TestCommandError:
    """Test CommandError exception."""

    def test_command_error_creation(self):
        """Test creating CommandError."""
        error = CommandError("Test error")
        assert str(error) == "Test error"

    def test_command_error_inheritance(self):
        """Test that CommandError inherits from Exception."""
        error = CommandError("Test")
        assert isinstance(error, Exception)


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_creation(self):
        """Test creating ValidationError."""
        error = ValidationError("Validation failed")
        assert str(error) == "Validation failed"

    def test_validation_error_inheritance(self):
        """Test that ValidationError inherits from CommandError."""
        error = ValidationError("Test")
        assert isinstance(error, CommandError)
        assert isinstance(error, Exception)


class TestCommandCategory:
    """Test CommandCategory enum."""

    def test_category_values(self):
        """Test all category values."""
        assert CommandCategory.USER.value == "user"
        assert CommandCategory.NOMINATOR.value == "nominator"
        assert CommandCategory.MODERATOR.value == "moderator"
        assert CommandCategory.ADMINISTRATOR.value == "administrator"
        assert CommandCategory.DEVELOPER.value == "developer"
        assert CommandCategory.MULTIPLAYER.value == "multiplayer"
        assert CommandCategory.MAPPOOL.value == "mappool"
        assert CommandCategory.CLAN.value == "clan"
        assert CommandCategory.SEASON.value == "season"

    def test_category_count(self):
        """Test that all categories are defined."""
        assert len(CommandCategory) == 9
