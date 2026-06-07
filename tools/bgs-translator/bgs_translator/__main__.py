"""Module entry point for running bgs-translator with python -m."""

# TODO(Chunk-B): Keep module execution delegated to the Typer CLI root.

from bgs_translator.cli.app import main

__all__ = []

if __name__ == "__main__":
    main()
