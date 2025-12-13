"""Day/night cycle system."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_world.types import GameState


class DayCycleSystem:
    """System that manages day/night cycle and ambient lighting."""

    def __init__(self, minutes_per_day: float = 10.0):
        """Initialize the day cycle system.

        Args:
            minutes_per_day: Real minutes for one full game day.
        """
        self._minutes_per_day = minutes_per_day
        # Hours per real second = 24 hours / (minutes_per_day * 60 seconds)
        self._hours_per_second = 24.0 / (minutes_per_day * 60.0)

    def update(self, state: GameState, dt: float) -> None:
        """Advance the day/night cycle.

        Args:
            state: The game state to update.
            dt: Delta time in seconds.
        """
        # Advance time
        state.world.time_of_day.hour += dt * self._hours_per_second
        if state.world.time_of_day.hour >= 24.0:
            state.world.time_of_day.hour -= 24.0

        # Update ambient light based on time
        state.world.ambient_light = self._calculate_ambient_light(
            state.world.time_of_day.hour
        )

        # Track session time in progression
        state.progression.total_session_time += dt

    def _calculate_ambient_light(self, hour: float) -> tuple[int, int, int]:
        """Calculate ambient light color based on hour.

        Args:
            hour: Hour of day (0-24).

        Returns:
            RGB tuple for ambient light.
        """
        if 5 <= hour < 7:
            # Dawn - orange/pink tones
            t = (hour - 5) / 2
            r = int(100 + t * 155)
            g = int(80 + t * 140)
            b = int(100 + t * 100)
            return (r, g, b)
        elif 7 <= hour < 17:
            # Day - full brightness
            return (255, 255, 255)
        elif 17 <= hour < 19:
            # Dusk - orange/red tones
            t = (hour - 17) / 2
            r = int(255 - t * 55)
            g = int(200 - t * 100)
            b = int(150 - t * 80)
            return (r, g, b)
        else:
            # Night - blue/dark tones
            return (50, 50, 100)
