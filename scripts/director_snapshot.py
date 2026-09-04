#!/usr/bin/env python3
"""Director Level 1: read-only structured snapshot of Fishbowl state.

Collects a bounded slice of the live Village database — recent events, agent
actions, open curiosity, memories, conversations, research activity, wall
activity, rabbit holes, and LLM/search-provider telemetry — as one JSON
object a Director model can evaluate.

Hard safety boundary (Level 1 is observation-only):

- The live database path is resolved *only* through
  ``app.core.db_safety.CANONICAL_LIVE_DB_PATH`` — never a hardcoded path,
  never ``DATABASE_URL``.
- Every connection opens SQLite in read-only URI mode (``mode=ro``), which
  errors on a missing file instead of silently creating one.
- ``check_live_db`` runs first and this script raises
  (``app.core.db_safety.LiveDatabaseError``) and refuses to query anything
  if the database is missing or fails its integrity check — the same
  fail-closed contract every other live-DB-touching script in this repo
  follows.
- Nothing here ever executes INSERT/UPDATE/DELETE/DDL, and the read-only URI
  mode makes any attempt to do so fail at the SQLite layer even if a future
  edit tried.

Director bookkeeping (the incremental cursor) lives in ``.director/`` on
disk, never in the Village database itself — see ``.director/cursor.json``
and ``scripts/director_loop.py``, which owns writing it.

Usage::

    .venv/bin/python scripts/director_snapshot.py
    .venv/bin/python scripts/director_snapshot.py --db-path /tmp/fixture.db --since-event-id 0
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.core.db_safety import CANONICAL_LIVE_DB_PATH, LiveDatabaseError, check_live_db  # noqa: E402

#: Action types app/schemas/actions.py describes as doing nothing more than
#: passing a turn — the denominator behind the "passive behavior rate" this
#: Director instance exists to watch. Kept here, not imported from
#: ActionType, so this script has zero dependency on app.schemas beyond this
#: one deliberate, explicit list — a Director observation script should not
#: need the Village's action schema to change shape along with it.
PASSIVE_ACTION_TYPES = frozenset(
    {"DO_NOTHING", "REST", "OBSERVE", "LISTEN_TO_MUSIC", "DRINK_COFFEE"}
)

DEFAULT_MAX_EVENTS = 500
DEFAULT_MAX_ROWS = 50


class DirectorSnapshotError(RuntimeError):
    """The snapshot could not be produced. Always wraps a fail-closed reason."""


def _connect_readonly(path: Path) -> sqlite3.Connection:
    """Open ``path`` strictly read-only. Raises rather than falling back to
    a writable connection if the read-only URI itself can't be opened."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError as exc:
        raise DirectorSnapshotError(f"could not open {path} read-only: {exc}") from exc
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"not JSON serializable: {type(obj)!r}")


