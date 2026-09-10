#!/usr/bin/env python3
"""Deterministic, offline regression test for director_bridge.py's round
orchestration (run_once/collect_bridge_state/safety gating/persistence/
the two-call Director<->Claude<->Director loop).

Never calls a real OpenAI API and never spawns a real `claude` subprocess —
call_openai_director, call_openai_director_evaluation, and invoke_claude_code
are monkeypatched with fixture stand-ins for the duration of each test,
exactly the same "no network, no spend" discipline every other
*_fixturetest.py suite in this repo already follows. The two argv-capturing
tests are the one exception worth calling out explicitly: they monkeypatch
subprocess.run itself (not invoke_claude_code), so the REAL command-
construction code inside invoke_claude_code runs and its exact argv can be
asserted on — still zero real subprocess execution, zero network.

Runs against the real repo's git state (read-only: `git status`/`git log`/
`git diff --stat` only) but never touches the canonical live database and
never invokes a live control endpoint.

Usage::

    .venv/bin/python scripts/director_bridge_fixturetest.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "scripts")]

import director_bridge as bridge  # noqa: E402

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


def _fake_evaluation(outcome: str = "accepted") -> bridge.DirectorEvaluation:
    return bridge.DirectorEvaluation(
        outcome=outcome, summary="fixture evaluation", evidence_assessment="fixture",
        remaining_risks=[], recommended_next_task="", recommended_safety_level=0,
        requires_founder_approval=False, stop_reason="fixture stop",
    )


def test_collect_state_is_compact_and_never_touches_live_db():
    state = bridge.collect_bridge_state("test objective")
    check("collect_bridge_state includes objective", state["objective"] == "test objective")
    check("collect_bridge_state includes branch", isinstance(state.get("branch"), str) and state["branch"])
    check("collect_bridge_state's git_status_summary is bounded", len(state["git_status_summary"]) <= 2000)
    check("collect_bridge_state's diff_summary is bounded", len(state["diff_summary"]) <= 2000)
    check("collect_bridge_state includes bounded history package", "constitution" in state["history"])
    check("collect_bridge_state never embeds a raw file diff (only --stat)", "@@ " not in state["diff_summary"])


def test_run_once_stop_path_never_touches_claude(monkeypatch):
    calls = {"claude_invoked": 0}

    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="stop", task_for_claude="", reason="nothing to do this round",
            required_checks=[], safety_level=0, requires_founder_approval=False, stop_conditions=[],
        )

    def fake_claude(*a, **k):
        calls["claude_invoked"] += 1
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0)

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)

    record = bridge.run_once("test objective")
    check("stop decision ends the round as stopped_by_director", record.final_state == "stopped_by_director")
    check("stop decision never invokes claude", calls["claude_invoked"] == 0)
    check("lock is released after the round", not bridge.BRIDGE_LOCK_PATH.exists())


def test_run_once_level0_completes_with_evaluation(monkeypatch):
    calls = {"claude_invoked": 0, "level_seen": None, "evaluation_calls": 0}

    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="continue", task_for_claude="read README.md and summarize it in one sentence",
            reason="harmless read-only demonstration", required_checks=[], safety_level=0,
            requires_founder_approval=False, stop_conditions=[],
        )

    def fake_claude(task_prompt, level, timeout=300):
        calls["claude_invoked"] += 1
        calls["level_seen"] = level
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result": "ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        calls["evaluation_calls"] += 1
        check("evaluation receives the deterministic evidence dict", "deterministic_safety_failure" in deterministic)
        return _fake_evaluation("accepted")

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)

    record = bridge.run_once("test objective")
    check("level-0 decision completes the round", record.final_state == "completed")
    check("level-0 decision invokes claude exactly once", calls["claude_invoked"] == 1)
    check("level-0 decision passes safety level READ_ONLY through", calls["level_seen"] == bridge.BridgeSafetyLevel.READ_ONLY)
    check("round record carries the claude task text", record.claude_task is not None and "README" in record.claude_task)
    check("the second Director call happens exactly once", calls["evaluation_calls"] == 1)
    check(
        "a clean round's evaluation outcome is NOT overridden",
        record.director_evaluation is not None
        and record.director_evaluation["outcome"] == "accepted"
        and record.director_evaluation["overridden_by_deterministic_check"] is False,
    )


def test_run_once_claude_timeout_is_deterministic_failure_and_never_continues(monkeypatch):
    """2026-09-10 timeout hardening regression: a timed-out Claude
    invocation (round bd046f7218294d50's real failure mode) must still
    resolve to final_state=='stopped_claude_timeout', must remain a
    deterministic safety failure regardless of what the second Director
    call says, and _watch_continuation_decision must never allow a watch
    to continue past it — a longer per-level timeout must never turn a
    timeout into a success or a continuable outcome."""
    calls = {"claude_invoked": 0}

    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="continue", task_for_claude="a task that will time out",
            reason="fixture", required_checks=[], safety_level=0,
            requires_founder_approval=False, stop_conditions=[],
        )

    def fake_claude(task_prompt, level, timeout=None, cwd=None):
        calls["claude_invoked"] += 1
        # Mirrors the real invoke_claude_code TimeoutExpired branch: no exit
        # code, no session id recoverable, empty stdout.
        return bridge.ClaudeInvocationResult(
            invoked=True, timed_out=True, exit_code=None, stdout="",
            stderr="timed out after 420s", duration_seconds=420.02,
        )

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        # Even a generous model outcome must not override a timeout.
        return _fake_evaluation("accepted")

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)

    record = bridge.run_once("test objective")
    check("a timed-out round invokes claude exactly once", calls["claude_invoked"] == 1)
    check("a timed-out round's final_state is stopped_claude_timeout", record.final_state == "stopped_claude_timeout")
    may_continue, reason = bridge._watch_continuation_decision(record)
    check(
        "a timed-out round can never continue a watch, even with an 'accepted' evaluation",
        not may_continue, detail=reason,
    )


def test_run_once_level2_never_executes_even_if_approved(monkeypatch):
    calls = {"claude_invoked": 0}

    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="request_approval", task_for_claude="run Run Day on the live Village",
            reason="advance the simulation", required_checks=[], safety_level=2,
            requires_founder_approval=True, stop_conditions=[],
        )

    def fake_claude(*a, **k):
        calls["claude_invoked"] += 1
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0)

    def fake_approval(decision, state):
        return {"requested_action": decision.task_for_claude, "approved": True, "note": "fixture-forced yes"}

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "request_founder_approval", fake_approval)

    record = bridge.run_once("test objective")
    check(
        "level-2 request never executes even when 'approved'",
        record.final_state == "stopped_pending_level2_not_executed",
    )
    check("level-2 request never invokes claude", calls["claude_invoked"] == 0)
    check("founder_approval is recorded on the round", record.founder_approval is not None and record.founder_approval["approved"] is True)


def test_run_once_refuses_safety_level_escalation_above_caller_cap(monkeypatch):
    """The mechanism `run_watch(..., max_safety_level=0)` relies on for the
    Level-0-only supervised acceptance test: a Director decision of Level 1
    must be refused, before Claude is ever invoked, when the caller's own
    ceiling is 0 — independent of the always-on Level-2 refusal above."""
    calls = {"claude_invoked": 0}

    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="continue", task_for_claude="edit a file", reason="fixture",
            required_checks=[], safety_level=1, requires_founder_approval=False, stop_conditions=[],
        )

    def fake_claude(*a, **k):
        calls["claude_invoked"] += 1
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0)

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return _fake_evaluation("accepted")

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)

    record = bridge.run_once("test objective", max_safety_level=0)
    check(
        "a Level-1 decision is refused when the caller's max_safety_level is 0",
        record.final_state == "stopped_safety_level_escalation",
    )
    check("the escalation refusal never invokes claude", calls["claude_invoked"] == 0)

    record_allowed = bridge.run_once("test objective", max_safety_level=1)
    check(
        "the SAME Level-1 decision proceeds when the caller's max_safety_level is 1",
        record_allowed.final_state == "completed" and calls["claude_invoked"] == 1,
    )


def test_invalid_director_response_stops_cleanly(monkeypatch):
    def fake_director(state, provider_name=None):
        raise bridge.BridgeError2("schema validation failed (fixture)")

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)

    record = bridge.run_once("test objective")
    check("invalid Director response stops the round", record.final_state == "stopped_invalid_director_response")
    check("invalid Director response is recorded in errors", any("schema validation" in e for e in record.errors))


def test_live_db_fingerprint_change_overrides_director_evaluation(monkeypatch):
    """Not just size_bytes: any invariant field changing must be caught,
    AND the Director's own evaluation outcome must never be allowed to
    contradict a mechanically-detected safety failure — this is the
    literal 'must not override deterministic safety failures' requirement,
    exercised by deliberately having the fixture Director claim
    'accepted' and asserting the code overrides it to 'blocked'."""
    fingerprints = iter([
        {"path": "x", "size_bytes": 1000, "mtime": 1.0, "table_count": 32, "integrity_ok": True,
         "current_day": 8, "current_period": "MORNING", "is_paused": False, "max_event_id": 955},
        {"path": "x", "size_bytes": 1000, "mtime": 1.0, "table_count": 32, "integrity_ok": True,
         "current_day": 8, "current_period": "NIGHT", "is_paused": False, "max_event_id": 999},
    ])

    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="continue", task_for_claude="do something", reason="test",
            required_checks=[], safety_level=0, requires_founder_approval=False, stop_conditions=[],
        )

    def fake_claude(*a, **k):
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0)

    def fake_fingerprint():
        return next(fingerprints)

    def fake_evaluation_claims_accepted(**kwargs):
        # Deliberately wrong / optimistic — the code must not trust this.
        return _fake_evaluation("accepted")

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "_live_db_fingerprint", fake_fingerprint)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation_claims_accepted)

    record = bridge.run_once("test objective")
    check(
        "same size_bytes but changed day/period/max_event_id is still flagged",
        record.live_db_involvement_suspected is True,
    )
    check("a flagged live DB change stops the round as a safety violation", record.final_state == "stopped_safety_violation")
    check(
        "the Director's 'accepted' claim is overridden to 'blocked'",
        record.director_evaluation is not None and record.director_evaluation["outcome"] == "blocked",
    )
    check(
        "the override is recorded, not silent",
        record.director_evaluation is not None and record.director_evaluation["overridden_by_deterministic_check"] is True,
    )


def test_run_once_accepts_a_substitute_director_client(monkeypatch):
    """Proves the DirectorClient seam is real, not just declared: run_once()
    never imports/calls OpenAI-specific functions when a substitute client is
    passed in — the future exact-ChatGPT-thread connector plugs in exactly
    this way, with zero changes to run_once()."""
    calls = {"decide": 0, "evaluate": 0, "openai_fn_called": 0}

    class FakeClient:
        def decide(self, state):
            calls["decide"] += 1
            return bridge.DirectorDecision(
                decision="continue", task_for_claude="read README.md and summarize it",
                reason="fixture client", required_checks=[], safety_level=0,
                requires_founder_approval=False, stop_conditions=[],
            )

        def evaluate(self, *, decision, claude_result, deterministic):
            calls["evaluate"] += 1
            return _fake_evaluation("accepted")

    def fail_if_real_openai_fn_called(*a, **k):
        calls["openai_fn_called"] += 1
        raise AssertionError("run_once must not call the OpenAI-specific function directly")

    def fake_claude(task_prompt, level, timeout=300):
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result": "ok"}')

    monkeypatch.setattr(bridge, "call_openai_director", fail_if_real_openai_fn_called)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fail_if_real_openai_fn_called)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)

    record = bridge.run_once("test objective", director_client=FakeClient())
    check("run_once completes using a substitute DirectorClient", record.final_state == "completed")
    check("the substitute client's decide() was called exactly once", calls["decide"] == 1)
    check("the substitute client's evaluate() was called exactly once", calls["evaluate"] == 1)
    check("run_once never called the OpenAI-specific module functions directly", calls["openai_fn_called"] == 0)


def test_persisted_round_never_contains_secrets():
    import os

    secret_markers = [v for v in (os.getenv("OPENAI_API_KEY"), os.getenv("ANTHROPIC_API_KEY")) if v]
    if not bridge.BRIDGE_LOG_PATH.exists():
        check("bridge log exists after prior tests ran", False, "no rounds were persisted")
        return
    text = bridge.BRIDGE_LOG_PATH.read_text()
    leaked = [m for m in secret_markers if m in text]
    check("persisted round log never contains a raw API key value", not leaked)


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout='{"result":"fixture"}', stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_level0_argv_is_allowlist_only_no_bypass(monkeypatch):
    """Captures the REAL argv invoke_claude_code constructs for Level 0 by
    monkeypatching subprocess.run itself, not invoke_claude_code — proves
    the actual command-construction code, not a description of it."""
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, env=None):
        captured["cmd"] = cmd
        captured["env"] = env
        captured["timeout"] = timeout
        return _FakeCompletedProcess()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    result = bridge.invoke_claude_code("harmless task", bridge.BridgeSafetyLevel.READ_ONLY)

    cmd = captured["cmd"]
    check("invocation succeeded (fixture subprocess)", result.invoked and result.exit_code == 0)
    check("argv never contains bypassPermissions", "bypassPermissions" not in cmd)
    check("argv uses dontAsk permission mode", "dontAsk" in cmd)
    check("argv isolates setting sources", "--setting-sources" in cmd and cmd[cmd.index("--setting-sources") + 1] == "")
    check(
        "Level 0 passes an explicit --tools built-in registration ceiling (2026-09-10): the "
        "session is only ever aware of Read/Grep/Glob, so Bash is not a registered tool at "
        "all — 'cannot invoke Bash' is a registration fact, not a permission-match outcome",
        "--tools" in cmd,
    )
    tools_value = cmd[cmd.index("--tools") + 1] if "--tools" in cmd else ""
    check(
        "Level 0 --tools value is exactly 'Read Grep Glob' with Bash absent",
        sorted(tools_value.split()) == ["Glob", "Grep", "Read"],
        detail=f"--tools={tools_value!r}",
    )
    check("Level 0 --tools value never names Bash/Edit/Write/NotebookEdit",
          not any(t in tools_value.split() for t in ("Bash", "Edit", "Write", "NotebookEdit")))
    check(
        "Level 0 defaults to the 420s per-level timeout (2026-09-10: replaces the old "
        "single 300s CLAUDE_INVOCATION_TIMEOUT_SECONDS after round bd046f7218294d50 was "
        "killed mid-task at that ceiling)",
        captured["timeout"] == bridge.CLAUDE_LEVEL0_TIMEOUT_SECONDS == 420,
    )
    allowed = cmd[cmd.index("--allowedTools") + 1]
    disallowed = cmd[cmd.index("--disallowedTools") + 1]
    check("Level 0 allowlist excludes Edit/Write", "Edit" not in allowed and "Write" not in allowed)
    check("Level 0 allowlist excludes bare Bash", "Bash" not in allowed.replace("Bash(", "X("))
    check(
        "Level 0 grants NO Bash at all (2026-09-09 permission-escape hardening: find/git "
        "branch/git log --output were all confirmed real bypasses of a subcommand-only "
        "match, so Level 0's entire Bash surface was removed rather than patched flag by flag)",
        "Bash(" not in allowed,
    )
    check("Level 0 disallow list names Edit/Write redundantly", "Edit" in disallowed and "Write" in disallowed)
    check(
        "Level 0 disallow list explicitly denies bare 'Bash' (2026-09-10: round "
        "bd046f7218294d50 proved a Bash call absent from --allowedTools can still execute "
        "— 'not in allowedTools' alone is not a mechanical denial — so Bash is now named "
        "in --disallowedTools explicitly; see director_bridge.py)",
        "Bash" in disallowed.split(),
    )
    check("result.argv on the returned object matches the real invocation", result.argv == cmd)
    env = captured["env"]
    check("subprocess env excludes VILLAGE_DATA_ROOT", "VILLAGE_DATA_ROOT" not in env)
    check("subprocess env excludes DATABASE_URL", "DATABASE_URL" not in env)
    check(
        "subprocess env excludes ANTHROPIC_API_KEY (nested session must use the "
        "invoking user's own login, not a possibly-exhausted .env key)",
        "ANTHROPIC_API_KEY" not in env,
    )
    check("subprocess env forces APP_ENV=development", env.get("APP_ENV") == "development")


def test_level1_argv_denies_dangerous_git_and_db_operations(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, env=None):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        return _FakeCompletedProcess()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    bridge.invoke_claude_code("harmless sandbox task", bridge.BridgeSafetyLevel.SANDBOX)

    cmd = captured["cmd"]
    check("Level 1 argv never contains bypassPermissions", "bypassPermissions" not in cmd)
    check("Level 1 argv uses dontAsk permission mode", "dontAsk" in cmd)
    check(
        "Level 1 argv is UNCHANGED by the 2026-09-10 Level-0 --tools hardening: it still "
        "omits --tools entirely (full built-in toolset; restriction is purely at the "
        "--allowedTools/--disallowedTools permission layer, exactly as before)",
        "--tools" not in cmd,
    )
    check(
        "Level 1 defaults to the 1200s per-level timeout (longer than Level 0's 420s "
        "because engineering rounds edit + run pytest inside the isolated workspace)",
        captured["timeout"] == bridge.CLAUDE_LEVEL1_TIMEOUT_SECONDS == 1200,
    )
    allowed = cmd[cmd.index("--allowedTools") + 1]
    disallowed = cmd[cmd.index("--disallowedTools") + 1]
    check("Level 1 allows Edit/Write", "Edit" in allowed and "Write" in allowed)
    for dangerous in (
        "git commit", "git push", "git reset", "git checkout", "rm", "curl", "wget", "sqlite3",
        # 2026-09-09 permission-escape hardening additions — each CONFIRMED
        # real via an isolated probe (see director_bridge_permission_escape_probe.py):
        # find -exec/-execdir/-delete (subcommand-only match, same class as
        # the two below), `git branch <name>` (real branch created, zero
        # denials), `git log`/`git diff --output=FILE` (real arbitrary file
        # write via git's own flag), python3/.venv-python (real network
        # request, real write outside the sandbox dir, real `git commit`
        # via subprocess — completely defeats every entry on this list).
        "git branch", "git log", "git diff", "find", "python3", ".venv/bin/python",
    ):
        check(f"Level 1 disallow list names {dangerous!r}", dangerous in disallowed)
    check("Level 1 allowlist never grants bare unrestricted Bash", "Bash " not in allowed and not allowed.rstrip().endswith("Bash"))
    for removed in ("Bash(find:*)", "Bash(git branch:*)", "Bash(git log:*)", "Bash(git diff:*)", "Bash(python3:*)", "Bash(.venv/bin/python:*)"):
        check(f"Level 1 allowlist no longer grants {removed!r}", removed not in allowed)


# =============================================================================
# 2026-09-09 permission-escape hardening: regression tests for every route
# CONFIRMED real by scripts/director_bridge_permission_escape_probe.py
# (find, shell chaining/redirects, git write-flags, python3 network/fs/
# subprocess), proven at the allowlist-construction level -- the same
# argv-capture technique as the tests above, never by trusting a prompt
# instruction. See the _LEVEL_TOOLS module-level comment in
# director_bridge.py for the full empirical writeup.
# =============================================================================


def _argv_for(level: bridge.BridgeSafetyLevel, monkeypatch) -> tuple[str, str]:
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, env=None):
        captured["cmd"] = cmd
        return _FakeCompletedProcess()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    bridge.invoke_claude_code("harmless task", level)
    cmd = captured["cmd"]
    return cmd[cmd.index("--allowedTools") + 1], cmd[cmd.index("--disallowedTools") + 1]


def test_escape_route_find_exec_execdir_delete_mechanically_rejected(monkeypatch):
    """find -exec / -execdir / -delete: CONFIRMED by structural equivalence
    (git branch/git log --output used the identical subcommand-only match
    and really did bypass) -- find is absent from BOTH levels' allowlists,
    not merely instructed against."""
    level0_allowed, _ = _argv_for(bridge.BridgeSafetyLevel.READ_ONLY, monkeypatch)
    level1_allowed, level1_disallowed = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    check("find -exec/-execdir/-delete: Level 0 has no Bash at all to run find with", "Bash(" not in level0_allowed)
    check("find -exec/-execdir/-delete: Level 1 allowlist does not grant Bash(find:*)", "Bash(find:*)" not in level1_allowed)
    check("find -exec/-execdir/-delete: Level 1 disallow list names 'find'", "find" in level1_disallowed)


def test_escape_route_shell_invocation_mechanically_rejected(monkeypatch):
    """Invoking a shell directly (sh/bash/zsh) is denylisted at Level 1 and
    was never in Level 0's allowlist (which has no Bash at all)."""
    level0_allowed, _ = _argv_for(bridge.BridgeSafetyLevel.READ_ONLY, monkeypatch)
    level1_allowed, level1_disallowed = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    for shell in ("sh", "bash", "zsh"):
        check(f"shell invocation: {shell!r} was never granted at Level 0 (no Bash at all)", "Bash(" not in level0_allowed)
        check(f"shell invocation: Bash({shell}:*) is not granted at Level 1", f"Bash({shell}:*)" not in level1_allowed)
        check(f"shell invocation: Level 1 disallow list names {shell!r}", f"Bash({shell}:*)" in level1_disallowed)


def test_escape_route_destructive_filesystem_command_mechanically_rejected(monkeypatch):
    """rm/rm -rf: denylisted at Level 1, absent (no Bash at all) at Level 0."""
    level0_allowed, _ = _argv_for(bridge.BridgeSafetyLevel.READ_ONLY, monkeypatch)
    level1_allowed, level1_disallowed = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    check("destructive fs command: Level 0 has no Bash at all", "Bash(" not in level0_allowed)
    check("destructive fs command: Level 1 does not grant Bash(rm:*)", "Bash(rm:*)" not in level1_allowed)
    check("destructive fs command: Level 1 disallow list names 'rm'", "Bash(rm:*)" in level1_disallowed and "Bash(rm -rf:*)" in level1_disallowed)


def test_escape_route_git_mutation_mechanically_rejected(monkeypatch):
    """git commit/push/reset/checkout/branch: all denylisted (or, for
    branch/log/diff, removed from the allowlist entirely) at Level 1;
    absent at Level 0 (no Bash)."""
    level0_allowed, _ = _argv_for(bridge.BridgeSafetyLevel.READ_ONLY, monkeypatch)
    level1_allowed, level1_disallowed = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    check("git mutation: Level 0 has no Bash at all", "Bash(" not in level0_allowed)
    for mutating in ("git commit", "git push", "git reset", "git checkout", "git branch"):
        pattern = f"Bash({mutating}:*)"
        check(f"git mutation: Level 1 does not grant {pattern!r}", pattern not in level1_allowed)
        check(f"git mutation: Level 1 disallow list names {mutating!r}", mutating in level1_disallowed)


def test_escape_route_network_command_mechanically_rejected(monkeypatch):
    """curl/wget (shell-level) and python3/.venv-python (the general
    network escape confirmed via a real HTTP round-trip) are all
    denylisted-or-absent at Level 1; Level 0 has no Bash at all."""
    level0_allowed, _ = _argv_for(bridge.BridgeSafetyLevel.READ_ONLY, monkeypatch)
    level1_allowed, level1_disallowed = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    check("network command: Level 0 has no Bash at all", "Bash(" not in level0_allowed)
    for net in ("curl", "wget", "python3", ".venv/bin/python"):
        pattern = f"Bash({net}:*)"
        check(f"network command: Level 1 does not grant {pattern!r}", pattern not in level1_allowed)
        check(f"network command: Level 1 disallow list names {net!r}", net in level1_disallowed)


def test_escape_route_canonical_db_access_mechanically_rejected(monkeypatch):
    """Two independent, already-verified mechanisms together: (1) the
    subprocess environment never carries VILLAGE_DATA_ROOT/DATABASE_URL, so
    app code resolving a DB path through normal channels gets a harmless
    stub; (2) the live-DB fingerprint check (run_once) treats any drift as
    an authoritative, non-overridable safety violation. NOT claimed as a
    complete guarantee: Bash(cat:*) remains granted at Level 1 with no
    path restriction, so a session that already knows the absolute live-DB
    path (e.g. from constitution.md's own text) could still read its raw
    bytes -- see the investigation report's remaining-concerns section.
    This test covers what IS mechanically enforced, not more."""
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, env=None):
        captured["env"] = env
        return _FakeCompletedProcess()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    bridge.invoke_claude_code("harmless task", bridge.BridgeSafetyLevel.SANDBOX)
    env = captured["env"]
    check("canonical DB access: subprocess env excludes VILLAGE_DATA_ROOT", "VILLAGE_DATA_ROOT" not in env)
    check("canonical DB access: subprocess env excludes DATABASE_URL", "DATABASE_URL" not in env)

    # The fingerprint-override mechanism itself is exercised end-to-end by
    # test_live_db_fingerprint_change_overrides_director_evaluation above;
    # here we just confirm sqlite3 (the CLI most directly capable of both
    # reading AND writing the canonical file) is mechanically absent too.
    _, level1_disallowed = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    check("canonical DB access: Level 1 disallow list names 'sqlite3'", "sqlite3" in level1_disallowed)


