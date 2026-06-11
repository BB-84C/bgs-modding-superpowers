"""Skyrim SE/AE/VR parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class SkyrimSESchema(YAMLBackedSchema):
    """YAML-backed Skyrim SE schema, reused for AE and VR aliases."""

    def __init__(self) -> None:
        super().__init__("SkyrimSE", "skyrim_se")


__all__ = ["SkyrimSESchema"]
