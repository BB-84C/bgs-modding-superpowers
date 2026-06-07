"""Windows chrome tinting for the Tk control panel.

On Windows 10 build 1809+ we can force a dark titlebar via the DWM
``UseImmersiveDarkMode`` attribute, which is enough for the green and
mono themes. On Windows 11 build 22000+ DWM also honours
``CaptionColor``, ``TextColor``, and ``BorderColor``, which lets us
paint the titlebar in the actual theme accent and pull the whole window
chrome into the phosphor aesthetic.

If DWM tinting is unavailable (older Windows, non-Windows host) the
caller should fall back to a custom titlebar via
``tk.Tk.overrideredirect(True)`` plus a manual title widget. That path
is documented as a TODO at the call site so it can be wired without
rediscovery.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import tkinter as tk
from ctypes import wintypes
from typing import Any, Final

from bgs_translator.gui.themes import ThemeConfig

log = logging.getLogger(__name__)

# DwmSetWindowAttribute attribute ids.
_DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY: Final[int] = 19  # Win10 1809..1909
_DWMWA_USE_IMMERSIVE_DARK_MODE: Final[int] = 20         # Win10 2004+
_DWMWA_BORDER_COLOR: Final[int] = 34                    # Win11 22000+
_DWMWA_CAPTION_COLOR: Final[int] = 35                   # Win11 22000+
_DWMWA_TEXT_COLOR: Final[int] = 36                      # Win11 22000+

_GA_ROOT: Final[int] = 2


def _hex_to_colorref(color_hex: str) -> int:
    """Convert ``#RRGGBB`` to a Win32 ``COLORREF`` (0x00BBGGRR)."""

    value = color_hex.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB hex color, got {color_hex!r}")
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return (b << 16) | (g << 8) | r


def _root_hwnd(root: tk.Tk) -> int | None:
    """Return the top-level HWND for ``root`` on Windows, or ``None``."""

    if sys.platform != "win32":
        return None
    try:
        # Ensure the window is realized so winfo_id has a real HWND.
        root.update_idletasks()
        child = int(root.winfo_id())
    except (tk.TclError, ValueError):
        return None
    try:
        user32: Any = ctypes.windll.user32
        ancestor = user32.GetAncestor(wintypes.HWND(child), _GA_ROOT)
        return int(ancestor) if ancestor else child
    except (OSError, AttributeError) as exc:
        log.debug("GetAncestor failed, using winfo_id directly: %s", exc)
        return child


def _set_dwm_uint32(hwnd: int, attribute: int, value: int) -> bool:
    """Best-effort wrapper around ``DwmSetWindowAttribute``."""

    try:
        dwmapi: Any = ctypes.windll.dwmapi
    except (OSError, AttributeError) as exc:
        log.debug("Could not load dwmapi: %s", exc)
        return False
    data = ctypes.c_uint32(value)
    try:
        hr = dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(attribute),
            ctypes.byref(data),
            ctypes.sizeof(data),
        )
    except OSError as exc:
        log.debug("DwmSetWindowAttribute call failed (attr=%s): %s", attribute, exc)
        return False
    if hr != 0:
        log.debug("DwmSetWindowAttribute returned HRESULT %s for attr %s", hr, attribute)
        return False
    return True


def apply_titlebar_tint(root: tk.Tk, theme: ThemeConfig) -> dict[str, bool]:
    """Tint the host Windows titlebar to match ``theme``.

    Returns a dict reporting which DWM attributes were accepted. All
    keys map to ``False`` on non-Windows or on legacy Windows builds
    where DWM ignores the request — failure is silent and safe.

    Strategy (TODO: implement override-redirect fallback if user later
    asks for a fully custom titlebar):
    1. Force the dark-mode immersive titlebar so light Win11 hosts do
       not render a white caption.
    2. Set the caption colour to the theme's surface / background.
    3. Set the caption text colour to the theme's accent.
    4. Set the window border colour to the theme's border.
    """

    if sys.platform != "win32":
        return {"dark_mode": False, "caption": False, "text": False, "border": False}

    hwnd = _root_hwnd(root)
    if hwnd is None:
        return {"dark_mode": False, "caption": False, "text": False, "border": False}

    results: dict[str, bool] = {}

    # 1. Dark immersive mode. Try the modern attribute first, then
    # fall back to the 1809 ID. Either acceptance counts as success.
    dark_modern = _set_dwm_uint32(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    dark_legacy = False
    if not dark_modern:
        dark_legacy = _set_dwm_uint32(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY, 1)
    results["dark_mode"] = dark_modern or dark_legacy

    # 2/3/4. Caption colour, caption text colour, border colour. These
    # only land on Windows 11 22000+; they fail silently elsewhere.
    try:
        caption_rgb = _hex_to_colorref(theme.surface)
        text_rgb = _hex_to_colorref(theme.accent)
        border_rgb = _hex_to_colorref(theme.border)
    except ValueError as exc:
        log.debug("Bad theme colour for titlebar tint: %s", exc)
        return {**results, "caption": False, "text": False, "border": False}

    results["caption"] = _set_dwm_uint32(hwnd, _DWMWA_CAPTION_COLOR, caption_rgb)
    results["text"] = _set_dwm_uint32(hwnd, _DWMWA_TEXT_COLOR, text_rgb)
    results["border"] = _set_dwm_uint32(hwnd, _DWMWA_BORDER_COLOR, border_rgb)

    log.debug("Titlebar tint applied: %s", results)
    return results


__all__ = ["apply_titlebar_tint"]
