#!/usr/bin/env python3
"""CLI entry point for the Director Safe Execution Broker.

This is the ONLY shape a routine Director/Claude-Code invocation should
ever take from here on:

    .venv/bin/python scripts/director_broker_cli.py \\
        --capability LIVE_DB_FINGERPRINT --params-file /tmp/params.json

Parameters are always read from a JSON file, never inlined on the command
line — this sidesteps shell-quoting/heredoc problems entirely (the actual
source of the earlier interactive-approval friction) rather than relying
on discipline to avoid them. ``--params-json`` exists only for the
simplest, quote-free flat parameter sets and is never required.

This script performs no logic of its own beyond argument parsing and
printing the result: all validation and execution happens inside
``director_broker.execute()``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import director_broker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability", required=True, help="One of the closed Capability catalog names")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--params-file", help="Path to a JSON file of parameters (preferred)")
    group.add_argument("--params-json", help="Inline JSON parameters (only for simple, quote-free values)")
    parser.add_argument("--director-round-id", default=None)
    args = parser.parse_args()

    if args.params_file:
        params = json.loads(Path(args.params_file).read_text())
    elif args.params_json:
        params = json.loads(args.params_json)
    else:
        params = {}

    result = director_broker.execute(
        args.capability, params, director_round_id=args.director_round_id,
    )
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0 if result.status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
