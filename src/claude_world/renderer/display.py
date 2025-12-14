"""Display output functions for terminal graphics protocols."""

from __future__ import annotations

import base64
import io
import os
import shutil
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


def is_inside_tmux() -> bool:
    """Check if we're running inside tmux."""
    return "TMUX" in os.environ


def tmux_wrap(sequence: str) -> str:
    """Wrap an escape sequence for tmux passthrough."""
    if not is_inside_tmux():
        return sequence
    escaped = sequence.replace("\033", "\033\033")
    return f"\033Ptmux;{escaped}\033\\"


def detect_graphics_protocol() -> str:
    """Detect which graphics protocol the terminal supports."""
    term = os.environ.get("TERM", "")
    term_program = os.environ.get("TERM_PROGRAM", "")

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


def display_kitty(frame: Image.Image, first_frame: bool) -> bool:
    """Display using Kitty graphics protocol.

    Returns: new value for first_frame
    """
    if first_frame:
        sys.stdout.write("\033[2J\033[H\033[?25l")
    else:
        sys.stdout.write("\033[H")

    buf = io.BytesIO()
    try:
        frame.save(buf, format="PNG")
        raw_data = buf.getvalue()
    finally:
        buf.close()
        del buf

    data = base64.b64encode(raw_data).decode("ascii")
    del raw_data

    chunk_size = 4096
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        m = 1 if i + chunk_size < len(data) else 0
        if i == 0:
            sys.stdout.write(f"\033_Ga=T,f=100,m={m};{chunk}\033\\")
        else:
            sys.stdout.write(f"\033_Gm={m};{chunk}\033\\")

    del data
    sys.stdout.flush()
    return False


def display_iterm2(frame: Image.Image, width: int, height: int, first_frame: bool) -> bool:
    """Display using iTerm2 inline images.

    Returns: new value for first_frame
    """
    if first_frame:
        sys.stdout.write("\033[2J\033[H\033[?25l")
    else:
        sys.stdout.write("\033[H")

    buf = io.BytesIO()
    try:
        frame.save(buf, format="PNG")
        raw_data = buf.getvalue()
    finally:
        buf.close()
        del buf

    data = base64.b64encode(raw_data).decode("ascii")
    del raw_data

    if is_inside_tmux():
        _display_iterm2_multipart(data, width, height)
    else:
        img_seq = f"\033]1337;File=inline=1;width={width}px;height={height}px;preserveAspectRatio=0:{data}\007"
        sys.stdout.write(img_seq)
        del img_seq

    del data
    sys.stdout.flush()
    return False


def _display_iterm2_multipart(data: str, width: int, height: int) -> None:
    """Display image using iTerm2 multipart protocol for tmux."""
    chunk_size = 65536
    start_seq = f"\033]1337;MultipartFile=inline=1;width={width}px;height={height}px;preserveAspectRatio=0\007"
    sys.stdout.write(tmux_wrap(start_seq))

    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        part_seq = f"\033]1337;FilePart={chunk}\007"
        sys.stdout.write(tmux_wrap(part_seq))

    end_seq = "\033]1337;FileEnd\007"
    sys.stdout.write(tmux_wrap(end_seq))


def display_sixel(frame: Image.Image, first_frame: bool) -> bool:
    """Display using Sixel graphics.

    Returns: new value for first_frame
    """
    if not shutil.which("img2sixel"):
        frame.save("/tmp/claude_world_frame.png")
        if first_frame:
            print("[img2sixel not found]")
        return False

    if first_frame:
        sys.stdout.write("\033[2J\033[H\033[?25l")
    else:
        sys.stdout.write("\033[H")
    sys.stdout.flush()

    tmp_path = "/tmp/claude_world_frame.png"
    frame.save(tmp_path, format="PNG")

    try:
        import subprocess
        result = subprocess.run(
            ["img2sixel", tmp_path],
            capture_output=True,
        )
        if result.returncode == 0:
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.flush()
        del result
    except Exception:
        pass

    return False


_pending_clear_process = None

def clear_tmux_scrollback() -> None:
    """Clear tmux pane scrollback buffer to free terminal memory.

    Manages a single background process to avoid accumulation.
    """
    global _pending_clear_process
    import subprocess

    # Clean up previous process if done
    if _pending_clear_process is not None:
        if _pending_clear_process.poll() is not None:
            _pending_clear_process = None
        else:
            # Previous clear still running, skip this one
            return

    try:
        _pending_clear_process = subprocess.Popen(
            ["tmux", "clear-history"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def enable_focus_reporting() -> None:
    """Enable terminal focus reporting."""
    sys.stdout.write("\033[?1004h")
    sys.stdout.flush()


def disable_focus_reporting() -> None:
    """Disable terminal focus reporting."""
    sys.stdout.write("\033[?1004l")
    sys.stdout.flush()


def cleanup_terminal() -> None:
    """Restore terminal state."""
    sys.stdout.write("\033[?1004l")
    sys.stdout.write("\033[2J\033[H\033[?25h")
    sys.stdout.flush()


def force_clear() -> None:
    """Force a full screen clear."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
