#!/usr/bin/env python3
"""Fixture-test harness for the Level 2A diagnostics added in the
post-stress-test improvement pass (Founder Packet 2026-09-04):
``conversation_decision_trace`` (recommendation #1) and the 11 diagnostics
broadening coverage beyond conversation/scheduler mechanics
(recommendation #3: research initiation/completion, research provenance,
memory formation/recall, relationship state, belief lifecycle, wall
activity/propagation, rabbit hole lifecycle, question continuity,
population-wide scheduling, invalid-decision patterns, observability gaps).

Every scenario runs the REAL state machine (create_candidate_diagnostic ->
approve_diagnostic(approved_by="Founder") -> run_diagnostic) against a
disposable, synthetic SQLite database this script builds and seeds itself
via the real ORM models — never the live Village DB, never a real agent or
conversation. ``diagnostics_dir`` is also a throwaway temp directory, never
``.director/diagnostics/``.

None of these 12 diagnostic_types is added to
director_autonomous_loop.AUTONOMOUS_DIAGNOSTIC_CATALOG by this delivery —
see each function's docstring in director_diagnostics.py for what it can
and cannot inspect, and the Founder Packet for why catalog membership is a
separate, later, explicit decision.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import director_diagnostics as dd  # noqa: E402
from app.db.models import (  # noqa: E402
    Agent,
    AgentBelief,
    AgentQuestion,
    AgentQuestionStatus,
    BeliefStatus,
    Claim,
    ClaimEvidence,
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationTrigger,
    DailyReport,
    Event,
    EventType,
    EvidenceStrength,
    FindingClassification,
    LLMRun,
    Memory,
    MemoryType,
    RabbitHole,
    RabbitHoleMember,
    RabbitHoleResearch,
    RabbitHoleStatus,
    Relationship,
    ResearchFinding,
    ResearchQuery,
    ResearchSession,
    ResearchSource,
    ResearchSourcePassage,
    ResearchStatus,
    ResearchWallPost,
    WallPostType,
)
from app.db.models.research import SourceQualityTier  # noqa: E402
from app.db.models.research_provenance import EvidenceRelation  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(("PASS " if passed else "FAIL "), name, ("" if passed else f"— {detail}"))


T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def build_fixture_db() -> tuple[Path, Any]:
    """One coherent synthetic Village slice touching every table the 12 new
    diagnostics read, built via the same guarded isolated-DB factory
    director_diagnostics.py itself uses (so the live-root-overlap safety
    check applies here too, not just inside a running diagnostic)."""
    tmp_dir, session = dd.create_guarded_isolated_sqlite_session(prefix="director_diagnostics_fixturetest_")

    for aid in ("agent_1", "agent_2", "agent_3"):
        session.add(Agent(agent_id=aid, identity=f"{aid} identity", voice=f"{aid} voice"))
    session.flush()

    convo = Conversation(
        id=1, trigger_type=ConversationTrigger.MORNING_GATHERING,
        participant_ids=["agent_1", "agent_2"], status=ConversationStatus.ENDED,
        consecutive_silences=2, ending_reason="the room went quiet", started_sim_day=1,
        correlation_id="convo-1",
    )
    session.add(convo)
    session.flush()

    session.add(ConversationMessage(id=1, conversation_id=1, agent_id="agent_2", content="hello there", turn_number=1))

    events = [
        Event(id=1, event_type=EventType.AGENT_WOKE, agent_id="agent_1",
              payload={"conversation_id": 1}, sim_day=1, sim_period="MORNING",
              correlation_id="corr-1", created_at=T0),
        Event(id=2, event_type=EventType.AGENT_ACTED, agent_id="agent_1",
              payload={"actions": ["OBSERVE"]}, sim_day=1, sim_period="MORNING",
              correlation_id="corr-1", causation_id=1, created_at=T0 + timedelta(seconds=1)),
        Event(id=3, event_type=EventType.AGENT_WOKE, agent_id="agent_2",
              payload={"conversation_id": 1}, sim_day=1, sim_period="MORNING",
              correlation_id="corr-2", created_at=T0 + timedelta(seconds=2)),
        Event(id=4, event_type=EventType.AGENT_ACTED, agent_id="agent_2",
              payload={"actions": ["SPEAK"], "public_dialogue": "hello there"}, sim_day=1, sim_period="MORNING",
              correlation_id="corr-2", causation_id=3, created_at=T0 + timedelta(seconds=3)),
        Event(id=5, event_type=EventType.CONVERSATION_ENDED, entity_type="conversation", entity_id="1",
              payload={"reason": "the room went quiet"}, sim_day=1, sim_period="MORNING",
              created_at=T0 + timedelta(seconds=4)),
        Event(id=6, event_type=EventType.AGENT_WOKE, agent_id="agent_3",
              payload={}, sim_day=1, sim_period="AFTERNOON", correlation_id="corr-3",
              created_at=T0 + timedelta(seconds=5)),
        Event(id=7, event_type=EventType.AGENT_ACTED, agent_id="agent_3",
              payload={"actions": ["START_CONVERSATION"]}, sim_day=1, sim_period="AFTERNOON",
              correlation_id="corr-3", causation_id=6, created_at=T0 + timedelta(seconds=6)),
        Event(id=8, event_type=EventType.INVALID_AGENT_DECISION, agent_id="agent_3",
              payload={"reason": "START_CONVERSATION requires a target_agent_id"}, sim_day=1,
              correlation_id="corr-3", created_at=T0 + timedelta(seconds=7)),
        Event(id=9, event_type=EventType.AGENT_RESEARCH_STARTED, agent_id="agent_1",
              payload={"research_id": "res_1"}, sim_day=1, created_at=T0 + timedelta(seconds=8)),
        Event(id=10, event_type=EventType.RESEARCH_COMPLETED, entity_type="research_session", entity_id="res_1",
              payload={}, sim_day=1, created_at=T0 + timedelta(seconds=30)),
        Event(id=11, event_type=EventType.MEMORY_CREATED, entity_type="memory", entity_id="1",
              agent_id="agent_1", payload={}, sim_day=1, created_at=T0 + timedelta(seconds=31)),
        Event(id=12, event_type=EventType.MEMORY_RECALLED, entity_type="memory", entity_id="1",
              agent_id="agent_1", payload={}, sim_day=2, created_at=T0 + timedelta(days=1)),
        Event(id=13, event_type=EventType.BELIEF_CREATED, entity_type="agent_belief", entity_id="1",
              agent_id="agent_1", payload={"confidence": 60}, sim_day=1, created_at=T0 + timedelta(seconds=32)),
        Event(id=14, event_type=EventType.BELIEF_UPDATED, entity_type="agent_belief", entity_id="1",
              agent_id="agent_1", payload={"new_confidence": 80}, sim_day=2, created_at=T0 + timedelta(days=1, seconds=1)),
        Event(id=15, event_type=EventType.RESEARCH_WALL_POSTED, entity_type="research_wall", entity_id="1",
              agent_id="agent_1", payload={}, sim_day=1, created_at=T0 + timedelta(seconds=33)),
        Event(id=16, event_type=EventType.WALL_POST_READ, entity_type="research_wall", entity_id="1",
              agent_id="agent_2", payload={}, sim_day=1, created_at=T0 + timedelta(seconds=34)),
        Event(id=17, event_type=EventType.RABBIT_HOLE_CREATED, entity_type="rabbit_hole", entity_id="1",
              agent_id="agent_1", payload={}, sim_day=1, created_at=T0 + timedelta(seconds=35)),
        Event(id=18, event_type=EventType.RABBIT_HOLE_JOINED, entity_type="rabbit_hole", entity_id="1",
              agent_id="agent_2", payload={}, sim_day=1, created_at=T0 + timedelta(seconds=36)),
        Event(id=19, event_type=EventType.QUESTION_CREATED, entity_type="agent_question", entity_id="1",
              agent_id="agent_1", payload={}, sim_day=1, created_at=T0 + timedelta(seconds=37)),
        Event(id=20, event_type=EventType.QUESTION_LINKED_TO_RESEARCH, entity_type="agent_question", entity_id="1",
              agent_id="agent_1", payload={"research_session_id": "res_1"}, sim_day=1,
              created_at=T0 + timedelta(seconds=38)),
    ]
    for e in events:
        session.add(e)
    session.flush()

    session.add(LLMRun(
        id=1, purpose="agent_decision", agent_id="agent_1", provider="fixture", model="fixture",
        is_fixture=True, input_tokens=100, output_tokens=20, latency_ms=5, stop_reason="end_turn",
        created_at=T0 + timedelta(seconds=1),
    ))
    session.flush()

    session.add(ResearchSession(
        id=1, research_id="res_1", agent_id="agent_1", question="does X affect Y?",
        status=ResearchStatus.COMPLETED, evidence_strength=EvidenceStrength.MODERATE,
        confidence=70.0, created_at=T0 + timedelta(seconds=9), is_fixture=True,
    ))
    session.flush()
    session.add(ResearchQuery(id=1, research_session_id="res_1", query_text="X and Y", sequence_number=0))
    session.add(ResearchSource(
        id=1, research_session_id="res_1", url="https://example.com/x", title="X and Y",
        quality_tier=SourceQualityTier.OFFICIAL, provider="fixture",
    ))
    session.flush()
    session.add(ResearchSourcePassage(
        id=1, source_id=1, research_query_id=1, excerpt_text="X correlates with Y.",
        excerpt_sha256="0" * 64,
    ))
    session.flush()
    session.add(ResearchFinding(
        id=1, research_session_id="res_1", finding_text="X correlates with Y.",
        classification=FindingClassification.REAL_WORLD_FACT,
    ))
    session.flush()
    session.add(Claim(
        id=1, research_session_id="res_1", finding_id=1, claim_text="X correlates with Y.",
        classification=FindingClassification.REAL_WORLD_FACT, confidence=70.0,
    ))
    session.flush()
    session.add(ClaimEvidence(id=1, claim_id=1, passage_id=1, relation=EvidenceRelation.SUPPORTS))
    session.flush()

    session.add(Memory(
        id=1, agent_id="agent_1", memory_type=MemoryType.SEMANTIC, content="X correlates with Y.",
        importance=60.0, confidence=70.0, created_sim_day=1, last_accessed=None,
        reinforcement_count=0,
    ))
    session.flush()

    session.add(Relationship(
        id=1, agent_a_id="agent_1", agent_b_id="agent_2", trust_score=65.0,
        interaction_count=1, familiarity=10.0, intellectual_affinity=55.0,
    ))
    session.flush()

    session.add(AgentBelief(
        id=1, agent_id="agent_1", statement="X affects Y", confidence=80.0, basis=["res_1"],
        status=BeliefStatus.SUPPORTED, updated_at=T0 + timedelta(days=1, seconds=1),
    ))
    session.flush()

    session.add(ResearchWallPost(
        id=1, agent_id="agent_1", post_type=WallPostType.FINDING, content="X correlates with Y.",
        related_research_id="res_1",
    ))
    session.flush()

    session.add(RabbitHole(
        id=1, title="Does X affect Y?", originating_agent_id="agent_1",
        evidence_strength=EvidenceStrength.MODERATE, status=RabbitHoleStatus.ACTIVE,
        activity_level=1.0, last_activity_day=1,
    ))
    session.flush()
    session.add(RabbitHoleMember(id=1, rabbit_hole_id=1, agent_id="agent_1", joined_at=T0))
    session.add(RabbitHoleMember(id=2, rabbit_hole_id=1, agent_id="agent_2", joined_at=T0 + timedelta(seconds=1)))
    session.add(RabbitHoleResearch(id=1, rabbit_hole_id=1, research_session_id="res_1"))
    session.flush()

    session.add(AgentQuestion(
        id=1, agent_id="agent_1", question="Does X affect Y?", status=AgentQuestionStatus.RESEARCHING,
        salience=55.0, research_session_id="res_1",
    ))
    session.flush()

    session.add(DailyReport(
        id=1, day_number=1, title="Day 1", summary_text="A quiet day.", structured={},
        had_meaningful_activity=True, is_fixture=True,
    ))
    session.flush()

    # Pure size padding: app.core.db_safety.check_live_db (correctly, for a
    # real live database) refuses anything under MIN_LIVE_DB_BYTES (8192) as
    # "looks empty or corrupt" -- run_diagnostic applies that same check to
    # ANY db_path, including a disposable fixture one. This minimal schema's
    # genuine content fits in a single 4096-byte SQLite page; one oversized
    # filler row pushes it past the threshold honestly (real data, just
    # padding-sized) rather than weakening the safety check itself.
    session.add(Memory(
        id=2, agent_id="agent_1", memory_type=MemoryType.EPISODIC, content="padding " * 2000,
        importance=1.0, confidence=1.0, created_sim_day=1,
    ))

    session.commit()
    # create_guarded_isolated_sqlite_session's engine runs in WAL mode by
    # default: committed data lives in the -wal file until checkpointed, so
    # the main .db file can stay at its initial single page indefinitely.
    # app.core.db_safety.check_live_db (correctly, for the real live DB)
    # only ever inspects the main file's size/contents -- so force a
    # checkpoint here rather than have every diagnostic fail its health
    # check against fully-committed, but not-yet-checkpointed, fixture data.
    from sqlalchemy import text
    session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    session.close()
    db_path = tmp_dir / "isolated_test.db"
    return tmp_dir, db_path


def run_one(diagnostic_type: str, db_path: Path, diagnostics_dir: Path, *, allowed_tables: list[str],
            scope: dict, capabilities: list[str] | None = None) -> dict:
    spec = dd.create_candidate_diagnostic(
        diagnostic_type=diagnostic_type, originating_round_id="round_fixturetest",
        originating_snapshot_id="snap_fixturetest", originating_recommendation="fixture test only",
        evidence_refs=[], allowed_operations={
            "read_live_db_tables": allowed_tables, "read_repo_files": [
                "app/services/context_builder.py", "app/services/orchestrator.py", "app/schemas/actions.py",
            ],
            "capabilities": capabilities or [],
        },
        scope=scope, success_criteria="fixture test", failure_criteria="fixture test",
        timeout_seconds=30, diagnostics_dir=diagnostics_dir,
    )
    dd.approve_diagnostic(spec.diagnostic_id, approved_by="Founder", diagnostics_dir=diagnostics_dir)
    spec = dd.run_diagnostic(spec.diagnostic_id, db_path=db_path, diagnostics_dir=diagnostics_dir)
    assert spec.state.value == "DIAGNOSTIC_COMPLETE", spec
    assert spec.run_status == "SUCCESS", spec.run_error
    return dd.load_evidence(spec.diagnostic_id, diagnostics_dir=diagnostics_dir)


def main() -> int:
    tmp_dir, db_path = build_fixture_db()
    diagnostics_dir = tmp_dir / "diagnostics_state"
    try:
        _run_scenarios(db_path, diagnostics_dir)
        _run_boundary_scenarios(db_path, diagnostics_dir)
    finally:
        from app.core.db_safety import safe_rmtree
        safe_rmtree(tmp_dir)

    print()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"{passed}/{len(RESULTS)} scenarios passed.")
    return 0 if passed == len(RESULTS) else 1


def _run_scenarios(db_path: Path, diagnostics_dir: Path) -> None:
    try:
        ev = run_one(
            "conversation_decision_trace", db_path, diagnostics_dir,
            allowed_tables=["events", "conversations", "conversation_messages", "llm_runs"],
            scope={"event_ids": [2, 4, 7]},
        )
        t2 = next(t for t in ev["traces"] if t["provenance"]["acted_event_id"] == 2)
        t4 = next(t for t in ev["traces"] if t["provenance"]["acted_event_id"] == 4)
        t7 = next(t for t in ev["traces"] if t["provenance"]["acted_event_id"] == 7)
        assert t2["provenance"]["wake_event_id"] == 1
        assert t2["raw_model_response"]["available"] is False
        assert t2["raw_model_response"]["telemetry_match"]["id"] == 1
        assert t4["persisted_as_conversation_message"] is True
        assert t4["closure"]["conversation_ended_immediately_after"] is True
        assert t7["validation_result"]["rejected"] is True
        assert t7["validation_result"]["reason"] == "START_CONVERSATION requires a target_agent_id"
        assert t7["state_presented"]["in_conversation"] is False
        record("conversation_decision_trace: telemetry gap reported, persistence/closure/validation all correct", True)
    except Exception as exc:  # noqa: BLE001
        record("conversation_decision_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "research_initiation_and_completion_trace", db_path, diagnostics_dir,
            allowed_tables=["events", "research_sessions", "research_queries", "research_sources",
                             "research_findings"],
            scope={"agent_ids": ["agent_1"]},
        )
        a1 = ev["agents"][0]
        assert a1["session_count"] == 1
        assert a1["sessions"][0]["reached_research_completed_event"] is True
        assert a1["sessions"][0]["finding_count"] == 1
        record("research_initiation_and_completion_trace: session/query/source/finding counts and completion event all correct", True)
    except Exception as exc:  # noqa: BLE001
        record("research_initiation_and_completion_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "research_provenance_and_evidence_flow_trace", db_path, diagnostics_dir,
            allowed_tables=["research_findings", "claims", "claim_evidence", "research_source_passages",
                             "research_sources", "research_wall"],
            scope={"finding_ids": [1]},
        )
        f1 = ev["findings"][0]
        assert f1["claim_count"] == 1
        assert f1["claims"][0]["evidence_chain"][0]["source"]["url"] == "https://example.com/x"
        assert len(f1["session_cited_by_wall_posts"]) == 1
        assert not f1["claims_with_zero_evidence"]
        record("research_provenance_and_evidence_flow_trace: claim -> evidence -> passage -> source chain intact", True)
    except Exception as exc:  # noqa: BLE001
        record("research_provenance_and_evidence_flow_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "memory_formation_and_recall_trace", db_path, diagnostics_dir,
            allowed_tables=["memories", "events"], scope={"memory_ids": [1]},
        )
        m1 = ev["memories"][0]
        assert m1["creation_event_id"] == 11
        assert m1["recalled_event_count"] == 1
        assert m1["consistency_checks"]["reinforcement_count_matches_event_count"] is True
        assert m1["consistency_checks"]["last_accessed_matches_last_recalled_event"] is False, (
            "seeded last_accessed=None with a real MEMORY_RECALLED event on disk -- must be reported "
            "as a mismatch, not silently treated as consistent"
        )
        record("memory_formation_and_recall_trace: creation/recall events found, deliberate last_accessed mismatch correctly caught", True)
    except Exception as exc:  # noqa: BLE001
        record("memory_formation_and_recall_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "relationship_state_and_influence_trace", db_path, diagnostics_dir,
            allowed_tables=["relationships", "conversations", "messages"],
            scope={"agent_pairs": [["agent_1", "agent_2"]]},
        )
        p = ev["pairs"][0]
        assert p["relationship_row"]["trust_score"] == 65.0
        assert p["shared_conversation_count_from_events"] == 1
        record("relationship_state_and_influence_trace: current relationship row plus independent conversation recount both correct", True)
    except Exception as exc:  # noqa: BLE001
        record("relationship_state_and_influence_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "belief_lifecycle_trace", db_path, diagnostics_dir,
            allowed_tables=["agent_beliefs", "events"], scope={"belief_ids": [1]},
        )
        b1 = ev["beliefs"][0]
        assert b1["lifecycle_event_count"] == 2
        assert b1["revision_count"] == 1
        assert b1["ever_rejected"] is False
        record("belief_lifecycle_trace: creation + one revision correctly traced, never-rejected correctly reported", True)
    except Exception as exc:  # noqa: BLE001
        record("belief_lifecycle_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "research_wall_activity_and_propagation_trace", db_path, diagnostics_dir,
            allowed_tables=["research_wall", "events"], scope={"post_ids": [1]},
        )
        p1 = ev["posts"][0]
        assert p1["distinct_readers"] == ["agent_2"]
        assert p1["read_event_count"] == 1
        assert p1["challenge_event_count"] == 0
        record("research_wall_activity_and_propagation_trace: readers and challenge count correct", True)
    except Exception as exc:  # noqa: BLE001
        record("research_wall_activity_and_propagation_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "rabbit_hole_lifecycle_trace", db_path, diagnostics_dir,
            allowed_tables=["rabbit_holes", "rabbit_hole_members", "rabbit_hole_research", "events"],
            scope={"rabbit_hole_ids": [1]},
        )
        r1 = ev["rabbit_holes"][0]
        assert len(r1["current_members"]) == 2
        assert r1["attached_research_session_ids"] == ["res_1"]
        assert r1["lifecycle_event_count"] == 2
        record("rabbit_hole_lifecycle_trace: membership, attached research, and lifecycle events all correct", True)
    except Exception as exc:  # noqa: BLE001
        record("rabbit_hole_lifecycle_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "agent_question_continuity_trace", db_path, diagnostics_dir,
            allowed_tables=["agent_questions", "events", "research_sessions"],
            scope={"question_ids": [1]},
        )
        q1 = ev["questions"][0]
        assert q1["lifecycle_event_count"] == 2
        assert q1["linked_research_session_status"] == "COMPLETED"
        assert q1["is_reformulation_chain_link"] is False
        record("agent_question_continuity_trace: lifecycle events and forward research-link status correct", True)
    except Exception as exc:  # noqa: BLE001
        record("agent_question_continuity_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "agent_opportunity_and_scheduling_trace", db_path, diagnostics_dir,
            allowed_tables=["events", "agents"], scope={"sim_day_range": [1, 1]},
        )
        pa = ev["per_agent"]
        assert pa["agent_1"]["acted_count"] == 1 and pa["agent_1"]["passive_count"] == 1
        assert pa["agent_2"]["acted_count"] == 1 and pa["agent_2"]["substantive_count"] == 1
        assert pa["agent_3"]["acted_count"] == 1
        assert ev["population_fairness"]["min_acted_count"] == 1
        assert ev["population_fairness"]["max_acted_count"] == 1
        assert ev["population_fairness"]["spread"] == 0
        record("agent_opportunity_and_scheduling_trace: per-agent passive/substantive split and population fairness stats correct", True)
    except Exception as exc:  # noqa: BLE001
        record("agent_opportunity_and_scheduling_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "invalid_decision_pattern_trace", db_path, diagnostics_dir,
            allowed_tables=["events"], scope={"sim_day_range": [1, 1]},
        )
        assert ev["total_invalid_decisions"] == 1
        assert ev["by_agent"]["agent_3"] == 1
        assert ev["detail"][0]["was_in_conversation"] is False
        assert "generation/validation failure" in ev["detail"][0]["classification"]
        record("invalid_decision_pattern_trace: classification, per-agent breakdown, and in-conversation flag all correct", True)
    except Exception as exc:  # noqa: BLE001
        record("invalid_decision_pattern_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        ev = run_one(
            "observability_gap_scan", db_path, diagnostics_dir,
            allowed_tables=["daily_reports", "events", "messages"], scope={"sim_day_range": [1, 1]},
        )
        d1 = ev["per_day"][0]
        assert d1["had_meaningful_activity"]  # raw sqlite read: 1/0, not a Python bool -- truthy check only
        assert d1["wall_posted_count"] == 1
        assert len(ev["known_structural_gaps"]) >= 3
        record("observability_gap_scan: per-day signature computed and known structural gaps listed", True)
    except Exception as exc:  # noqa: BLE001
        record("observability_gap_scan", False, f"{type(exc).__name__}: {exc}")


def _run_boundary_scenarios(db_path: Path, diagnostics_dir: Path) -> None:
    """Same allowlist/forbidden-operations guarantees the original 5
    diagnostics have — proven against one of the new diagnostic types
    rather than assumed to carry over."""
    try:
        spec = dd.create_candidate_diagnostic(
            diagnostic_type="memory_formation_and_recall_trace", originating_round_id="round_fixturetest",
            originating_snapshot_id="snap_fixturetest", originating_recommendation="boundary test",
            evidence_refs=[], allowed_operations={"read_live_db_tables": ["memories"]},  # events NOT declared
            scope={"memory_ids": [1]}, success_criteria="x", failure_criteria="x", timeout_seconds=30,
            diagnostics_dir=diagnostics_dir,
        )
        assert set(spec.forbidden_operations) >= set(dd.STANDARD_FORBIDDEN_OPERATIONS)
        dd.approve_diagnostic(spec.diagnostic_id, approved_by="Founder", diagnostics_dir=diagnostics_dir)
        # run_diagnostic sets run_status="FAILED" on disk AND re-raises the safety error -- both must
        # be checked, not just the exception.
        try:
            dd.run_diagnostic(spec.diagnostic_id, db_path=db_path, diagnostics_dir=diagnostics_dir)
            assert False, "reading an undeclared table must raise, not silently skip it"
        except dd.DiagnosticSafetyError as exc:
            assert "events" in str(exc) and "not in this diagnostic's" in str(exc), str(exc)
        reloaded = dd.load_spec(spec.diagnostic_id, diagnostics_dir=diagnostics_dir)
        assert reloaded.run_status == "FAILED", reloaded
        assert "events" in reloaded.run_error and "not in this diagnostic's" in reloaded.run_error
        record("new diagnostics inherit table-allowlist enforcement (undeclared table refused, standard forbidden-ops present)", True)
    except Exception as exc:  # noqa: BLE001
        record("table-allowlist enforcement on a new diagnostic type", False, f"{type(exc).__name__}: {exc}")

    try:
        spec = dd.create_candidate_diagnostic(
            diagnostic_type="conversation_decision_trace", originating_round_id="round_fixturetest",
            originating_snapshot_id="snap_fixturetest", originating_recommendation="boundary test",
            evidence_refs=[], allowed_operations={"read_live_db_tables": ["events", "conversations",
                                                                            "conversation_messages", "llm_runs"]},
            scope={"event_ids": [2]}, success_criteria="x", failure_criteria="x", timeout_seconds=30,
            diagnostics_dir=diagnostics_dir,
        )
        dd.approve_diagnostic(spec.diagnostic_id, approved_by="Founder", diagnostics_dir=diagnostics_dir)
        try:
            dd.run_diagnostic(spec.diagnostic_id, db_path=db_path, diagnostics_dir=diagnostics_dir)
            assert False, "missing read_repo_files declaration must raise, not silently return empty source"
        except dd.DiagnosticSafetyError:
            pass
        reloaded = dd.load_spec(spec.diagnostic_id, diagnostics_dir=diagnostics_dir)
        assert reloaded.run_status == "FAILED", reloaded
        record("conversation_decision_trace refuses to run without its declared read_repo_files", True)
    except Exception as exc:  # noqa: BLE001
        record("read_repo_files allowlist enforcement on conversation_decision_trace", False, f"{type(exc).__name__}: {exc}")

    try:
        spec = dd.create_candidate_diagnostic(
            diagnostic_type="invalid_decision_pattern_trace", originating_round_id="round_fixturetest",
            originating_snapshot_id="snap_fixturetest", originating_recommendation="boundary test",
            evidence_refs=[], allowed_operations={"read_live_db_tables": ["events"]},
            scope={"sim_day_range": [1, 1]}, success_criteria="x", failure_criteria="x", timeout_seconds=30,
            diagnostics_dir=diagnostics_dir,
        )
        dd.approve_diagnostic(spec.diagnostic_id, approved_by="Founder", diagnostics_dir=diagnostics_dir)
        spec = dd.run_diagnostic(spec.diagnostic_id, db_path=db_path, diagnostics_dir=diagnostics_dir)
        assert spec.state.value == "DIAGNOSTIC_COMPLETE", spec  # the legitimate first run must succeed
        try:
            dd.run_diagnostic(spec.diagnostic_id, db_path=db_path, diagnostics_dir=diagnostics_dir)
            assert False, "re-running an already-complete diagnostic must fail"
        except dd.DiagnosticSafetyError:
            pass
        record("new diagnostic types still cannot re-run past DIAGNOSTIC_COMPLETE", True)
    except Exception as exc:  # noqa: BLE001
        record("terminal-state enforcement on a new diagnostic type", False, f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
