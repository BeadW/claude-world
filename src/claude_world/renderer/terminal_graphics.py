"""Terminal graphics renderer using Kitty/iTerm2/Sixel protocols."""

from __future__ import annotations

import base64
import io
import math
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

if TYPE_CHECKING:
    from claude_world.types import GameState


def detect_graphics_protocol() -> str:
    """Detect which graphics protocol the terminal supports."""
    term = os.environ.get("TERM", "")
    term_program = os.environ.get("TERM_PROGRAM", "")

    # When inside tmux, prefer sixel because tmux handles it natively
    if is_inside_tmux():
        return "sixel"

    if "kitty" in term.lower():
        return "kitty"
    elif term_program == "iTerm.app":
        return "iterm2"
    elif "xterm" in term.lower() or "mlterm" in term.lower():
        return "sixel"
    else:
        return "none"


def is_inside_tmux() -> bool:
    """Check if we're running inside tmux."""
    return "TMUX" in os.environ


def tmux_wrap(sequence: str) -> str:
    """Wrap an escape sequence for tmux passthrough."""
    if not is_inside_tmux():
        return sequence
    escaped = sequence.replace("\033", "\033\033")
    return f"\033Ptmux;{escaped}\033\\"


class TerminalGraphicsRenderer:
    """Renders game state as idle game graphics in the terminal.

    Design: Centered Claude character with clean stats display.
    Inspired by popular idle games with focus on character and progression.
    """

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
                return None

            current_pane = subprocess.run(
                ["tmux", "display-message", "-p", "#{pane_id}"],
                capture_output=True,
                text=True,
            ).stdout.strip()

            pane_ids = result.stdout.strip().split("\n")

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
                    continue

                content = capture.stdout

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
        import subprocess
        if is_inside_tmux():
            try:
                result = subprocess.run(
                    ["tmux", "display-message", "-p", "#{pane_width} #{pane_height}"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    parts = result.stdout.strip().split()
                    if len(parts) == 2:
                        return int(parts[0]), int(parts[1])
            except Exception:
                pass
        return shutil.get_terminal_size()

    @staticmethod
    def _get_terminal_pixel_size() -> tuple[int, int]:
        """Get terminal/pane size in pixels."""
        import fcntl
        import struct
        import termios
        import subprocess

        xpixel, ypixel = 0, 0

        # Try ioctl first - this gets the actual pane pixel size in tmux
        try:
            # TIOCGWINSZ returns (rows, cols, xpixel, ypixel)
            result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ,
                                b'\x00' * 8)
            rows, cols, xpixel, ypixel = struct.unpack('HHHH', result)
        except Exception:
            pass

        # If ioctl gave us pixel size, use it
        if xpixel > 0 and ypixel > 0:
            return xpixel, ypixel

        # Otherwise, get character dimensions and estimate
        if is_inside_tmux():
            try:
                result = subprocess.run(
                    ["tmux", "display-message", "-p", "#{pane_width} #{pane_height}"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    parts = result.stdout.strip().split()
                    if len(parts) == 2:
                        cols, rows = int(parts[0]), int(parts[1])
            except Exception:
                cols, rows = shutil.get_terminal_size()
        else:
            cols, rows = shutil.get_terminal_size()

        # Estimate pixels - typical cell is ~9x18 pixels
        return cols * 9, rows * 18

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

    def render_frame(self, state: GameState) -> None:
        """Render a complete frame."""
        import time
        import traceback
        start = time.perf_counter()

        self._frame_count += 1

        try:
            # Close previous frame to free memory
            if hasattr(self, 'frame') and self.frame is not None:
                self.frame.close()

            # Periodic garbage collection to prevent memory buildup
            if self._frame_count % 100 == 0:
                import gc
                gc.collect()

            # Create fresh frame
            self.frame = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 255))
            self.draw = ImageDraw.Draw(self.frame)

            # Render layers (idle game style)
            self._render_background(state)
            self._render_scene(state)
            self._render_claude_character(state)
            self._render_particles(state)
            self._render_stats_panel(state)
            self._render_activity_indicator(state)

            # Output to terminal
            self._display_frame()
        except Exception as e:
            # Log error to file for debugging
            with open("/tmp/claude_world_error.log", "a") as f:
                f.write(f"\n--- Error at frame {self._frame_count} ---\n")
                f.write(f"Activity: {state.main_agent.activity.value if state and state.main_agent else 'unknown'}\n")
                f.write(f"Tool: {state.main_agent.current_tool if state and state.main_agent else 'unknown'}\n")
                f.write(traceback.format_exc())
            # Don't re-raise - try to keep running

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

        # Water on the edges (like a river or lake border)
        water_width = int(self.width * 0.12)
        # Left water
        self.draw.rectangle([0, grass_start_y, water_width, self.height], fill=self.COLORS["water"])
        # Right water
        self.draw.rectangle([self.width - water_width, grass_start_y, self.width, self.height], fill=self.COLORS["water"])

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

        # Draw clouds in the sky area
        self._draw_pixel_clouds(frame, state.world.time_of_day.phase)

        # Draw ambient floating particles (leaves during day, fireflies at night)
        self._draw_ambient_particles(frame, state.world.time_of_day.phase, px)

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
        # Tree dimensions
        trunk_w = int(px * 3 * scale)
        trunk_h = int(px * 6 * scale)
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

    def _render_particles(self, state: GameState) -> None:
        """Render particle effects."""
        self.particle_count = len(state.particles)

        for particle in state.particles:
            # Simple screen-space particles (no camera transform for idle game style)
            # Center the particle system around Claude
            center_x = self.width // 2
            center_y = int(self.height * 0.55)

            screen_x = center_x + int(particle.position.x - state.main_agent.position.x)
            screen_y = center_y + int(particle.position.y - state.main_agent.position.y)

            alpha = particle.lifetime / particle.max_lifetime
            color = tuple(int(c * alpha) for c in particle.color)
            size = max(1, int(4 * particle.scale * alpha))

            self.draw.ellipse(
                [screen_x - size, screen_y - size, screen_x + size, screen_y + size],
                fill=color
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
        # Coin shine
        self.draw.ellipse(
            [level_x + px * 2, level_y + px * 2, level_x + coin_size // 2, level_y + coin_size // 2],
            fill=(255, 230, 100)
        )

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

        # Level text above bar
        level_text = f"LEVEL {state.progression.level}"
        text_x = bar_x + bar_w // 2 - len(level_text) * 3
        self.draw.text((text_x, bar_y - int(2 * scale)), level_text, fill=self.COLORS["ui_text"])

        # XP bar outline
        self.draw.rectangle(
            [bar_x - px, bar_y + int(12 * scale) - px, bar_x + bar_w + px, bar_y + int(12 * scale) + bar_h + px],
            fill=self.COLORS["outline"]
        )
        # Bar background
        self.draw.rectangle(
            [bar_x, bar_y + int(12 * scale), bar_x + bar_w, bar_y + int(12 * scale) + bar_h],
            fill=(40, 30, 50)
        )
        # Bar fill
        xp_pct = min(1.0, state.progression.experience / max(1, state.progression.experience_to_next))
        if xp_pct > 0:
            fill_w = int(bar_w * xp_pct)
            # Only draw if rectangle has valid dimensions (x1 > x0)
            if fill_w > px * 2:
                self.draw.rectangle(
                    [bar_x + px, bar_y + int(12 * scale) + px, bar_x + fill_w - px, bar_y + int(12 * scale) + bar_h - px],
                    fill=self.COLORS["accent_xp"]
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

        # Position banner above Claude's head
        center_x = self.width // 2
        # Claude's head is around 0.58 * height, so position banner above that
        ground_y = int(self.height * 0.58)
        head_y = ground_y - int(px * 16)  # Approximate head position

        # Banner dimensions
        banner_h = int(px * 6)
        banner_w = int((len(display_text) * 7 + 16) * scale)
        banner_x = center_x - banner_w // 2
        banner_y = head_y - int(px * 12)  # Above Claude's head

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
        pointer_x = center_x
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
        if self._first_frame:
            sys.stdout.write("\033[2J\033[H\033[?25l")
            self._first_frame = False
        else:
            sys.stdout.write("\033[H")

        buf = io.BytesIO()
        try:
            self.frame.save(buf, format="PNG")
            data = base64.b64encode(buf.getvalue()).decode("ascii")
        finally:
            buf.close()

        chunk_size = 4096
        chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

        for i, chunk in enumerate(chunks):
            m = 1 if i < len(chunks) - 1 else 0
            if i == 0:
                sys.stdout.write(f"\033_Ga=T,f=100,m={m};{chunk}\033\\")
            else:
                sys.stdout.write(f"\033_Gm={m};{chunk}\033\\")

        sys.stdout.flush()

    def _display_iterm2(self) -> None:
        """Display using iTerm2 inline images."""
        if self._first_frame:
            sys.stdout.write("\033[2J\033[H\033[?25l")
            self._first_frame = False
        else:
            sys.stdout.write("\033[H")

        buf = io.BytesIO()
        try:
            self.frame.save(buf, format="PNG")
            data = base64.b64encode(buf.getvalue()).decode("ascii")
        finally:
            buf.close()

        if is_inside_tmux():
            self._display_iterm2_multipart(data)
        else:
            img_seq = f"\033]1337;File=inline=1;width={self.width}px;height={self.height}px;preserveAspectRatio=0:{data}\007"
            sys.stdout.write(img_seq)

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

        if self._first_frame:
            sys.stdout.write("\033[2J\033[H\033[?25l")
            self._first_frame = False
        else:
            sys.stdout.write("\033[H")
        sys.stdout.flush()

        tmp_path = "/tmp/claude_world_frame.png"
        self.frame.save(tmp_path, format="PNG")

        # Get current terminal pixel size
        pixel_width, pixel_height = self._get_terminal_pixel_size()

        try:
            import subprocess
            # Scale to fill terminal - use both width and height
            result = subprocess.run(
                ["img2sixel", "-w", str(pixel_width), "-h", str(pixel_height), tmp_path],
                capture_output=True,
            )
            if result.returncode == 0:
                sys.stdout.buffer.write(result.stdout)
                sys.stdout.flush()
            # Explicitly delete result to free subprocess buffers
            del result
        except Exception:
            pass

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
