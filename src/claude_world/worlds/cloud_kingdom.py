"""Cloud Kingdom world generation."""

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
class CloudKingdomConfig:
    """Configuration for cloud kingdom generation."""

    width: int = 1000
    height: int = 1000

    # Platform settings
    main_platform_radius: float = 150.0
    platform_count: int = 12
    platform_min_radius: float = 30.0
    platform_max_radius: float = 80.0

    # Decoration densities (0-1)
    crystal_pillar_density: float = 0.03
    cloud_puff_density: float = 0.08
    rainbow_bridge_count: int = 4
    floating_island_count: int = 6

    # Weather
    initial_weather: str = "clear"
    initial_time: float = 10.0  # 10 AM for bright sky

    # Seed for reproducibility (None = random)
    seed: Optional[int] = None


class CloudKingdomGenerator:
    """Generates cloud kingdom terrain and decorations."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize the generator.

        Args:
            seed: Random seed for reproducibility.
        """
        self._seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def generate_terrain(self, config: CloudKingdomConfig) -> TerrainData:
        """Generate terrain data for the cloud kingdom.

        Args:
            config: Kingdom configuration.

        Returns:
            Generated TerrainData.
        """
        if config.seed is not None:
            random.seed(config.seed)
            np.random.seed(config.seed)

        # Grid size (divided by 10 for coarser resolution)
        grid_w = config.width // 10
        grid_h = config.height // 10

        # Generate floating platforms
        platforms = self._generate_platforms(config)

        # Create heightmap
        heightmap = self._generate_heightmap(config, platforms, grid_w, grid_h)

        # Create tile map
        tiles = self._generate_tiles(heightmap, config, grid_w, grid_h)

        # Generate decorations
        decorations = self._generate_decorations(tiles, platforms, config, grid_w, grid_h)

        return TerrainData(
            heightmap=heightmap,
            tiles=tiles,
            decorations=decorations,
        )

    def _generate_platforms(
        self,
        config: CloudKingdomConfig,
    ) -> list[dict]:
        """Generate floating platform positions.

        Args:
            config: Kingdom configuration.

        Returns:
            List of platform dictionaries.
        """
        platforms = []

        # Main central platform
        platforms.append({
            "x": config.width / 2,
            "y": config.height / 2,
            "radius": config.main_platform_radius,
            "height": 0.5,
        })

        # Surrounding floating platforms
        for i in range(config.platform_count):
            angle = (i / config.platform_count) * 2 * np.pi
            distance = random.uniform(200, 400)
            radius = random.uniform(config.platform_min_radius, config.platform_max_radius)

            platforms.append({
                "x": config.width / 2 + np.cos(angle) * distance,
                "y": config.height / 2 + np.sin(angle) * distance,
                "radius": radius,
                "height": random.uniform(0.3, 0.7),
            })

        return platforms

    def _generate_heightmap(
        self,
        config: CloudKingdomConfig,
        platforms: list[dict],
        grid_w: int,
        grid_h: int,
    ) -> np.ndarray:
        """Generate heightmap for cloud terrain.

        Args:
            config: Kingdom configuration.
            platforms: List of platform positions.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            Heightmap array.
        """
        heightmap = np.zeros((grid_h, grid_w), dtype=np.float32)

        for y in range(grid_h):
            for x in range(grid_w):
                world_x = x * 10
                world_y = y * 10

                # Check each platform
                max_height = -1.0  # Sky/void below platforms
                for platform in platforms:
                    dx = world_x - platform["x"]
                    dy = world_y - platform["y"]
                    dist = np.sqrt(dx * dx + dy * dy)

                    if dist < platform["radius"]:
                        # Inside platform - create smooth dome shape
                        t = dist / platform["radius"]
                        height = platform["height"] * (1 - t * t)
                        max_height = max(max_height, height)

                heightmap[y, x] = max_height

        return heightmap

    def _generate_tiles(
        self,
        heightmap: np.ndarray,
        config: CloudKingdomConfig,
        grid_w: int,
        grid_h: int,
    ) -> np.ndarray:
        """Generate tile types based on heightmap.

        Args:
            heightmap: The heightmap.
            config: Kingdom configuration.
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
                    # Sky/void - use DEEP_WATER for sky appearance
                    tiles[y, x] = TerrainType.DEEP_WATER.value
                elif height < 0.2:
                    # Cloud edge - use SHALLOW_WATER for wispy clouds
                    tiles[y, x] = TerrainType.SHALLOW_WATER.value
                elif height < 0.35:
                    # Cloud surface - use SAND for white/cream clouds
                    tiles[y, x] = TerrainType.SAND.value
                elif height < 0.5:
                    # Solid cloud - use GRASS for grassy cloud platforms
                    tiles[y, x] = TerrainType.GRASS.value
                else:
                    # Peak/temple areas - use ROCK for stone structures
                    tiles[y, x] = TerrainType.ROCK.value

        return tiles

    def _generate_decorations(
        self,
        tiles: np.ndarray,
        platforms: list[dict],
        config: CloudKingdomConfig,
        grid_w: int,
        grid_h: int,
    ) -> list[dict]:
        """Generate decorations (pillars, clouds, rainbows, islands).

        Args:
            tiles: The tile map.
            platforms: Platform positions.
            config: Kingdom configuration.
            grid_w: Grid width.
            grid_h: Grid height.

        Returns:
            List of decoration dictionaries.
        """
        decorations = []

        # Add rainbow bridges between platforms
        for i in range(min(config.rainbow_bridge_count, len(platforms) - 1)):
            p1 = platforms[i]
            p2 = platforms[(i + 1) % len(platforms)]

            decorations.append({
                "type": "rainbow_bridge",
                "start_x": p1["x"],
                "start_y": p1["y"],
                "end_x": p2["x"],
                "end_y": p2["y"],
                "arc_height": random.uniform(30, 60),
            })

        # Add floating mini-islands
        for _ in range(config.floating_island_count):
            decorations.append({
                "type": "floating_island",
                "x": random.uniform(100, config.width - 100),
                "y": random.uniform(100, config.height - 100),
                "size": random.uniform(15, 40),
                "rotation": random.uniform(0, 360),
                "bob_speed": random.uniform(0.3, 0.8),
            })

        for y in range(grid_h):
            for x in range(grid_w):
                tile = tiles[y, x]

                # Crystal pillars on stone areas
                if tile == TerrainType.ROCK.value:
                    if random.random() < config.crystal_pillar_density:
                        decorations.append({
                            "type": "crystal_pillar",
                            "x": x * 10 + random.uniform(2, 8),
                            "y": y * 10 + random.uniform(2, 8),
                            "scale": random.uniform(0.8, 1.5),
                            "color": random.choice(["white", "gold", "silver", "opal"]),
                            "glow_intensity": random.uniform(0.3, 1.0),
                        })

                # Cloud puffs on cloud surfaces
                if tile in [TerrainType.SAND.value, TerrainType.SHALLOW_WATER.value]:
                    if random.random() < config.cloud_puff_density:
                        decorations.append({
                            "type": "cloud_puff",
                            "x": x * 10 + random.uniform(0, 10),
                            "y": y * 10 + random.uniform(0, 10),
                            "scale": random.uniform(0.5, 2.0),
                            "drift_speed": random.uniform(0.1, 0.5),
                            "opacity": random.uniform(0.5, 0.9),
                        })

        # Add ambient sparkles
        for _ in range(80):
            decorations.append({
                "type": "sky_sparkle",
                "x": random.uniform(0, config.width),
                "y": random.uniform(0, config.height),
                "size": random.uniform(1, 4),
                "twinkle_speed": random.uniform(0.5, 2.0),
                "color": random.choice(["white", "gold", "silver"]),
            })

        # Add birds/wisps
        for _ in range(15):
            decorations.append({
                "type": "sky_wisp",
                "x": random.uniform(0, config.width),
                "y": random.uniform(0, config.height),
                "speed": random.uniform(20, 50),
                "direction": random.uniform(0, 360),
                "color": random.choice(["white", "pale_blue", "pale_gold"]),
            })

        return decorations


# World locations for the cloud kingdom (used for tool-based movement)
CLOUD_KINGDOM_LOCATIONS = {
    "throne": Position(0, -40),            # Central throne - thinking/planning
    "library_cloud": Position(-90, 25),    # Library cloud - reading/searching
    "artisan_tower": Position(80, -35),    # Artisan tower - writing/building
    "fountain": Position(-60, 60),         # Cloud fountain - fetching
    "garden": Position(45, 45),            # Sky garden - resting
    "observatory": Position(100, 15),      # Observatory - exploring
    "archive_spire": Position(-110, -25),  # Archive spire - searching
    "center": Position(0, 0),              # Center
}


def create_cloud_kingdom(
    config: Optional[CloudKingdomConfig] = None,
) -> GameState:
    """Create a complete game state with cloud kingdom world.

    Args:
        config: Optional configuration. Defaults to standard settings.

    Returns:
        Complete GameState.
    """
    if config is None:
        config = CloudKingdomConfig()

    # Generate terrain
    generator = CloudKingdomGenerator(seed=config.seed)
    terrain = generator.generate_terrain(config)

    # Create world state
    world = WorldState(
        name="cloud-kingdom",
        width=config.width,
        height=config.height,
        terrain=terrain,
        water_offset=0.0,
        weather=WeatherState(
            type=config.initial_weather,
            intensity=0.0,
            wind_direction=90.0,
            wind_speed=5.0,
        ),
        time_of_day=TimeOfDay(hour=config.initial_time),
        ambient_light=(240, 245, 255),  # Bright, ethereal lighting
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
