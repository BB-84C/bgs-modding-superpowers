"""Manual resize hit-testing for override-redirect windows.

``overrideredirect(True)`` removes the native Win32/X11 resize border. This
module installs an 8-zone resize replacement on the outer amber frame so the
custom chrome keeps normal edge and corner resizing behavior.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from enum import Enum
from typing import Final

from bgs_translator.gui.themes import ThemeConfig

_HIT_MARGIN: Final[int] = 6


class ResizeZone(Enum):
    """Resize hit-test zones around the window perimeter."""

    NONE = "none"
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTHEAST = "northeast"
    NORTHWEST = "northwest"
    SOUTHEAST = "southeast"
    SOUTHWEST = "southwest"


_CURSORS: Final[dict[ResizeZone, str]] = {
    ResizeZone.NONE: "",
    ResizeZone.NORTH: "top_side",
    ResizeZone.SOUTH: "bottom_side",
    ResizeZone.EAST: "right_side",
    ResizeZone.WEST: "left_side",
    ResizeZone.NORTHEAST: "top_right_corner",
    ResizeZone.NORTHWEST: "top_left_corner",
    ResizeZone.SOUTHEAST: "bottom_right_corner",
    ResizeZone.SOUTHWEST: "bottom_left_corner",
}


@dataclass(frozen=True)
class _ResizeStart:
    zone: ResizeZone
    root_x: int
    root_y: int
    width: int
    height: int
    pointer_x: int
    pointer_y: int


class ResizeHandles(tk.Frame):
    """Bind edge/corner resize behavior to an outer window frame."""

    def __init__(self, *, root: tk.Tk, outer_frame: tk.Frame, theme: ThemeConfig) -> None:
        super().__init__(outer_frame, width=0, height=0, borderwidth=0, highlightthickness=0)
        self._root = root
        self._outer_frame = outer_frame
        self._theme = theme
        self._active_zone = ResizeZone.NONE
        self._resize_start: _ResizeStart | None = None

        outer_frame.bind("<Motion>", self._on_motion, add="+")
        outer_frame.bind("<Leave>", self._on_leave, add="+")
        outer_frame.bind("<ButtonPress-1>", self._on_button_press, add="+")
        outer_frame.bind("<B1-Motion>", self._on_drag_motion, add="+")
        outer_frame.bind("<ButtonRelease-1>", self._on_button_release, add="+")

    def apply_theme(self, theme: ThemeConfig) -> None:
        """Store the current theme for parity with other GUI widgets."""

        self._theme = theme

    def hit_test(self, x: int, y: int, width: int, height: int) -> ResizeZone:
        """Return the resize zone for a pointer position in frame coords."""

        near_left = x <= _HIT_MARGIN
        near_right = x >= width - _HIT_MARGIN
        near_top = y <= _HIT_MARGIN
        near_bottom = y >= height - _HIT_MARGIN

        if near_top and near_left:
            return ResizeZone.NORTHWEST
        if near_top and near_right:
            return ResizeZone.NORTHEAST
        if near_bottom and near_left:
            return ResizeZone.SOUTHWEST
        if near_bottom and near_right:
            return ResizeZone.SOUTHEAST
        if near_top:
            return ResizeZone.NORTH
        if near_bottom:
            return ResizeZone.SOUTH
        if near_left:
            return ResizeZone.WEST
        if near_right:
            return ResizeZone.EAST
        return ResizeZone.NONE

    def _zone_from_event(self, event: tk.Event[tk.Misc]) -> ResizeZone:
        width = max(1, self._outer_frame.winfo_width())
        height = max(1, self._outer_frame.winfo_height())
        return self.hit_test(int(event.x), int(event.y), width, height)

    def _on_motion(self, event: tk.Event[tk.Misc]) -> None:
        if self._resize_start is not None:
            return
        zone = self._zone_from_event(event)
        if zone is not self._active_zone:
            self._active_zone = zone
            self._set_cursor(zone)

    def _on_leave(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_start is None:
            self._active_zone = ResizeZone.NONE
            self._set_cursor(ResizeZone.NONE)

    def _on_button_press(self, event: tk.Event[tk.Misc]) -> None:
        zone = self._zone_from_event(event)
        if zone is ResizeZone.NONE:
            self._resize_start = None
            return
        self._root.update_idletasks()
        self._resize_start = _ResizeStart(
            zone=zone,
            root_x=int(self._root.winfo_x()),
            root_y=int(self._root.winfo_y()),
            width=int(self._root.winfo_width()),
            height=int(self._root.winfo_height()),
            pointer_x=int(event.x_root),
            pointer_y=int(event.y_root),
        )

    def _on_drag_motion(self, event: tk.Event[tk.Misc]) -> None:
        if self._resize_start is None:
            return
        start = self._resize_start
        dx = int(event.x_root) - start.pointer_x
        dy = int(event.y_root) - start.pointer_y

        x = start.root_x
        y = start.root_y
        width = start.width
        height = start.height

        if start.zone in {ResizeZone.EAST, ResizeZone.NORTHEAST, ResizeZone.SOUTHEAST}:
            width = start.width + dx
        if start.zone in {ResizeZone.WEST, ResizeZone.NORTHWEST, ResizeZone.SOUTHWEST}:
            x = start.root_x + dx
            width = start.width - dx
        if start.zone in {ResizeZone.SOUTH, ResizeZone.SOUTHEAST, ResizeZone.SOUTHWEST}:
            height = start.height + dy
        if start.zone in {ResizeZone.NORTH, ResizeZone.NORTHEAST, ResizeZone.NORTHWEST}:
            y = start.root_y + dy
            height = start.height - dy

        min_width, min_height = self._root.minsize()
        if width < min_width:
            if start.zone in {ResizeZone.WEST, ResizeZone.NORTHWEST, ResizeZone.SOUTHWEST}:
                x = start.root_x + start.width - min_width
            width = min_width
        if height < min_height:
            if start.zone in {ResizeZone.NORTH, ResizeZone.NORTHEAST, ResizeZone.NORTHWEST}:
                y = start.root_y + start.height - min_height
            height = min_height

        try:
            self._root.geometry(f"{width}x{height}+{x}+{y}")
        except tk.TclError:
            return

    def _on_button_release(self, _event: tk.Event[tk.Misc]) -> None:
        self._resize_start = None

    def _set_cursor(self, zone: ResizeZone) -> None:
        cursor = _CURSORS[zone]
        try:
            self._outer_frame.configure(cursor=cursor)
        except tk.TclError:
            self._outer_frame.configure(cursor="")


__all__ = ["ResizeHandles", "ResizeZone"]