def build_snapshot(
    *,
    db_path: Path | None = None,
    since_event_id: int = 0,
    max_events: int = DEFAULT_MAX_EVENTS,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    """Build the bounded, structured snapshot. Read-only; raises
    ``DirectorSnapshotError`` (wrapping ``LiveDatabaseError`` when relevant)
    rather than ever returning a partial result from an unhealthy database."""
    path = db_path if db_path is not None else CANONICAL_LIVE_DB_PATH

    check = check_live_db(path)
    if not check.healthy:
        reason = check.problem or "unknown problem"
        raise DirectorSnapshotError(
            f"Director snapshot refused: live database at {path} is not healthy "
            f"({reason}). Level 1 never queries a database that failed its own "
            "safety check — see app.core.db_safety.check_live_db."
        )

    conn = _connect_readonly(path)
    try:
        clock_row = conn.execute(
            "SELECT current_day, current_period, is_paused, last_advanced_at "
            "FROM simulation_clock WHERE id = 1"
        ).fetchone()
        clock = dict(clock_row) if clock_row else None

        total_new_events = conn.execute(
            "SELECT count(*) FROM events WHERE id > ?", (since_event_id,)
        ).fetchone()[0]
        events = _rows(
            conn,
            "SELECT id, event_type, agent_id, payload, sim_day, sim_period, "
            "entity_type, entity_id, correlation_id, causation_id, created_at "
            "FROM events WHERE id > ? ORDER BY id ASC LIMIT ?",
            (since_event_id, max_events),
        )
        for e in events:
            if e["payload"]:
                e["payload"] = json.loads(e["payload"])
        through_event_id = events[-1]["id"] if events else since_event_id
        truncated = total_new_events > len(events)

        event_type_counts = Counter(e["event_type"] for e in events)

        action_type_counts: Counter[str] = Counter()
        agent_actions: list[dict[str, Any]] = []
        for e in events:
            if e["event_type"] != "AGENT_ACTED":
                continue
            payload = e["payload"] or {}
            actions = payload.get("actions") or []
            action_type_counts.update(actions)
            agent_actions.append(
                {
                    "event_id": e["id"],
                    "agent_id": e["agent_id"],
                    "sim_day": e["sim_day"],
                    "sim_period": e["sim_period"],
                    "actions": actions,
                    "activity": payload.get("activity"),
                    "research_id": payload.get("research_id"),
                    "is_fixture": payload.get("is_fixture"),
                }
            )
        total_actions = sum(action_type_counts.values())
        passive_actions = sum(
            n for action, n in action_type_counts.items() if action in PASSIVE_ACTION_TYPES
        )
        passive_action_rate = (passive_actions / total_actions) if total_actions else None

        open_agent_questions = _rows(
            conn,
            "SELECT id, agent_id, question, status, salience, last_engaged_sim_day, "
            "research_session_id, rabbit_hole_id, created_at "
            "FROM agent_questions WHERE status IN ('OPEN', 'RESEARCHING') "
            "ORDER BY salience DESC, id DESC LIMIT ?",
            (max_rows,),
        )

        recent_memories = _rows(
            conn,
            "SELECT id, agent_id, memory_type, content, importance, confidence, "
            "created_sim_day, reinforcement_count, decay_score, created_at "
            "FROM memories ORDER BY id DESC LIMIT ?",
            (max_rows,),
        )

        recent_conversations = _rows(
            conn,
            "SELECT id, trigger_type, participant_ids, status, location, "
            "current_subject, initiating_reason, ending_reason, started_sim_day, "
            "started_sim_period, started_at, ended_at "
            "FROM conversations ORDER BY id DESC LIMIT ?",
            (max_rows,),
        )
        for c in recent_conversations:
            if c["participant_ids"]:
                c["participant_ids"] = json.loads(c["participant_ids"])

        recent_conversation_messages = _rows(
            conn,
            "SELECT id, conversation_id, agent_id, content, turn_number, created_at "
            "FROM conversation_messages ORDER BY id DESC LIMIT ?",
            (max_rows,),
        )

        recent_research_sessions = _rows(
            conn,
            "SELECT research_id, agent_id, question, status, evidence_strength, "
            "confidence, is_fixture, timestamp, created_at "
            "FROM research_sessions ORDER BY id DESC LIMIT ?",
            (max_rows,),
        )

        recent_research_findings = _rows(
            conn,
            "SELECT id, research_session_id, finding_text, classification, created_at "
            "FROM research_findings ORDER BY id DESC LIMIT ?",
            (max_rows,),
        )

        research_wall_activity = _rows(
            conn,
            "SELECT id, agent_id, post_type, content, related_research_id, "
            "related_wall_post_id, related_rabbit_hole_id, created_at "
            "FROM research_wall ORDER BY id DESC LIMIT ?",
            (max_rows,),
        )

        rabbit_holes = _rows(
            conn,
            "SELECT id, title, originating_agent_id, status, evidence_strength, "
            "activity_level, last_activity, last_activity_day, created_at "
            "FROM rabbit_holes ORDER BY id DESC LIMIT ?",
            (max_rows,),
        )

        llm_telemetry = _rows(
            conn,
            "SELECT purpose, provider, model, is_fixture, count(*) AS calls, "
            "sum(input_tokens) AS input_tokens, sum(output_tokens) AS output_tokens, "
            "sum(estimated_cost_usd) AS estimated_cost_usd "
            "FROM llm_runs GROUP BY purpose, provider, model, is_fixture "
            "ORDER BY calls DESC LIMIT ?",
            (max_rows,),
        )

        search_provider_usage = _rows(
            conn,
            "SELECT provider, is_fixture, count(*) AS sessions, "
            "sum(queries_executed) AS queries_executed, "
            "sum(sources_fetched) AS sources_fetched, sum(fetch_failures) AS fetch_failures, "
            "sum(CASE WHEN failed THEN 1 ELSE 0 END) AS failed_sessions "
            "FROM research_provider_usage GROUP BY provider, is_fixture "
            "ORDER BY sessions DESC LIMIT ?",
            (max_rows,),
        )
    finally:
        conn.close()

    return {
        "director_snapshot_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live_db_path": str(path),
        "live_db_check": {
            "size_bytes": check.size_bytes,
            "table_count": check.table_count,
            "integrity_ok": check.integrity_ok,
        },
        "window": {
            "since_event_id": since_event_id,
            "through_event_id": through_event_id,
            "events_returned": len(events),
            "events_available_beyond_window": truncated,
            "max_events": max_events,
            "max_rows_per_table": max_rows,
        },
        "simulation_clock": clock,
        "event_type_counts": dict(event_type_counts),
        "recent_events": events,
        "agent_actions": {
            "recent": agent_actions,
            "action_type_counts": dict(action_type_counts),
            "total_actions": total_actions,
            "passive_action_types": sorted(PASSIVE_ACTION_TYPES),
            "passive_action_count": passive_actions,
            "passive_action_rate": passive_action_rate,
        },
        "open_agent_questions": open_agent_questions,
        "recent_memories": recent_memories,
        "recent_conversations": recent_conversations,
        "recent_conversation_messages": recent_conversation_messages,
        "recent_research_sessions": recent_research_sessions,
        "recent_research_findings": recent_research_findings,
        "research_wall_activity": research_wall_activity,
        "rabbit_holes": rabbit_holes,
        "llm_telemetry": llm_telemetry,
        "search_provider_usage": search_provider_usage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="override the DB path (default: app.core.db_safety.CANONICAL_LIVE_DB_PATH). "
        "Only ever pass a disposable/fixture path here for testing — the live path "
        "is the safe default precisely so a normal invocation can't be pointed elsewhere.",
    )
    parser.add_argument("--since-event-id", type=int, default=0)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    args = parser.parse_args()

    try:
        snapshot = build_snapshot(
            db_path=args.db_path,
            since_event_id=args.since_event_id,
            max_events=args.max_events,
            max_rows=args.max_rows,
        )
    except (DirectorSnapshotError, LiveDatabaseError) as exc:
        print(f"director_snapshot: FAILED CLOSED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(snapshot, indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
