#!/usr/bin/env python3
"""Start Claude World with tmux split view.

This script creates a tmux session with:
- Top pane: Animated game world
- Bottom pane: Claude CLI session

The game reacts to Claude's activities through the hook system.

Usage:
    python scripts/start_claude_world.py [--game-height 200] [--fps 30]
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def check_tmux():
    """Check if tmux is available."""
    if shutil.which("tmux") is None:
        print("Error: tmux is required but not found.")
        print("Install with: brew install tmux (macOS) or apt install tmux (Linux)")
        sys.exit(1)


def check_claude():
    """Check if claude CLI is available."""
    if shutil.which("claude") is None:
        print("Error: claude CLI is required but not found.")
        print("Install with: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)


def get_session_name():
    """Generate a unique session name."""
    return f"claude-world-{os.getpid()}"


def get_terminal_size():
    """Get terminal size in columns, rows, and estimate cell dimensions."""
    cols, rows = shutil.get_terminal_size()
    # Approximate character cell size (varies by font/terminal)
    # These are reasonable defaults for most terminals
    char_width = 10
    char_height = 20
    return cols, rows, char_width, char_height


def pixels_to_rows(pixel_height: int, char_height: int = 20) -> int:
    """Convert pixel height to terminal rows."""
    return max(5, (pixel_height + char_height - 1) // char_height)


def create_tmux_session(session_name: str, game_height_px: int, fps: int):
    """Create tmux session with split panes.

    Args:
        session_name: Name for the tmux session.
        game_height_px: Height of game area in pixels.
        fps: Target frames per second for game.
    """
    script_dir = Path(__file__).parent.absolute()
    game_renderer = script_dir / "game_renderer.py"
    project_root = script_dir.parent

    # Get terminal dimensions
    cols, rows, char_width, char_height = get_terminal_size()
    game_rows = pixels_to_rows(game_height_px, char_height)

    # Calculate game width based on terminal width
    game_width_px = cols * char_width

    # Get Python from venv if available
    venv_python = project_root / ".venv" / "bin" / "python3"
    if venv_python.exists():
        python_cmd = str(venv_python)
    else:
        python_cmd = sys.executable

    # Detect parent terminal for graphics passthrough
    term_program = os.environ.get("TERM_PROGRAM", "")
    term_env = f"TERM_PROGRAM={term_program}" if term_program else ""

    # Game renderer command with explicit dimensions
    game_cmd = f"{term_env} {python_cmd} {game_renderer} --width {game_width_px} --height {game_height_px} --fps {fps}".strip()

    # Create new tmux session with GAME in first (top) pane
    subprocess.run([
        "tmux", "new-session",
        "-d",  # Detached
        "-s", session_name,
        "bash", "-c", game_cmd,
    ], check=True)

    # Configure session for seamless experience
    # Hide status bar
    subprocess.run([
        "tmux", "set-option", "-t", session_name, "status", "off"
    ], check=True)

    # Enable mouse mode for independent pane scrolling
    subprocess.run([
        "tmux", "set-option", "-t", session_name, "mouse", "on"
    ], check=True)

    # Allow passthrough (for non-sixel protocols if needed)
    subprocess.run([
        "tmux", "set-option", "-t", session_name, "allow-passthrough", "on"
    ], capture_output=True)  # May fail on older tmux, that's ok

    # Add a visual separator between panes
    subprocess.run([
        "tmux", "set-option", "-t", session_name, "pane-border-style", "fg=colour240"
    ], capture_output=True)
    subprocess.run([
        "tmux", "set-option", "-t", session_name, "pane-active-border-style", "fg=colour240"
    ], capture_output=True)

    # Wrap claude command to run from project directory (to pick up .claude/settings.json hooks)
    # and kill session when it exits
    claude_cmd = f"cd {project_root} && claude; tmux kill-session -t {session_name}"

    # Split and run Claude in bottom pane
    # Use -l to specify exact line count for game pane (more precise than percentage)
    subprocess.run([
        "tmux", "split-window",
        "-t", session_name,
        "-v",  # Vertical split
        "bash", "-c", claude_cmd,
    ], check=True)

    # Resize the top pane (game) to exact row count
    subprocess.run([
        "tmux", "resize-pane",
        "-t", f"{session_name}:0.0",  # Top pane (game)
        "-y", str(game_rows),
    ], check=True)

    # Select the bottom pane (Claude) so user can interact immediately
    subprocess.run([
        "tmux", "select-pane",
        "-t", f"{session_name}:0.1",  # Bottom pane (Claude)
    ], check=True)


def attach_to_session(session_name: str):
    """Attach to the tmux session."""
    # Replace current process with tmux attach
    os.execlp("tmux", "tmux", "attach-session", "-t", session_name)


def cleanup_session(session_name: str):
    """Kill the tmux session."""
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
    )


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Claude World - Animated game that reacts to Claude Code"
    )
    parser.add_argument(
        "--game-height",
        type=int,
        default=300,
        help="Height of game area in pixels (default: 300)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target frames per second (default: 30)",
    )

    args = parser.parse_args()

    # Validate game height
    if args.game_height < 50 or args.game_height > 800:
        print("Error: --game-height must be between 50 and 800 pixels")
        sys.exit(1)

    # Check dependencies
    check_tmux()
    check_claude()

    session_name = get_session_name()

    try:
        create_tmux_session(session_name, args.game_height, args.fps)
        time.sleep(0.3)  # Brief pause for session to initialize
        attach_to_session(session_name)

    except subprocess.CalledProcessError as e:
        print(f"Error starting Claude World: {e}")
        cleanup_session(session_name)
        sys.exit(1)
    except KeyboardInterrupt:
        cleanup_session(session_name)


if __name__ == "__main__":
    main()
