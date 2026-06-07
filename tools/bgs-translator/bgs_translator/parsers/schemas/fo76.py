"""Fallout 76 parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class FO76Schema(YAMLBackedSchema):
    """YAML-backed Fallout 76 schema."""

    def __init__(self) -> None:
        super().__init__("Fallout76", "fo76")


__all__ = ["FO76Schema"]
