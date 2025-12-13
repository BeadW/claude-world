"""Tests for renderer system (TDD tests written first)."""

from __future__ import annotations

import pytest
from pathlib import Path

from claude_world.renderer.sprite_loader import SpriteLoader
from claude_world.renderer.particle_system import ParticleSystem, ParticleEmitter, EffectConfig
from claude_world.renderer.headless import HeadlessRenderer
from claude_world.types import (
    Position,
    Velocity,
    GameState,
    AgentActivity,
)


class TestSpriteLoader:
    """Tests for sprite loading functionality."""

    def test_load_sprite_creates_sprite_data(self):
        """Test loading a sprite creates sprite data structure."""
        loader = SpriteLoader()
        # Generate a placeholder sprite for testing
        sprite = loader.create_placeholder_sprite("test_sprite", 32, 32)
        assert sprite.id == "test_sprite"
        assert sprite.width == 32
        assert sprite.height == 32

    def test_sprite_has_default_animation(self):
        """Test sprites have at least idle animation."""
        loader = SpriteLoader()
        sprite = loader.create_placeholder_sprite("test_sprite", 64, 64)
        assert "idle" in sprite.animations
        assert sprite.animations["idle"].loop is True

    def test_sprite_anchor_defaults_to_center_bottom(self):
        """Test sprite anchor defaults to center bottom."""
        loader = SpriteLoader()
        sprite = loader.create_placeholder_sprite("test", 64, 64)
        assert sprite.anchor == (32, 64)

    def test_register_sprite_adds_to_cache(self):
        """Test registering a sprite adds it to cache."""
        loader = SpriteLoader()
        sprite = loader.create_placeholder_sprite("my_sprite", 32, 32)
        loader.register(sprite)
        assert loader.get("my_sprite") is not None

    def test_get_nonexistent_sprite_returns_none(self):
        """Test getting nonexistent sprite returns None."""
        loader = SpriteLoader()
        assert loader.get("nonexistent") is None


class TestParticleEmitter:
    """Tests for particle emitter functionality."""

    def test_emitter_creates_particles(self):
        """Test emitter creates particles when updated."""
        config = EffectConfig(
            sprite="particle_star",
            count=(5, 10),
            lifetime=(0.5, 1.0),
            velocity=(50, 100),
            gravity=-20,
            fade=True,
            color_start=(255, 255, 255),
            color_end=(200, 200, 100),
            duration=0.5,
        )
        emitter = ParticleEmitter(
            position=Position(100, 100),
            config=config,
            lifetime=1.0,
        )
        particles = emitter.spawn(0.1)
        assert len(particles) > 0

    def test_emitter_expires_after_duration(self):
        """Test emitter is dead after duration."""
        config = EffectConfig(
            sprite="particle_star",
            count=(1, 2),
            lifetime=(0.1, 0.2),
            velocity=(10, 20),
            gravity=0,
            fade=False,
            color_start=(255, 255, 255),
            color_end=(255, 255, 255),
            duration=0.5,
        )
        emitter = ParticleEmitter(
            position=Position(0, 0),
            config=config,
            lifetime=0.5,
        )
        emitter.update(0.6)
        assert emitter.is_dead is True

    def test_particle_has_required_properties(self):
        """Test particles have required properties."""
        config = EffectConfig(
            sprite="star",
            count=(10, 10),  # Higher count for reliable spawning
            lifetime=(1.0, 1.0),
            velocity=(10, 10),
            gravity=0,
            fade=False,
            color_start=(255, 0, 0),
            color_end=(255, 0, 0),
            duration=0.1,  # Short duration for high spawn rate
        )
        emitter = ParticleEmitter(Position(0, 0), config, 1.0)
        particles = emitter.spawn(0.5)  # Longer dt for more spawns
        assert len(particles) > 0, "Should spawn at least one particle"
        p = particles[0]
        assert hasattr(p, "position")
        assert hasattr(p, "velocity")
        assert hasattr(p, "lifetime")
        assert hasattr(p, "color")


