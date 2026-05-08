"""
API v2 Models Package - Pydantic Data Models for API Responses

This module provides the foundational Pydantic BaseModel class and type
utilities for all v2 API response models. It establishes the base
configuration and utility methods that all API response models inherit,
ensuring consistent data validation and serialization across the v2 API.

The module defines a custom BaseModel class that extends Pydantic's
functionality with application-specific configurations and helper methods
for creating model instances from database query results and other
mapping structures.

Key Features:
    - Custom Pydantic BaseModel with application-specific configuration
    - Automatic whitespace stripping for string fields
    - Type-safe model creation from mapping structures
    - Generic type variable for model inheritance
    - Consistent data validation across all API models
    - Integration with FastAPI response serialization

Integration Points:
    - Clan models in app/api/v2/models/clans.py
    - Map models in app/api/v2/models/maps.py
    - Player models in app/api/v2/models/players.py
    - Score models in app/api/v2/models/scores.py
    - API endpoints in app/api/v2/
    - Database repositories in app/repositories/

Model Configuration:
    - str_strip_whitespace: Automatically strips whitespace from string fields
    - Ensures clean data presentation in API responses
    - Reduces data transfer size by removing unnecessary whitespace

Usage Pattern:
    # Create a model from database mapping
    from app.api.v2.models import BaseModel

    class PlayerModel(BaseModel):
        id: int
        name: str
        country: str

    # Create from database row
    player_data = {"id": 123, "name": "Player", "country": "US"}
    player = PlayerModel.from_mapping(player_data)

    # Use in API endpoint
    @router.get("/players/{player_id}")
    async def get_player(player_id: int) -> PlayerModel:
        data = await users_repo.fetch_one(id=player_id)
        return PlayerModel.from_mapping(data)

Related Files:
    - app/api/v2/models/clans.py: Clan data models
    - app/api/v2/models/maps.py: Map data models
    - app/api/v2/models/players.py: Player data models
    - app/api/v2/models/scores.py: Score data models
    - app/api/v2/common/responses.py: Response formatting utilities
"""

# isort: dont-add-imports
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from typing import TypeVar

from pydantic import BaseModel as _pydantic_BaseModel
from pydantic import ConfigDict

T = TypeVar("T", bound="BaseModel")


class BaseModel(_pydantic_BaseModel):
    """Base Pydantic model for all v2 API response models.

    This class extends Pydantic's BaseModel with application-specific
    configurations and utility methods for creating model instances
    from database query results and other mapping structures.

    Attributes:
        model_config: Configuration for whitespace stripping and validation
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    @classmethod
    def from_mapping(cls: type[T], mapping: Mapping[str, Any]) -> T:
        """Create a model instance from a mapping structure.

        This method allows easy creation of Pydantic models from database
        query results or other dictionary-like structures, using only the
        fields defined in the model.

        Args:
            mapping: A mapping structure (e.g., database row) with model fields

        Returns:
            A new instance of the model with data from the mapping
        """
        return cls(**{k: mapping[k] for k in cls.model_fields})
