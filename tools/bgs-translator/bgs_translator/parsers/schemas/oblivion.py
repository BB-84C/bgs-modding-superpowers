"""Oblivion parser schema ownership."""

from __future__ import annotations

from ._base import YAMLBackedSchema


class OblivionSchema(YAMLBackedSchema):
    """YAML-backed Oblivion schema."""

    def __init__(self) -> None:
        super().__init__("Oblivion", "oblivion")


__all__ = ["OblivionSchema"]
