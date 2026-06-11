"""Skyrim LE parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class SkyrimLESchema(YAMLBackedSchema):
    """YAML-backed Skyrim LE schema."""

    def __init__(self) -> None:
        super().__init__("SkyrimLE", "skyrim_le")


__all__ = ["SkyrimLESchema"]