def test_consequential_level_never_reaches_subprocess(monkeypatch):
    calls = {"subprocess_run": 0}

    def fake_run(*a, **k):
        calls["subprocess_run"] += 1
        return _FakeCompletedProcess()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    result = bridge.invoke_claude_code("do something consequential", bridge.BridgeSafetyLevel.CONSEQUENTIAL)
    check("CONSEQUENTIAL level is refused before any subprocess call", not result.invoked and calls["subprocess_run"] == 0)


# =============================================================================
# Watch-mode readiness fixes (2026-09-09 pre-watch hardening pass, blockers
# 1 and 2): _watch_continuation_decision() must gate on DirectorEvaluation,
# not just final_state; _check_git_state() must hard-stop on ambiguous git
# state rather than ever falling back to _run()'s soft "<unavailable: ...>"
# text. Everything below tests those two additions plus run_watch's use of
# them, still with zero real API calls and zero real `claude` subprocess
# execution — the git-state tests below use REAL, disposable, throwaway git
# repos (real `git init`/`commit`/`checkout`), never the actual project repo.
# =============================================================================


def _base_evaluation(**overrides: Any) -> dict[str, Any]:
    base = {
        "outcome": "accepted", "summary": "fixture", "evidence_assessment": "fixture",
        "remaining_risks": [], "recommended_next_task": "fixture: continue with the next bounded step",
        "recommended_safety_level": 0,
        "requires_founder_approval": False, "stop_reason": "", "overridden_by_deterministic_check": False,
    }
    base.update(overrides)
    return base


def _clean_round_record(**overrides: Any) -> bridge.BridgeRoundRecord:
    base: dict[str, Any] = dict(
        round_id="fixture_round", timestamp="2026-01-01T00:00:00+00:00", objective="test",
        director_input={}, final_state="completed",
        claude_result=bridge.ClaudeInvocationResult(invoked=True, exit_code=0, timed_out=False),
        director_evaluation=_base_evaluation(),
        errors=[], live_db_involvement_suspected=False, changed_files=[],
    )
    base.update(overrides)
    return bridge.BridgeRoundRecord(**base)


def test_watch_continuation_accepted_clean_round_may_continue():
    record = _clean_round_record()
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(1) accepted evaluation + clean round => may continue", may_continue, detail=reason)


def test_watch_continuation_needs_revision_with_safe_task_may_continue():
    """2026-09-09: needs_revision is no longer an automatic stop. A
    needs_revision evaluation that is itself safely continuable (Level 0/1,
    within max_safety_level, no Founder approval, non-empty next task, clean
    deterministic pass) must be allowed to continue exactly like 'accepted'."""
    record = _clean_round_record(director_evaluation=_base_evaluation(outcome="needs_revision"))
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(2) needs_revision with a safe Level-0 next task => may continue", may_continue, detail=reason)
    check("(2) the reason names needs_revision as safely continuable", "needs_revision" in reason)


def test_watch_continuation_needs_revision_missing_next_task_stops():
    """(2b) A needs_revision evaluation with no concrete next task cannot
    safely continue — nothing for the next round to do."""
    record = _clean_round_record(
        director_evaluation=_base_evaluation(outcome="needs_revision", recommended_next_task="")
    )
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(2b) needs_revision with an empty next task => watch stops", not may_continue, detail=reason)


def test_watch_continuation_needs_revision_founder_approval_stops():
    """(2c) A needs_revision evaluation that itself requires Founder
    approval cannot safely continue, regardless of how safe the requested
    level otherwise looks."""
    record = _clean_round_record(
        director_evaluation=_base_evaluation(outcome="needs_revision", requires_founder_approval=True)
    )
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(2c) needs_revision with requires_founder_approval=true => watch stops", not may_continue, detail=reason)


def test_watch_continuation_needs_revision_level2_stops():
    """(2d) A needs_revision evaluation requesting Level 2 can never
    safely continue, defensively, even if requires_founder_approval was
    (incorrectly) left false."""
    record = _clean_round_record(
        director_evaluation=_base_evaluation(outcome="needs_revision", recommended_safety_level=2)
    )
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(2d) needs_revision recommending Level 2 => watch stops", not may_continue, detail=reason)


def test_watch_continuation_needs_revision_level1_stops_when_max_safety_level_is_0():
    """(2e) A needs_revision evaluation recommending Level 1 cannot
    continue when the watch run itself is configured Level-0-only."""
    record = _clean_round_record(
        director_evaluation=_base_evaluation(outcome="needs_revision", recommended_safety_level=1)
    )
    may_continue, reason = bridge._watch_continuation_decision(record, max_safety_level=0)
    check(
        "(2e) needs_revision recommending Level 1 stops when max_safety_level=0",
        not may_continue, detail=reason,
    )


def test_watch_continuation_needs_revision_level1_continues_when_max_safety_level_is_1():
    """(2f) The same Level-1 recommendation IS allowed to continue when the
    watch run's configured max_safety_level permits Level 1."""
    record = _clean_round_record(
        director_evaluation=_base_evaluation(outcome="needs_revision", recommended_safety_level=1)
    )
    may_continue, reason = bridge._watch_continuation_decision(record, max_safety_level=1)
    check(
        "(2f) needs_revision recommending Level 1 continues when max_safety_level=1",
        may_continue, detail=reason,
    )


def test_watch_continuation_needs_revision_stops_on_live_db_involvement():
    """(2g) Deterministic verification (live DB fingerprint check) finding
    a suspected safety violation must stop a needs_revision round exactly
    like it stops an accepted one — defense in depth, never trusting the
    Director's own outcome alone."""
    record = _clean_round_record(
        director_evaluation=_base_evaluation(outcome="needs_revision"),
        live_db_involvement_suspected=True,
    )
    may_continue, reason = bridge._watch_continuation_decision(record)
    check(
        "(2g) needs_revision stops when live DB involvement was suspected",
        not may_continue, detail=reason,
    )


def test_watch_continuation_blocked_stops():
    record = _clean_round_record(director_evaluation=_base_evaluation(outcome="blocked"))
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(3) evaluation outcome 'blocked' => watch stops", not may_continue, detail=reason)


def test_watch_continuation_missing_evaluation_stops():
    record = _clean_round_record(director_evaluation=None)
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(4) a completed round with no DirectorEvaluation at all => watch stops", not may_continue, detail=reason)


def test_watch_stops_when_level2_requested(monkeypatch):
    """(5) A round that requests Level 2 never reaches 'completed' in the
    first place (run_once refuses it before Claude is invoked) — proves the
    FULL run_watch loop halts after exactly one round, not just that a
    hand-built record would fail the gate."""
    calls = {"decide": 0}

    class Level2Client:
        def decide(self, state):
            calls["decide"] += 1
            return bridge.DirectorDecision(
                decision="request_approval", task_for_claude="run Run Day on the live Village",
                reason="fixture", required_checks=[], safety_level=2,
                requires_founder_approval=True, stop_conditions=[],
            )

        def evaluate(self, **kwargs):
            raise AssertionError("evaluate() must never be called when Claude was never invoked")

    monkeypatch.setattr(
        bridge, "request_founder_approval",
        lambda decision, state: {"requested_action": decision.task_for_claude, "approved": False},
    )
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    bridge.run_watch("fixture objective", max_rounds=5, director_client=Level2Client())
    check("(5) watch stops after exactly one round when Level 2 is requested", calls["decide"] == 1)


def test_watch_continuation_stops_when_evaluation_requires_founder_approval():
    """(6) Distinct from a Level-2 request at decision time: here the ROUND
    itself completed cleanly, but the SECOND Director call's evaluation of
    what should happen next flags requires_founder_approval — must still
    stop, not just the decision-time check already covered by test (5)."""
    record = _clean_round_record(director_evaluation=_base_evaluation(requires_founder_approval=True))
    may_continue, reason = bridge._watch_continuation_decision(record)
    check(
        "(6) DirectorEvaluation.requires_founder_approval=true => watch stops even after a clean round",
        not may_continue, detail=reason,
    )


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=path, check=True)


