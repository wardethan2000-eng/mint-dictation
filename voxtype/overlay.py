import logging
import math

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

log = logging.getLogger(__name__)

OVERLAY_WIDTH = 220
OVERLAY_HEIGHT = 56
BAR_COUNT = 20
CORNER_RADIUS = 16
REFRESH_MS = 33  # ~30 fps


class DictationOverlay:
    """Small floating overlay showing mic icon and waveform during dictation."""

    def __init__(self, on_stop_clicked=None):
        self._on_stop_clicked = on_stop_clicked
        self._levels: list[float] = [0.0] * BAR_COUNT
        self._tick = 0
        self._timer_id = None

        self._window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self._window.set_decorated(False)
        self._window.set_keep_above(True)
        self._window.set_skip_taskbar_hint(True)
        self._window.set_skip_pager_hint(True)
        self._window.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self._window.set_resizable(False)
        self._window.set_default_size(OVERLAY_WIDTH, OVERLAY_HEIGHT)
        self._window.set_app_paintable(True)

        # Enable RGBA visual for transparency
        screen = self._window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self._window.set_visual(visual)

        # Drawing area fills the window
        self._drawing_area = Gtk.DrawingArea()
        self._drawing_area.set_size_request(OVERLAY_WIDTH, OVERLAY_HEIGHT)
        self._drawing_area.connect("draw", self._on_draw)

        # Event box for click handling
        event_box = Gtk.EventBox()
        event_box.add(self._drawing_area)
        event_box.connect("button-press-event", self._on_click)
        self._window.add(event_box)

        self._position_window()

    def _position_window(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geom = monitor.get_geometry()
        x = geom.x + (geom.width - OVERLAY_WIDTH) // 2
        y = geom.y + 24
        self._window.move(x, y)

    def show(self):
        self._tick = 0
        self._levels = [0.0] * BAR_COUNT
        self._window.show_all()
        self._timer_id = GLib.timeout_add(REFRESH_MS, self._on_tick)

    def hide(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self._window.hide()

    def update_levels(self, levels: list[float]):
        """Called from audio monitor with new waveform data."""
        # Resample to BAR_COUNT if needed
        if len(levels) >= BAR_COUNT:
            step = len(levels) / BAR_COUNT
            self._levels = [levels[int(i * step)] for i in range(BAR_COUNT)]
        else:
            self._levels = levels + [0.0] * (BAR_COUNT - len(levels))

    def _on_tick(self):
        self._tick += 1
        self._drawing_area.queue_draw()
        return True  # keep timer running

    def _on_click(self, widget, event):
        if self._on_stop_clicked:
            self._on_stop_clicked()

    def _on_draw(self, widget, cr: cairo.Context):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()

        # Clear to transparent
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        # Draw rounded rectangle background
        self._rounded_rect(cr, 0, 0, w, h, CORNER_RADIUS)
        cr.set_source_rgba(0.12, 0.12, 0.14, 0.92)
        cr.fill()

        # Draw mic icon (left side)
        mic_cx = 28
        mic_cy = h / 2
        self._draw_mic_icon(cr, mic_cx, mic_cy)

        # Draw waveform bars (right of mic)
        bar_area_x = 56
        bar_area_w = w - bar_area_x - 12
        bar_area_y = 10
        bar_area_h = h - 20
        self._draw_waveform(cr, bar_area_x, bar_area_y, bar_area_w, bar_area_h)

        return False

    def _draw_mic_icon(self, cr: cairo.Context, cx, cy):
        # Pulsing red circle behind mic
        pulse = 0.6 + 0.4 * math.sin(self._tick * 0.15)
        cr.arc(cx, cy, 14, 0, 2 * math.pi)
        cr.set_source_rgba(0.9, 0.22, 0.21, 0.25 * pulse)
        cr.fill()

        # Mic body (capsule)
        cr.set_source_rgba(0.9, 0.22, 0.21, 1.0)
        mic_w, mic_h = 7, 10
        r = mic_w / 2
        cr.move_to(cx - r, cy - mic_h / 2 + r)
        cr.arc(cx, cy - mic_h / 2 + r, r, math.pi, 0)
        cr.line_to(cx + r, cy + mic_h / 2 - r)
        cr.arc(cx, cy + mic_h / 2 - r, r, 0, math.pi)
        cr.close_path()
        cr.fill()

        # Mic stand arc
        cr.set_line_width(1.5)
        cr.arc(cx, cy + 1, 9, math.pi + 0.5, -0.5)
        cr.stroke()

        # Mic stand line
        cr.move_to(cx, cy + 10)
        cr.line_to(cx, cy + 14)
        cr.stroke()
        cr.move_to(cx - 4, cy + 14)
        cr.line_to(cx + 4, cy + 14)
        cr.stroke()

    def _draw_waveform(self, cr: cairo.Context, x, y, w, h):
        bar_w = max(2, (w / BAR_COUNT) * 0.6)
        gap = w / BAR_COUNT

        for i, level in enumerate(self._levels):
            # Add subtle animation even for silent levels
            animated = level + 0.04 * math.sin(self._tick * 0.12 + i * 0.5)
            bar_h = max(3, animated * h)

            bx = x + i * gap + (gap - bar_w) / 2
            by = y + (h - bar_h) / 2

            # Gradient from green to red based on level
            g = max(0, 1.0 - level * 1.5)
            r = min(1.0, level * 2)
            cr.set_source_rgba(r, g, 0.3, 0.85)

            self._rounded_rect(cr, bx, by, bar_w, bar_h, bar_w / 2)
            cr.fill()

    @staticmethod
    def _rounded_rect(cr: cairo.Context, x, y, w, h, r):
        r = min(r, w / 2, h / 2)
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
