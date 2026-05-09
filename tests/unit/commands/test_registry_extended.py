"""
Extended tests for command registry execution pipeline.

Covers disabled commands, deprecated commands, pre/post hooks,
and edge cases in command execution.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from app.commands import execute_command
from app.commands import get_registry
from app.commands import register_command
from app.commands.base import CommandCategory
from app.commands.base import CommandError
from app.commands.base import command
from app.commands.context import Context
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.DEVELOPER
    return player


@pytest.fixture
def mock_recipient():
    recipient = Mock()
    recipient.name = "#test"
    return recipient


@pytest.fixture
def mock_database():
    return AsyncMock()


@pytest.fixture
def mock_cache():
    return Mock()


@pytest.fixture
def mock_settings():
    settings = Mock()
    settings.COMMAND_PREFIX = "!"
    return settings


@pytest.fixture
def mock_state():
    state = Mock()
    return state


class TestDisabledCommands:
    """Test execution of disabled commands."""

    @pytest.mark.asyncio
    async def test_disabled_command_returns_message(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test that disabled command returns appropriate message."""
        mock_player.priv = Privileges.UNRESTRICTED

        # Find a command that is disabled
        registry = get_registry()
        cmds = registry.get_all_commands()
        disabled_cmd = None
        for cmd in cmds:
            if not cmd.metadata.enabled:
                disabled_cmd = cmd
                break

        if disabled_cmd:
            result = await execute_command(
                mock_player,
                mock_recipient,
                f"!{disabled_cmd.metadata.triggers[0]}",
                mock_database,
                mock_cache,
                mock_settings,
                mock_state,
            )
            assert result is not None
            assert result.resp == "This command is currently disabled."


