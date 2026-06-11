"""Starfield parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class StarfieldSchema(YAMLBackedSchema):
    """YAML-backed Starfield schema."""

    def __init__(self) -> None:
        super().__init__("Starfield", "starfield")


__all__ = ["StarfieldSchema"]
