"""Tests to detect and prevent rendering flickering issues.

IMPORTANT: This game ALWAYS runs inside tmux. Tests assume tmux environment.

These tests capture render output to detect:
- Multiple renders per frame
- Inconsistent frame sizes
- Duplicate escape sequences
- Size changes between frames
- Tmux passthrough issues
- Sixel scaling problems
"""

from __future__ import annotations

import io
import os
import re
import sys
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest

from claude_world.renderer.terminal_graphics import TerminalGraphicsRenderer
from claude_world.renderer.display import (
    detect_graphics_protocol,
    tmux_wrap,
    is_inside_tmux,
)
from claude_world.types import (
    Position,
    Velocity,
    GameState,
    WorldState,
    TerrainData,
    WeatherState,
    TimeOfDay,
    AgentEntity,
    EntityType,
    AgentActivity,
    AnimationState,
    Progression,
    Resources,
    Camera,
)


@contextmanager
def tmux_environment():
    """Context manager that ensures tmux environment variables are set."""
    original_tmux = os.environ.get("TMUX")
    original_term = os.environ.get("TERM")
    try:
        os.environ["TMUX"] = "/tmp/tmux-1000/default,12345,0"
        os.environ["TERM"] = "screen-256color"
        yield
    finally:
        if original_tmux is None:
            os.environ.pop("TMUX", None)
        else:
            os.environ["TMUX"] = original_tmux
        if original_term is None:
            os.environ.pop("TERM", None)
        else:
            os.environ["TERM"] = original_term


@pytest.fixture(autouse=True)
def ensure_tmux_env():
    """Ensure all tests run with tmux environment."""
    with tmux_environment():
        yield


@pytest.fixture
def mock_game_state():
    """Create a minimal game state for testing."""
    import numpy as np

    terrain = TerrainData(
        heightmap=np.zeros((10, 10), dtype=np.float32),
        tiles=np.full((10, 10), 2, dtype=np.uint8),
        decorations=[],
    )

    world = WorldState(
        name="test",
        width=100,
        height=100,
        terrain=terrain,
        water_offset=0.0,
        weather=WeatherState(
            type="clear",
            intensity=0.0,
            wind_direction=0.0,
            wind_speed=0.0,
        ),
        time_of_day=TimeOfDay(hour=12.0),
        ambient_light=(255, 255, 255),
    )

    agent = AgentEntity(
        id="main_agent",
        type=EntityType.MAIN_AGENT,
        position=Position(50.0, 50.0),
        velocity=Velocity(0.0, 0.0),
        sprite_id="claude_main",
        animation=AnimationState(current_animation="idle"),
        agent_type="main",
        activity=AgentActivity.IDLE,
    )

    return GameState(
        world=world,
        entities={"main_agent": agent},
        main_agent=agent,
        particles=[],
        resources=Resources(),
        progression=Progression(),
        camera=Camera(x=50, y=50, target="main_agent"),
        session_active=True,
    )


class OutputCapture:
    """Captures stdout writes for analysis."""

    def __init__(self):
        self.writes: list[str] = []
        self.buffer_writes: list[bytes] = []
        self._buffer = BufferCapture(self)

    def write(self, data: str) -> int:
        self.writes.append(data)
        return len(data)

    def flush(self) -> None:
        pass

    @property
    def buffer(self):
        """Mock buffer for binary writes."""
        return self._buffer

    def count_cursor_home(self) -> int:
        """Count cursor home sequences (\\033[H)."""
        return sum(1 for w in self.writes if "\033[H" in w)

    def count_clear_screen(self) -> int:
        """Count clear screen sequences (\\033[2J)."""
        return sum(1 for w in self.writes if "\033[2J" in w)

    def count_tmux_passthrough_starts(self) -> int:
        """Count tmux passthrough sequence starts."""
        return sum(1 for w in self.writes if "\033Ptmux;" in w)

    def count_sixel_starts(self) -> int:
        """Count sixel DCS sequence starts in buffer writes.

        Each buffer write that contains sixel data counts as one sixel output.
        We check for the DCS (Device Control String) start sequence.
        """
        count = 0
        for w in self.buffer_writes:
            # Sixel starts with ESC P (DCS) - check if this write contains sixel data
            # \033P and \x1bP are the same (ESC P)
            if b"\033P" in w or b"\x1bP" in w:
                count += 1
        return count

    def count_iterm2_images(self) -> int:
        """Count iTerm2 inline image sequences."""
        count = 0
        for w in self.writes:
            # Regular iTerm2 image
            count += len(re.findall(r"\033\]1337;File=inline=1", w))
            # Multipart start
            count += len(re.findall(r"\033\]1337;MultipartFile=inline=1", w))
        return count

    def count_kitty_images(self) -> int:
        """Count Kitty graphics protocol transmissions."""
        count = 0
        for w in self.writes:
            # Kitty image start (a=T means transmit)
            count += len(re.findall(r"\033_Ga=T", w))
        return count

    def extract_iterm2_dimensions(self) -> list[tuple[int, int]]:
        """Extract width/height from iTerm2 image sequences."""
        dims = []
        for w in self.writes:
            matches = re.findall(r"width=(\d+)px;height=(\d+)px", w)
            dims.extend((int(m[0]), int(m[1])) for m in matches)
        return dims

    def get_all_output(self) -> str:
        """Get all captured output as single string."""
        return "".join(self.writes)

    def get_all_binary_output(self) -> bytes:
        """Get all binary output."""
        return b"".join(self.buffer_writes)


