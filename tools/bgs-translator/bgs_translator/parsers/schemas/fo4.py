"""Fallout 4 / Fallout 4 VR parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class FO4Schema(YAMLBackedSchema):
    """YAML-backed Fallout 4 schema."""

    def __init__(self) -> None:
        super().__init__("Fallout4", "fo4")


__all__ = ["FO4Schema"]
