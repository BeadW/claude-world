"""Main game engine for Claude World."""

from __future__ import annotations

from typing import Any, Optional

from claude_world.types import (
    GameState,
    AgentActivity,
    AgentStatus,
    TOOL_XP_REWARDS,
    check_achievements,
    AchievementPopup,
    check_milestones,
    MilestonePopup,
)
from .state import GameStateManager
from .entity import EntityManager
from .claude_mapper import map_claude_event
from .systems import MovementSystem, AnimationSystem, DayCycleSystem, WeatherSystem


class GameEngine:
    """Main game engine that coordinates all game systems."""

    def __init__(
        self,
        initial_state: Optional[GameState] = None,
        config: Optional[dict] = None,
    ):
        """Initialize the game engine.

        Args:
            initial_state: Optional initial game state.
            config: Optional configuration dictionary.
        """
        self._config = config or {}

        if initial_state:
            self._state_manager = GameStateManager(initial_state)
        else:
            raise ValueError("initial_state is required")

        self._entity_manager = EntityManager(self._state_manager.get_state())

        # Initialize systems
        self._systems = [
            MovementSystem(),
            AnimationSystem(),
            DayCycleSystem(minutes_per_day=self._config.get("day_cycle_minutes", 10)),
            WeatherSystem(),
        ]

    def get_state(self) -> GameState:
        """Get the current game state.

        Returns:
            A copy of the current game state.
        """
        return self._entity_manager.get_state()

    def update(self, dt: float) -> None:
        """Update the game state.

        Args:
            dt: Delta time in seconds since last update.
        """
        state = self._entity_manager.get_state()

        # Update all systems
        for system in self._systems:
            system.update(state, dt)

        # Update floating texts
        for ft in state.floating_texts[:]:
            ft.update(dt)
            if ft.is_dead:
                state.floating_texts.remove(ft)

        # Update achievement popups
        for popup in state.achievement_popups[:]:
            popup.update(dt)
            if popup.is_dead:
                state.achievement_popups.remove(popup)

        # Update milestone popups
        for popup in state.milestone_popups[:]:
            popup.update(dt)
            if popup.is_dead:
                state.milestone_popups.remove(popup)

        # Update progression timers
        if state.progression.level_up_timer > 0:
            state.progression.level_up_timer -= dt
        if state.progression.xp_gain_flash > 0:
            state.progression.xp_gain_flash -= dt

        # Smoothly animate display_xp toward actual experience
        target_xp = float(state.progression.experience)
        state.progression.display_xp += (target_xp - state.progression.display_xp) * min(1.0, dt * 5.0)

        # Sync state back
        self._entity_manager._state = state

    def dispatch_claude_event(self, event: dict[str, Any]) -> None:
        """Handle a Claude event.

        Args:
            event: The Claude event dictionary.
        """
        game_events = map_claude_event(event)

        for game_event in game_events:
            self._handle_game_event(game_event)

    def _handle_game_event(self, event: dict[str, Any]) -> None:
        """Handle a game event.

        Args:
            event: The game event dictionary.
        """
        event_type = event.get("type", "")
        data = event.get("data", {})

        if event_type == "CHANGE_ACTIVITY":
            activity = data.get("activity", AgentActivity.IDLE)
            tool_name = data.get("tool_name")
            agent_id = data.get("agent_id")  # None = main agent

            if agent_id is None:
                # Main agent activity change
                self._entity_manager.set_main_agent_activity(activity, tool_name)
            else:
                # Subagent activity change
                self._entity_manager.set_subagent_activity(agent_id, activity, tool_name)

        elif event_type == "SPAWN_AGENT":
            self._entity_manager.spawn_subagent(
                agent_id=data.get("agent_id", ""),
                agent_type=data.get("agent_type", "general-purpose"),
                description=data.get("description", ""),
            )
            state = self._entity_manager.get_state()
            state.progression.total_subagents_spawned += 1
            # Set status to working
            agent_id = data.get("agent_id", "")
            if agent_id in state.entities:
                agent = state.entities[agent_id]
                if hasattr(agent, 'status'):
                    agent.status = AgentStatus.WORKING

        elif event_type == "REMOVE_AGENT":
            agent_id = data.get("agent_id", "")
            # Remove the agent immediately (status was shown during task)
            self._entity_manager.remove_entity(agent_id)

        elif event_type == "AWARD_RESOURCES":
            state = self._entity_manager.get_state()

            if "xp" in data:
                xp_amount = data["xp"]
                leveled_up = state.progression.add_experience(xp_amount)
                # Spawn floating XP text
                state.spawn_floating_text(
                    f"+{xp_amount} XP",
                    color=(200, 100, 255),  # Purple for XP
                    offset_x=-30,
                )
                if leveled_up:
                    # Spawn level-up text
                    state.spawn_floating_text(
                        f"LEVEL {state.progression.level}!",
                        color=(255, 215, 0),  # Gold
                        offset_x=0,
                        offset_y=-50,
                    )

            if "tokens" in data:
                tokens_amount = data["tokens"]
                state.resources.tokens += tokens_amount
                # Spawn floating token text
                state.spawn_floating_text(
                    f"+{tokens_amount}",
                    color=(255, 200, 50),  # Gold for tokens
                    offset_x=30,
                )

            if "connections" in data:
                conn_amount = data["connections"]
                state.resources.connections += conn_amount
                state.spawn_floating_text(
                    f"+{conn_amount} conn",
                    color=(100, 200, 100),  # Green for connections
                    offset_x=0,
                )

            if "tool_name" in data:
                tool_name = data["tool_name"]
                state.progression.total_tools_used += 1
                state.progression.tool_usage_breakdown[tool_name] = (
                    state.progression.tool_usage_breakdown.get(tool_name, 0) + 1
                )

            # Check for newly unlocked achievements
            newly_unlocked = check_achievements(state)
            for achievement in newly_unlocked:
                popup = AchievementPopup(
                    achievement=achievement,
                    lifetime=4.0,
                    max_lifetime=4.0,
                )
                state.achievement_popups.append(popup)

            # Check for newly reached milestones
            newly_reached = check_milestones(state)
            for milestone in newly_reached:
                popup = MilestonePopup(
                    milestone=milestone,
                    lifetime=5.0,
                    max_lifetime=5.0,
                )
                state.milestone_popups.append(popup)

        elif event_type == "SPAWN_PARTICLES":
            # Particle spawning is handled by the renderer
            pass

        elif event_type == "SESSION_START":
            state = self._entity_manager.get_state()
            state.session_active = True

        elif event_type == "SESSION_END":
            state = self._entity_manager.get_state()
            state.session_active = False

        elif event_type == "API_USAGE":
            state = self._entity_manager.get_state()
            state.resources.api_costs.add_usage(
                input_tokens=data.get("input_tokens", 0),
                output_tokens=data.get("output_tokens", 0),
                cache_read=data.get("cache_read", 0),
                cache_write=data.get("cache_write", 0),
            )

    def subscribe(self, listener) -> callable:
        """Subscribe to state changes.

        Args:
            listener: A function to call when state changes.

        Returns:
            An unsubscribe function.
        """
        return self._state_manager.subscribe(listener)
