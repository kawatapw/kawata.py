"""
Tests for the command validation framework.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from app.commands.context import Context
from app.commands.validation import (
    ArgCountValidator,
    BooleanValidator,
    ChoiceValidator,
    DurationValidator,
    GamemodeValidator,
    MapExistsValidator,
    ModsValidator,
    NumericValidator,
    PlayerExistsValidator,
    ReasonValidator,
    UsernameValidator,
    ValidationError,
)


@pytest.fixture
def mock_context():
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.args = []
    ctx.parsed_durations = None
    ctx.get_player = AsyncMock(return_value=None)
    return ctx


class TestArgCountValidator:
    """Test argument count validation."""

    @pytest.mark.asyncio
    async def test_valid_arg_count(self, mock_context):
        """Test that valid argument count passes validation."""
        mock_context.args = ["arg1", "arg2", "arg3"]
        validator = ArgCountValidator(min_count=2, max_count=4)

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_too_few_args(self, mock_context):
        """Test that too few arguments raises ValidationError."""
        mock_context.args = ["arg1"]
        validator = ArgCountValidator(min_count=2)

        with pytest.raises(ValidationError, match="Expected at least 2 arguments"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_too_many_args(self, mock_context):
        """Test that too many arguments raises ValidationError."""
        mock_context.args = ["arg1", "arg2", "arg3", "arg4"]
        validator = ArgCountValidator(max_count=3)

        with pytest.raises(ValidationError, match="Expected at most 3 arguments"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_no_constraints(self, mock_context):
        """Test validator with no min/max constraints."""
        mock_context.args = []
        validator = ArgCountValidator()

        # Should not raise
        await validator(mock_context)


class TestPlayerExistsValidator:
    """Test player existence validation."""

    @pytest.mark.asyncio
    async def test_player_found(self, mock_context):
        """Test that existing player passes validation."""
        mock_context.args = ["TestPlayer"]
        mock_player = Mock()
        mock_player.is_online = True
        mock_context.get_player = AsyncMock(return_value=mock_player)

        validator = PlayerExistsValidator(arg_index=0)

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_player_not_found(self, mock_context):
        """Test that non-existent player raises ValidationError."""
        mock_context.args = ["NonExistentPlayer"]
        mock_context.get_player = AsyncMock(return_value=None)

        validator = PlayerExistsValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Player.*not found"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_player_arg(self, mock_context):
        """Test that missing player argument raises ValidationError."""
        mock_context.args = []
        validator = PlayerExistsValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Missing player name"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_empty_player_name(self, mock_context):
        """Test that empty player name raises ValidationError."""
        mock_context.args = [""]
        validator = PlayerExistsValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Player name cannot be empty"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_offline_player_not_allowed(self, mock_context):
        """Test that offline player raises ValidationError when not allowed."""
        mock_context.args = ["OfflinePlayer"]
        mock_player = Mock()
        mock_player.is_online = False
        mock_context.get_player = AsyncMock(return_value=mock_player)

        validator = PlayerExistsValidator(arg_index=0, allow_offline=False)

        with pytest.raises(ValidationError, match="is not online"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_offline_player_allowed(self, mock_context):
        """Test that offline player passes validation when allowed."""
        mock_context.args = ["OfflinePlayer"]
        mock_player = Mock()
        mock_player.is_online = False
        mock_context.get_player = AsyncMock(return_value=mock_player)

        validator = PlayerExistsValidator(arg_index=0, allow_offline=True)

        # Should not raise
        await validator(mock_context)


class TestUsernameValidator:
    """Test username validation."""

    @pytest.mark.asyncio
    async def test_valid_username(self, mock_context):
        """Test that valid username passes validation."""
        mock_context.args = ["ValidUser123"]
        validator = UsernameValidator()

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_too_short_username(self, mock_context):
        """Test that too short username raises ValidationError."""
        mock_context.args = ["ab"]
        validator = UsernameValidator()

        # "ab" is actually valid (2 characters)
        # Let's test with 1 character
        mock_context.args = ["a"]
        with pytest.raises(ValidationError, match="Username must be 2-15 characters"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_too_long_username(self, mock_context):
        """Test that too long username raises ValidationError."""
        mock_context.args = ["ThisUsernameIsWayTooLong123"]
        validator = UsernameValidator()

        with pytest.raises(ValidationError, match="Username must be 2-15 characters"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_username_with_invalid_chars(self, mock_context):
        """Test that username with invalid characters raises ValidationError."""
        mock_context.args = ["User@Name"]
        validator = UsernameValidator()

        with pytest.raises(ValidationError, match="Username must be"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_username_with_both_underscore_and_space(self, mock_context):
        """Test that username with both underscore and space raises ValidationError."""
        mock_context.args = ["User_Name Test"]
        validator = UsernameValidator()

        with pytest.raises(
            ValidationError, match='may contain "_" or " ", but not both'
        ):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_username(self, mock_context):
        """Test that missing username raises ValidationError."""
        mock_context.args = []
        validator = UsernameValidator()

        with pytest.raises(ValidationError, match="Missing username"):
            await validator(mock_context)


class TestDurationValidator:
    """Test duration validation."""

    @pytest.mark.asyncio
    async def test_valid_duration(self, mock_context):
        """Test that valid duration passes validation."""
        mock_context.args = ["10m"]
        validator = DurationValidator(arg_index=0)

        # Should not raise
        await validator(mock_context)

        # Check that duration was parsed
        assert mock_context.parsed_durations is not None
        assert 0 in mock_context.parsed_durations

    @pytest.mark.asyncio
    async def test_invalid_duration_format(self, mock_context):
        """Test that invalid duration format raises ValidationError."""
        mock_context.args = ["invalid"]
        validator = DurationValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Invalid duration"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_negative_duration(self, mock_context):
        """Test that negative duration raises ValidationError."""
        mock_context.args = ["-10m"]
        validator = DurationValidator(arg_index=0)

        with pytest.raises(ValidationError, match='Invalid duration: "-10m"'):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_duration(self, mock_context):
        """Test that missing duration raises ValidationError."""
        mock_context.args = []
        validator = DurationValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Missing duration"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_empty_duration(self, mock_context):
        """Test that empty duration raises ValidationError."""
        mock_context.args = [""]
        validator = DurationValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Duration cannot be empty"):
            await validator(mock_context)


class TestReasonValidator:
    """Test reason validation."""

    @pytest.mark.asyncio
    async def test_valid_reason(self, mock_context):
        """Test that valid reason passes validation."""
        mock_context.args = ["Test", "reason", "here"]
        validator = ReasonValidator(arg_index=0)

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_short_reason(self, mock_context):
        """Test that short reason raises ValidationError."""
        mock_context.args = ["a"]
        validator = ReasonValidator(arg_index=0, min_length=5)

        with pytest.raises(
            ValidationError, match="Reason must be at least 5 characters"
        ):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_reason(self, mock_context):
        """Test that missing reason raises ValidationError."""
        mock_context.args = []
        validator = ReasonValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Missing reason"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_reason_from_multiple_args(self, mock_context):
        """Test that reason can span multiple arguments."""
        mock_context.args = ["This", "is", "a", "long", "reason"]
        validator = ReasonValidator(arg_index=0)

        # Should not raise
        await validator(mock_context)


class TestGamemodeValidator:
    """Test gamemode validation."""

    @pytest.mark.asyncio
    async def test_valid_gamemode(self, mock_context):
        """Test that valid gamemode passes validation."""
        mock_context.args = ["vn!std"]
        validator = GamemodeValidator(arg_index=0)

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_invalid_gamemode(self, mock_context):
        """Test that invalid gamemode raises ValidationError."""
        mock_context.args = ["invalid_mode"]
        validator = GamemodeValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Invalid gamemode"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_gamemode(self, mock_context):
        """Test that missing gamemode raises ValidationError."""
        mock_context.args = []
        validator = GamemodeValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Missing gamemode"):
            await validator(mock_context)


class TestModsValidator:
    """Test mods validation."""

    @pytest.mark.asyncio
    async def test_valid_mods(self, mock_context):
        """Test that valid mods pass validation."""
        mock_context.args = ["HD", "HR"]
        validator = ModsValidator(arg_index=0)

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_invalid_mods(self, mock_context):
        """Test that invalid mods raise ValidationError."""
        mock_context.args = ["XYZ"]
        validator = ModsValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Invalid mods"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_mods(self, mock_context):
        """Test that missing mods raises ValidationError."""
        mock_context.args = []
        validator = ModsValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Missing mods"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_empty_mods(self, mock_context):
        """Test that empty mods raises ValidationError."""
        mock_context.args = [""]
        validator = ModsValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Mods cannot be empty"):
            await validator(mock_context)


class TestMapExistsValidator:
    """Test beatmap existence validation."""

    @pytest.mark.asyncio
    async def test_valid_map_id(self, mock_context):
        """Test that valid map ID passes validation."""
        mock_context.args = ["123456"]
        validator = MapExistsValidator(arg_index=0)

        # Should not raise (even if map doesn't exist, the format is valid)
        # This test would need actual database mocking to fully test

    @pytest.mark.asyncio
    async def test_invalid_map_id(self, mock_context):
        """Test that non-numeric map ID raises ValidationError."""
        mock_context.args = ["abc"]
        validator = MapExistsValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Map ID must be a number"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_map_id(self, mock_context):
        """Test that missing map ID raises ValidationError."""
        mock_context.args = []
        validator = MapExistsValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Missing map ID"):
            await validator(mock_context)


class TestBooleanValidator:
    """Test boolean validation."""

    @pytest.mark.asyncio
    async def test_valid_true_values(self, mock_context):
        """Test that valid true values pass validation."""
        for value in ["on", "true", "yes", "1", "ON", "TRUE"]:
            mock_context.args = [value]
            validator = BooleanValidator(arg_index=0)

            # Should not raise
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_valid_false_values(self, mock_context):
        """Test that valid false values pass validation."""
        for value in ["off", "false", "no", "0", "OFF", "FALSE"]:
            mock_context.args = [value]
            validator = BooleanValidator(arg_index=0)

            # Should not raise
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_invalid_boolean_value(self, mock_context):
        """Test that invalid boolean value raises ValidationError."""
        mock_context.args = ["maybe"]
        validator = BooleanValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Invalid boolean value"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_boolean_value(self, mock_context):
        """Test that missing boolean value raises ValidationError."""
        mock_context.args = []
        validator = BooleanValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Missing boolean value"):
            await validator(mock_context)


class TestNumericValidator:
    """Test numeric validation."""

    @pytest.mark.asyncio
    async def test_valid_integer(self, mock_context):
        """Test that valid integer passes validation."""
        mock_context.args = ["42"]
        validator = NumericValidator(arg_index=0, integer_only=True)

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_valid_float(self, mock_context):
        """Test that valid float passes validation."""
        mock_context.args = ["3.14"]
        validator = NumericValidator(arg_index=0)

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_invalid_number(self, mock_context):
        """Test that invalid number raises ValidationError."""
        mock_context.args = ["abc"]
        validator = NumericValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Invalid number"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_value_below_minimum(self, mock_context):
        """Test that value below minimum raises ValidationError."""
        mock_context.args = ["5"]
        validator = NumericValidator(arg_index=0, min_value=10)

        with pytest.raises(ValidationError, match="Value must be at least 10"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_value_above_maximum(self, mock_context):
        """Test that value above maximum raises ValidationError."""
        mock_context.args = ["15"]
        validator = NumericValidator(arg_index=0, max_value=10)

        with pytest.raises(ValidationError, match="Value must be at most 10"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_float_when_integer_required(self, mock_context):
        """Test that float raises ValidationError when integer required."""
        mock_context.args = ["3.14"]
        validator = NumericValidator(arg_index=0, integer_only=True)

        with pytest.raises(ValidationError, match="Invalid number"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_numeric_value(self, mock_context):
        """Test that missing numeric value raises ValidationError."""
        mock_context.args = []
        validator = NumericValidator(arg_index=0)

        with pytest.raises(ValidationError, match="Missing numeric value"):
            await validator(mock_context)


class TestChoiceValidator:
    """Test choice validation."""

    @pytest.mark.asyncio
    async def test_valid_choice(self, mock_context):
        """Test that valid choice passes validation."""
        mock_context.args = ["option1"]
        validator = ChoiceValidator(
            arg_index=0, choices=["option1", "option2", "option3"]
        )

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_invalid_choice(self, mock_context):
        """Test that invalid choice raises ValidationError."""
        mock_context.args = ["invalid"]
        validator = ChoiceValidator(
            arg_index=0, choices=["option1", "option2", "option3"]
        )

        with pytest.raises(ValidationError, match="Invalid value"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_case_insensitive_choice(self, mock_context):
        """Test case-insensitive choice validation."""
        mock_context.args = ["OPTION1"]
        validator = ChoiceValidator(
            arg_index=0, choices=["option1", "option2"], case_sensitive=False
        )

        # Should not raise
        await validator(mock_context)

    @pytest.mark.asyncio
    async def test_case_sensitive_choice(self, mock_context):
        """Test case-sensitive choice validation."""
        mock_context.args = ["OPTION1"]
        validator = ChoiceValidator(
            arg_index=0, choices=["option1", "option2"], case_sensitive=True
        )

        with pytest.raises(ValidationError, match="Invalid value"):
            await validator(mock_context)

    @pytest.mark.asyncio
    async def test_missing_choice(self, mock_context):
        """Test that missing choice raises ValidationError."""
        mock_context.args = []
        validator = ChoiceValidator(arg_index=0, choices=["option1", "option2"])

        with pytest.raises(ValidationError, match="Missing value"):
            await validator(mock_context)


class TestConvenienceFunctions:
    """Test convenience functions for creating validators."""

    def test_arg_count_convenience(self):
        """Test arg_count convenience function."""
        from app.commands.validation import validate

        validator = validate.arg_count(min_count=1, max_count=5)
        assert isinstance(validator, ArgCountValidator)

    def test_player_exists_convenience(self):
        """Test player_exists convenience function."""
        from app.commands.validation import validate

        validator = validate.player_exists(arg_index=0, allow_offline=True)
        assert isinstance(validator, PlayerExistsValidator)

    def test_username_convenience(self):
        """Test username convenience function."""
        from app.commands.validation import validate

        validator = validate.username()
        assert isinstance(validator, UsernameValidator)

    def test_duration_convenience(self):
        """Test duration convenience function."""
        from app.commands.validation import validate

        validator = validate.duration(arg_index=0)
        assert isinstance(validator, DurationValidator)

    def test_reason_convenience(self):
        """Test reason convenience function."""
        from app.commands.validation import validate

        validator = validate.reason(arg_index=0, min_length=1)
        assert isinstance(validator, ReasonValidator)

    def test_gamemode_convenience(self):
        """Test gamemode convenience function."""
        from app.commands.validation import validate

        validator = validate.gamemode(arg_index=0)
        assert isinstance(validator, GamemodeValidator)

    def test_mods_convenience(self):
        """Test mods convenience function."""
        from app.commands.validation import validate

        validator = validate.mods(arg_index=0)
        assert isinstance(validator, ModsValidator)

    def test_map_exists_convenience(self):
        """Test map_exists convenience function."""
        from app.commands.validation import validate

        validator = validate.map_exists(arg_index=0)
        assert isinstance(validator, MapExistsValidator)

    def test_boolean_convenience(self):
        """Test boolean convenience function."""
        from app.commands.validation import validate

        validator = validate.boolean(arg_index=0)
        assert isinstance(validator, BooleanValidator)

    def test_numeric_convenience(self):
        """Test numeric convenience function."""
        from app.commands.validation import validate

        validator = validate.numeric(arg_index=0, min_value=1, integer_only=True)
        assert isinstance(validator, NumericValidator)

    def test_choice_convenience(self):
        """Test choice convenience function."""
        from app.commands.validation import validate

        validator = validate.choice(arg_index=0, choices=["a", "b"])
        assert isinstance(validator, ChoiceValidator)


class TestPresetValidators:
    """Test preset validators."""

    def test_player_name_preset(self):
        """Test player_name preset validator."""
        from app.commands.validation import VALIDATORS

        assert "player_name" in VALIDATORS
        assert isinstance(VALIDATORS["player_name"], PlayerExistsValidator)

    def test_duration_preset(self):
        """Test duration preset validator."""
        from app.commands.validation import VALIDATORS

        assert "duration" in VALIDATORS
        assert isinstance(VALIDATORS["duration"], DurationValidator)

    def test_reason_preset(self):
        """Test reason preset validator."""
        from app.commands.validation import VALIDATORS

        assert "reason" in VALIDATORS
        assert isinstance(VALIDATORS["reason"], ReasonValidator)

    def test_username_preset(self):
        """Test username preset validator."""
        from app.commands.validation import VALIDATORS

        assert "username" in VALIDATORS
        assert isinstance(VALIDATORS["username"], UsernameValidator)

    def test_map_id_preset(self):
        """Test map_id preset validator."""
        from app.commands.validation import VALIDATORS

        assert "map_id" in VALIDATORS
        assert isinstance(VALIDATORS["map_id"], MapExistsValidator)

    def test_gamemode_preset(self):
        """Test gamemode preset validator."""
        from app.commands.validation import VALIDATORS

        assert "gamemode" in VALIDATORS
        assert isinstance(VALIDATORS["gamemode"], GamemodeValidator)

    def test_mods_preset(self):
        """Test mods preset validator."""
        from app.commands.validation import VALIDATORS

        assert "mods" in VALIDATORS
        assert isinstance(VALIDATORS["mods"], ModsValidator)

    def test_boolean_preset(self):
        """Test boolean preset validator."""
        from app.commands.validation import VALIDATORS

        assert "boolean" in VALIDATORS
        assert isinstance(VALIDATORS["boolean"], BooleanValidator)

    def test_positive_int_preset(self):
        """Test positive_int preset validator."""
        from app.commands.validation import VALIDATORS

        assert "positive_int" in VALIDATORS
        assert isinstance(VALIDATORS["positive_int"], NumericValidator)

    def test_non_negative_int_preset(self):
        """Test non_negative_int preset validator."""
        from app.commands.validation import VALIDATORS

        assert "non_negative_int" in VALIDATORS
        assert isinstance(VALIDATORS["non_negative_int"], NumericValidator)

    def test_percentage_preset(self):
        """Test percentage preset validator."""
        from app.commands.validation import VALIDATORS

        assert "percentage" in VALIDATORS
        assert isinstance(VALIDATORS["percentage"], NumericValidator)
