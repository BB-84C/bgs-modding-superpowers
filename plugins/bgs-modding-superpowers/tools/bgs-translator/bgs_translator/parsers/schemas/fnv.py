"""Fallout: New Vegas parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class FNVSchema(YAMLBackedSchema):
    """YAML-backed Fallout: New Vegas schema."""

    def __init__(self) -> None:
        super().__init__("FalloutNV", "fnv")


__all__ = ["FNVSchema"]
