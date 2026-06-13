"""mo2-assets CLI app.

Subcommands:
    summary             mod-vs-mod overview (matches MO2 left-pane shape)
    mod-conflicts NAME  per-mod 3-section report (matches MO2 dialog)
    resolve-file PATH   winner + losers for one VFS path
    archive-inventory NAME  every BA2/BSA member contributed by a mod
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from ..archive_order import Game, discover_archives_for_plugins
from ..conflict_resolver import ConflictResolver, resolve_all_winners
from ..mod_enumerator import enumerate_mod_files
from ..profile import read_profile
from ..types import FileEntry, Mod
from .output import (
    archive_entry_to_dict,
    conflict_report_to_dict,
    mod_summary_to_dict,
    render_summary_human,
    resolved_winner_to_dict,
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
) -> tuple[list[Mod], dict[str, list[FileEntry]]]:
    profile = read_profile(profile_dir=profile_dir, mods_root=mods_root)
    candidate_archives: list[str] = []
    for mod in profile.enabled_mods:
        if mod.root.exists():
            candidate_archives.extend(
                child.name
                for child in mod.root.iterdir()
                if child.is_file() and child.suffix.lower() in (".bsa", ".ba2")
            )
    archive_order = discover_archives_for_plugins(
        plugins=profile.enabled_plugins,
        candidate_archives=candidate_archives,
        game=game,
    )
    entries_by_mod: dict[str, list[FileEntry]] = {
        mod.name: enumerate_mod_files(mod=mod, archive_order=archive_order)
        for mod in profile.enabled_mods
    }
    return profile.enabled_mods, entries_by_mod


@app.command()
def summary(
    profile: ProfileOpt,
    mods: ModsOpt = None,
    game: GameOpt = Game.SKYRIM,
    output_format: FormatOpt = OutputFormat.HUMAN,
) -> None:
    """Mod-vs-mod overview."""
    mods_root = _resolve_mods_root(profile, mods)
    enabled_mods, entries_by_mod = _build_world(profile, mods_root, game)
    winners = resolve_all_winners(mods=enabled_mods, entries_by_mod=entries_by_mod)

    rows: list[dict[str, Any]] = []
    for mod in enabled_mods:
        entries = entries_by_mod.get(mod.name, [])
        conflicts = sum(
            1
            for e in entries
            if winners[e.relative_path].bucket.value != "no-conflict"
        )
        rows.append(mod_summary_to_dict(mod, total_files=len(entries), total_conflicts=conflicts))

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
    enabled_mods, entries_by_mod = _build_world(profile, mods_root, game)
    resolver = ConflictResolver(mods=enabled_mods, entries_by_mod=entries_by_mod)
    report = resolver.report_for_mod(mod_name)
    payload = conflict_report_to_dict(report)

    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"== {mod_name} ==")
        typer.echo(f"kept ({len(payload['kept'])}):")
        for k in payload["kept"]:
            typer.echo(
                f"  + {k['path']}  (vs {', '.join(loser['owner_mod'] for loser in k['losers'])})"
            )
        typer.echo(f"overwritten ({len(payload['overwritten'])}):")
        for o in payload["overwritten"]:
            typer.echo(f"  - {o['path']}  (by {o['winner']['owner_mod']})")
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
    enabled_mods, entries_by_mod = _build_world(profile, mods_root, game)
    winners = resolve_all_winners(mods=enabled_mods, entries_by_mod=entries_by_mod)
    normalized = path.replace("\\", "/").lower()
    winner = winners.get(normalized)
    if winner is None:
        if output_format is OutputFormat.JSON:
            typer.echo(json.dumps({"path": normalized, "winner": None, "losers": []}))
        else:
            typer.echo(f"{normalized}: not contributed by any enabled mod")
        return
    payload = resolved_winner_to_dict(winner)
    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"{payload['path']} -> {payload['winner']['owner_mod']} [{payload['bucket']}]")
        for loser in payload["losers"]:
            typer.echo(f"  loses: {loser['owner_mod']}")


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
    _enabled_mods, entries_by_mod = _build_world(profile, mods_root, game)
    archives: dict[str, dict[str, Any]] = {}
    for entry in entries_by_mod.get(mod_name, []):
        if entry.archive is None:
            continue
        key = entry.archive.name
        archives.setdefault(
            key,
            {**archive_entry_to_dict(entry.archive), "members": []},
        )
        archives[key]["members"].append(entry.relative_path)

    archive_rows: list[dict[str, Any]] = list(archives.values())
    payload: dict[str, Any] = {"mod": mod_name, "archives": archive_rows}
    if output_format is OutputFormat.JSON:
        typer.echo(json.dumps(payload, indent=2))
    else:
        if not payload["archives"]:
            typer.echo(f"{mod_name}: no archives")
            return
        for arc in payload["archives"]:
            typer.echo(f"-- {arc['name']} [{arc['kind']}] load_order={arc['load_order']} --")
            for member in arc["members"]:
                typer.echo(f"  {member}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
