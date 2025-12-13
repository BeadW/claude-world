"""Generate placeholder sprite images for testing."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from .sprite_definitions import SPRITE_DEFINITIONS, ANIMATION_DEFINITIONS


# Color schemes for different sprite types
SPRITE_COLORS: dict[str, Tuple[int, int, int]] = {
    "claude_main": (200, 150, 100),  # Tan/brown (Claude)
    "explore_agent": (100, 200, 100),  # Green
    "plan_agent": (100, 100, 200),  # Blue
    "general_agent": (150, 150, 150),  # Gray
    "palm_tree": (50, 150, 50),  # Dark green
    "rock": (120, 120, 120),  # Gray
    "flower": (255, 100, 150),  # Pink
    "particle_star": (255, 255, 100),  # Yellow
    "particle_code": (100, 200, 255),  # Cyan
    "particle_bubble": (200, 200, 255),  # Light blue
}


class PlaceholderGenerator:
    """Generates placeholder sprite images."""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize the generator.

        Args:
            output_dir: Output directory for generated sprites.
        """
        self.output_dir = output_dir or Path("assets/sprites")

    def generate_all(self) -> dict[str, Path]:
        """Generate all placeholder sprites.

        Returns:
            Dictionary of sprite_id to generated file path.
        """
        if not HAS_PIL:
            return {}

        self.output_dir.mkdir(parents=True, exist_ok=True)
        generated = {}

        for sprite_id, sprite_def in SPRITE_DEFINITIONS.items():
            path = self.generate_sprite(sprite_id, sprite_def)
            if path:
                generated[sprite_id] = path

        return generated

    def generate_sprite(
        self,
        sprite_id: str,
        sprite_def: dict,
    ) -> Optional[Path]:
        """Generate a single placeholder sprite.

        Args:
            sprite_id: The sprite identifier.
            sprite_def: Sprite definition dict.

        Returns:
            Path to generated file or None.
        """
        if not HAS_PIL:
            return None

        anim_def = ANIMATION_DEFINITIONS.get(sprite_id, {})

        # Calculate spritesheet size
        width = sprite_def["width"]
        height = sprite_def["height"]

        # Find total frames needed
        max_x = width
        max_y = height

        for anim_data in anim_def.values():
            for frame in anim_data.get("frames", []):
                x, y, w, h = frame
                max_x = max(max_x, x + w)
                max_y = max(max_y, y + h)

        # Create image
        img = Image.new("RGBA", (max_x, max_y), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Get color for this sprite
        color = SPRITE_COLORS.get(sprite_id, (200, 200, 200))

        # Draw frames
        if anim_def:
            for anim_data in anim_def.values():
                for frame in anim_data.get("frames", []):
                    x, y, w, h = frame
                    self._draw_placeholder_frame(draw, x, y, w, h, color, sprite_id)
        else:
            # Single frame
            self._draw_placeholder_frame(draw, 0, 0, width, height, color, sprite_id)

        # Save
        output_path = self.output_dir / f"{sprite_id}.png"
        img.save(output_path)

        return output_path

    def _draw_placeholder_frame(
        self,
        draw: "ImageDraw.Draw",
        x: int,
        y: int,
        w: int,
        h: int,
        color: Tuple[int, int, int],
        sprite_id: str,
    ) -> None:
        """Draw a placeholder frame.

        Args:
            draw: ImageDraw instance.
            x: X position.
            y: Y position.
            w: Width.
            h: Height.
            color: RGB color tuple.
            sprite_id: Sprite identifier for styling.
        """
        # Draw different shapes based on sprite type
        if "agent" in sprite_id or sprite_id == "claude_main":
            # Draw a simple character shape
            # Body (oval)
            body_margin = w // 8
            draw.ellipse(
                [x + body_margin, y + h // 3, x + w - body_margin, y + h - 2],
                fill=color,
                outline=(color[0] // 2, color[1] // 2, color[2] // 2),
            )
            # Head (circle)
            head_size = w // 3
            head_x = x + w // 2 - head_size // 2
            head_y = y + h // 8
            draw.ellipse(
                [head_x, head_y, head_x + head_size, head_y + head_size],
                fill=color,
                outline=(color[0] // 2, color[1] // 2, color[2] // 2),
            )

        elif sprite_id == "palm_tree":
            # Trunk
            trunk_w = w // 6
            trunk_x = x + w // 2 - trunk_w // 2
            draw.rectangle(
                [trunk_x, y + h // 3, trunk_x + trunk_w, y + h],
                fill=(139, 90, 43),
            )
            # Leaves (triangle/fan shape)
            leaf_color = color
            for offset in [-w // 3, 0, w // 3]:
                draw.polygon(
                    [
                        (x + w // 2, y),
                        (x + w // 2 + offset - w // 4, y + h // 3),
                        (x + w // 2 + offset + w // 4, y + h // 3),
                    ],
                    fill=leaf_color,
                )

        elif sprite_id == "rock":
            # Irregular polygon for rock
            points = [
                (x + w // 4, y + h),
                (x, y + h // 2),
                (x + w // 6, y + h // 4),
                (x + w // 2, y),
                (x + w - w // 6, y + h // 4),
                (x + w, y + h // 2),
                (x + w - w // 4, y + h),
            ]
            draw.polygon(points, fill=color, outline=(80, 80, 80))

        elif sprite_id == "flower":
            # Center
            cx, cy = x + w // 2, y + h // 2
            # Petals
            petal_r = w // 4
            for angle in range(0, 360, 72):
                import math
                px = cx + int(petal_r * 0.7 * math.cos(math.radians(angle)))
                py = cy + int(petal_r * 0.7 * math.sin(math.radians(angle)))
                draw.ellipse(
                    [px - petal_r // 2, py - petal_r // 2, px + petal_r // 2, py + petal_r // 2],
                    fill=color,
                )
            # Center
            draw.ellipse(
                [cx - 2, cy - 2, cx + 2, cy + 2],
                fill=(255, 200, 0),
            )

        elif "particle" in sprite_id:
            # Simple circle/star for particles
            if "star" in sprite_id:
                # Draw a small star
                cx, cy = x + w // 2, y + h // 2
                r = w // 2 - 1
                points = []
                for i in range(5):
                    import math
                    angle = math.radians(i * 72 - 90)
                    points.append((cx + int(r * math.cos(angle)), cy + int(r * math.sin(angle))))
                    angle = math.radians(i * 72 + 36 - 90)
                    points.append((cx + int(r * 0.4 * math.cos(angle)), cy + int(r * 0.4 * math.sin(angle))))
                draw.polygon(points, fill=color)
            else:
                # Circle
                draw.ellipse([x + 1, y + 1, x + w - 1, y + h - 1], fill=color)

        else:
            # Default: filled rectangle
            draw.rectangle([x + 1, y + 1, x + w - 2, y + h - 2], fill=color)


def generate_placeholders(output_dir: Optional[Path] = None) -> dict[str, Path]:
    """Convenience function to generate all placeholders.

    Args:
        output_dir: Output directory.

    Returns:
        Dictionary of sprite_id to generated file path.
    """
    generator = PlaceholderGenerator(output_dir)
    return generator.generate_all()
