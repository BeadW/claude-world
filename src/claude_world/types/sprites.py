"""Sprite and animation types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


@dataclass
class AnimationFrame:
    """Single frame of animation."""

    region: tuple[int, int, int, int]  # x, y, w, h in spritesheet
    duration_ms: int


@dataclass
class Animation:
    """Sprite animation sequence."""

    name: str
    frames: list[AnimationFrame]
    loop: bool = True


@dataclass
class Sprite:
    """A sprite backed by image data."""

    id: str
    path: Path | str
    width: int
    height: int
    anchor: tuple[int, int]  # Origin point (x, y)
    animations: dict[str, Animation] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.path, str):
            self.path = Path(self.path)
