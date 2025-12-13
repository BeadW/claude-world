"""Main application entry point."""

from __future__ import annotations

import asyncio
from typing import Optional, Union

from claude_world.engine import GameEngine
from claude_world.plugin import EventBridge, HookHandler
from claude_world.renderer.headless import HeadlessRenderer
from claude_world.renderer.terminal_graphics import TerminalGraphicsRenderer
from claude_world.worlds import create_tropical_island

from .game_loop import GameLoop
from .pty_manager import PTYManager


class Application:
    """Main Claude World application."""

    def __init__(
        self,
        headless: bool = False,
        world_name: str = "tropical-island",
        target_fps: int = 30,
        width: int = 800,
        height: int = 500,
    ):
        """Initialize the application.

        Args:
            headless: Run without display (for testing).
            world_name: Name of world to load.
            target_fps: Target frames per second.
            width: Renderer width in pixels.
            height: Renderer height in pixels.
        """
        self.headless = headless
        self.world_name = world_name
        self.target_fps = target_fps
        self.width = width
        self.height = height

        # Components (created in initialize)
        self.engine: Optional[GameEngine] = None
        self.renderer: Optional[Union[HeadlessRenderer, TerminalGraphicsRenderer]] = None
        self.game_loop: Optional[GameLoop] = None
        self.event_bridge: Optional[EventBridge] = None
        self.hook_handler: Optional[HookHandler] = None
        self.pty_manager: Optional[PTYManager] = None

        self._running = False
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all application components."""
        if self._initialized:
            return

        # Create initial game state using world generator
        initial_state = create_tropical_island()

        # Create game engine
        self.engine = GameEngine(initial_state=initial_state)

        # Create renderer
        if self.headless:
            self.renderer = HeadlessRenderer(width=80, height=24)
        else:
            # Use terminal graphics renderer for real graphics
            self.renderer = TerminalGraphicsRenderer(
                width=self.width,
                height=self.height,
            )

        # Create game loop
        self.game_loop = GameLoop(
            engine=self.engine,
            renderer=self.renderer,
            target_fps=self.target_fps,
        )

        # Create event bridge
        self.event_bridge = EventBridge()
        self.event_bridge.on_event = self._handle_event

        # Create hook handler
        self.hook_handler = HookHandler()

        # Create PTY manager (only if not headless)
        if not self.headless:
            self.pty_manager = PTYManager()

        self._initialized = True

    def _create_initial_state(self) -> GameState:
        """Create the initial game state.

        Returns:
            Initial GameState.
        """
        # Create terrain (simple placeholder)
        width, height = 1000, 1000
        heightmap = np.zeros((height // 10, width // 10), dtype=np.float32)
        tiles = np.full((height // 10, width // 10), 2, dtype=np.uint8)  # Sand

        terrain = TerrainData(
            heightmap=heightmap,
            tiles=tiles,
            decorations=[],
        )

        # Create world state
        world = WorldState(
            name=self.world_name,
            width=width,
            height=height,
            terrain=terrain,
            water_offset=0.0,
            weather=WeatherState(
                type="clear",
                intensity=0.0,
                wind_direction=45.0,
                wind_speed=5.0,
            ),
            time_of_day=TimeOfDay(hour=10.0),  # 10 AM
            ambient_light=(255, 255, 255),
        )

        # Create main agent
        main_agent = AgentEntity(
            id="main_agent",
            type=EntityType.MAIN_AGENT,
            position=Position(500.0, 500.0),
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
            camera=Camera(x=500, y=500, target="main_agent"),
            session_active=False,
        )

    async def _handle_event(self, event: dict) -> None:
        """Handle an incoming event.

        Args:
            event: The event to handle.
        """
        if self.game_loop is not None:
            self.game_loop.dispatch_event(event)

    async def run(self) -> None:
        """Run the main application loop."""
        await self.initialize()

        self._running = True

        # Start event bridge server
        bridge_task = asyncio.create_task(self.event_bridge.start_server())

        # Start game loop
        game_task = asyncio.create_task(self.game_loop.run_async())

        try:
            # Run until stopped
            while self._running:
                await asyncio.sleep(0.1)
        finally:
            # Cleanup
            self.game_loop.stop()
            self.event_bridge.stop()

            # Cancel tasks
            bridge_task.cancel()
            game_task.cancel()

            try:
                await bridge_task
            except asyncio.CancelledError:
                pass

            try:
                await game_task
            except asyncio.CancelledError:
                pass

    async def shutdown(self) -> None:
        """Shutdown the application."""
        self._running = False

        if self.event_bridge is not None:
            self.event_bridge.cleanup()

        if self.pty_manager is not None:
            self.pty_manager.stop()

    def stop(self) -> None:
        """Stop the application."""
        self._running = False


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Claude World - Interactive Game")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no display)",
    )
    parser.add_argument(
        "--world",
        default="tropical-island",
        help="World to load",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target FPS",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=800,
        help="Renderer width in pixels",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=500,
        help="Renderer height in pixels",
    )

    args = parser.parse_args()

    app = Application(
        headless=args.headless,
        world_name=args.world,
        target_fps=args.fps,
        width=args.width,
        height=args.height,
    )

    asyncio.run(app.run())


if __name__ == "__main__":
    main()
