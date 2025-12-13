#!/usr/bin/env python3
"""Game client for querying Claude World game state."""

import asyncio
import json
import sys
import tempfile
from pathlib import Path


async def send_message(message: dict) -> dict:
    """Send a message to the Claude World game.

    Args:
        message: Message dictionary to send.

    Returns:
        Dictionary with response or error.
    """
    socket_path = Path(tempfile.gettempdir()) / "claude_world.sock"

    if not socket_path.exists():
        return {"error": "Game not running"}

    try:
        reader, writer = await asyncio.open_unix_connection(
            path=str(socket_path)
        )

        data = json.dumps(message).encode("utf-8")

        # Send length prefix + data
        writer.write(len(data).to_bytes(4, "big"))
        writer.write(data)
        await writer.drain()

        # Read response length
        length_data = await reader.read(4)
        if not length_data:
            return {"error": "No response"}

        length = int.from_bytes(length_data, "big")

        # Read response
        response_data = await reader.read(length)
        writer.close()
        await writer.wait_closed()

        return json.loads(response_data.decode("utf-8"))

    except (ConnectionRefusedError, FileNotFoundError):
        return {"error": "Cannot connect to game"}
    except json.JSONDecodeError:
        return {"error": "Invalid response"}


async def query_game(query_type: str) -> dict:
    """Query the Claude World game for state information.

    Args:
        query_type: Type of query (status, skills, achievements).

    Returns:
        Dictionary with game state or error.
    """
    return await send_message({"type": "QUERY", "query": query_type})


async def send_action(action_type: str, data: dict) -> dict:
    """Send an action to modify game state.

    Args:
        action_type: Type of action (upgrade, etc.).
        data: Action parameters.

    Returns:
        Dictionary with result or error.
    """
    return await send_message({"type": "ACTION", "action": action_type, "data": data})


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Claude World Game Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Query commands
    query_parser = subparsers.add_parser("status", help="Get game status")
    query_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    skills_parser = subparsers.add_parser("skills", help="Get skill levels")
    skills_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    ach_parser = subparsers.add_parser("achievements", help="Get achievements")
    ach_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # Action commands
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade a skill")
    upgrade_parser.add_argument(
        "skill",
        choices=["reading", "writing", "searching", "building"],
        help="Skill to upgrade",
    )
    upgrade_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Handle queries
    if args.command in ["status", "skills", "achievements"]:
        result = asyncio.run(query_game(args.command))

        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                print(f"Error: {result['error']}")
                sys.exit(1)

            if args.command == "status":
                print(f"Level: {result.get('level', 1)}")
                print(f"XP: {result.get('experience', 0)}/{result.get('xp_to_next', 100)}")
                print(f"Tokens: {result.get('tokens', 0)}")
                print(f"Connections: {result.get('connections', 0)}")
                print(f"Activity: {result.get('activity', 'idle')}")
                print(f"Tools Used: {result.get('tools_used', 0)}")
                print(f"Agents Spawned: {result.get('agents_spawned', 0)}")
                print(f"Time: {result.get('time_of_day', 'day')}")

            elif args.command == "skills":
                print("Skills:")
                print(f"  Reading: {result.get('reading', 1)}")
                print(f"  Writing: {result.get('writing', 1)}")
                print(f"  Searching: {result.get('searching', 1)}")
                print(f"  Building: {result.get('building', 1)}")
                print(f"\nTokens available: {result.get('tokens', 0)}")

            elif args.command == "achievements":
                unlocked = result.get("unlocked", [])
                print(f"Achievements Unlocked: {len(unlocked)}")
                for ach in unlocked:
                    print(f"  - {ach}")
                print(f"\nTotal Tools Used: {result.get('total_tools', 0)}")
                print(f"Total Agents Spawned: {result.get('total_agents', 0)}")

    # Handle actions
    elif args.command == "upgrade":
        result = asyncio.run(send_action("upgrade", {"skill": args.skill}))

        if getattr(args, "json", False):
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                print(f"Error: {result['error']}")
                sys.exit(1)

            if result.get("success"):
                print(result.get("message", "Upgrade successful!"))
            else:
                print(f"Failed: {result.get('message', 'Unknown error')}")
                sys.exit(1)


if __name__ == "__main__":
    main()