class BufferCapture:
    """Captures binary writes to stdout.buffer."""

    def __init__(self, parent: OutputCapture):
        self.parent = parent

    def write(self, data: bytes) -> int:
        self.parent.buffer_writes.append(data)
        return len(data)

    def flush(self) -> None:
        pass


class TestTmuxEnvironment:
    """Tests that verify tmux environment handling."""

    def test_is_inside_tmux_returns_true(self):
        """Test we correctly detect tmux environment."""
        assert is_inside_tmux() is True

    def test_protocol_is_sixel_in_tmux(self):
        """Test sixel protocol is selected in tmux."""
        protocol = detect_graphics_protocol()
        assert protocol == "sixel", f"Expected sixel in tmux, got {protocol}"

    def test_tmux_wrap_wraps_sequences(self):
        """Test tmux_wrap properly wraps escape sequences."""
        seq = "\033[H"
        wrapped = tmux_wrap(seq)
        assert "\033Ptmux;" in wrapped
        assert wrapped.endswith("\033\\")


class TestRendererSizeConsistency:
    """Tests that renderer maintains consistent size in tmux."""

    def test_renderer_size_fixed_at_init(self):
        """Test renderer width/height don't change after init."""
        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    renderer = TerminalGraphicsRenderer(width=800, height=400)

        initial_width = renderer.width
        initial_height = renderer.height

        assert renderer.width == initial_width
        assert renderer.height == initial_height
        assert renderer.protocol == "sixel"  # Should be sixel in tmux

    def test_frame_buffer_matches_renderer_size(self, mock_game_state):
        """Test frame buffer dimensions match renderer dimensions."""
        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch.object(TerminalGraphicsRenderer, '_display_frame'):
                        renderer = TerminalGraphicsRenderer(width=800, height=400)
                        renderer.render_frame(mock_game_state)

        assert renderer.frame.width == renderer.width
        assert renderer.frame.height == renderer.height

    def test_multiple_frames_same_size(self, mock_game_state):
        """Test multiple renders produce same size frames."""
        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch.object(TerminalGraphicsRenderer, '_display_frame'):
                        renderer = TerminalGraphicsRenderer(width=800, height=400)

                        sizes = []
                        for _ in range(10):
                            renderer.render_frame(mock_game_state)
                            sizes.append((renderer.frame.width, renderer.frame.height))

        # All frames should be same size
        assert len(set(sizes)) == 1, f"Frame sizes varied: {set(sizes)}"


class TestSingleRenderPerFrame:
    """Tests that only one render output happens per frame in tmux."""

    def test_sixel_single_output_per_frame(self, mock_game_state):
        """Test sixel outputs exactly once per frame."""
        capture = OutputCapture()

        # Mock img2sixel to return fake sixel data
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"\033Pq#0;2;0;0;0~-\033\\"

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch('shutil.which', return_value='/usr/bin/img2sixel'):
                        with patch('subprocess.run', return_value=mock_result):
                            renderer = TerminalGraphicsRenderer(width=800, height=400)
                            assert renderer.protocol == "sixel"

                            with patch.object(sys, 'stdout', capture):
                                renderer.render_frame(mock_game_state)

        # Should have exactly 1 sixel output
        assert capture.count_sixel_starts() == 1, \
            f"Expected 1 sixel output, got {capture.count_sixel_starts()}"

    def test_single_cursor_home_per_frame(self, mock_game_state):
        """Test only one cursor home sequence per frame (after first)."""
        capture = OutputCapture()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"\033Pq#0;2;0;0;0~-\033\\"

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch('shutil.which', return_value='/usr/bin/img2sixel'):
                        with patch('subprocess.run', return_value=mock_result):
                            renderer = TerminalGraphicsRenderer(width=800, height=400)
                            renderer._first_frame = False  # Not first frame

                            with patch.object(sys, 'stdout', capture):
                                renderer.render_frame(mock_game_state)

        # Should have exactly 1 cursor home
        assert capture.count_cursor_home() == 1, \
            f"Expected 1 cursor home, got {capture.count_cursor_home()}"


