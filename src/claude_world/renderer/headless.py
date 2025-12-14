"""Headless renderer for testing."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from claude_world.types import Position, TerrainType

if TYPE_CHECKING:
    from claude_world.types import GameState


class HeadlessRenderer:
    """A headless renderer that creates ASCII art visualization.

    Used for testing and demo environments.
    """

    def __init__(self, width: int = 80, height: int = 24):
        """Initialize the headless renderer.

        Args:
            width: Screen width in characters.
            height: Screen height in characters.
        """
        self.width = width
        self.height = height
        self.screen: list[list[str]] = [[" " for _ in range(width)] for _ in range(height)]
        self.last_render_time: float = 0.0
        self.rendered_entities: dict[str, dict] = {}
        self.particle_count: int = 0
        self._render_count = 0

    def clear(self) -> None:
        """Clear the screen buffer."""
        self.screen = [[" " for _ in range(self.width)] for _ in range(self.height)]
        self.rendered_entities.clear()
        self.particle_count = 0

    def render_frame(self, state: GameState) -> None:
        """Render a complete frame.

        Args:
            state: The game state to render.
        """
        self.clear()
        start_time = time.perf_counter()

        # Render sky/background
        self._render_background(state)

        # Render terrain
        self._render_terrain(state)

        # Render water
        self._render_water(state)

        # Render decorations
        self._render_decorations(state)

        # Render other entities (subagents)
        for entity in state.entities.values():
            if entity.id != state.main_agent.id:
                self._render_entity(entity)

        # Render main agent (on top)
        self._render_entity(state.main_agent)

        # Render particles
        for particle in state.particles:
            self.draw_particle(particle.position, particle.color, particle.scale)
            self.particle_count += 1

        # Render UI (last, on top of everything)
        self._render_ui(state)

        # Track timing
        self.last_render_time = time.perf_counter() - start_time
        self._render_count += 1

    def _render_background(self, state: GameState) -> None:
        """Render sky/background based on time of day."""
        phase = state.world.time_of_day.phase

        # Fill sky based on time of day
        if phase == "night":
            for y in range(3):
                for x in range(self.width):
                    if (x + y) % 7 == 0:
                        self.screen[y][x] = "·"
                    elif (x * y) % 23 == 0:
                        self.screen[y][x] = "*"
        elif phase == "dawn" or phase == "dusk":
            # Gradient effect
            for x in range(self.width):
                if x % 3 == 0:
                    self.screen[0][x] = "~"

    def _render_terrain(self, state: GameState) -> None:
        """Render terrain as ASCII."""
        terrain = state.world.terrain
        camera_x = state.camera.x
        camera_y = state.camera.y

        # Map terrain tiles to characters
        tile_chars = {
            TerrainType.DEEP_WATER.value: "≈",
            TerrainType.SHALLOW_WATER.value: "~",
            TerrainType.SAND.value: "░",
            TerrainType.GRASS.value: "▒",
            TerrainType.DIRT.value: "▓",
            TerrainType.ROCK.value: "█",
        }

        # Calculate visible area (center on camera)
        world_w = state.world.width
        world_h = state.world.height

        # Reserve top 3 rows for UI
        ui_height = 3
        game_height = self.height - ui_height

        for screen_y in range(ui_height, self.height):
            for screen_x in range(self.width):
                # Convert screen to world coordinates
                world_x = camera_x + (screen_x - self.width // 2) * (world_w / self.width)
                world_y = camera_y + (screen_y - ui_height - game_height // 2) * (world_h / game_height)

                # Get tile at this position
                tile_x = int(world_x / 10) % terrain.tiles.shape[1]
                tile_y = int(world_y / 10) % terrain.tiles.shape[0]

                if 0 <= tile_x < terrain.tiles.shape[1] and 0 <= tile_y < terrain.tiles.shape[0]:
                    tile_type = terrain.tiles[tile_y, tile_x]
                    char = tile_chars.get(tile_type, " ")
                    self.screen[screen_y][screen_x] = char

    def _render_water(self, state: GameState) -> None:
        """Add water animation effect."""
        offset = state.world.water_offset

        # Animate water tiles
        ui_height = 3
        for screen_y in range(ui_height, self.height):
            for screen_x in range(self.width):
                if self.screen[screen_y][screen_x] in ("≈", "~"):
                    # Animate based on offset
                    phase = (screen_x + screen_y + int(offset * 10)) % 3
                    if self.screen[screen_y][screen_x] == "≈":
                        self.screen[screen_y][screen_x] = ["≈", "≋", "≈"][phase]
                    else:
                        self.screen[screen_y][screen_x] = ["~", "∼", "~"][phase]

    def _render_decorations(self, state: GameState) -> None:
        """Render terrain decorations."""
        decorations = state.world.terrain.decorations
        camera_x = state.camera.x
        camera_y = state.camera.y
        ui_height = 3
        game_height = self.height - ui_height

        for deco in decorations:
            # Convert world to screen coords
            screen_x = int((deco["x"] - camera_x) * self.width / state.world.width + self.width // 2)
            screen_y = int((deco["y"] - camera_y) * game_height / state.world.height + game_height // 2) + ui_height

            if 0 <= screen_x < self.width and ui_height <= screen_y < self.height:
                deco_type = deco["type"]
                if deco_type == "palm_tree":
                    # Draw a simple palm tree
                    if screen_y > ui_height:
                        self.screen[screen_y - 1][screen_x] = "🌴"[0] if screen_x < self.width else "Y"
                    self.screen[screen_y][screen_x] = "|"
                elif deco_type == "rock":
                    self.screen[screen_y][screen_x] = "●"
                elif deco_type == "flower":
                    self.screen[screen_y][screen_x] = "*"

    def _render_entity(self, entity) -> None:
        """Render an entity."""
        self.rendered_entities[entity.id] = {
            "position": (entity.position.x, entity.position.y),
            "sprite_id": entity.sprite_id,
            "animation": entity.animation.current_animation,
            "frame": entity.animation.current_frame,
        }

        self.draw_sprite(
            entity.sprite_id,
            entity.position,
            entity.animation.current_animation,
            entity.animation.current_frame,
        )

    def _render_ui(self, state: GameState) -> None:
        """Render UI overlay."""
        # Clear UI area
        for y in range(3):
            for x in range(self.width):
                self.screen[y][x] = " "

        # Draw border
        self.screen[2] = list("─" * self.width)

        # Top row: Level, XP bar, Activity
        level_text = f"Lv.{state.progression.level}"
        self.draw_text(1, 0, level_text, (255, 255, 255))

        # XP bar
        xp_pct = state.progression.experience / state.progression.experience_to_next
        bar_width = 15
        filled = int(xp_pct * bar_width)
        xp_bar = "[" + "█" * filled + "░" * (bar_width - filled) + "]"
        self.draw_text(len(level_text) + 2, 0, xp_bar, (100, 255, 100))

        # Activity indicator
        activity = state.main_agent.activity.value.upper()
        activity_text = f"◆ {activity}"
        self.draw_text(len(level_text) + bar_width + 5, 0, activity_text, (255, 200, 100))

        # Second row: Resources and stats
        tokens = f"⬡ {state.resources.tokens}"
        tools = f"⚒ {state.progression.total_tools_used}"
        agents = f"◎ {state.progression.total_subagents_spawned}"

        self.draw_text(1, 1, tokens, (255, 200, 50))
        self.draw_text(12, 1, tools, (150, 200, 255))
        self.draw_text(22, 1, agents, (200, 150, 255))

        # Time and weather
        hour = int(state.world.time_of_day.hour)
        minute = int((state.world.time_of_day.hour % 1) * 60)
        time_text = f"{hour:02d}:{minute:02d}"
        weather_icon = {"clear": "☀", "cloudy": "☁", "rain": "🌧", "storm": "⛈"}.get(state.world.weather.type, "?")
        self.draw_text(self.width - 12, 1, f"{weather_icon} {time_text}", (200, 200, 200))

        # Session indicator
        if state.session_active:
            self.draw_text(self.width - 3, 0, "●", (100, 255, 100))
        else:
            self.draw_text(self.width - 3, 0, "○", (150, 150, 150))

    def draw_sprite(
        self,
        sprite_id: str,
        position: Position,
        animation: str,
        frame: int,
    ) -> None:
        """Draw a sprite at position."""
        # Convert world position to screen position
        screen_x = int(position.x * self.width / 1000)
        screen_y = int(position.y * (self.height - 3) / 1000) + 3  # Account for UI

        # Clamp to screen
        screen_x = max(0, min(self.width - 1, screen_x))
        screen_y = max(3, min(self.height - 1, screen_y))

        # Get sprite representation based on animation state
        sprite_art = self._get_sprite_art(sprite_id, animation, frame)

        # Draw multi-character sprite
        for dy, row in enumerate(sprite_art):
            for dx, char in enumerate(row):
                if char != " ":
                    py = screen_y + dy - len(sprite_art) + 1
                    px = screen_x + dx - len(row) // 2
                    if 3 <= py < self.height and 0 <= px < self.width:
                        self.screen[py][px] = char

    def _get_sprite_art(self, sprite_id: str, animation: str, frame: int) -> list[str]:
        """Get ASCII art for a sprite."""
        if sprite_id == "claude_main":
            if animation == "idle":
                return [" ○ ", "/█\\", " ┴ "] if frame % 2 == 0 else [" ○ ", "/█\\", " ╨ "]
            elif animation == "thinking":
                return [" ○?", "/█\\", " ┴ "] if frame % 2 == 0 else [" ?○", "/█\\", " ┴ "]
            elif animation == "reading":
                return [" ○ ", "▐█▌", " ┴ "]
            elif animation == "writing":
                return [" ○ ", "/█▌", " ┴ "] if frame % 2 == 0 else [" ○ ", "▐█\\", " ┴ "]
            elif animation == "searching":
                return [" ◎ ", "/█\\", " ┴ "]
            elif animation == "building":
                return [" ○ ", "/█⚒", " ┴ "] if frame % 2 == 0 else [" ○ ", "⚒█\\", " ┴ "]
            else:
                return [" ○ ", "/█\\", " ┴ "]
        elif "agent" in sprite_id:
            return ["○", "█"]
        else:
            return ["?"]

    def _get_sprite_char(self, sprite_id: str) -> str:
        """Get a single character for a sprite."""
        char_map = {
            "claude_main": "@",
            "explore_agent": "E",
            "plan_agent": "P",
            "general_agent": "G",
            "palm_tree": "♣",
            "rock": "●",
            "flower": "*",
        }
        return char_map.get(sprite_id, "?")

    def draw_particle(
        self,
        position: Position,
        color: tuple[int, int, int],
        scale: float,
    ) -> None:
        """Draw a particle."""
        screen_x = int(position.x * self.width / 1000)
        screen_y = int(position.y * (self.height - 3) / 1000) + 3

        if 3 <= screen_y < self.height and 0 <= screen_x < self.width:
            # Use different chars based on color brightness
            brightness = sum(color) / 3
            if brightness > 200:
                self.screen[screen_y][screen_x] = "✦"
            elif brightness > 100:
                self.screen[screen_y][screen_x] = "·"
            else:
                self.screen[screen_y][screen_x] = "."

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        color: tuple[int, int, int],
    ) -> None:
        """Draw text at screen position."""
        if y < 0 or y >= self.height:
            return

        for i, char in enumerate(text):
            px = x + i
            if 0 <= px < self.width:
                self.screen[y][px] = char

    def get_screen_string(self) -> str:
        """Get the screen as a string."""
        return "\n".join("".join(row) for row in self.screen)
