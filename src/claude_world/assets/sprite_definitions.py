"""Sprite and animation definitions for all game assets."""

from __future__ import annotations

from typing import Optional

from claude_world.types import Sprite, Animation, AnimationFrame


# Animation frame definitions (timing in milliseconds)
ANIMATION_DEFINITIONS: dict[str, dict] = {
    # Main Claude agent animations
    "claude_main": {
        "idle": {
            "frames": [(0, 0, 64, 64), (64, 0, 64, 64)],
            "durations": [500, 500],
            "loop": True,
        },
        "thinking": {
            "frames": [(0, 64, 64, 64), (64, 64, 64, 64), (128, 64, 64, 64)],
            "durations": [300, 300, 300],
            "loop": True,
        },
        "reading": {
            "frames": [(0, 128, 64, 64), (64, 128, 64, 64)],
            "durations": [400, 400],
            "loop": True,
        },
        "writing": {
            "frames": [(0, 192, 64, 64), (64, 192, 64, 64), (128, 192, 64, 64)],
            "durations": [200, 200, 200],
            "loop": True,
        },
        "walk_right": {
            "frames": [(0, 256, 64, 64), (64, 256, 64, 64), (128, 256, 64, 64), (192, 256, 64, 64)],
            "durations": [150, 150, 150, 150],
            "loop": True,
        },
        "walk_left": {
            "frames": [(0, 320, 64, 64), (64, 320, 64, 64), (128, 320, 64, 64), (192, 320, 64, 64)],
            "durations": [150, 150, 150, 150],
            "loop": True,
        },
        "excited": {
            "frames": [(0, 384, 64, 64), (64, 384, 64, 64), (128, 384, 64, 64)],
            "durations": [100, 100, 100],
            "loop": False,
        },
        "searching": {
            "frames": [(0, 448, 64, 64), (64, 448, 64, 64)],
            "durations": [300, 300],
            "loop": True,
        },
        "building": {
            "frames": [(0, 512, 64, 64), (64, 512, 64, 64), (128, 512, 64, 64)],
            "durations": [250, 250, 250],
            "loop": True,
        },
        "communicating": {
            "frames": [(0, 576, 64, 64), (64, 576, 64, 64)],
            "durations": [400, 400],
            "loop": True,
        },
        "resting": {
            "frames": [(0, 640, 64, 64)],
            "durations": [1000],
            "loop": True,
        },
    },
    # Subagent animations (simpler)
    "explore_agent": {
        "idle": {
            "frames": [(0, 0, 48, 48), (48, 0, 48, 48)],
            "durations": [600, 600],
            "loop": True,
        },
        "exploring": {
            "frames": [(0, 48, 48, 48), (48, 48, 48, 48), (96, 48, 48, 48)],
            "durations": [200, 200, 200],
            "loop": True,
        },
    },
    "plan_agent": {
        "idle": {
            "frames": [(0, 0, 48, 48), (48, 0, 48, 48)],
            "durations": [700, 700],
            "loop": True,
        },
        "planning": {
            "frames": [(0, 48, 48, 48), (48, 48, 48, 48)],
            "durations": [400, 400],
            "loop": True,
        },
    },
    "general_agent": {
        "idle": {
            "frames": [(0, 0, 48, 48), (48, 0, 48, 48)],
            "durations": [500, 500],
            "loop": True,
        },
        "working": {
            "frames": [(0, 48, 48, 48), (48, 48, 48, 48)],
            "durations": [300, 300],
            "loop": True,
        },
    },
    # Decorations (static or simple animations)
    "palm_tree": {
        "idle": {
            "frames": [(0, 0, 64, 96)],
            "durations": [1000],
            "loop": True,
        },
        "sway": {
            "frames": [(0, 0, 64, 96), (64, 0, 64, 96), (128, 0, 64, 96)],
            "durations": [500, 500, 500],
            "loop": True,
        },
    },
    "rock": {
        "idle": {
            "frames": [(0, 0, 32, 32)],
            "durations": [1000],
            "loop": True,
        },
    },
    "flower": {
        "idle": {
            "frames": [(0, 0, 16, 16), (16, 0, 16, 16)],
            "durations": [800, 800],
            "loop": True,
        },
    },
    # Particles
    "particle_star": {
        "idle": {
            "frames": [(0, 0, 8, 8), (8, 0, 8, 8), (16, 0, 8, 8)],
            "durations": [100, 100, 100],
            "loop": True,
        },
    },
    "particle_code": {
        "idle": {
            "frames": [(0, 0, 8, 8)],
            "durations": [100],
            "loop": True,
        },
    },
    "particle_bubble": {
        "idle": {
            "frames": [(0, 0, 12, 12), (12, 0, 12, 12)],
            "durations": [150, 150],
            "loop": True,
        },
    },
}

