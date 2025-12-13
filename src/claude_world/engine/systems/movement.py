"""Movement system for entity physics."""

from __future__ import annotations

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
        # Update main agent
        main = state.main_agent
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