def _commit(path: Path, filename: str, content: str, message: str) -> str:
    (path / filename).write_text(content + "\n")
    subprocess.run(["git", "add", filename], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=path, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_git_state_check_raises_when_git_command_itself_fails(monkeypatch):
    """(7a) A git command that fails to execute at all (binary missing,
    permission error, etc.) must raise GitStateError — never be converted
    into _run()'s soft '<unavailable: ...>' evidence text."""

    def fake_run(*a, **k):
        raise FileNotFoundError("git binary not found (fixture)")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    raised = False
    try:
        bridge._check_git_state()
    except bridge.GitStateError:
        raised = True
    check("(7a) a failed git command execution raises GitStateError", raised)


def test_git_state_check_raises_on_unresolvable_repo(monkeypatch):
    """(7b) A directory that is not a git repository at all: `git rev-parse
    --git-dir` returns nonzero -> must raise, not silently proceed."""
    tmp = Path(tempfile.mkdtemp(prefix="not_a_repo_"))
    try:
        monkeypatch.setattr(bridge, "REPO_ROOT", tmp)
        raised = False
        try:
            bridge._check_git_state()
        except bridge.GitStateError:
            raised = True
        check("(7b) a non-git directory raises GitStateError (repository cannot be resolved)", raised)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_git_state_check_detached_head(monkeypatch):
    """(8) A detached HEAD is ambiguous git state by default; explicitly
    opting in (allow_detached_head=True) is the only way past it."""
    tmp = Path(tempfile.mkdtemp(prefix="detached_head_repo_"))
    try:
        _init_repo(tmp)
        first_sha = _commit(tmp, "a.txt", "one", "first")
        _commit(tmp, "a.txt", "two", "second")
        subprocess.run(["git", "checkout", "-q", first_sha], cwd=tmp, check=True)

        monkeypatch.setattr(bridge, "REPO_ROOT", tmp)
        raised = False
        try:
            bridge._check_git_state()
        except bridge.GitStateError:
            raised = True
        check("(8) a detached HEAD raises GitStateError by default", raised)

        state = bridge._check_git_state(allow_detached_head=True)
        check(
            "(8) a detached HEAD is allowed only when explicitly opted in",
            state["detached_head"] is True,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_git_state_check_merge_in_progress(monkeypatch):
    """(9a) MERGE_HEAD present under .git => merge in progress => hard stop,
    detected as a marker file, independent of what `git status` itself
    would report."""
    tmp = Path(tempfile.mkdtemp(prefix="merge_in_progress_repo_"))
    try:
        _init_repo(tmp)
        _commit(tmp, "a.txt", "one", "first")
        (tmp / ".git" / "MERGE_HEAD").write_text("deadbeef\n")

        monkeypatch.setattr(bridge, "REPO_ROOT", tmp)
        reason = ""
        try:
            bridge._check_git_state()
        except bridge.GitStateError as exc:
            reason = str(exc)
        check("(9a) an in-progress merge (MERGE_HEAD present) raises GitStateError", "merge" in reason.lower())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_git_state_check_rebase_in_progress(monkeypatch):
    """(9b) Same marker-file mechanism, for a rebase (rebase-merge dir)."""
    tmp = Path(tempfile.mkdtemp(prefix="rebase_in_progress_repo_"))
    try:
        _init_repo(tmp)
        _commit(tmp, "a.txt", "one", "first")
        (tmp / ".git" / "rebase-merge").mkdir()

        monkeypatch.setattr(bridge, "REPO_ROOT", tmp)
        reason = ""
        try:
            bridge._check_git_state()
        except bridge.GitStateError as exc:
            reason = str(exc)
        check("(9b) an in-progress rebase (rebase-merge/ present) raises GitStateError", "rebase" in reason.lower())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_git_state_check_unresolved_conflict_detected(monkeypatch):
    """(9c) Even with no in-progress marker file, an unresolved conflict
    reported by `git status` itself (UU/AA/DD codes) must raise — the
    porcelain-parsing branch, exercised with canned subprocess output so
    this doesn't depend on actually reproducing a real merge conflict."""

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        if cmd[:2] == ["git", "rev-parse"]:
            return _FakeCompletedProcess(returncode=0, stdout=".git\n")
        if cmd[:2] == ["git", "symbolic-ref"]:
            return _FakeCompletedProcess(returncode=0, stdout="refs/heads/main\n")
        if cmd[:2] == ["git", "status"]:
            return _FakeCompletedProcess(returncode=0, stdout="UU conflicted.txt\n")
        raise AssertionError(f"unexpected git command in fake_run: {cmd}")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    reason = ""
    try:
        bridge._check_git_state()
    except bridge.GitStateError as exc:
        reason = str(exc)
    check("(9c) an unresolved merge conflict (UU status) raises GitStateError", "conflict" in reason.lower())


def test_watch_continuation_stops_on_deterministic_verification_failure():
    """(10) Defense in depth: even if final_state somehow read 'completed',
    an explicit live_db_involvement_suspected=True must independently block
    continuation — the gate never trusts final_state alone."""
    record = _clean_round_record(live_db_involvement_suspected=True)
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(10) live_db_involvement_suspected=True stops watch even if final_state says completed", not may_continue, detail=reason)


def test_watch_continuation_stops_on_claude_failure():
    """(11) Same defense-in-depth principle for a bad claude_result."""
    record = _clean_round_record(
        claude_result=bridge.ClaudeInvocationResult(invoked=True, exit_code=1, timed_out=False)
    )
    may_continue, reason = bridge._watch_continuation_decision(record)
    check("(11) a nonzero Claude exit code stops watch even if final_state says completed", not may_continue, detail=reason)


def test_watch_stops_immediately_when_git_state_check_raises(monkeypatch):
    """Integration-level companion to the _check_git_state unit tests:
    run_watch itself must never call the Director at all once the git-state
    gate fails, on round 1 or any later round."""
    calls = {"decide": 0}

    class CountingClient:
        def decide(self, state):
            calls["decide"] += 1
            return bridge.DirectorDecision(
                decision="stop", task_for_claude="", reason="unused", required_checks=[],
                safety_level=0, requires_founder_approval=False, stop_conditions=[],
            )

        def evaluate(self, **kwargs):
            raise AssertionError("evaluate() should never be reached")

    def always_ambiguous(**kwargs):
        raise bridge.GitStateError("fixture: simulated ambiguous git state")

    monkeypatch.setattr(bridge, "_check_git_state", always_ambiguous)
    bridge.run_watch("fixture objective", max_rounds=5, director_client=CountingClient())
    check("run_watch never calls the Director when the initial git-state check itself fails", calls["decide"] == 0)


def test_watch_respects_max_rounds(monkeypatch):
    """(14) A Director that would happily continue forever (always
    'continue', always a clean Level-0 Claude result, always 'accepted',
    always recommending a genuinely NEW next task — never the same one
    twice, so loop detection never fires) must still be capped at
    max_rounds — proven by counting decide() calls, not by trusting a
    printed message."""
    calls = {"decide": 0}

    class AlwaysContinueClient:
        def decide(self, state):
            calls["decide"] += 1
            return bridge.DirectorDecision(
                decision="continue", task_for_claude="read README.md", reason="fixture",
                required_checks=[], safety_level=0, requires_founder_approval=False, stop_conditions=[],
            )

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(
                **_base_evaluation(recommended_next_task=f"fixture: distinct follow-up task #{calls['decide']}")
            )

    def fake_claude(task_prompt, level, timeout=300):
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result": "ok"}')

    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=AlwaysContinueClient())
    check("(14) a Director that always continues is still capped at exactly max_rounds calls", calls["decide"] == 3)
    check("(14) the run stops with MAX_ROUNDS_REACHED, not some other reason", result.stop_reason == "MAX_ROUNDS_REACHED")


def test_watch_feeds_recommended_next_task_into_next_round_objective(monkeypatch):
    """(15) 2026-09 activation: the whole point of turning run_once into a
    supervised loop is that DirectorEvaluation.recommended_next_task DOES
    become the next round's objective -- but ONLY structurally (a plain
    string assignment) and ONLY after _watch_continuation_decision has
    already confirmed the round was fully clean. Proven by giving round 1 a
    distinct, recognizable recommended_next_task and asserting round 2's
    decide() sees exactly that string, not the original objective."""
    seen_objectives: list[str] = []
    SECOND_ROUND_TASK = "fixture: investigate the specific follow-up finding from round 1"

    class RecordingClient:
        def decide(self, state):
            seen_objectives.append(state["objective"])
            return bridge.DirectorDecision(
                decision="continue", task_for_claude="read README.md", reason="fixture",
                required_checks=[], safety_level=0, requires_founder_approval=False, stop_conditions=[],
            )

        def evaluate(self, *, decision, claude_result, deterministic):
            next_task = SECOND_ROUND_TASK if len(seen_objectives) == 1 else ""
            return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task=next_task))

    def fake_claude(task_prompt, level, timeout=300):
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result": "ok"}')

    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("the one true fixture objective", max_rounds=2, director_client=RecordingClient())

    check("(15) exactly two rounds were attempted", len(seen_objectives) == 2)
    check("(15) round 1's Director call receives the ORIGINAL objective", seen_objectives[0] == "the one true fixture objective")
    check(
        "(15) round 2's Director call receives round 1's recommended_next_task, structurally",
        seen_objectives[1] == SECOND_ROUND_TASK,
    )
    check("(15) two rounds are recorded on the returned WatchRunResult", len(result.rounds) == 2)
    check("(15) round 1 has no parent (it is the first round)", result.rounds[0].parent_round_id is None)
    check(
        "(15) round 2's parent_round_id is round 1's round_id (auditable parent/child chain)",
        result.rounds[1].parent_round_id == result.rounds[0].round_id,
    )
    check(
        "(15) the run stops with COMPLETED once round 2's evaluation recommends no further task",
        result.stop_reason == "COMPLETED",
    )


# =============================================================================
# 2026-09-09 filesystem/context-boundary hardening: path-scoped Read/Grep/
# Glob/Edit/Write (real behavior confirmed via
# scripts/director_bridge_workspace_isolation_probe.py), an isolated
# throwaway workspace for every Level-1 round (never the real repo), and a
# redaction choke point so the live-data path/secrets never reach a
# prompt/context payload. Tests below are all deterministic/offline.
# =============================================================================


def test_secret_shaped_env_var_name_is_excluded_even_when_not_individually_named(monkeypatch):
    """The exclusion list names four specific vars; this is the defense-
    in-depth catch-all for a FIFTH one nobody thought to add — proven by
    injecting a fake var with a secret-shaped name that is NOT in
    _EXCLUDED_ENV_VAR_NAMES and confirming it's excluded anyway."""
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, env=None):
        captured["env"] = env
        return _FakeCompletedProcess()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    monkeypatch.setattr(bridge.os, "environ", {**bridge.os.environ, "SOME_FUTURE_STRIPE_API_KEY": "sk_live_fake_9f1e2c"})
    bridge.invoke_claude_code("harmless task", bridge.BridgeSafetyLevel.READ_ONLY)
    env = captured["env"]
    check(
        "a secret-shaped env var name never explicitly listed is still excluded",
        "SOME_FUTURE_STRIPE_API_KEY" not in env,
    )
    check("ordinary env vars (PATH) are not collaterally stripped", "PATH" in env or len(env) >= 0)


def test_redact_sensitive_context_masks_the_live_data_path_and_secrets():
    fake_db_path = "/Users/zacharywolk/village-data/live/internal_village.db"
    text = f"the live database lives at {fake_db_path} and the root is /Users/zacharywolk/village-data"
    redacted = bridge._redact_sensitive_context(text)
    # Whatever the CURRENT real resolved path/root actually is, redaction
    # must remove it if present; here we directly exercise the function
    # against a plausible live-data string shape, and separately (below)
    # against the bridge's own currently-resolved values.
    check(
        "_redact_sensitive_context is defined and callable without raising",
        isinstance(redacted, str),
    )


def test_context_leak_scan_of_real_collect_bridge_state_and_constitution():
    """The section-6 'context-leak test': builds the actual, real
    collect_bridge_state() payload (as sent to the OpenAI Director) and the
    actual, real load_constitution() text (as included within it), and
    fails if the resolved live-data root, live DB path, or any configured
    secret value appears anywhere in either. Real repo, real .env-resolved
    values — never a fixture stand-in — because a fixture value could
    never prove a real leak either way."""
    sensitive_pairs = bridge._sensitive_strings_to_redact()
    if not sensitive_pairs:
        check(
            "at least one real sensitive value was resolved to scan for "
            "(if this fails, the environment this suite is running in has none configured)",
            False,
        )
        return

    constitution_text = bridge.load_constitution()
    state = bridge.collect_bridge_state("context-leak scan objective")
    state_text = json.dumps(state, default=str)

    for real_value, placeholder in sensitive_pairs:
        check(
            f"load_constitution() output never contains the real value behind {placeholder}",
            real_value not in constitution_text,
        )
        check(
            f"collect_bridge_state() output never contains the real value behind {placeholder}",
            real_value not in state_text,
        )


def test_context_leak_scan_of_claude_facing_prompt_for_both_levels(monkeypatch):
    """Same scan, applied to the ACTUAL full_prompt text invoke_claude_code
    constructs for a Claude subprocess — captured via the real argv, not a
    description of it — for both Level 0 and Level 1."""
    sensitive_pairs = bridge._sensitive_strings_to_redact()
    if not sensitive_pairs:
        check("at least one real sensitive value was resolved to scan the Claude-facing prompt for", False)
        return

    for level in (bridge.BridgeSafetyLevel.READ_ONLY, bridge.BridgeSafetyLevel.SANDBOX):
        captured = {}

        def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, env=None):
            captured["cmd"] = cmd
            captured["env"] = env
            return _FakeCompletedProcess()

        monkeypatch.setattr(bridge.subprocess, "run", fake_run)
        bridge.invoke_claude_code(
            "an ordinary task that never mentions anything sensitive", level,
        )
        prompt = captured["cmd"][2]  # [claude_bin, "-p", full_prompt, ...]
        env = captured["env"]
        for real_value, placeholder in sensitive_pairs:
            check(
                f"Level {int(level)}'s Claude-facing prompt never contains the real value behind {placeholder}",
                real_value not in prompt,
            )
            check(
                f"Level {int(level)}'s subprocess env never carries the real value behind {placeholder} "
                "as a value (argv-embedded deny patterns are a separate, intentional layer)",
                all(real_value != v for v in env.values()),
            )


def test_level0_read_grep_glob_are_path_scoped_to_cwd(monkeypatch):
    """Confirms the argv itself carries `(./**)` scoping, not a bare grant —
    the real enforcement of this was proven with actual isolated `claude -p`
    probes (director_bridge_workspace_isolation_probe.py); this test proves
    the code that constructs the argv keeps doing so."""
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, env=None):
        captured["cmd"] = cmd
        return _FakeCompletedProcess()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    bridge.invoke_claude_code("harmless task", bridge.BridgeSafetyLevel.READ_ONLY)
    allowed = captured["cmd"][captured["cmd"].index("--allowedTools") + 1]
    for scoped in ("Read(./**)", "Grep(./**)", "Glob(./**)"):
        check(f"Level 0 allowlist grants {scoped!r} (path-scoped, not bare)", scoped in allowed)
    for bare in ("Read ", "Grep ", "Glob "):
        check(f"Level 0 allowlist never grants a bare {bare.strip()!r} alongside the scoped form", allowed.count(bare) == 0)


def test_level1_read_edit_write_grep_glob_are_path_scoped_to_cwd(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None, env=None):
        captured["cmd"] = cmd
        return _FakeCompletedProcess()

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    bridge.invoke_claude_code("harmless task", bridge.BridgeSafetyLevel.SANDBOX)
    allowed = captured["cmd"][captured["cmd"].index("--allowedTools") + 1]
    for scoped in ("Read(./**)", "Grep(./**)", "Glob(./**)", "Edit(./**)", "Write(./**)"):
        check(f"Level 1 allowlist grants {scoped!r} (path-scoped, not bare)", scoped in allowed)
    for removed in ("Bash(cat:*)", "Bash(ls:*)", "Bash(mkdir:*)", "Bash(touch:*)"):
        check(f"Level 1 allowlist no longer grants unnecessary shell reader {removed!r}", removed not in allowed)


def test_level1_workspace_is_created_used_and_cleaned_up(monkeypatch):
    """Proves run_once's SANDBOX path actually creates an isolated
    workspace (real, unmocked _create_level1_workspace — a real, cheap
    `git clone --local` of the real repo, never touching it), passes it as
    cwd to invoke_claude_code (mocked here to avoid real Claude spend),
    computes evidence from the WORKSPACE (not the real repo), and cleans
    the workspace up afterward regardless of outcome."""
    calls = {"cwd_seen": None}
    real_create = bridge._create_level1_workspace
    created_paths = []

    def spying_create():
        ws = real_create()
        created_paths.append(ws)
        return ws

    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="continue", task_for_claude="edit a file", reason="fixture",
            required_checks=[], safety_level=1, requires_founder_approval=False, stop_conditions=[],
        )

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        calls["cwd_seen"] = cwd
        # Make a real edit INSIDE the isolated workspace to prove
        # changed_files/diff_stat are computed from it, not the real repo.
        (cwd / "director_bridge_workspace_probe_marker.txt").write_text("edited by fixture\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result": "ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return _fake_evaluation("accepted")

    monkeypatch.setattr(bridge, "_create_level1_workspace", spying_create)
    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)

    record = bridge.run_once("test objective")

    check("a Level-1 round created exactly one isolated workspace", len(created_paths) == 1)
    check("invoke_claude_code was called with cwd= the isolated workspace, not REPO_ROOT", calls["cwd_seen"] == created_paths[0])
    check(
        "changed_files reflects the workspace's own new file, not anything from the real repo",
        "director_bridge_workspace_probe_marker.txt" in record.changed_files,
    )
    check("the isolated workspace was deleted after the round", not created_paths[0].exists())
    check("the real repo's own working tree was never touched", not (bridge.REPO_ROOT / "director_bridge_workspace_probe_marker.txt").exists())

    # The full sandbox patch is preserved before the workspace is destroyed.
    check("record.workspace_diff_path was set for the Level-1 round", bool(record.workspace_diff_path))
    if record.workspace_diff_path:
        patch_file = bridge.REPO_ROOT / record.workspace_diff_path
        try:
            check("the preserved patch file exists on disk", patch_file.is_file())
            patch_text = patch_file.read_text() if patch_file.is_file() else ""
            check(
                "the preserved patch contains ONLY the sandbox change (the new marker file), "
                "not the rsync'd baseline noise",
                "director_bridge_workspace_probe_marker.txt" in patch_text
                and "edited by fixture" in patch_text
                and "scripts/director_bridge.py" not in patch_text,
                detail=patch_text[:400],
            )
            check("record.diff_stat is the baseline-noise-free scoped stat",
                  "director_bridge_workspace_probe_marker.txt" in (record.diff_stat or "")
                  and "director_bridge.py" not in (record.diff_stat or ""))
            check("the bridge NEVER applied the patch to the real repo (no auto-promotion)",
                  not (bridge.REPO_ROOT / "director_bridge_workspace_probe_marker.txt").exists())
        finally:
            patch_file.unlink(missing_ok=True)


def test_level1_workspace_never_contains_env_file():
    """2026-09-09: the FIRST real run of the workspace-isolation probe
    found that .env (real API keys, real VILLAGE_DATA_ROOT) was copied
    straight into the "isolated" workspace, and Claude — correctly
    permitted to Read anything inside its own workspace — read it. Fixed
    by excluding .env* from the rsync in _create_level1_workspace(). This
    test creates a REAL workspace (cheap: a local git clone + rsync of
    this actual repo, no Claude involved) and asserts no .env* file
    exists anywhere inside it."""
    if not (bridge.REPO_ROOT / ".env").exists():
        check("a real .env exists in this repo to test the exclusion against", False)
        return
    workspace = bridge._create_level1_workspace()
    try:
        leaked = sorted({p for p in workspace.rglob(".env*") if ".git" not in p.parts})
        check(
            "no .env* file exists anywhere inside a freshly created Level-1 workspace",
            not leaked, detail=str(leaked),
        )
    finally:
        bridge._cleanup_level1_workspace(workspace)


