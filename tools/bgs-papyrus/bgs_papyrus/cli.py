import argparse
import sys
from pathlib import Path

from . import caps, compile as compile_mod, decompile as decompile_mod, detect, model
from .games import Game


GAME_CHOICES = ["skyrimle", "skyrimse", "fallout4", "starfield"]


def _game(value: str) -> Game:
    return Game[value.upper()]


def _default_out(source: str) -> str:
    path = Path(source)
    return str(path.parent if path.parent != Path("") else Path.cwd())


def main(argv=None):
    p = argparse.ArgumentParser(prog="bgs-papyrus")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    capabilities = sub.add_parser("capabilities")
    capabilities.add_argument("--json", action="store_true", dest="json")

    detect_toolchain = sub.add_parser("detect-toolchain")
    detect_toolchain.add_argument("--json", action="store_true", dest="json")
    detect_toolchain.add_argument("--game", choices=GAME_CHOICES)

    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("source")
    compile_parser.add_argument("--json", action="store_true", dest="json")
    compile_parser.add_argument("--game", required=True, choices=GAME_CHOICES)
    compile_parser.add_argument("--out")
    compile_parser.add_argument("--import", action="append", dest="imports")
    compile_parser.add_argument("--backend", choices=["ck", "caprica", "russo", "auto"], default="auto")
    compile_parser.add_argument("--flags")
    compile_parser.add_argument("--optimize", action="store_true")
    compile_parser.add_argument("--release", action="store_true")
    compile_parser.add_argument("--final", action="store_true")
    compile_parser.add_argument("--all", action="store_true", dest="all_")

    decompile_parser = sub.add_parser("decompile")
    decompile_parser.add_argument("source")
    decompile_parser.add_argument("--json", action="store_true", dest="json")
    decompile_parser.add_argument("--game", required=True, choices=GAME_CHOICES)
    decompile_parser.add_argument("--out")
    decompile_parser.add_argument("--backend", choices=["champollion"], default="champollion")
    decompile_parser.add_argument("--sf-syntax-fix", action=argparse.BooleanOptionalAction, default=None)
    decompile_parser.add_argument("--recursive", action="store_true")
    decompile_parser.add_argument("--threaded", action="store_true")

    args = p.parse_args(argv)
    try:
        if args.command == "capabilities":
            env = caps.run()
        elif args.command == "detect-toolchain":
            env = detect.run(_game(args.game) if args.game else None)
        elif args.command == "compile":
            env = compile_mod.compile_run(
                _game(args.game),
                args.source,
                args.out or _default_out(args.source),
                backend=args.backend,
                imports=args.imports,
                flags=args.flags,
                all_=args.all_,
                optimize=args.optimize,
                release=args.release,
                final=args.final,
                timeout=300,
            )
        elif args.command == "decompile":
            env = decompile_mod.decompile_run(
                _game(args.game),
                args.source,
                args.out or _default_out(args.source),
                backend=args.backend,
                sf_syntax_fix=args.sf_syntax_fix,
                recursive=args.recursive,
                threaded=args.threaded,
                timeout=300,
            )
        else:
            env = model.Envelope(ok=True, command=args.command, data={})
        print(env.to_json() if args.json else env.human())
        return 0
    except Exception as e:
        env = model.Envelope(
            ok=False,
            command=getattr(args, "command", ""),
            error={"code": "internal", "message": str(e)},
        )
        print(env.to_json() if args.json else env.human(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
