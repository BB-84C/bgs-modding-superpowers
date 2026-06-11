"""Fallout 3 parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class FO3Schema(YAMLBackedSchema):
    """YAML-backed Fallout 3 schema."""

    def __init__(self) -> None:
        super().__init__("Fallout3", "fo3")


__all__ = ["FO3Schema"]
