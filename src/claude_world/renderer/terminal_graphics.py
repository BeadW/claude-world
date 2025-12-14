"""Terminal graphics renderer using Kitty/iTerm2/Sixel protocols."""

from __future__ import annotations

import base64
import io
import math
import os
import shutil
import sys
from typing import TYPE_CHECKING, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

if TYPE_CHECKING:
    from claude_world.types import GameState

# Import from split modules
from claude_world.renderer.terminal_size import (
    is_inside_tmux,
    get_pane_size,
    get_terminal_pixel_width,
    get_terminal_pixel_size,
    get_cell_size,
    resize_tmux_pane,
    get_pane_pixel_size,
    ASPECT_RATIO,
)
from claude_world.renderer.display import (
    detect_graphics_protocol,
    tmux_wrap,
    display_kitty,
    display_iterm2,
    display_sixel,
    clear_tmux_scrollback,
    enable_focus_reporting as _enable_focus_reporting,
    disable_focus_reporting as _disable_focus_reporting,
    cleanup_terminal,
)
from claude_world.renderer.world_objects import WorldObjectsMixin


class TerminalGraphicsRenderer(WorldObjectsMixin):
    """Renders game state as idle game graphics in the terminal.

    Design: Centered Claude character with clean stats display.
    Inspired by popular idle games with focus on character and progression.
    """

    # Fixed aspect ratio for game (width:height) - imported from terminal_size
    ASPECT_RATIO = ASPECT_RATIO

    # Color palette - Pixel art style with bold, flat colors
    COLORS = {
        # Background - bright sky blue
        "bg_top": (135, 206, 235),
        "bg_bottom": (100, 180, 220),
        # Accent colors
        "accent_primary": (255, 200, 50),     # Gold/yellow
        "accent_secondary": (100, 160, 255),  # Blue
        "accent_success": (100, 200, 100),    # Green
        "accent_xp": (200, 100, 255),         # Purple
        # Claude character colors - teal like the logo
        "claude_body": (100, 180, 180),       # Teal
        "claude_dark": (70, 140, 140),        # Darker teal
        "claude_light": (150, 210, 210),      # Light teal
        "claude_eyes": (40, 40, 45),          # Dark
        # UI colors - wood panel style
        "ui_bg": (180, 140, 100),             # Wood brown
        "ui_bg_dark": (140, 100, 70),         # Darker wood
        "ui_border": (80, 50, 30),            # Dark brown outline
        "ui_text": (255, 255, 255),           # White text
        "ui_text_dark": (60, 40, 30),         # Dark text
        # Scene colors - vibrant pixel art style
        "water": (70, 150, 220),
        "water_light": (100, 180, 240),
        "water_dark": (50, 120, 180),
        "sand": (240, 210, 150),
        "sand_dark": (210, 180, 120),
        "grass": (100, 180, 80),
        "grass_light": (130, 210, 100),
        "grass_dark": (70, 140, 60),
        # Tree colors
        "tree_trunk": (120, 80, 50),
        "tree_trunk_dark": (90, 60, 40),
        "tree_leaves": (80, 160, 80),
        "tree_leaves_light": (110, 190, 100),
        "tree_leaves_dark": (60, 130, 60),
        # Outline color for pixel art style
        "outline": (40, 30, 20),
    }

    # Tool name to activity verb mapping (matches Claude Code's display)
    TOOL_VERBS = {
        "Read": "Reading...",
        "Write": "Writing...",
        "Edit": "Editing...",
        "Bash": "Running...",
        "Glob": "Searching...",
        "Grep": "Searching...",
        "WebFetch": "Fetching...",
        "WebSearch": "Searching...",
        "Task": "Delegating...",
        "TodoWrite": "Planning...",
        "AskUserQuestion": "Asking...",
        "NotebookEdit": "Editing...",
    }

    # Claude Code's actual thinking verbs (from source)
    THINKING_VERBS = [
        "Accomplishing...", "Actioning...", "Actualizing...", "Baking...",
        "Brewing...", "Calculating...", "Cerebrating...", "Churning...",
        "Clauding...", "Coalescing...", "Cogitating...", "Computing...",
        "Conjuring...", "Considering...", "Cooking...", "Crafting...",
        "Creating...", "Crunching...", "Deliberating...", "Determining...",
        "Doing...", "Effecting...", "Finagling...", "Forging...",
        "Forming...", "Generating...", "Hatching...", "Herding...",
        "Honking...", "Hustling...", "Ideating...", "Inferring...",
        "Manifesting...", "Marinating...", "Moseying...", "Mulling...",
        "Mustering...", "Musing...", "Noodling...", "Percolating...",
        "Pondering...", "Processing...", "Puttering...", "Reticulating...",
        "Ruminating...", "Schlepping...", "Simmering...", "Smooshing...",
        "Spinning...", "Stewing...", "Synthesizing...", "Thinking...",
        "Transmuting...", "Vibing...", "Working...",
    ]

    # Known Claude Code verbs to look for in terminal output (without "...")
    CLAUDE_CODE_VERBS = {
        "Accomplishing", "Actioning", "Actualizing", "Baking", "Brewing",
        "Calculating", "Cerebrating", "Churning", "Clauding", "Coalescing",
        "Cogitating", "Computing", "Conjuring", "Considering", "Cooking",
        "Crafting", "Creating", "Crunching", "Deliberating", "Determining",
        "Doing", "Effecting", "Finagling", "Forging", "Forming", "Generating",
        "Hatching", "Herding", "Honking", "Hustling", "Ideating", "Inferring",
        "Manifesting", "Marinating", "Moseying", "Mulling", "Mustering",
        "Musing", "Noodling", "Percolating", "Pondering", "Processing",
        "Puttering", "Reticulating", "Ruminating", "Schlepping", "Simmering",
        "Smooshing", "Spinning", "Stewing", "Synthesizing", "Thinking",
        "Transmuting", "Vibing", "Working",
        "Thought",  # For "Thought for Xs" display
    }

    @staticmethod
    def _get_claude_code_verb() -> str | None:
        """Read the current verb from the Claude Code tmux pane.

        Returns:
            The verb (e.g., "Unravelling") or None if not found.
        """
        import subprocess
        import re

        if not is_inside_tmux():
            return None

        try:
            # List all panes and find the one running claude (not our game pane)
            result = subprocess.run(
                ["tmux", "list-panes", "-F", "#{pane_id}"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                del result  # Explicitly free subprocess buffers
                return None

            pane_ids = result.stdout.strip().split("\n")
            del result  # Free memory immediately

            result2 = subprocess.run(
                ["tmux", "display-message", "-p", "#{pane_id}"],
                capture_output=True,
                text=True,
            )
            current_pane = result2.stdout.strip()
            del result2  # Free memory immediately

            # Check other panes for Claude Code verb
            for pane_id in pane_ids:
                if pane_id == current_pane:
                    continue  # Skip our own pane

                # Capture the last few lines of the other pane
                capture = subprocess.run(
                    ["tmux", "capture-pane", "-t", pane_id, "-p", "-S", "-5"],
                    capture_output=True,
                    text=True,
                )
                if capture.returncode != 0:
                    del capture
                    continue

                content = capture.stdout
                del capture  # Free subprocess buffers

                # Look for verb patterns like "Unravelling..." or "⠋ Pondering"
                # Match: optional spinner + word + "..." or "(esc to interrupt)"
                for line in content.split("\n"):
                    # Look for lines with verbs followed by ... or timing info
                    match = re.search(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏\s]*(\w+)(?:\.{3}|…)', line)
                    if match:
                        word = match.group(1)
                        if word in TerminalGraphicsRenderer.CLAUDE_CODE_VERBS:
                            return word

                    # Also check for "Verb for Xs" pattern
                    match = re.search(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏\s]*(\w+)\s+for\s+\d+', line)
                    if match:
                        word = match.group(1)
                        if word in TerminalGraphicsRenderer.CLAUDE_CODE_VERBS:
                            return word

        except Exception:
            pass

        return None

    @staticmethod
    def _get_pane_size_static() -> tuple[int, int]:
        """Get the tmux pane size or terminal size in characters."""
        return get_pane_size()


    @staticmethod
    def _get_terminal_pixel_width() -> int:
        """Get terminal/pane width in pixels."""
        return get_terminal_pixel_width()

    @classmethod
    def _get_terminal_pixel_size(cls) -> tuple[int, int]:
        """Get terminal size in pixels for frame size."""
        return get_terminal_pixel_size()

    def _get_pane_pixel_size(self) -> tuple[int, int]:
        """Get current tmux pane size in pixels."""
        return get_pane_pixel_size(self._cell_width, self._cell_height, self.width, self.height)

    def __init__(self, width: int = 0, height: int = 0):
        """Initialize the renderer.

        Args:
            width: Width in pixels. 0 = auto-detect from terminal.
            height: Height in pixels. 0 = auto-detect from terminal.
        """
        if not HAS_PIL:
            raise RuntimeError("PIL/Pillow is required for graphics rendering")

        # Get terminal pixel size
        pixel_width, pixel_height = self._get_terminal_pixel_size()

        # Get character cell size for reference
        pane_cols, pane_rows = self._get_pane_size_static()

        # Use provided size or terminal pixel size
        if width <= 0:
            width = pixel_width
        if height <= 0:
            height = pixel_height

        self.width = width
        self.height = height
        self.pane_cols = pane_cols
        self.pane_rows = pane_rows
        self.protocol = detect_graphics_protocol()

        # Store cell size for pane size calculations
        self._cell_width, self._cell_height = self._get_cell_size()

        # Create frame buffer
        self.frame = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        self.draw = ImageDraw.Draw(self.frame)

        # Animation state
        self._frame_count = 0
        self._first_frame = True
        self._focus_reporting_enabled = False

        # Stats
        self.last_render_time = 0.0
        self.rendered_entities: dict[str, dict] = {}
        self.particle_count = 0

        # Claude Code verb tracking
        self._cached_verb: str | None = None
        self._verb_cache_frame = 0

        # Memory management - clear terminal scrollback periodically
        self._last_scrollback_clear = 0

    @staticmethod
    def _get_cell_size() -> tuple[int, int]:
        """Get terminal cell size in pixels."""
        return get_cell_size()

    def _resize_tmux_pane(self) -> None:
        """Resize the current tmux pane to fit the rendered frame."""
        resize_tmux_pane(self.height, self._cell_height)

    def _safe_ellipse(self, coords: list, **kwargs) -> None:
        """Draw an ellipse only if coordinates are valid (x2 > x1 and y2 > y1)."""
        x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]
        if x2 > x1 and y2 > y1:
            self.draw.ellipse(coords, **kwargs)

    def render_frame(self, state: GameState) -> None:
        """Render a complete frame."""
        import time
        import traceback
        start = time.perf_counter()

        self._frame_count += 1

        # Size is fixed at startup - no dynamic resizing to prevent flickering

        # Close previous frame and draw to free memory
        if hasattr(self, 'draw') and self.draw is not None:
            del self.draw
            self.draw = None
        if hasattr(self, 'frame') and self.frame is not None:
            self.frame.close()
            del self.frame
            self.frame = None

        # Aggressive garbage collection - every 10 frames (~0.3 second at 30fps)
        # Critical for preventing PIL image memory buildup
        if self._frame_count % 10 == 0:
            import gc
            gc.collect(0)  # Generation 0 only - fast
        # Full GC every 90 frames (~3 seconds)
        if self._frame_count % 90 == 0:
            import gc
            gc.collect()

        # Create fresh frame
        self.frame = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
        self.draw = ImageDraw.Draw(self.frame)

        try:
            # Render layers (idle game style)
            self._render_background(state)
            self._render_scene(state)
            self._render_subagent_connections(state)
            self._render_subagents(state)
            self._render_claude_character(state)
            self._render_tool_spinner(state)
            self._render_particles(state)
            self._render_floating_texts(state)
            self._render_stats_panel(state)
            self._render_activity_indicator(state)
            self._render_achievement_popups(state)
            self._render_level_up_overlay(state)
            self._display_frame()
        except Exception as e:
            # Log error to file for debugging
            with open("/tmp/claude_world_error.log", "a") as f:
                f.write(f"\n--- Error at frame {self._frame_count} ---\n")
                f.write(f"Activity: {state.main_agent.activity.value if state and state.main_agent else 'unknown'}\n")
                f.write(f"Tool: {state.main_agent.current_tool if state and state.main_agent else 'unknown'}\n")
                f.write(traceback.format_exc())

        self.last_render_time = time.perf_counter() - start

    def _render_background(self, state: GameState) -> None:
        """Render pixel art style background based on time of day."""
        phase = state.world.time_of_day.phase
        hour = state.world.time_of_day.hour

        # Time-based color schemes - bright, flat pixel art colors
        if phase == "day":
            sky_color = (135, 206, 235)  # Bright sky blue
        elif phase == "dawn":
            t = (hour - 5) / 2
            sky_color = self._lerp_color((255, 180, 150), (135, 206, 235), t)
        elif phase == "dusk":
            t = (hour - 17) / 2
            sky_color = self._lerp_color((135, 206, 235), (255, 150, 100), t)
        else:  # night
            sky_color = (30, 40, 70)

        # Flat fill - pixel art style (no gradient)
        self.draw.rectangle([0, 0, self.width, self.height], fill=sky_color)

        # Stars at night - bigger, blockier pixels
        if phase == "night":
            import random
            random.seed(42)
            pixel_size = max(2, self.height // 150)
            for _ in range(40):
                x = random.randint(0, self.width)
                y = random.randint(0, int(self.height * 0.4))
                # Twinkle by toggling visibility
                twinkle = (self._frame_count + x) % 60 < 50
                if twinkle:
                    self.draw.rectangle(
                        [x, y, x + pixel_size, y + pixel_size],
                        fill=(255, 255, 220)
                    )

    def _render_scene(self, state: GameState) -> None:
        """Render top-down pixel art scene with grass, trees, and water."""
        center_x = self.width // 2
        frame = self._frame_count

        # Pixel size for chunky pixel art look
        px = max(2, self.height // 120)

        # Draw grass background (fills most of the screen)
        grass_start_y = int(self.height * 0.25)
        self.draw.rectangle(
            [0, grass_start_y, self.width, self.height],
            fill=self.COLORS["grass"]
        )

        # Add grass texture - darker patches in a grid pattern
        for gy in range(grass_start_y, self.height, px * 8):
            for gx in range(0, self.width, px * 8):
                # Checkerboard-ish pattern with some randomness
                if ((gx // (px * 8)) + (gy // (px * 8))) % 2 == 0:
                    self.draw.rectangle(
                        [gx, gy, gx + px * 4, gy + px * 4],
                        fill=self.COLORS["grass_light"]
                    )

        # Water on the edges (like ocean surrounding the island)
        water_width = int(self.width * 0.10)
        beach_width = int(self.width * 0.06)

        # Left water
        self.draw.rectangle([0, grass_start_y, water_width, self.height], fill=self.COLORS["water"])
        # Right water
        self.draw.rectangle([self.width - water_width, grass_start_y, self.width, self.height], fill=self.COLORS["water"])

        # Beach sand between water and grass (left side)
        self.draw.rectangle([water_width, grass_start_y, water_width + beach_width, self.height],
                          fill=self.COLORS["sand"])
        # Beach sand (right side)
        self.draw.rectangle([self.width - water_width - beach_width, grass_start_y,
                           self.width - water_width, self.height], fill=self.COLORS["sand"])

        # Sandy shore details - darker wet sand near water
        wet_sand = (210, 185, 130)
        self.draw.rectangle([water_width, grass_start_y, water_width + px * 3, self.height], fill=wet_sand)
        self.draw.rectangle([self.width - water_width - px * 3, grass_start_y,
                           self.width - water_width, self.height], fill=wet_sand)

        # Scattered shells and pebbles on beach
        import random
        random.seed(555)
        shell_colors = [(240, 235, 220), (220, 200, 170), (200, 180, 150)]
        for _ in range(12):
            # Left beach shells
            sx = random.randint(water_width + px * 2, water_width + beach_width - px * 2)
            sy = random.randint(grass_start_y + px * 4, self.height - px * 4)
            shell_size = random.randint(1, 2) * px
            self._safe_ellipse([sx - shell_size, sy - shell_size//2,
                             sx + shell_size, sy + shell_size//2],
                            fill=random.choice(shell_colors))
            # Right beach shells
            sx = random.randint(self.width - water_width - beach_width + px * 2,
                               self.width - water_width - px * 2)
            sy = random.randint(grass_start_y + px * 4, self.height - px * 4)
            self._safe_ellipse([sx - shell_size, sy - shell_size//2,
                             sx + shell_size, sy + shell_size//2],
                            fill=random.choice(shell_colors))

        # Water wave animation - horizontal lines
        for wy in range(grass_start_y, self.height, px * 6):
            wave_offset = int(math.sin(frame * 0.1 + wy * 0.05) * px * 2)
            # Left side waves
            self.draw.rectangle(
                [water_width - px * 3 + wave_offset, wy, water_width + wave_offset, wy + px * 2],
                fill=self.COLORS["water_light"]
            )
            # Right side waves
            self.draw.rectangle(
                [self.width - water_width - wave_offset, wy, self.width - water_width + px * 3 - wave_offset, wy + px * 2],
                fill=self.COLORS["water_light"]
            )

        # Foam at waterline (animated)
        for wy in range(grass_start_y, self.height, px * 8):
            foam_offset = int(math.sin(frame * 0.08 + wy * 0.03) * px)
            # Left foam
            self.draw.ellipse([water_width + foam_offset - px * 2, wy,
                             water_width + foam_offset + px * 2, wy + px * 3],
                            fill=(255, 255, 255))
            # Right foam
            self.draw.ellipse([self.width - water_width - foam_offset - px * 2, wy,
                             self.width - water_width - foam_offset + px * 2, wy + px * 3],
                            fill=(255, 255, 255))

        # Draw pixel art trees scattered around (but not in center where Claude is)
        tree_positions = [
            # Left side trees
            (0.15, 0.35), (0.20, 0.50), (0.18, 0.70), (0.25, 0.85),
            (0.22, 0.40), (0.28, 0.60),
            # Right side trees
            (0.75, 0.35), (0.80, 0.55), (0.78, 0.75), (0.85, 0.45),
            (0.82, 0.65), (0.77, 0.85),
            # Back trees (smaller, behind)
            (0.35, 0.30), (0.50, 0.28), (0.65, 0.32),
        ]

        # Draw clouds FIRST - they're in the background behind trees
        self._draw_pixel_clouds(frame, state.world.time_of_day.phase)

        # Sort by Y position for proper layering
        tree_positions.sort(key=lambda p: p[1])

        for tx, ty in tree_positions:
            tree_x = int(self.width * tx)
            tree_y = int(self.height * ty)
            # Trees further back are smaller
            tree_scale = 0.6 + ty * 0.5
            self._draw_pixel_tree(tree_x, tree_y, tree_scale, px, frame)

        # Small path/clearing in center where Claude stands
        path_y = int(self.height * 0.55)
        path_w = int(self.width * 0.25)
        self.draw.rectangle(
            [center_x - path_w // 2, path_y - px * 4, center_x + path_w // 2, path_y + px * 8],
            fill=self.COLORS["grass_light"]
        )

        # Draw interactive world objects at each location
        self._draw_world_objects(center_x, int(self.height * 0.58), px, frame, state)

        # Draw ambient floating particles (leaves during day, fireflies at night)
        self._draw_ambient_particles(frame, state.world.time_of_day.phase, px)

    def _draw_world_objects(self, center_x: int, center_y: int, px: int, frame: int, state: GameState) -> None:
        """Draw interactive objects at world locations - matching WORLD_LOCATIONS in entity.py."""
        current_loc = state.main_agent.current_location

        # Positions match WORLD_LOCATIONS in entity.py (relative offsets from center)
        # Scale factor converts entity coords to pixel coords
        scale = px * 1.5

        # Palm tree reading spot - Position(-170, -50)
        palm_x = center_x + int(-170 * scale / px)
        palm_y = center_y + int(-50 * scale / px)
        self._draw_reading_palm(palm_x, palm_y, px, frame, active=(current_loc == "palm_tree"))

        # Rock pile - Position(170, 60)
        rock_x = center_x + int(170 * scale / px)
        rock_y = center_y + int(60 * scale / px)
        self._draw_rock_pile(rock_x, rock_y, px, frame, active=(current_loc == "rock_pile"))

        # Sandy patch - Position(-130, 80)
        sand_x = center_x + int(-130 * scale / px)
        sand_y = center_y + int(80 * scale / px)
        self._draw_sand_patch(sand_x, sand_y, px, frame, active=(current_loc == "sand_patch"))

        # Tide pool - Position(160, -60)
        pool_x = center_x + int(160 * scale / px)
        pool_y = center_y + int(-60 * scale / px)
        self._draw_tide_pool(pool_x, pool_y, px, frame, active=(current_loc == "tide_pool"))

        # Bushes - Position(120, 30)
        bush_x = center_x + int(120 * scale / px)
        bush_y = center_y + int(30 * scale / px)
        self._draw_bush(bush_x, bush_y, px, frame, active=(current_loc == "bushes"))

        # Message bottle at shore - Position(-180, 70)
        bottle_x = center_x + int(-180 * scale / px)
        bottle_y = center_y + int(70 * scale / px)
        self._draw_message_bottle(bottle_x, bottle_y, px, frame, active=(current_loc == "shore"))

        # Thinking spot on hilltop - Position(80, -80)
        hilltop_x = center_x + int(80 * scale / px)
        hilltop_y = center_y + int(-80 * scale / px)
        self._draw_thinking_spot(hilltop_x, hilltop_y, px, frame, active=(current_loc == "hilltop"))

    def _draw_reading_palm(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a palm tree with reading spot beneath it."""
        trunk_color = (120, 80, 50)
        trunk_dark = (90, 60, 40)
        frond_color = (60, 140, 60)
        frond_light = (90, 170, 80)
        outline = self.COLORS["outline"]

        # Sway animation
        sway = int(math.sin(frame * 0.04) * px * 2)

        # Shadow on ground
        self.draw.ellipse([x - px*6, y + px*4, x + px*6, y + px*6], fill=(60, 120, 50))

        # Trunk - curved palm trunk
        for i in range(4):
            trunk_x = x + int(math.sin(i * 0.3) * px)
            trunk_y = y - i * px * 3
            self.draw.rectangle([trunk_x - px*2 - px, trunk_y - px*2,
                               trunk_x + px*2 + px, trunk_y + px*2], fill=outline)
            self.draw.rectangle([trunk_x - px*2, trunk_y - px*2,
                               trunk_x + px*2, trunk_y + px*2], fill=trunk_color)
            self.draw.rectangle([trunk_x - px, trunk_y - px*2,
                               trunk_x, trunk_y + px*2], fill=trunk_dark)

        # Coconuts
        coconut_y = y - px * 10
        for i, ox in enumerate([-px*2, px*2]):
            self.draw.ellipse([x + ox + sway - px*2, coconut_y - px*2,
                             x + ox + sway + px*2, coconut_y + px*2], fill=(100, 70, 40))

        # Palm fronds
        frond_base_y = y - px * 12
        fronds = [(-1.2, 0.8), (-0.6, 0.9), (0, 1.0), (0.6, 0.9), (1.2, 0.8)]
        for angle_offset, length_mult in fronds:
            angle = math.pi / 2 + angle_offset + sway * 0.02
            frond_len = px * 8 * length_mult
            end_x = x + sway + int(math.cos(angle) * frond_len)
            end_y = frond_base_y + int(math.sin(angle) * frond_len * 0.3)

            # Draw frond as elongated shape
            mid_x = x + sway + int(math.cos(angle) * frond_len * 0.5)
            mid_y = frond_base_y + int(math.sin(angle) * frond_len * 0.15)

            # Frond segments
            for j in range(3):
                seg_t = j / 3.0
                seg_x = x + sway + int(math.cos(angle) * frond_len * seg_t)
                seg_y = frond_base_y + int(math.sin(angle) * frond_len * 0.3 * seg_t) - j * px
                seg_color = frond_light if j == 0 else frond_color
                self.draw.ellipse([seg_x - px*2, seg_y - px, seg_x + px*2, seg_y + px], fill=seg_color)

        # When active (reading), show book/scroll and reading effects
        if active:
            # Book resting on ground beneath palm
            book_x = x - px * 3
            book_y = y + px * 2
            book_w = px * 5
            book_h = px * 3

            # Book outline and fill
            self.draw.rectangle([book_x - px, book_y - px, book_x + book_w + px, book_y + book_h + px],
                              fill=outline)
            self.draw.rectangle([book_x, book_y, book_x + book_w, book_y + book_h],
                              fill=(240, 230, 210))
            # Book spine
            self.draw.rectangle([book_x + book_w//2 - px//2, book_y, book_x + book_w//2 + px//2, book_y + book_h],
                              fill=(180, 140, 100))

            # Animated page turn
            page_phase = (frame % 90) / 90.0
            if page_phase > 0.7:
                # Page lifting
                page_lift = int((page_phase - 0.7) / 0.3 * px * 3)
                self.draw.polygon([
                    (book_x + book_w//2, book_y),
                    (book_x + book_w, book_y - page_lift),
                    (book_x + book_w, book_y + book_h),
                    (book_x + book_w//2, book_y + book_h)
                ], fill=(255, 250, 240))

            # Reading sparkles/highlights
            for i in range(3):
                sparkle_phase = (frame * 0.1 + i * 2.5) % (math.pi * 2)
                sparkle_x = book_x + book_w//2 + int(math.cos(sparkle_phase) * px * 4)
                sparkle_y = book_y - px * 2 + int(math.sin(sparkle_phase) * px * 2)
                if (frame + i * 11) % 20 < 14:
                    self.draw.rectangle([sparkle_x - px//2, sparkle_y - px//2,
                                       sparkle_x + px//2, sparkle_y + px//2], fill=(255, 255, 200))

    def _draw_rock_pile(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a pile of rocks with better depth and detail."""
        # Rock color palette with proper highlights and shadows
        rock_base = [(130, 125, 120), (115, 110, 105), (145, 140, 135), (100, 95, 90)]
        rock_highlight = [(170, 165, 160), (155, 150, 145), (180, 175, 170), (140, 135, 130)]
        rock_shadow = [(90, 85, 80), (75, 70, 65), (100, 95, 90), (60, 55, 50)]
        outline = self.COLORS["outline"]

        # When active, rocks shake
        shake = int(math.sin(frame * 0.4) * px) if active else 0

        # Ground shadow under pile
        shadow_color = (60, 100, 50) if not active else (80, 120, 70)
        self.draw.ellipse([x - px*8, y + px*2, x + px*8, y + px*5], fill=shadow_color)

        # Draw 5 rocks in a pile (back to front for proper layering)
        rocks = [
            # (x_offset, y_offset, width, height, color_idx)
            (-px*4, -px*3, px*5, px*4, 0),   # Back left
            (px*3, -px*2, px*4, px*3, 1),    # Back right
            (-px*2, px*1, px*6, px*4, 2),    # Front left (large)
            (px*4, px*2, px*5, px*3, 3),     # Front right
            (px*1, -px*4, px*4, px*3, 0),    # Top center
        ]

        for i, (ox, oy, w, h, ci) in enumerate(rocks):
            # Add individual rock shake when active
            rock_shake = int(math.sin(frame * 0.5 + i * 1.5) * px) if active else 0
            rx, ry = x + ox + shake, y + oy + rock_shake

            base = rock_base[ci]
            highlight = rock_highlight[ci]
            shadow = rock_shadow[ci]

            if active:
                # Brighten when active
                base = tuple(min(255, c + 25) for c in base)
                highlight = tuple(min(255, c + 25) for c in highlight)

            # Outline
            self.draw.ellipse([rx - w - px, ry - h - px, rx + w + px, ry + h + px], fill=outline)
            # Main rock body
            self.draw.ellipse([rx - w, ry - h, rx + w, ry + h], fill=base)
            # Highlight on top-left
            self.draw.ellipse([rx - w + px, ry - h + px, rx - px, ry - px], fill=highlight)
            # Shadow on bottom-right
            self.draw.ellipse([rx + px, ry + px, rx + w - px, ry + h - px], fill=shadow)

        # Small pebbles around the base
        pebble_positions = [(-px*7, px*3), (px*7, px*4), (-px*5, px*4), (px*6, px*3)]
        for i, (px_off, py_off) in enumerate(pebble_positions):
            peb_x, peb_y = x + px_off + shake, y + py_off
            peb_size = px + (i % 2)
            self._safe_ellipse([peb_x - peb_size, peb_y - peb_size//2,
                             peb_x + peb_size, peb_y + peb_size//2], fill=rock_base[i % 4])

        # When active, show sparks and dust particles
        if active:
            # Sparks flying upward
            for i in range(5):
                spark_x = x + int(math.sin(frame * 0.25 + i * 1.2) * px * 6)
                spark_y = y - px * 5 - int((frame * 2 + i * 7) % (px * 10))
                spark_size = px if (frame + i) % 3 == 0 else px // 2
                spark_color = (255, 220, 100) if i % 2 == 0 else (255, 180, 80)
                self.draw.rectangle([spark_x - spark_size, spark_y - spark_size,
                                   spark_x + spark_size, spark_y + spark_size], fill=spark_color)

            # Dust puffs
            for i in range(3):
                dust_x = x + int(math.cos(frame * 0.12 + i * 2.5) * px * 7)
                dust_y = y + px * 3 + int(math.sin(frame * 0.08 + i) * px)
                dust_size = px * 2 + int(abs(math.sin(frame * 0.1 + i)) * px * 1.5)
                dust_color = (180, 170, 160) if i % 2 == 0 else (160, 150, 140)
                self.draw.ellipse([dust_x - dust_size, dust_y - dust_size,
                                 dust_x + dust_size, dust_y + dust_size], fill=dust_color)

    def _draw_sand_patch(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a sandy dig spot with shovel and writing/building area."""
        sand_color = (230, 210, 170)
        sand_dark = (200, 180, 140)
        sand_light = (245, 230, 195)
        outline = self.COLORS["outline"]
        wood_color = (140, 100, 60)
        metal_color = (180, 180, 190)

        # Ground shadow
        self.draw.ellipse([x - px*10, y + px*3, x + px*10, y + px*5], fill=(60, 100, 50))

        # Sandy area - larger base
        self.draw.ellipse([x - px*8 - px, y - px*4 - px, x + px*8 + px, y + px*4 + px], fill=outline)
        self.draw.ellipse([x - px*8, y - px*4, x + px*8, y + px*4], fill=sand_color)
        self.draw.ellipse([x - px*5, y - px*2, x + px*5, y + px*2], fill=sand_light)

        # Small sand mound (dug up pile)
        self.draw.ellipse([x + px*4, y - px*3, x + px*7, y - px], fill=sand_dark)
        self.draw.ellipse([x + px*5, y - px*3, x + px*6, y - px*2], fill=sand_color)

        # Shovel stuck in sand (shows this is for digging/building)
        shovel_x = x - px * 5
        shovel_bob = int(math.sin(frame * 0.1) * px * 0.5) if active else 0

        # Shovel handle
        self.draw.rectangle([shovel_x - px, y - px*10 + shovel_bob, shovel_x + px, y - px*2 + shovel_bob], fill=outline)
        self.draw.rectangle([shovel_x - px//2, y - px*10 + shovel_bob, shovel_x + px//2, y - px*2 + shovel_bob], fill=wood_color)

        # Shovel blade
        self.draw.polygon([
            (shovel_x - px*2, y - px*2 + shovel_bob),
            (shovel_x + px*2, y - px*2 + shovel_bob),
            (shovel_x + px, y + px + shovel_bob),
            (shovel_x - px, y + px + shovel_bob)
        ], fill=outline)
        self.draw.polygon([
            (shovel_x - px*1.5, y - px*1.5 + shovel_bob),
            (shovel_x + px*1.5, y - px*1.5 + shovel_bob),
            (shovel_x + px*0.5, y + shovel_bob),
            (shovel_x - px*0.5, y + shovel_bob)
        ], fill=metal_color)

        # Writing stick/twig next to dig area
        stick_x = x + px * 2
        self.draw.line([(stick_x, y - px*2), (stick_x + px*3, y + px)], fill=wood_color, width=max(1, px))

        # When active, show writing/digging animation
        if active:
            # Glowing active area
            glow_size = px * 6 + int(math.sin(frame * 0.1) * px)
            self._safe_ellipse([x - glow_size, y - glow_size//2 - px,
                             x + glow_size, y + glow_size//2], fill=sand_light)

            # Animated writing marks in the sand
            write_cycle = frame % 120
            num_marks = min((write_cycle // 15) + 1, 8)

            for i in range(num_marks):
                mx = x - px*3 + (i % 4) * px * 2
                my = y - px * 2 + (i // 4) * px * 2

                if i == num_marks - 1:
                    progress = (write_cycle % 15) / 15.0
                    stroke_len = int(px * 2 * progress)
                else:
                    stroke_len = px * 2

                stroke_color = (160, 140, 100)
                if i % 3 == 0:
                    self.draw.line([(mx, my), (mx + stroke_len, my)], fill=stroke_color, width=max(1, px//2))
                elif i % 3 == 1:
                    self.draw.line([(mx, my), (mx + stroke_len, my + stroke_len//2)], fill=stroke_color, width=max(1, px//2))
                else:
                    self.draw.arc([mx, my - px, mx + stroke_len + px, my + px], 0, 180, fill=stroke_color, width=max(1, px//2))

            # Sand flying up from digging
            for i in range(4):
                grain_x = x + int(math.sin(frame * 0.3 + i * 1.5) * px * 4)
                grain_y = y - px * 3 - int((frame * 1.5 + i * 6) % 12) * px // 2
                grain_size = px if i % 2 == 0 else px // 2
                self.draw.rectangle([grain_x, grain_y, grain_x + grain_size, grain_y + grain_size], fill=sand_color)

    def _draw_tide_pool(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a magical scrying pool for web fetching/searching."""
        water_color = (80, 140, 200)
        water_light = (120, 180, 230)
        water_deep = (50, 100, 160)
        outline = self.COLORS["outline"]
        stone_color = (140, 135, 130)
        stone_light = (170, 165, 160)
        magic_glow = (180, 220, 255)

        # Ground shadow
        self.draw.ellipse([x - px*8, y + px*3, x + px*8, y + px*5], fill=(60, 100, 50))

        # Stone rim around pool (makes it look intentional, not just a puddle)
        self.draw.ellipse([x - px*7 - px, y - px*4 - px, x + px*7 + px, y + px*4 + px], fill=outline)
        self.draw.ellipse([x - px*7, y - px*4, x + px*7, y + px*4], fill=stone_color)
        self.draw.ellipse([x - px*6, y - px*3, x + px*4, y + px*3], fill=stone_light)

        # Pool water inside stone rim
        self.draw.ellipse([x - px*5, y - px*3, x + px*5, y + px*3], fill=water_deep)
        self.draw.ellipse([x - px*4, y - px*2, x + px*4, y + px*2], fill=water_color)

        # Magical sparkles on surface (shows it's for searching/fetching)
        for i in range(4):
            sparkle_phase = (frame * 0.1 + i * 1.5) % (math.pi * 2)
            sparkle_x = x + int(math.cos(sparkle_phase + i) * px * 3)
            sparkle_y = y + int(math.sin(sparkle_phase + i) * px * 1.5)
            if (frame + i * 7) % 20 < 12:
                self.draw.rectangle([sparkle_x - px//2, sparkle_y - px//2,
                                   sparkle_x + px//2, sparkle_y + px//2], fill=magic_glow)

        # Magnifying glass icon floating above (shows it's for searching)
        glass_bob = int(math.sin(frame * 0.06) * px)
        glass_x = x + px * 3
        glass_y = y - px * 6 + glass_bob
        # Glass lens (circle)
        self.draw.ellipse([glass_x - px*2 - px, glass_y - px*2 - px,
                         glass_x + px*2 + px, glass_y + px*2 + px], fill=outline)
        self.draw.ellipse([glass_x - px*2, glass_y - px*2,
                         glass_x + px*2, glass_y + px*2], fill=water_light)
        # Glass handle
        handle_start_x = glass_x + px * 2
        handle_start_y = glass_y + px * 2
        self.draw.line([(handle_start_x, handle_start_y),
                       (handle_start_x + px * 2, handle_start_y + px * 2)],
                      fill=outline, width=max(2, px))

        # When active, show fetching/searching animation
        if active:
            # Glowing center - something being retrieved
            glow_pulse = abs(math.sin(frame * 0.15))
            glow_color = (int(140 + 80 * glow_pulse), int(200 + 50 * glow_pulse), int(255))
            glow_size = int(px * 3 + glow_pulse * px * 2)
            self._safe_ellipse([x - glow_size, y - glow_size//2,
                             x + glow_size, y + glow_size//2], fill=glow_color)

            # Data/information rising from pool
            for i in range(5):
                data_phase = (frame * 0.5 + i * 8) % 25
                dx = x + int(math.sin(frame * 0.15 + i * 1.2) * px * 4)
                dy = y - px * 2 - int(data_phase * px * 0.6)
                if data_phase < 20:
                    # Small rectangles representing data
                    data_w = px * (2 if i % 2 == 0 else 1)
                    data_h = px
                    self.draw.rectangle([dx - data_w//2, dy - data_h//2,
                                       dx + data_w//2, dy + data_h//2], fill=magic_glow)

            # Ripple rings expanding outward
            for i in range(3):
                ring_phase = (frame * 0.12 + i * 1.2) % 3.0
                ring_size = int(px * 2 + ring_phase * px * 2)
                ring_alpha = 1.0 - (ring_phase / 3.0)
                if ring_alpha > 0.2:
                    self._safe_ellipse([x - ring_size, y - ring_size//2,
                                     x + ring_size, y + ring_size//2],
                                    outline=magic_glow, width=max(1, int(px * ring_alpha * 1.5)))

    def _draw_bush(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw bushes for searching with berries and depth."""
        bush_color = (75, 135, 65)
        bush_light = (95, 165, 85)
        bush_mid = (85, 150, 75)
        bush_dark = (55, 105, 45)
        outline = self.COLORS["outline"]
        berry_red = (200, 60, 70)
        berry_dark = (150, 40, 50)

        # Ground shadow
        shadow_color = (60, 100, 50) if not active else (80, 120, 70)
        self.draw.ellipse([x - px*8, y + px*3, x + px*8, y + px*5], fill=shadow_color)

        # When active, bushes shake more dramatically
        base_rustle = int(math.sin(frame * 0.5) * px * 2) if active else 0

        # Multiple bush blobs arranged for depth
        blobs = [
            # (x_off, y_off, width, height, color)
            (-px*4, px*1, px*4, px*3, bush_dark),   # Back left
            (px*3, -px*1, px*4, px*3, bush_dark),   # Back right
            (-px*1, -px*2, px*5, px*4, bush_mid),   # Back center
            (-px*3, px*2, px*5, px*3, bush_color),  # Front left
            (px*2, px*2, px*5, px*3, bush_color),   # Front right
            (0, px*1, px*4, px*3, bush_light),      # Front center highlight
        ]

        for i, (ox, oy, w, h, color) in enumerate(blobs):
            # Individual rustle for each blob
            blob_rustle = int(math.sin(frame * 0.6 + i * 1.2) * px) if active else 0
            bx, by = x + ox + base_rustle + blob_rustle, y + oy
            # Outline
            self.draw.ellipse([bx - w - px, by - h - px, bx + w + px, by + h + px], fill=outline)
            # Bush body
            self.draw.ellipse([bx - w, by - h, bx + w, by + h], fill=color)
            # Small highlight blob
            if i >= 3:  # Only on front bushes
                self._safe_ellipse([bx - w//2, by - h + px, bx, by - px], fill=bush_light)

        # Add berries scattered on the bush
        berry_positions = [(-px*3, 0), (px*2, px), (-px, -px*2), (px*4, -px), (-px*5, px*2)]
        for i, (bx_off, by_off) in enumerate(berry_positions):
            # Berry sway with bush
            berry_rustle = int(math.sin(frame * 0.6 + i * 0.8) * px * 0.5) if active else 0
            bx, by = x + bx_off + base_rustle + berry_rustle, y + by_off
            # Berry with highlight
            self.draw.ellipse([bx - px, by - px, bx + px, by + px], fill=berry_red)
            self._safe_ellipse([bx - px//2, by - px//2, bx, by], fill=(255, 100, 110))

        # When active, show leaves flying out and a peek effect
        if active:
            # Leaves flying out from searching
            for i in range(5):
                leaf_phase = (frame * 0.3 + i * 7) % 25
                leaf_x = x + int(math.cos(frame * 0.2 + i * 1.3) * (px * 4 + leaf_phase * px * 0.6))
                leaf_y = y - px * 3 - int(leaf_phase * px * 0.5)
                leaf_color = bush_light if i % 2 == 0 else bush_color
                if leaf_phase < 18:
                    self._safe_ellipse([leaf_x - px, leaf_y - px//2, leaf_x + px, leaf_y + px//2], fill=leaf_color)

            # Parting effect - darker gap in center showing Claude is looking inside
            gap_x = x + int(math.sin(frame * 0.1) * px)
            self.draw.ellipse([gap_x - px*2, y - px*2, gap_x + px*2, y + px], fill=bush_dark)

            # Sparkle/search particles rising up
            for i in range(3):
                search_x = x + int(math.sin(frame * 0.15 + i * 2.5) * px * 5)
                search_y = y - px * 5 - int((frame * 0.8 + i * 6) % (px * 8))
                search_size = px if (frame + i * 3) % 5 < 3 else px // 2
                self.draw.rectangle([search_x - search_size, search_y - search_size,
                                   search_x + search_size, search_y + search_size], fill=(255, 255, 200))

    def _draw_message_bottle(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a beach mailbox/message station for asking questions."""
        outline = self.COLORS["outline"]
        wood_color = (140, 100, 60)
        wood_dark = (100, 70, 40)
        wood_light = (180, 140, 100)
        paper_color = (255, 250, 230)
        sand_color = self.COLORS["sand"]

        # Ground shadow
        self.draw.ellipse([x - px*6, y + px*3, x + px*6, y + px*5], fill=(60, 100, 50))

        # Sandy base patch (this is on the beach)
        self.draw.ellipse([x - px*5, y + px, x + px*5, y + px*4], fill=sand_color)

        # Wooden post holding mailbox
        self.draw.rectangle([x - px - px, y - px*8, x + px + px, y + px*2], fill=outline)
        self.draw.rectangle([x - px, y - px*8, x + px, y + px*2], fill=wood_color)
        self.draw.rectangle([x - px//2, y - px*8, x, y + px*2], fill=wood_dark)

        # Mailbox body on top of post
        mailbox_y = y - px * 10
        # Mailbox back
        self.draw.rectangle([x - px*4 - px, mailbox_y - px*2 - px, x + px*4 + px, mailbox_y + px*2 + px], fill=outline)
        self.draw.rectangle([x - px*4, mailbox_y - px*2, x + px*4, mailbox_y + px*2], fill=wood_color)
        self.draw.rectangle([x - px*4, mailbox_y - px*2, x - px*2, mailbox_y + px*2], fill=wood_light)
        # Mailbox opening
        self.draw.rectangle([x - px*2, mailbox_y - px, x + px*2, mailbox_y + px], fill=wood_dark)

        # Flag on mailbox (up when active = asking question)
        flag_color = (200, 50, 50) if active else (150, 40, 40)
        flag_x = x + px * 4
        flag_y = mailbox_y - px * 2
        # Flag pole
        self.draw.rectangle([flag_x, flag_y, flag_x + px, mailbox_y + px*2], fill=outline)
        # Flag (raised when active)
        if active:
            flag_bob = int(math.sin(frame * 0.2) * px * 0.5)
            self.draw.rectangle([flag_x + px, flag_y - px*2 + flag_bob, flag_x + px*4, flag_y + px + flag_bob], fill=flag_color)
        else:
            self.draw.rectangle([flag_x + px, mailbox_y, flag_x + px*4, mailbox_y + px*3], fill=flag_color)

        # Question mark icon floating nearby
        qmark_bob = int(math.sin(frame * 0.06) * px)
        qmark_x = x - px * 5
        qmark_y = y - px * 12 + qmark_bob
        # Question mark bubble
        self.draw.ellipse([qmark_x - px*2 - px, qmark_y - px*2 - px, qmark_x + px*2 + px, qmark_y + px*2 + px], fill=outline)
        self.draw.ellipse([qmark_x - px*2, qmark_y - px*2, qmark_x + px*2, qmark_y + px*2], fill=(255, 255, 255))
        # "?" character (simplified)
        self.draw.arc([qmark_x - px, qmark_y - px*1.5, qmark_x + px, qmark_y + px*0.5], 180, 0, fill=(80, 80, 80), width=max(1, px))
        self._safe_ellipse([qmark_x - px//2, qmark_y + px//2, qmark_x + px//2, qmark_y + px], fill=(80, 80, 80))

        # When active, show message being sent
        if active:
            # Glowing mailbox
            glow = abs(math.sin(frame * 0.12))
            glow_color = (255, 255, 200)
            self.draw.ellipse([x - px*5, mailbox_y - px*3, x + px*5, mailbox_y + px*3], fill=glow_color)
            # Redraw mailbox on glow
            self.draw.rectangle([x - px*4, mailbox_y - px*2, x + px*4, mailbox_y + px*2], fill=wood_color)

            # Letters/envelopes floating out
            for i in range(3):
                letter_phase = (frame * 0.3 + i * 10) % 30
                lx = x + int(math.sin(frame * 0.1 + i * 2) * px * 4)
                ly = mailbox_y - px * 2 - int(letter_phase * px * 0.5)
                if letter_phase < 25:
                    # Envelope
                    self.draw.rectangle([lx - px*2, ly - px, lx + px*2, ly + px], fill=paper_color)
                    # Envelope flap
                    self.draw.polygon([(lx - px*2, ly - px), (lx, ly), (lx + px*2, ly - px)], fill=(230, 220, 200))

            # Sparkles
            for i in range(4):
                sparkle_angle = frame * 0.1 + i * 1.5
                sparkle_x = x + int(math.cos(sparkle_angle) * px * 6)
                sparkle_y = mailbox_y + int(math.sin(sparkle_angle) * px * 4)
                if (frame + i * 6) % 15 < 10:
                    self.draw.rectangle([sparkle_x - px//2, sparkle_y - px//2,
                                       sparkle_x + px//2, sparkle_y + px//2], fill=(255, 255, 150))

    def _draw_thinking_spot(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a meditation stone/thinking pedestal on the hilltop."""
        outline = self.COLORS["outline"]
        stone_base = (160, 155, 150)
        stone_light = (190, 185, 180)
        stone_dark = (120, 115, 110)

        # Ground shadow
        self.draw.ellipse([x - px*6, y + px*2, x + px*6, y + px*4], fill=(60, 100, 50))

        # Stone pedestal base (wide flat stone)
        self.draw.ellipse([x - px*5 - px, y - px, x + px*5 + px, y + px*3 + px], fill=outline)
        self.draw.ellipse([x - px*5, y - px, x + px*5, y + px*3], fill=stone_base)
        self.draw.ellipse([x - px*3, y - px, x + px*2, y + px*2], fill=stone_light)

        # Meditation cushion on top (inviting spot to sit and think)
        cushion_color = (180, 100, 120) if not active else (220, 120, 140)
        cushion_light = (210, 140, 160)
        self.draw.ellipse([x - px*3 - px, y - px*3 - px, x + px*3 + px, y + px], fill=outline)
        self.draw.ellipse([x - px*3, y - px*3, x + px*3, y], fill=cushion_color)
        self.draw.ellipse([x - px*2, y - px*3, x + px, y - px], fill=cushion_light)

        # Floating thought bubble icon above (shows purpose)
        bubble_bob = int(math.sin(frame * 0.05) * px)
        bubble_y = y - px * 8 + bubble_bob
        # Bubble outline and fill
        self.draw.ellipse([x - px*3 - px, bubble_y - px*2 - px, x + px*3 + px, bubble_y + px*2 + px], fill=outline)
        self.draw.ellipse([x - px*3, bubble_y - px*2, x + px*3, bubble_y + px*2], fill=(255, 255, 255))
        # Small connecting dots
        self.draw.ellipse([x - px, y - px*5 + bubble_bob, x + px, y - px*4 + bubble_bob], fill=(255, 255, 255))
        self._safe_ellipse([x - px//2, y - px*6 + bubble_bob, x + px//2, y - px*5 + bubble_bob], fill=(255, 255, 255))
        # "..." dots inside bubble (thinking indicator)
        dot_y = bubble_y
        for i in range(3):
            dot_x = x - px*2 + i * px * 2
            self._safe_ellipse([dot_x - px//2, dot_y - px//2, dot_x + px//2, dot_y + px//2], fill=(100, 100, 100))

        # When active, show elaborate thinking effects
        if active:
            # Glowing aura around pedestal
            aura_pulse = int(abs(math.sin(frame * 0.08)) * px * 2)
            aura_color = (255, 255, 200, 100)
            self.draw.ellipse([x - px*6 - aura_pulse, y - px*4 - aura_pulse,
                             x + px*6 + aura_pulse, y + px*3 + aura_pulse], fill=(255, 255, 220))

            # Redraw cushion on top of aura
            self.draw.ellipse([x - px*3 - px, y - px*3 - px, x + px*3 + px, y + px], fill=outline)
            self.draw.ellipse([x - px*3, y - px*3, x + px*3, y], fill=(220, 120, 140))

            # Orbiting thought sparkles
            for i in range(6):
                angle = frame * 0.08 + i * math.pi / 3
                dist = px * 6 + int(math.sin(frame * 0.15 + i * 0.7) * px * 2)
                sx = x + int(math.cos(angle) * dist)
                sy = y - px * 4 + int(math.sin(angle) * dist * 0.4)
                sparkle_size = px + int(abs(math.sin(frame * 0.1 + i)) * px)
                sparkle_color = [(255, 255, 180), (255, 220, 150), (200, 255, 200)][i % 3]
                if (frame + i * 5) % 20 < 15:
                    self.draw.rectangle([sx - sparkle_size, sy - sparkle_size,
                                       sx + sparkle_size, sy + sparkle_size], fill=sparkle_color)

            # Rising thought bubbles
            for i in range(3):
                bubble_phase = (frame * 0.2 + i * 12) % 30
                bx = x + int(math.sin(frame * 0.05 + i * 2) * px * 4)
                by = y - px * 6 - int(bubble_phase * px * 0.7)
                bsize = px * (3 - i) // 2 + px
                if bubble_phase < 25:
                    self.draw.ellipse([bx - bsize - px, by - bsize - px,
                                     bx + bsize + px, by + bsize + px], fill=outline)
                    self.draw.ellipse([bx - bsize, by - bsize, bx + bsize, by + bsize], fill=(255, 255, 255))

    def _draw_ambient_particles(self, frame: int, phase: str, px: int) -> None:
        """Draw floating ambient particles for a living world feel."""
        import random

        # Use frame-based seed for consistent but animated particles
        num_particles = 12

        for i in range(num_particles):
            # Each particle has its own movement pattern
            random.seed(i * 777)
            base_x = random.randint(0, self.width)
            base_y = random.randint(int(self.height * 0.25), int(self.height * 0.85))
            speed_x = random.uniform(0.3, 0.8)
            speed_y = random.uniform(0.1, 0.3)
            phase_offset = random.uniform(0, math.pi * 2)

            # Animate position
            x = int((base_x + frame * speed_x) % self.width)
            y = int(base_y + math.sin(frame * 0.05 + phase_offset) * px * 4)

            if phase == "night":
                # Fireflies - glowing yellow dots that pulse
                glow = abs(math.sin(frame * 0.1 + i))
                if glow > 0.5:
                    brightness = int(150 + glow * 105)
                    # Glow effect
                    self.draw.ellipse(
                        [x - px * 2, y - px * 2, x + px * 2, y + px * 2],
                        fill=(brightness // 2, brightness // 2, 0)
                    )
                    # Core
                    self.draw.rectangle(
                        [x - px // 2, y - px // 2, x + px // 2, y + px // 2],
                        fill=(brightness, brightness, 50)
                    )
            else:
                # Floating leaves/petals during day
                leaf_color = [(180, 220, 140), (140, 200, 120), (200, 180, 160)][i % 3]
                # Leaf rotates as it floats
                angle = frame * 0.08 + i
                leaf_w = int(px * 1.5)
                leaf_h = int(px * 0.8)
                # Simple rotating leaf (just offset the rectangle slightly)
                offset = int(math.sin(angle) * px)
                self.draw.rectangle(
                    [x - leaf_w + offset, y - leaf_h,
                     x + leaf_w + offset, y + leaf_h],
                    fill=leaf_color
                )

    def _draw_pixel_tree(self, x: int, y: int, scale: float, px: int, frame: int) -> None:
        """Draw a pixel art tree like in the reference image - round canopy with trunk."""
        # Tree dimensions - taller trunk for proper tree look
        trunk_w = int(px * 3 * scale)
        trunk_h = int(px * 12 * scale)  # Doubled trunk height
        canopy_r = int(px * 8 * scale)

        # More noticeable sway animation - each tree sways at different rate
        sway = int(math.sin(frame * 0.03 + x * 0.02) * px * 2 * scale)

        # Shadow on ground (ellipse)
        shadow_w = int(canopy_r * 1.2)
        shadow_h = int(canopy_r * 0.4)
        self.draw.ellipse(
            [x - shadow_w, y + trunk_h - shadow_h // 2,
             x + shadow_w, y + trunk_h + shadow_h // 2],
            fill=(60, 120, 50)
        )

        # Trunk - rectangular with dark outline
        trunk_left = x - trunk_w // 2
        trunk_top = y
        # Outline
        self.draw.rectangle(
            [trunk_left - px, trunk_top, trunk_left + trunk_w + px, y + trunk_h + px],
            fill=self.COLORS["outline"]
        )
        # Main trunk
        self.draw.rectangle(
            [trunk_left, trunk_top, trunk_left + trunk_w, y + trunk_h],
            fill=self.COLORS["tree_trunk"]
        )
        # Trunk highlight
        self.draw.rectangle(
            [trunk_left, trunk_top, trunk_left + trunk_w // 3, y + trunk_h],
            fill=self.COLORS["tree_trunk_dark"]
        )

        # Canopy - large round/oval shape with outline
        canopy_x = x + sway
        canopy_y = y - canopy_r // 2

        # Dark outline
        self.draw.ellipse(
            [canopy_x - canopy_r - px * 2, canopy_y - canopy_r - px * 2,
             canopy_x + canopy_r + px * 2, canopy_y + canopy_r + px * 2],
            fill=self.COLORS["outline"]
        )

        # Main canopy (darker base)
        self.draw.ellipse(
            [canopy_x - canopy_r, canopy_y - canopy_r,
             canopy_x + canopy_r, canopy_y + canopy_r],
            fill=self.COLORS["tree_leaves_dark"]
        )

        # Lighter top portion for 3D effect
        self.draw.ellipse(
            [canopy_x - canopy_r + px * 2, canopy_y - canopy_r,
             canopy_x + canopy_r - px * 2, canopy_y + px * 2],
            fill=self.COLORS["tree_leaves"]
        )

        # Highlight spot
        highlight_x = canopy_x - canopy_r // 3
        highlight_y = canopy_y - canopy_r // 3
        highlight_r = canopy_r // 3
        self.draw.ellipse(
            [highlight_x - highlight_r, highlight_y - highlight_r,
             highlight_x + highlight_r, highlight_y + highlight_r],
            fill=self.COLORS["tree_leaves_light"]
        )

    def _draw_pixel_clouds(self, frame: int, phase: str) -> None:
        """Draw pixel art style clouds."""
        px = max(2, self.height // 120)

        # Cloud color based on time
        if phase == "night":
            cloud_color = (80, 90, 110)
        else:
            cloud_color = (255, 255, 255)

        import random
        random.seed(789)

        for i in range(3):
            base_x = random.randint(0, self.width)
            y = random.randint(int(self.height * 0.05), int(self.height * 0.18))
            speed = 0.2 + i * 0.1

            # Drift across screen
            x = int((base_x + frame * speed) % (self.width + 100) - 50)

            # Draw blocky cloud shape
            cloud_w = px * (8 + i * 2)
            cloud_h = px * 4

            # Main body
            self.draw.rectangle([x - cloud_w, y, x + cloud_w, y + cloud_h], fill=cloud_color)
            # Left bump
            self.draw.rectangle([x - cloud_w - px * 2, y + px, x - cloud_w, y + cloud_h - px], fill=cloud_color)
            # Right bump
            self.draw.rectangle([x + cloud_w, y + px, x + cloud_w + px * 2, y + cloud_h - px], fill=cloud_color)
            # Top bump
            self.draw.rectangle([x - px * 3, y - px * 2, x + px * 3, y], fill=cloud_color)

    def _render_claude_character(self, state: GameState) -> None:
        """Render Claude as a pixel art character with bold outlines like reference."""
        activity = state.main_agent.activity.value
        frame = self._frame_count

        # Pixel size for consistent chunky look
        px = max(2, self.height // 120)
        scale = self.height / 350

        # Character dimensions
        char_w = int(px * 14)
        char_h = int(px * 18)

        # Base position from game state - offset from screen center
        screen_center_x = self.width // 2
        screen_center_y = int(self.height * 0.58)

        # Apply Claude's position offset from state
        center_x = screen_center_x + int(state.main_agent.position.x)
        ground_y = screen_center_y + int(state.main_agent.position.y)

        # Get movement state
        is_walking = state.main_agent.is_walking
        facing = state.main_agent.facing_direction

        # Breathing animation - subtle scale pulse
        breath = 1.0 + math.sin(frame * 0.04) * 0.02

        # Walking animation - leg movement and bob
        if is_walking:
            # Faster bob while walking
            bob = int(math.sin(frame * 0.3) * px * 1.5)
            # Look in direction of movement
            look_dir = facing
        else:
            # Idle bob - gentle floating motion
            bob = int(math.sin(frame * 0.08) * px * breath)

            # Look-around animation - more natural pattern
            look_cycle = (frame % 400) / 400.0
            if look_cycle < 0.08:
                look_dir = -1  # Look left
            elif look_cycle < 0.15:
                look_dir = -1  # Hold left
            elif look_cycle < 0.25:
                look_dir = 0   # Center
            elif look_cycle < 0.55:
                look_dir = 0   # Hold center (longest)
            elif look_cycle < 0.63:
                look_dir = 1   # Look right
            elif look_cycle < 0.70:
                look_dir = 1   # Hold right
            elif look_cycle < 0.80:
                look_dir = 0   # Back to center
            else:
                look_dir = 0   # Hold center

        # Occasional head tilt during thinking
        head_tilt = 0
        if activity == "thinking" and not is_walking:
            head_tilt = int(math.sin(frame * 0.03) * px)

        # Activity-specific movement only when not walking
        if not is_walking:
            if activity == "thinking":
                center_x += int(math.sin(frame * 0.02) * px * 3)
            elif activity == "searching":
                center_x += int(math.sin(frame * 0.05) * px * 5)

        # Colors
        body_color = self.COLORS["claude_body"]
        dark_color = self.COLORS["claude_dark"]
        light_color = self.COLORS["claude_light"]
        outline = self.COLORS["outline"]

        # Calculate positions
        feet_y = ground_y + bob
        body_y = feet_y - int(px * 8)
        head_y = body_y - int(px * 8)

        # === SHADOW ===
        shadow_w = int(px * 8)
        shadow_h = int(px * 3)
        self.draw.ellipse(
            [center_x - shadow_w, ground_y + px * 2,
             center_x + shadow_w, ground_y + px * 2 + shadow_h],
            fill=(60, 120, 50)
        )

        # === FEET (two small blocks with walking animation) ===
        foot_w = int(px * 3)
        foot_h = int(px * 3)
        foot_spacing = int(px * 2)

        # Walking animation - alternating foot positions
        if is_walking:
            walk_cycle = math.sin(frame * 0.4)
            left_foot_offset = int(walk_cycle * px * 3)
            right_foot_offset = int(-walk_cycle * px * 3)
        else:
            left_foot_offset = 0
            right_foot_offset = 0

        # Left foot outline + fill
        left_foot_y = feet_y - left_foot_offset
        self.draw.rectangle(
            [center_x - foot_spacing - foot_w - px, left_foot_y - px,
             center_x - foot_spacing + px, left_foot_y + foot_h + px],
            fill=outline
        )
        self.draw.rectangle(
            [center_x - foot_spacing - foot_w, left_foot_y,
             center_x - foot_spacing, left_foot_y + foot_h],
            fill=dark_color
        )

        # Right foot outline + fill
        right_foot_y = feet_y - right_foot_offset
        self.draw.rectangle(
            [center_x + foot_spacing - px, right_foot_y - px,
             center_x + foot_spacing + foot_w + px, right_foot_y + foot_h + px],
            fill=outline
        )
        self.draw.rectangle(
            [center_x + foot_spacing, right_foot_y,
             center_x + foot_spacing + foot_w, right_foot_y + foot_h],
            fill=dark_color
        )

        # === BODY (wider rectangle) ===
        body_w = int(px * 10)
        body_h = int(px * 8)

        # Body outline
        self.draw.rectangle(
            [center_x - body_w // 2 - px * 2, body_y - px * 2,
             center_x + body_w // 2 + px * 2, body_y + body_h + px * 2],
            fill=outline
        )
        # Body fill
        self.draw.rectangle(
            [center_x - body_w // 2, body_y,
             center_x + body_w // 2, body_y + body_h],
            fill=body_color
        )
        # Body shading (left side darker)
        self.draw.rectangle(
            [center_x - body_w // 2, body_y,
             center_x - body_w // 2 + px * 2, body_y + body_h],
            fill=dark_color
        )

        # === ARMS ===
        arm_w = int(px * 3)
        arm_h = int(px * 5)
        arm_y = body_y + int(px * 2)  # Arms attach near top of body

        # Arm swing animation when walking
        if is_walking:
            arm_swing = int(math.sin(frame * 0.4) * px * 2)
        else:
            # Gentle idle arm movement
            arm_swing = int(math.sin(frame * 0.06) * px)

        # Left arm - outline then fill
        left_arm_x = center_x - body_w // 2 - arm_w
        self.draw.rectangle(
            [left_arm_x - px, arm_y - arm_swing - px,
             left_arm_x + arm_w + px, arm_y - arm_swing + arm_h + px],
            fill=outline
        )
        self.draw.rectangle(
            [left_arm_x, arm_y - arm_swing,
             left_arm_x + arm_w, arm_y - arm_swing + arm_h],
            fill=body_color
        )

        # Right arm - outline then fill
        right_arm_x = center_x + body_w // 2
        self.draw.rectangle(
            [right_arm_x - px, arm_y + arm_swing - px,
             right_arm_x + arm_w + px, arm_y + arm_swing + arm_h + px],
            fill=outline
        )
        self.draw.rectangle(
            [right_arm_x, arm_y + arm_swing,
             right_arm_x + arm_w, arm_y + arm_swing + arm_h],
            fill=body_color
        )

        # === HEAD (slightly narrower than body) ===
        head_w = int(px * 8)
        head_h = int(px * 8)

        # Head outline
        self.draw.rectangle(
            [center_x - head_w // 2 - px * 2, head_y - px * 2,
             center_x + head_w // 2 + px * 2, head_y + head_h + px * 2],
            fill=outline
        )
        # Head fill
        self.draw.rectangle(
            [center_x - head_w // 2, head_y,
             center_x + head_w // 2, head_y + head_h],
            fill=body_color
        )
        # Head highlight (top-left)
        self.draw.rectangle(
            [center_x - head_w // 2 + px, head_y + px,
             center_x - head_w // 2 + px * 3, head_y + px * 3],
            fill=light_color
        )

        # === EYES ===
        eye_w = int(px * 2)
        eye_h = int(px * 3)
        eye_spacing = int(px * 2)
        eye_y = head_y + int(px * 2)
        eye_offset = look_dir * px

        blink = (frame % 150) < 5

        if not blink:
            # Left eye
            self.draw.rectangle(
                [center_x - eye_spacing - eye_w + eye_offset, eye_y,
                 center_x - eye_spacing + eye_offset, eye_y + eye_h],
                fill=self.COLORS["claude_eyes"]
            )
            # Right eye
            self.draw.rectangle(
                [center_x + eye_spacing + eye_offset, eye_y,
                 center_x + eye_spacing + eye_w + eye_offset, eye_y + eye_h],
                fill=self.COLORS["claude_eyes"]
            )
        else:
            # Closed eyes (horizontal lines)
            self.draw.rectangle(
                [center_x - eye_spacing - eye_w, eye_y + eye_h // 2,
                 center_x - eye_spacing, eye_y + eye_h // 2 + px],
                fill=self.COLORS["claude_eyes"]
            )
            self.draw.rectangle(
                [center_x + eye_spacing, eye_y + eye_h // 2,
                 center_x + eye_spacing + eye_w, eye_y + eye_h // 2 + px],
                fill=self.COLORS["claude_eyes"]
            )

        # Activity accessories
        self._render_activity_accessory(center_x, head_y, body_y + bob, scale, activity, frame)

    def _render_subagent_connections(self, state: GameState) -> None:
        """Render connection lines from main Claude to subagents."""
        from claude_world.types import EntityType

        px = max(2, self.height // 120)
        frame = self._frame_count

        # Screen center and Claude's position
        screen_center_x = self.width // 2
        screen_center_y = int(self.height * 0.58)
        claude_x = screen_center_x + int(state.main_agent.position.x)
        claude_y = screen_center_y + int(state.main_agent.position.y)

        # Get all subagents
        subagents = [e for e in state.entities.values() if e.type == EntityType.SUB_AGENT]

        for agent in subagents:
            agent_screen_x = screen_center_x + int(agent.position.x)
            agent_screen_y = screen_center_y + int(agent.position.y)

            # Get agent type for color coding
            agent_type = getattr(agent, 'agent_type', 'general-purpose')
            status = getattr(agent, 'status', None)
            status_value = status.value if hasattr(status, 'value') else 'idle'

            # Draw connection line with animated dashes
            self._draw_connection_line(
                claude_x, claude_y - px * 8,  # From Claude's body center
                agent_screen_x, agent_screen_y,
                px, frame, agent_type, status_value
            )

    def _draw_connection_line(self, x1: int, y1: int, x2: int, y2: int, px: int, frame: int,
                                agent_type: str = "general-purpose", status: str = "idle") -> None:
        """Draw an animated dashed connection line between two points."""
        # Calculate line parameters
        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 1:
            return

        # Normalize direction
        nx = dx / distance
        ny = dy / distance

        # Animated dash offset (direction: from Claude to agent for "working", reverse for "complete")
        if status == "complete":
            dash_offset = (distance - (frame * 3) % 20) % 20
        else:
            dash_offset = (frame * 2) % 20

        # Draw dashed line with glow effect
        dash_len = px * 4
        gap_len = px * 2
        segment_len = dash_len + gap_len

        # Color based on agent type
        type_colors = {
            "Explore": (100, 200, 150),      # Green
            "Plan": (180, 140, 220),          # Purple
            "general-purpose": (100, 180, 220),  # Blue/cyan
        }
        base_rgb = type_colors.get(agent_type, (100, 180, 220))

        # Pulse effect
        pulse = abs(math.sin(frame * 0.1))
        base_color = tuple(min(255, int(c + 30 * pulse)) for c in base_rgb)

        # Line thickness based on status
        line_width = max(1, px)
        if status == "working":
            line_width = max(2, px + 1)
        elif status == "complete":
            # Thicker, brighter line when complete
            line_width = max(3, px + 2)
            base_color = (100, 255, 150)  # Green for complete

        # Draw each dash segment
        pos = dash_offset
        while pos < distance:
            start_pos = max(0, pos)
            end_pos = min(distance, pos + dash_len)

            if end_pos > start_pos:
                sx = int(x1 + nx * start_pos)
                sy = int(y1 + ny * start_pos)
                ex = int(x1 + nx * end_pos)
                ey = int(y1 + ny * end_pos)

                # Draw line segment
                self.draw.line([(sx, sy), (ex, ey)], fill=base_color, width=line_width)

            pos += segment_len

        # Draw direction arrows along the line
        if distance > 60:
            arrow_count = max(1, int(distance / 80))
            for i in range(arrow_count):
                arrow_pos = distance * (i + 1) / (arrow_count + 1)
                ax = int(x1 + nx * arrow_pos)
                ay = int(y1 + ny * arrow_pos)

                # Arrow pointing toward subagent (or reverse if complete)
                arrow_dir = 1 if status != "complete" else -1
                arrow_len = px * 3
                # Perpendicular
                perp_x, perp_y = -ny, nx

                # Arrow points
                tip_x = ax + int(nx * arrow_len * arrow_dir)
                tip_y = ay + int(ny * arrow_len * arrow_dir)
                left_x = ax + int(perp_x * arrow_len * 0.5)
                left_y = ay + int(perp_y * arrow_len * 0.5)
                right_x = ax - int(perp_x * arrow_len * 0.5)
                right_y = ay - int(perp_y * arrow_len * 0.5)

                # Draw arrow
                self.draw.polygon(
                    [(tip_x, tip_y), (left_x, left_y), (right_x, right_y)],
                    fill=base_color
                )

        # Draw energy particles along the line (only if distance is large enough)
        if distance > 30:
            particle_count = 3 if status == "working" else 2
            particle_speed = 4 if status == "working" else 2
            for i in range(particle_count):
                particle_pos = ((frame * particle_speed + i * 30) % int(distance))
                if status == "complete":
                    particle_pos = distance - particle_pos  # Reverse direction
                px_pos = int(x1 + nx * particle_pos)
                py_pos = int(y1 + ny * particle_pos)
                particle_size = px + int(abs(math.sin(frame * 0.2 + i)) * px)
                # Particle color matches line
                particle_color = tuple(min(255, c + 50) for c in base_color)
                self.draw.ellipse(
                    [px_pos - particle_size, py_pos - particle_size,
                     px_pos + particle_size, py_pos + particle_size],
                    fill=particle_color
                )

    def _render_subagents(self, state: GameState) -> None:
        """Render all active subagents."""
        from claude_world.types import EntityType

        px = max(2, self.height // 120)
        frame = self._frame_count

        # Screen center for position offset
        screen_center_x = self.width // 2
        screen_center_y = int(self.height * 0.58)

        # Get all subagents
        subagents = [e for e in state.entities.values() if e.type == EntityType.SUB_AGENT]

        for agent in subagents:
            agent_x = screen_center_x + int(agent.position.x)
            agent_y = screen_center_y + int(agent.position.y)
            self._draw_subagent(agent_x, agent_y, agent, px, frame)

    def _draw_subagent(self, x: int, y: int, agent, px: int, frame: int) -> None:
        """Draw a single subagent character with arms and feet."""
        # Subagent colors based on type
        agent_colors = {
            "Explore": ((100, 200, 150), (70, 160, 120)),    # Green
            "Plan": ((180, 140, 220), (140, 100, 180)),       # Purple
            "general-purpose": ((150, 180, 220), (110, 140, 180)),  # Blue
        }
        body_color, dark_color = agent_colors.get(
            agent.agent_type, ((150, 180, 220), (110, 140, 180))
        )
        outline = self.COLORS["outline"]

        # Bobbing animation
        bob = int(math.sin(frame * 0.1 + hash(agent.id) % 100) * px)

        # Check if walking
        is_walking = getattr(agent, 'is_walking', False)

        # Size (smaller than main Claude)
        body_w = int(px * 6)
        body_h = int(px * 5)
        head_w = int(px * 5)
        head_h = int(px * 5)

        # Shadow
        self.draw.ellipse(
            [x - px * 4, y + px, x + px * 4, y + px * 3],
            fill=(60, 120, 50)
        )

        # === FEET ===
        foot_w = int(px * 2)
        foot_h = int(px * 2)
        foot_y = y + bob

        # Walking animation for feet
        if is_walking:
            left_foot_offset = int(math.sin(frame * 0.4 + hash(agent.id)) * px * 2)
            right_foot_offset = int(math.sin(frame * 0.4 + hash(agent.id) + math.pi) * px * 2)
        else:
            left_foot_offset = 0
            right_foot_offset = 0

        # Left foot - outline then fill
        left_foot_x = x - body_w // 2 + px
        self.draw.rectangle(
            [left_foot_x - px, foot_y - left_foot_offset - px,
             left_foot_x + foot_w + px, foot_y - left_foot_offset + foot_h + px],
            fill=outline
        )
        self.draw.rectangle(
            [left_foot_x, foot_y - left_foot_offset,
             left_foot_x + foot_w, foot_y - left_foot_offset + foot_h],
            fill=body_color
        )

        # Right foot - outline then fill
        right_foot_x = x + body_w // 2 - foot_w - px
        self.draw.rectangle(
            [right_foot_x - px, foot_y - right_foot_offset - px,
             right_foot_x + foot_w + px, foot_y - right_foot_offset + foot_h + px],
            fill=outline
        )
        self.draw.rectangle(
            [right_foot_x, foot_y - right_foot_offset,
             right_foot_x + foot_w, foot_y - right_foot_offset + foot_h],
            fill=body_color
        )

        # Body outline + fill
        self.draw.rectangle(
            [x - body_w // 2 - px, y - body_h + bob - px,
             x + body_w // 2 + px, y + bob + px],
            fill=outline
        )
        self.draw.rectangle(
            [x - body_w // 2, y - body_h + bob,
             x + body_w // 2, y + bob],
            fill=body_color
        )
        self.draw.rectangle(
            [x - body_w // 2, y - body_h + bob,
             x - body_w // 2 + px * 2, y + bob],
            fill=dark_color
        )

        # === ARMS ===
        arm_w = int(px * 2)
        arm_h = int(px * 4)
        arm_y = y - body_h + bob + int(px * 2)

        # Arm swing animation
        if is_walking:
            arm_swing = int(math.sin(frame * 0.4 + hash(agent.id)) * px * 2)
        else:
            arm_swing = int(math.sin(frame * 0.06 + hash(agent.id)) * px)

        # Left arm - outline then fill
        left_arm_x = x - body_w // 2 - arm_w
        self.draw.rectangle(
            [left_arm_x - px, arm_y - arm_swing - px,
             left_arm_x + arm_w + px, arm_y - arm_swing + arm_h + px],
            fill=outline
        )
        self.draw.rectangle(
            [left_arm_x, arm_y - arm_swing,
             left_arm_x + arm_w, arm_y - arm_swing + arm_h],
            fill=body_color
        )

        # Right arm - outline then fill
        right_arm_x = x + body_w // 2
        self.draw.rectangle(
            [right_arm_x - px, arm_y + arm_swing - px,
             right_arm_x + arm_w + px, arm_y + arm_swing + arm_h + px],
            fill=outline
        )
        self.draw.rectangle(
            [right_arm_x, arm_y + arm_swing,
             right_arm_x + arm_w, arm_y + arm_swing + arm_h],
            fill=body_color
        )

        # Head outline + fill
        head_y = y - body_h - head_h // 2 + bob
        self.draw.rectangle(
            [x - head_w // 2 - px, head_y - head_h // 2 - px,
             x + head_w // 2 + px, head_y + head_h // 2 + px],
            fill=outline
        )
        self.draw.rectangle(
            [x - head_w // 2, head_y - head_h // 2,
             x + head_w // 2, head_y + head_h // 2],
            fill=body_color
        )

        # Eyes
        eye_y = head_y - px
        self.draw.rectangle(
            [x - px * 2, eye_y, x - px, eye_y + px * 2],
            fill=self.COLORS["claude_eyes"]
        )
        self.draw.rectangle(
            [x + px, eye_y, x + px * 2, eye_y + px * 2],
            fill=self.COLORS["claude_eyes"]
        )

        # Activity-specific indicator above subagent
        activity = agent.activity.value if hasattr(agent.activity, 'value') else str(agent.activity)
        indicator_y = head_y - head_h - px * 2

        if activity == "exploring":
            # Small binoculars icon
            lens_r = px
            gap = px * 2
            self.draw.ellipse(
                [x - gap - lens_r, indicator_y - lens_r, x - gap + lens_r, indicator_y + lens_r],
                fill=(80, 80, 100), outline=(60, 60, 80)
            )
            self.draw.ellipse(
                [x + gap - lens_r, indicator_y - lens_r, x + gap + lens_r, indicator_y + lens_r],
                fill=(80, 80, 100), outline=(60, 60, 80)
            )
            # Glint animation
            glint_x = x - gap + int(math.sin(frame * 0.1) * px)
            self.draw.rectangle([glint_x, indicator_y - px, glint_x + 1, indicator_y], fill=(180, 200, 255))

        elif activity == "thinking":
            # Mini thought bubble
            bubble_bob = int(math.sin(frame * 0.08) * 2)
            for i, (bx_off, by_off, br) in enumerate([(-px, px, 1), (-px*2, 0, 2), (-px*3, -px*2, 3)]):
                self.draw.ellipse(
                    [x + bx_off - br, indicator_y + by_off + bubble_bob - br,
                     x + bx_off + br, indicator_y + by_off + bubble_bob + br],
                    fill=(255, 255, 255), outline=(200, 200, 200)
                )

        elif activity == "reading":
            # Mini book icon
            book_w, book_h = px * 3, px * 2
            self.draw.rectangle(
                [x - book_w // 2, indicator_y - book_h // 2, x + book_w // 2, indicator_y + book_h // 2],
                fill=(240, 230, 210), outline=(180, 160, 130)
            )
            # Spine
            self.draw.line([(x, indicator_y - book_h // 2), (x, indicator_y + book_h // 2)], fill=(160, 140, 110))

        elif activity == "writing":
            # Pencil/code symbol
            symbols = ["{}", "< >", "[]"]
            sym_idx = (frame // 20 + hash(agent.id)) % len(symbols)
            self.draw.text((x - px * 2, indicator_y - px), symbols[sym_idx], fill=(150, 200, 255))

        elif activity == "searching":
            # Mini magnifying glass
            glass_r = px * 2
            self.draw.ellipse(
                [x - glass_r, indicator_y - glass_r, x + glass_r, indicator_y + glass_r],
                outline=(200, 150, 50), width=1
            )
            self.draw.line(
                [(x + glass_r - 1, indicator_y + glass_r - 1), (x + glass_r + px, indicator_y + glass_r + px)],
                fill=(200, 150, 50), width=1
            )

        elif activity == "building":
            # Mini rotating gear
            gear_r = px * 2
            rotation = frame * 0.08 + hash(agent.id)
            for i in range(4):
                angle = rotation + i * math.pi / 2
                sx = x + int(math.cos(angle) * gear_r)
                sy = indicator_y + int(math.sin(angle) * gear_r)
                self.draw.rectangle([sx - 1, sy - 1, sx + 1, sy + 1], fill=(200, 150, 50))
            self.draw.ellipse([x - px, indicator_y - px, x + px, indicator_y + px], fill=(180, 130, 40))

        elif activity == "communicating":
            # Radio waves
            wave_phase = (frame * 0.15) % 1.0
            for i in range(2):
                arc_r = int((px + i * px * 2) * (0.5 + wave_phase * 0.5))
                alpha = int(200 * (1 - wave_phase))
                self.draw.arc(
                    [x + px - arc_r, indicator_y - arc_r, x + px + arc_r, indicator_y + arc_r],
                    start=-45, end=45, fill=(alpha, alpha, 255), width=1
                )

        else:
            # Default: simple orbiting dot
            orbit_angle = frame * 0.15 + hash(agent.id) % 100
            orbit_r = px * 4
            dot_x = x + int(math.cos(orbit_angle) * orbit_r)
            dot_y = indicator_y + int(math.sin(orbit_angle) * orbit_r * 0.5)
            self.draw.ellipse(
                [dot_x - px, dot_y - px, dot_x + px, dot_y + px],
                fill=(200, 200, 255)
            )

        # Agent type label (small text above)
        type_short = {
            "Explore": "EXP",
            "Plan": "PLAN",
            "general-purpose": "GEN",
        }.get(agent.agent_type, "AGT")
        self.draw.text(
            (x - px * 3, head_y - head_h - px * 4),
            type_short,
            fill=(200, 200, 200)
        )

        # Status indicator (above type label)
        status = getattr(agent, 'status', None)
        if status:
            status_y = head_y - head_h - px * 8
            status_value = status.value if hasattr(status, 'value') else str(status)

            if status_value == "complete":
                # Green checkmark
                check_color = (100, 255, 100)
                # Draw checkmark
                self.draw.line([(x - px * 2, status_y), (x, status_y + px * 2)], fill=check_color, width=2)
                self.draw.line([(x, status_y + px * 2), (x + px * 3, status_y - px)], fill=check_color, width=2)
                # Glow effect
                self.draw.ellipse(
                    [x - px * 4, status_y - px * 2, x + px * 4, status_y + px * 4],
                    outline=(100, 255, 100)
                )

            elif status_value == "error":
                # Red X
                error_color = (255, 100, 100)
                self.draw.line([(x - px * 2, status_y - px), (x + px * 2, status_y + px * 3)], fill=error_color, width=2)
                self.draw.line([(x - px * 2, status_y + px * 3), (x + px * 2, status_y - px)], fill=error_color, width=2)
                # Pulsing glow
                pulse = abs(math.sin(frame * 0.2))
                glow_r = int(px * 4 * (1 + pulse * 0.3))
                self.draw.ellipse(
                    [x - glow_r, status_y - glow_r // 2, x + glow_r, status_y + glow_r],
                    outline=(255, int(100 * pulse), int(100 * pulse))
                )

            elif status_value == "working":
                # Lightning bolt / energy indicator
                bolt_color = (255, 220, 100)
                # Animated bolt
                bolt_offset = int(math.sin(frame * 0.3) * px)
                points = [
                    (x - px, status_y - px + bolt_offset),
                    (x + px, status_y + px + bolt_offset),
                    (x, status_y + px + bolt_offset),
                    (x + px * 2, status_y + px * 3 + bolt_offset),
                    (x, status_y + px * 2 + bolt_offset),
                    (x + px, status_y + px * 2 + bolt_offset),
                ]
                for i in range(len(points) - 1):
                    self.draw.line([points[i], points[i + 1]], fill=bolt_color, width=1)
                # Sparkle
                sparkle_phase = frame * 0.2
                for i in range(3):
                    angle = sparkle_phase + i * 2.1
                    sx = x + int(math.cos(angle) * px * 3)
                    sy = status_y + px + int(math.sin(angle) * px * 2)
                    self.draw.point((sx, sy), fill=(255, 255, 200))

    def _render_activity_accessory(self, x: int, head_y: int, body_y: int,
                                    scale: float, activity: str, frame: int) -> None:
        """Render activity-specific visual elements (icons near Claude, not text)."""
        # Note: Text bubble is now handled by _render_activity_indicator
        # This method only draws small icons/props for certain activities

        if activity == "reading":
            # Book
            book_y = body_y - int(20 * scale)
            book_w = int(25 * scale)
            book_h = int(18 * scale)
            self.draw.rectangle(
                [x - book_w, book_y - book_h, x + book_w, book_y + book_h],
                fill=(240, 230, 210), outline=(180, 160, 130)
            )
            # Pages
            for i in range(3):
                self.draw.line(
                    [(x - book_w + 5 + i * 8, book_y - book_h + 5),
                     (x - book_w + 5 + i * 8, book_y + book_h - 5)],
                    fill=(200, 190, 170)
                )

        elif activity == "writing":
            # Floating code/text particles
            for i in range(5):
                angle = (frame * 0.02 + i * 1.2) % (2 * math.pi)
                radius = 50 + i * 10
                px = x + int(math.cos(angle) * radius * scale * 0.4)
                py = body_y - int(10 * scale) + int(math.sin(angle * 2) * 20)

                # Code symbols
                symbols = ["{ }", "< >", "[ ]", "( )", "=>"]
                self.draw.text((px, py), symbols[i % len(symbols)],
                              fill=self.COLORS["accent_secondary"])

        elif activity == "searching":
            # Magnifying glass
            glass_x = x + int(45 * scale)
            glass_y = head_y
            glass_r = int(15 * scale)
            self.draw.ellipse(
                [glass_x - glass_r, glass_y - glass_r, glass_x + glass_r, glass_y + glass_r],
                outline=self.COLORS["accent_primary"], width=3
            )
            self.draw.line(
                [(glass_x + glass_r - 3, glass_y + glass_r - 3),
                 (glass_x + glass_r + 10, glass_y + glass_r + 10)],
                fill=self.COLORS["accent_primary"], width=4
            )

        elif activity == "building":
            # Gear/tool
            gear_x = x + int(50 * scale)
            gear_y = body_y - int(30 * scale)
            rotation = frame * 0.05

            for i in range(6):
                angle = rotation + i * math.pi / 3
                x1 = gear_x + int(math.cos(angle) * 12)
                y1 = gear_y + int(math.sin(angle) * 12)
                x2 = gear_x + int(math.cos(angle) * 20)
                y2 = gear_y + int(math.sin(angle) * 20)
                self.draw.line([(x1, y1), (x2, y2)], fill=self.COLORS["accent_primary"], width=3)

            self.draw.ellipse(
                [gear_x - 10, gear_y - 10, gear_x + 10, gear_y + 10],
                fill=self.COLORS["accent_primary"]
            )

        elif activity == "thinking":
            # Floating thought bubbles with ellipsis
            bubble_x = x + int(50 * scale)
            bubble_y = head_y - int(20 * scale)

            # Three ascending bubbles
            for i in range(3):
                size = int((4 + i * 3) * scale)
                bx = bubble_x - i * int(8 * scale)
                by = bubble_y - i * int(12 * scale)
                bob_offset = int(math.sin(frame * 0.08 + i * 0.5) * 3)
                self.draw.ellipse(
                    [bx - size, by - size + bob_offset, bx + size, by + size + bob_offset],
                    fill=(255, 255, 255), outline=(200, 200, 200)
                )

            # Main thought cloud
            cloud_x = bubble_x - int(30 * scale)
            cloud_y = bubble_y - int(50 * scale)
            cloud_w = int(40 * scale)
            cloud_h = int(25 * scale)
            bob = int(math.sin(frame * 0.06) * 2)

            # Cloud shape (overlapping circles)
            for cx, cy, cr in [
                (cloud_x, cloud_y + bob, cloud_h // 2),
                (cloud_x + cloud_w // 3, cloud_y - 5 + bob, cloud_h // 2 + 3),
                (cloud_x + cloud_w * 2 // 3, cloud_y + bob, cloud_h // 2),
            ]:
                self.draw.ellipse(
                    [cx - cr, cy - cr, cx + cr, cy + cr],
                    fill=(255, 255, 255), outline=(200, 200, 200)
                )

            # Ellipsis dots in cloud
            for i in range(3):
                dot_x = cloud_x + int((i - 1) * 10 * scale)
                dot_y = cloud_y + bob
                dot_r = int(3 * scale)
                self.draw.ellipse(
                    [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
                    fill=(100, 100, 100)
                )

        elif activity == "exploring":
            # Binoculars/telescope icon
            scope_x = x + int(45 * scale)
            scope_y = head_y - int(5 * scale)
            scope_r = int(10 * scale)
            scope_gap = int(8 * scale)

            # Scanning animation
            scan_angle = math.sin(frame * 0.04) * 0.3

            # Left lens
            left_x = scope_x - scope_gap
            self.draw.ellipse(
                [left_x - scope_r, scope_y - scope_r, left_x + scope_r, scope_y + scope_r],
                fill=(60, 60, 80), outline=(40, 40, 50), width=2
            )
            # Lens glint
            glint_offset = int(math.sin(frame * 0.1) * 3)
            self.draw.ellipse(
                [left_x - 3 + glint_offset, scope_y - 5, left_x + 1 + glint_offset, scope_y - 1],
                fill=(150, 180, 255)
            )

            # Right lens
            right_x = scope_x + scope_gap
            self.draw.ellipse(
                [right_x - scope_r, scope_y - scope_r, right_x + scope_r, scope_y + scope_r],
                fill=(60, 60, 80), outline=(40, 40, 50), width=2
            )
            # Lens glint
            self.draw.ellipse(
                [right_x - 3 + glint_offset, scope_y - 5, right_x + 1 + glint_offset, scope_y - 1],
                fill=(150, 180, 255)
            )

            # Bridge between lenses
            self.draw.rectangle(
                [left_x + scope_r - 2, scope_y - 3, right_x - scope_r + 2, scope_y + 3],
                fill=(50, 50, 60)
            )

            # Scanning lines emanating outward
            for i in range(3):
                angle = scan_angle + (i - 1) * 0.2
                line_len = int(25 * scale) + i * 5
                end_x = scope_x + int(math.cos(angle) * line_len)
                end_y = scope_y + int(math.sin(angle) * line_len * 0.3)
                alpha = 150 - i * 40
                self.draw.line(
                    [(scope_x + scope_gap + scope_r, scope_y), (end_x, end_y)],
                    fill=(alpha, alpha + 50, 255), width=1
                )

        elif activity == "communicating":
            # Speech/radio waves emanating
            wave_x = x + int(50 * scale)
            wave_y = head_y

            # Animated wave arcs
            for i in range(3):
                wave_phase = (frame * 0.1 + i * 0.5) % 2
                if wave_phase < 1.5:  # Only show during part of animation
                    arc_r = int((15 + i * 12) * scale * wave_phase)
                    arc_alpha = int(255 * (1 - wave_phase / 1.5))

                    # Draw arc segments
                    for angle in range(-30, 31, 10):
                        rad = math.radians(angle)
                        ax = wave_x + int(math.cos(rad) * arc_r)
                        ay = wave_y + int(math.sin(rad) * arc_r * 0.5)
                        self.draw.ellipse(
                            [ax - 2, ay - 2, ax + 2, ay + 2],
                            fill=(arc_alpha, arc_alpha, 255)
                        )

            # Central speaker/antenna icon
            self.draw.polygon(
                [(wave_x - 5, wave_y - 8), (wave_x + 5, wave_y - 3),
                 (wave_x + 5, wave_y + 3), (wave_x - 5, wave_y + 8)],
                fill=(200, 180, 100), outline=(150, 130, 70)
            )

        elif activity == "idle":
            # Subtle floating sparkles/dust motes when idle
            for i in range(4):
                sparkle_phase = (frame * 0.03 + i * 1.5) % (2 * math.pi)
                sparkle_x = x + int(math.cos(sparkle_phase + i) * 40 * scale)
                sparkle_y = body_y - int(20 * scale) + int(math.sin(sparkle_phase * 2) * 30)
                sparkle_alpha = int(100 + 100 * math.sin(sparkle_phase))

                if sparkle_alpha > 50:
                    size = int(2 * scale * (0.5 + 0.5 * math.sin(sparkle_phase)))
                    self.draw.ellipse(
                        [sparkle_x - size, sparkle_y - size, sparkle_x + size, sparkle_y + size],
                        fill=(255, 255, 200, sparkle_alpha)
                    )

    def _render_tool_spinner(self, state: GameState) -> None:
        """Render tool-specific spinner/indicator near Claude."""
        tool = state.main_agent.current_tool or state.main_agent.last_tool
        if not tool or state.main_agent.activity.value == "idle":
            return

        scale = min(self.width / 800, self.height / 400)
        scale = max(0.5, min(scale, 2.0))
        px = max(2, self.height // 120)

        # Position spinner to the right of Claude
        center_x = self.width // 2
        center_y = int(self.height * 0.55)
        spinner_x = center_x + int(60 * scale)
        spinner_y = center_y - int(40 * scale)

        frame = self._frame_count

        # Tool-specific spinner animations
        if tool in ["Read"]:
            # Page flip animation - book pages
            page_offset = int((frame % 30) / 10)
            book_colors = [(200, 180, 150), (220, 200, 170), (240, 220, 190)]
            book_w = int(20 * scale)
            book_h = int(16 * scale)
            # Book base
            self.draw.rectangle(
                [spinner_x, spinner_y, spinner_x + book_w, spinner_y + book_h],
                fill=book_colors[page_offset % 3],
                outline=(100, 80, 60)
            )
            # Page lines
            for i in range(3):
                line_y = spinner_y + int(4 * scale) + i * int(3 * scale)
                self.draw.line(
                    [(spinner_x + 3, line_y), (spinner_x + book_w - 3, line_y)],
                    fill=(80, 60, 40),
                    width=1
                )

        elif tool in ["Write", "Edit"]:
            # Pencil wiggle with writing particles
            wiggle = int(3 * math.sin(frame * 0.4))
            pencil_len = int(20 * scale)
            # Pencil body (yellow)
            self.draw.rectangle(
                [spinner_x + wiggle, spinner_y, spinner_x + pencil_len + wiggle, spinner_y + int(6 * scale)],
                fill=(255, 220, 100),
                outline=(200, 170, 50)
            )
            # Pencil tip
            self.draw.polygon(
                [(spinner_x + pencil_len + wiggle, spinner_y),
                 (spinner_x + pencil_len + int(6 * scale) + wiggle, spinner_y + int(3 * scale)),
                 (spinner_x + pencil_len + wiggle, spinner_y + int(6 * scale))],
                fill=(100, 80, 60)
            )
            # Writing sparkles
            for i in range(3):
                spark_x = spinner_x + pencil_len + int(10 * scale) + int(math.cos(frame * 0.3 + i) * 8)
                spark_y = spinner_y + int(3 * scale) + int(math.sin(frame * 0.3 + i) * 8)
                spark_size = int(2 * scale * (0.5 + 0.5 * math.sin(frame * 0.2 + i)))
                self.draw.ellipse(
                    [spark_x - spark_size, spark_y - spark_size, spark_x + spark_size, spark_y + spark_size],
                    fill=(100, 200, 255)
                )

        elif tool in ["Bash"]:
            # Terminal cursor blink
            cursor_visible = (frame % 30) < 20
            term_w = int(24 * scale)
            term_h = int(16 * scale)
            # Terminal background
            self.draw.rectangle(
                [spinner_x, spinner_y, spinner_x + term_w, spinner_y + term_h],
                fill=(30, 30, 40),
                outline=(60, 60, 80)
            )
            # Prompt
            self.draw.text((spinner_x + 2, spinner_y + 2), ">", fill=(100, 255, 100))
            # Cursor
            if cursor_visible:
                cursor_x = spinner_x + int(10 * scale)
                self.draw.rectangle(
                    [cursor_x, spinner_y + 3, cursor_x + int(6 * scale), spinner_y + term_h - 3],
                    fill=(200, 200, 200)
                )

        elif tool in ["Grep", "Glob"]:
            # Magnifying glass sweep
            sweep_angle = (frame % 60) * 6  # 0-360 over 60 frames
            glass_x = spinner_x + int(10 * scale) + int(8 * math.cos(math.radians(sweep_angle)))
            glass_y = spinner_y + int(8 * scale) + int(4 * math.sin(math.radians(sweep_angle)))
            glass_r = int(8 * scale)
            # Glass circle
            self.draw.ellipse(
                [glass_x - glass_r, glass_y - glass_r, glass_x + glass_r, glass_y + glass_r],
                fill=None,
                outline=(200, 200, 255),
                width=2
            )
            # Handle
            handle_x = glass_x + int(glass_r * 0.7)
            handle_y = glass_y + int(glass_r * 0.7)
            self.draw.line(
                [(handle_x, handle_y), (handle_x + int(6 * scale), handle_y + int(6 * scale))],
                fill=(150, 130, 100),
                width=3
            )
            # Shine
            self.draw.arc(
                [glass_x - glass_r + 2, glass_y - glass_r + 2, glass_x, glass_y],
                start=200, end=280,
                fill=(255, 255, 255),
                width=1
            )

        elif tool in ["WebFetch", "WebSearch"]:
            # Loading dots (Braille-style animation)
            dots = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            dot_idx = (frame // 3) % len(dots)
            # Draw dots as circles instead (more visible)
            dot_positions = [
                (0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)
            ]
            pattern = [
                [1, 0, 1, 0, 1, 0],  # ⠋
                [1, 1, 0, 0, 1, 0],  # ⠙
                [1, 1, 0, 1, 0, 0],  # ⠹
                [0, 1, 0, 1, 0, 1],  # ⠸
                [0, 0, 1, 1, 0, 1],  # ⠼
                [0, 0, 0, 1, 1, 1],  # ⠴
                [0, 0, 1, 0, 1, 1],  # ⠦
                [1, 0, 1, 0, 0, 1],  # ⠧
                [1, 0, 1, 0, 1, 0],  # ⠇
                [1, 0, 0, 0, 1, 1],  # ⠏
            ]
            dot_size = int(3 * scale)
            for i, (dx, dy) in enumerate(dot_positions):
                if pattern[dot_idx][i]:
                    dx_px = spinner_x + dx * int(8 * scale)
                    dy_px = spinner_y + dy * int(6 * scale)
                    self.draw.ellipse(
                        [dx_px, dy_px, dx_px + dot_size, dy_px + dot_size],
                        fill=(100, 200, 255)
                    )
            # Globe icon
            globe_x = spinner_x + int(20 * scale)
            globe_r = int(8 * scale)
            self.draw.ellipse(
                [globe_x - globe_r, spinner_y, globe_x + globe_r, spinner_y + globe_r * 2],
                fill=None,
                outline=(100, 150, 200),
                width=1
            )
            # Latitude lines
            self.draw.line(
                [(globe_x - globe_r, spinner_y + globe_r), (globe_x + globe_r, spinner_y + globe_r)],
                fill=(100, 150, 200)
            )

        elif tool in ["Task"]:
            # Branching/spawning animation
            branch_phase = (frame % 40) / 40.0
            # Central node
            node_r = int(5 * scale)
            self.draw.ellipse(
                [spinner_x - node_r, spinner_y - node_r, spinner_x + node_r, spinner_y + node_r],
                fill=(100, 180, 180),
                outline=(70, 140, 140)
            )
            # Branching lines
            for i in range(3):
                angle = math.radians(i * 120 - 90 + frame * 2)
                length = int(15 * scale * branch_phase)
                end_x = spinner_x + int(length * math.cos(angle))
                end_y = spinner_y + int(length * math.sin(angle))
                # Line
                self.draw.line(
                    [(spinner_x, spinner_y), (end_x, end_y)],
                    fill=(100, 200, 180),
                    width=2
                )
                # End node
                if branch_phase > 0.5:
                    small_r = int(3 * scale * (branch_phase - 0.5) * 2)
                    self.draw.ellipse(
                        [end_x - small_r, end_y - small_r, end_x + small_r, end_y + small_r],
                        fill=(150, 210, 200)
                    )

        else:
            # Default: simple spinning indicator
            spin_angle = frame * 10
            for i in range(8):
                angle = math.radians(spin_angle + i * 45)
                dist = int(8 * scale)
                dot_x = spinner_x + int(dist * math.cos(angle))
                dot_y = spinner_y + int(dist * math.sin(angle))
                alpha = 1.0 - (i / 8.0)
                dot_r = int(2 * scale)
                color = (int(150 * alpha), int(150 * alpha), int(200 * alpha))
                self.draw.ellipse(
                    [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
                    fill=color
                )

    def _render_particles(self, state: GameState) -> None:
        """Render particle effects."""
        self.particle_count = len(state.particles)

        for particle in state.particles:
            # Skip dead particles
            if particle.lifetime <= 0 or particle.max_lifetime <= 0:
                continue

            # Simple screen-space particles (no camera transform for idle game style)
            # Center the particle system around Claude
            center_x = self.width // 2
            center_y = int(self.height * 0.55)

            screen_x = center_x + int(particle.position.x - state.main_agent.position.x)
            screen_y = center_y + int(particle.position.y - state.main_agent.position.y)

            # Clamp alpha to valid range
            alpha = max(0.0, min(1.0, particle.lifetime / particle.max_lifetime))
            color = tuple(max(0, min(255, int(c * alpha))) for c in particle.color)
            size = max(1, int(4 * particle.scale * alpha))

            # Validate ellipse coordinates before drawing
            x1, y1 = screen_x - size, screen_y - size
            x2, y2 = screen_x + size, screen_y + size
            if x2 > x1 and y2 > y1:
                self.draw.ellipse([x1, y1, x2, y2], fill=color)

    def _render_floating_texts(self, state: GameState) -> None:
        """Render floating text popups (e.g., +5 XP)."""
        if not hasattr(state, 'floating_texts'):
            return

        center_x = self.width // 2
        center_y = int(self.height * 0.55)

        for ft in state.floating_texts:
            # Position relative to Claude
            screen_x = center_x + int(ft.position.x - state.main_agent.position.x)
            screen_y = center_y + int(ft.position.y - state.main_agent.position.y)

            # Calculate alpha (fade out)
            alpha = ft.alpha

            # Scale text size based on screen
            scale = min(self.width / 800, self.height / 400)
            scale = max(0.5, min(scale, 2.0))

            # Color with alpha
            color = tuple(int(c * alpha) for c in ft.color)

            # Draw text with outline for readability
            outline_color = tuple(int(20 * alpha) for _ in range(3))

            # Draw outline (4 directions)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.draw.text(
                    (screen_x + dx, screen_y + dy),
                    ft.text,
                    fill=outline_color
                )

            # Draw main text
            self.draw.text(
                (screen_x, screen_y),
                ft.text,
                fill=color
            )

    def _render_level_up_overlay(self, state: GameState) -> None:
        """Render level-up celebration overlay."""
        if state.progression.level_up_timer <= 0:
            return

        # Calculate animation progress (0 to 1, where 1 is start of animation)
        progress = state.progression.level_up_timer / 3.0  # 3 second duration

        scale = min(self.width / 800, self.height / 400)
        scale = max(0.5, min(scale, 2.0))

        # Flash effect at the start
        if progress > 0.9:
            flash_alpha = int((progress - 0.9) * 10 * 100)
            overlay = Image.new("RGBA", (self.width, self.height), (255, 255, 255, flash_alpha))
            self.frame = Image.alpha_composite(self.frame, overlay)
            self.draw = ImageDraw.Draw(self.frame)

        # "LEVEL UP!" banner
        if progress > 0.3:
            banner_alpha = min(1.0, (progress - 0.3) / 0.2)

            # Banner position - centered, above Claude
            banner_y = int(self.height * 0.25)
            banner_text = f"LEVEL UP!"

            # Pulsing scale effect
            pulse = 1.0 + 0.1 * math.sin(self._frame_count * 0.3)

            # Gold color with fade
            gold = (255, 215, 0)
            color = tuple(int(c * banner_alpha) for c in gold)
            outline_color = tuple(int(40 * banner_alpha) for _ in range(3))

            # Draw banner text centered
            text_x = self.width // 2 - len(banner_text) * 4
            text_y = banner_y

            # Draw outline
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)]:
                self.draw.text((text_x + dx, text_y + dy), banner_text, fill=outline_color)

            # Draw main text
            self.draw.text((text_x, text_y), banner_text, fill=color)

            # Level number below
            level_text = f"Level {state.progression.level}"
            level_x = self.width // 2 - len(level_text) * 3
            self.draw.text((level_x, text_y + 20), level_text, fill=color)

        # Confetti particles
        if progress > 0.5:
            import random
            random.seed(int(self._frame_count / 2))
            confetti_colors = [
                (255, 100, 100), (100, 255, 100), (100, 100, 255),
                (255, 255, 100), (255, 100, 255), (100, 255, 255),
            ]
            for i in range(20):
                x = random.randint(0, self.width)
                y = random.randint(0, self.height)
                # Fall down over time
                y = (y + int((1 - progress) * 200)) % self.height
                size = random.randint(2, 5)
                color = confetti_colors[i % len(confetti_colors)]
                alpha_color = tuple(int(c * progress) for c in color)
                self.draw.rectangle(
                    [x, y, x + size, y + size],
                    fill=alpha_color
                )

    def _render_stats_panel(self, state: GameState) -> None:
        """Render pixel art wood panel UI at the bottom like the reference."""
        px = max(2, self.height // 120)
        scale = min(self.width / 800, self.height / 400)
        scale = max(0.5, min(scale, 2.0))

        panel_h = int(55 * scale)
        panel_y = self.height - panel_h

        # Wood panel background with border
        border_size = px * 2

        # Dark border/outline
        self.draw.rectangle(
            [0, panel_y - border_size, self.width, self.height],
            fill=self.COLORS["ui_border"]
        )

        # Main wood panel
        self.draw.rectangle(
            [border_size, panel_y, self.width - border_size, self.height - border_size],
            fill=self.COLORS["ui_bg"]
        )

        # Wood grain lines (horizontal)
        for wy in range(panel_y + px * 3, self.height - border_size, px * 4):
            self.draw.rectangle(
                [border_size + px, wy, self.width - border_size - px, wy + px],
                fill=self.COLORS["ui_bg_dark"]
            )

        # === Left section: Level with gold coin icon ===
        margin = int(12 * scale)
        level_x = margin + border_size
        level_y = panel_y + int(10 * scale)

        # Gold coin icon
        coin_size = int(20 * scale)
        # Coin outline
        self.draw.ellipse(
            [level_x - px, level_y - px, level_x + coin_size + px, level_y + coin_size + px],
            fill=self.COLORS["outline"]
        )
        # Coin body
        self.draw.ellipse(
            [level_x, level_y, level_x + coin_size, level_y + coin_size],
            fill=self.COLORS["accent_primary"]
        )
        # Coin shine (validate coordinates to prevent crash)
        shine_x1, shine_y1 = level_x + px * 2, level_y + px * 2
        shine_x2, shine_y2 = level_x + coin_size // 2, level_y + coin_size // 2
        if shine_x2 > shine_x1 and shine_y2 > shine_y1:
            self.draw.ellipse([shine_x1, shine_y1, shine_x2, shine_y2], fill=(255, 230, 100))

        # Token count
        self.draw.text(
            (level_x + coin_size + px * 3, level_y + px),
            f"{state.resources.tokens}",
            fill=self.COLORS["ui_text"]
        )

        # === Center: Level bar ===
        bar_w = int(150 * scale)
        bar_h = int(16 * scale)
        bar_x = self.width // 2 - bar_w // 2
        bar_y = panel_y + int(12 * scale)

        # Level text above bar (with pulse on level-up)
        level_text = f"LEVEL {state.progression.level}"
        text_x = bar_x + bar_w // 2 - len(level_text) * 3
        level_color = self.COLORS["ui_text"]
        if state.progression.level_up_timer > 0:
            # Pulse gold during level-up celebration
            pulse = int(127 + 127 * math.sin(self._frame_count * 0.4))
            level_color = (255, 200 + pulse // 4, pulse // 2)
        self.draw.text((text_x, bar_y - int(2 * scale)), level_text, fill=level_color)

        # Use animated display_xp for smooth fill
        display_xp = state.progression.display_xp if hasattr(state.progression, 'display_xp') else state.progression.experience
        xp_pct = min(1.0, display_xp / max(1, state.progression.experience_to_next))

        # Glow effect when close to level-up (last 20%)
        bar_inner_y = bar_y + int(12 * scale)
        if xp_pct > 0.8:
            glow_intensity = (xp_pct - 0.8) / 0.2  # 0 to 1
            glow_pulse = 0.5 + 0.5 * math.sin(self._frame_count * 0.2)
            glow_alpha = int(glow_intensity * glow_pulse * 60)
            glow_color = (200, 100, 255, glow_alpha)
            # Draw glow around bar
            for glow_offset in range(1, 4):
                self.draw.rectangle(
                    [bar_x - glow_offset - px, bar_inner_y - glow_offset - px,
                     bar_x + bar_w + glow_offset + px, bar_inner_y + bar_h + glow_offset + px],
                    outline=(200, 100, 255)
                )

        # XP bar outline
        self.draw.rectangle(
            [bar_x - px, bar_inner_y - px, bar_x + bar_w + px, bar_inner_y + bar_h + px],
            fill=self.COLORS["outline"]
        )
        # Bar background
        self.draw.rectangle(
            [bar_x, bar_inner_y, bar_x + bar_w, bar_inner_y + bar_h],
            fill=(40, 30, 50)
        )

        # Milestone markers at 25%, 50%, 75%
        for milestone_pct in [0.25, 0.5, 0.75]:
            marker_x = bar_x + int(bar_w * milestone_pct)
            marker_color = (80, 60, 100) if xp_pct < milestone_pct else (150, 100, 200)
            self.draw.line(
                [(marker_x, bar_inner_y + 2), (marker_x, bar_inner_y + bar_h - 2)],
                fill=marker_color,
                width=1
            )

        # Bar fill with animated width
        if xp_pct > 0:
            fill_w = int(bar_w * xp_pct)
            # Only draw if rectangle has valid dimensions (x1 > x0)
            if fill_w > px * 2:
                # Determine fill color - pulse brighter on XP gain
                fill_color = self.COLORS["accent_xp"]
                if state.progression.xp_gain_flash > 0:
                    flash_intensity = state.progression.xp_gain_flash / 0.5
                    pulse_bright = int(flash_intensity * 50)
                    fill_color = (
                        min(255, fill_color[0] + pulse_bright),
                        min(255, fill_color[1] + pulse_bright),
                        min(255, fill_color[2] + pulse_bright),
                    )
                self.draw.rectangle(
                    [bar_x + px, bar_inner_y + px, bar_x + fill_w - px, bar_inner_y + bar_h - px],
                    fill=fill_color
                )

                # Shine effect on the bar fill
                shine_x = bar_x + px + int((fill_w - px * 2) * 0.3)
                self.draw.rectangle(
                    [shine_x, bar_inner_y + px, shine_x + px * 2, bar_inner_y + bar_h // 3],
                    fill=(255, 200, 255)
                )

        # XP text
        xp_text = f"{state.progression.experience}/{state.progression.experience_to_next}"
        self.draw.text(
            (bar_x + bar_w + px * 4, bar_y + int(14 * scale)),
            xp_text,
            fill=self.COLORS["ui_text"]
        )

        # === Right section: Tools and agents counts ===
        right_x = self.width - int(120 * scale)
        icon_y = panel_y + int(12 * scale)
        icon_size = int(16 * scale)

        # Tools icon (hammer/wrench shape)
        self.draw.rectangle(
            [right_x, icon_y, right_x + icon_size, icon_y + icon_size],
            fill=self.COLORS["accent_secondary"]
        )
        self.draw.rectangle(
            [right_x - px, icon_y - px, right_x + icon_size + px, icon_y + icon_size + px],
            outline=self.COLORS["outline"]
        )
        self.draw.text(
            (right_x + icon_size + px * 3, icon_y),
            f"{state.progression.total_tools_used}",
            fill=self.COLORS["ui_text"]
        )

        # Agents icon (person shape)
        agent_x = right_x + int(50 * scale)
        self.draw.ellipse(
            [agent_x, icon_y, agent_x + icon_size, icon_y + icon_size],
            fill=self.COLORS["accent_success"]
        )
        self.draw.rectangle(
            [agent_x - px, icon_y - px, agent_x + icon_size + px, icon_y + icon_size + px],
            outline=self.COLORS["outline"]
        )
        self.draw.text(
            (agent_x + icon_size + px * 3, icon_y),
            f"{state.progression.total_subagents_spawned}",
            fill=self.COLORS["ui_text"]
        )

        # === API Cost Tracker (top right corner) ===
        self._render_api_cost_tracker(state, px, scale)

    def _render_api_cost_tracker(self, state: GameState, px: int, scale: float) -> None:
        """Render API cost tracking display in top-right corner."""
        api_costs = state.resources.api_costs

        # Only show if we have any usage
        if api_costs.total_tokens == 0:
            return

        # Position in top-right corner
        margin = int(8 * scale)
        panel_w = int(100 * scale)
        panel_h = int(50 * scale)
        panel_x = self.width - panel_w - margin
        panel_y = margin

        # Semi-transparent dark background
        self.draw.rectangle(
            [panel_x - px, panel_y - px, panel_x + panel_w + px, panel_y + panel_h + px],
            fill=self.COLORS["outline"]
        )
        self.draw.rectangle(
            [panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
            fill=(40, 35, 50)
        )

        # Cost header
        cost_text = f"${api_costs.total_cost_usd:.4f}"
        self.draw.text(
            (panel_x + px * 2, panel_y + px * 2),
            cost_text,
            fill=self.COLORS["accent_primary"]
        )

        # Token breakdown (compact)
        tokens_k = api_costs.total_tokens / 1000
        if tokens_k >= 1000:
            token_text = f"{tokens_k/1000:.1f}M tok"
        elif tokens_k >= 1:
            token_text = f"{tokens_k:.1f}k tok"
        else:
            token_text = f"{api_costs.total_tokens} tok"

        self.draw.text(
            (panel_x + px * 2, panel_y + px * 2 + int(14 * scale)),
            token_text,
            fill=(180, 180, 200)
        )

        # Input/Output split
        in_k = api_costs.input_tokens / 1000
        out_k = api_costs.output_tokens / 1000
        split_text = f"in:{in_k:.0f}k out:{out_k:.0f}k"
        self.draw.text(
            (panel_x + px * 2, panel_y + px * 2 + int(26 * scale)),
            split_text,
            fill=(140, 140, 160)
        )

    def _render_activity_indicator(self, state: GameState) -> None:
        """Render activity indicator as pixel art banner at top of screen."""
        import time

        activity = state.main_agent.activity.value

        # Get the display text - use current tool, or recent last_tool if within display window
        current_tool = state.main_agent.current_tool
        display_tool = current_tool

        # If no current tool, check if we should show the last tool (minimum display time)
        min_display_time = 1.0  # Show tool verb for at least 1 second
        if not display_tool and hasattr(state.main_agent, 'last_tool'):
            elapsed = time.time() - state.main_agent.last_tool_time
            if elapsed < min_display_time and state.main_agent.last_tool:
                display_tool = state.main_agent.last_tool

        # Skip if idle AND no recent tool to display
        if activity == "idle" and not display_tool:
            return

        if display_tool and display_tool in self.TOOL_VERBS:
            display_text = self.TOOL_VERBS[display_tool]
        else:
            # For thinking, try to read the actual verb from Claude Code's terminal
            if activity == "thinking":
                # Only refresh verb cache every 10 frames (~0.3s at 30fps)
                if self._frame_count - self._verb_cache_frame >= 10:
                    self._cached_verb = self._get_claude_code_verb()
                    self._verb_cache_frame = self._frame_count

                if self._cached_verb:
                    display_text = f"{self._cached_verb}..."
                else:
                    # Fallback to rotating verbs if can't read from terminal
                    verb_index = (self._frame_count // 60) % len(self.THINKING_VERBS)
                    display_text = self.THINKING_VERBS[verb_index]
            else:
                activity_verbs = {
                    "reading": "Reading...",
                    "writing": "Writing...",
                    "searching": "Searching...",
                    "building": "Building...",
                    "exploring": "Exploring...",
                    "communicating": "Connecting...",
                    "resting": "Resting...",
                    "celebrating": "Celebrating!",
                }
                display_text = activity_verbs.get(activity, activity.title() + "...")

        px = max(2, self.height // 120)
        scale = min(self.width / 800, self.height / 400)
        scale = max(0.5, min(scale, 2.0))

        # Get agent's actual screen position
        # Agent position is relative offset from center, so convert to screen coords
        screen_center_x = self.width // 2
        screen_center_y = int(self.height * 0.58)

        agent_pos = state.main_agent.position
        agent_screen_x = screen_center_x + int(agent_pos.x)
        agent_screen_y = screen_center_y + int(agent_pos.y)

        # Claude's head is above the ground position
        head_y = agent_screen_y - int(px * 16)

        # Banner dimensions
        banner_h = int(px * 6)
        banner_w = int((len(display_text) * 7 + 16) * scale)
        banner_x = agent_screen_x - banner_w // 2
        banner_y = head_y - int(px * 12)  # Above Claude's head

        # Clamp banner to screen bounds
        banner_x = max(px * 2, min(banner_x, self.width - banner_w - px * 2))
        banner_y = max(px * 2, banner_y)

        # Pulsing animation
        pulse = (self._frame_count % 30) < 15

        # Banner outline (black border)
        self.draw.rectangle(
            [banner_x - px * 2, banner_y - px * 2,
             banner_x + banner_w + px * 2, banner_y + banner_h + px * 2],
            fill=self.COLORS["outline"]
        )

        # Banner background (gold/yellow, slightly different on pulse)
        banner_color = (255, 255, 255) if pulse else (245, 245, 245)
        self.draw.rectangle(
            [banner_x, banner_y, banner_x + banner_w, banner_y + banner_h],
            fill=banner_color
        )

        # Small pointer/tail pointing down toward Claude
        # Pointer points to actual agent position, but stays within banner bounds
        pointer_x = max(banner_x + px * 3, min(agent_screen_x, banner_x + banner_w - px * 3))
        pointer_top = banner_y + banner_h
        pointer_bottom = pointer_top + px * 3
        self.draw.polygon(
            [(pointer_x - px * 2, pointer_top),
             (pointer_x + px * 2, pointer_top),
             (pointer_x, pointer_bottom)],
            fill=self.COLORS["outline"]
        )
        self.draw.polygon(
            [(pointer_x - px, pointer_top),
             (pointer_x + px, pointer_top),
             (pointer_x, pointer_bottom - px)],
            fill=(245, 245, 245)
        )

        # Activity text (dark text on light background)
        text_x = banner_x + int(8 * scale)
        text_y = banner_y + px
        self.draw.text((text_x, text_y), display_text, fill=self.COLORS["ui_text_dark"])

    def _render_achievement_popups(self, state: GameState) -> None:
        """Render achievement unlock popups sliding in from the right."""
        if not hasattr(state, 'achievement_popups') or not state.achievement_popups:
            return

        scale = min(self.width / 800, self.height / 400)
        scale = max(0.5, min(scale, 2.0))
        px = max(2, self.height // 120)

        # Stack popups from bottom-right
        popup_h = int(50 * scale)
        popup_w = int(180 * scale)
        margin = int(10 * scale)
        start_y = int(self.height * 0.3)

        for i, popup in enumerate(state.achievement_popups[:3]):  # Max 3 visible
            achievement = popup.achievement
            progress = popup.progress

            # Slide-in animation (first 0.2 of lifetime)
            if progress < 0.1:
                slide_progress = progress / 0.1
                offset_x = int((1 - slide_progress) * (popup_w + margin))
            # Slide-out animation (last 0.2 of lifetime)
            elif progress > 0.8:
                slide_progress = (progress - 0.8) / 0.2
                offset_x = int(slide_progress * (popup_w + margin))
            else:
                offset_x = 0

            popup_x = self.width - popup_w - margin + offset_x
            popup_y = start_y + i * (popup_h + margin)

            # Popup background with border
            self.draw.rectangle(
                [popup_x - px, popup_y - px, popup_x + popup_w + px, popup_y + popup_h + px],
                fill=self.COLORS["outline"]
            )
            self.draw.rectangle(
                [popup_x, popup_y, popup_x + popup_w, popup_y + popup_h],
                fill=(50, 45, 60)
            )

            # Gold accent bar on left
            accent_w = int(4 * scale)
            self.draw.rectangle(
                [popup_x, popup_y, popup_x + accent_w, popup_y + popup_h],
                fill=self.COLORS["accent_primary"]
            )

            # Icon
            icon_size = int(30 * scale)
            icon_x = popup_x + accent_w + int(8 * scale)
            icon_y = popup_y + (popup_h - icon_size) // 2
            # Draw icon background circle
            self.draw.ellipse(
                [icon_x, icon_y, icon_x + icon_size, icon_y + icon_size],
                fill=(80, 70, 100)
            )
            # Draw icon text (emoji)
            icon_text_x = icon_x + icon_size // 2 - 4
            icon_text_y = icon_y + icon_size // 2 - 6
            self.draw.text((icon_text_x, icon_text_y), achievement.icon, fill=(255, 255, 255))

            # Achievement text
            text_x = icon_x + icon_size + int(8 * scale)

            # "ACHIEVEMENT" header
            header_y = popup_y + int(6 * scale)
            self.draw.text(
                (text_x, header_y),
                "ACHIEVEMENT",
                fill=(150, 140, 160)
            )

            # Achievement name
            name_y = header_y + int(12 * scale)
            name_color = self.COLORS["accent_primary"]
            self.draw.text(
                (text_x, name_y),
                achievement.name,
                fill=name_color
            )

            # Description (if space)
            if popup_h > int(45 * scale):
                desc_y = name_y + int(12 * scale)
                # Truncate description if too long
                desc_text = achievement.description
                max_chars = int((popup_w - icon_size - 30) / 5)
                if len(desc_text) > max_chars:
                    desc_text = desc_text[:max_chars - 3] + "..."
                self.draw.text(
                    (text_x, desc_y),
                    desc_text,
                    fill=(120, 110, 130)
                )

            # Sparkle effect
            if progress < 0.5:
                sparkle_phase = progress * 10
                for j in range(4):
                    angle = sparkle_phase + j * math.pi / 2
                    sparkle_x = popup_x + popup_w // 2 + int(math.cos(angle) * 30)
                    sparkle_y = popup_y + popup_h // 2 + int(math.sin(angle) * 20)
                    sparkle_size = int(3 * scale * (0.5 - progress))
                    if sparkle_size > 0:
                        self.draw.ellipse(
                            [sparkle_x - sparkle_size, sparkle_y - sparkle_size,
                             sparkle_x + sparkle_size, sparkle_y + sparkle_size],
                            fill=self.COLORS["accent_primary"]
                        )

    def _draw_rounded_rect(self, x1: int, y1: int, x2: int, y2: int,
                           radius: int, fill=None, outline=None) -> None:
        """Draw a rounded rectangle."""
        # Clamp radius
        radius = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)

        if fill:
            # Main rectangle
            self.draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
            self.draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
            # Corners
            self.draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
            self.draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
            self.draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
            self.draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)

        if outline:
            # Draw outline arcs and lines
            self.draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=outline)
            self.draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=outline)
            self.draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=outline)
            self.draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=outline)
            self.draw.line([(x1 + radius, y1), (x2 - radius, y1)], fill=outline)
            self.draw.line([(x1 + radius, y2), (x2 - radius, y2)], fill=outline)
            self.draw.line([(x1, y1 + radius), (x1, y2 - radius)], fill=outline)
            self.draw.line([(x2, y1 + radius), (x2, y2 - radius)], fill=outline)

    def _display_frame(self) -> None:
        """Display the frame using the appropriate terminal protocol."""
        if self.protocol == "kitty":
            self._display_kitty()
        elif self.protocol == "iterm2":
            self._display_iterm2()
        elif self.protocol == "sixel":
            self._display_sixel()
        else:
            self.frame.save("/tmp/claude_world_frame.png")
            if self._first_frame:
                print("\033[2J\033[H[Frame saved to /tmp/claude_world_frame.png]")

    def _display_kitty(self) -> None:
        """Display using Kitty graphics protocol."""
        # Clear tmux scrollback every 100 frames to prevent memory leak
        if is_inside_tmux() and (self._frame_count - self._last_scrollback_clear) >= 100:
            self._clear_tmux_scrollback()
            self._last_scrollback_clear = self._frame_count

        if self._first_frame:
            sys.stdout.write("\033[2J\033[H\033[?25l")
            self._first_frame = False
        else:
            sys.stdout.write("\033[H")

        buf = io.BytesIO()
        try:
            self.frame.save(buf, format="PNG")
            raw_data = buf.getvalue()
        finally:
            buf.close()
            del buf

        data = base64.b64encode(raw_data).decode("ascii")
        del raw_data  # Free raw bytes

        chunk_size = 4096
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            m = 1 if i + chunk_size < len(data) else 0
            if i == 0:
                sys.stdout.write(f"\033_Ga=T,f=100,m={m};{chunk}\033\\")
            else:
                sys.stdout.write(f"\033_Gm={m};{chunk}\033\\")

        del data  # Free base64 string
        sys.stdout.flush()

    def _display_iterm2(self) -> None:
        """Display using iTerm2 inline images."""
        # Clear tmux scrollback every 100 frames to prevent memory leak
        if is_inside_tmux() and (self._frame_count - self._last_scrollback_clear) >= 100:
            self._clear_tmux_scrollback()
            self._last_scrollback_clear = self._frame_count

        if self._first_frame:
            sys.stdout.write("\033[2J\033[H\033[?25l")
            self._first_frame = False
        else:
            sys.stdout.write("\033[H")

        buf = io.BytesIO()
        try:
            self.frame.save(buf, format="PNG")
            raw_data = buf.getvalue()
        finally:
            buf.close()
            del buf

        data = base64.b64encode(raw_data).decode("ascii")
        del raw_data  # Free raw bytes

        if is_inside_tmux():
            self._display_iterm2_multipart(data)
        else:
            img_seq = f"\033]1337;File=inline=1;width={self.width}px;height={self.height}px;preserveAspectRatio=0:{data}\007"
            sys.stdout.write(img_seq)
            del img_seq

        del data  # Free base64 string
        sys.stdout.flush()

    def _display_iterm2_multipart(self, data: str) -> None:
        """Display image using iTerm2 multipart protocol for tmux."""
        chunk_size = 65536
        start_seq = f"\033]1337;MultipartFile=inline=1;width={self.width}px;height={self.height}px;preserveAspectRatio=0\007"
        sys.stdout.write(tmux_wrap(start_seq))

        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            part_seq = f"\033]1337;FilePart={chunk}\007"
            sys.stdout.write(tmux_wrap(part_seq))

        end_seq = "\033]1337;FileEnd\007"
        sys.stdout.write(tmux_wrap(end_seq))

    def _get_tmux_pane_size(self) -> tuple[int, int]:
        """Get the tmux pane size in characters."""
        return self._get_pane_size_static()

    def _display_sixel(self) -> None:
        """Display using Sixel graphics - scales to fill terminal pane."""
        if not shutil.which("img2sixel"):
            self.frame.save("/tmp/claude_world_frame.png")
            if self._first_frame:
                print("[img2sixel not found]")
                self._first_frame = False
            return

        # Clear tmux scrollback every 300 frames to prevent memory leak
        # Do NOT set _first_frame = True - that causes visible flicker
        if is_inside_tmux() and (self._frame_count - self._last_scrollback_clear) >= 300:
            self._clear_tmux_scrollback()
            self._last_scrollback_clear = self._frame_count

        if self._first_frame:
            sys.stdout.write("\033[2J\033[H\033[?25l")
            self._first_frame = False
        else:
            sys.stdout.write("\033[H")
        sys.stdout.flush()

        tmp_path = "/tmp/claude_world_frame.png"
        self.frame.save(tmp_path, format="PNG")

        try:
            import subprocess
            # Use fixed frame size for consistent output - no dynamic scaling
            result = subprocess.run(
                ["img2sixel", "-w", str(self.width), "-h", str(self.height), tmp_path],
                capture_output=True,
            )
            if result.returncode == 0:
                sys.stdout.buffer.write(result.stdout)
                sys.stdout.flush()
            # Explicitly delete result to free subprocess buffers
            del result
        except Exception:
            pass

    def _clear_tmux_scrollback(self) -> None:
        """Clear tmux pane scrollback buffer to free terminal memory."""
        clear_tmux_scrollback()

    def force_clear(self) -> None:
        """Force a full screen clear on next frame."""
        self._first_frame = True

    def enable_focus_reporting(self) -> None:
        """Enable terminal focus reporting."""
        sys.stdout.write("\033[?1004h")
        sys.stdout.flush()
        self._focus_reporting_enabled = True

    def disable_focus_reporting(self) -> None:
        """Disable terminal focus reporting."""
        sys.stdout.write("\033[?1004l")
        sys.stdout.flush()
        self._focus_reporting_enabled = False

    def cleanup(self) -> None:
        """Restore terminal state."""
        if self._focus_reporting_enabled:
            sys.stdout.write("\033[?1004l")
        sys.stdout.write("\033[2J\033[H\033[?25h")
        sys.stdout.flush()

    def _lerp_color(self, c1: Tuple[int, int, int], c2: Tuple[int, int, int],
                    t: float) -> Tuple[int, int, int]:
        """Linear interpolate between two colors."""
        return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

    def get_screen_string(self) -> str:
        """Get a text representation (for compatibility)."""
        return f"[Graphics frame {self.width}x{self.height}]"
