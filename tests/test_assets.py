"""Tests for asset management."""

from __future__ import annotations

import pytest
from pathlib import Path

from claude_world.assets import (
    SPRITE_DEFINITIONS,
    ANIMATION_DEFINITIONS,
    create_all_sprites,
    get_sprite_definition,
    PlaceholderGenerator,
)
from claude_world.assets.sprite_definitions import create_sprite


class TestSpriteDefinitions:
    """Tests for sprite definitions."""

    def test_has_claude_main_sprite(self):
        """Test claude_main sprite is defined."""
        assert "claude_main" in SPRITE_DEFINITIONS

    def test_has_agent_sprites(self):
        """Test agent sprites are defined."""
        assert "explore_agent" in SPRITE_DEFINITIONS
        assert "plan_agent" in SPRITE_DEFINITIONS
        assert "general_agent" in SPRITE_DEFINITIONS

    def test_has_decoration_sprites(self):
        """Test decoration sprites are defined."""
        assert "palm_tree" in SPRITE_DEFINITIONS
        assert "rock" in SPRITE_DEFINITIONS
        assert "flower" in SPRITE_DEFINITIONS

    def test_has_particle_sprites(self):
        """Test particle sprites are defined."""
        assert "particle_star" in SPRITE_DEFINITIONS
        assert "particle_code" in SPRITE_DEFINITIONS

    def test_sprite_has_required_fields(self):
        """Test sprite definitions have required fields."""
        for sprite_id, sprite_def in SPRITE_DEFINITIONS.items():
            assert "width" in sprite_def, f"{sprite_id} missing width"
            assert "height" in sprite_def, f"{sprite_id} missing height"
            assert "anchor" in sprite_def, f"{sprite_id} missing anchor"

    def test_get_sprite_definition(self):
        """Test getting sprite definition."""
        sprite_def = get_sprite_definition("claude_main")
        assert sprite_def is not None
        assert sprite_def["width"] == 64

    def test_get_unknown_sprite_returns_none(self):
        """Test getting unknown sprite returns None."""
        assert get_sprite_definition("nonexistent") is None


class TestAnimationDefinitions:
    """Tests for animation definitions."""

    def test_claude_main_has_animations(self):
        """Test claude_main has animations defined."""
        assert "claude_main" in ANIMATION_DEFINITIONS
        anims = ANIMATION_DEFINITIONS["claude_main"]
        assert "idle" in anims
        assert "thinking" in anims
        assert "reading" in anims
        assert "writing" in anims

    def test_animations_have_required_fields(self):
        """Test animation definitions have required fields."""
        for sprite_id, anims in ANIMATION_DEFINITIONS.items():
            for anim_name, anim_data in anims.items():
                assert "frames" in anim_data, f"{sprite_id}.{anim_name} missing frames"
                assert "durations" in anim_data, f"{sprite_id}.{anim_name} missing durations"
                assert "loop" in anim_data, f"{sprite_id}.{anim_name} missing loop"

    def test_frames_are_tuples(self):
        """Test animation frames are region tuples."""
        for sprite_id, anims in ANIMATION_DEFINITIONS.items():
            for anim_name, anim_data in anims.items():
                for frame in anim_data["frames"]:
                    assert len(frame) == 4, f"{sprite_id}.{anim_name} frame should be (x, y, w, h)"


class TestCreateSprite:
    """Tests for sprite creation."""

    def test_create_sprite_returns_sprite(self):
        """Test creating a sprite returns Sprite object."""
        sprite = create_sprite("claude_main")
        assert sprite is not None
        assert sprite.id == "claude_main"

    def test_created_sprite_has_correct_size(self):
        """Test created sprite has correct dimensions."""
        sprite = create_sprite("claude_main")
        assert sprite.width == 64
        assert sprite.height == 64

    def test_created_sprite_has_animations(self):
        """Test created sprite has animations."""
        sprite = create_sprite("claude_main")
        assert "idle" in sprite.animations
        assert "thinking" in sprite.animations

    def test_animation_has_frames(self):
        """Test created animation has frames."""
        sprite = create_sprite("claude_main")
        idle = sprite.animations["idle"]
        assert len(idle.frames) > 0

    def test_create_all_sprites(self):
        """Test creating all sprites."""
        sprites = create_all_sprites()
        assert len(sprites) == len(SPRITE_DEFINITIONS)
        assert "claude_main" in sprites
        assert "palm_tree" in sprites


class TestPlaceholderGenerator:
    """Tests for placeholder sprite generation."""

    def test_generator_creates(self):
        """Test generator can be created."""
        generator = PlaceholderGenerator()
        assert generator is not None

    def test_generator_has_output_dir(self):
        """Test generator has output directory."""
        generator = PlaceholderGenerator()
        assert generator.output_dir is not None

    def test_generator_custom_output_dir(self):
        """Test generator accepts custom output directory."""
        custom_path = Path("/tmp/test_sprites")
        generator = PlaceholderGenerator(output_dir=custom_path)
        assert generator.output_dir == custom_path

    @pytest.mark.skipif(
        not PlaceholderGenerator().__class__.__module__,
        reason="PIL not available"
    )
    def test_generate_sprite_creates_file(self, tmp_path):
        """Test generating a sprite creates a file."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not available")

        generator = PlaceholderGenerator(output_dir=tmp_path)
        sprite_def = SPRITE_DEFINITIONS["claude_main"]
        path = generator.generate_sprite("claude_main", sprite_def)

        assert path is not None
        assert path.exists()
        assert path.suffix == ".png"

    @pytest.mark.skipif(
        not PlaceholderGenerator().__class__.__module__,
        reason="PIL not available"
    )
    def test_generate_all_creates_files(self, tmp_path):
        """Test generating all sprites creates files."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not available")

        generator = PlaceholderGenerator(output_dir=tmp_path)
        generated = generator.generate_all()

        assert len(generated) > 0
        for sprite_id, path in generated.items():
            assert path.exists(), f"{sprite_id} file not created"