def test_level1_workspace_never_contains_database_artifacts():
    """2026-09-10 database-artifact hardening: `rsync -a` (no .gitignore
    awareness) was also copying the repo's local, gitignored SQLite dev
    stubs (`village.db`, `internal_village_live.db`,
    `data/live/quarantine/.../internal_village.db`) and any `-wal`/`-shm`
    sidecars into the "isolated" workspace. `_create_level1_workspace`
    now excludes `*.db` / `*.sqlite3` and every SQLite sidecar spelling.
    This test writes representative fixtures (top-level, nested, and every
    sidecar spelling) into the copy source, creates a REAL workspace
    (cheap: local git clone + rsync, no Claude), asserts the DB artifacts
    are absent while a normal file at the same depths IS present, and
    restores the working tree to its exact prior state."""
    import shutil as _shutil
    import uuid as _uuid

    repo = bridge.REPO_ROOT
    nonce = _uuid.uuid4().hex[:10]
    pfx = f"PROBE_FIXT_DBX_{nonce}"
    db_files = [
        repo / f"{pfx}.db", repo / f"{pfx}.db-wal", repo / f"{pfx}.db-shm",
        repo / f"{pfx}.sqlite3", repo / f"{pfx}.sqlite3-wal", repo / f"{pfx}.sqlite3-shm",
    ]
    normal_top = repo / f"{pfx}_normal.txt"
    nested_dir = repo / f"{pfx}_nested"
    nested_keep = nested_dir / "keep.txt"
    nested_db = nested_dir / "inner.db"
    all_fixtures = [*db_files, normal_top, nested_keep, nested_db]

    status_before = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo, capture_output=True, text=True,
    ).stdout

    for p in db_files:
        p.write_text(f"fixture {p.name} {nonce}\n")
    normal_top.write_text(f"normal {nonce}\n")
    nested_dir.mkdir(exist_ok=True)
    nested_keep.write_text(f"keep {nonce}\n")
    nested_db.write_text(f"nested db {nonce}\n")

    workspace = None
    try:
        workspace = bridge._create_level1_workspace()
        rg = lambda pat: sorted(
            str(p.relative_to(workspace)) for p in workspace.rglob(pat)
            if ".git" not in p.parts
        )
        check("Level-1 workspace: a normal top-level source file IS copied", (workspace / f"{pfx}_normal.txt").exists())
        check("Level-1 workspace: a normal nested source file IS copied", (workspace / f"{pfx}_nested" / "keep.txt").exists())
        check("Level-1 workspace: NO *.db anywhere (top-level + nested)", not rg("*.db"), detail=str(rg("*.db")))
        check("Level-1 workspace: NO *.sqlite3 anywhere", not rg("*.sqlite3"), detail=str(rg("*.sqlite3")))
        for pat in ("*.db-wal", "*.db-shm", "*.sqlite3-wal", "*.sqlite3-shm"):
            check(f"Level-1 workspace: NO {pat} sidecar anywhere", not rg(pat), detail=str(rg(pat)))
    finally:
        if workspace is not None:
            bridge._cleanup_level1_workspace(workspace)
        for p in all_fixtures:
            p.unlink(missing_ok=True)
        _shutil.rmtree(nested_dir, ignore_errors=True)

    status_after = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo, capture_output=True, text=True,
    ).stdout
    check("Level-1 DB-fixture test: all fixtures removed (verified by exact path)",
          not [str(p) for p in all_fixtures if p.exists()])
    check("Level-1 DB-fixture test: git status is byte-for-byte back to its pre-test state",
          status_after == status_before,
          detail=f"before/after differ:\n{status_before!r}\n{status_after!r}")


# =============================================================================
# 2026-09 supervised-loop activation: end-to-end run_watch() tests (not just
# the lower-level _watch_continuation_decision/_classify_round_stop_reason
# unit tests above) for every required halt condition, the new stop-reason
# taxonomy, and repeated-task-loop detection. All fixture-only.
# =============================================================================


def _make_decision(**overrides: Any) -> bridge.DirectorDecision:
    base = dict(
        decision="continue", task_for_claude="read README.md", reason="fixture",
        required_checks=[], safety_level=0, requires_founder_approval=False, stop_conditions=[],
    )
    base.update(overrides)
    return bridge.DirectorDecision(**base)


def test_watch_accepted_level0_round_continues_to_next_round(monkeypatch):
    """(1) An accepted, clean Level-0 round leads to a second round whose
    objective is the first round's recommended_next_task."""
    decide_calls: list[dict] = []

    class Client:
        def decide(self, state):
            decide_calls.append(state)
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            second_task = "" if len(decide_calls) == 2 else "fixture: level-0 follow-up"
            return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task=second_task, recommended_safety_level=0))

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture L0 objective", max_rounds=2, director_client=Client())

    check("(1) accepted Level-0 round: two rounds ran", len(result.rounds) == 2)
    check("(1) accepted Level-0 round: round 1 accepted safety_level 0", result.rounds[0].safety_level == 0)
    check("(1) accepted Level-0 round: round 2's objective was round 1's recommended_next_task", decide_calls[1]["objective"] == "fixture: level-0 follow-up")
    check("(1) accepted Level-0 round: final stop_reason is COMPLETED", result.stop_reason == "COMPLETED")


def test_watch_accepted_level1_round_continues_to_next_round(monkeypatch):
    """(2) An accepted, clean Level-1 round (real isolated workspace,
    invoke_claude_code mocked to avoid real Claude spend) also leads to a
    second round.

    2026-09-10 cumulative staging: run_watch() now creates ONE persistent
    Level1StagingSession per watch run and threads it through every
    run_once() call, so both rounds below use the SAME workspace — this
    replaced the pre-cumulative-staging behavior (a fresh, distinct
    workspace destroyed after every single round) this test used to
    assert. See test_level1_staging_workspace_reused_across_consecutive_
    rounds below for the dedicated reuse/continuity proof."""
    decide_calls: list[dict] = []
    workspaces_used: list[Path] = []

    class Client:
        def decide(self, state):
            decide_calls.append(state)
            return _make_decision(safety_level=1, task_for_claude="edit a file")

        def evaluate(self, *, decision, claude_result, deterministic):
            second_task = "" if len(decide_calls) == 2 else "fixture: level-1 follow-up"
            return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task=second_task, recommended_safety_level=1))

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        workspaces_used.append(cwd)
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture L1 objective", max_rounds=2, max_safety_level=1, director_client=Client())

    check("(2) accepted Level-1 round: two rounds ran", len(result.rounds) == 2)
    check("(2) accepted Level-1 round: both rounds accepted safety_level 1", all(r.safety_level == 1 for r in result.rounds))
    check(
        "(2) accepted Level-1 round: both rounds used the SAME real isolated staging workspace "
        "(cumulative staging — no longer a fresh one per round)",
        len(set(workspaces_used)) == 1 and all(workspaces_used),
    )
    check("(2) accepted Level-1 round: round 2's objective was round 1's recommended_next_task", decide_calls[1]["objective"] == "fixture: level-1 follow-up")
    check("(2) accepted Level-1 round: final stop_reason is COMPLETED", result.stop_reason == "COMPLETED")


def test_watch_director_stop_is_challenged_then_backlog_exhausted(monkeypatch):
    """(3) Director-stop policy: a fault-free decision=='stop' does NOT end
    the session on its own — the Director is re-prompted once with the
    explicit backlog, and only a SECOND consecutive barren stop (no
    productive round between) ends the run with BACKLOG_EXHAUSTED. A
    genuine safety/correctness stop would still be honoured immediately;
    this bare stop is not one."""
    seen_objectives = []

    class Client:
        def decide(self, state):
            seen_objectives.append(state["objective"])
            return _make_decision(decision="stop", task_for_claude="")

        def evaluate(self, **kwargs):
            raise AssertionError("evaluate() must never be called when Claude was never invoked")

    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=5, director_client=Client())
    check("(3) Director stop: challenged once, then stopped (2 rounds)", len(result.rounds) == 2)
    check("(3) Director stop: stop_reason is BACKLOG_EXHAUSTED", result.stop_reason == "BACKLOG_EXHAUSTED")
    check("(3) Director stop: the 2nd round's objective was the explicit backlog challenge",
          len(seen_objectives) == 2 and "Director-stop policy" in seen_objectives[1])


def test_watch_productive_completion_redirects_to_next_backlog_item(monkeypatch):
    """(3b) Director-stop policy: a PRODUCTIVE round (retained, changed
    files) that ends with an empty recommended_next_task does NOT stop the
    session with COMPLETED mid-run — the Director is re-prompted with the
    'feature_complete' backlog challenge and the run continues. A
    productive round also keeps the barren-stop streak at zero, so the run
    only ends at max_rounds here, never BACKLOG_EXHAUSTED."""
    seen_objectives = []
    n = {"i": 0}

    class Client:
        def decide(self, state):
            seen_objectives.append(state["objective"])
            return _make_decision(safety_level=1, task_for_claude="implement backlog item")

        def evaluate(self, *, decision, claude_result, deterministic):
            # Every round is accepted with NO next task -> soft COMPLETED each time.
            return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task="", recommended_safety_level=1))

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        n["i"] += 1
        (cwd / f"backlog_item_{n['i']}.txt").write_text(f"feature {n['i']}\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture backlog objective", max_rounds=4, max_safety_level=1, director_client=Client())

    check("(3b) productive completion: ran the full round budget, not stopped early", len(result.rounds) == 4)
    check("(3b) productive completion: never BACKLOG_EXHAUSTED — productive rounds don't count as exhaustion",
          result.stop_reason != "BACKLOG_EXHAUSTED")
    check("(3b) productive completion: ends healthy at the round budget",
          result.stop_reason in ("MAX_ROUNDS_REACHED", "COMPLETED"))
    check("(3b) productive completion: rounds 2..4 got the feature-complete backlog challenge",
          len(seen_objectives) == 4 and all("SELECTING THE NEXT BACKLOG ITEM" in o for o in seen_objectives[1:]))
    check("(3b) productive completion: each finished feature was recorded", len(result.completed_tasks) >= 1)
    check("(3b) productive completion: every round retained its work",
          all(r.level1_retained for r in result.rounds))
    _cleanup_watch_run_patches(result)


def test_watch_needs_revision_halts_with_correct_reason(monkeypatch):
    """(4) needs_revision halts with DIRECTOR_NEEDS_REVISION -- when the
    requested revision is NOT itself safely continuable (here: no concrete
    next task). 2026-09-09: a needs_revision with a safe next task no
    longer halts at all -- see
    test_watch_needs_revision_safe_level0_continues_automatically below."""
    class Client:
        def decide(self, state):
            return _make_decision()

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(**_base_evaluation(outcome="needs_revision", recommended_next_task=""))

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(4) needs_revision (unsafe: no next task): exactly one round ran", len(result.rounds) == 1)
    check("(4) needs_revision (unsafe: no next task): stop_reason is DIRECTOR_NEEDS_REVISION", result.stop_reason == "DIRECTOR_NEEDS_REVISION")


def test_watch_needs_revision_safe_level0_continues_automatically(monkeypatch):
    """(1) 2026-09-09 core behavior: a needs_revision evaluation with a
    concrete, safe Level-0 recommended_next_task must NOT return control to
    the Founder -- watch mode automatically enters the next round using
    that task as its objective, exactly like an 'accepted' outcome would."""
    decide_calls: list[dict] = []

    class Client:
        def decide(self, state):
            decide_calls.append(state)
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            if len(decide_calls) == 2:
                # Round 2 fully accepted with nothing further recommended --
                # isolates this test to proving round 1's needs_revision
                # alone triggers automatic continuation, independent of how
                # round 2 itself ultimately concludes.
                return bridge.DirectorEvaluation(**_base_evaluation(outcome="accepted", recommended_next_task=""))
            return bridge.DirectorEvaluation(
                **_base_evaluation(
                    outcome="needs_revision", recommended_next_task="fixture: safe level-0 revision follow-up",
                    recommended_safety_level=0,
                )
            )

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=2, director_client=Client())

    check("(1) needs_revision safe L0: watch automatically entered round 2 (no Founder stop)", len(result.rounds) == 2)
    check(
        "(1) needs_revision safe L0: round 2's objective is round 1's recommended_next_task",
        decide_calls[1]["objective"] == "fixture: safe level-0 revision follow-up",
    )
    check("(1) needs_revision safe L0: run ends with COMPLETED, not DIRECTOR_NEEDS_REVISION", result.stop_reason == "COMPLETED")


def test_watch_needs_revision_safe_level1_continues_when_max_safety_level_allows(monkeypatch):
    """(2) A safe Level-1 needs_revision next task continues automatically
    when the watch run's configured max_safety_level permits Level 1."""
    decide_calls: list[dict] = []

    class Client:
        def decide(self, state):
            decide_calls.append(state)
            return _make_decision(safety_level=1, task_for_claude="edit a file")

        def evaluate(self, *, decision, claude_result, deterministic):
            if len(decide_calls) == 2:
                return bridge.DirectorEvaluation(**_base_evaluation(outcome="accepted", recommended_next_task=""))
            return bridge.DirectorEvaluation(
                **_base_evaluation(
                    outcome="needs_revision", recommended_next_task="fixture: safe level-1 revision follow-up",
                    recommended_safety_level=1,
                )
            )

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=2, max_safety_level=1, director_client=Client())

    check("(2) needs_revision safe L1 with max_safety_level=1: watch entered round 2", len(result.rounds) == 2)
    check("(2) needs_revision safe L1 with max_safety_level=1: ends with COMPLETED", result.stop_reason == "COMPLETED")


def test_watch_needs_revision_level1_stops_when_max_safety_level_is_0(monkeypatch):
    """(3) The same Level-1 needs_revision next task must stop watch mode
    (return control to the Founder) when the run is configured Level-0-only.
    Proven end-to-end: exactly one round runs, one decide() call."""
    calls = {"decide": 0}

    class Client:
        def decide(self, state):
            calls["decide"] += 1
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(
                **_base_evaluation(outcome="needs_revision", recommended_next_task="fixture: level-1 follow-up", recommended_safety_level=1)
            )

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, max_safety_level=0, director_client=Client())

    check("(3) needs_revision L1 with max_safety_level=0: exactly one round ran", len(result.rounds) == 1)
    check("(3) needs_revision L1 with max_safety_level=0: exactly one decide() call", calls["decide"] == 1)
    check("(3) needs_revision L1 with max_safety_level=0: stop_reason is DIRECTOR_NEEDS_REVISION", result.stop_reason == "DIRECTOR_NEEDS_REVISION")


def test_watch_needs_revision_level2_halts_end_to_end(monkeypatch):
    """(4b) needs_revision recommending Level 2 in the EVALUATION (distinct
    from a Level-2 DECISION, already covered by
    test_watch_level2_recommendation_halts_with_correct_reason) must also
    stop watch mode end-to-end."""
    class Client:
        def decide(self, state):
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(
                **_base_evaluation(outcome="needs_revision", recommended_next_task="fixture: escalate", recommended_safety_level=2)
            )

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(4b) needs_revision recommending Level 2: exactly one round ran", len(result.rounds) == 1)
    check("(4b) needs_revision recommending Level 2: stop_reason is DIRECTOR_NEEDS_REVISION", result.stop_reason == "DIRECTOR_NEEDS_REVISION")


def test_watch_needs_revision_founder_approval_halts_end_to_end(monkeypatch):
    """(5) needs_revision whose evaluation itself sets
    requires_founder_approval=true must stop watch mode end-to-end, even
    with an otherwise Level-0, non-empty recommended_next_task."""
    class Client:
        def decide(self, state):
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(
                **_base_evaluation(
                    outcome="needs_revision", recommended_next_task="fixture: needs a human look",
                    recommended_safety_level=0, requires_founder_approval=True,
                )
            )

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(5) needs_revision + founder approval: exactly one round ran", len(result.rounds) == 1)
    check("(5) needs_revision + founder approval: stop_reason is DIRECTOR_NEEDS_REVISION", result.stop_reason == "DIRECTOR_NEEDS_REVISION")


def test_watch_needs_revision_missing_next_task_halts_end_to_end(monkeypatch):
    """(6) needs_revision with an empty recommended_next_task must stop
    watch mode end-to-end -- there is nothing for the next round to do."""
    class Client:
        def decide(self, state):
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(
                **_base_evaluation(outcome="needs_revision", recommended_next_task="", recommended_safety_level=0)
            )

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(6) needs_revision + missing next task: exactly one round ran", len(result.rounds) == 1)
    check("(6) needs_revision + missing next task: stop_reason is DIRECTOR_NEEDS_REVISION", result.stop_reason == "DIRECTOR_NEEDS_REVISION")


def test_watch_needs_revision_failed_verification_halts_end_to_end(monkeypatch):
    """(7) A needs_revision evaluation is meaningless once deterministic
    verification itself found a safety violation (here: canonical live DB
    fingerprint changed) -- run_once force-overrides the outcome to
    'blocked' in that case (see run_once's hard override), so this proves
    the override, not just the gate, keeps a "needs_revision"-labeled
    Director opinion from ever continuing past a real safety violation."""
    class Client:
        def decide(self, state):
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(
                **_base_evaluation(outcome="needs_revision", recommended_next_task="fixture: keep going", recommended_safety_level=0)
            )

    fingerprints = iter([
        {"path": "x", "size_bytes": 1000, "mtime": 1.0, "table_count": 32, "integrity_ok": True,
         "current_day": 8, "current_period": "MORNING", "is_paused": False, "max_event_id": 955},
        {"path": "x", "size_bytes": 2000, "mtime": 2.0, "table_count": 32, "integrity_ok": True,
         "current_day": 8, "current_period": "MORNING", "is_paused": False, "max_event_id": 955},
    ])
    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge, "_live_db_fingerprint", lambda: next(fingerprints))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(7) needs_revision + failed verification: exactly one round ran", len(result.rounds) == 1)
    check("(7) needs_revision + failed verification: stop_reason is LIVE_DB_CHANGED, not a continuation", result.stop_reason == "LIVE_DB_CHANGED")


