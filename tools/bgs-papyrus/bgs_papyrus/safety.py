from __future__ import annotations

from pathlib import Path


def is_protected_game_path(p) -> bool:
    parts = [part.lower() for part in Path(p).resolve(strict=False).parts]
    return _contains_game_data(parts, ("steamapps", "common")) or _contains_game_data(parts, ("stock game",))


def _contains_game_data(parts: list[str], prefix: tuple[str, ...]) -> bool:
    width = len(prefix)
    for index in range(0, len(parts) - width - 1):
        if tuple(parts[index : index + width]) != prefix:
            continue
        game_index = index + width
        data_index = game_index + 1
        if data_index < len(parts) and parts[data_index] == "data":
            return True
    return False
