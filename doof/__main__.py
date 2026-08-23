"""CLI entry point: python -m doof [serve|chat|train|gui]"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doof",
        description="DOOF v0.1 — local personal AI",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="gui",
        choices=["gui", "serve", "chat", "train", "version"],
        help="Command to run (default: gui)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="API host (serve)")
    parser.add_argument("--port", type=int, default=8765, help="API port (serve)")
    parser.add_argument(
        "--checkpoint",
        default="checkpoints/doof_v01.pt",
        help="Checkpoint path",
    )
    parser.add_argument("--epochs", type=int, default=5, help="Training epochs")
    args = parser.parse_args(argv)

    if args.command == "version":
        from doof import __version__
        print(f"DOOF v{__version__}")
        return 0

    if args.command == "serve":
        from doof.api import run_server
        run_server(host=args.host, port=args.port)
        return 0

    if args.command == "chat":
        from doof.inference import DOOFInference
        doof = DOOFInference(args.checkpoint)
        print("DOOF loaded. Type 'exit' to quit.\n")
        while True:
            try:
                prompt = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not prompt or prompt.lower() in ("exit", "quit"):
                break
            response = doof.generate(prompt, max_new_tokens=80, temperature=0.7)
            print(f"DOOF: {response}\n")
        return 0

    if args.command == "train":
        from doof.training import DOOFTrainer, TrainingConfig
        config = TrainingConfig(
            data_path="data/train.txt",
            checkpoint_dir="checkpoints",
            epochs=args.epochs,
            batch_size=8,
            seq_len=128,
            learning_rate=3e-4,
        )
        trainer = DOOFTrainer(config)
        trainer.train()
        return 0

    from doof.gui.app import main as gui_main
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
