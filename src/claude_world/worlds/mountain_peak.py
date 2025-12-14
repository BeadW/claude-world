"""Mountain Peak world generation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
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
class MountainPeakConfig:
    """Configuration for mountain peak generation."""

    width: int = 1000
    height: int = 1000
    peak_height: float = 0.9
    peak_center: tuple[float, float] = field(default_factory=lambda: (500.0, 500.0))

    # Terrain settings
    snow_line: float = 0.6  # Height above which snow appears
    tree_line: float = 0.4  # Height above which no trees
    base_radius: float = 400.0  # Mountain base radius

    # Decoration densities (0-1)
    pine_density: float = 0.04
    rock_density: float = 0.06
    crystal_density: float = 0.01

    # Weather
    initial_weather: str = "cloudy"
    initial_time: float = 14.0  # 2 PM

    # Seed for reproducibility (None = random)
    seed: Optional[int] = None


class MountainPeakGenerator:
    """Generates mountain peak terrain and decorations."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize the generator.

        Args:
            seed: Random seed for reproducibility.
        """
        self._seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def generate_terrain(self, config: MountainPeakConfig) -> TerrainData:
        """Generate terrain data for the mountain.

        Args:
            config: Mountain configuration.

        Returns:
            Generated TerrainData.
        """
        if config.seed is not None:
            random.seed(config.seed)
            np.random.seed(config.seed)

        # Grid size (divided by 10 for coarser resolution)
        grid_w = config.width // 10
        grid_h = config.height // 10

        # Create heightmap
        heightmap = self._generate_heightmap(config, grid_w, grid_h)

        # Create tile map
        tiles = self._generate_tiles(heightmap, config, grid_w, grid_h)

        # Generate decorations
        decorations = self._generate_decorations(tiles, heightmap, config, grid_w, grid_h)

        return TerrainData(
            heightmap=heightmap,
            tiles=tiles,
            decorations=decorations,
        )

    def _generate_heightmap(
        self,
        config: MountainPeakConfig,
        grid_w: int,
        grid_h: int,
    ) -> np.ndarray:
        """Generate heightmap for mountain terrain.

        Args:
            config: Mountain configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            Heightmap array.
        """
        heightmap = np.zeros((grid_h, grid_w), dtype=np.float32)

        cx = config.peak_center[0] / 10
        cy = config.peak_center[1] / 10
        radius = config.base_radius / 10

        for y in range(grid_h):
            for x in range(grid_w):
                # Distance from center
                dx = x - cx
                dy = y - cy
                dist = np.sqrt(dx * dx + dy * dy)

                # Mountain shape - conical with noise
                if dist < radius:
                    t = dist / radius
                    # Conical shape with smooth edges
                    height = config.peak_height * (1 - t) * (1 - t * 0.5)

                    # Add ridges (radial noise)
                    angle = np.arctan2(dy, dx)
                    ridge_noise = 0.1 * np.sin(angle * 8) * (1 - t)
                    height += ridge_noise

                    # Add random variation
                    height += random.uniform(-0.05, 0.05)
                    heightmap[y, x] = max(0, height)
                else:
                    # Valley/flatlands
                    falloff = (dist - radius) / 20
                    heightmap[y, x] = max(-0.1, 0.05 - falloff * 0.1)

        return heightmap

    def _generate_tiles(
        self,
        heightmap: np.ndarray,
        config: MountainPeakConfig,
        grid_w: int,
        grid_h: int,
    ) -> np.ndarray:
        """Generate tile types based on heightmap.

        Args:
            heightmap: The heightmap.
            config: Mountain configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            Tile type array.
        """
        tiles = np.zeros((grid_h, grid_w), dtype=np.uint8)

        for y in range(grid_h):
            for x in range(grid_w):
                height = heightmap[y, x]

                if height < 0:
                    # Frozen lake/water at base
                    tiles[y, x] = TerrainType.SHALLOW_WATER.value
                elif height < 0.1:
                    # Dirt/gravel at base
                    tiles[y, x] = TerrainType.DIRT.value
                elif height < config.tree_line:
                    # Grass/meadow below tree line
                    tiles[y, x] = TerrainType.GRASS.value
                elif height < config.snow_line:
                    # Rocky terrain above tree line
                    tiles[y, x] = TerrainType.ROCK.value
                else:
                    # Snow at the peak (use SAND as snow)
                    tiles[y, x] = TerrainType.SAND.value  # Will be rendered as snow

        return tiles

    def _generate_decorations(
        self,
        tiles: np.ndarray,
        heightmap: np.ndarray,
        config: MountainPeakConfig,
        grid_w: int,
        grid_h: int,
    ) -> list[dict]:
        """Generate decorations (pine trees, rocks, crystals).

        Args:
            tiles: The tile map.
            heightmap: The heightmap.
            config: Mountain configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            List of decoration dictionaries.
        """
        decorations = []

        for y in range(grid_h):
            for x in range(grid_w):
                tile = tiles[y, x]
                height = heightmap[y, x]

                # Pine trees on grass (below tree line)
                if tile == TerrainType.GRASS.value:
                    if random.random() < config.pine_density:
                        decorations.append({
                            "type": "pine_tree",
                            "x": x * 10 + random.uniform(0, 10),
                            "y": y * 10 + random.uniform(0, 10),
                            "scale": random.uniform(0.7, 1.3),
                            "variant": random.randint(0, 2),
                        })

                # Rocks on rocky terrain and snow
                if tile in [TerrainType.ROCK.value, TerrainType.SAND.value]:
                    if random.random() < config.rock_density:
                        decorations.append({
                            "type": "mountain_rock",
                            "x": x * 10 + random.uniform(0, 10),
                            "y": y * 10 + random.uniform(0, 10),
                            "scale": random.uniform(0.5, 2.0),
                            "variant": random.randint(0, 3),
                            "snow_covered": height > config.snow_line,
                        })

                # Crystals in rocky areas (rare)
                if tile == TerrainType.ROCK.value:
                    if random.random() < config.crystal_density:
                        decorations.append({
                            "type": "crystal",
                            "x": x * 10 + random.uniform(0, 10),
                            "y": y * 10 + random.uniform(0, 10),
                            "scale": random.uniform(0.3, 0.8),
                            "color": random.choice(["blue", "purple", "cyan"]),
                        })

        return decorations


# World locations for the mountain (used for tool-based movement)
MOUNTAIN_WORLD_LOCATIONS = {
    "peak": Position(0, -60),           # Mountain peak - thinking/planning
    "cave": Position(-120, 40),         # Cave entrance - reading/searching
    "cliff_edge": Position(100, -30),   # Cliff edge - writing/building
    "frozen_lake": Position(-80, 80),   # Frozen lake - fetching
    "campfire": Position(60, 60),       # Campfire - resting
    "lookout": Position(140, 10),       # Lookout point - exploring
    "crystal_cave": Position(-140, -20), # Crystal cave - searching
    "center": Position(0, 0),           # Center
}


def create_mountain_peak(
    config: Optional[MountainPeakConfig] = None,
) -> GameState:
    """Create a complete game state with mountain peak world.

    Args:
        config: Optional configuration. Defaults to standard settings.

    Returns:
        Complete GameState.
    """
    if config is None:
        config = MountainPeakConfig()

    # Generate terrain
    generator = MountainPeakGenerator(seed=config.seed)
    terrain = generator.generate_terrain(config)

    # Create world state
    world = WorldState(
        name="mountain-peak",
        width=config.width,
        height=config.height,
        terrain=terrain,
        water_offset=0.0,
        weather=WeatherState(
            type=config.initial_weather,
            intensity=0.3,
            wind_direction=180.0,
            wind_speed=15.0,
        ),
        time_of_day=TimeOfDay(hour=config.initial_time),
        ambient_light=(220, 230, 255),  # Slightly blue-tinted for mountain
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
            x=config.peak_center[0],
            y=config.peak_center[1],
            target="main_agent",
        ),
        session_active=False,
    )
