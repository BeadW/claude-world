"""Digital Grid world generation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import numpy as np

from claude_world.types import (
    AgentActivity,
    AgentEntity,
    AgentMood,
    AnimationState,
    Camera,
    EntityType,
    GameState,
    Position,
    Progression,
    Resources,
    TerrainData,
    TerrainType,
    TimeOfDay,
    Velocity,
    WeatherState,
    WorldState,
)


@dataclass
class DigitalGridConfig:
    """Configuration for digital grid generation."""

    width: int = 1000
    height: int = 1000

    # Grid settings
    grid_spacing: int = 50  # Distance between grid lines
    node_density: float = 0.15  # Density of circuit nodes
    data_stream_count: int = 8  # Number of data streams

    # Decoration densities (0-1)
    terminal_density: float = 0.02
    server_density: float = 0.015
    antenna_density: float = 0.01

    # Weather
    initial_weather: str = "clear"
    initial_time: float = 22.0  # 10 PM for neon glow

    # Seed for reproducibility (None = random)
    seed: Optional[int] = None


class DigitalGridGenerator:
    """Generates digital grid terrain and decorations."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize the generator.

        Args:
            seed: Random seed for reproducibility.
        """
        self._seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def generate_terrain(self, config: DigitalGridConfig) -> TerrainData:
        """Generate terrain data for the digital grid.

        Args:
            config: Grid configuration.

        Returns:
            Generated TerrainData.
        """
        if config.seed is not None:
            random.seed(config.seed)
            np.random.seed(config.seed)

        # Grid size (divided by 10 for coarser resolution)
        grid_w = config.width // 10
        grid_h = config.height // 10

        # Create heightmap (mostly flat with some variation)
        heightmap = self._generate_heightmap(config, grid_w, grid_h)

        # Create tile map
        tiles = self._generate_tiles(heightmap, config, grid_w, grid_h)

        # Generate decorations
        decorations = self._generate_decorations(tiles, config, grid_w, grid_h)

        return TerrainData(
            heightmap=heightmap,
            tiles=tiles,
            decorations=decorations,
        )

    def _generate_heightmap(
        self,
        config: DigitalGridConfig,
        grid_w: int,
        grid_h: int,
    ) -> np.ndarray:
        """Generate heightmap for digital terrain.

        Args:
            config: Grid configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            Heightmap array.
        """
        heightmap = np.zeros((grid_h, grid_w), dtype=np.float32)

        # Create subtle platform variations
        for y in range(grid_h):
            for x in range(grid_w):
                # Create circuit board-like stepped platforms
                platform_x = (x * 10) // config.grid_spacing
                platform_y = (y * 10) // config.grid_spacing

                # Hash for consistent platform heights
                platform_hash = (platform_x * 31 + platform_y * 17) % 100
                if platform_hash < 30:
                    heightmap[y, x] = 0.1
                elif platform_hash < 50:
                    heightmap[y, x] = 0.2
                elif platform_hash < 60:
                    heightmap[y, x] = 0.3
                else:
                    heightmap[y, x] = 0.0

        return heightmap

    def _generate_tiles(
        self,
        heightmap: np.ndarray,
        config: DigitalGridConfig,
        grid_w: int,
        grid_h: int,
    ) -> np.ndarray:
        """Generate tile types based on grid pattern.

        Args:
            heightmap: The heightmap.
            config: Grid configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            Tile type array.
        """
        tiles = np.zeros((grid_h, grid_w), dtype=np.uint8)

        for y in range(grid_h):
            for x in range(grid_w):
                world_x = x * 10
                world_y = y * 10

                # Grid lines
                on_grid_line = (
                    world_x % config.grid_spacing < 10
                    or world_y % config.grid_spacing < 10
                )

                # Circuit node intersections
                on_intersection = (
                    world_x % config.grid_spacing < 10
                    and world_y % config.grid_spacing < 10
                )

                height = heightmap[y, x]

                if on_intersection:
                    # Intersection nodes - use ROCK for bright circuit nodes
                    tiles[y, x] = TerrainType.ROCK.value
                elif on_grid_line:
                    # Grid lines - use DIRT for circuit traces
                    tiles[y, x] = TerrainType.DIRT.value
                elif height > 0.2:
                    # Elevated platforms - use GRASS for platform surface
                    tiles[y, x] = TerrainType.GRASS.value
                elif height > 0.1:
                    # Low platforms - use SAND for secondary platforms
                    tiles[y, x] = TerrainType.SAND.value
                else:
                    # Base grid floor - use DEEP_WATER for dark floor
                    tiles[y, x] = TerrainType.DEEP_WATER.value

        return tiles

    def _generate_decorations(
        self,
        tiles: np.ndarray,
        config: DigitalGridConfig,
        grid_w: int,
        grid_h: int,
    ) -> list[dict]:
        """Generate decorations (terminals, servers, antennas).

        Args:
            tiles: The tile map.
            config: Grid configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            List of decoration dictionaries.
        """
        decorations = []

        # Add data streams
        for i in range(config.data_stream_count):
            start_x = random.uniform(100, config.width - 100)
            start_y = random.uniform(100, config.height - 100)
            angle = random.uniform(0, 2 * np.pi)
            length = random.uniform(100, 300)

            decorations.append({
                "type": "data_stream",
                "x": start_x,
                "y": start_y,
                "angle": angle,
                "length": length,
                "color": random.choice(["cyan", "magenta", "green", "yellow"]),
                "speed": random.uniform(0.5, 2.0),
            })

        for y in range(grid_h):
            for x in range(grid_w):
                tile = tiles[y, x]

                # Terminals on platforms
                if tile == TerrainType.GRASS.value:
                    if random.random() < config.terminal_density:
                        decorations.append({
                            "type": "terminal",
                            "x": x * 10 + random.uniform(2, 8),
                            "y": y * 10 + random.uniform(2, 8),
                            "scale": random.uniform(0.8, 1.2),
                            "screen_color": random.choice(["green", "amber", "blue"]),
                            "active": random.random() > 0.3,
                        })

                # Servers on secondary platforms
                if tile == TerrainType.SAND.value:
                    if random.random() < config.server_density:
                        decorations.append({
                            "type": "server_rack",
                            "x": x * 10 + random.uniform(2, 8),
                            "y": y * 10 + random.uniform(2, 8),
                            "scale": random.uniform(0.7, 1.3),
                            "led_color": random.choice(["green", "blue", "red"]),
                            "blink_rate": random.uniform(0.5, 2.0),
                        })

                # Antennas at intersections
                if tile == TerrainType.ROCK.value:
                    if random.random() < config.antenna_density:
                        decorations.append({
                            "type": "antenna",
                            "x": x * 10 + 5,
                            "y": y * 10 + 5,
                            "scale": random.uniform(1.0, 2.0),
                            "signal_strength": random.uniform(0.3, 1.0),
                        })

        # Add floating data particles
        for _ in range(50):
            decorations.append({
                "type": "data_particle",
                "x": random.uniform(0, config.width),
                "y": random.uniform(0, config.height),
                "size": random.uniform(2, 6),
                "color": random.choice(["cyan", "magenta", "white"]),
                "float_speed": random.uniform(0.2, 1.0),
            })

        return decorations


# World locations for the digital grid (used for tool-based movement)
DIGITAL_GRID_LOCATIONS = {
    "mainframe": Position(0, -50),         # Central mainframe - thinking/planning
    "data_center": Position(-100, 30),     # Data center - reading/searching
    "code_forge": Position(90, -40),       # Code forge - writing/building
    "network_hub": Position(-70, 70),      # Network hub - fetching
    "power_core": Position(50, 50),        # Power core - resting
    "scanner_array": Position(120, 20),    # Scanner array - exploring
    "archive": Position(-130, -30),        # Archive - searching
    "center": Position(0, 0),              # Center
}


def create_digital_grid(
    config: Optional[DigitalGridConfig] = None,
) -> GameState:
    """Create a complete game state with digital grid world.

    Args:
        config: Optional configuration. Defaults to standard settings.

    Returns:
        Complete GameState.
    """
    if config is None:
        config = DigitalGridConfig()

    # Generate terrain
    generator = DigitalGridGenerator(seed=config.seed)
    terrain = generator.generate_terrain(config)

    # Create world state
    world = WorldState(
        name="digital-grid",
        width=config.width,
        height=config.height,
        terrain=terrain,
        water_offset=0.0,
        weather=WeatherState(
            type=config.initial_weather,
            intensity=0.0,
            wind_direction=0.0,
            wind_speed=0.0,
        ),
        time_of_day=TimeOfDay(hour=config.initial_time),
        ambient_light=(20, 30, 50),  # Dark blue-tinted for neon contrast
    )

    # Create main agent at center
    main_agent = AgentEntity(
        id="main_agent",
        type=EntityType.MAIN_AGENT,
        position=Position(0.0, 0.0),
        velocity=Velocity(0.0, 0.0),
        sprite_id="claude_main",
        animation=AnimationState(current_animation="idle"),
        agent_type="main",
        activity=AgentActivity.IDLE,
        mood=AgentMood.NEUTRAL,
    )

    # Create game state
    return GameState(
        world=world,
        entities={main_agent.id: main_agent},
        main_agent=main_agent,
        particles=[],
        resources=Resources(),
        progression=Progression(),
        camera=Camera(
            x=config.width / 2,
            y=config.height / 2,
            target="main_agent",
        ),
        session_active=False,
    )
