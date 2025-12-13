"""World loading and management."""

from __future__ import annotations

from typing import Any, Dict, Optional

from claude_world.types import GameState

from .tropical_island import TropicalIslandConfig, create_tropical_island


class WorldLoader:
    """Loads and manages game worlds."""

    def __init__(self):
        """Initialize the world loader."""
        self._world_factories = {
            "tropical-island": self._create_tropical_island,
        }
        self._configs: Dict[str, Any] = {
            "tropical-island": TropicalIslandConfig(),
        }

    @property
    def available_worlds(self) -> list[str]:
        """Get list of available world names.

        Returns:
            List of world names.
        """
        return list(self._world_factories.keys())

    def load(
        self,
        world_name: str,
        config: Optional[Any] = None,
    ) -> GameState:
        """Load a world by name.

        Args:
            world_name: Name of the world to load.
            config: Optional configuration override.

        Returns:
            GameState for the world.

        Raises:
            ValueError: If world name is not found.
        """
        if world_name not in self._world_factories:
            raise ValueError(
                f"Unknown world: {world_name}. "
                f"Available: {', '.join(self.available_worlds)}"
            )

        factory = self._world_factories[world_name]
        return factory(config)

    def get_config(self, world_name: str) -> Any:
        """Get the configuration for a world.

        Args:
            world_name: Name of the world.

        Returns:
            World configuration.

        Raises:
            ValueError: If world name is not found.
        """
        if world_name not in self._configs:
            raise ValueError(f"Unknown world: {world_name}")

        return self._configs[world_name]

    def register_world(
        self,
        name: str,
        factory: callable,
        config: Any,
    ) -> None:
        """Register a new world.

        Args:
            name: World name.
            factory: Factory function that creates GameState.
            config: Default configuration for the world.
        """
        self._world_factories[name] = factory
        self._configs[name] = config

    def _create_tropical_island(
        self,
        config: Optional[TropicalIslandConfig] = None,
    ) -> GameState:
        """Create tropical island world.

        Args:
            config: Optional configuration.

        Returns:
            GameState for tropical island.
        """
        return create_tropical_island(config)
