"""Shared dataclasses for mo2-assets-engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Mod:
    name: str
    priority: int
    enabled: bool
    root: Path
