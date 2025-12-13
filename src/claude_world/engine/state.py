"""Game state management."""

from __future__ import annotations

from typing import Callable, Optional

from claude_world.types import GameState


class GameStateManager:
    """Manages the game state with subscription support."""

    def __init__(self, initial_state: GameState):
        """Initialize with an initial game state.

        Args:
            initial_state: The initial game state.
        """
        self._state = initial_state
        self._listeners: list[Callable[[GameState], None]] = []

    def get_state(self) -> GameState:
        """Get the current game state.

        Returns:
            A copy of the current game state.
        """
        return self._state.copy()

    def update_state(self, updater: Callable[[GameState], GameState]) -> None:
        """Update the state using an updater function.

        Args:
            updater: A function that takes the current state and returns the new state.
        """
        self._state = updater(self._state)
        self._notify_listeners()

    def subscribe(self, listener: Callable[[GameState], None]) -> Callable[[], None]:
        """Subscribe to state changes.

        Args:
            listener: A function to call when state changes.

        Returns:
            An unsubscribe function.
        """
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _notify_listeners(self) -> None:
        """Notify all listeners of state change."""
        state_copy = self._state.copy()
        for listener in self._listeners:
            listener(state_copy)
