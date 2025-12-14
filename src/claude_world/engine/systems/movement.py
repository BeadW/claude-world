"""Movement system for entity physics."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_world.types import GameState

from claude_world.types import EntityType, Position


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
            # Subagents get autonomous wandering behavior
            if entity.type == EntityType.SUB_AGENT:
                self._update_subagent_wandering(entity, main, dt)
                self._update_agent_movement(entity, dt)

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

    def _update_subagent_wandering(self, agent, main_agent, dt: float) -> None:
        """Give subagents autonomous wandering behavior around the main agent.

        Subagents will periodically pick a new target location near the main
        agent and walk there, making them appear to be actively exploring.
        """
        # Skip if already walking to a target
        if agent.is_walking and agent.target_position is not None:
            return

        # Random chance to start wandering each frame (average ~2-4 seconds idle)
        if random.random() > dt * 0.4:  # ~40% chance per second
            return

        # Pick a random offset from the main agent's position
        # Subagents wander in a 120px radius around main Claude
        wander_radius = 120
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(30, wander_radius)

        target_x = main_agent.position.x + math.cos(angle) * distance
        target_y = main_agent.position.y + math.sin(angle) * distance

        # Clamp to reasonable bounds (stay on screen area)
        target_x = max(-180, min(180, target_x))
        target_y = max(-100, min(100, target_y))

        # Set the target and start walking
        agent.target_position = Position(target_x, target_y)
        agent.is_walking = True
        agent.move_speed = random.uniform(60, 100)  # Subagents move a bit slower

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
