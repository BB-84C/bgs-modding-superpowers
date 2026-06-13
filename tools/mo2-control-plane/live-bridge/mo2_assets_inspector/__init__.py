"""MO2 Assets Inspector support package.

Public surface for the top-level plugin entry: `plugin.create_plugin()`.

Dev-time type checking:
    pip install mobase-stubs
    mypy tools/mo2-control-plane/live-bridge/mo2_assets_inspector/ \
        --explicit-package-bases
"""

from __future__ import annotations

import sys

sys.modules.setdefault("Mo2AssetsInspector", sys.modules[__name__])
