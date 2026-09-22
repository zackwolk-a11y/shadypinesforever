#!/usr/bin/env python3
"""Bridge-owned, mechanically-restricted test execution for Level-1 rounds.

Closes the gap the 2026-09-10 acceptance run exposed: `.venv` is (correctly)
excluded from every Level-1 workspace and `python3`/`.venv/bin/python` are
(correctly) absent from Claude's allowlist there — see the HARD SAFETY
BOUNDARY comment in director_bridge.py for why both of those are real
security fixes, not oversights. That left no way for a Level-1 round to
actually execute `scripts/test_fishbowl.py`, only to edit it.

This script is the fix, and it is deliberately NOT "give Claude python3
back." Claude never gets to construct or vary the test-invocation command
at all: director_bridge.py builds ONE EXACT (no `:*` wildcard) Bash
permission string per allowlisted target — e.g.
`Bash(/real/repo/.venv/bin/python scripts/director_bridge_test_runner.py --target scripts/test_fishbowl.py)`
— so the only way to reach this script through the sandboxed Bash tool is
to reproduce that literal command byte-for-byte. There is no flag, target,
or shell metacharacter Claude can add: any deviation fails the exact-string
match and is denied at the permission layer before this file ever runs.

Everything below is a SECOND, independent layer of the same restriction —
defense in depth, not the only thing standing between Claude and arbitrary
code, in case this script is ever reached some other way (direct
inspection, a future refactor, a permission-layer regression):

  - `--target` must be an exact member of ALLOWED_TEST_TARGETS (module-
    level, hardcoded, not read from any file, not the CLI's problem to
    enumerate). No globs, no pytest node-id syntax, no directories.
  - The resolved target path is verified to stay inside cwd (no `..`,
    no absolute-path escape).
  - cwd is verified to NOT be the real repository — this script only ever
    runs meaningfully inside a disposable Level-1 workspace clone.
  - The interpreter that reaches main() is verified to be the real repo's
    own `.venv/bin/python` — the one interpreter this script is allowed to
    delegate to for the actual test subprocess (reused via `sys.executable`,
    never re-resolved from PATH).
  - The test subprocess's environment is built from an ALLOWLIST of names,
    never by filtering os.environ — nothing new added to this process's
    own environment leaks in by omission. VILLAGE_DATA_ROOT is pointed at
    a fixture directory inside the workspace itself, never left to any
    ambient value. No `.env`-sourced value, API key, or DATABASE_URL is
    ever placed in it (every approved target is required to set its own
    throwaway sqlite DATABASE_URL before importing app/ — see
    scripts/test_fishbowl.py's own header comment for the existing
    convention this relies on).
  - The subprocess runs with a bounded timeout and is never retried.

Result contract: a single JSON object is printed to stdout (so Claude's own
Bash tool_use result — and therefore its summary — reflects the real
outcome) AND written to `<cwd>/.director/level1_test_result.json`. That
second copy is what director_bridge.py's run_once() reads back directly,
mechanically, after Claude's turn ends — never inferred from Claude's own
prose. `.director/` inside a Level-1 workspace is already excluded from
every changed-files/diff computation in director_bridge.py
(_workspace_dirty_files' own `.director/` filter), so this bookkeeping file
never pollutes the round's diff or the durable patch.

Usage (as constructed by director_bridge.py — never hand-typed by Claude):

    /real/repo/.venv/bin/python scripts/director_bridge_test_runner.py \\
        --target scripts/test_fishbowl.py
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

#: The ONLY test targets a Level-1 round may ever request. Exact string
#: match only — no globs, no pytest node-id syntax, no directories. Extend
#: this list deliberately, one reviewed line at a time; director_bridge.py
#: derives its allowed/disallowed Bash permission strings directly from it,
#: so adding a target here immediately (and only) grants that one path.
ALLOWED_TEST_TARGETS: tuple[str, ...] = (
    "scripts/test_fishbowl.py",
)

#: Deliberately a LITERAL absolute path, not `Path(__file__).resolve()...`.
#: This file is cloned verbatim into every Level-1 workspace (it is an
#: ordinary tracked repo file), so a __file__-relative "real repo root"
#: would resolve to the WORKSPACE itself when this script runs there —
#: silently defeating the "refuse to run against the real repo" check
#: below. The real path is hardcoded so that check stays meaningful
#: regardless of where this file is currently executing from.
REAL_REPO_ROOT = Path("/Users/zacharywolk/shadypinesforever")
REAL_HOST_PYTHON = REAL_REPO_ROOT / ".venv" / "bin" / "python"

#: Bounded and well inside director_bridge.py's own CLAUDE_LEVEL1_TIMEOUT_
#: SECONDS (1200s) for the whole round, leaving headroom for the edit turns
#: around it.
_TEST_SUBPROCESS_TIMEOUT_SECONDS = 240

#: Allowlist, not denylist, for the test subprocess's environment — every
#: other approach filters os.environ and therefore silently admits whatever
#: gets added to *this* process's own environment tomorrow. Only names that
#: are structurally necessary for a Python subprocess to run at all.
_ENV_PASSTHROUGH_NAMES = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TERM")


class RunnerError(RuntimeError):
    """A refusal this script makes on purpose — never a bug to fix by
    catching it more broadly; every raise site below is a specific,
    intentional safety boundary."""


def _sanitized_env(workspace: Path) -> dict[str, str]:
    env = {name: os.environ[name] for name in _ENV_PASSTHROUGH_NAMES if name in os.environ}
    env["APP_ENV"] = "development"
    env.setdefault("LLM_PROVIDER", "fixture")
    env.setdefault("RESEARCH_PROVIDER", "fixture")
    # Fixture-only, entirely inside the disposable workspace: never the
    # canonical live path (/Users/zacharywolk/village-data/...), never the
    # real repo's own data/ directory. Approved targets are expected to set
    # their own throwaway DATABASE_URL (scripts/test_fishbowl.py does) —
    # this is the belt-and-suspenders default for whatever app code reads
    # VILLAGE_DATA_ROOT directly before that happens.
    env["VILLAGE_DATA_ROOT"] = str(workspace / ".director_bridge_test_fixture" / "village_data")
    return env


def _validate_target(raw_target: str, workspace: Path) -> Path:
    if raw_target not in ALLOWED_TEST_TARGETS:
        raise RunnerError(
            f"target {raw_target!r} is not on the approved allowlist {ALLOWED_TEST_TARGETS!r}"
        )
    candidate = (workspace / raw_target).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError:
        raise RunnerError(f"target {raw_target!r} resolves outside the workspace") from None
    if not candidate.is_file():
        raise RunnerError(f"target {raw_target!r} does not exist in this workspace")
    return candidate


def _validate_environment(workspace: Path) -> None:
    if workspace.resolve() == REAL_REPO_ROOT.resolve():
        raise RunnerError(
            "refusing to run: cwd is the real repository root, not an isolated Level-1 workspace"
        )
    actual_interpreter = Path(sys.executable).resolve()
    expected_interpreter = REAL_HOST_PYTHON.resolve()
    if actual_interpreter != expected_interpreter:
        raise RunnerError(
            f"refusing to run: launched with interpreter {actual_interpreter}, "
            f"expected the real repo's own {expected_interpreter}"
        )


def _write_result(workspace: Path, result: dict) -> None:
    marker_dir = workspace / ".director"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "level1_test_result.json").write_text(json.dumps(result, indent=2))


def run(raw_target: str, workspace: Path) -> dict:
    _validate_environment(workspace)
    target_path = _validate_target(raw_target, workspace)

    cmd = [sys.executable, str(target_path)]
    env = _sanitized_env(workspace)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=str(workspace), env=env, capture_output=True, text=True,
            timeout=_TEST_SUBPROCESS_TIMEOUT_SECONDS,
        )
        return {
            "ok": True,
            "target": raw_target,
            "exit_code": proc.returncode,
            "timed_out": False,
            "duration_seconds": time.monotonic() - started,
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-20000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": True,
            "target": raw_target,
            "exit_code": None,
            "timed_out": True,
            "duration_seconds": time.monotonic() - started,
            "stdout": (exc.stdout or "")[-20000:] if isinstance(exc.stdout, str) else "",
            "stderr": f"timed out after {_TEST_SUBPROCESS_TIMEOUT_SECONDS}s",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge-controlled Level-1 test runner.")
    parser.add_argument("--target", required=True)
    args = parser.parse_args()

    workspace = Path.cwd()
    try:
        result = run(args.target, workspace)
    except RunnerError as exc:
        result = {"ok": False, "target": args.target, "error": str(exc)}
        print(json.dumps(result))
        try:
            _write_result(workspace, result)
        except OSError:
            pass
        return 2

    print(json.dumps(result))
    try:
        _write_result(workspace, result)
    except OSError:
        pass
    return 0 if (result["exit_code"] == 0 and not result["timed_out"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
