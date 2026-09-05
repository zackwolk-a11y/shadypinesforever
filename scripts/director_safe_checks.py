#!/usr/bin/env python3
"""Director safe-check entrypoint -- the ONE routine verification command.

    .venv/bin/python scripts/director_safe_checks.py

Replaces the pattern of ad hoc `python3 -c`, shell pipelines, and repeated
individual test/inspection invocations with a single, stable, auditable
command. Everything here is a direct Python/library call -- no
`subprocess.run(..., shell=True)`, no Director-supplied command string, no
arbitrary Python execution. Every live-DB touch goes through
`director_broker.execute()` (mode=ro reads only) or the existing isolated
fixture-test suites, exactly as a human running them individually already
would; this script only aggregates and reports.

Runs, in order, and fails closed (non-zero exit if anything fails):

  1. syntax checks on every Director/broker script
  2. real live DB fingerprint (read-only)
  3. real live DB integrity (read-only)
  4. real Director unattended status summary, if one exists
  5. bounded-live-window invariant spot-check (worst-case burst == 42)
  6. broker fixture test suite (adversarial + positive, in-process)
  7. isolated unattended-runner fixture test suite (subprocess-isolated
     from real data by that suite's own design, in-process orchestration)
  8. research smoke test (confirms zero production regression)
  9. final live DB re-check + summary
"""

from __future__ import annotations

import ast
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT.parent))

SECTION_RESULTS: list[tuple[str, bool, str]] = []


def record(section: str, passed: bool, detail: str = "") -> None:
    SECTION_RESULTS.append((section, passed, detail))
    print(("PASS " if passed else "FAIL "), section, ("" if passed else f"— {detail}"))


