"""
Command Validation Framework

Provides built-in validators and validation utilities for command arguments.
"""

from __future__ import annotations

from typing import Any

from pytimeparse.timeparse import timeparse

from app.commands.base import ValidationError
from app.commands.context import Context
from app.constants import regexes
from app.constants.gamemodes import GAMEMODE_REPR_LIST
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap


class Validator:
    """Base validator class."""

    async def __call__(self, ctx: Context, *args: Any) -> None:
        """Validate arguments."""
        raise NotImplementedError


class ArgCountValidator(Validator):
    """Validates argument count."""

    def __init__(self, min_count: int | None = None, max_count: int | None = None):
        self.min_count = min_count
        self.max_count = max_count

    async def __call__(self, ctx: Context, *args: Any) -> None:
        count = len(ctx.args)
        if self.min_count is not None and count < self.min_count:
            raise ValidationError(
                f"Expected at least {self.min_count} arguments, got {count}"
            )
        if self.max_count is not None and count > self.max_count:
            raise ValidationError(
                f"Expected at most {self.max_count} arguments, got {count}"
            )


class PlayerExistsValidator(Validator):
    """Validates that a player exists."""

    def __init__(self, arg_index: int = 0, allow_offline: bool = True):
        self.arg_index = arg_index
        self.allow_offline = allow_offline

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(
                f"Missing player name at argument {self.arg_index + 1}"
            )

        player_name = ctx.args[self.arg_index]
        if not player_name:
            raise ValidationError("Player name cannot be empty")

        player = await ctx.get_player(player_name)
        if not player:
            raise ValidationError(f'Player "{player_name}" not found')

        if not self.allow_offline and not player.is_online:
            raise ValidationError(f'Player "{player_name}" is not online')


class UsernameValidator(Validator):
    """Validates a username format."""

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if not ctx.args:
            raise ValidationError("Missing username")

        username = ctx.args[0]
        if not regexes.USERNAME.match(username):
            raise ValidationError(
                "Username must be 2-15 characters long, "
                "and can only contain letters, numbers, hyphens, and underscores"
            )

        if "_" in username and " " in username:
            raise ValidationError('Username may contain "_" or " ", but not both')


class DurationValidator(Validator):
    """Validates a duration string."""

    def __init__(self, arg_index: int = 0):
        self.arg_index = arg_index

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(f"Missing duration at argument {self.arg_index + 1}")

        duration_str = ctx.args[self.arg_index]
        if not duration_str:
            raise ValidationError("Duration cannot be empty")

        try:
            duration = timeparse(duration_str)
        except Exception as e:
            raise ValidationError(f'Invalid duration: "{duration_str}"') from e

        if duration is None:
            raise ValidationError(f'Invalid duration format: "{duration_str}"')

        if duration <= 0:
            raise ValidationError("Duration must be positive")

        # Store parsed duration for later use
        if ctx.parsed_durations is None:
            ctx.parsed_durations = {}
        ctx.parsed_durations[self.arg_index] = duration


class ReasonValidator(Validator):
    """Validates a reason string."""

    def __init__(self, arg_index: int = 0, min_length: int = 1):
        self.arg_index = arg_index
        self.min_length = min_length

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(f"Missing reason at argument {self.arg_index + 1}")

        reason = " ".join(ctx.args[self.arg_index :])
        if len(reason) < self.min_length:
            raise ValidationError(
                f"Reason must be at least {self.min_length} characters"
            )


class GamemodeValidator(Validator):
    """Validates a gamemode string."""

    def __init__(self, arg_index: int = 0):
        self.arg_index = arg_index

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(f"Missing gamemode at argument {self.arg_index + 1}")

        mode_str = ctx.args[self.arg_index]
        if mode_str not in GAMEMODE_REPR_LIST:
            raise ValidationError(
                f"Invalid gamemode: {mode_str}. "
                f"Valid modes: {', '.join(GAMEMODE_REPR_LIST)}"
            )


class ModsValidator(Validator):
    """Validates mod string."""

    def __init__(self, arg_index: int = 0, gamemode_arg_index: int | None = None):
        self.arg_index = arg_index
        self.gamemode_arg_index = gamemode_arg_index

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(f"Missing mods at argument {self.arg_index + 1}")

        mods_str = ctx.args[self.arg_index]
        if not mods_str:
            raise ValidationError("Mods cannot be empty")

        try:
            mods = Mods.from_modstr(mods_str)

            # Validate against gamemode if provided
            if self.gamemode_arg_index is not None and self.gamemode_arg_index < len(
                ctx.args
            ):
                mode_str = ctx.args[self.gamemode_arg_index]
                if mode_str in GAMEMODE_REPR_LIST:
                    mode_index = GAMEMODE_REPR_LIST.index(mode_str)
                    mods = mods.filter_invalid_combos(mode_index)
        except Exception as e:
            raise ValidationError(f'Invalid mods: "{mods_str}"') from e

        # Check if no valid mods were found
        if mods == Mods.NOMOD:
            raise ValidationError(f'Invalid mods: "{mods_str}"')


class MapExistsValidator(Validator):
    """Validates that a beatmap exists."""

    def __init__(self, arg_index: int = 0):
        self.arg_index = arg_index

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(f"Missing map ID at argument {self.arg_index + 1}")

        map_id_str = ctx.args[self.arg_index]
        if not map_id_str.isdigit():
            raise ValidationError(f"Map ID must be a number, got: {map_id_str}")

        map_id = int(map_id_str)
        bmap = await Beatmap.from_bid(map_id)
        if not bmap:
            raise ValidationError(f"Beatmap with ID {map_id} not found")


