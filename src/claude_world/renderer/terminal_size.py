"""Terminal size detection and tmux pane management."""

from __future__ import annotations

import os
import shutil
import sys

# Cache cell size to prevent oscillation when pane resizes
_cached_cell_size: tuple[int, int] | None = None

# Fixed aspect ratio for game (width:height)
ASPECT_RATIO = 2.5  # 2.5:1 ratio gives a nice wide game view


def is_inside_tmux() -> bool:
    """Check if we're running inside tmux."""
    return "TMUX" in os.environ


def get_pane_size() -> tuple[int, int]:
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


def get_terminal_pixel_width() -> int:
    """Get terminal/pane width in pixels."""
    import fcntl
    import struct
    import subprocess
    import termios

    # Get cell width from ioctl
    cell_width = 16  # Default
    try:
        result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\x00' * 8)
        term_rows, term_cols, xpixel, ypixel = struct.unpack('HHHH', result)
        if term_cols > 0 and xpixel > 0:
            cell_width = xpixel // term_cols
    except Exception:
        pass

    # In tmux, get pane width in columns and multiply by cell width
    if is_inside_tmux():
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#{pane_width}"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                pane_cols = int(result.stdout.strip())
                return pane_cols * cell_width
        except Exception:
            pass

    # Fallback: use ioctl pixel width directly
    try:
        result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\x00' * 8)
        term_rows, term_cols, xpixel, ypixel = struct.unpack('HHHH', result)
        if xpixel > 0:
            return xpixel
    except Exception:
        pass

    # Last resort fallback
    cols, rows = shutil.get_terminal_size()
    return cols * cell_width


def get_terminal_pixel_size() -> tuple[int, int]:
    """Get terminal size in pixels for frame size.

    In multi-pane mode: width from terminal, height from aspect ratio.
    In single-pane mode: use actual terminal dimensions.
    """
    import fcntl
    import struct
    import subprocess
    import termios

    width = get_terminal_pixel_width()

    # Check if we're in single-pane mode
    if is_inside_tmux():
        try:
            result = subprocess.run(
                ["tmux", "list-panes", "-F", "#{pane_id}"],
                capture_output=True,
                text=True,
            )
            pane_count = len(result.stdout.strip().split('\n')) if result.returncode == 0 else 1
        except Exception:
            pane_count = 1

        if pane_count == 1:
            # Single pane - use actual terminal height
            try:
                result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\x00' * 8)
                _, _, _, ypixel = struct.unpack('HHHH', result)
                if ypixel > 0:
                    return width, ypixel
            except Exception:
                pass

    # Multi-pane mode or fallback - use aspect ratio
    height = int(width / ASPECT_RATIO)
    return width, height


def get_cell_size() -> tuple[int, int]:
    """Get terminal cell size in pixels.

    Uses ioctl for pixel dimensions and tmux window dimensions
    to calculate actual cell size. Includes 20% correction for
    terminal chrome not reported in ioctl pixel values.

    Result is cached to prevent oscillation when pane resizes.
    """
    global _cached_cell_size

    if _cached_cell_size is not None:
        return _cached_cell_size

    import fcntl
    import struct
    import subprocess
    import termios

    try:
        # Get pixel dimensions from ioctl (returns full terminal size)
        result = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b'\x00' * 8)
        _, _, xpixel, ypixel = struct.unpack('HHHH', result)

        if xpixel > 0 and ypixel > 0 and is_inside_tmux():
            # Get total window dimensions (all panes combined)
            tmux_result = subprocess.run(
                ["tmux", "display-message", "-p", "#{window_width} #{window_height}"],
                capture_output=True,
                text=True,
            )
            if tmux_result.returncode == 0:
                parts = tmux_result.stdout.strip().split()
                if len(parts) == 2:
                    window_cols, window_rows = int(parts[0]), int(parts[1])
                    cell_w = xpixel // window_cols
                    # Add 20% to account for terminal chrome not in ypixel
                    cell_h = (ypixel * 120) // (window_rows * 100)
                    _cached_cell_size = (cell_w, cell_h)
                    return _cached_cell_size
    except Exception:
        pass

    _cached_cell_size = (16, 20)  # Fallback
    return _cached_cell_size


def resize_tmux_pane(height: int, cell_height: int) -> None:
    """Resize the current tmux pane to fit the rendered frame.

    Args:
        height: Target height in pixels.
        cell_height: Height of a character cell in pixels.
    """
    if not is_inside_tmux():
        return

    import subprocess

    # Calculate required rows for frame height
    required_rows = (height + cell_height - 1) // cell_height

    # Get pane info and window height
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{pane_id} #{pane_height} #{window_height}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split()
            pane_id = parts[0]
            current_rows = int(parts[1])
            window_rows = int(parts[2])
        else:
            return
    except Exception:
        return

    # In single-pane mode (pane == window), don't try to resize
    if current_rows >= window_rows - 2:
        return

    # Don't try to resize beyond window height (minus room for other panes)
    max_rows = window_rows - 5
    if required_rows > max_rows:
        required_rows = max_rows

    # Log resize attempts
    with open("/tmp/claude_world_resize.log", "a") as f:
        f.write(f"height={height} cell_h={cell_height} required={required_rows} current={current_rows} diff={abs(current_rows - required_rows)}\n")

    # Only resize if difference is more than 2 rows (prevents oscillation)
    if abs(current_rows - required_rows) > 2:
        try:
            subprocess.run(
                ["tmux", "resize-pane", "-t", pane_id, "-y", str(required_rows)],
                capture_output=True,
            )
        except Exception:
            pass


def get_pane_pixel_size(cell_width: int, cell_height: int, fallback_width: int, fallback_height: int) -> tuple[int, int]:
    """Get current tmux pane size in pixels.

    Args:
        cell_width: Width of a character cell in pixels.
        cell_height: Height of a character cell in pixels.
        fallback_width: Width to return on error.
        fallback_height: Height to return on error.
    """
    import subprocess

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
                return cols * cell_width, rows * cell_height
    except Exception:
        pass

    return fallback_width, fallback_height
