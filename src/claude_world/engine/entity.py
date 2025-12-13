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
