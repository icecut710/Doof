"""CLI entry point: python -m doof [serve|chat|train|worker|gui]"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doof", description="DOOF private AI OS")
    parser.add_argument(
        "command",
        nargs="?",
        default="gui",
        choices=["serve", "chat", "train", "worker", "gui"],
        help="subcommand (default: gui)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="API bind host")
    parser.add_argument("--port", type=int, default=8765, help="API port")
    args = parser.parse_args(argv)

    if args.command == "serve":
        try:
            from doof.api_mount import install

            install()
        except Exception as e:
            print(f"[doof] api_mount: {e}")
        from doof.api import run_server

        run_server(host=args.host, port=args.port)
        return 0

    if args.command == "gui":
        try:
            from doof.api_mount import install

            install()
        except Exception as e:
            print(f"[doof] api_mount: {e}")
        from doof.gui.app import main as gui_main

        return int(gui_main() or 0)

    if args.command == "chat":
        from scripts.chat import main as chat_main  # type: ignore

        return int(chat_main() or 0)

    if args.command == "train":
        from scripts.train import main as train_main  # type: ignore

        return int(train_main() or 0)

    if args.command == "worker":
        from scripts.worker import main as worker_main  # type: ignore

        return int(worker_main() or 0)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