class TestParticleSystem:
    """Tests for particle system."""

    def test_particle_system_creates_empty(self):
        """Test particle system starts empty."""
        ps = ParticleSystem()
        assert len(ps.particles) == 0
        assert len(ps.emitters) == 0

    def test_emit_adds_emitter(self):
        """Test emit adds an emitter."""
        ps = ParticleSystem()
        ps.emit("sparkle", Position(100, 100))
        assert len(ps.emitters) == 1

    def test_update_processes_particles(self):
        """Test update processes particles."""
        ps = ParticleSystem()
        ps.emit("sparkle", Position(100, 100))
        ps.update(0.1)
        assert len(ps.particles) > 0

    def test_dead_particles_removed(self):
        """Test dead particles are removed."""
        ps = ParticleSystem()
        ps.emit("sparkle", Position(0, 0))
        # Update many times to let particles die
        for _ in range(100):
            ps.update(0.1)
        # All particles should eventually die
        assert len(ps.particles) == 0


class TestHeadlessRenderer:
    """Tests for headless renderer backend."""

    def test_headless_renderer_creates(self):
        """Test headless renderer can be created."""
        renderer = HeadlessRenderer(width=800, height=600)
        assert renderer.width == 800
        assert renderer.height == 600

    def test_headless_renderer_has_screen_buffer(self):
        """Test headless renderer has screen buffer."""
        renderer = HeadlessRenderer(width=100, height=50)
        assert renderer.screen is not None
        assert len(renderer.screen) == 50  # rows
        assert len(renderer.screen[0]) == 100  # cols

    def test_render_frame_updates_buffer(self, basic_game_state):
        """Test rendering updates the screen buffer."""
        renderer = HeadlessRenderer(width=80, height=24)
        renderer.render_frame(basic_game_state)
        # Screen should have some content
        assert renderer.last_render_time > 0

    def test_headless_supports_sprites(self):
        """Test headless renderer supports sprite rendering."""
        renderer = HeadlessRenderer(width=80, height=24)
        renderer.draw_sprite("test", Position(40, 12), "idle", 0)
        # Should not raise

    def test_headless_supports_particles(self):
        """Test headless renderer supports particle rendering."""
        renderer = HeadlessRenderer(width=80, height=24)
        renderer.draw_particle(Position(10, 10), (255, 255, 255), 1.0)
        # Should not raise

    def test_headless_supports_ui(self):
        """Test headless renderer supports UI rendering."""
        renderer = HeadlessRenderer(width=80, height=24)
        renderer.draw_text(0, 0, "Hello World", (255, 255, 255))
        # Should not raise

    def test_clear_clears_buffer(self):
        """Test clear clears the buffer."""
        renderer = HeadlessRenderer(width=80, height=24)
        renderer.draw_text(0, 0, "Test", (255, 255, 255))
        renderer.clear()
        # Buffer should be cleared
        assert all(c == " " for c in renderer.screen[0])


class TestRendererIntegration:
    """Integration tests for renderer with game state."""

    def test_render_main_agent(self, basic_game_state):
        """Test rendering main agent."""
        renderer = HeadlessRenderer(width=80, height=24)
        renderer.render_frame(basic_game_state)
        # Main agent should be tracked
        assert "main_agent" in renderer.rendered_entities

    def test_render_with_particles(self, basic_game_state):
        """Test rendering with particles."""
        from claude_world.types import Particle, Velocity

        particle = Particle(
            position=Position(500, 500),
            velocity=Velocity(0, -10),
            lifetime=1.0,
            max_lifetime=1.0,
            sprite="star",
            color=(255, 255, 0),
        )
        basic_game_state.particles.append(particle)

        renderer = HeadlessRenderer(width=80, height=24)
        renderer.render_frame(basic_game_state)
        assert renderer.particle_count == 1

    def test_render_subagents(self, basic_game_state):
        """Test rendering subagents."""
        from claude_world.types import (
            AgentEntity,
            EntityType,
            AnimationState,
        )

        subagent = AgentEntity(
            id="sub-1",
            type=EntityType.SUB_AGENT,
            position=Position(550, 500),
            velocity=Velocity(0, 0),
            sprite_id="explore_agent",
            animation=AnimationState(current_animation="idle"),
            agent_type="Explore",
            activity=AgentActivity.EXPLORING,
        )
        basic_game_state.entities["sub-1"] = subagent

        renderer = HeadlessRenderer(width=80, height=24)
        renderer.render_frame(basic_game_state)
        assert "sub-1" in renderer.rendered_entities