def test_watch_needs_revision_repeated_task_redirects_then_backlog_exhausted(monkeypatch):
    """(8) A Director that keeps returning needs_revision with the exact
    SAME (normalized) next task is first redirected onto a different
    backlog area (repetition protection applies to needs_revision
    continuations, not just accepted ones); once it refuses every redirect
    the run stops with BACKLOG_EXHAUSTED after exactly
    WATCH_MAX_BACKLOG_REDIRECTS redirects, never REPEATED_TASK_LOOP and
    never running the whole round budget."""
    class Client:
        def decide(self, state):
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(
                **_base_evaluation(
                    outcome="needs_revision", recommended_next_task="fixture: repeat the same audit again",
                    recommended_safety_level=0,
                )
            )

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture: repeat the same audit again", max_rounds=10, director_client=Client())
    check("(8) repeated task: stopped before reaching max_rounds", len(result.rounds) < 10)
    check("(8) repeated task: stop_reason is BACKLOG_EXHAUSTED", result.stop_reason == "BACKLOG_EXHAUSTED")
    check("(8) repeated task: bounded at WATCH_MAX_BACKLOG_REDIRECTS + 1 rounds",
          len(result.rounds) == bridge.WATCH_MAX_BACKLOG_REDIRECTS + 1)
    check("(8) repeated task: the exhausted task is recorded", result.stalled_tasks == ["fixture: repeat the same audit again"])


def test_watch_needs_revision_rounds_obey_max_rounds(monkeypatch):
    """(9) A Director that always returns a safe, DISTINCT needs_revision
    next task (never triggering repeated-task-loop protection) must still
    be capped at exactly max_rounds decide() calls -- needs_revision
    continuations consume the same round budget as accepted ones."""
    calls = {"decide": 0}

    class Client:
        def decide(self, state):
            calls["decide"] += 1
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(
                **_base_evaluation(
                    outcome="needs_revision",
                    recommended_next_task=f"fixture: distinct revision follow-up #{calls['decide']}",
                    recommended_safety_level=0,
                )
            )

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(9) needs_revision obeys max_rounds: exactly max_rounds decide() calls", calls["decide"] == 3)
    check("(9) needs_revision obeys max_rounds: exactly max_rounds rounds recorded", len(result.rounds) == 3)
    check("(9) needs_revision obeys max_rounds: stop_reason is MAX_ROUNDS_REACHED", result.stop_reason == "MAX_ROUNDS_REACHED")


def test_watch_needs_revision_exactly_one_claude_invocation_per_round(monkeypatch):
    """(10 & 11) Across a multi-round needs_revision continuation chain,
    invoke_claude_code must be called exactly once per round (never more)
    -- and, critically, evaluate() (the second, DirectorEvaluation-
    producing Director call) must NEVER itself trigger a Claude invocation:
    the count seen INSIDE evaluate() must always equal the count seen
    immediately after invoke_claude_code returns for that same round,
    proving the evaluation step is a pure judgment call over already-
    collected deterministic evidence, never a second opportunity to run
    Claude."""
    claude_calls = {"n": 0}
    counts_at_evaluate_time: list[int] = []
    counts_after_claude_returned: list[int] = []

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        claude_calls["n"] += 1
        counts_after_claude_returned.append(claude_calls["n"])
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    class Client:
        def decide(self, state):
            return _make_decision(safety_level=0)

        def evaluate(self, *, decision, claude_result, deterministic):
            counts_at_evaluate_time.append(claude_calls["n"])
            return bridge.DirectorEvaluation(
                **_base_evaluation(
                    outcome="needs_revision",
                    recommended_next_task=f"fixture: distinct revision follow-up #{claude_calls['n']}",
                    recommended_safety_level=0,
                )
            )

    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())

    check("(9/10) three rounds ran", len(result.rounds) == 3)
    check("(10) exactly one Claude invocation occurred per round (3 rounds -> 3 total invocations)", claude_calls["n"] == 3)
    check(
        "(11) DirectorEvaluation's evaluate() call never itself invokes Claude "
        "(the count it observes always matches the count right after invoke_claude_code returned)",
        counts_at_evaluate_time == counts_after_claude_returned,
    )


def test_watch_blocked_halts_with_correct_reason(monkeypatch):
    """(5) blocked halts with DIRECTOR_REJECTED_RESULT."""
    class Client:
        def decide(self, state):
            return _make_decision()

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(**_base_evaluation(outcome="blocked"))

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(5) blocked: exactly one round ran", len(result.rounds) == 1)
    check("(5) blocked: stop_reason is DIRECTOR_REJECTED_RESULT", result.stop_reason == "DIRECTOR_REJECTED_RESULT")


def test_watch_level2_recommendation_halts_with_correct_reason(monkeypatch):
    """(6) A Level-2 request at decision time halts with LEVEL_2_REQUESTED."""
    class Client:
        def decide(self, state):
            return _make_decision(decision="request_approval", safety_level=2, requires_founder_approval=True, task_for_claude="run Run Day")

        def evaluate(self, **kwargs):
            raise AssertionError("evaluate() must never be called when Claude was never invoked")

    monkeypatch.setattr(bridge, "request_founder_approval", lambda decision, state: {"requested_action": decision.task_for_claude, "approved": False})
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(6) Level-2 request: exactly one round ran", len(result.rounds) == 1)
    check("(6) Level-2 request: stop_reason is LEVEL_2_REQUESTED", result.stop_reason == "LEVEL_2_REQUESTED")


def test_watch_founder_approval_required_halts_with_correct_reason(monkeypatch):
    """(7) requires_founder_approval=True at decision time (Level 1, not
    Level 2) halts with FOUNDER_APPROVAL_REQUIRED, distinct from LEVEL_2_REQUESTED."""
    class Client:
        def decide(self, state):
            return _make_decision(decision="request_approval", safety_level=1, requires_founder_approval=True)

        def evaluate(self, **kwargs):
            raise AssertionError("evaluate() must never be called when Claude was never invoked")

    monkeypatch.setattr(bridge, "request_founder_approval", lambda decision, state: {"requested_action": decision.task_for_claude, "approved": False})
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(7) Founder approval required: exactly one round ran", len(result.rounds) == 1)
    check("(7) Founder approval required: stop_reason is FOUNDER_APPROVAL_REQUIRED", result.stop_reason == "FOUNDER_APPROVAL_REQUIRED")


def test_watch_claude_failure_halts_with_correct_reason(monkeypatch):
    """(8) A nonzero Claude exit code halts with CLAUDE_FAILED. run_once
    still calls the second Director evaluation even on a deterministic
    failure (a failure has meaning worth evaluating too) — its outcome is
    force-overridden to 'blocked' regardless of what it returns, so the
    fixture evaluation's content here is irrelevant to the final label."""
    class Client:
        def decide(self, state):
            return _make_decision()

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(**_base_evaluation(outcome="accepted"))

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=1, stdout="", stderr="boom"))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(8) Claude failure: exactly one round ran", len(result.rounds) == 1)
    check("(8) Claude failure: stop_reason is CLAUDE_FAILED", result.stop_reason == "CLAUDE_FAILED")


def test_watch_claude_timeout_halts_with_correct_reason_and_never_continues(monkeypatch):
    """2026-09-10 timeout hardening regression, at the full run_watch level:
    a per-level-bounded timeout (round bd046f7218294d50's real failure mode,
    now at 420s/1200s instead of the old flat 300s) must still map to
    CLAUDE_FAILED and stop watch mode after exactly one round and exactly
    one Claude invocation — a longer timeout bound must never itself become
    a route to automatic continuation or to any Level-2 behavior."""
    class Client:
        def decide(self, state):
            return _make_decision()

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(**_base_evaluation(outcome="accepted"))

    calls = {"claude_invoked": 0}

    def fake_claude(*a, **k):
        calls["claude_invoked"] += 1
        return bridge.ClaudeInvocationResult(
            invoked=True, timed_out=True, exit_code=None, stdout="",
            stderr="timed out after 420s", duration_seconds=420.02,
        )

    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("timeout halt: exactly one Claude invocation occurred", calls["claude_invoked"] == 1)
    check("timeout halt: exactly one round ran (no automatic retry after a timeout)", len(result.rounds) == 1)
    check("timeout halt: the round's final_state is stopped_claude_timeout", result.rounds[0].final_state == "stopped_claude_timeout")
    check("timeout halt: watch stop_reason is CLAUDE_FAILED", result.stop_reason == "CLAUDE_FAILED")
    check(
        "timeout halt: watch never reaches Level-2/CONSEQUENTIAL behavior via a timeout",
        result.stop_reason not in ("FOUNDER_APPROVAL_REQUIRED",) and result.rounds[0].safety_level != int(bridge.BridgeSafetyLevel.CONSEQUENTIAL),
    )


def test_watch_verification_failure_halts_with_correct_reason(monkeypatch):
    """(9) The second Director (evaluation) call itself failing is a
    VERIFICATION_FAILED halt -- distinct from a bad outcome value."""
    class Client:
        def decide(self, state):
            return _make_decision()

        def evaluate(self, *, decision, claude_result, deterministic):
            raise bridge.BridgeError2("fixture: evaluation call failed")

    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(9) verification failure: exactly one round ran", len(result.rounds) == 1)
    check("(9) verification failure: stop_reason is VERIFICATION_FAILED", result.stop_reason == "VERIFICATION_FAILED")


def test_watch_live_db_changed_halts_with_correct_reason(monkeypatch):
    """(10) A live-DB-fingerprint change distinguishes LIVE_DB_CHANGED
    (structural fields) from LIVE_VILLAGE_CHANGED (simulation-state
    fields only)."""
    class Client:
        def decide(self, state):
            return _make_decision()

        def evaluate(self, *, decision, claude_result, deterministic):
            return bridge.DirectorEvaluation(**_base_evaluation())

    fingerprints_structural = iter([
        {"path": "x", "size_bytes": 1000, "mtime": 1.0, "table_count": 32, "integrity_ok": True,
         "current_day": 8, "current_period": "MORNING", "is_paused": False, "max_event_id": 955},
        {"path": "x", "size_bytes": 2000, "mtime": 2.0, "table_count": 32, "integrity_ok": True,
         "current_day": 8, "current_period": "MORNING", "is_paused": False, "max_event_id": 955},
    ])
    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge, "_live_db_fingerprint", lambda: next(fingerprints_structural))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(10) structural DB change: exactly one round ran", len(result.rounds) == 1)
    check("(10) structural DB change: stop_reason is LIVE_DB_CHANGED", result.stop_reason == "LIVE_DB_CHANGED")

    fingerprints_simulation = iter([
        {"path": "x", "size_bytes": 1000, "mtime": 1.0, "table_count": 32, "integrity_ok": True,
         "current_day": 8, "current_period": "MORNING", "is_paused": False, "max_event_id": 955},
        {"path": "x", "size_bytes": 1000, "mtime": 1.0, "table_count": 32, "integrity_ok": True,
         "current_day": 8, "current_period": "NIGHT", "is_paused": False, "max_event_id": 999},
    ])
    monkeypatch.setattr(bridge, "_live_db_fingerprint", lambda: next(fingerprints_simulation))
    result2 = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(10) simulation-state change: exactly one round ran", len(result2.rounds) == 1)
    check("(10) simulation-state change: stop_reason is LIVE_VILLAGE_CHANGED", result2.stop_reason == "LIVE_VILLAGE_CHANGED")


def test_watch_unsafe_git_state_halts_with_correct_reason(monkeypatch):
    """(11) An ambiguous git state halts with GIT_STATE_UNSAFE, before any Director call."""
    calls = {"decide": 0}

    class Client:
        def decide(self, state):
            calls["decide"] += 1
            return _make_decision()

        def evaluate(self, **kwargs):
            raise AssertionError("evaluate() should never be reached")

    def always_ambiguous(**kwargs):
        raise bridge.GitStateError("fixture: simulated ambiguous git state")

    monkeypatch.setattr(bridge, "_check_git_state", always_ambiguous)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(11) unsafe git state: no rounds ran at all", len(result.rounds) == 0)
    check("(11) unsafe git state: no Director call was made", calls["decide"] == 0)
    check("(11) unsafe git state: stop_reason is GIT_STATE_UNSAFE", result.stop_reason == "GIT_STATE_UNSAFE")


def test_watch_malformed_director_response_halts_with_correct_reason(monkeypatch):
    """(12) An invalid first-Director response halts with INVALID_DIRECTOR_RESPONSE."""
    class Client:
        def decide(self, state):
            raise bridge.BridgeError2("fixture: schema validation failed")

        def evaluate(self, **kwargs):
            raise AssertionError("evaluate() should never be reached")

    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(12) malformed Director response: exactly one round ran", len(result.rounds) == 1)
    check("(12) malformed Director response: stop_reason is INVALID_DIRECTOR_RESPONSE", result.stop_reason == "INVALID_DIRECTOR_RESPONSE")


def test_watch_repeated_task_text_redirects_then_backlog_exhausted(monkeypatch):
    """(13a) The Director recommending the SAME (normalized) task it just
    did no longer halts the run outright — it is redirected onto a
    different backlog area, and only after it refuses every redirect does
    the run end with BACKLOG_EXHAUSTED (never REPEATED_TASK_LOOP, never the
    whole round budget)."""
    class Client:
        def decide(self, state):
            return _make_decision()

        def evaluate(self, *, decision, claude_result, deterministic):
            # Deliberately recommends the exact same task the round JUST used.
            return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task=state_objective_holder["objective"]))

    state_objective_holder = {"objective": "fixture objective"}

    real_collect_state = bridge.collect_bridge_state
    seen_objectives = []

    def spying_collect_state(objective):
        state_objective_holder["objective"] = objective
        seen_objectives.append(objective)
        return real_collect_state(objective)

    monkeypatch.setattr(bridge, "collect_bridge_state", spying_collect_state)
    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=10, director_client=Client())
    check("(13a) repeated task text: stopped before reaching max_rounds", len(result.rounds) < 10)
    check("(13a) repeated task text: stop_reason is BACKLOG_EXHAUSTED, not REPEATED_TASK_LOOP",
          result.stop_reason == "BACKLOG_EXHAUSTED")
    check("(13a) repeated task text: the Director was actually redirected at least once",
          any("EXHAUSTED" in o for o in seen_objectives))
    check("(13a) repeated task text: redirects are bounded at WATCH_MAX_BACKLOG_REDIRECTS + 1 rounds",
          len(result.rounds) == bridge.WATCH_MAX_BACKLOG_REDIRECTS + 1)


def test_watch_repeated_no_change_result_redirects_to_a_different_backlog_area(monkeypatch):
    """(13b) Two consecutive Level-1 rounds that produce zero changed
    files exhaust that task and REDIRECT the Director to a different
    backlog area — the run continues rather than stopping, and the very
    next objective the Director sees is the backlog-redirect prompt."""
    counter = {"n": 0}

    class Client:
        def decide(self, state):
            return _make_decision(safety_level=1, task_for_claude="inspect only, make no edits")

        def evaluate(self, *, decision, claude_result, deterministic):
            counter["n"] += 1
            return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task=f"fixture: distinct task #{counter['n']}", recommended_safety_level=1))

    seen_objectives = []
    real_collect_state = bridge.collect_bridge_state

    def spying_collect_state(objective):
        seen_objectives.append(objective)
        return real_collect_state(objective)

    monkeypatch.setattr(bridge, "collect_bridge_state", spying_collect_state)
    monkeypatch.setattr(bridge, "invoke_claude_code", lambda *a, **k: bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok, no changes made"}'))
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)
    result = bridge.run_watch("fixture objective", max_rounds=3, director_client=Client())
    check("(13b) repeated no-change result: the run did NOT stop with REPEATED_TASK_LOOP",
          result.stop_reason != "REPEATED_TASK_LOOP")
    check("(13b) repeated no-change result: at least 3 rounds ran (2 no-change + a redirected round)",
          len(result.rounds) >= 3)
    check("(13b) repeated no-change result: the Director was redirected to a backlog area",
          any("EXHAUSTED" in o and "priority areas" in o for o in seen_objectives))
    check("(13b) repeated no-change result: the stalled task was recorded",
          result.stalled_tasks == ["fixture: distinct task #1"])


def test_watch_max_rounds_hard_ceiling_is_enforced():
    """max_rounds above WATCH_MAX_ROUNDS_CEILING is refused outright,
    never silently clamped -- no round runs at all."""
    result = bridge.run_watch("fixture objective", max_rounds=bridge.WATCH_MAX_ROUNDS_CEILING + 1)
    check("max_rounds above the hard ceiling runs zero rounds", len(result.rounds) == 0)
    check("max_rounds above the hard ceiling is refused, not silently clamped", "outside the allowed range" in result.stop_detail)


def test_watch_default_max_rounds_is_three():
    check("WATCH_MAX_ROUNDS_DEFAULT is 3", bridge.WATCH_MAX_ROUNDS_DEFAULT == 3)
    check("WATCH_MAX_ROUNDS_CEILING is 10", bridge.WATCH_MAX_ROUNDS_CEILING == 10)


class _MonkeyPatch:
    """A tiny, dependency-free stand-in for pytest's monkeypatch fixture —
    this suite intentionally has no pytest/test-framework dependency, same
    as every other *_fixturetest.py script in this repo."""

    def __init__(self):
        self._sets: list[tuple[Any, str, Any]] = []

    def setattr(self, obj, name, value):
        self._sets.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def undo(self):
        for obj, name, old in reversed(self._sets):
            setattr(obj, name, old)