def _run_capturing(fn) -> tuple[int, str]:
    """Runs a zero-arg callable that returns an int exit code, capturing
    its stdout so this script's own output stays legible; returns
    (exit_code, captured_output)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn()
    return code, buf.getvalue()


def section_syntax_checks() -> None:
    print("\n=== 1. Syntax checks ===")
    targets = [
        "director_broker.py",
        "director_broker_cli.py",
        "director_broker_fixturetest.py",
        "director_unattended.py",
        "director_unattended_fixturetest.py",
        "director_diagnostics.py",
        "director_experiments.py",
    ]
    all_ok = True
    for name in targets:
        path = REPO_ROOT / name
        if not path.exists():
            record(f"syntax: {name}", False, "file not found")
            all_ok = False
            continue
        try:
            ast.parse(path.read_text())
            record(f"syntax: {name}", True)
        except SyntaxError as exc:
            record(f"syntax: {name}", False, str(exc))
            all_ok = False
    return all_ok


def section_live_db_status() -> dict | None:
    print("\n=== 2/3/9. Real live DB fingerprint + integrity (read-only) ===")
    import director_broker as broker

    fp = broker.execute("LIVE_DB_FINGERPRINT", {})
    record("live DB fingerprint call succeeds", fp.status == "SUCCESS", fp.failure_reason or "")
    integ = broker.execute("CHECK_LIVE_DB_INTEGRITY", {})
    record("live DB integrity check succeeds", integ.status == "SUCCESS" and integ.result.get("healthy") is True, str(integ.result))

    if fp.status == "SUCCESS":
        r = fp.result
        print(
            f"    max_event_id={r.get('max_event_id')} day={r.get('current_day')} "
            f"period={r.get('current_period')} paused={r.get('is_paused')} "
            f"sha256={r.get('sha256')}"
        )
        return r
    return None


def section_director_status() -> None:
    print("\n=== 4. Real Director unattended status ===")
    status_path = REPO_ROOT.parent / ".director" / "unattended_status.json"
    if not status_path.exists():
        print("    no unattended_status.json on disk -- runner has never launched for real yet.")
        record("Director status readable (or absent, which is fine)", True)
        return
    import json
    try:
        status = json.loads(status_path.read_text())
        print(
            f"    state={status.get('state')} completed={status.get('completed_task_count')} "
            f"live_events_added_total={status.get('live_events_added_total')} "
            f"max_live_event_baseline={status.get('max_live_event_baseline')} "
            f"provider_calls_used={status.get('provider_calls_used')} "
            f"stop_reason={status.get('stop_reason')}"
        )
        record("Director status file parses correctly", True)
    except Exception as exc:  # noqa: BLE001
        record("Director status file parses correctly", False, str(exc))


def section_bounded_window_invariant() -> None:
    print("\n=== 5. Bounded-live-window invariant spot-check ===")
    import director_broker as broker
    from app.core.config import get_settings

    wc = broker._derive_worst_case_activation_burst(get_settings())
    record("worst-case activation burst is the proven value (42)", wc == 42, f"got {wc}")
    record(
        "RunBoundedLiveWindowParams ceiling matches the current night policy (50)",
        broker.RunBoundedLiveWindowParams.model_fields["max_new_events"].metadata[-1].le == 50,
        "checked live field constraint",
    )


def section_broker_fixture_suite() -> bool:
    print("\n=== 6. Broker fixture test suite (adversarial + positive) ===")
    import director_broker_fixturetest as suite
    code, output = _run_capturing(suite.main)
    last_line = [line for line in output.splitlines() if line.strip()][-1] if output.strip() else ""
    record("director_broker_fixturetest.py", code == 0, last_line)
    if code != 0:
        print(output[-3000:])
    return code == 0


def section_unattended_fixture_suite() -> bool:
    print("\n=== 7. Isolated unattended-runner fixture test suite ===")
    import os
    if not os.environ.get("VILLAGE_DATA_ROOT"):
        record(
            "isolated unattended-runner suite",
            False,
            "VILLAGE_DATA_ROOT is not set in this process -- the suite's own "
            "real-live-DB before/after check would silently no-op against the "
            "wrong path. Export VILLAGE_DATA_ROOT to the real value before "
            "running this entrypoint.",
        )
        return False
    import director_unattended_fixturetest as suite
    code, output = _run_capturing(suite.main)
    last_line = [line for line in output.splitlines() if line.strip()][-1] if output.strip() else ""
    record("director_unattended_fixturetest.py", code == 0, last_line)
    if code != 0:
        print(output[-3000:])
    return code == 0


def section_research_smoke_test() -> bool:
    print("\n=== 8. Research smoke test (production regression check) ===")
    import os
    import subprocess
    # This process may already have loaded .env (via director_broker's own
    # module-level dotenv load in an earlier section), which would leak a
    # real RESEARCH_PROVIDER=tavily into an inherited environment. The
    # smoke test explicitly requires both providers on 'fixture' (or
    # unset) -- give it a clean override rather than relying on whatever
    # this process happens to have accumulated.
    env = dict(os.environ)
    env["LLM_PROVIDER"] = "fixture"
    env["RESEARCH_PROVIDER"] = "fixture"
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "smoke_test_research.py")],
        cwd=REPO_ROOT.parent, env=env, capture_output=True, text=True, timeout=120,
    )
    record("smoke_test_research.py", proc.returncode == 0, proc.stdout[-500:] + proc.stderr[-500:])
    return proc.returncode == 0


def main() -> int:
    all_ok = True

    all_ok &= section_syntax_checks()
    fingerprint_before = section_live_db_status()
    section_director_status()
    section_bounded_window_invariant()
    all_ok &= section_broker_fixture_suite()
    all_ok &= section_unattended_fixture_suite()
    all_ok &= section_research_smoke_test()

    print("\n=== 9. Final live DB re-check ===")
    fingerprint_after = section_live_db_status()
    if fingerprint_before and fingerprint_after:
        record(
            "live DB hash unchanged across this entire safe-check run",
            fingerprint_before["sha256"] == fingerprint_after["sha256"],
            f"before={fingerprint_before['sha256']} after={fingerprint_after['sha256']}",
        )
        record(
            "live DB max_event_id unchanged across this entire safe-check run",
            fingerprint_before["max_event_id"] == fingerprint_after["max_event_id"],
            f"before={fingerprint_before['max_event_id']} after={fingerprint_after['max_event_id']}",
        )

    print()
    passed = sum(1 for _, ok, _ in SECTION_RESULTS if ok)
    total = len(SECTION_RESULTS)
    print(f"{passed}/{total} check groups passed.")
    return 0 if all_ok and passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
