"""MO2 Assets Inspector - IPluginTool plugin entry.

Deployed at runtime to `<MO2_Root>/plugins/mo2_assets_inspector.py` alongside
the support tree at `<MO2_Root>/plugins/Mo2AssetsInspector/`.

This top-level file is a thin entry that:
  1. Inserts the support tree's `vendored/` dir onto sys.path so the bundled
     `mo2_assets_engine` package becomes importable inside MO2's Python.
  2. Imports and re-exports `createPlugin` from the support package.

All real plugin behavior lives under `Mo2AssetsInspector/` (the support tree).
"""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_NAME = "Mo2AssetsInspector"
PLUGIN_SOURCE_SUBTREE = "tools/mo2-control-plane/live-bridge/"
PLUGIN_DEPLOYMENT_TARGET = "plugins/mo2_assets_inspector.py"
PLUGIN_SUPPORT_TARGET = "plugins/Mo2AssetsInspector/"

_SUPPORT_DIR = Path(__file__).resolve().parent / PLUGIN_NAME
_VENDORED_DIR = _SUPPORT_DIR / "vendored"

if _VENDORED_DIR.exists() and str(_VENDORED_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDORED_DIR))

# Late import: support tree must be on sys.path before this resolves.
from Mo2AssetsInspector.plugin import create_plugin as _create_plugin  # noqa: E402


def createPlugin():  # noqa: N802 - MO2 plugin contract requires this name
    return _create_plugin()