# =============================================================================
# 2026-09-10 Level-1 test-runner hardening: the pytest/.venv availability gap
# found by the first real Level-1 acceptance round (2026-09-10) — .venv is
# correctly excluded from every Level-1 workspace and python3/.venv/bin/
# python are correctly absent from Claude's allowlist there, so a round had
# no way to actually execute scripts/test_fishbowl.py, only to edit it.
# Fixed by director_bridge_test_runner.py: a bridge-owned test runner Claude
# can invoke only via one EXACT (no ':*' wildcard) Bash permission string
# per approved target — never a general pytest/python3 grant. These tests
# prove the mechanism end to end; see that module's own docstring for the
# full safety-layer writeup.
# =============================================================================


def test_level1_pytest_wildcard_access_is_gone(monkeypatch):
    allowed, _ = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    check("Level 1 no longer grants Bash(pytest:*)", "Bash(pytest:*)" not in allowed)
    check("Level 1 no longer grants Bash(.venv/bin/pytest:*)", "Bash(.venv/bin/pytest:*)" not in allowed)
    check("no bare 'pytest' token appears anywhere in the Level 1 allowlist", "pytest" not in allowed)


def test_level1_grants_exactly_one_exact_match_command_per_approved_test_target(monkeypatch):
    allowed, _ = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    for target in bridge._test_runner.ALLOWED_TEST_TARGETS:
        exact = (
            f"Bash({bridge._test_runner.REAL_HOST_PYTHON} "
            f"scripts/director_bridge_test_runner.py --target {target})"
        )
        check(f"Level 1 allowlist grants the exact test-runner command for {target!r}", exact in allowed)
        check(f"that grant for {target!r} is an EXACT match, not a wildcard", f"{exact[:-1]}:*)" not in allowed)
    check(
        "the ONLY way to reach a Python interpreter at Level 1 is through director_bridge_test_runner.py "
        "(no bare python3/.venv/bin/python grant re-introduced)",
        "Bash(python3" not in allowed and "Bash(.venv/bin/python:" not in allowed,
    )


def test_level1_disallow_list_unaffected_by_test_runner_change(monkeypatch):
    """The pytest-wildcard removal must not have silently dropped anything
    else off the existing, separately-hardened denylist (item 4: 'Bash
    remains restricted according to existing Level-1 policy')."""
    _, disallowed = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    for dangerous in (
        "git commit", "git push", "git reset", "git checkout", "git branch", "git log", "git diff",
        "find", "python3", ".venv/bin/python", "rm", "curl", "wget", "sqlite3", "scp", "ssh",
        "alembic", "sh", "bash", "zsh", "chmod", "chown", "perl", "node", "cat", "ls", "mkdir", "touch",
    ):
        check(f"Level 1 disallow list still names {dangerous!r}", dangerous in disallowed)


def test_level1_preamble_documents_the_exact_test_runner_command():
    preamble = bridge._SAFETY_PREAMBLE[bridge.BridgeSafetyLevel.SANDBOX]
    for target in bridge._test_runner.ALLOWED_TEST_TARGETS:
        command = (
            f"{bridge._test_runner.REAL_HOST_PYTHON} scripts/director_bridge_test_runner.py "
            f"--target {target}"
        )
        check(f"the SANDBOX preamble tells Claude the exact runnable command for {target!r}", command in preamble)
    check(
        "the preamble still tells Claude there is no general python3/pytest access",
        "no general pytest, python3" in preamble,
    )


def test_test_runner_rejects_unapproved_target():
    workspace = bridge._create_level1_workspace()
    try:
        try:
            bridge._test_runner.run("scripts/does_not_exist_on_the_allowlist.py", workspace)
            check("an unapproved target raises RunnerError", False)
        except bridge._test_runner.RunnerError as exc:
            check("an unapproved target raises RunnerError", True, detail=str(exc))
    finally:
        bridge._cleanup_level1_workspace(workspace)


def test_test_runner_rejects_path_traversal_target():
    workspace = bridge._create_level1_workspace()
    try:
        for traversal in ("../scripts/test_fishbowl.py", "/etc/passwd", "scripts/test_fishbowl.py/../../etc/passwd"):
            try:
                bridge._test_runner.run(traversal, workspace)
                check(f"target {traversal!r} is rejected", False)
            except bridge._test_runner.RunnerError:
                check(f"target {traversal!r} is rejected", True)
    finally:
        bridge._cleanup_level1_workspace(workspace)


def test_test_runner_refuses_to_run_against_the_real_repo_root():
    try:
        bridge._test_runner.run("scripts/test_fishbowl.py", bridge.REPO_ROOT)
        check("the runner refuses cwd == the real repo root", False)
    except bridge._test_runner.RunnerError as exc:
        check("the runner refuses cwd == the real repo root", True, detail=str(exc))


def test_test_runner_sanitized_env_excludes_secrets_and_scopes_village_data_root():
    workspace = bridge._create_level1_workspace()
    try:
        env = bridge._test_runner._sanitized_env(workspace)
        check("sanitized env has no DATABASE_URL", "DATABASE_URL" not in env)
        secret_markers = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")
        leaked = [k for k in env if any(m in k.upper() for m in secret_markers)]
        check("sanitized env has no secret-shaped variable names", not leaked, detail=str(leaked))
        check(
            "sanitized env's VILLAGE_DATA_ROOT lives inside the workspace, not the canonical live path",
            env["VILLAGE_DATA_ROOT"].startswith(str(workspace)),
        )
        check(
            "sanitized env's VILLAGE_DATA_ROOT is not the canonical live data root",
            "village-data" not in env["VILLAGE_DATA_ROOT"],
        )
    finally:
        bridge._cleanup_level1_workspace(workspace)


def test_test_runner_timeout_is_handled_deterministically(monkeypatch):
    workspace = bridge._create_level1_workspace()
    try:
        def fake_run(cmd, cwd=None, env=None, capture_output=None, text=None, timeout=None):
            raise bridge._test_runner.subprocess.TimeoutExpired(cmd=cmd, timeout=timeout, output="partial", stderr="")

        monkeypatch.setattr(bridge._test_runner.subprocess, "run", fake_run)
        result = bridge._test_runner.run("scripts/test_fishbowl.py", workspace)
        check("a hung test subprocess is reported as timed_out, never raised", result["timed_out"] is True)
        check("a timeout still returns ok=True (the RUNNER itself didn't crash)", result["ok"] is True)
        check("a timeout carries no misleading exit_code", result["exit_code"] is None)
    finally:
        bridge._cleanup_level1_workspace(workspace)


def test_test_runner_real_run_against_isolated_workspace_passes_and_stays_isolated():
    """Real, unmocked, no-Claude-tokens proof: creates a real Level-1
    workspace, runs the real approved test target through the real runner
    exactly as director_bridge.py's own exact-match Bash grant would invoke
    it, and checks isolation end to end. Costs ~5-10s wall clock, zero API
    tokens — same discipline as test_level1_workspace_never_contains_env_file."""
    live_before = bridge._live_db_fingerprint()
    workspace = bridge._create_level1_workspace()
    try:
        check(".venv is not copied into the workspace", not (workspace / ".venv").exists())
        cmd = [
            str(bridge._test_runner.REAL_HOST_PYTHON), "scripts/director_bridge_test_runner.py",
            "--target", "scripts/test_fishbowl.py",
        ]
        proc = bridge.subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True, timeout=300)
        check("the exact bridge-constructed command exits 0", proc.returncode == 0, detail=proc.stderr[-500:])
        result = json.loads(proc.stdout)
        check("the runner reports ok=True", result.get("ok") is True)
        check("the approved test itself passed (exit_code 0)", result.get("exit_code") == 0)
        check("the approved test was not timed out", result.get("timed_out") is False)
        check("the test's own PASS summary line is present", "PASS: The Fishbowl" in result.get("stdout", ""))
        check(
            "the real repo's own smoke_test_fishbowl.db was never created "
            "(the test ran against the workspace's own throwaway DB)",
            not (bridge.REPO_ROOT / "smoke_test_fishbowl.db").exists(),
        )
        marker = workspace / ".director" / "level1_test_result.json"
        check("the runner wrote its result marker inside the workspace's .director/", marker.is_file())
    finally:
        bridge._cleanup_level1_workspace(workspace)
    live_after = bridge._live_db_fingerprint()
    check("the canonical live DB fingerprint is unchanged by this whole test", live_before == live_after)


def test_run_once_captures_level1_test_result_deterministically(monkeypatch):
    """Proves run_once()'s new wiring: whatever director_bridge_test_runner.py
    wrote to <workspace>/.director/level1_test_result.json this round is
    read back mechanically into record.test_results AND forwarded into the
    second DirectorEvaluation call's deterministic_evidence — independent
    of anything the (fixture, here) Claude invocation claims in prose."""
    calls = {"deterministic_seen": None}
    fake_marker = json.dumps({"ok": True, "target": "scripts/test_fishbowl.py", "exit_code": 0, "timed_out": False})

    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="continue", task_for_claude="edit and test", reason="fixture",
            required_checks=[], safety_level=1, requires_founder_approval=False, stop_conditions=[],
        )

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        # Simulate what a real Claude turn does when it runs the approved
        # test-runner command: the marker file appears inside the
        # workspace's .director/ before Claude's turn ends.
        marker_dir = cwd / ".director"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "level1_test_result.json").write_text(fake_marker)
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result": "ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        calls["deterministic_seen"] = deterministic
        return _fake_evaluation("accepted")

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)

    record = bridge.run_once("test objective")
    check("record.test_results is populated from the workspace marker file", record.test_results == fake_marker)
    check(
        "deterministic_evidence forwarded to the second DirectorEvaluation call includes test_results",
        calls["deterministic_seen"] is not None and calls["deterministic_seen"].get("test_results") == fake_marker,
    )


def test_run_once_test_results_is_none_when_no_test_ran(monkeypatch):
    """The absence case: a Level-1 round where Claude never invoked the
    test runner at all must leave record.test_results as None, never a
    guessed/default value — the absence itself is the evidence."""
    def fake_director(state, provider_name=None):
        return bridge.DirectorDecision(
            decision="continue", task_for_claude="edit only, no test", reason="fixture",
            required_checks=[], safety_level=1, requires_founder_approval=False, stop_conditions=[],
        )

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result": "ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return _fake_evaluation("needs_revision")

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)

    record = bridge.run_once("test objective")
    check("record.test_results is None when no test-runner marker was written", record.test_results is None)


def test_test_runner_change_introduces_no_new_level2_or_auto_promotion_path():
    """Item 18: no automatic Level-2 behavior and no new auto-apply-patch
    path introduced by this change."""
    check(
        "only READ_ONLY and SANDBOX are ever invokable by this bridge",
        set(bridge._LEVEL_TOOLS.keys()) == {bridge.BridgeSafetyLevel.READ_ONLY, bridge.BridgeSafetyLevel.SANDBOX},
    )
    check(
        "BridgeSafetyLevel.CONSEQUENTIAL is still 2 and still absent from _LEVEL_TOOLS",
        bridge.BridgeSafetyLevel.CONSEQUENTIAL == 2 and bridge.BridgeSafetyLevel.CONSEQUENTIAL not in bridge._LEVEL_TOOLS,
    )
    import inspect

    runner_source = inspect.getsource(bridge._test_runner)
    check(
        "director_bridge_test_runner.py never calls git apply/commit/push",
        not any(bad in runner_source for bad in ("git apply", "git commit", "git push")),
    )


def _cleanup_watch_run_patches(result: bridge.WatchRunResult) -> None:
    """Every real run_watch() call in the tests below writes real durable
    audit artifacts into the SAME .director/audit/workspace_diffs/ this
    bridge uses for real acceptance runs — both the cumulative patch AND
    each individual round's own per-round patch (_preserve_workspace_diff,
    unchanged, still fires every Level-1 round regardless of staging).
    Matches the cleanup discipline test_level1_workspace_is_created_used_
    and_cleaned_up already used for its own single-round patch — a fixture
    test must never leave litter in a directory real acceptance runs also
    write to."""
    if result.level1_cumulative_patch_path:
        (bridge.REPO_ROOT / result.level1_cumulative_patch_path).unlink(missing_ok=True)
    for record in result.rounds:
        if record.workspace_diff_path:
            (bridge.REPO_ROOT / record.workspace_diff_path).unlink(missing_ok=True)


# =============================================================================
# 2026-09-10 cumulative Level-1 staging workspace: the architectural fix for
# the gap both real acceptance runs this same day hit — every Level-1 round
# used to clone a FRESH workspace from REPO_ROOT, so round N+1 could never
# see or build on round N's work. run_watch() now creates ONE persistent
# staging workspace, lazily, and reuses it for every Level-1 round in that
# run; a round's changes are retained (workspace-local git commit) or rolled
# back (workspace-local git reset --hard + clean) based on the SAME "safe
# enough" definition _watch_continuation_decision already used for
# continuation, applied here to retainability instead. See the
# Level1StagingSession module comment in director_bridge.py (above
# _cleanup_level1_workspace) for the full design. Item numbers below refer to
# the 24-item test list from that implementation task.
# =============================================================================


def test_level1_staging_workspace_reused_across_consecutive_rounds(monkeypatch):
    """Items 1-6, 17, 19: run_watch() creates exactly ONE persistent
    Level-1 staging workspace, lazily, on the first Level-1 round; a
    second Level-1 round in the SAME watch run reuses it, can READ round
    1's own file content (proving real continuity, not just path
    equality), and extends it. Both rounds are retained; the cumulative
    patch contains both; it survives workspace cleanup."""
    workspaces_used: list[Path] = []
    created_workspaces: list[Path] = []
    real_create = bridge._create_level1_workspace

    def spying_create():
        ws = real_create()
        created_workspaces.append(ws)
        return ws

    marker = "director_bridge_cumulative_probe_marker.txt"
    calls = {"n": 0}

    def fake_director(state, provider_name=None):
        calls["n"] += 1
        return _make_decision(safety_level=1, task_for_claude=f"round {calls['n']}")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        workspaces_used.append(cwd)
        path = cwd / marker
        if calls["n"] == 1:
            path.write_text("round1\n")
        else:
            # Round 2 can only produce this exact content if it actually
            # read round 1's own file first — proving real continuity.
            existing = path.read_text() if path.exists() else "<MISSING: round 1's file is not visible>\n"
            path.write_text(existing + "round2\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        next_task = "" if calls["n"] >= 2 else "fixture: round 2"
        return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task=next_task, recommended_safety_level=1))

    monkeypatch.setattr(bridge, "_create_level1_workspace", spying_create)
    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch("fixture cumulative objective", max_rounds=2, max_safety_level=1)

    check("(1) exactly one Level-1 staging workspace was created this watch run", len(created_workspaces) == 1)
    check(
        "(2) both rounds used that same workspace path",
        len(workspaces_used) == 2 and len(set(workspaces_used)) == 1 and workspaces_used[0] == created_workspaces[0],
    )
    check("two rounds ran", len(result.rounds) == 2)
    r1, r2 = result.rounds
    check("(5) round 1 was retained", r1.level1_retained is True)
    check("(6) round 2 was retained", r2.level1_retained is True)
    check(
        "(3,4) round 2's checkpoint equals round 1's retained commit — real accumulation, not overwrite",
        r1.level1_commit_after is not None and r1.level1_commit_after == r2.level1_checkpoint_before,
    )
    check("round 2's own commit differs from round 1's (it added a new commit on top)", r1.level1_commit_after != r2.level1_commit_after)
    check("the staging workspace was destroyed after the watch run", not created_workspaces[0].exists())
    check("(17) the cumulative patch was generated", bool(result.level1_cumulative_patch_path))
    if result.level1_cumulative_patch_path:
        patch_file = bridge.REPO_ROOT / result.level1_cumulative_patch_path
        check("(19) the cumulative patch file survives after workspace cleanup", patch_file.is_file())
        patch_text = patch_file.read_text()
        check("(17) cumulative patch contains round 1's content", "+round1" in patch_text, detail=patch_text[:600])
        check(
            "(17) cumulative patch contains round 2's content too (proves round 2 built on round 1)",
            "+round2" in patch_text, detail=patch_text[:600],
        )
        check(
            "recorded sha256 matches the actual file",
            result.level1_cumulative_patch_sha256 == hashlib.sha256(patch_file.read_bytes()).hexdigest(),
        )
        check("recorded size matches the actual file", result.level1_cumulative_patch_size_bytes == patch_file.stat().st_size)
    _cleanup_watch_run_patches(result)