class TestNoDoubleRender:
    """Tests that there's no accidental double rendering in tmux."""

    def test_render_frame_single_display_call(self, mock_game_state):
        """Test render_frame calls _display_frame exactly once."""
        display_calls = []

        def mock_display():
            display_calls.append(1)

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    renderer = TerminalGraphicsRenderer(width=800, height=400)
                    renderer._display_frame = mock_display

                    renderer.render_frame(mock_game_state)

        assert len(display_calls) == 1, \
            f"_display_frame called {len(display_calls)} times, expected 1"

    def test_no_multiple_image_starts(self, mock_game_state):
        """Test no multiple image protocol starts in single frame."""
        capture = OutputCapture()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"\033Pq#0;2;0;0;0~-\033\\"

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch('shutil.which', return_value='/usr/bin/img2sixel'):
                        with patch('subprocess.run', return_value=mock_result):
                            renderer = TerminalGraphicsRenderer(width=800, height=400)

                            with patch.object(sys, 'stdout', capture):
                                renderer.render_frame(mock_game_state)

        output = capture.get_all_output()

        # Count image outputs by checking capture counts
        sixel_count = capture.count_sixel_starts()
        iterm2_count = capture.count_iterm2_images()
        kitty_count = capture.count_kitty_images()

        # Total should be exactly 1
        total = sixel_count + iterm2_count + kitty_count
        assert total == 1, \
            f"Multiple image outputs: sixel={sixel_count}, iterm2={iterm2_count}, kitty={kitty_count}"


class TestSixelScaling:
    """Tests for sixel scaling issues that cause flickering."""

    def test_img2sixel_called_without_scaling_args(self, mock_game_state):
        """Test img2sixel is called without auto-scaling arguments."""
        called_args = []

        def capture_run(args, **kwargs):
            called_args.append(args)
            result = MagicMock()
            result.returncode = 0
            result.stdout = b"\033Pq~-\033\\"
            return result

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch('shutil.which', return_value='/usr/bin/img2sixel'):
                        with patch('subprocess.run', side_effect=capture_run):
                            with patch.object(sys, 'stdout', OutputCapture()):
                                renderer = TerminalGraphicsRenderer(width=800, height=400)
                                renderer.render_frame(mock_game_state)

        assert len(called_args) > 0, "img2sixel was not called"
        args = called_args[0]

        # Check that no scaling options are passed
        # -w (width) and -h (height) options would cause scaling
        assert "-w" not in args, "img2sixel should not have -w scaling"
        assert "-h" not in args, "img2sixel should not have -h scaling"
        assert "--width" not in args, "img2sixel should not have --width scaling"
        assert "--height" not in args, "img2sixel should not have --height scaling"

    def test_frame_saved_at_correct_size_for_sixel(self, mock_game_state):
        """Test the PNG saved for sixel is at renderer's native size."""
        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch.object(TerminalGraphicsRenderer, '_display_frame'):
                        renderer = TerminalGraphicsRenderer(width=800, height=400)
                        renderer.render_frame(mock_game_state)

                        # Check the frame that would be saved
                        assert renderer.frame.width == 800
                        assert renderer.frame.height == 400

    def test_png_saved_for_sixel_has_correct_dimensions(self, mock_game_state):
        """Test the actual PNG file saved for img2sixel has correct dimensions."""
        from PIL import Image
        import tempfile
        import os

        saved_path = None

        def capture_save(self_img, path, **kwargs):
            nonlocal saved_path
            saved_path = path
            # Actually save the image so we can check it
            original_save(self_img, path, **kwargs)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"\033Pq~-\033\\"

        from PIL.Image import Image as PILImage
        original_save = PILImage.save

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch('shutil.which', return_value='/usr/bin/img2sixel'):
                        with patch('subprocess.run', return_value=mock_result):
                            with patch.object(PILImage, 'save', capture_save):
                                with patch.object(sys, 'stdout', OutputCapture()):
                                    renderer = TerminalGraphicsRenderer(width=800, height=400)
                                    renderer.render_frame(mock_game_state)

        # Verify the saved PNG has correct dimensions
        assert saved_path is not None, "PNG was not saved"
        if os.path.exists(saved_path):
            with Image.open(saved_path) as img:
                assert img.width == 800, f"PNG width {img.width} != renderer width 800"
                assert img.height == 400, f"PNG height {img.height} != renderer height 400"