# Sprite definitions with sizes and anchors
SPRITE_DEFINITIONS: dict[str, dict] = {
    "claude_main": {
        "width": 64,
        "height": 64,
        "anchor": (32, 60),  # Center bottom
    },
    "explore_agent": {
        "width": 48,
        "height": 48,
        "anchor": (24, 44),
    },
    "plan_agent": {
        "width": 48,
        "height": 48,
        "anchor": (24, 44),
    },
    "general_agent": {
        "width": 48,
        "height": 48,
        "anchor": (24, 44),
    },
    "palm_tree": {
        "width": 64,
        "height": 96,
        "anchor": (32, 92),
    },
    "rock": {
        "width": 32,
        "height": 32,
        "anchor": (16, 28),
    },
    "flower": {
        "width": 16,
        "height": 16,
        "anchor": (8, 14),
    },
    "particle_star": {
        "width": 8,
        "height": 8,
        "anchor": (4, 4),
    },
    "particle_code": {
        "width": 8,
        "height": 8,
        "anchor": (4, 4),
    },
    "particle_bubble": {
        "width": 12,
        "height": 12,
        "anchor": (6, 6),
    },
}


def get_sprite_definition(sprite_id: str) -> Optional[dict]:
    """Get a sprite definition by ID.

    Args:
        sprite_id: The sprite identifier.

    Returns:
        Sprite definition dict or None.
    """
    return SPRITE_DEFINITIONS.get(sprite_id)


def create_sprite(sprite_id: str) -> Optional[Sprite]:
    """Create a Sprite from definitions.

    Args:
        sprite_id: The sprite identifier.

    Returns:
        Sprite object or None if not found.
    """
    sprite_def = SPRITE_DEFINITIONS.get(sprite_id)
    anim_def = ANIMATION_DEFINITIONS.get(sprite_id)

    if sprite_def is None:
        return None

    # Build animations
    animations: dict[str, Animation] = {}

    if anim_def:
        for anim_name, anim_data in anim_def.items():
            frames = []
            for i, region in enumerate(anim_data["frames"]):
                duration = anim_data["durations"][i] if i < len(anim_data["durations"]) else 100
                frames.append(AnimationFrame(region=region, duration_ms=duration))

            animations[anim_name] = Animation(
                name=anim_name,
                frames=frames,
                loop=anim_data.get("loop", True),
            )
    else:
        # Default idle animation
        animations["idle"] = Animation(
            name="idle",
            frames=[AnimationFrame(
                region=(0, 0, sprite_def["width"], sprite_def["height"]),
                duration_ms=500,
            )],
            loop=True,
        )

    return Sprite(
        id=sprite_id,
        path=None,  # No file path for programmatic sprites
        width=sprite_def["width"],
        height=sprite_def["height"],
        anchor=sprite_def["anchor"],
        animations=animations,
    )


def create_all_sprites() -> dict[str, Sprite]:
    """Create all defined sprites.

    Returns:
        Dictionary of sprite_id to Sprite.
    """
    sprites = {}
    for sprite_id in SPRITE_DEFINITIONS:
        sprite = create_sprite(sprite_id)
        if sprite:
            sprites[sprite_id] = sprite
    return sprites
