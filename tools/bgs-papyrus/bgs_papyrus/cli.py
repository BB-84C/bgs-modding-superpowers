import argparse
import sys

from . import caps, model


def main(argv=None):
    p = argparse.ArgumentParser(prog="bgs-papyrus")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    capabilities = sub.add_parser("capabilities")
    capabilities.add_argument("--json", action="store_true", dest="json")
    args = p.parse_args(argv)
    try:
        if args.command == "capabilities":
            env = caps.run()
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