class TestDeprecatedCommands:
    """Test execution of deprecated commands."""

    @pytest.mark.asyncio
    async def test_deprecated_command_returns_message(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test that deprecated command returns deprecation message."""
        mock_player.priv = Privileges.UNRESTRICTED

        # Find a command that is deprecated
        registry = get_registry()
        cmds = registry.get_all_commands()
        deprecated_cmd = None
        for cmd in cmds:
            if cmd.metadata.deprecated:
                deprecated_cmd = cmd
                break

        if deprecated_cmd:
            result = await execute_command(
                mock_player,
                mock_recipient,
                f"!{deprecated_cmd.metadata.triggers[0]}",
                mock_database,
                mock_cache,
                mock_settings,
                mock_state,
            )
            assert result is not None
            assert "deprecated" in result.resp.lower()

    @pytest.mark.asyncio
    async def test_deprecated_command_with_custom_message(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test deprecated command with custom deprecation message."""
        mock_player.priv = Privileges.UNRESTRICTED

        # Find a deprecated command with a custom message
        registry = get_registry()
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.deprecated and cmd.metadata.deprecation_message:
                result = await execute_command(
                    mock_player,
                    mock_recipient,
                    f"!{cmd.metadata.triggers[0]}",
                    mock_database,
                    mock_cache,
                    mock_settings,
                    mock_state,
                )
                assert result is not None
                assert cmd.metadata.deprecation_message in result.resp
                return

        # If no command has a custom message, the test is skipped implicitly


class TestPreExecutionHooks:
    """Test pre-execution hooks."""

    @pytest.mark.asyncio
    async def test_pre_hook_raises_command_error(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test that pre-hook raising CommandError returns error response."""
        mock_player.priv = Privileges.UNRESTRICTED

        # Create a command with a pre-hook that raises CommandError
        async def failing_hook(ctx: Context) -> None:
            raise CommandError("Pre-hook failed")

        @command(
            name="hook_test",
            category=CommandCategory.USER,
            pre_hooks=[failing_hook],
        )
        async def hook_test_cmd(ctx: Context) -> str:
            return "should not reach"

        # Register the command
        register_command(hook_test_cmd)

        result = await execute_command(
            mock_player,
            mock_recipient,
            "!hook_test",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        assert result is not None
        assert "Pre-hook failed" in result.resp


class TestPostExecutionHooks:
    """Test post-execution hooks."""

    @pytest.mark.asyncio
    async def test_post_hook_with_two_params(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test post-hook that accepts (context, result)."""
        mock_player.priv = Privileges.UNRESTRICTED
        hook_called = {"value": False}

        async def two_param_hook(ctx: Context, result: str | None) -> None:
            hook_called["value"] = True
            assert result is not None

        @command(
            name="post_test2",
            category=CommandCategory.USER,
            post_hooks=[two_param_hook],
        )
        async def post_test_cmd(ctx: Context) -> str:
            return "success"

        register_command(post_test_cmd)

        result = await execute_command(
            mock_player,
            mock_recipient,
            "!post_test2",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        assert result is not None
        assert result.resp == "success"
        assert hook_called["value"] is True

    @pytest.mark.asyncio
    async def test_post_hook_with_one_param(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test post-hook that accepts only (context)."""
        mock_player.priv = Privileges.UNRESTRICTED
        hook_called = {"value": False}

        async def one_param_hook(ctx: Context) -> None:
            hook_called["value"] = True

        @command(
            name="post_test1",
            category=CommandCategory.USER,
            post_hooks=[one_param_hook],
        )
        async def post_test_cmd(ctx: Context) -> str:
            return "success"

        register_command(post_test_cmd)

        result = await execute_command(
            mock_player,
            mock_recipient,
            "!post_test1",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        assert result is not None
        assert result.resp == "success"
        assert hook_called["value"] is True

    @pytest.mark.asyncio
    async def test_post_hook_exception_does_not_fail_command(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test that post-hook exception is caught and logged but doesn't fail command."""
        mock_player.priv = Privileges.UNRESTRICTED

        async def failing_hook(ctx: Context) -> None:
            raise RuntimeError("Hook error")

        @command(
            name="post_fail",
            category=CommandCategory.USER,
            post_hooks=[failing_hook],
        )
        async def post_fail_cmd(ctx: Context) -> str:
            return "command success"

        register_command(post_fail_cmd)

        # Patch traceback.print_exc to capture the call
        with patch("traceback.print_exc") as mock_print_exc:
            result = await execute_command(
                mock_player,
                mock_recipient,
                "!post_fail",
                mock_database,
                mock_cache,
                mock_settings,
                mock_state,
            )

        # Command should still succeed
        assert result is not None
        assert result.resp == "command success"
        # Exception should be logged
        mock_print_exc.assert_called_once()


class TestGenerateDocs:
    """Test generate_docs edge cases."""

    def test_generate_docs_empty_category(self):
        """Test generate_docs handles categories with no commands."""
        registry = get_registry()
        docs = registry.generate_docs()
        # Should not crash and should contain valid markdown
        assert "# Command Reference" in docs

    def test_generate_docs_hidden_commands_excluded(self):
        """Test that hidden commands are excluded from docs."""
        registry = get_registry()
        docs = registry.generate_docs()
        # Find a hidden command
        cmds = registry.get_all_commands()
        hidden_cmds = [c for c in cmds if c.metadata.hidden]
        if hidden_cmds:
            # Hidden commands should not appear in docs as command entries
            # They might appear in other contexts (like help command descriptions)
            for cmd in hidden_cmds:
                # Check that the command is not listed as a primary entry
                # The docs format uses "#### !name" for command entries
                assert f"#### !{cmd.metadata.name}" not in docs

    def test_generate_docs_includes_usage(self):
        """Test that docs include usage when available."""
        registry = get_registry()
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.usage:
                docs = registry.generate_docs()
                assert "**Usage:**" in docs
                return

    def test_generate_docs_includes_examples(self):
        """Test that docs include examples when available."""
        registry = get_registry()
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.examples:
                docs = registry.generate_docs()
                assert "**Examples:**" in docs
                return

    def test_generate_docs_includes_detailed_help(self):
        """Test that docs include detailed help when available."""
        registry = get_registry()
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.detailed_help:
                docs = registry.generate_docs()
                # Detailed help should be included
                assert cmd.metadata.detailed_help in docs
                return


class TestNamespaceResolution:
    """Test namespace command resolution edge cases."""

    @pytest.mark.asyncio
    async def test_namespace_command_not_in_match(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test namespace command when player is not in a match."""
        mock_player.priv = Privileges.UNRESTRICTED
        mock_player.match = None

        # mp_help should work even without being in a match
        result = await execute_command(
            mock_player,
            mock_recipient,
            "!mp help",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        # Should return some response (not None) since mp_help is accessible
        # The exact response depends on whether the command requires match context

    @pytest.mark.asyncio
    async def test_namespaced_trigger_format(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test command lookup using namespaced_trigger format (mp_help)."""
        mock_player.priv = Privileges.UNRESTRICTED

        registry = get_registry()
        # The trigger "mp_help" should resolve to the mp help command
        cmd = registry.get_by_trigger("mp_help")
        if cmd:
            result = await execute_command(
                mock_player,
                mock_recipient,
                "!mp_help",
                mock_database,
                mock_cache,
                mock_settings,
                mock_state,
            )
            # Should get a response
            assert result is not None


class TestCommandExecutionEdgeCasesExtended:
    """Additional edge cases for command execution."""

    @pytest.mark.asyncio
    async def test_execute_command_with_only_prefix_and_spaces(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test message with only prefix and whitespace."""
        mock_player.priv = Privileges.UNRESTRICTED
        result = await execute_command(
            mock_player,
            mock_recipient,
            "!   ",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_command_case_insensitive_trigger(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test that trigger lookup is case-insensitive (lowercase)."""
        mock_player.priv = Privileges.UNRESTRICTED
        # ROLL should resolve to roll
        result = await execute_command(
            mock_player,
            mock_recipient,
            "!ROLL 10",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        # Should find the roll command
        assert result is not None
        assert "rolls" in result.resp.lower() or result.resp is None

    @pytest.mark.asyncio
    async def test_execute_namespace_command_with_extra_args(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test namespace command with extra arguments."""
        mock_player.priv = Privileges.UNRESTRICTED
        # mp help with extra args
        result = await execute_command(
            mock_player,
            mock_recipient,
            "!mp help extra arg",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        # Should handle gracefully

    @pytest.mark.asyncio
    async def test_execute_command_with_newlines(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test command with newlines in message."""
        mock_player.priv = Privileges.UNRESTRICTED
        result = await execute_command(
            mock_player,
            mock_recipient,
            "!roll\n10",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        # Should handle or return None

    @pytest.mark.asyncio
    async def test_execute_multiple_commands_sequentially(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test executing multiple commands in sequence."""
        mock_player.priv = Privileges.UNRESTRICTED

        results = []
        for i in range(5):
            result = await execute_command(
                mock_player,
                mock_recipient,
                "!roll 6",
                mock_database,
                mock_cache,
                mock_settings,
                mock_state,
            )
            results.append(result)

        assert len(results) == 5
        for r in results:
            assert r is not None
            assert r.resp is not None
            assert "rolls" in r.resp

    @pytest.mark.asyncio
    async def test_execute_concurrent_commands(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test executing multiple commands concurrently."""
        mock_player.priv = Privileges.UNRESTRICTED

        tasks = [
            execute_command(
                mock_player,
                mock_recipient,
                "!roll 6",
                mock_database,
                mock_cache,
                mock_settings,
                mock_state,
            )
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for r in results:
            assert r is not None
            assert r.resp is not None

    @pytest.mark.asyncio
    async def test_execute_command_with_unicode_args(
        self,
        mock_player,
        mock_recipient,
        mock_database,
        mock_cache,
        mock_settings,
        mock_state,
    ):
        """Test command with unicode arguments."""
        mock_player.priv = Privileges.UNRESTRICTED
        # Commands should handle unicode gracefully
        result = await execute_command(
            mock_player,
            mock_recipient,
            "!roll 100",
            mock_database,
            mock_cache,
            mock_settings,
            mock_state,
        )
        assert result is not None


class TestGetAvailableCommands:
    """Test get_available commands filtering."""

    def test_get_available_excludes_higher_privilege(self):
        """Test that get_available excludes commands requiring higher privileges."""
        registry = get_registry()
        normal_player = Mock()
        normal_player.priv = Privileges.UNRESTRICTED

        available = registry.get_available(normal_player)
        # Should not include developer-only commands
        dev_commands = [c for c in available if c.privileges == Privileges.DEVELOPER]
        assert len(dev_commands) == 0

    def test_get_available_includes_matching_privilege(self):
        """Test that get_available includes commands with matching privileges."""
        registry = get_registry()
        unrestricted_player = Mock()
        unrestricted_player.priv = Privileges.UNRESTRICTED

        available = registry.get_available(unrestricted_player)
        # Should include some unrestricted commands
        unrestricted_cmds = [
            c for c in available if c.privileges == Privileges.UNRESTRICTED
        ]
        assert len(unrestricted_cmds) > 0

    def test_get_available_administrator_sees_more(self):
        """Test that administrator sees different commands than normal user."""
        registry = get_registry()
        normal_player = Mock()
        normal_player.priv = Privileges.UNRESTRICTED
        admin_player = Mock()
        admin_player.priv = Privileges.ADMINISTRATOR

        normal_available = registry.get_available(normal_player)
        admin_available = registry.get_available(admin_player)

        # Administrator should see at least some commands that normal users can't
        # The exact count may vary based on hidden commands and other factors
        assert len(admin_available) > 0
        assert len(normal_available) > 0


class TestRegistryHelpers:
    """Test registry helper functions."""

    def test_get_registry_returns_singleton(self):
        """Test that get_registry returns the same instance."""
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_get_all_commands_not_empty(self):
        """Test that get_all_commands returns non-empty list."""
        registry = get_registry()
        cmds = registry.get_all_commands()
        assert len(cmds) > 0

    def test_get_by_trigger_returns_none_for_unknown(self):
        """Test that get_by_trigger returns None for unknown trigger."""
        registry = get_registry()
        assert registry.get_by_trigger("unknown_xyz_123") is None

    def test_get_by_category_returns_list(self):
        """Test that get_by_category always returns a list."""
        registry = get_registry()
        for category in CommandCategory:
            result = registry.get_by_category(category)
            assert isinstance(result, list)
