"""Animation system for sprite animations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_world.types import GameState


class AnimationSystem:
    """System that advances entity animations over time."""

    def update(self, state: GameState, dt: float) -> None:
        """Update all entity animations.

        Args:
            state: The game state to update.
            dt: Delta time in seconds.
        """
        # Update main agent animation (simplified without sprite lookup)
        main = state.main_agent
        if main.animation.playing:
            main.animation.frame_time += dt * main.animation.speed

        # Update other entity animations
        for entity in state.entities.values():
            if entity.animation.playing:
                entity.animation.frame_time += dt * entity.animation.speed

        # Update water animation offset
        state.world.water_offset += dt * 0.5  # Slow wave motion
        if state.world.water_offset > 1.0:
            state.world.water_offset -= 1.0
