"""Weather system for environmental effects."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_world.types import GameState


class WeatherSystem:
    """System that manages weather patterns and transitions."""

    def __init__(self, change_interval: float = 300.0):
        """Initialize the weather system.

        Args:
            change_interval: Average seconds between weather changes.
        """
        self._change_interval = change_interval
        self._time_since_change = 0.0
        self._transition_progress = 0.0
        self._target_weather: str | None = None

    def update(self, state: GameState, dt: float) -> None:
        """Update weather conditions.

        Args:
            state: The game state to update.
            dt: Delta time in seconds.
        """
        self._time_since_change += dt

        # Check for random weather change
        if self._time_since_change >= self._change_interval:
            if random.random() < 0.1:  # 10% chance per interval
                self._trigger_weather_change(state)
            self._time_since_change = 0.0

        # Handle weather transition
        if self._target_weather:
            self._transition_progress += dt * 0.1  # Slow transition
            if self._transition_progress >= 1.0:
                state.world.weather.type = self._target_weather
                self._target_weather = None
                self._transition_progress = 0.0

        # Update wind (subtle variations)
        state.world.weather.wind_direction += random.uniform(-1, 1) * dt
        state.world.weather.wind_direction %= 360

        # Update intensity based on weather type
        self._update_intensity(state, dt)

    def _trigger_weather_change(self, state: GameState) -> None:
        """Trigger a weather change.

        Args:
            state: The game state.
        """
        weather_types = ["clear", "cloudy", "rain", "storm"]
        current = state.world.weather.type
        options = [w for w in weather_types if w != current]
        self._target_weather = random.choice(options)
        self._transition_progress = 0.0

    def _update_intensity(self, state: GameState, dt: float) -> None:
        """Update weather intensity.

        Args:
            state: The game state.
            dt: Delta time.
        """
        weather = state.world.weather
        target_intensity = {
            "clear": 0.0,
            "cloudy": 0.3,
            "rain": 0.6,
            "storm": 1.0,
        }.get(weather.type, 0.0)

        # Smooth transition to target
        diff = target_intensity - weather.intensity
        weather.intensity += diff * dt * 0.5

        # Wind speed correlates with intensity
        base_wind = 2.0 + weather.intensity * 8.0
        weather.wind_speed = base_wind + random.uniform(-0.5, 0.5)
