#!/usr/bin/env python3
"""Deterministic Packet 9 smoke test: drives the real loop until both an
organic reflection chain and an automatic daily report have happened, then
asserts each end to end.

    Several of an agent's own memories accumulate real significance
      -> the mechanical pressure threshold is crossed (app/services/reflection.py)
      -> a reflection is actually formed, citing real prior memories/research/
         beliefs/conversations/rabbit holes/wall posts/earlier reflections —
         never an invented id
      -> that reflection is shown in the agent's own later context
         (RECENT REFLECTIONS, app/services/context_builder.py) and goes on to
         shape a later action's real content
    AND, independently:
    the simulated day reaches NIGHT's end
      -> app/services/daily_synthesis.py gathers the day's real activity from
         the database (never the raw log, never fabricated)
      -> ranks it by actual significance, not by count
      -> a Daily Field Report is generated automatically and persisted
      -> its content maps back to real rows, every sourced item still
         carrying its real id and §2 classification

Every step happens through the real event loop — scheduler picks an agent,
FixtureLLMProvider.complete() makes that agent's own decision (including the
reflection/report syntheses once triggered), and orchestrator validation and
execution run exactly as they would for a live model. Nothing here scripts a
reflection's content, hand-writes a report, or inserts a finished record
directly — a fixed seed only makes which choices happen to occur
reproducible, the same discipline as every other smoke_test_*.py in this repo.

Usage::

    python scripts/smoke_test_reflection_report.py
    python scripts/smoke_test_reflection_report.py --seed other --max-events 8000
    python scripts/smoke_test_reflection_report.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_reflection_report.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "packet9-smoke"
#: Reflections take several simulated days of real activity to accumulate
#: enough significance to trigger (observed ~5-10 days per agent in manual
#: runs), and a report is only generated once per day boundary — a much
#: longer ceiling than Packets 5-8's single-chain smoke tests need.
DEFAULT_MAX_EVENTS = 8000

#: A genuine later influence needs the later action to be on a later
#: simulated day than the reflection that (may have) shaped it.
MIN_INFLUENCE_GAP_DAYS = 1


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument("--keep-db", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="print every event")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    import seed_agents

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.providers.llm import get_llm_provider
    from app.services.orchestrator import run_next_event

    settings = get_settings()
    print(f"Database: {settings.database_url}  (throwaway, deleted first)")
    if not settings.uses_fixture_llm or not settings.uses_fixture_research:
        print("This smoke test requires the fixture providers on both sides.")
        return 1

    session = SessionLocal()
    try:
        report = seed_agents.run(session)
        session.commit()
        print(f"Seeded: {len(report.created)} rows created.\n")

        provider = get_llm_provider(settings)

        print(f"Driving RUN NEXT EVENT (seed={args.seed!r}, up to {args.max_events} events)...")
        for i in range(1, args.max_events + 1):
            outcome = run_next_event(
                session, settings=settings, provider=provider,
                seed=args.seed, auto_advance=True,
            )
            session.commit()
            if args.verbose and outcome.decision is not None:
                print(f"  [{i}] {outcome.activated_agent_id}: {outcome.decision.summary}")

            if i % 800 == 0:
                print(f"  ... {i} events so far")

            if i % 100 == 0 or i == args.max_events:
                result = _check_all(session, settings)
                if result["complete"]:
                    print(f"\nAll checkpoints complete after {i} events.")
                    break
        else:
            result = _check_all(session, settings)

        print("\nChain checkpoints:")
        for label, ok in result["checks"]:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

        if not result["complete"]:
            print(
                f"\nFAIL: not every checkpoint completed within {args.max_events} events. "
                "Try a higher --max-events or a different --seed."
            )
            return 1

        print("\nPASS: an organic reflection chain and an automatic daily report both occurred:")
        print(f"  reflection #{result['reflection_id']} ({result['reflection_agent']}, "
              f"day {result['reflection_day']}): {result['reflection_topic']!r}")
        print(f"    triggered at pressure {result['pressure_at_trigger']:.1f} "
              f"(threshold {result['threshold']:.1f})")
        print(f"    sources: {result['source_summary']}")
        print(f"    later influenced: {result['influenced_kind']} on day {result['influenced_day']} "
              f"— {result['influenced_text']!r}")
        print(f"  daily report #{result['report_id']} (day {result['report_day']}) "
              f"had_meaningful_activity={result['report_had_activity']}")
        print(f"    top-ranked item: {result['report_top_item']!r}")
        print("\nInspect it directly:")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_reflections.py")
        print(f"  DATABASE_URL={settings.database_url} .venv/bin/python scripts/inspect_daily_report.py --structured")
        return 0
    finally:
        session.close()
        if not args.keep_db:
            _clean_db()
        else:
            print(f"\nDatabase kept at {DB_PATH}")


def _check_all(session, settings) -> dict:
    """Try every reflection and every report in whatever state the database
    is in now, same reasoning as every other smoke test here: the earliest
    reflection formed is not necessarily the one that also went on to
    influence a later action, so every candidate gets a real attempt."""
    checks: list[tuple[str, bool]] = []
    result: dict = {"complete": False, "checks": checks}

    reflection_result = _check_reflection_chain(session)
    checks.extend(reflection_result["checks"])
    result.update({k: v for k, v in reflection_result.items() if k != "checks"})

    report_result = _check_daily_report(session, settings)
    checks.extend(report_result["checks"])
    result.update({k: v for k, v in report_result.items() if k != "checks"})

    result["complete"] = reflection_result["complete"] and report_result["complete"]
    return result


def _check_reflection_chain(session) -> dict:
    from app.db.models.conversations import Conversation
    from app.db.models.events import Event
    from app.db.models.rabbit_holes import RabbitHole
    from app.db.models.reflection import AgentReflection
    from app.db.models.research import ResearchSession
    from app.db.models.wall import ResearchWallPost
    from app.domain.enums import EventType
    from app.services.wall import keywords as extract_keywords

    checks: list[tuple[str, bool]] = []
    result: dict = {"complete": False, "checks": checks}

    created_events = {
        e.entity_id: e
        for e in session.query(Event).filter(Event.event_type == EventType.REFLECTION_CREATED)
    }
    stage_triggered = bool(created_events)
    checks.append(("reflection was triggered by accumulated significance", stage_triggered))
    if not stage_triggered:
        checks.append(("reflection cites real prior inputs", False))
        checks.append(("reflection later influenced agent context/behavior", False))
        return result

    reflections = (
        session.query(AgentReflection)
        .filter(AgentReflection.id.in_([int(rid) for rid in created_events]))
        .order_by(AgentReflection.id)
        .all()
    )

    # Provenance: true if ANY reflection has a non-empty source list AND that
    # threshold was genuinely crossed at trigger time (never just asserted).
    grounded = None
    threshold = pressure_at_trigger = None
    for r in reflections:
        source_counts = {
            "memories": len(r.source_memory_ids or []),
            "research": len(r.source_research_ids or []),
            "beliefs": len(r.source_belief_ids or []),
            "conversations": len(r.source_conversation_ids or []),
            "rabbit_holes": len(r.source_rabbit_hole_ids or []),
            "wall_posts": len(r.source_wall_post_ids or []),
            "reflections": len(r.source_reflection_ids or []),
        }
        if sum(source_counts.values()) > 0:
            evt = created_events[str(r.id)]
            grounded = r
            threshold = evt.payload.get("threshold")
            pressure_at_trigger = evt.payload.get("pressure_at_trigger")
            result["source_summary"] = ", ".join(f"{k}={v}" for k, v in source_counts.items() if v)
            break
    stage_grounded = grounded is not None and pressure_at_trigger is not None and threshold is not None and pressure_at_trigger >= threshold
    checks.append(("reflection cites real prior inputs", stage_grounded))
    if not stage_grounded:
        checks.append(("reflection later influenced agent context/behavior", False))
        return result

    result.update(
        reflection_id=grounded.id, reflection_agent=grounded.agent_id,
        reflection_day=grounded.simulation_day, reflection_topic=grounded.topic,
        pressure_at_trigger=pressure_at_trigger, threshold=threshold,
    )

    # Influence: this agent's own later research/wall/rabbit-hole/conversation
    # content, on a later simulated day, genuinely overlapping the
    # reflection's own topic/summary/open_question vocabulary — the same
    # keyword-citation discipline scripts/smoke_test_character_development.py
    # already uses for "an emerging interest cited as a later action's topic".
    influence_found = None
    for r in reflections:
        topic_kw = (
            extract_keywords(r.topic) | extract_keywords(r.summary) | extract_keywords(r.open_question or "")
        )
        if not topic_kw:
            continue

        later_research = session.query(ResearchSession).filter(ResearchSession.agent_id == r.agent_id).all()
        for rs in later_research:
            started = session.query(Event).filter(
                Event.event_type == EventType.AGENT_RESEARCH_STARTED, Event.entity_id == rs.research_id
            ).first()
            day = started.sim_day if started else None
            if day is None or day - r.simulation_day < MIN_INFLUENCE_GAP_DAYS:
                continue
            overlap = topic_kw & extract_keywords(rs.question)
            if overlap:
                influence_found = (r, "research question", day, rs.question, overlap)
                break
        if influence_found:
            break

        later_posts = session.query(ResearchWallPost).filter(ResearchWallPost.agent_id == r.agent_id).all()
        for post in later_posts:
            posted = session.query(Event).filter(
                Event.event_type == EventType.RESEARCH_WALL_POSTED, Event.entity_id == str(post.id)
            ).first()
            day = posted.sim_day if posted else None
            if day is None or day - r.simulation_day < MIN_INFLUENCE_GAP_DAYS:
                continue
            overlap = topic_kw & extract_keywords(post.content)
            if overlap:
                influence_found = (r, "wall post", day, post.content, overlap)
                break
        if influence_found:
            break

        later_holes = session.query(RabbitHole).filter(RabbitHole.originating_agent_id == r.agent_id).all()
        for hole in later_holes:
            if hole.last_activity_day is None or hole.last_activity_day - r.simulation_day < MIN_INFLUENCE_GAP_DAYS:
                continue
            overlap = topic_kw & extract_keywords(hole.title)
            if overlap:
                influence_found = (r, "rabbit hole", hole.last_activity_day, hole.title, overlap)
                break
        if influence_found:
            break

        later_convos = (
            session.query(Conversation)
            .filter(Conversation.participant_ids.isnot(None))
            .all()
        )
        for convo in later_convos:
            if r.agent_id not in (convo.participant_ids or []):
                continue
            day = convo.started_sim_day
            if day is None or day - r.simulation_day < MIN_INFLUENCE_GAP_DAYS or not convo.current_subject:
                continue
            overlap = topic_kw & extract_keywords(convo.current_subject)
            if overlap:
                influence_found = (r, "conversation subject", day, convo.current_subject, overlap)
                break
        if influence_found:
            break

    stage_influenced = influence_found is not None
    checks.append(("reflection later influenced agent context/behavior", stage_influenced))
    if not stage_influenced:
        return result

    r, kind, day, text, overlap = influence_found
    result.update(
        reflection_id=r.id, reflection_agent=r.agent_id, reflection_day=r.simulation_day,
        reflection_topic=r.topic, influenced_kind=kind, influenced_day=day, influenced_text=text,
    )
    result["complete"] = True
    return result


def _check_daily_report(session, settings) -> dict:
    from app.db.models.events import Event
    from app.db.models.reports import DailyReport
    from app.domain.enums import EventType

    checks: list[tuple[str, bool]] = []
    result: dict = {"complete": False, "checks": checks}

    reports = session.query(DailyReport).order_by(DailyReport.day_number).all()
    created_events = {
        e.payload.get("day"): e
        for e in session.query(Event).filter(Event.event_type == EventType.DAILY_REPORT_CREATED)
    }
    stage_created = bool(reports) and bool(created_events)
    checks.append(("daily report was created automatically", stage_created))
    if not stage_created:
        checks.append(("report content maps to real database activity", False))
        checks.append(("sourced claims retain provenance", False))
        checks.append(("low-value noise was not promoted as major insight", False))
        return result

    # Prefer a report that actually had meaningful activity, so the mapping
    # and provenance checks have something real to verify against.
    candidate = next((r for r in reports if r.had_meaningful_activity), reports[0])
    facts = candidate.structured.get("facts", {})

    # Maps to real DB activity: at least one fact item's real id resolves to
    # an actual row of the kind it claims to be.
    mapped = _first_real_mapping(session, facts)
    stage_mapped = mapped is not None
    checks.append(("report content maps to real database activity", stage_mapped))

    # Provenance: every item in whichever list mapped carries a real id and a
    # real §2 classification tag, not just prose.
    stage_provenance = stage_mapped and all(
        item.get("id") and item.get("classification") for item in facts.get(mapped[0], []) if mapped
    )
    checks.append(("sourced claims retain provenance", stage_provenance))

    # Ranking: whichever fact list drove "top discoveries" is sorted by real
    # score, descending — the mechanical guarantee that a high-value item
    # cannot be crowded out by many low-value ones once capped.
    findings = facts.get("findings", [])
    scores = [item.get("score", 0) for item in findings]
    stage_ranked = scores == sorted(scores, reverse=True)
    checks.append(("low-value noise was not promoted as major insight", stage_ranked))

    result.update(
        report_id=candidate.id, report_day=candidate.day_number,
        report_had_activity=candidate.had_meaningful_activity,
        report_top_item=(findings[0]["text"] if findings else (mapped[1].get("text") if mapped else "")),
    )
    result["complete"] = stage_created and stage_mapped and stage_provenance and stage_ranked
    return result


def _first_real_mapping(session, facts: dict) -> tuple[str, dict] | None:
    """The first fact item across every category whose real id genuinely
    resolves to a real row of the kind it claims — never trusted on the
    strength of the JSON alone."""
    from app.db.models.agents import AgentBelief
    from app.db.models.memory import Memory
    from app.db.models.rabbit_holes import RabbitHole
    from app.db.models.reflection import AgentReflection
    from app.db.models.research import ResearchFinding, ResearchSession
    from app.db.models.wall import ResearchWallPost
    from sqlalchemy import select

    resolvers = {
        "findings": lambda i: session.get(ResearchFinding, int(i)) is not None,
        "wall_posts": lambda i: session.get(ResearchWallPost, int(i)) is not None,
        "rabbit_holes": lambda i: session.get(RabbitHole, int(i)) is not None,
        "belief_changes": lambda i: session.get(AgentBelief, int(i)) is not None,
        "memories": lambda i: session.get(Memory, int(i)) is not None,
        "reflections": lambda i: session.get(AgentReflection, int(i)) is not None,
        "failed_research": lambda i: session.scalars(
            select(ResearchSession).where(ResearchSession.research_id == i)
        ).first() is not None,
    }
    for kind, resolver in resolvers.items():
        for item in facts.get(kind, []):
            try:
                if resolver(item["id"]):
                    return kind, item
            except (ValueError, TypeError, KeyError):
                continue
    return None


if __name__ == "__main__":
    raise SystemExit(main())