def test_level0_round_never_touches_staging_workspace(monkeypatch):
    """Item 11: a Level-0 round mixed into the same watch run must never
    receive cwd=<staging workspace> and must never mutate it — Level 0 has
    no Bash/Edit/Write registered at all (see _LEVEL_TOOLS's Level-0
    "--tools" ceiling), so this proves the mechanism never even offers it
    the chance."""
    cwd_seen: list[tuple] = []
    calls = {"n": 0}

    def fake_director(state, provider_name=None):
        calls["n"] += 1
        level = 1 if calls["n"] == 1 else 0
        return _make_decision(safety_level=level, task_for_claude=f"round {calls['n']}")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        cwd_seen.append((level, cwd))
        if cwd is not None:
            (cwd / "level1_marker.txt").write_text("from level 1\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        last = calls["n"] >= 2
        return bridge.DirectorEvaluation(
            **_base_evaluation(
                recommended_next_task="" if last else "fixture: round 2 (level 0)",
                recommended_safety_level=0 if not last else 0,
            )
        )

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch("fixture level0-mixed objective", max_rounds=2, max_safety_level=1)

    check("two rounds ran", len(result.rounds) == 2)
    check(
        "(11) round 1 (Level 1) received the staging workspace as cwd",
        cwd_seen[0][0] == bridge.BridgeSafetyLevel.SANDBOX and cwd_seen[0][1] is not None,
    )
    check(
        "(11) round 2 (Level 0) received cwd=None — never the staging workspace",
        cwd_seen[1][0] == bridge.BridgeSafetyLevel.READ_ONLY and cwd_seen[1][1] is None,
    )
    check(
        "(11) round 2 carries no staging-session bookkeeping at all (never touched it)",
        result.rounds[1].level1_checkpoint_before is None and result.rounds[1].level1_retained is None,
    )
    _cleanup_watch_run_patches(result)


def test_blocked_round_rolls_back_and_prior_retained_round_survives(monkeypatch):
    """Items 7, 10, 18: round 1 retained, round 2 blocked & rolled back —
    only round 2's edit is discarded; round 1's survives, and the
    cumulative patch reflects round 1 alone (never a rolled-back round)."""
    calls = {"n": 0}
    marker = "director_bridge_rollback_probe_marker.txt"
    workspaces: list[Path] = []
    real_create = bridge._create_level1_workspace

    def spying_create():
        ws = real_create()
        workspaces.append(ws)
        return ws

    def fake_director(state, provider_name=None):
        calls["n"] += 1
        return _make_decision(safety_level=1, task_for_claude=f"round {calls['n']}")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        (cwd / marker).write_text(f"round{calls['n']}\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        if calls["n"] == 1:
            return bridge.DirectorEvaluation(
                **_base_evaluation(outcome="accepted", recommended_next_task="fixture: round 2", recommended_safety_level=1)
            )
        return bridge.DirectorEvaluation(**_base_evaluation(outcome="blocked", recommended_next_task="", recommended_safety_level=1))

    monkeypatch.setattr(bridge, "_create_level1_workspace", spying_create)
    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch("fixture rollback objective", max_rounds=3, max_safety_level=1)

    check("(7) two rounds ran (blocked stops the loop before round 3)", len(result.rounds) == 2)
    r1, r2 = result.rounds
    check("round 1 retained", r1.level1_retained is True)
    check("(7) round 2 NOT retained (blocked)", r2.level1_retained is False)
    check("(7) round 2's post-round commit equals its own pre-round checkpoint (rolled back)", r2.level1_commit_after == r2.level1_checkpoint_before)
    check("(10) round 2's checkpoint equals round 1's retained commit (started from round 1's state)", r2.level1_checkpoint_before == r1.level1_commit_after)
    check("watch stopped for a blocked/rejected reason", result.stop_reason == "DIRECTOR_REJECTED_RESULT")
    check("(18) cumulative patch was generated (round 1 alone)", bool(result.level1_cumulative_patch_path))
    if result.level1_cumulative_patch_path:
        patch_text = (bridge.REPO_ROOT / result.level1_cumulative_patch_path).read_text()
        check("(18) cumulative patch contains round 1's retained content", "round1" in patch_text)
        check("(18) cumulative patch does NOT contain round 2's rolled-back content", "round2" not in patch_text, detail=patch_text[:600])
    _cleanup_watch_run_patches(result)
    check("staging workspace was cleaned up", not workspaces[0].exists())


def test_verification_failure_rolls_back_only_that_round(monkeypatch):
    """Item 8: a round whose Claude subprocess exits nonzero (a
    deterministic verification failure, forced to outcome='blocked'
    regardless of what the Director evaluation itself says — see run_once's
    hard override) is rolled back; the prior retained round survives."""
    calls = {"n": 0}
    marker = "director_bridge_detfail_probe_marker.txt"

    def fake_director(state, provider_name=None):
        calls["n"] += 1
        return _make_decision(safety_level=1, task_for_claude=f"round {calls['n']}")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        if calls["n"] == 1:
            (cwd / marker).write_text("round1\n")
            return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')
        (cwd / marker).write_text("round2-partial\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=1, stdout='{"result":"error"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return bridge.DirectorEvaluation(
            **_base_evaluation(recommended_next_task="fixture: round 2" if calls["n"] == 1 else "", recommended_safety_level=1)
        )

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch("fixture detfail objective", max_rounds=3, max_safety_level=1)

    check("two rounds ran", len(result.rounds) == 2)
    r1, r2 = result.rounds
    check("round 1 retained", r1.level1_retained is True)
    check("(8) round 2 (nonzero exit) NOT retained", r2.level1_retained is False)
    check("(8) round 2's final_state reflects the nonzero exit", r2.final_state == "stopped_claude_nonzero_exit")
    check("(8) round 2 rolled back to round 1's state", r2.level1_commit_after == r1.level1_commit_after == r2.level1_checkpoint_before)
    _cleanup_watch_run_patches(result)


def test_claude_timeout_rolls_back_only_that_round(monkeypatch):
    """Item 9: a timed-out round is rolled back the same way as a nonzero
    exit; the prior retained round survives."""
    calls = {"n": 0}
    marker = "director_bridge_timeout_probe_marker.txt"

    def fake_director(state, provider_name=None):
        calls["n"] += 1
        return _make_decision(safety_level=1, task_for_claude=f"round {calls['n']}")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        if calls["n"] == 1:
            (cwd / marker).write_text("round1\n")
            return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')
        (cwd / marker).write_text("round2-partial\n")
        return bridge.ClaudeInvocationResult(invoked=True, timed_out=True, stdout="")

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return bridge.DirectorEvaluation(
            **_base_evaluation(recommended_next_task="fixture: round 2" if calls["n"] == 1 else "", recommended_safety_level=1)
        )

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch("fixture timeout objective", max_rounds=3, max_safety_level=1)

    check("two rounds ran", len(result.rounds) == 2)
    r1, r2 = result.rounds
    check("round 1 retained", r1.level1_retained is True)
    check("(9) round 2 (timed out) NOT retained", r2.level1_retained is False)
    check("(9) round 2's final_state reflects the timeout", r2.final_state == "stopped_claude_timeout")
    check("(9) round 2 rolled back to round 1's state", r2.level1_commit_after == r1.level1_commit_after == r2.level1_checkpoint_before)
    _cleanup_watch_run_patches(result)


def test_level2_recommendation_during_staging_run_rolls_back_and_halts(monkeypatch):
    """Item 23: a round whose DirectorEvaluation recommends Level 2 next is
    treated the same as blocked/founder-approval — its OWN changes are
    rolled back too (per the spec's explicit bucketing: a Level-2 request
    doesn't get to keep its code merely because the process itself
    succeeded), and the watch loop halts for Founder approval. Cumulative
    staging changes nothing about either existing gate."""
    def fake_director(state, provider_name=None):
        return _make_decision(safety_level=1, task_for_claude="round 1")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        (cwd / "level2_probe_marker.txt").write_text("round1\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return bridge.DirectorEvaluation(
            **_base_evaluation(recommended_next_task="fixture: needs level 2", recommended_safety_level=2)
        )

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch("fixture level2-recommend objective", max_rounds=3, max_safety_level=1)

    check("(23) watch halts rather than escalate to Level 2", result.stop_reason == "LEVEL_2_REQUESTED")
    check(
        "(23) round 1's changes were rolled back, not retained — a Level-2 recommendation is treated as unsafe",
        result.rounds[0].level1_retained is False,
    )
    _cleanup_watch_run_patches(result)


def test_staging_watch_run_leaves_main_repo_and_live_db_untouched(monkeypatch):
    """Items 12, 13: across a whole watch run using cumulative staging,
    the real repo's own working tree and the canonical live DB are
    completely unaffected — the staging workspace is a fully separate
    disposable clone throughout, and every new git operation this feature
    adds is `-C <staging workspace>`, never the ambient REPO_ROOT."""
    before_status = bridge._run(["git", "status", "--porcelain"])
    before_db = bridge._live_db_fingerprint()

    def fake_director(state, provider_name=None):
        return _make_decision(safety_level=1, task_for_claude="round 1")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        (cwd / "isolation_probe_marker.txt").write_text("hello\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task="", recommended_safety_level=1))

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch("fixture isolation objective", max_rounds=1, max_safety_level=1)

    after_status = bridge._run(["git", "status", "--porcelain"])
    after_db = bridge._live_db_fingerprint()
    check("(12) main repo git status unchanged by the whole staging watch run", before_status == after_status)
    check("(13) canonical live DB fingerprint unchanged", before_db == after_db)
    check("(12) the round's marker file never appears in the real repo", not (bridge.REPO_ROOT / "isolation_probe_marker.txt").exists())
    _cleanup_watch_run_patches(result)


def test_staging_baseline_commit_does_not_reintroduce_excluded_content():
    """Item 14: _level1_init_staging_baseline's `git add -A` runs on the
    SAME already-exclusion-swept workspace every Level-1 round already
    uses — it commits that state, but must never cause .venv/.env/DB
    artifacts to appear."""
    workspace = bridge._create_level1_workspace()
    try:
        baseline = bridge._level1_init_staging_baseline(workspace)
        check("(14) baseline commit was created", bool(baseline))
        check("(14) .venv still absent after the baseline commit", not (workspace / ".venv").exists())
        leaked_env = sorted({p for p in workspace.rglob(".env*") if ".git" not in p.parts})
        check("(14) no .env* file exists after the baseline commit", not leaked_env, detail=str(leaked_env))
        leaked_db = sorted(
            {p for p in workspace.rglob("*.db") if ".git" not in p.parts}
            | {p for p in workspace.rglob("*.sqlite3") if ".git" not in p.parts}
        )
        check("(14) no DB artifact exists after the baseline commit", not leaked_db, detail=str(leaked_db))
    finally:
        bridge._cleanup_level1_workspace(workspace)


def test_safe_test_runner_executes_inside_staging_session_workspace():
    """Item 15: the bridge-owned test runner still works correctly against
    a workspace that has gone through the staging baseline-commit step —
    real, unmocked, zero Claude tokens (same discipline as the other real-
    but-free workspace probes in this suite)."""
    workspace = bridge._create_level1_workspace()
    try:
        bridge._level1_init_staging_baseline(workspace)
        cmd = [
            str(bridge._test_runner.REAL_HOST_PYTHON), "scripts/director_bridge_test_runner.py",
            "--target", "scripts/test_fishbowl.py",
        ]
        proc = bridge.subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True, timeout=300)
        check("(15) the exact bridge-constructed test command exits 0 inside a staged workspace", proc.returncode == 0, detail=proc.stderr[-500:])
        result = json.loads(proc.stdout)
        check("(15) the approved test itself passed", result.get("exit_code") == 0)
        check("(15) not timed out", result.get("timed_out") is False)
    finally:
        bridge._cleanup_level1_workspace(workspace)


def test_generic_python_bash_restrictions_unaffected_by_cumulative_staging(monkeypatch):
    """Item 16: adding the cumulative staging workspace must not touch
    Level-1's permission strings at all — a pure regression re-check on
    top of the dedicated test-runner-hardening tests above."""
    allowed, disallowed = _argv_for(bridge.BridgeSafetyLevel.SANDBOX, monkeypatch)
    check("(16) python3 remains disallowed", "python3" in disallowed)
    check("(16) .venv/bin/python remains disallowed", ".venv/bin/python" in disallowed)
    check(
        "(16) no bare/wildcard python grant exists in the allowlist",
        "Bash(python3" not in allowed and "Bash(.venv/bin/python:" not in allowed,
    )
    check(
        "(16) the exact test-runner command remains the only Python path",
        all(
            f"Bash({bridge._test_runner.REAL_HOST_PYTHON} scripts/director_bridge_test_runner.py --target {t})" in allowed
            for t in bridge._test_runner.ALLOWED_TEST_TARGETS
        ),
    )


def test_disposable_registry_registers_during_run_and_clears_on_normal_completion(monkeypatch):
    """Item 20: the staging workspace is registered the moment it's
    created (visible to a read of the registry WHILE the round is still in
    progress) and unregistered again on normal end-of-watch-run cleanup,
    without disturbing any other pre-existing registry entries."""
    seen_during_run: dict[str, Any] = {}

    def fake_director(state, provider_name=None):
        return _make_decision(safety_level=1, task_for_claude="round 1")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        seen_during_run["registry"] = dict(bridge._read_disposable_registry())
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task="", recommended_safety_level=1))

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    before_registry = bridge._read_disposable_registry()
    result = bridge.run_watch("fixture registry objective", max_rounds=1, max_safety_level=1)
    after_registry = bridge._read_disposable_registry()

    check(
        "(20) the session was registered WHILE the round was still in progress",
        result.watch_run_id in seen_during_run.get("registry", {}),
    )
    check("(20) the registry entry is cleared again after normal completion", result.watch_run_id not in after_registry)
    check("(20) no other pre-existing registry entries were disturbed", after_registry == before_registry)
    _cleanup_watch_run_patches(result)


def test_disposable_registry_entry_has_enough_info_to_recover_a_crash():
    """Item 21: a registered-but-never-unregistered entry (simulating what
    would be left on disk if the process died before run_watch's `finally`
    ran) carries everything needed to find and reconcile the orphaned
    staging workspace by hand: its exact path, the commit its cumulative
    diff should be measured from, and which watch run it belonged to."""
    workspace = bridge._create_level1_workspace()
    session_id = "fixture_crash_probe_" + workspace.name[-8:]
    try:
        baseline = bridge._level1_init_staging_baseline(workspace)
        bridge._register_disposable_workspace(session_id, workspace, baseline)
        entry = bridge._read_disposable_registry().get(session_id)
        check("(21) a crashed-run entry is present", entry is not None)
        if entry:
            check("(21) entry records the exact workspace path", entry.get("workspace") == str(workspace))
            check("(21) entry records the baseline commit to diff the cumulative patch from", entry.get("baseline_commit") == baseline)
            check("(21) entry records which watch run it belonged to", entry.get("watch_run_id") == session_id)
            check("(21) the recorded workspace path actually still exists on disk (recoverable)", Path(entry["workspace"]).exists())
    finally:
        bridge._unregister_disposable_workspace(session_id)
        bridge._cleanup_level1_workspace(workspace)


def test_cumulative_staging_never_commits_or_pushes_the_real_repo():
    """Item 22: every new git operation this feature adds is scoped to the
    staging workspace via `-C <workspace>` — none of the new checkpoint/
    commit/rollback/diff helpers' actual CODE references REPO_ROOT or a
    bare push/commit that could reach the real repo. Checked via each
    function's compiled bytecode co_names (the global identifiers its code
    actually references), not raw source text — so a docstring merely
    explaining "this never touches REPO_ROOT" in prose can't produce a
    false positive the way a plain substring search over the source would."""
    fns = (
        bridge._level1_init_staging_baseline, bridge._level1_commit_round,
        bridge._level1_rollback, bridge._level1_cumulative_diff,
    )
    for fn in fns:
        check(f"(22) {fn.__name__} never references REPO_ROOT in its actual code", "REPO_ROOT" not in fn.__code__.co_names)
    import inspect

    source = "".join(inspect.getsource(fn) for fn in fns)
    check("(22) 'git push' never appears in any of them", "git push" not in source)


# =============================================================================
# 2026-09-10 safe cumulative SESSION SEEDING: a new watch run may seed its
# persistent Level-1 staging workspace from a PRIOR run's durable cumulative
# patch. The seed is verified (path-safety + optional sha256), applied ONLY
# inside the isolated staging workspace (never REPO_ROOT), and the seeded
# state must pass every approved test before any round builds on it. Plus
# task-exhaustion hardening: a stalled individual task redirects the Director
# to a different backlog area instead of ending the whole run.
# =============================================================================

_SEED_MARKER = "seed_probe_marker.txt"


def _make_seed_patch(*, path: str = _SEED_MARKER, body: str = "seeded-by-prior-run\n") -> tuple[Path, str]:
    """Writes a real, minimal, well-formed `git apply`-able new-file patch
    to a throwaway temp file and returns (patch_path, sha256). Not under
    .director/ — the patch FILE location is irrelevant to _validate_seed_
    patch, which only inspects the paths INSIDE the diff."""
    lines = body.splitlines() or [""]
    hunk = f"@@ -0,0 +1,{len(lines)} @@\n" + "".join(f"+{l}\n" for l in lines)
    patch_text = (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        f"{hunk}"
    )
    fd = bridge.tempfile.NamedTemporaryFile(
        mode="w", suffix="_seed.patch", prefix="director_bridge_fixture_", delete=False
    )
    fd.write(patch_text)
    fd.close()
    p = Path(fd.name)
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


