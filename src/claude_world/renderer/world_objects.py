"""World object rendering functions for the game."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import ImageDraw
    from claude_world.types import GameState


class WorldObjectsMixin:
    """Mixin class providing world object rendering methods."""

    # These will be set by the main renderer class
    draw: ImageDraw.ImageDraw
    width: int
    height: int
    COLORS: dict

    def _safe_ellipse(self, coords: list, **kwargs) -> None:
        """Draw an ellipse only if coordinates are valid."""
        raise NotImplementedError

    def _draw_world_objects(self, center_x: int, center_y: int, px: int, frame: int, state: GameState) -> None:
        """Draw interactive objects at world locations - matching WORLD_LOCATIONS in entity.py."""
        current_loc = state.main_agent.current_location

        # Positions match WORLD_LOCATIONS in entity.py (relative offsets from center)
        # Scale factor converts entity coords to pixel coords
        scale = px * 1.5

        # Palm tree reading spot - Position(-170, -50)
        palm_x = center_x + int(-170 * scale / px)
        palm_y = center_y + int(-50 * scale / px)
        self._draw_reading_palm(palm_x, palm_y, px, frame, active=(current_loc == "palm_tree"))

        # Rock pile - Position(170, 60)
        rock_x = center_x + int(170 * scale / px)
        rock_y = center_y + int(60 * scale / px)
        self._draw_rock_pile(rock_x, rock_y, px, frame, active=(current_loc == "rock_pile"))

        # Sandy patch - Position(-130, 80)
        sand_x = center_x + int(-130 * scale / px)
        sand_y = center_y + int(80 * scale / px)
        self._draw_sand_patch(sand_x, sand_y, px, frame, active=(current_loc == "sand_patch"))

        # Tide pool - Position(160, -60)
        pool_x = center_x + int(160 * scale / px)
        pool_y = center_y + int(-60 * scale / px)
        self._draw_tide_pool(pool_x, pool_y, px, frame, active=(current_loc == "tide_pool"))

        # Bushes - Position(120, 30)
        bush_x = center_x + int(120 * scale / px)
        bush_y = center_y + int(30 * scale / px)
        self._draw_bush(bush_x, bush_y, px, frame, active=(current_loc == "bushes"))

        # Message bottle at shore - Position(-180, 70)
        bottle_x = center_x + int(-180 * scale / px)
        bottle_y = center_y + int(70 * scale / px)
        self._draw_message_bottle(bottle_x, bottle_y, px, frame, active=(current_loc == "shore"))

        # Thinking spot on hilltop - Position(80, -80)
        hilltop_x = center_x + int(80 * scale / px)
        hilltop_y = center_y + int(-80 * scale / px)
        self._draw_thinking_spot(hilltop_x, hilltop_y, px, frame, active=(current_loc == "hilltop"))

    def _draw_reading_palm(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a palm tree with reading spot beneath it."""
        trunk_color = (120, 80, 50)
        trunk_dark = (90, 60, 40)
        frond_color = (60, 140, 60)
        frond_light = (90, 170, 80)
        outline = self.COLORS["outline"]

        sway = int(math.sin(frame * 0.04) * px * 2)

        # Shadow on ground
        self.draw.ellipse([x - px*6, y + px*4, x + px*6, y + px*6], fill=(60, 120, 50))

        # Trunk - curved palm trunk
        for i in range(4):
            trunk_x = x + int(math.sin(i * 0.3) * px)
            trunk_y = y - i * px * 3
            self.draw.rectangle([trunk_x - px*2 - px, trunk_y - px*2,
                               trunk_x + px*2 + px, trunk_y + px*2], fill=outline)
            self.draw.rectangle([trunk_x - px*2, trunk_y - px*2,
                               trunk_x + px*2, trunk_y + px*2], fill=trunk_color)
            self.draw.rectangle([trunk_x - px, trunk_y - px*2,
                               trunk_x, trunk_y + px*2], fill=trunk_dark)

        # Coconuts
        coconut_y = y - px * 10
        for i, ox in enumerate([-px*2, px*2]):
            self.draw.ellipse([x + ox + sway - px*2, coconut_y - px*2,
                             x + ox + sway + px*2, coconut_y + px*2], fill=(100, 70, 40))

        # Palm fronds
        frond_base_y = y - px * 12
        fronds = [(-1.2, 0.8), (-0.6, 0.9), (0, 1.0), (0.6, 0.9), (1.2, 0.8)]
        for angle_offset, length_mult in fronds:
            angle = math.pi / 2 + angle_offset + sway * 0.02
            frond_len = px * 8 * length_mult

            for j in range(3):
                seg_t = j / 3.0
                seg_x = x + sway + int(math.cos(angle) * frond_len * seg_t)
                seg_y = frond_base_y + int(math.sin(angle) * frond_len * 0.3 * seg_t) - j * px
                seg_color = frond_light if j == 0 else frond_color
                self.draw.ellipse([seg_x - px*2, seg_y - px, seg_x + px*2, seg_y + px], fill=seg_color)

        if active:
            book_x = x - px * 3
            book_y = y + px * 2
            book_w = px * 5
            book_h = px * 3

            self.draw.rectangle([book_x - px, book_y - px, book_x + book_w + px, book_y + book_h + px],
                              fill=outline)
            self.draw.rectangle([book_x, book_y, book_x + book_w, book_y + book_h],
                              fill=(240, 230, 210))
            self.draw.rectangle([book_x + book_w//2 - px//2, book_y, book_x + book_w//2 + px//2, book_y + book_h],
                              fill=(180, 140, 100))

            page_phase = (frame % 90) / 90.0
            if page_phase > 0.7:
                page_lift = int((page_phase - 0.7) / 0.3 * px * 3)
                self.draw.polygon([
                    (book_x + book_w//2, book_y),
                    (book_x + book_w, book_y - page_lift),
                    (book_x + book_w, book_y + book_h),
                    (book_x + book_w//2, book_y + book_h)
                ], fill=(255, 250, 240))

            for i in range(3):
                sparkle_phase = (frame * 0.1 + i * 2.5) % (math.pi * 2)
                sparkle_x = book_x + book_w//2 + int(math.cos(sparkle_phase) * px * 4)
                sparkle_y = book_y - px * 2 + int(math.sin(sparkle_phase) * px * 2)
                if (frame + i * 11) % 20 < 14:
                    self.draw.rectangle([sparkle_x - px//2, sparkle_y - px//2,
                                       sparkle_x + px//2, sparkle_y + px//2], fill=(255, 255, 200))

    def _draw_rock_pile(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a pile of rocks with depth and detail."""
        rock_base = [(130, 125, 120), (115, 110, 105), (145, 140, 135), (100, 95, 90)]
        rock_highlight = [(170, 165, 160), (155, 150, 145), (180, 175, 170), (140, 135, 130)]
        rock_shadow = [(90, 85, 80), (75, 70, 65), (100, 95, 90), (60, 55, 50)]
        outline = self.COLORS["outline"]

        shake = int(math.sin(frame * 0.4) * px) if active else 0

        shadow_color = (60, 100, 50) if not active else (80, 120, 70)
        self.draw.ellipse([x - px*8, y + px*2, x + px*8, y + px*5], fill=shadow_color)

        rocks = [
            (-px*4, -px*3, px*5, px*4, 0),
            (px*3, -px*2, px*4, px*3, 1),
            (-px*2, px*1, px*6, px*4, 2),
            (px*4, px*2, px*5, px*3, 3),
            (px*1, -px*4, px*4, px*3, 0),
        ]

        for i, (ox, oy, w, h, ci) in enumerate(rocks):
            rock_shake = int(math.sin(frame * 0.5 + i * 1.5) * px) if active else 0
            rx, ry = x + ox + shake, y + oy + rock_shake

            base = rock_base[ci]
            highlight = rock_highlight[ci]
            shadow = rock_shadow[ci]

            if active:
                base = tuple(min(255, c + 25) for c in base)
                highlight = tuple(min(255, c + 25) for c in highlight)

            self.draw.ellipse([rx - w - px, ry - h - px, rx + w + px, ry + h + px], fill=outline)
            self.draw.ellipse([rx - w, ry - h, rx + w, ry + h], fill=base)
            self.draw.ellipse([rx - w + px, ry - h + px, rx - px, ry - px], fill=highlight)
            self.draw.ellipse([rx + px, ry + px, rx + w - px, ry + h - px], fill=shadow)

        pebble_positions = [(-px*7, px*3), (px*7, px*4), (-px*5, px*4), (px*6, px*3)]
        for i, (px_off, py_off) in enumerate(pebble_positions):
            peb_x, peb_y = x + px_off + shake, y + py_off
            peb_size = px + (i % 2)
            self._safe_ellipse([peb_x - peb_size, peb_y - peb_size//2,
                             peb_x + peb_size, peb_y + peb_size//2], fill=rock_base[i % 4])

        if active:
            for i in range(5):
                spark_x = x + int(math.sin(frame * 0.25 + i * 1.2) * px * 6)
                spark_y = y - px * 5 - int((frame * 2 + i * 7) % (px * 10))
                spark_size = px if (frame + i) % 3 == 0 else px // 2
                spark_color = (255, 220, 100) if i % 2 == 0 else (255, 180, 80)
                self.draw.rectangle([spark_x - spark_size, spark_y - spark_size,
                                   spark_x + spark_size, spark_y + spark_size], fill=spark_color)

            for i in range(3):
                dust_x = x + int(math.cos(frame * 0.12 + i * 2.5) * px * 7)
                dust_y = y + px * 3 + int(math.sin(frame * 0.08 + i) * px)
                dust_size = px * 2 + int(abs(math.sin(frame * 0.1 + i)) * px * 1.5)
                dust_color = (180, 170, 160) if i % 2 == 0 else (160, 150, 140)
                self.draw.ellipse([dust_x - dust_size, dust_y - dust_size,
                                 dust_x + dust_size, dust_y + dust_size], fill=dust_color)

    def _draw_sand_patch(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a sandy dig spot with shovel and writing/building area."""
        sand_color = (230, 210, 170)
        sand_dark = (200, 180, 140)
        sand_light = (245, 230, 195)
        outline = self.COLORS["outline"]
        wood_color = (140, 100, 60)
        metal_color = (180, 180, 190)

        self.draw.ellipse([x - px*10, y + px*3, x + px*10, y + px*5], fill=(60, 100, 50))

        self.draw.ellipse([x - px*8 - px, y - px*4 - px, x + px*8 + px, y + px*4 + px], fill=outline)
        self.draw.ellipse([x - px*8, y - px*4, x + px*8, y + px*4], fill=sand_color)
        self.draw.ellipse([x - px*5, y - px*2, x + px*5, y + px*2], fill=sand_light)

        self.draw.ellipse([x + px*4, y - px*3, x + px*7, y - px], fill=sand_dark)
        self.draw.ellipse([x + px*5, y - px*3, x + px*6, y - px*2], fill=sand_color)

        shovel_x = x - px * 5
        shovel_bob = int(math.sin(frame * 0.1) * px * 0.5) if active else 0

        self.draw.rectangle([shovel_x - px, y - px*10 + shovel_bob, shovel_x + px, y - px*2 + shovel_bob], fill=outline)
        self.draw.rectangle([shovel_x - px//2, y - px*10 + shovel_bob, shovel_x + px//2, y - px*2 + shovel_bob], fill=wood_color)

        self.draw.polygon([
            (shovel_x - px*2, y - px*2 + shovel_bob),
            (shovel_x + px*2, y - px*2 + shovel_bob),
            (shovel_x + px, y + px + shovel_bob),
            (shovel_x - px, y + px + shovel_bob)
        ], fill=outline)
        self.draw.polygon([
            (shovel_x - px*1.5, y - px*1.5 + shovel_bob),
            (shovel_x + px*1.5, y - px*1.5 + shovel_bob),
            (shovel_x + px*0.5, y + shovel_bob),
            (shovel_x - px*0.5, y + shovel_bob)
        ], fill=metal_color)

        stick_x = x + px * 2
        self.draw.line([(stick_x, y - px*2), (stick_x + px*3, y + px)], fill=wood_color, width=max(1, px))

        if active:
            glow_size = px * 6 + int(math.sin(frame * 0.1) * px)
            self._safe_ellipse([x - glow_size, y - glow_size//2 - px,
                             x + glow_size, y + glow_size//2], fill=sand_light)

            write_cycle = frame % 120
            num_marks = min((write_cycle // 15) + 1, 8)

            for i in range(num_marks):
                mx = x - px*3 + (i % 4) * px * 2
                my = y - px * 2 + (i // 4) * px * 2

                if i == num_marks - 1:
                    progress = (write_cycle % 15) / 15.0
                    stroke_len = int(px * 2 * progress)
                else:
                    stroke_len = px * 2

                stroke_color = (160, 140, 100)
                if i % 3 == 0:
                    self.draw.line([(mx, my), (mx + stroke_len, my)], fill=stroke_color, width=max(1, px//2))
                elif i % 3 == 1:
                    self.draw.line([(mx, my), (mx + stroke_len, my + stroke_len//2)], fill=stroke_color, width=max(1, px//2))
                else:
                    self.draw.arc([mx, my - px, mx + stroke_len + px, my + px], 0, 180, fill=stroke_color, width=max(1, px//2))

            for i in range(4):
                grain_x = x + int(math.sin(frame * 0.3 + i * 1.5) * px * 4)
                grain_y = y - px * 3 - int((frame * 1.5 + i * 6) % 12) * px // 2
                grain_size = px if i % 2 == 0 else px // 2
                self.draw.rectangle([grain_x, grain_y, grain_x + grain_size, grain_y + grain_size], fill=sand_color)

    def _draw_tide_pool(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a magical scrying pool for web fetching/searching."""
        water_color = (80, 140, 200)
        water_light = (120, 180, 230)
        water_deep = (50, 100, 160)
        outline = self.COLORS["outline"]
        stone_color = (140, 135, 130)
        stone_light = (170, 165, 160)
        magic_glow = (180, 220, 255)

        self.draw.ellipse([x - px*8, y + px*3, x + px*8, y + px*5], fill=(60, 100, 50))

        self.draw.ellipse([x - px*7 - px, y - px*4 - px, x + px*7 + px, y + px*4 + px], fill=outline)
        self.draw.ellipse([x - px*7, y - px*4, x + px*7, y + px*4], fill=stone_color)
        self.draw.ellipse([x - px*6, y - px*3, x + px*4, y + px*3], fill=stone_light)

        self.draw.ellipse([x - px*5, y - px*3, x + px*5, y + px*3], fill=water_deep)
        self.draw.ellipse([x - px*4, y - px*2, x + px*4, y + px*2], fill=water_color)

        for i in range(4):
            sparkle_phase = (frame * 0.1 + i * 1.5) % (math.pi * 2)
            sparkle_x = x + int(math.cos(sparkle_phase + i) * px * 3)
            sparkle_y = y + int(math.sin(sparkle_phase + i) * px * 1.5)
            if (frame + i * 7) % 20 < 12:
                self.draw.rectangle([sparkle_x - px//2, sparkle_y - px//2,
                                   sparkle_x + px//2, sparkle_y + px//2], fill=magic_glow)

        glass_bob = int(math.sin(frame * 0.06) * px)
        glass_x = x + px * 3
        glass_y = y - px * 6 + glass_bob
        self.draw.ellipse([glass_x - px*2 - px, glass_y - px*2 - px,
                         glass_x + px*2 + px, glass_y + px*2 + px], fill=outline)
        self.draw.ellipse([glass_x - px*2, glass_y - px*2,
                         glass_x + px*2, glass_y + px*2], fill=water_light)
        handle_start_x = glass_x + px * 2
        handle_start_y = glass_y + px * 2
        self.draw.line([(handle_start_x, handle_start_y),
                       (handle_start_x + px * 2, handle_start_y + px * 2)],
                      fill=outline, width=max(2, px))

        if active:
            glow_pulse = abs(math.sin(frame * 0.15))
            glow_color = (int(140 + 80 * glow_pulse), int(200 + 50 * glow_pulse), int(255))
            glow_size = int(px * 3 + glow_pulse * px * 2)
            self._safe_ellipse([x - glow_size, y - glow_size//2,
                             x + glow_size, y + glow_size//2], fill=glow_color)

            for i in range(5):
                data_phase = (frame * 0.5 + i * 8) % 25
                dx = x + int(math.sin(frame * 0.15 + i * 1.2) * px * 4)
                dy = y - px * 2 - int(data_phase * px * 0.6)
                if data_phase < 20:
                    data_w = px * (2 if i % 2 == 0 else 1)
                    data_h = px
                    self.draw.rectangle([dx - data_w//2, dy - data_h//2,
                                       dx + data_w//2, dy + data_h//2], fill=magic_glow)

            for i in range(3):
                ring_phase = (frame * 0.12 + i * 1.2) % 3.0
                ring_size = int(px * 2 + ring_phase * px * 2)
                ring_alpha = 1.0 - (ring_phase / 3.0)
                if ring_alpha > 0.2:
                    self._safe_ellipse([x - ring_size, y - ring_size//2,
                                     x + ring_size, y + ring_size//2],
                                    outline=magic_glow, width=max(1, int(px * ring_alpha * 1.5)))

    def _draw_bush(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw bushes for searching with berries and depth."""
        bush_color = (75, 135, 65)
        bush_light = (95, 165, 85)
        bush_mid = (85, 150, 75)
        bush_dark = (55, 105, 45)
        outline = self.COLORS["outline"]
        berry_red = (200, 60, 70)

        shadow_color = (60, 100, 50) if not active else (80, 120, 70)
        self.draw.ellipse([x - px*8, y + px*3, x + px*8, y + px*5], fill=shadow_color)

        base_rustle = int(math.sin(frame * 0.5) * px * 2) if active else 0

        blobs = [
            (-px*4, px*1, px*4, px*3, bush_dark),
            (px*3, -px*1, px*4, px*3, bush_dark),
            (-px*1, -px*2, px*5, px*4, bush_mid),
            (-px*3, px*2, px*5, px*3, bush_color),
            (px*2, px*2, px*5, px*3, bush_color),
            (0, px*1, px*4, px*3, bush_light),
        ]

        for i, (ox, oy, w, h, color) in enumerate(blobs):
            blob_rustle = int(math.sin(frame * 0.6 + i * 1.2) * px) if active else 0
            bx, by = x + ox + base_rustle + blob_rustle, y + oy
            self.draw.ellipse([bx - w - px, by - h - px, bx + w + px, by + h + px], fill=outline)
            self.draw.ellipse([bx - w, by - h, bx + w, by + h], fill=color)
            if i >= 3:
                self._safe_ellipse([bx - w//2, by - h + px, bx, by - px], fill=bush_light)

        berry_positions = [(-px*3, 0), (px*2, px), (-px, -px*2), (px*4, -px), (-px*5, px*2)]
        for i, (bx_off, by_off) in enumerate(berry_positions):
            berry_rustle = int(math.sin(frame * 0.6 + i * 0.8) * px * 0.5) if active else 0
            bx, by = x + bx_off + base_rustle + berry_rustle, y + by_off
            self.draw.ellipse([bx - px, by - px, bx + px, by + px], fill=berry_red)
            self._safe_ellipse([bx - px//2, by - px//2, bx, by], fill=(255, 100, 110))

        if active:
            for i in range(5):
                leaf_phase = (frame * 0.3 + i * 7) % 25
                leaf_x = x + int(math.cos(frame * 0.2 + i * 1.3) * (px * 4 + leaf_phase * px * 0.6))
                leaf_y = y - px * 3 - int(leaf_phase * px * 0.5)
                leaf_color = bush_light if i % 2 == 0 else bush_color
                if leaf_phase < 18:
                    self._safe_ellipse([leaf_x - px, leaf_y - px//2, leaf_x + px, leaf_y + px//2], fill=leaf_color)

            gap_x = x + int(math.sin(frame * 0.1) * px)
            self.draw.ellipse([gap_x - px*2, y - px*2, gap_x + px*2, y + px], fill=bush_dark)

            for i in range(3):
                search_x = x + int(math.sin(frame * 0.15 + i * 2.5) * px * 5)
                search_y = y - px * 5 - int((frame * 0.8 + i * 6) % (px * 8))
                search_size = px if (frame + i * 3) % 5 < 3 else px // 2
                self.draw.rectangle([search_x - search_size, search_y - search_size,
                                   search_x + search_size, search_y + search_size], fill=(255, 255, 200))

    def _draw_message_bottle(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a beach mailbox/message station for asking questions."""
        outline = self.COLORS["outline"]
        wood_color = (140, 100, 60)
        wood_dark = (100, 70, 40)
        wood_light = (180, 140, 100)
        paper_color = (255, 250, 230)
        sand_color = self.COLORS["sand"]

        self.draw.ellipse([x - px*6, y + px*3, x + px*6, y + px*5], fill=(60, 100, 50))
        self.draw.ellipse([x - px*5, y + px, x + px*5, y + px*4], fill=sand_color)

        self.draw.rectangle([x - px - px, y - px*8, x + px + px, y + px*2], fill=outline)
        self.draw.rectangle([x - px, y - px*8, x + px, y + px*2], fill=wood_color)
        self.draw.rectangle([x - px//2, y - px*8, x, y + px*2], fill=wood_dark)

        mailbox_y = y - px * 10
        self.draw.rectangle([x - px*4 - px, mailbox_y - px*2 - px, x + px*4 + px, mailbox_y + px*2 + px], fill=outline)
        self.draw.rectangle([x - px*4, mailbox_y - px*2, x + px*4, mailbox_y + px*2], fill=wood_color)
        self.draw.rectangle([x - px*4, mailbox_y - px*2, x - px*2, mailbox_y + px*2], fill=wood_light)
        self.draw.rectangle([x - px*2, mailbox_y - px, x + px*2, mailbox_y + px], fill=wood_dark)

        flag_color = (200, 50, 50) if active else (150, 40, 40)
        flag_x = x + px * 4
        flag_y = mailbox_y - px * 2
        self.draw.rectangle([flag_x, flag_y, flag_x + px, mailbox_y + px*2], fill=outline)
        if active:
            flag_bob = int(math.sin(frame * 0.2) * px * 0.5)
            self.draw.rectangle([flag_x + px, flag_y - px*2 + flag_bob, flag_x + px*4, flag_y + px + flag_bob], fill=flag_color)
        else:
            self.draw.rectangle([flag_x + px, mailbox_y, flag_x + px*4, mailbox_y + px*3], fill=flag_color)

        qmark_bob = int(math.sin(frame * 0.06) * px)
        qmark_x = x - px * 5
        qmark_y = y - px * 12 + qmark_bob
        self.draw.ellipse([qmark_x - px*2 - px, qmark_y - px*2 - px, qmark_x + px*2 + px, qmark_y + px*2 + px], fill=outline)
        self.draw.ellipse([qmark_x - px*2, qmark_y - px*2, qmark_x + px*2, qmark_y + px*2], fill=(255, 255, 255))
        self.draw.arc([qmark_x - px, qmark_y - px*1.5, qmark_x + px, qmark_y + px*0.5], 180, 0, fill=(80, 80, 80), width=max(1, px))
        self._safe_ellipse([qmark_x - px//2, qmark_y + px//2, qmark_x + px//2, qmark_y + px], fill=(80, 80, 80))

        if active:
            abs(math.sin(frame * 0.12))
            glow_color = (255, 255, 200)
            self.draw.ellipse([x - px*5, mailbox_y - px*3, x + px*5, mailbox_y + px*3], fill=glow_color)
            self.draw.rectangle([x - px*4, mailbox_y - px*2, x + px*4, mailbox_y + px*2], fill=wood_color)

            for i in range(3):
                letter_phase = (frame * 0.3 + i * 10) % 30
                lx = x + int(math.sin(frame * 0.1 + i * 2) * px * 4)
                ly = mailbox_y - px * 2 - int(letter_phase * px * 0.5)
                if letter_phase < 25:
                    self.draw.rectangle([lx - px*2, ly - px, lx + px*2, ly + px], fill=paper_color)
                    self.draw.polygon([(lx - px*2, ly - px), (lx, ly), (lx + px*2, ly - px)], fill=(230, 220, 200))

            for i in range(4):
                sparkle_angle = frame * 0.1 + i * 1.5
                sparkle_x = x + int(math.cos(sparkle_angle) * px * 6)
                sparkle_y = mailbox_y + int(math.sin(sparkle_angle) * px * 4)
                if (frame + i * 6) % 15 < 10:
                    self.draw.rectangle([sparkle_x - px//2, sparkle_y - px//2,
                                       sparkle_x + px//2, sparkle_y + px//2], fill=(255, 255, 150))

    def _draw_thinking_spot(self, x: int, y: int, px: int, frame: int, active: bool = False) -> None:
        """Draw a meditation stone/thinking pedestal on the hilltop."""
        outline = self.COLORS["outline"]
        stone_base = (160, 155, 150)
        stone_light = (190, 185, 180)

        self.draw.ellipse([x - px*6, y + px*2, x + px*6, y + px*4], fill=(60, 100, 50))

        self.draw.ellipse([x - px*5 - px, y - px, x + px*5 + px, y + px*3 + px], fill=outline)
        self.draw.ellipse([x - px*5, y - px, x + px*5, y + px*3], fill=stone_base)
        self.draw.ellipse([x - px*3, y - px, x + px*2, y + px*2], fill=stone_light)

        cushion_color = (180, 100, 120) if not active else (220, 120, 140)
        cushion_light = (210, 140, 160)
        self.draw.ellipse([x - px*3 - px, y - px*3 - px, x + px*3 + px, y + px], fill=outline)
        self.draw.ellipse([x - px*3, y - px*3, x + px*3, y], fill=cushion_color)
        self.draw.ellipse([x - px*2, y - px*3, x + px, y - px], fill=cushion_light)

        bubble_bob = int(math.sin(frame * 0.05) * px)
        bubble_y = y - px * 8 + bubble_bob
        self.draw.ellipse([x - px*3 - px, bubble_y - px*2 - px, x + px*3 + px, bubble_y + px*2 + px], fill=outline)
        self.draw.ellipse([x - px*3, bubble_y - px*2, x + px*3, bubble_y + px*2], fill=(255, 255, 255))
        self.draw.ellipse([x - px, y - px*5 + bubble_bob, x + px, y - px*4 + bubble_bob], fill=(255, 255, 255))
        self._safe_ellipse([x - px//2, y - px*6 + bubble_bob, x + px//2, y - px*5 + bubble_bob], fill=(255, 255, 255))
        dot_y = bubble_y
        for i in range(3):
            dot_x = x - px*2 + i * px * 2
            self._safe_ellipse([dot_x - px//2, dot_y - px//2, dot_x + px//2, dot_y + px//2], fill=(100, 100, 100))

        if active:
            aura_pulse = int(abs(math.sin(frame * 0.08)) * px * 2)
            self.draw.ellipse([x - px*6 - aura_pulse, y - px*4 - aura_pulse,
                             x + px*6 + aura_pulse, y + px*3 + aura_pulse], fill=(255, 255, 220))

            self.draw.ellipse([x - px*3 - px, y - px*3 - px, x + px*3 + px, y + px], fill=outline)
            self.draw.ellipse([x - px*3, y - px*3, x + px*3, y], fill=(220, 120, 140))

            for i in range(6):
                angle = frame * 0.08 + i * math.pi / 3
                dist = px * 6 + int(math.sin(frame * 0.15 + i * 0.7) * px * 2)
                sx = x + int(math.cos(angle) * dist)
                sy = y - px * 4 + int(math.sin(angle) * dist * 0.4)
                sparkle_size = px + int(abs(math.sin(frame * 0.1 + i)) * px)
                sparkle_color = [(255, 255, 180), (255, 220, 150), (200, 255, 200)][i % 3]
                if (frame + i * 5) % 20 < 15:
                    self.draw.rectangle([sx - sparkle_size, sy - sparkle_size,
                                       sx + sparkle_size, sy + sparkle_size], fill=sparkle_color)

            for i in range(3):
                bubble_phase = (frame * 0.2 + i * 12) % 30
                bx = x + int(math.sin(frame * 0.05 + i * 2) * px * 4)
                by = y - px * 6 - int(bubble_phase * px * 0.7)
                bsize = px * (3 - i) // 2 + px
                if bubble_phase < 25:
                    self.draw.ellipse([bx - bsize - px, by - bsize - px,
                                     bx + bsize + px, by + bsize + px], fill=outline)
                    self.draw.ellipse([bx - bsize, by - bsize, bx + bsize, by + bsize], fill=(255, 255, 255))

    def _draw_ambient_particles(self, frame: int, phase: str, px: int) -> None:
        """Draw floating ambient particles for a living world feel."""
        import random

        num_particles = 12

        for i in range(num_particles):
            random.seed(i * 777)
            base_x = random.randint(0, self.width)
            base_y = random.randint(int(self.height * 0.25), int(self.height * 0.85))
            speed_x = random.uniform(0.3, 0.8)
            random.uniform(0.1, 0.3)
            phase_offset = random.uniform(0, math.pi * 2)

            x = int((base_x + frame * speed_x) % self.width)
            y = int(base_y + math.sin(frame * 0.05 + phase_offset) * px * 4)

            if phase == "night":
                glow = abs(math.sin(frame * 0.1 + i))
                if glow > 0.5:
                    brightness = int(150 + glow * 105)
                    self.draw.ellipse(
                        [x - px * 2, y - px * 2, x + px * 2, y + px * 2],
                        fill=(brightness // 2, brightness // 2, 0)
                    )
                    self.draw.rectangle(
                        [x - px // 2, y - px // 2, x + px // 2, y + px // 2],
                        fill=(brightness, brightness, 50)
                    )
            else:
                leaf_color = [(180, 220, 140), (140, 200, 120), (200, 180, 160)][i % 3]
                angle = frame * 0.08 + i
                leaf_w = int(px * 1.5)
                leaf_h = int(px * 0.8)
                offset = int(math.sin(angle) * px)
                self.draw.rectangle(
                    [x - leaf_w + offset, y - leaf_h,
                     x + leaf_w + offset, y + leaf_h],
                    fill=leaf_color
                )

    def _draw_pixel_tree(self, x: int, y: int, scale: float, px: int, frame: int) -> None:
        """Draw a pixel art tree - round canopy with trunk."""
        trunk_w = int(px * 3 * scale)
        trunk_h = int(px * 12 * scale)
        canopy_r = int(px * 8 * scale)

        sway = int(math.sin(frame * 0.03 + x * 0.02) * px * 2 * scale)

        shadow_w = int(canopy_r * 1.2)
        shadow_h = int(canopy_r * 0.4)
        self.draw.ellipse(
            [x - shadow_w, y + trunk_h - shadow_h // 2,
             x + shadow_w, y + trunk_h + shadow_h // 2],
            fill=(60, 120, 50)
        )

        trunk_left = x - trunk_w // 2
        trunk_top = y
        self.draw.rectangle(
            [trunk_left - px, trunk_top, trunk_left + trunk_w + px, y + trunk_h + px],
            fill=self.COLORS["outline"]
        )
        self.draw.rectangle(
            [trunk_left, trunk_top, trunk_left + trunk_w, y + trunk_h],
            fill=self.COLORS["tree_trunk"]
        )
        self.draw.rectangle(
            [trunk_left, trunk_top, trunk_left + trunk_w // 3, y + trunk_h],
            fill=self.COLORS["tree_trunk_dark"]
        )

        canopy_x = x + sway
        canopy_y = y - canopy_r // 2

        self.draw.ellipse(
            [canopy_x - canopy_r - px * 2, canopy_y - canopy_r - px * 2,
             canopy_x + canopy_r + px * 2, canopy_y + canopy_r + px * 2],
            fill=self.COLORS["outline"]
        )

        self.draw.ellipse(
            [canopy_x - canopy_r, canopy_y - canopy_r,
             canopy_x + canopy_r, canopy_y + canopy_r],
            fill=self.COLORS["tree_leaves_dark"]
        )

        self.draw.ellipse(
            [canopy_x - canopy_r + px * 2, canopy_y - canopy_r,
             canopy_x + canopy_r - px * 2, canopy_y + px * 2],
            fill=self.COLORS["tree_leaves"]
        )

        highlight_x = canopy_x - canopy_r // 3
        highlight_y = canopy_y - canopy_r // 3
        highlight_r = canopy_r // 3
        self.draw.ellipse(
            [highlight_x - highlight_r, highlight_y - highlight_r,
             highlight_x + highlight_r, highlight_y + highlight_r],
            fill=self.COLORS["tree_leaves_light"]
        )

    def _draw_pixel_clouds(self, frame: int, phase: str) -> None:
        """Draw pixel art style clouds."""
        px = max(2, self.height // 120)

        if phase == "night":
            cloud_color = (80, 90, 110)
        else:
            cloud_color = (255, 255, 255)

        import random
        random.seed(789)

        for i in range(3):
            base_x = random.randint(0, self.width)
            y = random.randint(int(self.height * 0.05), int(self.height * 0.18))
            speed = 0.2 + i * 0.1

            x = int((base_x + frame * speed) % (self.width + 100) - 50)

            cloud_w = px * (8 + i * 2)
            cloud_h = px * 4

            self.draw.rectangle([x - cloud_w, y, x + cloud_w, y + cloud_h], fill=cloud_color)
            self.draw.rectangle([x - cloud_w - px * 2, y + px, x - cloud_w, y + cloud_h - px], fill=cloud_color)
            self.draw.rectangle([x + cloud_w, y + px, x + cloud_w + px * 2, y + cloud_h - px], fill=cloud_color)
            self.draw.rectangle([x - px * 3, y - px * 2, x + px * 3, y], fill=cloud_color)
