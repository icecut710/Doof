"""DOOF Training Worker — CLI entry point.

Registers as a compute node, sends periodic heartbeats, and polls
for training jobs assigned by the scheduler.  The strongest worker
(highest VRAM) receives each job.

Usage::

    python scripts/worker.py [--name NAME] [--api URL]
    python -m doof worker [--name NAME] [--api URL]
"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="doof-worker",
        description="DOOF v0.2 training worker — pulls jobs and trains",
    )
    parser.add_argument(
        "--name", default=None, help="Worker node name (default: hostname)"
    )
    parser.add_argument(
        "--api", default=None,
        help="API base URL for heartbeat reporting (optional; default: db-direct)",
    )
    args = parser.parse_args(argv)

    from doof.training import run_worker
    run_worker(node_name=args.name, api_base=args.api)
    return 0


if __name__ == "__main__":
    sys.exit(main())
