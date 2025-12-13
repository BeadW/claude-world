"""PTY management for Claude CLI passthrough."""

from __future__ import annotations

import os
import pty
import select
import signal
import subprocess
import termios
import tty
from typing import Optional, Callable


class StartupFilter:
    """Filters Claude Code startup/welcome screen output."""

    # Characters that indicate startup box
    BOX_CHARS = {"╭", "╮", "╰", "╯", "│", "─", "┬", "┴", "├", "┤", "┼"}

    def __init__(self):
        """Initialize the startup filter."""
        self.in_startup = True
        self._box_line_count = 0
        self._empty_after_box = 0

    def is_startup_content(self, text: str) -> bool:
        """Check if text appears to be startup content.

        Args:
            text: Text to check.

        Returns:
            True if text looks like startup content.
        """
        if not self.in_startup:
            return False

        # Check for box drawing characters
        for char in text:
            if char in self.BOX_CHARS:
                return True

        return False

    def process_line(self, line: str) -> bool:
        """Process a line and update state.

        Args:
            line: Line to process.

        Returns:
            True if line should be filtered out.
        """
        if not self.in_startup:
            return False

        # Check for box drawing characters
        has_box = any(char in self.BOX_CHARS for char in line)

        if has_box:
            self._box_line_count += 1
            return True

        # Check for end of box (empty line after box)
        if self._box_line_count > 0:
            stripped = line.strip()
            if stripped == "":
                self._empty_after_box += 1
                if self._empty_after_box >= 1:
                    # End of startup, but still filter this line
                    return True
            elif stripped.startswith(">") or stripped.startswith("$"):
                # Prompt detected, exit startup mode
                self.in_startup = False
                return False
            elif not has_box:
                # Non-box content after seeing box - might be normal output
                self._empty_after_box += 1
                if self._empty_after_box >= 2:
                    self.in_startup = False
                return self._empty_after_box < 2

        return False

    def filter_lines(self, lines: list[str]) -> list[str]:
        """Filter multiple lines.

        Args:
            lines: Lines to filter.

        Returns:
            Filtered lines.
        """
        result = []
        for line in lines:
            if not self.process_line(line):
                result.append(line)
        return result


class PTYManager:
    """Manages PTY for Claude CLI subprocess."""

    def __init__(
        self,
        command: Optional[list[str]] = None,
        on_output: Optional[Callable[[bytes], None]] = None,
    ):
        """Initialize the PTY manager.

        Args:
            command: Command to run. Defaults to ['claude'].
            on_output: Callback for output data.
        """
        self.command = command or ["claude"]
        self.on_output = on_output
        self.startup_filter = StartupFilter()

        self._master_fd: Optional[int] = None
        self._slave_fd: Optional[int] = None
        self._process: Optional[subprocess.Popen] = None
        self._running = False

        self.cols = 80
        self.rows = 24
        self._write_buffer: list[bytes] = []

    def start(self) -> bool:
        """Start the PTY and subprocess.

        Returns:
            True if started successfully.
        """
        try:
            # Create pseudo-terminal
            self._master_fd, self._slave_fd = pty.openpty()

            # Set terminal size
            self._set_terminal_size()

            # Start subprocess
            self._process = subprocess.Popen(
                self.command,
                stdin=self._slave_fd,
                stdout=self._slave_fd,
                stderr=self._slave_fd,
                preexec_fn=os.setsid,
            )

            self._running = True

            # Close slave in parent
            os.close(self._slave_fd)
            self._slave_fd = None

            return True

        except Exception:
            self._cleanup()
            return False

    def _set_terminal_size(self) -> None:
        """Set terminal size on the PTY."""
        if self._slave_fd is not None:
            try:
                import fcntl
                import struct

                size = struct.pack("HHHH", self.rows, self.cols, 0, 0)
                fcntl.ioctl(self._slave_fd, termios.TIOCSWINSZ, size)
            except Exception:
                pass

    def write(self, data: bytes) -> None:
        """Write data to the PTY.

        Args:
            data: Data to write.
        """
        if self._master_fd is not None:
            try:
                os.write(self._master_fd, data)
            except OSError:
                pass
        else:
            # Buffer for later
            self._write_buffer.append(data)

    def read(self, timeout: float = 0.01) -> bytes:
        """Read data from the PTY.

        Args:
            timeout: Read timeout in seconds.

        Returns:
            Data read from PTY.
        """
        if self._master_fd is None:
            return b""

        try:
            ready, _, _ = select.select([self._master_fd], [], [], timeout)
            if ready:
                return os.read(self._master_fd, 4096)
        except OSError:
            pass

        return b""

    def resize(self, cols: int, rows: int) -> None:
        """Resize the PTY.

        Args:
            cols: New column count.
            rows: New row count.
        """
        self.cols = cols
        self.rows = rows

        if self._master_fd is not None:
            try:
                import fcntl
                import struct

                size = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, size)

                # Send SIGWINCH to process
                if self._process is not None:
                    self._process.send_signal(signal.SIGWINCH)
            except Exception:
                pass

    def is_alive(self) -> bool:
        """Check if subprocess is still running.

        Returns:
            True if subprocess is alive.
        """
        if self._process is None:
            return False
        return self._process.poll() is None

    def stop(self) -> None:
        """Stop the PTY and subprocess."""
        self._running = False

        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._process.kill()
            except Exception:
                pass

        self._cleanup()

    def _cleanup(self) -> None:
        """Clean up file descriptors."""
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

        if self._slave_fd is not None:
            try:
                os.close(self._slave_fd)
            except OSError:
                pass
            self._slave_fd = None
