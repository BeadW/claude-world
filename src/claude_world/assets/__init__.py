"""Asset management for Claude World."""

from __future__ import annotations

from .sprite_definitions import (
    SPRITE_DEFINITIONS,
    ANIMATION_DEFINITIONS,
    create_all_sprites,
    get_sprite_definition,
)
from .placeholder_generator import PlaceholderGenerator

__all__ = [
    "SPRITE_DEFINITIONS",
    "ANIMATION_DEFINITIONS",
    "create_all_sprites",
    "get_sprite_definition",
    "PlaceholderGenerator",
]
