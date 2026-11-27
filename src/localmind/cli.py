"""Small, headless-safe command-line entry point."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .paths import AppPaths, default_paths


def _print_paths(paths: AppPaths) -> int:
    print(f"Config:  {paths.config}")
    print(f"Data:    {paths.data_dir}")
    print(f"Cache:   {paths.cache_dir}")
    print(f"Storage: {paths.storage}")
    print(f"Vault:   {paths.vault}")
    return 0


def _doctor(paths: AppPaths) -> int:
    from .config import Config
    from .rag import check_ollama

    problems: list[str] = []
    try:
        paths.ensure_base_dirs()
    except OSError as exc:
        problems.append(f"LocalMind data directories are not writable: {exc}")
    try:
        import tkinter  # noqa: F401
    except ImportError:
        problems.append("Tkinter is missing. Install the Tk package supplied by your Python or OS.")
    problems.extend(check_ollama(Config.load(paths.config)))
    if problems:
        print("LocalMind is not ready:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("LocalMind is ready.")
    return 0


def _launch(paths: AppPaths) -> int:
    try:
        from .app import App
        app = App(paths)
    except ImportError as exc:
        if exc.name == "tkinter":
            print("Tkinter is missing. Install the Tk package supplied by your Python or OS.", file=sys.stderr)
            return 1
        raise
    except Exception as exc:
        if exc.__class__.__name__ == "TclError":
            print(f"LocalMind could not open a desktop window: {exc}", file=sys.stderr)
            return 1
        raise
    app.mainloop()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="localmind")
    parser.add_argument("--version", action="version", version=f"LocalMind {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("paths", help="show LocalMind's user-owned files")
    sub.add_parser("doctor", help="check local setup and models")
    args = parser.parse_args(argv)
    paths = default_paths()
    if args.command == "paths":
        return _print_paths(paths)
    if args.command == "doctor":
        return _doctor(paths)
    return _launch(paths)
