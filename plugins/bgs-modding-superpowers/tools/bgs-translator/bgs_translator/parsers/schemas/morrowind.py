"""Morrowind parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class MorrowindSchema(YAMLBackedSchema):
    """YAML-backed Morrowind TES3 schema for inline XML dictionary output."""

    def __init__(self) -> None:
        super().__init__("Morrowind", "morrowind")


__all__ = ["MorrowindSchema"]