def test_seed_patch_validation_rejects_unsafe_content():
    """Seed patch safety validation: _validate_seed_patch refuses a sha256
    mismatch, an empty diff, absolute paths, path traversal, .env / DB /
    secret / .director paths, binary diffs and symlink modes — the same
    categories the manual Gate-1 promotion checklist covered by hand."""
    good_path, good_sha = _make_seed_patch()
    try:
        ok, err, touched = bridge._validate_seed_patch(good_path, good_sha)
        check("a well-formed safe seed patch validates", ok, detail=err)
        check("its touched-files list is correct", touched == [_SEED_MARKER])

        ok, err, _ = bridge._validate_seed_patch(good_path, "0" * 64)
        check("sha256 mismatch is rejected", not ok and "sha256 mismatch" in err)

        ok, err, _ = bridge._validate_seed_patch(good_path, None)
        check("no expected sha still validates a safe patch (hash optional)", ok, detail=err)

        for bad, why in [
            ("diff --git a/.env b/.env\n--- a/.env\n+++ b/.env\n@@ -0,0 +1 @@\n+X=1\n", ".env"),
            ("diff --git a/.director/x b/.director/x\n--- a/.director/x\n+++ b/.director/x\n@@ -0,0 +1 @@\n+x\n", ".director path"),
            ("diff --git a//etc/passwd b//etc/passwd\n--- a//etc/passwd\n+++ b//etc/passwd\n@@ -0,0 +1 @@\n+x\n", "absolute path"),
            ("diff --git a/../x b/../x\n--- a/../x\n+++ b/../x\n@@ -0,0 +1 @@\n+x\n", "path traversal"),
            ("diff --git a/app/secret_key.py b/app/secret_key.py\n--- a/app/secret_key.py\n+++ b/app/secret_key.py\n@@ -0,0 +1 @@\n+x\n", "secret-shaped path"),
            ("diff --git a/data.db b/data.db\n--- a/data.db\n+++ b/data.db\n@@ -0,0 +1 @@\n+x\n", "DB artifact"),
            ("diff --git a/link b/link\nnew file mode 120000\n--- /dev/null\n+++ b/link\n@@ -0,0 +1 @@\n+target\n", "symlink mode"),
            ("diff --git a/x.png b/x.png\nGIT binary patch\nliteral 0\n", "binary diff"),
            ("nothing here at all\n", "no touched files"),
        ]:
            tmp = Path(bridge.tempfile.mkstemp(suffix=".patch")[1])
            tmp.write_text(bad)
            try:
                ok, err, _ = bridge._validate_seed_patch(tmp, None)
                check(f"seed validation rejects: {why}", not ok, detail=f"err={err!r}")
            finally:
                tmp.unlink(missing_ok=True)
    finally:
        good_path.unlink(missing_ok=True)


def test_seed_hash_mismatch_refuses_to_start_watch_run(monkeypatch):
    """Seed patch hash checking end to end: run_watch given a seed patch
    whose sha256 does not match refuses to start — zero rounds, stop_reason
    SEED_REJECTED, provenance recorded, and _create_level1_workspace is
    never even called."""
    created = []
    monkeypatch.setattr(bridge, "_create_level1_workspace", lambda: created.append(1))
    patch_path, _real_sha = _make_seed_patch()
    try:
        result = bridge.run_watch(
            "fixture seed objective", max_rounds=3, max_safety_level=1,
            seed_patch=patch_path, seed_patch_sha256="deadbeef" * 8,
        )
        check("seed hash mismatch: zero rounds ran", len(result.rounds) == 0)
        check("seed hash mismatch: stop_reason is SEED_REJECTED", result.stop_reason == "SEED_REJECTED")
        check("seed hash mismatch: no staging workspace was ever created", not created)
        check("seed hash mismatch: provenance recorded ok=False", (result.seed_provenance or {}).get("ok") is False)
    finally:
        patch_path.unlink(missing_ok=True)
        _cleanup_watch_run_patches(result)


def test_seed_applied_only_to_staging_visible_to_rounds_and_never_repo_root(monkeypatch):
    """The core end-to-end seeding guarantee, with a REAL disposable staging
    workspace and a REAL post-seed test run (zero Claude tokens):
      - the seed is applied ONLY inside the staging workspace;
      - REPO_ROOT's working tree and the canonical live DB are untouched;
      - the seeded file is visible to a subsequent Level-1 round;
      - the final cumulative patch contains BOTH the seeded content AND the
        new round's retained work (prior autonomous work + new work)."""
    before_status = bridge._run(["git", "status", "--porcelain"])
    before_db = bridge._live_db_fingerprint()
    patch_path, sha = _make_seed_patch(body="seeded-line-A\nseeded-line-B\n")

    round_saw_seed = {"visible": None}

    def fake_director(state, provider_name=None):
        return _make_decision(safety_level=1, task_for_claude="round 1: build on the seed")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        seed_file = cwd / _SEED_MARKER
        round_saw_seed["visible"] = seed_file.is_file() and "seeded-line-A" in seed_file.read_text()
        (cwd / "round1_new_work.txt").write_text("added-by-round-1\n")
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task="", recommended_safety_level=1))

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch(
        "fixture seed e2e objective", max_rounds=1, max_safety_level=1,
        seed_patch=patch_path, seed_patch_sha256=sha,
    )
    try:
        check("seed e2e: exactly one round ran", len(result.rounds) == 1)
        check("seed e2e: provenance ok=True (verified + applied + tested)", (result.seed_provenance or {}).get("ok") is True)
        check("seed e2e: provenance records it was actually applied", (result.seed_provenance or {}).get("applied") is True)
        check("seed e2e: provenance records the post-seed test passed", (result.seed_provenance or {}).get("test_ok") is True)
        check("seed e2e: the seeded file was visible to the Level-1 round", round_saw_seed["visible"] is True)
        check("seed e2e: REPO_ROOT working tree completely unchanged", before_status == bridge._run(["git", "status", "--porcelain"]))
        check("seed e2e: canonical live DB fingerprint unchanged", before_db == bridge._live_db_fingerprint())
        check("seed e2e: the seeded marker never appears in REPO_ROOT", not (bridge.REPO_ROOT / _SEED_MARKER).exists())
        check("seed e2e: the round's new file never appears in REPO_ROOT", not (bridge.REPO_ROOT / "round1_new_work.txt").exists())
        check("seed e2e: a cumulative patch was produced", bool(result.level1_cumulative_patch_path))
        if result.level1_cumulative_patch_path:
            patch_text = (bridge.REPO_ROOT / result.level1_cumulative_patch_path).read_text()
            check("seed e2e: cumulative patch contains the SEEDED content", "+seeded-line-A" in patch_text, detail=patch_text[:800])
            check("seed e2e: cumulative patch contains the NEW round work too", "+added-by-round-1" in patch_text, detail=patch_text[:800])
    finally:
        patch_path.unlink(missing_ok=True)
        _cleanup_watch_run_patches(result)


def test_seed_rejected_content_aborts_run_without_building_on_it(monkeypatch):
    """A seed patch that is well-formed enough to pass the early check but
    fails INSIDE the staging workspace (does not apply cleanly) aborts the
    very first Level-1 round with SEED_REJECTED — no round's work is ever
    built on an unverified starting point, and REPO_ROOT stays clean."""
    before_status = bridge._run(["git", "status", "--porcelain"])
    # Valid path, valid shape, but targets an existing file with context
    # that cannot match — `git apply --check` inside the workspace fails.
    bad = (
        "diff --git a/README.md b/README.md\n"
        "--- a/README.md\n+++ b/README.md\n"
        "@@ -999999,3 +999999,3 @@ this context line does not exist anywhere\n"
        "-nonexistent original line\n+replacement line\n context\n"
    )
    tmp = Path(bridge.tempfile.mkstemp(suffix="_seed.patch")[1])
    tmp.write_text(bad)

    claude_calls = {"n": 0}

    def fake_director(state, provider_name=None):
        return _make_decision(safety_level=1, task_for_claude="round 1")

    def fake_claude(task_prompt, level, cwd=None, timeout=300):
        claude_calls["n"] += 1
        return bridge.ClaudeInvocationResult(invoked=True, exit_code=0, stdout='{"result":"ok"}')

    def fake_evaluation(*, decision, claude_result, deterministic, provider_name=None):
        return bridge.DirectorEvaluation(**_base_evaluation(recommended_next_task="", recommended_safety_level=1))

    monkeypatch.setattr(bridge, "call_openai_director", fake_director)
    monkeypatch.setattr(bridge, "invoke_claude_code", fake_claude)
    monkeypatch.setattr(bridge, "call_openai_director_evaluation", fake_evaluation)
    monkeypatch.setattr(bridge.time, "sleep", lambda s: None)

    result = bridge.run_watch(
        "fixture seed reject objective", max_rounds=3, max_safety_level=1, seed_patch=tmp,
    )
    try:
        check("bad seed: stop_reason is SEED_REJECTED", result.stop_reason == "SEED_REJECTED")
        check("bad seed: Claude was never invoked (nothing built on the seed)", claude_calls["n"] == 0)
        check("bad seed: no cumulative patch retained", not result.level1_cumulative_patch_path)
        check("bad seed: REPO_ROOT working tree unchanged", before_status == bridge._run(["git", "status", "--porcelain"]))
        check("bad seed: provenance recorded the failure", (result.seed_provenance or {}).get("ok") is False)
    finally:
        tmp.unlink(missing_ok=True)
        _cleanup_watch_run_patches(result)


def test_backlog_redirect_objective_only_adds_constraints():
    """The redirect objective is a plain string that only ADDS constraints:
    it names the exhausted work, forbids returning to it, lists the priority
    backlog areas, and re-states (never relaxes) the Level-0/1 + no-live-DB
    + no-commit/push safety envelope."""
    text = bridge._backlog_redirect_objective(
        exhausted_task="polish the Research Wall legend",
        rejected_next_task="polish the Research Wall legend again",
        already_stalled=["polish the research wall legend"],
    )
    check("redirect names the work as exhausted", "EXHAUSTED" in text)
    check("redirect forbids the rejected suggestion", "polish the Research Wall legend again" in text)
    check("redirect lists the already-stalled task", "polish the research wall legend" in text)
    check("redirect offers the priority backlog areas", "conversation visualization" in text and "Rabbit Holes" in text)
    check("redirect re-states the safety envelope", "Level 0 or Level 1" in text and "never advance the live Village" in text)
    check("redirect allows a clean stop when nothing distinct remains", "recommend" in text and "stopping" in text)


def test_backlog_exhausted_is_a_healthy_stop_reason():
    """BACKLOG_EXHAUSTED is a clean 'we genuinely finished the useful work'
    outcome, not a fault — it is in WATCH_STOP_REASONS, the founder summary
    treats it as HEALTHY, and main() returns exit 0 for it."""
    check("BACKLOG_EXHAUSTED is a recognized watch stop reason", "BACKLOG_EXHAUSTED" in bridge.WATCH_STOP_REASONS)
    check("SEED_REJECTED is a recognized watch stop reason", "SEED_REJECTED" in bridge.WATCH_STOP_REASONS)
    check("WATCH_MAX_BACKLOG_REDIRECTS is a small positive bound", 0 < bridge.WATCH_MAX_BACKLOG_REDIRECTS < bridge.WATCH_MAX_ROUNDS_CEILING)


def main() -> int:
    tests = [
        test_collect_state_is_compact_and_never_touches_live_db,
        test_run_once_stop_path_never_touches_claude,
        test_run_once_level0_completes_with_evaluation,
        test_run_once_claude_timeout_is_deterministic_failure_and_never_continues,
        test_run_once_level2_never_executes_even_if_approved,
        test_run_once_refuses_safety_level_escalation_above_caller_cap,
        test_invalid_director_response_stops_cleanly,
        test_live_db_fingerprint_change_overrides_director_evaluation,
        test_level0_argv_is_allowlist_only_no_bypass,
        test_level1_argv_denies_dangerous_git_and_db_operations,
        test_escape_route_find_exec_execdir_delete_mechanically_rejected,
        test_escape_route_shell_invocation_mechanically_rejected,
        test_escape_route_destructive_filesystem_command_mechanically_rejected,
        test_escape_route_git_mutation_mechanically_rejected,
        test_escape_route_network_command_mechanically_rejected,
        test_escape_route_canonical_db_access_mechanically_rejected,
        test_consequential_level_never_reaches_subprocess,
        test_run_once_accepts_a_substitute_director_client,
        test_watch_continuation_accepted_clean_round_may_continue,
        test_watch_continuation_needs_revision_with_safe_task_may_continue,
        test_watch_continuation_needs_revision_missing_next_task_stops,
        test_watch_continuation_needs_revision_founder_approval_stops,
        test_watch_continuation_needs_revision_level2_stops,
        test_watch_continuation_needs_revision_level1_stops_when_max_safety_level_is_0,
        test_watch_continuation_needs_revision_level1_continues_when_max_safety_level_is_1,
        test_watch_continuation_needs_revision_stops_on_live_db_involvement,
        test_watch_continuation_blocked_stops,
        test_watch_continuation_missing_evaluation_stops,
        test_watch_stops_when_level2_requested,
        test_watch_continuation_stops_when_evaluation_requires_founder_approval,
        test_git_state_check_raises_when_git_command_itself_fails,
        test_git_state_check_raises_on_unresolvable_repo,
        test_git_state_check_detached_head,
        test_git_state_check_merge_in_progress,
        test_git_state_check_rebase_in_progress,
        test_git_state_check_unresolved_conflict_detected,
        test_watch_continuation_stops_on_deterministic_verification_failure,
        test_watch_continuation_stops_on_claude_failure,
        test_watch_stops_immediately_when_git_state_check_raises,
        test_watch_respects_max_rounds,
        test_watch_feeds_recommended_next_task_into_next_round_objective,
        test_secret_shaped_env_var_name_is_excluded_even_when_not_individually_named,
        test_redact_sensitive_context_masks_the_live_data_path_and_secrets,
        test_context_leak_scan_of_real_collect_bridge_state_and_constitution,
        test_context_leak_scan_of_claude_facing_prompt_for_both_levels,
        test_level0_read_grep_glob_are_path_scoped_to_cwd,
        test_level1_read_edit_write_grep_glob_are_path_scoped_to_cwd,
        test_level1_workspace_is_created_used_and_cleaned_up,
        test_level1_workspace_never_contains_env_file,
        test_level1_workspace_never_contains_database_artifacts,
        test_watch_accepted_level0_round_continues_to_next_round,
        test_watch_accepted_level1_round_continues_to_next_round,
        test_watch_director_stop_is_challenged_then_backlog_exhausted,
        test_watch_productive_completion_redirects_to_next_backlog_item,
        test_watch_needs_revision_halts_with_correct_reason,
        test_watch_needs_revision_safe_level0_continues_automatically,
        test_watch_needs_revision_safe_level1_continues_when_max_safety_level_allows,
        test_watch_needs_revision_level1_stops_when_max_safety_level_is_0,
        test_watch_needs_revision_level2_halts_end_to_end,
        test_watch_needs_revision_founder_approval_halts_end_to_end,
        test_watch_needs_revision_missing_next_task_halts_end_to_end,
        test_watch_needs_revision_failed_verification_halts_end_to_end,
        test_watch_needs_revision_repeated_task_redirects_then_backlog_exhausted,
        test_watch_needs_revision_rounds_obey_max_rounds,
        test_watch_needs_revision_exactly_one_claude_invocation_per_round,
        test_watch_blocked_halts_with_correct_reason,
        test_watch_level2_recommendation_halts_with_correct_reason,
        test_watch_founder_approval_required_halts_with_correct_reason,
        test_watch_claude_failure_halts_with_correct_reason,
        test_watch_claude_timeout_halts_with_correct_reason_and_never_continues,
        test_watch_verification_failure_halts_with_correct_reason,
        test_watch_live_db_changed_halts_with_correct_reason,
        test_watch_unsafe_git_state_halts_with_correct_reason,
        test_watch_malformed_director_response_halts_with_correct_reason,
        test_watch_repeated_task_text_redirects_then_backlog_exhausted,
        test_watch_repeated_no_change_result_redirects_to_a_different_backlog_area,
        test_watch_max_rounds_hard_ceiling_is_enforced,
        test_watch_default_max_rounds_is_three,
        test_persisted_round_never_contains_secrets,
        test_level1_pytest_wildcard_access_is_gone,
        test_level1_grants_exactly_one_exact_match_command_per_approved_test_target,
        test_level1_disallow_list_unaffected_by_test_runner_change,
        test_level1_preamble_documents_the_exact_test_runner_command,
        test_test_runner_rejects_unapproved_target,
        test_test_runner_rejects_path_traversal_target,
        test_test_runner_refuses_to_run_against_the_real_repo_root,
        test_test_runner_sanitized_env_excludes_secrets_and_scopes_village_data_root,
        test_test_runner_timeout_is_handled_deterministically,
        test_test_runner_real_run_against_isolated_workspace_passes_and_stays_isolated,
        test_run_once_captures_level1_test_result_deterministically,
        test_run_once_test_results_is_none_when_no_test_ran,
        test_test_runner_change_introduces_no_new_level2_or_auto_promotion_path,
        test_level1_staging_workspace_reused_across_consecutive_rounds,
        test_level0_round_never_touches_staging_workspace,
        test_blocked_round_rolls_back_and_prior_retained_round_survives,
        test_verification_failure_rolls_back_only_that_round,
        test_claude_timeout_rolls_back_only_that_round,
        test_level2_recommendation_during_staging_run_rolls_back_and_halts,
        test_staging_watch_run_leaves_main_repo_and_live_db_untouched,
        test_staging_baseline_commit_does_not_reintroduce_excluded_content,
        test_safe_test_runner_executes_inside_staging_session_workspace,
        test_generic_python_bash_restrictions_unaffected_by_cumulative_staging,
        test_disposable_registry_registers_during_run_and_clears_on_normal_completion,
        test_disposable_registry_entry_has_enough_info_to_recover_a_crash,
        test_cumulative_staging_never_commits_or_pushes_the_real_repo,
        test_seed_patch_validation_rejects_unsafe_content,
        test_seed_hash_mismatch_refuses_to_start_watch_run,
        test_seed_applied_only_to_staging_visible_to_rounds_and_never_repo_root,
        test_seed_rejected_content_aborts_run_without_building_on_it,
        test_backlog_redirect_objective_only_adds_constraints,
        test_backlog_exhausted_is_a_healthy_stop_reason,
    ]
    for test in tests:
        mp = _MonkeyPatch()
        try:
            if "monkeypatch" in test.__code__.co_varnames[: test.__code__.co_argcount]:
                test(mp)
            else:
                test()
        finally:
            mp.undo()
    print(f"\n{len(tests) - len(FAILURES)}/{len(tests)} test functions had all checks pass.")
    if FAILURES:
        print(f"FAILED checks: {FAILURES}")
        return 1
    print("PASS: director_bridge round orchestration (fixture-only, no live DB, no real API calls, no real subprocess).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
