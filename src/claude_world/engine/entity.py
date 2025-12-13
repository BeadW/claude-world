"""Entity management for the game."""

from __future__ import annotations

import random
from typing import Optional

from claude_world.types import (
    Entity,
    EntityType,
    AgentEntity,
    AgentActivity,
    AgentMood,
    Position,
    Velocity,
    AnimationState,
    GameState,
)


# World locations where Claude can go for different activities
# Positions are relative offsets from center (0, 0)
# These are thematic for the tropical island world
WORLD_LOCATIONS = {
    "center": Position(0, 0),             # Default idle position - the clearing
    "palm_tree": Position(-70, -15),      # By the palm tree - for reading/resting
    "rock_pile": Position(75, 25),        # Rock pile - for searching under rocks
    "sand_patch": Position(-55, 35),      # Sandy area - for digging/building
    "tide_pool": Position(85, -10),       # By the water - for exploring/fetching
    "hilltop": Position(0, -50),          # Higher ground - for thinking/planning
    "shore": Position(-85, 20),           # Beach shore - for communication (messages in bottles)
    "bushes": Position(60, 45),           # Dense bushes - for searching
}

# Tool → Location mapping (themed for tropical island)
TOOL_LOCATION_MAP = {
    "Read": "palm_tree",          # Reading under a palm tree
    "Write": "sand_patch",        # Writing in the sand
    "Edit": "sand_patch",         # Editing marks in the sand
    "Bash": "rock_pile",          # Bashing rocks together
    "Glob": "bushes",             # Looking through bushes
    "Grep": "rock_pile",          # Searching under rocks
    "WebFetch": "tide_pool",      # Fetching from the tide pool
    "WebSearch": "tide_pool",     # Searching the waters
    "Task": "hilltop",            # Thinking on the hilltop
    "TodoWrite": "sand_patch",    # Planning in the sand
    "AskUserQuestion": "shore",   # Sending message in a bottle
    "NotebookEdit": "palm_tree",  # Working under shade
}


# Spawn point offsets for subagents
SUBAGENT_SPAWN_OFFSETS = [
    (100, 0),
    (-100, 0),
    (50, -50),
    (-50, -50),
    (75, 50),
    (-75, 50),
]


class EntityManager:
    """Manages game entities."""

    def __init__(self, state: GameState):
        """Initialize with a game state.

        Args:
            state: The game state to manage.
        """
        self._state = state
        self._spawn_index = 0

    def get_state(self) -> GameState:
        """Get the current state.

        Returns:
            The current game state.
        """
        return self._state

    def spawn_subagent(
        self,
        agent_id: str,
        agent_type: str,
        description: str,
    ) -> AgentEntity:
        """Spawn a new subagent.

        Args:
            agent_id: Unique identifier for the agent.
            agent_type: Type of agent (Explore, Plan, etc.)
            description: Description of what the agent is doing.

        Returns:
            The created agent entity.
        """
        # Determine spawn position near main agent
        main_pos = self._state.main_agent.position
        offset = SUBAGENT_SPAWN_OFFSETS[self._spawn_index % len(SUBAGENT_SPAWN_OFFSETS)]
        self._spawn_index += 1

        spawn_x = main_pos.x + offset[0]
        spawn_y = main_pos.y + offset[1]

        # Determine sprite based on agent type
        sprite_map = {
            "Explore": "explore_agent",
            "Plan": "plan_agent",
            "general-purpose": "general_agent",
        }
        sprite_id = sprite_map.get(agent_type, "general_agent")

        agent = AgentEntity(
            id=agent_id,
            type=EntityType.SUB_AGENT,
            position=Position(spawn_x, spawn_y),
            velocity=Velocity(0, 0),
            sprite_id=sprite_id,
            animation=AnimationState(current_animation="idle"),
            agent_type=agent_type,
            activity=AgentActivity.EXPLORING,
            mood=AgentMood.FOCUSED,
            linked_claude_id=agent_id,
        )

        self._state.entities[agent_id] = agent
        return agent

    def remove_entity(self, entity_id: str) -> Optional[Entity]:
        """Remove an entity by ID.

        Args:
            entity_id: The ID of the entity to remove.

        Returns:
            The removed entity, or None if not found.
        """
        return self._state.entities.pop(entity_id, None)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID.

        Args:
            entity_id: The ID of the entity to get.

        Returns:
            The entity, or None if not found.
        """
        return self._state.entities.get(entity_id)

    def get_entities_by_type(self, entity_type: EntityType) -> list[Entity]:
        """Get all entities of a specific type.

        Args:
            entity_type: The type of entities to get.

        Returns:
            A list of entities of the specified type.
        """
        return [e for e in self._state.entities.values() if e.type == entity_type]

    def set_main_agent_activity(
        self, activity: AgentActivity, tool_name: str | None = None
    ) -> None:
        """Set the main agent's activity.

        Args:
            activity: The new activity.
            tool_name: The tool currently being used (for verb display).
        """
        import time

        self._state.main_agent.set_activity(activity)
        self._state.main_agent.current_tool = tool_name

        # Track last tool for minimum display time
        if tool_name is not None:
            self._state.main_agent.last_tool = tool_name
            self._state.main_agent.last_tool_time = time.time()

            # Move Claude to the appropriate location for this tool
            self._move_to_tool_location(tool_name)
        elif activity == AgentActivity.IDLE:
            # Return to center when idle
            self._move_to_location("center")

    def _move_to_tool_location(self, tool_name: str) -> None:
        """Move Claude to the location for a specific tool."""
        location_name = TOOL_LOCATION_MAP.get(tool_name, "center")
        self._move_to_location(location_name)

    def _move_to_location(self, location_name: str) -> None:
        """Set Claude's target position to a named location."""
        if location_name not in WORLD_LOCATIONS:
            location_name = "center"

        target = WORLD_LOCATIONS[location_name]
        agent = self._state.main_agent

        # Only start moving if not already at this location
        if agent.current_location != location_name:
            agent.target_position = Position(target.x, target.y)
            agent.is_walking = True
            agent.current_location = location_name

            # Set facing direction based on target
            if target.x > agent.position.x:
                agent.facing_direction = 1
            elif target.x < agent.position.x:
                agent.facing_direction = -1

    def update_entity_position(
        self,
        entity_id: str,
        position: Position,
    ) -> None:
        """Update an entity's position.

        Args:
            entity_id: The ID of the entity to update.
            position: The new position.
        """
        entity = self._state.entities.get(entity_id)
        if entity:
            entity.position = position
