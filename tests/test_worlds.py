"""Tests for world generation (TDD tests written first)."""

from __future__ import annotations

import pytest
import numpy as np

from claude_world.worlds.tropical_island import (
    TropicalIslandConfig,
    TropicalIslandGenerator,
    create_tropical_island,
)
from claude_world.worlds.world_loader import WorldLoader
from claude_world.types import TerrainType


class TestTropicalIslandConfig:
    """Tests for tropical island configuration."""

    def test_config_creates_with_defaults(self):
        """Test config has sensible defaults."""
        config = TropicalIslandConfig()
        assert config.width > 0
        assert config.height > 0
        assert config.island_radius > 0

    def test_config_custom_size(self):
        """Test config accepts custom size."""
        config = TropicalIslandConfig(width=500, height=500)
        assert config.width == 500
        assert config.height == 500

    def test_config_has_palm_density(self):
        """Test config has palm tree density."""
        config = TropicalIslandConfig()
        assert 0 <= config.palm_density <= 1

    def test_config_has_rock_density(self):
        """Test config has rock density."""
        config = TropicalIslandConfig()
        assert 0 <= config.rock_density <= 1


class TestTropicalIslandGenerator:
    """Tests for tropical island generation."""

    def test_generator_creates(self):
        """Test generator can be created."""
        generator = TropicalIslandGenerator()
        assert generator is not None

    def test_generator_creates_terrain(self):
        """Test generator creates terrain data."""
        generator = TropicalIslandGenerator()
        config = TropicalIslandConfig(width=100, height=100)
        terrain = generator.generate_terrain(config)
        assert terrain is not None
        assert terrain.heightmap.shape == (10, 10)  # Divided by 10
        assert terrain.tiles.shape == (10, 10)

    def test_terrain_has_water(self):
        """Test generated terrain has water tiles."""
        generator = TropicalIslandGenerator()
        config = TropicalIslandConfig(width=100, height=100)
        terrain = generator.generate_terrain(config)
        has_water = np.any(terrain.tiles == TerrainType.DEEP_WATER.value) or np.any(
            terrain.tiles == TerrainType.SHALLOW_WATER.value
        )
        assert has_water

    def test_terrain_has_sand(self):
        """Test generated terrain has sand tiles."""
        generator = TropicalIslandGenerator()
        # Use properly centered config
        config = TropicalIslandConfig(
            width=200, height=200,
            island_center=(100, 100),
            island_radius=70
        )
        terrain = generator.generate_terrain(config)
        has_sand = np.any(terrain.tiles == TerrainType.SAND.value)
        assert has_sand

    def test_terrain_has_grass(self):
        """Test generated terrain has grass tiles."""
        generator = TropicalIslandGenerator()
        # Use properly centered config
        config = TropicalIslandConfig(
            width=200, height=200,
            island_center=(100, 100),
            island_radius=70
        )
        terrain = generator.generate_terrain(config)
        has_grass = np.any(terrain.tiles == TerrainType.GRASS.value)
        assert has_grass

    def test_generator_creates_decorations(self):
        """Test generator creates decorations."""
        generator = TropicalIslandGenerator()
        # Use properly centered config with larger island
        config = TropicalIslandConfig(
            width=400, height=400,
            island_center=(200, 200),
            island_radius=150,
            palm_density=0.3
        )
        terrain = generator.generate_terrain(config)
        # Should have some decorations
        assert len(terrain.decorations) > 0

    def test_decorations_have_required_fields(self):
        """Test decorations have required fields."""
        generator = TropicalIslandGenerator()
        config = TropicalIslandConfig(
            width=400, height=400,
            island_center=(200, 200),
            island_radius=150,
            palm_density=0.3
        )
        terrain = generator.generate_terrain(config)
        for deco in terrain.decorations:
            assert "type" in deco
            assert "x" in deco
            assert "y" in deco


class TestCreateTropicalIsland:
    """Tests for create_tropical_island helper."""

    def test_creates_game_state(self):
        """Test helper creates complete game state."""
        state = create_tropical_island()
        assert state is not None
        assert state.world.name == "tropical-island"

    def test_state_has_main_agent(self):
        """Test state has main agent."""
        state = create_tropical_island()
        assert state.main_agent is not None
        assert state.main_agent.id == "main_agent"

    def test_state_has_valid_terrain(self):
        """Test state has valid terrain."""
        state = create_tropical_island()
        assert state.world.terrain is not None
        assert state.world.terrain.heightmap is not None

    def test_custom_config(self):
        """Test helper accepts custom config."""
        config = TropicalIslandConfig(width=500, height=500)
        state = create_tropical_island(config)
        assert state.world.width == 500
        assert state.world.height == 500


class TestWorldLoader:
    """Tests for world loader."""

    def test_loader_creates(self):
        """Test world loader can be created."""
        loader = WorldLoader()
        assert loader is not None

    def test_loader_has_registered_worlds(self):
        """Test loader has worlds registered."""
        loader = WorldLoader()
        assert "tropical-island" in loader.available_worlds

    def test_load_tropical_island(self):
        """Test loading tropical island world."""
        loader = WorldLoader()
        state = loader.load("tropical-island")
        assert state is not None
        assert state.world.name == "tropical-island"

    def test_load_unknown_world_raises(self):
        """Test loading unknown world raises error."""
        loader = WorldLoader()
        with pytest.raises(ValueError):
            loader.load("unknown-world")

    def test_loader_get_config(self):
        """Test getting world config."""
        loader = WorldLoader()
        config = loader.get_config("tropical-island")
        assert config is not None
