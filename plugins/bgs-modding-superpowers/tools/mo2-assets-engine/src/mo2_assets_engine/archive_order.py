"""Attach BSA/BA2 archives to enabled plugins by runtime naming convention."""

from __future__ import annotations

import re
from enum import StrEnum


class Game(StrEnum):
    SKYRIM = "skyrim"  # LE / SE / AE / VR (same archive convention)
    FALLOUT3_FNV = "fallout3-fnv"
    FALLOUT4 = "fallout4"  # incl. VR
    STARFIELD = "starfield"


_NAMING_CONVENTIONS: dict[Game, tuple[str, ...]] = {
    Game.SKYRIM: (
        r"{base}\.bsa",
        r"{base} - Textures\.bsa",
        r"{base} - Textures\d+\.bsa",
    ),
    Game.FALLOUT3_FNV: (
        r"{base}\.bsa",
        r"{base} - Textures\.bsa",
    ),
    Game.FALLOUT4: (
        r"{base} - Main\.ba2",
        r"{base} - Textures\.ba2",
        r"{base} - Main\d+\.ba2",
        r"{base} - Textures\d+\.ba2",
    ),
    Game.STARFIELD: (
        r"{base}\.ba2",
        r"{base} - Main\.ba2",
        r"{base} - Textures\.ba2",
        r"{base} - Main\d+\.ba2",
        r"{base} - Textures\d+\.ba2",
    ),
}


def discover_archives_for_plugins(
    *,
    plugins: list[str],
    candidate_archives: list[str],
    game: Game,
) -> dict[str, str]:
    """Return convention attachments as ``archive_name.lower() -> plugin_name``.

    The game runtime binds convention-named archives from a global Data tree,
    not from the folder that happens to hold the plugin.  Therefore matching is
    performed across the whole candidate archive pool.  If two enabled plugins
    can claim the same archive name (normally only duplicate basenames such as
    ``Foo.esm`` and ``Foo.esp``), the earlier plugin in forward load order wins.
    I have not found a public runtime fixture that demonstrates duplicate-base
    reattachment semantics; first-claim is the least surprising model because
    the archive path itself is single-instance in Data and the loader encounters
    earlier plugins first.
    """
    conventions = _NAMING_CONVENTIONS[game]
    plugin_patterns = [
        (
            load_order,
            plugin_name,
            [
                re.compile(
                    pattern.format(base=re.escape(_strip_plugin_suffix(plugin_name))),
                    flags=re.IGNORECASE,
                )
                for pattern in conventions
            ],
        )
        for load_order, plugin_name in enumerate(plugins)
    ]

    attachments: dict[str, str] = {}
    claim_orders: dict[str, int] = {}
    for archive_name in candidate_archives:
        archive_key = archive_name.lower()
        for load_order, plugin_name, patterns in plugin_patterns:
            if not any(pattern.fullmatch(archive_name) for pattern in patterns):
                continue
            previous_order = claim_orders.get(archive_key)
            if previous_order is None or load_order < previous_order:
                attachments[archive_key] = plugin_name
                claim_orders[archive_key] = load_order
            break
    return attachments


def _strip_plugin_suffix(plugin_name: str) -> str:
    for suffix in (".esp", ".esm", ".esl"):
        if plugin_name.lower().endswith(suffix):
            return plugin_name[: -len(suffix)]
    return plugin_name
