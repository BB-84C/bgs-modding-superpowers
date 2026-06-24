#!/usr/bin/env python3
# Generalized from BB84's make_mods_from_cc.py.
"""Install Creation Club payloads from MO2 overwrite as individual MO2 mods."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path


GAME_NAMES = {
    "skyrimse": "Skyrim",
    "fallout4": "Fallout4",
    "starfield": "Starfield",
}


def log(message: str) -> None:
    print(message, file=sys.stderr)


def extract_prefix(filename: str) -> str | None:
    """Return the CC file group prefix from known Bethesda CC filename shapes."""
    path = Path(filename)
    stem = path.stem

    if path.suffix.lower() == ".esm":
        return stem

    if " - " in stem:
        prefix, _rest = stem.split(" - ", 1)
        prefix = prefix.strip()
        return prefix or None

    return None


def write_meta_ini(folder: Path, game_name: str, dry_run: bool) -> bool:
    meta_path = folder / "meta.ini"
    if meta_path.exists():
        log(f"[WARN] meta.ini already exists, leaving unchanged: {meta_path}")
        return False

    content = f"[General]\ngameName={game_name}\nmodid=0\n[installedFiles]\nsize=0\n"
    if dry_run:
        log(f"[DRY-RUN] Would write minimal meta.ini: {meta_path}")
        return True

    meta_path.write_text(content, encoding="utf-8", newline="\n")
    log(f"[OK] Wrote meta.ini: {meta_path}")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Copy Creation Club files from an MO2 overwrite/source directory into one MO2 mod folder per detected CC prefix.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python scripts/install-cc-as-mods.py --mo2-root "D:/Starfield MO2" --game starfield --dry-run
  python scripts/install-cc-as-mods.py --mo2-root "D:/MO2-Skyrim" --game skyrimse --suffix "-creation"
  python scripts/install-cc-as-mods.py --mo2-root "D:/MO2-FO4" --game fallout4 --source-dir "D:/MO2-FO4/overwrite" --target-dir "D:/MO2-FO4/mods"

Detected filename shapes:
  <prefix>.esm
  <prefix> - main.ba2
  <prefix> - <anything>.<ext>
""",
    )
    parser.add_argument("--mo2-root", required=True, type=Path, help="MO2 instance root.")
    parser.add_argument("--source-dir", type=Path, help="Source directory. Defaults to <mo2-root>/overwrite.")
    parser.add_argument("--target-dir", type=Path, help="Target mods directory. Defaults to <mo2-root>/mods.")
    parser.add_argument("--dry-run", action="store_true", help="Print intended actions without creating folders or copying files.")
    parser.add_argument("--suffix", default="-cc", help="Suffix appended to each detected prefix for the created mod folder. Default: -cc")
    parser.add_argument("--game", choices=sorted(GAME_NAMES), required=True, help="Game label to write into generated meta.ini.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    mo2_root = args.mo2_root.expanduser()
    source_dir = (args.source_dir or (mo2_root / "overwrite")).expanduser()
    target_dir = (args.target_dir or (mo2_root / "mods")).expanduser()
    game_name = GAME_NAMES[args.game]

    if not source_dir.exists() or not source_dir.is_dir():
        log(f"[ERROR] Source directory does not exist: {source_dir}")
        return 1

    if target_dir.exists() and not target_dir.is_dir():
        log(f"[ERROR] Target path exists but is not a directory: {target_dir}")
        return 1

    if not target_dir.exists():
        if args.dry_run:
            log(f"[DRY-RUN] Would create target directory: {target_dir}")
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            log(f"[OK] Created target directory: {target_dir}")

    file_groups: dict[str, list[Path]] = defaultdict(list)
    ignored = 0
    for entry in sorted(source_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_file() or entry.name.endswith(".mohidden"):
            ignored += 1
            continue
        prefix = extract_prefix(entry.name)
        if prefix is None:
            ignored += 1
            continue
        file_groups[prefix].append(entry)

    if ignored:
        log(f"[INFO] Ignored {ignored} non-matching, hidden, or non-file entries.")

    groups_created = 0
    files_copied = 0
    files_skipped = 0
    groups_summary: list[dict[str, object]] = []

    for prefix, files in sorted(file_groups.items(), key=lambda item: item[0].lower()):
        dest_dir = target_dir / f"{prefix}{args.suffix}"
        folder_exists = dest_dir.exists()

        if not folder_exists:
            groups_created += 1
            if args.dry_run:
                log(f"[DRY-RUN] Would create mod folder: {dest_dir}")
            else:
                dest_dir.mkdir(parents=True, exist_ok=False)
                log(f"[OK] Created mod folder: {dest_dir}")
            write_meta_ini(dest_dir, game_name, args.dry_run)

        copied_for_group: list[str] = []
        for file_path in files:
            dest_file = dest_dir / file_path.name
            if dest_file.exists():
                files_skipped += 1
                log(f"[WARN] Destination exists, skipping: {dest_file}")
                continue

            if args.dry_run:
                log(f"[DRY-RUN] Would copy: {file_path} -> {dest_file}")
            else:
                shutil.copy2(file_path, dest_file)
                log(f"[OK] Copied: {file_path.name} -> {dest_dir}")
            files_copied += 1
            copied_for_group.append(str(dest_file))

        groups_summary.append({"prefix": prefix, "folder": str(dest_dir), "files": copied_for_group})

    summary = {
        "ok": True,
        "groups_created": groups_created,
        "files_copied": files_copied,
        "files_skipped": files_skipped,
        "groups": groups_summary,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
