"""Sprite loading and management."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from claude_world.types import Sprite, Animation, AnimationFrame


class SpriteLoader:
    """Loads and caches sprites."""

    def __init__(self, asset_path: Optional[Path] = None):
        """Initialize the sprite loader.

        Args:
            asset_path: Base path for sprite assets.
        """
        self._asset_path = asset_path or Path("assets/sprites")
        self._cache: dict[str, Sprite] = {}

    def create_placeholder_sprite(
        self,
        sprite_id: str,
        width: int,
        height: int,
        animations: Optional[dict[str, Animation]] = None,
    ) -> Sprite:
        """Create a placeholder sprite for testing or fallback.

        Args:
            sprite_id: Unique identifier for the sprite.
            width: Width in pixels.
            height: Height in pixels.
            animations: Optional animations dict.

        Returns:
            A placeholder Sprite.
        """
        if animations is None:
            # Create default idle animation
            animations = {
                "idle": Animation(
                    name="idle",
                    frames=[
                        AnimationFrame(
                            region=(0, 0, width, height),
                            duration_ms=500,
                        )
                    ],
                    loop=True,
                )
            }

        return Sprite(
            id=sprite_id,
            path=None,
            width=width,
            height=height,
            anchor=(width // 2, height),  # Center bottom
            animations=animations,
        )

    def load(self, sprite_id: str) -> Optional[Sprite]:
        """Load a sprite by ID.

        Args:
            sprite_id: The sprite identifier.

        Returns:
            The loaded Sprite or None if not found.
        """
        if sprite_id in self._cache:
            return self._cache[sprite_id]

        # Try to load from file
        sprite_path = self._asset_path / f"{sprite_id}.png"
        if sprite_path.exists():
            sprite = self._load_from_file(sprite_id, sprite_path)
            self._cache[sprite_id] = sprite
            return sprite

        return None

    def _load_from_file(self, sprite_id: str, path: Path) -> Sprite:
        """Load sprite from a PNG file.

        Args:
            sprite_id: The sprite identifier.
            path: Path to the PNG file.

        Returns:
            The loaded Sprite.
        """
        try:
            from PIL import Image

            with Image.open(path) as img:
                width, height = img.size
        except ImportError:
            # Fallback if PIL not available
            width, height = 64, 64

        return Sprite(
            id=sprite_id,
            path=path,
            width=width,
            height=height,
            anchor=(width // 2, height),
            animations={
                "idle": Animation(
                    name="idle",
                    frames=[
                        AnimationFrame(
                            region=(0, 0, width, height),
                            duration_ms=500,
                        )
                    ],
                    loop=True,
                )
            },
        )

    def register(self, sprite: Sprite) -> None:
        """Register a sprite in the cache.

        Args:
            sprite: The sprite to register.
        """
        self._cache[sprite.id] = sprite

    def get(self, sprite_id: str) -> Optional[Sprite]:
        """Get a sprite from cache.

        Args:
            sprite_id: The sprite identifier.

        Returns:
            The cached Sprite or None.
        """
        return self._cache.get(sprite_id)

    def preload_all(self) -> None:
        """Preload all sprites from asset path."""
        if not self._asset_path.exists():
            return

        for png_file in self._asset_path.glob("*.png"):
            sprite_id = png_file.stem
            if sprite_id not in self._cache:
                self.load(sprite_id)
