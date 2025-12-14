#!/usr/bin/env python3
"""Claude Code hook client - sends events to Claude World game."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


async def send_event(event: dict) -> bool:
    """Send an event to the Claude World game.

    Args:
        event: Event dictionary to send.

    Returns:
        True if sent successfully.
    """
    socket_path = Path(tempfile.gettempdir()) / "claude_world.sock"

    if not socket_path.exists():
        return False

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(path=str(socket_path)),
            timeout=1.0
        )

        # Serialize event
        data = json.dumps(event).encode("utf-8")

        # Send length prefix + data
        writer.write(len(data).to_bytes(4, "big"))
        writer.write(data)
        await asyncio.wait_for(writer.drain(), timeout=1.0)

        # Wait for acknowledgment with timeout
        response = await asyncio.wait_for(reader.read(2), timeout=1.0)
        writer.close()
        await writer.wait_closed()

        return response == b"OK"

    except Exception as e:
        # Log error for debugging
        try:
            with open("/tmp/claude_world_hook_error.log", "a") as f:
                f.write(f"Hook error: {e}\n")
        except Exception:
            pass
        return False


def main():
    """Main entry point for hook client."""
    import argparse
    import time

    parser = argparse.ArgumentParser(description="Claude World Hook Client")
    parser.add_argument("hook_type", help="Type of hook (PreToolUse, PostToolUse, etc.)")
    parser.add_argument("--input", "-i", help="JSON input from stdin or file")

    args = parser.parse_args()

    # Read input from stdin if available
    if not sys.stdin.isatty():
        input_data = sys.stdin.read()
    elif args.input:
        input_data = args.input
    else:
        input_data = "{}"

    try:
        hook_data = json.loads(input_data) if input_data.strip() else {}
    except json.JSONDecodeError:
        hook_data = {}

    # Map hook types to events
    hook_type = args.hook_type.lower()
    timestamp = time.time()

    # Extract session_id if available (helps identify main vs subagent)
    session_id = hook_data.get("session_id", "")

    if hook_type == "pretooluse":
        event = {
            "type": "TOOL_START",
            "timestamp": timestamp,
            "payload": {
                "tool_name": hook_data.get("tool_name", "unknown"),
                "tool_input": hook_data.get("tool_input", {}),
                "tool_use_id": hook_data.get("tool_use_id", f"tool-{timestamp}"),
                "session_id": session_id,
            },
        }
    elif hook_type == "posttooluse":
        event = {
            "type": "TOOL_COMPLETE",
            "timestamp": timestamp,
            "payload": {
                "tool_name": hook_data.get("tool_name", "unknown"),
                "tool_response": hook_data.get("tool_response", ""),
                "session_id": session_id,
            },
        }
    elif hook_type == "sessionstart":
        event = {
            "type": "SESSION_START",
            "timestamp": timestamp,
            "payload": {
                "source": hook_data.get("source", "startup"),
            },
        }
    elif hook_type == "stop":
        event = {
            "type": "SESSION_END",
            "timestamp": timestamp,
            "payload": {},
        }
    elif hook_type == "subagentspawn" or hook_type == "subagentstart":
        event = {
            "type": "AGENT_SPAWN",
            "timestamp": timestamp,
            "payload": {
                "agent_id": hook_data.get("agent_id", f"agent-{timestamp}"),
                "agent_type": hook_data.get("agent_type", "general"),
                "description": hook_data.get("description", ""),
                "session_id": session_id,
            },
        }
    elif hook_type == "subagentstop":
        event = {
            "type": "AGENT_COMPLETE",
            "timestamp": timestamp,
            "payload": {
                "agent_id": hook_data.get("agent_id", ""),
                "success": hook_data.get("success", True),
                "session_id": session_id,
            },
        }
    elif hook_type == "userpromptsubmit":
        event = {
            "type": "USER_PROMPT",
            "timestamp": timestamp,
            "payload": {
                "prompt": hook_data.get("prompt", ""),
            },
        }
    else:
        print(f"Unknown hook type: {hook_type}", file=sys.stderr)
        sys.exit(1)

    # Send event
    success = asyncio.run(send_event(event))

    if not success:
        # Game not running, silently exit
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
