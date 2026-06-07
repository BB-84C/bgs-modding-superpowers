"""DPI awareness and Tk scaling for the control panel.

Windows: enable per-monitor v2 DPI awareness through shcore.dll so the
window is not scaled by the system. Then ask Tk to scale its internal
coordinate system to match the host DPI.

Other platforms: best-effort scaling only.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from typing import Any

log = logging.getLogger(__name__)

# PROCESS_PER_MONITOR_DPI_AWARE = 2 on Windows.
_PER_MONITOR_DPI_AWARE = 2


def enable_windows_dpi_awareness() -> bool:
    """Enable per-monitor v2 DPI awareness on Windows.

    Returns ``True`` if the call succeeded, ``False`` otherwise (silent
    on non-Windows platforms).
    """

    if sys.platform != "win32":
        return False
    try:
        import ctypes

        windll: Any = ctypes.windll
        shcore = windll.shcore
        result = shcore.SetProcessDpiAwareness(_PER_MONITOR_DPI_AWARE)
        # 0 == S_OK; non-zero is an HRESULT failure but already-set is fine.
        if result not in (0, 1):
            log.debug("SetProcessDpiAwareness returned HRESULT %s", result)
        return True
    except (OSError, AttributeError) as exc:
        log.debug("Could not enable DPI awareness: %s", exc)
        return False


def apply_tk_scaling(root: tk.Misc) -> float:
    """Tell Tk how big a point should be in pixels.

    The returned float is the scaling factor that was applied.
    """

    try:
        # winfo_fpixels of one inch is the system reported DPI in pixels.
        dpi = float(root.winfo_fpixels("1i"))
    except tk.TclError:
        dpi = 96.0

    scaling = max(1.0, dpi / 72.0)
    try:
        root.tk.call("tk", "scaling", scaling)
    except tk.TclError as exc:
        log.debug("Could not apply Tk scaling %s: %s", scaling, exc)
    return scaling


__all__ = ["apply_tk_scaling", "enable_windows_dpi_awareness"]
