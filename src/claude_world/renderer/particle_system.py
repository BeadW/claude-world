"""Particle system for visual effects."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from claude_world.types import Position, Velocity, Particle

if TYPE_CHECKING:
    pass


@dataclass
class EffectConfig:
    """Configuration for a particle effect."""

    sprite: str
    count: tuple[int, int]  # Min/max particles per spawn
    lifetime: tuple[float, float]  # Particle lifetime range
    velocity: tuple[float, float]  # Initial velocity range
    gravity: float
    fade: bool
    color_start: tuple[int, int, int]
    color_end: tuple[int, int, int]
    duration: float  # Emitter duration


# Predefined effect configurations
EFFECT_CONFIGS: dict[str, EffectConfig] = {
    "sparkle": EffectConfig(
        sprite="particle_star",
        count=(5, 10),
        lifetime=(0.3, 0.8),
        velocity=(50, 100),
        gravity=-20,  # Float upward
        fade=True,
        color_start=(255, 255, 200),
        color_end=(255, 200, 100),
        duration=0.5,
    ),
    "write_burst": EffectConfig(
        sprite="particle_code",
        count=(10, 20),
        lifetime=(0.5, 1.0),
        velocity=(30, 80),
        gravity=50,
        fade=True,
        color_start=(100, 200, 255),
        color_end=(50, 100, 200),
        duration=0.3,
    ),
    "magnify": EffectConfig(
        sprite="particle_lens",
        count=(3, 5),
        lifetime=(0.4, 0.6),
        velocity=(20, 40),
        gravity=0,
        fade=True,
        color_start=(255, 255, 100),
        color_end=(200, 200, 50),
        duration=0.4,
    ),
    "wave": EffectConfig(
        sprite="particle_wave",
        count=(8, 12),
        lifetime=(0.6, 1.2),
        velocity=(40, 60),
        gravity=-10,
        fade=True,
        color_start=(100, 150, 255),
        color_end=(50, 100, 200),
        duration=0.5,
    ),
    "bubble": EffectConfig(
        sprite="particle_bubble",
        count=(6, 10),
        lifetime=(0.8, 1.5),
        velocity=(20, 50),
        gravity=-30,  # Float upward
        fade=True,
        color_start=(200, 200, 255),
        color_end=(150, 150, 200),
        duration=0.6,
    ),
    "rain": EffectConfig(
        sprite="particle_drop",
        count=(20, 40),
        lifetime=(1.0, 2.0),
        velocity=(100, 200),
        gravity=200,
        fade=False,
        color_start=(150, 200, 255),
        color_end=(150, 200, 255),
        duration=0.1,
    ),
    "star": EffectConfig(
        sprite="particle_star",
        count=(3, 6),
        lifetime=(0.5, 1.0),
        velocity=(30, 60),
        gravity=-15,
        fade=True,
        color_start=(255, 255, 100),
        color_end=(255, 200, 50),
        duration=0.5,
    ),
}


@dataclass
class ParticleEmitter:
    """Emits particles at a position."""

    position: Position
    config: EffectConfig
    lifetime: float
    _time_alive: float = 0.0
    _spawn_accumulator: float = 0.0

    @property
    def is_dead(self) -> bool:
        """Check if emitter has expired."""
        return self._time_alive >= self.lifetime

    def update(self, dt: float) -> None:
        """Update emitter time.

        Args:
            dt: Delta time in seconds.
        """
        self._time_alive += dt

    def spawn(self, dt: float) -> list[Particle]:
        """Spawn particles for this time step.

        Args:
            dt: Delta time in seconds.

        Returns:
            List of new particles.
        """
        if self.is_dead:
            return []

        particles: list[Particle] = []

        # Spawn rate based on config
        spawn_rate = (self.config.count[0] + self.config.count[1]) / 2 / self.config.duration
        self._spawn_accumulator += spawn_rate * dt

        while self._spawn_accumulator >= 1.0:
            self._spawn_accumulator -= 1.0
            particles.append(self._create_particle())

        return particles

    def _create_particle(self) -> Particle:
        """Create a single particle.

        Returns:
            A new Particle.
        """
        # Random velocity direction
        angle = random.uniform(0, 360)
        speed = random.uniform(*self.config.velocity)
        import math

        vx = speed * math.cos(math.radians(angle))
        vy = speed * math.sin(math.radians(angle))

        # Random lifetime
        lifetime = random.uniform(*self.config.lifetime)

        # Start color
        color = self.config.color_start

        return Particle(
            position=Position(self.position.x, self.position.y),
            velocity=Velocity(vx, vy),
            lifetime=lifetime,
            max_lifetime=lifetime,
            sprite=self.config.sprite,
            color=color,
        )


class ParticleSystem:
    """Manages all particles and emitters."""

    def __init__(self):
        """Initialize the particle system."""
        self.particles: list[Particle] = []
        self.emitters: list[ParticleEmitter] = []

    def emit(self, effect_type: str, position: Position) -> None:
        """Start emitting an effect at a position.

        Args:
            effect_type: The type of effect to emit.
            position: The position to emit from.
        """
        config = EFFECT_CONFIGS.get(effect_type)
        if config is None:
            # Default to sparkle if unknown effect
            config = EFFECT_CONFIGS["sparkle"]

        emitter = ParticleEmitter(
            position=Position(position.x, position.y),
            config=config,
            lifetime=config.duration,
        )
        self.emitters.append(emitter)

    def update(self, dt: float) -> None:
        """Update all particles and emitters.

        Args:
            dt: Delta time in seconds.
        """
        # Update emitters and spawn particles
        for emitter in self.emitters[:]:
            emitter.update(dt)
            new_particles = emitter.spawn(dt)
            self.particles.extend(new_particles)

            if emitter.is_dead:
                self.emitters.remove(emitter)

        # Update particles
        for particle in self.particles[:]:
            # Apply velocity
            particle.position.x += particle.velocity.x * dt
            particle.position.y += particle.velocity.y * dt

            # Apply gravity (from emitter config - use a default)
            particle.velocity.y += 50 * dt  # Default gravity

            # Decrease lifetime
            particle.lifetime -= dt

            if particle.is_dead:
                self.particles.remove(particle)

    def clear(self) -> None:
        """Clear all particles and emitters."""
        self.particles.clear()
        self.emitters.clear()
