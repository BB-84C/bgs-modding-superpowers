"""Resolve winners across the unified virtual Data tree."""

from __future__ import annotations

from dataclasses import dataclass

from .virtual_data_tree import Provider, SourceType, VirtualDataTree


@dataclass(frozen=True)
class ResolvedFile:
    relative_path: str
    winner: Provider
    losers: list[Provider]
    is_conflict: bool


def resolve_tree(tree: VirtualDataTree) -> dict[str, ResolvedFile]:
    """Apply BGS engine winner rules across the unified provider list."""
    resolved: dict[str, ResolvedFile] = {}
    for relative_path, providers in tree.file_providers.items():
        winner = _winner(providers)
        losers = [provider for provider in providers if provider is not winner]
        resolved[relative_path] = ResolvedFile(
            relative_path=relative_path,
            winner=winner,
            losers=losers,
            is_conflict=bool(losers),
        )
    return resolved


def _winner(providers: list[Provider]) -> Provider:
    loose = [provider for provider in providers if provider.source_type is SourceType.LOOSE]
    if loose:
        return max(loose, key=lambda provider: provider.mod_priority)
    return max(
        providers,
        key=lambda provider: (provider.attached_plugin_load_order or -1, provider.mod_priority),
    )
