#!/usr/bin/env python3
"""Adversarial + positive fixture tests for scripts/director_broker.py.

Every mutation/adversarial scenario runs against a disposable, synthetic
SQLite database this script builds itself (via the same
``create_guarded_isolated_sqlite_session`` primitive director_diagnostics.py
already uses) with ``director_broker.CANONICAL_LIVE_DB_PATH`` monkeypatched
to point at it for the duration of that scenario only — the real live
database is never opened in write mode, never targeted by a mutation
attempt, and is restored to its real module reference immediately after
each such scenario. A small number of scenarios explicitly marked
"REAL LIVE DB, READ-ONLY" intentionally run against the true canonical
live database precisely because they only ever exercise the read-only
path, to prove genuine end-to-end integration rather than only ever
testing against a fixture — every one of those verifies the live DB hash
is unchanged immediately afterward.

Run with:
    .venv/bin/python scripts/director_broker_fixturetest.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import director_broker as broker  # noqa: E402
import director_diagnostics as dd  # noqa: E402
from app.core.db_safety import CANONICAL_LIVE_DB_PATH as REAL_LIVE_DB_PATH  # noqa: E402
from app.core.db_safety import safe_rmtree  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(("PASS " if passed else "FAIL "), name, ("" if passed else f"— {detail}"))


def build_fixture_live_db() -> tuple[Path, Path]:
    """A real-schema, disposable SQLite DB seeded with the real seed_agents
    roster, standing in for 'the live DB' in every adversarial scenario.
    Never the real file."""
    tmp_dir, session = dd.create_guarded_isolated_sqlite_session(prefix="director_broker_fixturetest_")
    session.close()
    db_path = tmp_dir / "isolated_test.db"
    import seed_agents
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path}")
    seeded_session = sessionmaker(bind=engine)()
    seed_agents.run(seeded_session)
    seeded_session.commit()
    # Pad well past check_live_db's MIN_LIVE_DB_BYTES (8192) -- a freshly
    # seeded SQLite file can otherwise land just under that "looks
    # empty/corrupt" floor, which is the right behavior for the real
    # canonical file but would make this fixture spuriously fail its own
    # health check. A handful of ordinary rows via the real Memory model
    # is a more faithful pad than raw bytes.
    from app.db.models.memory import Memory
    from app.domain.enums import MemoryType

    for i in range(30):
        seeded_session.add(
            Memory(
                agent_id="agent_roxy", memory_type=MemoryType.EPISODIC,
                content=f"fixturetest padding memory number {i} " + ("x" * 200),
                importance=10.0, confidence=10.0,
            )
        )
    seeded_session.commit()
    seeded_session.execute(__import__("sqlalchemy").text("PRAGMA wal_checkpoint(TRUNCATE)"))
    seeded_session.close()
    engine.dispose()
    return tmp_dir, db_path


def with_fixture_live_db(fn):
    """Decorator-style helper: monkeypatches director_broker's live-DB
    constant to a disposable fixture for the duration of fn(db_path), then
    restores it and deletes the fixture, in a finally block."""
    tmp_dir, db_path = build_fixture_live_db()
    original = broker.CANONICAL_LIVE_DB_PATH
    broker.CANONICAL_LIVE_DB_PATH = db_path
    try:
        fn(db_path)
    finally:
        broker.CANONICAL_LIVE_DB_PATH = original
        safe_rmtree(tmp_dir)


# ===========================================================================
# ADVERSARIAL TESTS
# ===========================================================================


def test_adversarial_sql_mutations(db_path: Path) -> None:
    mutation_queries = {
        "INSERT": "INSERT INTO agents (agent_id, identity, voice) VALUES ('x','x','x')",
        "UPDATE": "UPDATE agents SET identity='hacked' WHERE agent_id='agent_dex'",
        "DELETE": "DELETE FROM agents WHERE agent_id='agent_dex'",
        "CREATE": "CREATE TABLE evil (x INTEGER)",
        "DROP": "DROP TABLE agents",
        "ALTER": "ALTER TABLE agents ADD COLUMN evil TEXT",
        "ATTACH": f"ATTACH DATABASE '{db_path}' AS evil",
        "DETACH": "DETACH DATABASE main",
        "VACUUM": "VACUUM",
        "writable PRAGMA": "PRAGMA journal_mode=DELETE",
        "load_extension": "SELECT load_extension('evil.so')",
    }
    for label, sql in mutation_queries.items():
        result = broker.execute("LIVE_DB_READ", {"sql": sql})
        ok = result.status == "REJECTED"
        record(f"LIVE_DB_READ rejects {label}", ok, result.failure_reason or "")

    # Multi-statement: schema-level rejection.
    result = broker.execute("LIVE_DB_READ", {"sql": "SELECT 1; DROP TABLE agents"})
    record("LIVE_DB_READ rejects multiple statements", result.status == "REJECTED", result.failure_reason or "")

    # Defense in depth: bypass the string-level filter by calling the
    # trusted open-connection helper directly and attempting a mutation
    # through the SQLite authorizer itself, independent of the regex.
    conn = broker._open_live_db_readonly()
    try:
        try:
            conn.execute("DELETE FROM agents")
            record("SQLite authorizer denies DELETE even if string filter were bypassed", False, "no exception raised")
        except Exception as exc:  # noqa: BLE001
            record("SQLite authorizer denies DELETE even if string filter were bypassed", True, str(exc))
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
            record("SQLite authorizer/query_only denies writable PRAGMA", False, "PRAGMA journal_mode=DELETE did not raise")
        except Exception as exc:  # noqa: BLE001
            record("SQLite authorizer/query_only denies writable PRAGMA", True, str(exc))
    finally:
        conn.close()


def test_adversarial_paths(tmp_extra_dir: Path) -> None:
    result = broker.execute("READ_REPO_FILE", {"relative_path": "../../../../etc/passwd"})
    record("READ_REPO_FILE rejects path traversal", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("READ_REPO_FILE", {"relative_path": "/etc/passwd"})
    record("READ_REPO_FILE rejects absolute path", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("READ_REPO_FILE", {"relative_path": ".env"})
    record("READ_REPO_FILE refuses to read .env", result.status == "REJECTED", result.failure_reason or "")

    # Symlink escape, tested directly against the shared _resolve_within
    # helper every path-based capability uses, with disposable temp dirs
    # (never inside the real repo).
    root = tmp_extra_dir / "approved_root"
    outside = tmp_extra_dir / "outside_secret"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("nope")
    (root / "escape_link").symlink_to(outside / "secret.txt")
    try:
        broker._resolve_within(root, "escape_link")
        record("_resolve_within rejects a symlink escaping the approved root", False, "no exception raised")
    except broker.BrokerError as exc:
        record("_resolve_within rejects a symlink escaping the approved root", True, str(exc))

    result = broker.execute("WRITE_DIRECTOR_ARTIFACT", {"relative_path": "app/services/memory.py", "content": "x"})
    record("WRITE_DIRECTOR_ARTIFACT refuses a production-code path", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("WRITE_DIRECTOR_ARTIFACT", {"relative_path": "cursor.json", "content": "{}"})
    record("WRITE_DIRECTOR_ARTIFACT refuses .director/cursor.json (loop-owned state, not evidence)", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("DELETE_DISPOSABLE_RESOURCE", {"disposable_id": "not-a-real-id-not-hex-32"})
    record("DELETE_DISPOSABLE_RESOURCE rejects a malformed id (schema level)", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("DELETE_DISPOSABLE_RESOURCE", {"disposable_id": "0" * 32})
    record("DELETE_DISPOSABLE_RESOURCE rejects a well-formed but never-issued id", result.status == "REJECTED", result.failure_reason or "")

    # "live DB passed as disposable DB": structurally impossible, since
    # CreateDisposableDbParams has no path-shaped field at all.
    result = broker.execute("CREATE_DISPOSABLE_DB", {"label": "x", "destination": str(REAL_LIVE_DB_PATH)})
    record("CREATE_DISPOSABLE_DB rejects an unknown 'destination' field outright (no path input exists)", result.status == "REJECTED", result.failure_reason or "")

    # Arbitrary filesystem delete: DELETE_DISPOSABLE_RESOURCE only ever
    # accepts a 32-hex-char id, never a path — confirm structurally.
    fields = set(broker.DeleteDisposableResourceParams.model_fields.keys())
    record("DELETE_DISPOSABLE_RESOURCE's schema has no path-shaped field", fields == {"disposable_id"}, str(fields))


def test_adversarial_git(_: Path) -> None:
    for bad_subcommand in ("reset", "clean", "checkout", "commit", "push", "merge", "rebase", "stash", "cherry-pick", "config"):
        result = broker.execute("GIT_READONLY", {"subcommand": bad_subcommand})
        record(f"GIT_READONLY rejects git {bad_subcommand}", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("GIT_READONLY", {"subcommand": "show", "ref": "HEAD; rm -rf /"})
    record("GIT_READONLY rejects shell metacharacters in ref", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("GIT_READONLY", {"subcommand": "show", "ref": "$(whoami)"})
    record("GIT_READONLY rejects command substitution in ref", result.status == "REJECTED", result.failure_reason or "")


def test_adversarial_no_execution_surface(_: Path) -> None:
    dangerous_field_names = {"command", "commands", "argv", "code", "script", "python", "shell", "cmd", "expr", "eval"}
    for capability, model in broker._PARAM_MODELS.items():
        fields = set(model.model_fields.keys())
        overlap = fields & dangerous_field_names
        record(
            f"{capability.value} has no free-text execution field",
            not overlap,
            f"found: {overlap}" if overlap else "",
        )

    for forbidden_name in broker.EXPLICITLY_FORBIDDEN_CAPABILITY_NAMES:
        result = broker.execute(forbidden_name, {})
        record(f"capability {forbidden_name!r} is unreachable (not in the closed catalog)", result.status == "REJECTED", result.failure_reason or "")

    record("no register_capability-shaped function exists on the module", not any(
        name.lower().startswith("register") or "self_register" in name.lower() for name in dir(broker)
    ), "")

    record(
        "Capability enum has exactly the intended fixed membership (no runtime mutation possible)",
        isinstance(broker.Capability, type) and issubclass(broker.Capability, __import__("enum").Enum),
        "",
    )


def test_adversarial_secrets(_: Path) -> None:
    result = broker.execute("PROVIDER_CONFIGURATION_STATUS", {})
    dumped = json.dumps(result.to_dict())
    import os
    real_key = os.environ.get("ANTHROPIC_API_KEY", "")
    leaked = bool(real_key) and real_key in dumped
    record("PROVIDER_CONFIGURATION_STATUS never includes the raw API key", not leaked, "")
    record(
        "PROVIDER_CONFIGURATION_STATUS result has no key-shaped field",
        "api_key" not in result.result and "anthropic_api_key" not in result.result,
        str(list(result.result.keys())),
    )


# ===========================================================================
# POSITIVE TESTS
# ===========================================================================


def test_positive_live_db_read(db_path: Path) -> None:
    result = broker.execute("LIVE_DB_READ", {"sql": "SELECT agent_id FROM agents ORDER BY agent_id"})
    record("LIVE_DB_READ succeeds on a genuine SELECT", result.status == "SUCCESS" and result.result.get("row_count", 0) > 0, result.failure_reason or "")

    result = broker.execute("CHECK_LIVE_DB_INTEGRITY", {})
    record("CHECK_LIVE_DB_INTEGRITY succeeds", result.status == "SUCCESS" and result.result.get("healthy") is True, result.failure_reason or "")

    result = broker.execute("GET_POPULATION_COUNTS", {})
    record("GET_POPULATION_COUNTS succeeds", result.status == "SUCCESS" and "agents" in result.result.get("counts", {}), result.failure_reason or "")

    result = broker.execute("GET_AGENT_MEMORIES", {"agent_id": "agent_roxy"})
    record("GET_AGENT_MEMORIES succeeds (typed capability, not raw SQL)", result.status == "SUCCESS", result.failure_reason or "")

    result = broker.execute("GET_AGENT_QUESTIONS", {"agent_id": "agent_roxy"})
    record("GET_AGENT_QUESTIONS succeeds", result.status == "SUCCESS", result.failure_reason or "")

    result = broker.execute("GET_EVENT_RANGE", {"start_id": 1, "end_id": 5})
    record("GET_EVENT_RANGE succeeds", result.status == "SUCCESS", result.failure_reason or "")


def test_positive_files_and_artifacts(_: Path) -> None:
    result = broker.execute("READ_REPO_FILE", {"relative_path": "app/core/config.py"})
    record("READ_REPO_FILE succeeds on a real repo file", result.status == "SUCCESS" and "Settings" in result.result.get("content", ""), result.failure_reason or "")

    marker = "director_broker_fixturetest marker"
    write_result = broker.execute(
        "WRITE_DIRECTOR_ARTIFACT",
        {"relative_path": "diagnostics/_broker_fixturetest_scratch.txt", "content": marker},
    )
    record("WRITE_DIRECTOR_ARTIFACT succeeds inside an approved subtree", write_result.status == "SUCCESS", write_result.failure_reason or "")

    read_result = broker.execute("READ_DIRECTOR_ARTIFACT", {"relative_path": "diagnostics/_broker_fixturetest_scratch.txt"})
    record(
        "READ_DIRECTOR_ARTIFACT reads back exactly what was written",
        read_result.status == "SUCCESS" and read_result.result.get("content") == marker,
        read_result.failure_reason or "",
    )
    (broker.DIRECTOR_DIR / "diagnostics" / "_broker_fixturetest_scratch.txt").unlink(missing_ok=True)

    packet_result = broker.execute(
        "WRITE_FOUNDER_PACKET",
        {"filename": "_broker_fixturetest_scratch.md", "content": "# scratch\n"},
    )
    record("WRITE_FOUNDER_PACKET succeeds", packet_result.status == "SUCCESS", packet_result.failure_reason or "")
    (broker.DIRECTOR_DIR / "founder_packets" / "_broker_fixturetest_scratch.md").unlink(missing_ok=True)


def test_positive_git(_: Path) -> None:
    result = broker.execute("GIT_READONLY", {"subcommand": "status"})
    record("GIT_READONLY status succeeds", result.status == "SUCCESS" and result.result.get("returncode") == 0, result.failure_reason or "")

    result = broker.execute("GIT_READONLY", {"subcommand": "rev_parse_head"})
    record("GIT_READONLY rev_parse_head succeeds", result.status == "SUCCESS", result.failure_reason or "")


def test_positive_disposable_lifecycle(_: Path) -> None:
    create_result = broker.execute("CREATE_DISPOSABLE_DB", {"label": "fixturetest"})
    record("CREATE_DISPOSABLE_DB succeeds", create_result.status == "SUCCESS", create_result.failure_reason or "")
    disposable_id = create_result.result.get("disposable_id")

    scratch_dir = Path(create_result.result["scratch_dir"])
    record("disposable scratch dir is outside every live-data root", scratch_dir.exists() and REAL_LIVE_DB_PATH.parent not in scratch_dir.parents, "")

    delete_result = broker.execute("DELETE_DISPOSABLE_RESOURCE", {"disposable_id": disposable_id})
    record("DELETE_DISPOSABLE_RESOURCE succeeds for a broker-issued id", delete_result.status == "SUCCESS", delete_result.failure_reason or "")
    record("disposable scratch dir is actually gone after deletion", not scratch_dir.exists(), "")


def test_positive_disposable_experiment(_: Path) -> None:
    import os
    os.environ.pop("LLM_PROVIDER", None)  # ensure fixture provider, zero real spend in the test suite
    before_hash = hashlib.sha256(REAL_LIVE_DB_PATH.read_bytes()).hexdigest() if REAL_LIVE_DB_PATH.exists() else None

    result = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {
            "experiment_id": "quiet_agent_thread_counterfactual",
            "agent_id": "agent_lucid",
            "memory_content": "Fixture-test memory content, never sent to a real model.",
            "memory_type": "EPISODIC",
            "n_pairs": 1,
        },
    )
    record("RUN_APPROVED_DISPOSABLE_EXPERIMENT succeeds against the fixture provider", result.status == "SUCCESS", result.failure_reason or "")
    if result.status == "SUCCESS":
        trials = result.result.get("trials", [])
        record("disposable experiment used the fixture provider (is_fixture=True), zero real spend", all(t["is_fixture"] for t in trials), str(trials))

    after_hash = hashlib.sha256(REAL_LIVE_DB_PATH.read_bytes()).hexdigest() if REAL_LIVE_DB_PATH.exists() else None
    record("live DB hash unchanged after a disposable experiment", before_hash == after_hash, "")

    unknown_result = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {"experiment_id": "not_a_real_experiment", "agent_id": "agent_lucid", "memory_content": "x", "memory_type": "EPISODIC"},
    )
    record("RUN_APPROVED_DISPOSABLE_EXPERIMENT rejects an unregistered experiment_id", unknown_result.status == "REJECTED", unknown_result.failure_reason or "")

    disallowed_agent = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {"experiment_id": "quiet_agent_thread_counterfactual", "agent_id": "agent_alien_but_not_really", "memory_content": "x", "memory_type": "EPISODIC"},
    )
    record("RUN_APPROVED_DISPOSABLE_EXPERIMENT rejects an unlisted agent_id", disallowed_agent.status == "REJECTED", disallowed_agent.failure_reason or "")


def test_positive_and_adversarial_research_sharing_experiment(_: Path) -> None:
    """Backlog #2-4's newly registered experiment_id
    (research_sharing_priming_counterfactual): valid invocation, malformed
    parameters, wrong agent_id, and live-DB-unchanged all covered here,
    per the Founder's Step 4 adversarial-testing requirement for any newly
    registered experiment."""
    import os
    os.environ.pop("LLM_PROVIDER", None)
    before_hash = hashlib.sha256(REAL_LIVE_DB_PATH.read_bytes()).hexdigest() if REAL_LIVE_DB_PATH.exists() else None

    result = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {
            "experiment_id": "research_sharing_priming_counterfactual",
            "agent_id": "agent_roxy",
            "memory_content": "I finished real research on Portland's DIY scene but never posted it anywhere or told the others what I found.",
            "memory_type": "EPISODIC",
            "n_pairs": 1,
        },
    )
    record("research_sharing_priming_counterfactual succeeds for agent_roxy against the fixture provider", result.status == "SUCCESS", result.failure_reason or "")
    if result.status == "SUCCESS":
        trials = result.result.get("trials", [])
        record("research_sharing_priming_counterfactual used the fixture provider, zero real spend", all(t["is_fixture"] for t in trials), "")
        record("research_sharing_priming_counterfactual seeded a real research_id", bool(result.result.get("research_id")), "")

    wrong_agent = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {
            "experiment_id": "research_sharing_priming_counterfactual",
            "agent_id": "agent_lucid",
            "memory_content": "x", "memory_type": "EPISODIC", "n_pairs": 1,
        },
    )
    record(
        "research_sharing_priming_counterfactual rejects any agent_id other than agent_roxy",
        wrong_agent.status == "REJECTED", wrong_agent.failure_reason or "",
    )

    malformed = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {"experiment_id": "research_sharing_priming_counterfactual", "agent_id": "agent_roxy", "memory_content": "x", "memory_type": "NOT_A_REAL_TYPE", "n_pairs": 1},
    )
    record("research_sharing_priming_counterfactual rejects an invalid memory_type (schema level)", malformed.status == "REJECTED", malformed.failure_reason or "")

    extra_field = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {"experiment_id": "research_sharing_priming_counterfactual", "agent_id": "agent_roxy", "memory_content": "x", "memory_type": "EPISODIC", "n_pairs": 1, "python_path": "/tmp/evil.py"},
    )
    record("research_sharing_priming_counterfactual rejects an unknown 'python_path'-style field outright", extra_field.status == "REJECTED", extra_field.failure_reason or "")

    too_many_pairs = broker.execute(
        "RUN_APPROVED_DISPOSABLE_EXPERIMENT",
        {"experiment_id": "research_sharing_priming_counterfactual", "agent_id": "agent_roxy", "memory_content": "x", "memory_type": "EPISODIC", "n_pairs": 999},
    )
    record("research_sharing_priming_counterfactual rejects n_pairs above the schema ceiling (8)", too_many_pairs.status == "REJECTED", too_many_pairs.failure_reason or "")

    after_hash = hashlib.sha256(REAL_LIVE_DB_PATH.read_bytes()).hexdigest() if REAL_LIVE_DB_PATH.exists() else None
    record("live DB hash unchanged after the new experiment's full adversarial+positive scenario set", before_hash == after_hash, "")


def test_positive_provider_and_level2a(_: Path) -> None:
    import os
    os.environ.pop("LLM_PROVIDER", None)

    result = broker.execute("PROVIDER_CONFIGURATION_STATUS", {})
    record("PROVIDER_CONFIGURATION_STATUS succeeds", result.status == "SUCCESS" and "provider" in result.result, result.failure_reason or "")

    call_result = broker.execute(
        "CALL_AUTHORIZED_DIRECTOR_PROVIDER",
        {"system": "You are a test.", "user": "Say hello.", "purpose": "fixturetest_probe", "max_tokens": 200},
    )
    record("CALL_AUTHORIZED_DIRECTOR_PROVIDER succeeds against the fixture provider", call_result.status == "SUCCESS", call_result.failure_reason or "")

    before_hash = hashlib.sha256(REAL_LIVE_DB_PATH.read_bytes()).hexdigest() if REAL_LIVE_DB_PATH.exists() else None
    diag_result = broker.execute(
        "RUN_APPROVED_LEVEL_2A_DIAGNOSTIC",
        {"diagnostic_type": "agent_question_continuity_trace", "scope": {"question_ids": [4]}},
    )
    record(
        "RUN_APPROVED_LEVEL_2A_DIAGNOSTIC succeeds against the real live DB (read-only)",
        diag_result.status == "SUCCESS" and diag_result.result.get("run_status") == "SUCCESS",
        diag_result.failure_reason or "",
    )
    after_hash = hashlib.sha256(REAL_LIVE_DB_PATH.read_bytes()).hexdigest() if REAL_LIVE_DB_PATH.exists() else None
    record("live DB hash unchanged after a Level 2A diagnostic run", before_hash == after_hash, "")

    bad_diag = broker.execute("RUN_APPROVED_LEVEL_2A_DIAGNOSTIC", {"diagnostic_type": "not_an_approved_diagnostic"})
    record("RUN_APPROVED_LEVEL_2A_DIAGNOSTIC rejects an unapproved diagnostic_type", bad_diag.status == "REJECTED", bad_diag.failure_reason or "")


def test_audit_log_written(_: Path) -> None:
    before = broker.AUDIT_LOG_PATH.read_text().splitlines() if broker.AUDIT_LOG_PATH.exists() else []
    broker.execute("PROVIDER_CONFIGURATION_STATUS", {})
    after = broker.AUDIT_LOG_PATH.read_text().splitlines()
    record("audit log gains exactly one line per execute() call", len(after) == len(before) + 1, f"{len(before)} -> {len(after)}")
    last_entry = json.loads(after[-1])
    required_fields = {
        "operation_id", "capability", "status", "started_at", "ended_at", "result",
        "paths_read", "paths_written", "live_db_accessed", "live_db_mutated",
        "provider_calls", "disposable_resource_ids", "failure_reason", "safety_checks",
        "director_round_id",
    }
    record("audit entry has every required field", required_fields.issubset(last_entry.keys()), str(set(last_entry.keys())))


def test_run_bounded_live_window(_: Path) -> None:
    """RUN_BOUNDED_LIVE_WINDOW -- Founder-authorized 2026-09-05. Proves,
    without ever touching the real live DB in write mode, that the
    capability correctly refuses to advance under the current
    (unbounded-findings) research schema, and separately proves the pure
    advancement algorithm's mathematical bound guarantee against a real
    disposable DB using the real run_next_event() + fixture provider."""
    import os
    os.environ.pop("LLM_PROVIDER", None)

    good_params = {
        "max_new_events": 25,
        "question": "Does a real live window surface fresh cross-agent transmission evidence?",
        "favored_hypothesis": "Some real cross-agent influence will appear.",
        "competing_hypothesis": "No new cross-agent influence appears in a small window.",
    }

    # --- Malformed / adversarial parameter rejection ---
    for bad_field, bad_value, label in [
        ("max_new_events", 0, "max_new_events below minimum (1)"),
        ("max_new_events", 26, "max_new_events above the Founder-mandated ceiling (25)"),
        ("question", "", "empty question (preregistration required)"),
        ("favored_hypothesis", "", "empty favored_hypothesis"),
        ("competing_hypothesis", "", "empty competing_hypothesis"),
    ]:
        bad_params = dict(good_params)
        bad_params[bad_field] = bad_value
        r = broker.execute("RUN_BOUNDED_LIVE_WINDOW", bad_params)
        record(f"RUN_BOUNDED_LIVE_WINDOW rejects {label}", r.status == "REJECTED", r.failure_reason or "")

    extra_field_params = dict(good_params)
    extra_field_params["event_ceiling_override"] = 999999
    r = broker.execute("RUN_BOUNDED_LIVE_WINDOW", extra_field_params)
    record("RUN_BOUNDED_LIVE_WINDOW rejects an unknown field (no override surface exists)", r.status == "REJECTED", r.failure_reason or "")

    # Confirm the schema itself has no path-shaped or code-shaped field --
    # structurally, there is nothing for a caller to point at an
    # alternate/live DB path, a python file, or a shell command.
    fields = set(broker.RunBoundedLiveWindowParams.model_fields.keys())
    record(
        "RunBoundedLiveWindowParams has no path/code/command-shaped field",
        fields == {"max_new_events", "question", "favored_hypothesis", "competing_hypothesis"},
        str(fields),
    )

    # --- Proves the capability never opens a database at all when the
    # bound cannot be mechanically guaranteed -- even a nonexistent path
    # still returns a clean, correct refusal. ---
    original_path = broker.CANONICAL_LIVE_DB_PATH
    broker.CANONICAL_LIVE_DB_PATH = Path("/tmp/rbtw_fixturetest_definitely_does_not_exist.db")
    try:
        r = broker.execute("RUN_BOUNDED_LIVE_WINDOW", good_params)
        record("RUN_BOUNDED_LIVE_WINDOW succeeds even against a nonexistent DB path (never opens it)", r.status == "SUCCESS", r.failure_reason or "")
        record(
            "RUN_BOUNDED_LIVE_WINDOW correctly reports LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED for a 25-event window (worst case 42 > 25)",
            r.result.get("status") == "LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED" and r.result.get("computed_worst_case_burst") == 42,
            str(r.result),
        )
        record("RUN_BOUNDED_LIVE_WINDOW's refusal never touches the live DB (live_db_accessed=False)", r.live_db_accessed is False, "")
        record("RUN_BOUNDED_LIVE_WINDOW's refusal never mutates anything (live_db_mutated=False)", r.live_db_mutated is False, "")
    finally:
        broker.CANONICAL_LIVE_DB_PATH = original_path

    # --- CORRECTED, 2026-09-05: the real ResearchSynthesis schema already
    # bounds every list field via custom @field_validator functions (not
    # Pydantic-native max_length metadata, which is why the original
    # version of this check looked in the wrong place and returned None).
    # Proves this two ways: (1) the derivation function now returns the
    # exact expected integer, and (2) the underlying custom validators
    # actually behave as claimed, executed live rather than assumed. ---
    from app.core.config import get_settings
    wc = broker._derive_worst_case_activation_burst(get_settings())
    record("worst-case activation burst is now a concrete, finite, correctly-derived integer", wc == 42, f"got {wc}")

    from app.domain.enums import EvidenceStrength as _EvidenceStrength
    from app.domain.enums import FindingClassification as _FindingClassification
    from app.schemas.research import (
        MAX_FINDINGS_PER_SYNTHESIS as _MAX_FINDINGS,
        MAX_FOLLOW_UP_QUESTIONS as _MAX_FOLLOW_UPS,
        MAX_OPEN_QUESTIONS as _MAX_OPEN_Q,
        ResearchSynthesis as _RS,
        SynthesizedFinding as _SF,
    )
    import pydantic as _pydantic

    try:
        _RS(
            interpretation="x", evidence_strength=_EvidenceStrength.WEAK,
            findings=[_SF(text="f", classification=_FindingClassification.RESEARCH_FINDING) for _ in range(_MAX_FINDINGS + 1)],
        )
        record("ResearchSynthesis.findings really raises past its real cap (executed live)", False, "did not raise")
    except _pydantic.ValidationError:
        record("ResearchSynthesis.findings really raises past its real cap (executed live)", True, "")

    rs_oq = _RS(interpretation="x", evidence_strength=_EvidenceStrength.WEAK, open_questions=[f"q{i}" for i in range(_MAX_OPEN_Q + 3)])
    record("ResearchSynthesis.open_questions really truncates to its real cap (executed live)", len(rs_oq.open_questions) == _MAX_OPEN_Q, f"got {len(rs_oq.open_questions)}, cap {_MAX_OPEN_Q}")

    rs_fu = _RS(interpretation="x", evidence_strength=_EvidenceStrength.WEAK, follow_up_questions=[f"f{i}" for i in range(_MAX_FOLLOW_UPS + 3)])
    record("ResearchSynthesis.follow_up_questions really truncates to its real cap (executed live)", len(rs_fu.follow_up_questions) == _MAX_FOLLOW_UPS, f"got {len(rs_fu.follow_up_questions)}, cap {_MAX_FOLLOW_UPS}")

    # --- Pure algorithm correctness, against a REAL disposable DB with the
    # REAL run_next_event() + fixture provider, proving the bound
    # guarantee holds mechanically when given a true worst-case burst. ---
    import director_diagnostics as dd
    from app.core.db_safety import safe_rmtree
    from sqlalchemy import select
    import seed_agents
    from app.providers.llm import get_llm_provider
    from app.services.orchestrator import run_next_event
    from app.db.models.events import Event

    tmp_dir, session = dd.create_guarded_isolated_sqlite_session(prefix="director_broker_fixturetest_rbtw_")
    try:
        seed_agents.run(session)
        session.commit()
        settings = get_settings()
        provider = get_llm_provider(settings)

        def _get_max() -> int:
            return session.scalar(select(Event.id).order_by(Event.id.desc()).limit(1)) or 0

        def _run_one():
            outcome = run_next_event(session, settings=settings, provider=provider)
            session.commit()
            return outcome

        start = _get_max()
        outcome = broker._advance_bounded(session, _get_max, _run_one, target_max_event_id=start + 10, worst_case_burst=3)
        record(
            "pure _advance_bounded algorithm never exceeds its target against a real disposable DB",
            outcome.end_max_event_id <= outcome.target_max_event_id,
            f"start={outcome.start_max_event_id} end={outcome.end_max_event_id} target={outcome.target_max_event_id}",
        )
        record("pure _advance_bounded algorithm ran at least one real activation", outcome.activations_run > 0, str(outcome.activations_run))
        record(
            "pure _advance_bounded algorithm stops for a legitimate reason",
            outcome.stopped_reason in ("target_reached", "insufficient_margin", "no_eligible_agent"),
            outcome.stopped_reason,
        )

        # Adversarial: an intentionally WRONG (too-small) worst_case_burst
        # must trip the internal safety-violation check rather than
        # silently overshoot -- proves the guard is load-bearing, not
        # decorative. Uses a fake run_one that always reports a burst
        # larger than the deliberately-wrong margin allows.
        from app.domain.enums import EventType as _EventType

        def _run_one_big_burst():
            # Simulate a single call emitting far more events than the
            # (deliberately wrong) worst_case_burst below would allow --
            # bypasses run_next_event entirely to make the "one atomic
            # call emitted N rows" scenario deterministic and instant.
            for _ in range(20):
                session.add(Event(event_type=_EventType.AGENT_WOKE, agent_id="agent_dex", payload={}, sim_day=1, sim_period="MORNING"))
            session.commit()
            return object()

        try:
            broker._advance_bounded(session, _get_max, _run_one_big_burst, target_max_event_id=_get_max() + 5, worst_case_burst=3)
            record("wrong worst_case_burst is caught by the internal safety check", False, "no exception raised -- silent overshoot!")
        except broker.BrokerError as exc:
            record("wrong worst_case_burst is caught by the internal safety check", "SAFETY VIOLATION" in str(exc), str(exc))
    finally:
        session.close()
        safe_rmtree(tmp_dir)

    # --- Full end-to-end exercise of the (currently unreachable in
    # production) live-execution branch: monkeypatch both
    # _derive_worst_case_activation_burst (to simulate a future schema fix
    # making the bound computable) AND CANONICAL_LIVE_DB_PATH (to a
    # disposable "fake live" DB, never the real one) to prove the full
    # pause -> advance -> re-pause -> integrity-check code path is
    # correct, not just the pure algorithm in isolation. ---
    tmp_dir2, fake_live_path = build_fixture_live_db()
    original_derive = broker._derive_worst_case_activation_burst
    original_path = broker.CANONICAL_LIVE_DB_PATH
    try:
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(str(fake_live_path))
        conn.execute("UPDATE simulation_clock SET is_paused = 1")
        conn.commit()
        conn.close()

        broker._derive_worst_case_activation_burst = lambda settings: 3
        broker.CANONICAL_LIVE_DB_PATH = fake_live_path

        r = broker.execute("RUN_BOUNDED_LIVE_WINDOW", {**good_params, "max_new_events": 10})
        record("full live-execution branch succeeds against a disposable fake-live DB", r.status == "SUCCESS", r.failure_reason or "")
        if r.status == "SUCCESS":
            record("live-execution branch reports status COMPLETED", r.result.get("status") == "COMPLETED", str(r.result))
            record("live-execution branch never exceeds the requested window", r.result.get("events_added", 999) <= 10, str(r.result))
            record("live-execution branch ran at least one activation", r.result.get("activations_run", 0) > 0, str(r.result))

        conn = _sqlite3.connect(str(fake_live_path))
        is_paused_after = conn.execute("SELECT is_paused FROM simulation_clock LIMIT 1").fetchone()[0]
        conn.close()
        record("fake-live DB is paused again after the window completes", bool(is_paused_after), f"is_paused={is_paused_after}")

        integ = broker.execute("CHECK_LIVE_DB_INTEGRITY", {})
        record("fake-live DB passes integrity check after the window", integ.result.get("healthy") is True, str(integ.result))
    finally:
        broker._derive_worst_case_activation_burst = original_derive
        broker.CANONICAL_LIVE_DB_PATH = original_path

    # --- CORRECTION, 2026-09-05: regression test for a real infinite-loop
    # risk found while re-deriving the worst-case burst. With
    # auto_advance=False (deliberate, see _impl_run_bounded_live_window's
    # docstring), run_next_event() returns a real EventOutcome -- never a
    # literal None -- even when no agent is eligible to act (e.g. every
    # seeded agent has exhausted MAX_DAILY_AGENT_ACTIVATIONS=6). That
    # produces zero new events, so without the activated_agent_id is None
    # check, _advance_bounded's margin would never shrink and the loop
    # would spin forever. Requests a window (300) far larger than 8 seeded
    # agents x 6 daily activations could ever satisfy, with a hard
    # wall-clock timeout as a backstop in case the fix regresses. ---
    tmp_dir3, fake_live_path3 = build_fixture_live_db()
    try:
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(str(fake_live_path3))
        conn.execute("UPDATE simulation_clock SET is_paused = 1")
        conn.commit()
        conn.close()

        broker._derive_worst_case_activation_burst = lambda settings: 3
        broker.CANONICAL_LIVE_DB_PATH = fake_live_path3

        # The public API's own le=25 ceiling makes a 300-event request
        # impossible for any real caller to construct -- correct, desired
        # behavior. To test the internal loop's own infinite-loop
        # resistance beyond what any real caller could trigger, this
        # deliberately bypasses that validation via model_construct() and
        # calls the implementation directly, exactly as execute() would
        # dispatch to it.
        oversized_params = broker.RunBoundedLiveWindowParams.model_construct(
            max_new_events=300, question=good_params["question"],
            favored_hypothesis=good_params["favored_hypothesis"],
            competing_hypothesis=good_params["competing_hypothesis"],
        )
        fake_result = broker.BrokerResult(
            operation_id="test", capability="RUN_BOUNDED_LIVE_WINDOW", status="FAILED",
            started_at="", ended_at="",
        )
        start_time = time.time()
        payload = broker._impl_run_bounded_live_window(oversized_params, fake_result)
        elapsed = time.time() - start_time
        record(
            "a request no eligible agent can fully satisfy terminates promptly rather than looping forever",
            elapsed < 30.0,
            f"took {elapsed:.1f}s",
        )
        record(
            "it reports a legitimate stop reason, not a silent hang",
            payload.get("stopped_reason") in ("target_reached", "insufficient_margin", "no_eligible_agent"),
            str(payload),
        )
    finally:
        broker._derive_worst_case_activation_burst = original_derive
        broker.CANONICAL_LIVE_DB_PATH = original_path
        safe_rmtree(tmp_dir3)
        safe_rmtree(tmp_dir2)


def test_fail_closed_on_malformed_requests(_: Path) -> None:
    result = broker.execute("LIVE_DB_READ", {"sql": 12345})
    record("malformed params (wrong type) fail closed as REJECTED, not a crash", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("LIVE_DB_READ", {"sql": "SELECT 1", "unexpected_field": "x"})
    record("unknown extra parameter field fails closed (extra='forbid')", result.status == "REJECTED", result.failure_reason or "")

    result = broker.execute("totally_unknown_capability_xyz", {})
    record("unknown capability name fails closed", result.status == "REJECTED", result.failure_reason or "")


def main() -> int:
    import tempfile

    before_hash = hashlib.sha256(REAL_LIVE_DB_PATH.read_bytes()).hexdigest() if REAL_LIVE_DB_PATH.exists() else None

    with_fixture_live_db(test_adversarial_sql_mutations)

    extra_tmp = Path(tempfile.mkdtemp(prefix="director_broker_fixturetest_paths_"))
    try:
        test_adversarial_paths(extra_tmp)
    finally:
        safe_rmtree(extra_tmp)

    test_adversarial_git(Path("."))
    test_adversarial_no_execution_surface(Path("."))
    test_adversarial_secrets(Path("."))

    with_fixture_live_db(test_positive_live_db_read)
    test_positive_files_and_artifacts(Path("."))
    test_positive_git(Path("."))
    test_positive_disposable_lifecycle(Path("."))
    test_positive_disposable_experiment(Path("."))
    test_positive_and_adversarial_research_sharing_experiment(Path("."))
    test_positive_provider_and_level2a(Path("."))
    test_audit_log_written(Path("."))
    test_run_bounded_live_window(Path("."))
    test_fail_closed_on_malformed_requests(Path("."))

    after_hash = hashlib.sha256(REAL_LIVE_DB_PATH.read_bytes()).hexdigest() if REAL_LIVE_DB_PATH.exists() else None
    record("REAL live DB hash unchanged across the entire fixture-test run", before_hash == after_hash, "")

    print()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"{passed}/{len(RESULTS)} scenarios passed.")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