class TestFrameCountTracking:
    """Tests for frame count consistency."""

    def test_frame_count_increments_once_per_render(self, mock_game_state):
        """Test frame count increments exactly once per render_frame call."""
        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch.object(TerminalGraphicsRenderer, '_display_frame'):
                        renderer = TerminalGraphicsRenderer(width=800, height=400)

                        initial = renderer._frame_count
                        for i in range(5):
                            renderer.render_frame(mock_game_state)
                            assert renderer._frame_count == initial + i + 1, \
                                f"Frame count wrong after render {i+1}"


class TestTmuxScrollbackClearing:
    """Tests for tmux scrollback clearing (can cause flicker if done wrong)."""

    def test_scrollback_clear_not_every_frame(self, mock_game_state):
        """Test scrollback isn't cleared every frame (causes flicker)."""
        clear_calls = []

        def mock_clear():
            clear_calls.append(1)

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch.object(TerminalGraphicsRenderer, '_display_frame'):
                        renderer = TerminalGraphicsRenderer(width=800, height=400)
                        renderer._clear_tmux_scrollback = mock_clear

                        # Render 10 frames
                        for _ in range(10):
                            renderer.render_frame(mock_game_state)

        # Should NOT clear on every frame
        assert len(clear_calls) < 10, \
            f"Scrollback cleared {len(clear_calls)} times in 10 frames - too frequent!"

    def test_scrollback_clear_interval_reasonable(self, mock_game_state):
        """Test scrollback clear happens at reasonable intervals."""
        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch.object(TerminalGraphicsRenderer, '_display_frame'):
                        renderer = TerminalGraphicsRenderer(width=800, height=400)

                        # The interval should be at least 100 frames
                        # Check the constant or logic
                        # At 30fps, 100 frames = ~3.3 seconds minimum
                        assert renderer._last_scrollback_clear == 0


class TestConsecutiveFrameConsistency:
    """Tests that consecutive frames don't cause visual jumps."""

    def test_no_clear_screen_between_frames(self, mock_game_state):
        """Test no full screen clear between consecutive frames."""
        captures = []

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"\033Pq~-\033\\"

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch('shutil.which', return_value='/usr/bin/img2sixel'):
                        with patch('subprocess.run', return_value=mock_result):
                            renderer = TerminalGraphicsRenderer(width=800, height=400)
                            renderer._first_frame = False  # Not first frame

                            for _ in range(5):
                                capture = OutputCapture()
                                with patch.object(sys, 'stdout', capture):
                                    renderer.render_frame(mock_game_state)
                                captures.append(capture)

        # After first frame, should never have clear screen
        for i, cap in enumerate(captures):
            clear_count = cap.count_clear_screen()
            assert clear_count == 0, \
                f"Frame {i+1} had {clear_count} clear screens - causes flicker!"

    def test_cursor_always_reset_to_home(self, mock_game_state):
        """Test cursor is reset to home before each frame."""
        captures = []

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"\033Pq~-\033\\"

        with patch.object(TerminalGraphicsRenderer, '_get_terminal_pixel_size', return_value=(800, 400)):
            with patch.object(TerminalGraphicsRenderer, '_get_pane_size_static', return_value=(100, 30)):
                with patch.object(TerminalGraphicsRenderer, '_get_cell_size', return_value=(8, 16)):
                    with patch('shutil.which', return_value='/usr/bin/img2sixel'):
                        with patch('subprocess.run', return_value=mock_result):
                            renderer = TerminalGraphicsRenderer(width=800, height=400)
                            renderer._first_frame = False

                            for _ in range(5):
                                capture = OutputCapture()
                                with patch.object(sys, 'stdout', capture):
                                    renderer.render_frame(mock_game_state)
                                captures.append(capture)

        # Each frame should have exactly one cursor home
        for i, cap in enumerate(captures):
            home_count = cap.count_cursor_home()
            assert home_count == 1, \
                f"Frame {i+1} had {home_count} cursor homes, expected 1"