class BooleanValidator(Validator):
    """Validates a boolean-like argument."""

    def __init__(
        self,
        arg_index: int = 0,
        true_values: list[str] | None = None,
        false_values: list[str] | None = None,
    ):
        self.arg_index = arg_index
        self.true_values = true_values or ["on", "true", "yes", "1"]
        self.false_values = false_values or ["off", "false", "no", "0"]

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(
                f"Missing boolean value at argument {self.arg_index + 1}"
            )

        value = ctx.args[self.arg_index].lower()
        if value not in self.true_values and value not in self.false_values:
            valid_values = ", ".join(self.true_values + self.false_values)
            raise ValidationError(
                f"Invalid boolean value: {value}. Valid values: {valid_values}"
            )


class NumericValidator(Validator):
    """Validates a numeric argument."""

    def __init__(
        self,
        arg_index: int = 0,
        min_value: float | None = None,
        max_value: float | None = None,
        integer_only: bool = False,
    ):
        self.arg_index = arg_index
        self.min_value = min_value
        self.max_value = max_value
        self.integer_only = integer_only

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(
                f"Missing numeric value at argument {self.arg_index + 1}"
            )

        value_str = ctx.args[self.arg_index]
        try:
            if self.integer_only:
                value: float = float(int(value_str))
            else:
                value = float(value_str)
        except ValueError as e:
            raise ValidationError(f'Invalid number: "{value_str}"') from e

        if self.min_value is not None and value < self.min_value:
            raise ValidationError(f"Value must be at least {self.min_value}")

        if self.max_value is not None and value > self.max_value:
            raise ValidationError(f"Value must be at most {self.max_value}")


class ChoiceValidator(Validator):
    """Validates that an argument is one of a set of choices."""

    def __init__(
        self,
        arg_index: int = 0,
        choices: list[str] | None = None,
        case_sensitive: bool = False,
    ):
        self.arg_index = arg_index
        self.choices = choices or []
        self.case_sensitive = case_sensitive

    async def __call__(self, ctx: Context, *args: Any) -> None:
        if self.arg_index >= len(ctx.args):
            raise ValidationError(f"Missing value at argument {self.arg_index + 1}")

        value = ctx.args[self.arg_index]
        if not self.case_sensitive:
            value_lower = value.lower()
            choices_lower = [c.lower() for c in self.choices]
            if value_lower not in choices_lower:
                raise ValidationError(
                    f'Invalid value: "{value}". '
                    f"Valid choices: {', '.join(self.choices)}"
                )
        elif value not in self.choices:
            raise ValidationError(
                f'Invalid value: "{value}". Valid choices: {", ".join(self.choices)}'
            )


# Convenience functions for creating validators
def arg_count(
    min_count: int | None = None, max_count: int | None = None
) -> ArgCountValidator:
    """Create an argument count validator."""
    return ArgCountValidator(min_count, max_count)


def player_exists(
    arg_index: int = 0, allow_offline: bool = True
) -> PlayerExistsValidator:
    """Create a player exists validator."""
    return PlayerExistsValidator(arg_index, allow_offline)


def username() -> UsernameValidator:
    """Create a username validator."""
    return UsernameValidator()


def duration(arg_index: int = 0) -> DurationValidator:
    """Create a duration validator."""
    return DurationValidator(arg_index)


def reason(arg_index: int = 0, min_length: int = 1) -> ReasonValidator:
    """Create a reason validator."""
    return ReasonValidator(arg_index, min_length)


def gamemode(arg_index: int = 0) -> GamemodeValidator:
    """Create a gamemode validator."""
    return GamemodeValidator(arg_index)


def mods(arg_index: int = 0, gamemode_arg_index: int | None = None) -> ModsValidator:
    """Create a mods validator."""
    return ModsValidator(arg_index, gamemode_arg_index)


def map_exists(arg_index: int = 0) -> MapExistsValidator:
    """Create a beatmap exists validator."""
    return MapExistsValidator(arg_index)


def boolean(arg_index: int = 0) -> BooleanValidator:
    """Create a boolean validator."""
    return BooleanValidator(arg_index)


def numeric(
    arg_index: int = 0,
    min_value: float | None = None,
    max_value: float | None = None,
    integer_only: bool = False,
) -> NumericValidator:
    """Create a numeric validator."""
    return NumericValidator(arg_index, min_value, max_value, integer_only)


def choice(
    arg_index: int = 0,
    choices: list[str] | None = None,
    case_sensitive: bool = False,
) -> ChoiceValidator:
    """Create a choice validator."""
    return ChoiceValidator(arg_index, choices, case_sensitive)


# Preset validators for common patterns
VALIDATORS = {
    "player_name": player_exists(0),
    "duration": duration(1),
    "reason": reason(2),
    "username": username(),
    "map_id": map_exists(0),
    "gamemode": gamemode(0),
    "mods": mods(0),
    "boolean": boolean(0),
    "positive_int": numeric(0, min_value=1, integer_only=True),
    "non_negative_int": numeric(0, min_value=0, integer_only=True),
    "percentage": numeric(0, min_value=0, max_value=100),
}


# Convenience class for accessing validators
class validate:
    """Convenience class for accessing validators."""

    arg_count = arg_count
    player_exists = player_exists
    username = username
    duration = duration
    reason = reason
    gamemode = gamemode
    mods = mods
    map_exists = map_exists
    boolean = boolean
    numeric = numeric
    choice = choice
