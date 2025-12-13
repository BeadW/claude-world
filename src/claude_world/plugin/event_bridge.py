"""Event bridge for IPC between plugin and game."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional


class EventBridge:
    """Handles IPC between Claude Code plugin and game engine."""

    def __init__(self, socket_path: Optional[Path] = None):
        """Initialize the event bridge.

        Args:
            socket_path: Path for Unix domain socket. Defaults to temp directory.
        """
        if socket_path is None:
            socket_path = Path(tempfile.gettempdir()) / "claude_world.sock"
        self.socket_path = socket_path
        self.event_queue: list[dict[str, Any]] = []
        self._running = False
        self._server: Optional[asyncio.Server] = None
        self.on_event: Optional[Callable[[dict[str, Any]], Any]] = None
        self.on_query: Optional[Callable[[str], dict[str, Any]]] = None
        self.on_action: Optional[Callable[[str, dict[str, Any]], dict[str, Any]]] = None

    def serialize_event(self, event: dict[str, Any]) -> bytes:
        """Serialize an event for transmission.

        Args:
            event: Event dictionary.

        Returns:
            Serialized bytes.
        """
        return json.dumps(event).encode("utf-8")

    def deserialize_event(self, data: bytes) -> dict[str, Any]:
        """Deserialize an event from bytes.

        Args:
            data: Serialized event bytes.

        Returns:
            Event dictionary.
        """
        return json.loads(data.decode("utf-8"))

    def queue_event(self, event: dict[str, Any]) -> None:
        """Add an event to the queue.

        Args:
            event: Event to queue.
        """
        self.event_queue.append(event)

    def get_queued_events(self) -> list[dict[str, Any]]:
        """Get and clear all queued events.

        Returns:
            List of queued events.
        """
        events = self.event_queue[:]
        self.event_queue.clear()
        return events

    async def process_queued_events(self) -> None:
        """Process all queued events through the handler."""
        if self.on_event is None:
            return

        events = self.get_queued_events()
        for event in events:
            result = self.on_event(event)
            if asyncio.iscoroutine(result):
                await result

    async def start_server(self) -> None:
        """Start the Unix socket server."""
        # Clean up old socket
        if self.socket_path.exists():
            os.unlink(self.socket_path)

        self._running = True

        async def handle_client(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            """Handle a client connection."""
            try:
                while self._running:
                    # Read length prefix (4 bytes)
                    length_data = await reader.read(4)
                    if not length_data:
                        break

                    length = int.from_bytes(length_data, "big")
                    if length > 1024 * 1024:  # 1MB max
                        break

                    # Read event data
                    data = await reader.read(length)
                    if not data:
                        break

                    try:
                        message = self.deserialize_event(data)

                        # Check if it's a query, action, or event
                        if message.get("type") == "QUERY":
                            # Handle query - return game state
                            query_type = message.get("query", "status")
                            if self.on_query:
                                result = self.on_query(query_type)
                                response = json.dumps(result).encode("utf-8")
                                writer.write(len(response).to_bytes(4, "big"))
                                writer.write(response)
                            else:
                                writer.write(b"\x00\x00\x00\x02OK")
                            await writer.drain()
                        elif message.get("type") == "ACTION":
                            # Handle action - modify game state
                            action_type = message.get("action", "")
                            action_data = message.get("data", {})
                            if self.on_action:
                                result = self.on_action(action_type, action_data)
                                response = json.dumps(result).encode("utf-8")
                                writer.write(len(response).to_bytes(4, "big"))
                                writer.write(response)
                            else:
                                writer.write(b"\x00\x00\x00\x02OK")
                            await writer.drain()
                        else:
                            # Handle event
                            self.queue_event(message)
                            await self.process_queued_events()
                            writer.write(b"OK")
                            await writer.drain()
                    except json.JSONDecodeError:
                        writer.write(b"ERR")
                        await writer.drain()

            except asyncio.CancelledError:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        self._server = await asyncio.start_unix_server(
            handle_client,
            path=str(self.socket_path),
        )

        async with self._server:
            await self._server.serve_forever()

    def stop(self) -> None:
        """Stop the event bridge server."""
        self._running = False
        if self._server is not None:
            self._server.close()

    async def send_event(self, event: dict[str, Any]) -> bool:
        """Send an event to the server.

        Args:
            event: Event to send.

        Returns:
            True if sent successfully.
        """
        try:
            reader, writer = await asyncio.open_unix_connection(
                path=str(self.socket_path)
            )

            # Serialize event
            data = self.serialize_event(event)

            # Send length prefix + data
            writer.write(len(data).to_bytes(4, "big"))
            writer.write(data)
            await writer.drain()

            # Wait for acknowledgment
            response = await reader.read(2)
            writer.close()
            await writer.wait_closed()

            return response == b"OK"

        except (ConnectionRefusedError, FileNotFoundError):
            return False

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        if self.socket_path.exists():
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
