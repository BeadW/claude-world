"""Movement system for entity physics."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_world.types import GameState


class MovementSystem:
    """System that handles entity movement based on velocity."""

    def __init__(self, friction: float = 0.95):
        """Initialize the movement system.

        Args:
            friction: Friction coefficient applied each frame.
        """
        self._friction = friction

    def update(self, state: GameState, dt: float) -> None:
        """Update entity positions based on velocity.

        Args:
            state: The game state to update.
            dt: Delta time in seconds.
        """
        # Update main agent with target-based movement
        main = state.main_agent
        self._update_agent_movement(main, dt)

        # Apply velocity (for any remaining physics-based movement)
        main.position.x += main.velocity.x * dt
        main.position.y += main.velocity.y * dt
        main.velocity.x *= self._friction
        main.velocity.y *= self._friction

        # Update other entities
        for entity in state.entities.values():
            entity.position.x += entity.velocity.x * dt
            entity.position.y += entity.velocity.y * dt
            entity.velocity.x *= self._friction
            entity.velocity.y *= self._friction

        # Update particles
        for particle in state.particles:
            particle.position.x += particle.velocity.x * dt
            particle.position.y += particle.velocity.y * dt
            particle.lifetime -= dt

        # Remove dead particles
        state.particles = [p for p in state.particles if not p.is_dead]

    def _update_agent_movement(self, agent, dt: float) -> None:
        """Update agent movement toward target position."""
        if not agent.is_walking or agent.target_position is None:
            return

        # Calculate direction to target
        dx = agent.target_position.x - agent.position.x
        dy = agent.target_position.y - agent.position.y
        distance = math.sqrt(dx * dx + dy * dy)

        # Arrival threshold
        arrival_distance = 5.0

        if distance <= arrival_distance:
            # Arrived at destination
            agent.position.x = agent.target_position.x
            agent.position.y = agent.target_position.y
            agent.is_walking = False
            agent.target_position = None
        else:
            # Move toward target
            move_distance = agent.move_speed * dt
            if move_distance > distance:
                move_distance = distance

            # Normalize direction and apply movement
            agent.position.x += (dx / distance) * move_distance
            agent.position.y += (dy / distance) * move_distance

            # Update facing direction
            if dx > 0:
                agent.facing_direction = 1
            elif dx < 0:
                agent.facing_direction = -1
