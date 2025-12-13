"""Tropical island world generation."""

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
class TropicalIslandConfig:
    """Configuration for tropical island generation."""

    width: int = 1000
    height: int = 1000
    island_radius: float = 350.0
    island_center: tuple[float, float] = field(default_factory=lambda: (500.0, 500.0))

    # Terrain settings
    sand_width: float = 30.0  # Width of sand beach
    water_depth: float = 50.0  # Depth of deep water zone

    # Decoration densities (0-1)
    palm_density: float = 0.05
    rock_density: float = 0.02
    flower_density: float = 0.03

    # Weather
    initial_weather: str = "clear"
    initial_time: float = 10.0  # 10 AM

    # Seed for reproducibility (None = random)
    seed: Optional[int] = None


class TropicalIslandGenerator:
    """Generates tropical island terrain and decorations."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize the generator.

        Args:
            seed: Random seed for reproducibility.
        """
        self._seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def generate_terrain(self, config: TropicalIslandConfig) -> TerrainData:
        """Generate terrain data for the island.

        Args:
            config: Island configuration.

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
        decorations = self._generate_decorations(tiles, config, grid_w, grid_h)

        return TerrainData(
            heightmap=heightmap,
            tiles=tiles,
            decorations=decorations,
        )

    def _generate_heightmap(
        self,
        config: TropicalIslandConfig,
        grid_w: int,
        grid_h: int,
    ) -> np.ndarray:
        """Generate heightmap using distance from center.

        Args:
            config: Island configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            Heightmap array.
        """
        heightmap = np.zeros((grid_h, grid_w), dtype=np.float32)

        cx = config.island_center[0] / 10
        cy = config.island_center[1] / 10
        radius = config.island_radius / 10

        for y in range(grid_h):
            for x in range(grid_w):
                # Distance from center
                dx = x - cx
                dy = y - cy
                dist = np.sqrt(dx * dx + dy * dy)

                # Height based on distance (higher in center)
                if dist < radius:
                    # Smooth falloff from center
                    t = dist / radius
                    height = (1 - t * t) * 0.5  # Quadratic falloff

                    # Add some noise
                    height += random.uniform(-0.05, 0.05)
                    heightmap[y, x] = max(0, height)
                else:
                    # Below sea level
                    heightmap[y, x] = -0.1

        return heightmap

    def _generate_tiles(
        self,
        heightmap: np.ndarray,
        config: TropicalIslandConfig,
        grid_w: int,
        grid_h: int,
    ) -> np.ndarray:
        """Generate tile types based on heightmap.

        Args:
            heightmap: The heightmap.
            config: Island configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            Tile type array.
        """
        tiles = np.zeros((grid_h, grid_w), dtype=np.uint8)

        for y in range(grid_h):
            for x in range(grid_w):
                height = heightmap[y, x]

                if height < -0.05:
                    tiles[y, x] = TerrainType.DEEP_WATER.value
                elif height < 0.0:
                    tiles[y, x] = TerrainType.SHALLOW_WATER.value
                elif height < 0.1:
                    tiles[y, x] = TerrainType.SAND.value
                elif height < 0.3:
                    tiles[y, x] = TerrainType.GRASS.value
                else:
                    # Higher areas might have rocks/dirt
                    if random.random() < 0.3:
                        tiles[y, x] = TerrainType.ROCK.value
                    else:
                        tiles[y, x] = TerrainType.GRASS.value

        return tiles

    def _generate_decorations(
        self,
        tiles: np.ndarray,
        config: TropicalIslandConfig,
        grid_w: int,
        grid_h: int,
    ) -> list[dict]:
        """Generate decorations (palm trees, rocks, flowers).

        Args:
            tiles: The tile map.
            config: Island configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            List of decoration dictionaries.
        """
        decorations = []

        for y in range(grid_h):
            for x in range(grid_w):
                tile = tiles[y, x]

                # Only place decorations on land
                if tile == TerrainType.GRASS.value:
                    # Palm trees
                    if random.random() < config.palm_density:
                        decorations.append({
                            "type": "palm_tree",
                            "x": x * 10 + random.uniform(0, 10),
                            "y": y * 10 + random.uniform(0, 10),
                            "scale": random.uniform(0.8, 1.2),
                            "variant": random.randint(0, 2),
                        })

                    # Flowers
                    if random.random() < config.flower_density:
                        decorations.append({
                            "type": "flower",
                            "x": x * 10 + random.uniform(0, 10),
                            "y": y * 10 + random.uniform(0, 10),
                            "scale": random.uniform(0.5, 1.0),
                            "color": random.choice(["red", "yellow", "pink", "white"]),
                        })

                elif tile == TerrainType.SAND.value:
                    # Rocks on beach
                    if random.random() < config.rock_density:
                        decorations.append({
                            "type": "rock",
                            "x": x * 10 + random.uniform(0, 10),
                            "y": y * 10 + random.uniform(0, 10),
                            "scale": random.uniform(0.5, 1.5),
                            "variant": random.randint(0, 3),
                        })

        return decorations


def create_tropical_island(
    config: Optional[TropicalIslandConfig] = None,
) -> GameState:
    """Create a complete game state with tropical island world.

    Args:
        config: Optional configuration. Defaults to standard settings.

    Returns:
        Complete GameState.
    """
    if config is None:
        config = TropicalIslandConfig()

    # Generate terrain
    generator = TropicalIslandGenerator(seed=config.seed)
    terrain = generator.generate_terrain(config)

    # Create world state
    world = WorldState(
        name="tropical-island",
        width=config.width,
        height=config.height,
        terrain=terrain,
        water_offset=0.0,
        weather=WeatherState(
            type=config.initial_weather,
            intensity=0.0,
            wind_direction=45.0,
            wind_speed=5.0,
        ),
        time_of_day=TimeOfDay(hour=config.initial_time),
        ambient_light=(255, 255, 255),
    )

    # Create main agent at center of island
    main_agent = AgentEntity(
        id="main_agent",
        type=EntityType.MAIN_AGENT,
        position=Position(
            config.island_center[0],
            config.island_center[1],
        ),
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
            x=config.island_center[0],
            y=config.island_center[1],
            target="main_agent",
        ),
        session_active=False,
    )
