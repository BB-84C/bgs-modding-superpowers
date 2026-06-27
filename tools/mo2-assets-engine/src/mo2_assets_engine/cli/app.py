"""mo2-assets CLI app.

Subcommands:
    summary             mod attribution overview
    mod-conflicts NAME  attribution-filtered conflict report
    resolve-file PATH   winner + losers for one VFS path
    archive-inventory NAME  every BA2/BSA member contributed by a mod
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from ..archive_order import Game
from ..conflict_resolver import resolve_tree
from ..mod_enumerator import enumerate_archive_member_paths
from ..profile import read_profile
from ..types import Mod
from ..virtual_data_tree import SourceType, VirtualDataTree, build_virtual_data_tree
from .output import (
    mod_summary_to_dict,
    render_summary_human,
    resolved_file_to_dict,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)


class OutputFormat(StrEnum):
    HUMAN = "human"
    JSON = "json"


ProfileOpt = Annotated[Path, typer.Option("--profile", help="MO2 profile directory")]
ModsOpt = Annotated[
    Path | None,
    typer.Option("--mods", help="MO2 mods root (default: <profile>/../../mods)"),
]
GameOpt = Annotated[Game, typer.Option("--game", help="Target game")]
FormatOpt = Annotated[OutputFormat, typer.Option("--format", help="Output format")]


def _resolve_mods_root(profile: Path, mods: Path | None) -> Path:
    if mods is not None:
        return mods
    return profile.parent.parent / "mods"


def _build_world(
    profile_dir: Path, mods_root: Path, game: Game
) -> VirtualDataTree:
    profile = read_profile(profile_dir=profile_dir, mods_root=mods_root)
    return build_virtual_data_tree(profile=profile, game=game)


def _providers_for_mod(tree: VirtualDataTree, mod_name: str) -> dict[str, list[Any]]:
    return {
        path: [provider for provider in providers if provider.source_mod == mod_name]
        for path, providers in tree.file_providers.items()
        if any(provider.source_mod == mod_name for provider in providers)
    }


def _report_for_mod(tree: VirtualDataTree, mod_name: str) -> dict[str, Any]:
    resolved = resolve_tree(tree)
    paths = sorted(_providers_for_mod(tree, mod_name))
    kept: list[dict[str, Any]] = []
    overwritten: list[dict[str, Any]] = []
    no_conflict: list[str] = []
    for path in paths:
        item = resolved[path]
        if not item.is_conflict:
            no_conflict.append(path)
        elif item.winner.source_mod == mod_name:
            kept.append(resolved_file_to_dict(item))
        else:
            overwritten.append(resolved_file_to_dict(item))
    return {
        "mod": mod_name,
        "kept": kept,
        "overwritten": overwritten,
        "no_conflict": no_conflict,
    }


@app.command()
def summary(
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """Mod-vs-mod overview."""
    mods_root = _resolve_mods_root(profile, mods)
    tree = _build_world(profile, mods_root, game)
    resolved = resolve_tree(tree)

    rows: list[dict[str, Any]] = []
    mods_by_name: dict[str, Mod] = {mod.name: mod for mod in read_profile(profile_dir=profile, mods_root=mods_root).enabled_mods}
    for mod_name, mod in mods_by_name.items():
        paths = _providers_for_mod(tree, mod_name)
        conflicts = sum(1 for path in paths if resolved[path].is_conflict)
        rows.append(mod_summary_to_dict(mod, total_files=len(paths), total_conflicts=conflicts))

    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps({"mods": rows}, indent=2))
    else:
        typer.echo(render_summary_human(rows))


@app.command("mod-conflicts")
def mod_conflicts(
    mod_name: Annotated[str, typer.Argument()],
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """3-section conflict report for one mod."""
    mods_root = _resolve_mods_root(profile, mods)
    tree = _build_world(profile, mods_root, game)
    payload = _report_for_mod(tree, mod_name)

    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"== {mod_name} ==")
        typer.echo(f"kept ({len(payload['kept'])}):")
        for k in payload["kept"]:
            typer.echo(
                f"  + {k['path']}  (vs {', '.join(loser['mod'] for loser in k['losers'])})"
            )
        typer.echo(f"overwritten ({len(payload['overwritten'])}):")
        for o in payload["overwritten"]:
            typer.echo(f"  - {o['path']}  (by {o['winner']['mod']})")
        typer.echo(f"no_conflict ({len(payload['no_conflict'])}):")
        for path in payload["no_conflict"]:
            typer.echo(f"    {path}")


@app.command("resolve-file")
def resolve_file(
    path: Annotated[str, typer.Argument()],
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """Resolve the winner for a single VFS path."""
    mods_root = _resolve_mods_root(profile, mods)
    tree = _build_world(profile, mods_root, game)
    winners = resolve_tree(tree)
    normalized = path.replace("\\", "/").lower()
    winner = winners.get(normalized)
    if winner is None:
        if output_format is OutputFormat.JSON:
            typer.echo(json.dumps({"path": normalized, "winner": None, "losers": []}))
        else:
            typer.echo(f"{normalized}: not contributed by any enabled mod")
        return
    payload = resolved_file_to_dict(winner)
    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"{payload['path']} -> {payload['winner']['mod']}")
        for loser in payload["losers"]:
            typer.echo(f"  loses: {loser['mod']}")


@app.command("archive-inventory")
def archive_inventory(
    mod_name: Annotated[str, typer.Argument()],
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """List every BA2/BSA member a mod contributes."""
    mods_root = _resolve_mods_root(profile, mods)
    tree = _build_world(profile, mods_root, game)
    loaded_archive_names = {
        provider.archive_name
        for providers in tree.file_providers.values()
        for provider in providers
        if provider.source_type is SourceType.ARCHIVE and provider.archive_name is not None
    }
    archives: dict[str, dict[str, Any]] = {}
    for archive in tree.archives:
        if archive.source_mod != mod_name or archive.name not in loaded_archive_names:
            continue
        archive_path = mods_root / archive.source_mod / archive.name
        archives[archive.name] = {
            "name": archive.name,
            "members": enumerate_archive_member_paths(archive_path),
        }

    archive_rows: list[dict[str, Any]] = list(archives.values())
    payload: dict[str, Any] = {"mod": mod_name, "archives": archive_rows}
    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        if not payload["archives"]:
            typer.echo(f"{mod_name}: no archives")
            return
        for arc in payload["archives"]:
            typer.echo(f"-- {arc['name']} --")
            for member in arc["members"]:
                typer.echo(f"  {member}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
