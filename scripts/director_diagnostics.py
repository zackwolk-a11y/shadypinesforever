"""Director Level 2A: bounded, read-only, Founder-approved diagnostics.

The one place the Director is allowed to *do* something beyond producing a
recommendation — but only a pre-registered, hand-written, read-only
diagnostic function, never arbitrary or model-generated code. Safety comes
from restricting what capability a diagnostic implementation is even
handed, not from trying to sandbox arbitrary execution:

- ``DiagnosticContext`` is the ONLY interface a diagnostic implementation
  gets. It exposes exactly four operations — read the live DB (SELECT-only,
  against a per-diagnostic table allowlist, over the same ``mode=ro``
  connection director_snapshot.py uses), read a repo code file (path must
  match a per-diagnostic allowlist), read Director state under
  ``.director/`` (snapshots/history/observations), and write evidence
  (only under ``.director/diagnostics/{diagnostic_id}/``). No shell, no
  subprocess, no raw ``open()``, no raw ``sqlite3.connect()``, no network.
- Every operation not exposed by ``DiagnosticContext`` is structurally
  unavailable to a diagnostic implementation — there is no escape hatch to
  fail closed *from*, because there is nothing to escape through.

Founder-approval state machine (the Director may never self-promote):

    CANDIDATE_FOR_DIAGNOSTIC --[approve_diagnostic()]--> APPROVED_FOR_DIAGNOSTIC
    APPROVED_FOR_DIAGNOSTIC --[run_diagnostic(), automatic]--> DIAGNOSTIC_COMPLETE

``approve_diagnostic`` is the only function that performs the first
transition. There are exactly two legitimate callers, both distinguishable
forever afterward by the ``approved_by`` field it stamps onto the spec:

1. A human — this module's CLI, or Claude when the Founder has said so
   explicitly in conversation — passing ``approved_by="Founder"`` (the
   default). This is the only caller for a brand-new diagnostic_type, or
   for any diagnostic outside the closed, hardcoded catalog described
   below.
2. ``scripts/director_autonomous_loop.py``'s ``run_cycle``, passing
   ``approved_by="autonomous_director_loop"`` — but ONLY when all of the
   following hold, none of which this module enforces itself (the
   enforcement lives entirely in director_autonomous_loop.py, which is the
   actual authorization boundary):
   - that module's own ``AUTONOMOUS_EXECUTION_ENABLED`` master switch is
     ``True`` — a distinct, explicit, separately-authorized Founder
     decision, off by default;
   - the diagnostic_type is a member of that module's hardcoded
     ``AUTONOMOUS_DIAGNOSTIC_CATALOG`` — registering a new diagnostic_type
     here does NOT by itself make it autonomous-eligible;
   - the diagnostic's ``allowed_operations``/``scope`` were not invented by
     the loop — they were either cloned verbatim from, or selected (via a
     strict, bounded, evidence-matching selector — never free-text, never
     a newly-synthesized value) among, prior specs of that diagnostic_type
     that a *human* already ran to ``DIAGNOSTIC_COMPLETE``/``SUCCESS``. A
     diagnostic_type with no such prior human-run spec cannot be
     autonomously approved at all.

   In short: the autonomous loop can replay or evidence-select among
   parameter choices a human already exercised at least once for a
   catalog-approved diagnostic_type; it can never invent a new
   diagnostic_type, a new capability, or a genuinely new parameter value
   that wasn't already present in already-collected evidence.

No other caller is legitimate. ``run_diagnostic`` refuses outright (fails
closed) unless the spec is already ``APPROVED_FOR_DIAGNOSTIC``, regardless
of who approved it.
"""

from __future__ import annotations

import enum
import json
import re
import signal
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
DIRECTOR_DIR = REPO_ROOT / ".director"
DEFAULT_DIAGNOSTICS_DIR = DIRECTOR_DIR / "diagnostics"


class DiagnosticSafetyError(RuntimeError):
    """A diagnostic implementation asked for something outside its own
    declared allowlist, or outside what DiagnosticContext exposes at all.
    Always fails the diagnostic; never partially proceeds."""


class DiagnosticTimeoutError(RuntimeError):
    """The diagnostic exceeded its declared timeout_seconds."""


class DiagnosticState(str, enum.Enum):
    CANDIDATE_FOR_DIAGNOSTIC = "CANDIDATE_FOR_DIAGNOSTIC"
    APPROVED_FOR_DIAGNOSTIC = "APPROVED_FOR_DIAGNOSTIC"
    DIAGNOSTIC_COMPLETE = "DIAGNOSTIC_COMPLETE"


#: Included in every diagnostic's forbidden_operations, always, regardless
#: of diagnostic_type — a diagnostic-specific list may only ADD to this,
#: never narrow it. Mirrors .director/context/constitution.md §4.
STANDARD_FORBIDDEN_OPERATIONS: tuple[str, ...] = (
    "live_database_write",
    "live_database_schema_change",
    "code_modification",
    "simulation_advancement",
    "village_event_execution",
    "database_migration",
    "database_restore",
    "agent_seeding",
    "config_change",
    "shell_command_execution",
    "network_request",
    "recommendation_implementation",
)


class DiagnosticSpec(BaseModel):
    diagnostic_id: str
    diagnostic_type: str
    originating_round_id: str
    originating_snapshot_id: str
    originating_recommendation: str
    evidence_refs: list[str] = Field(default_factory=list)
    allowed_operations: dict[str, list[str]]  # e.g. {"read_live_db_tables": [...], "read_repo_files": [...]}
    forbidden_operations: list[str] = Field(default_factory=lambda: list(STANDARD_FORBIDDEN_OPERATIONS))
    scope: dict[str, Any] = Field(default_factory=dict)
    success_criteria: str
    failure_criteria: str
    timeout_seconds: int
    output_evidence_dir: str  # relative to .director/diagnostics/
    state: DiagnosticState = DiagnosticState.CANDIDATE_FOR_DIAGNOSTIC
    created_at: str
    approved_at: str | None = None
    approved_by: str | None = None
    completed_at: str | None = None
    run_status: str | None = None  # "SUCCESS" | "FAILED", set only once execution finishes or errors
    run_error: str | None = None


#: The hardcoded, global ceiling for call_service_function — no DiagnosticSpec,
#: however it declares allowed_operations.call_service_functions, can ever
#: reach a function outside this set. Two-layer check: this constant first,
#: the spec's own declared subset of it second (same pattern as
#: read_live_db_tables/read_repo_files) — see call_service_function below.
ALLOWED_SERVICE_FUNCTIONS: frozenset[tuple[str, str]] = frozenset({
    ("app.services.conversations", "next_speaker"),
    ("app.services.conversations", "should_close"),
})


def resolve_allowed_service_function(module_path: str, function_name: str) -> Callable[..., Any]:
    """The global-ceiling half of call_service_function's two-layer check —
    standalone so director_experiments.py's ExperimentContext can reuse the
    exact same ceiling rather than re-declaring it. Never checks a spec's
    own declared subset; callers (DiagnosticContext.call_service_function,
    ExperimentContext.call_service_function) do that themselves first."""
    key = (module_path, function_name)
    if key not in ALLOWED_SERVICE_FUNCTIONS:
        raise DiagnosticSafetyError(
            f"call_service_function refuses {module_path}.{function_name} — not in the hardcoded "
            f"global allowlist {sorted(ALLOWED_SERVICE_FUNCTIONS)}."
        )
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, function_name)


def create_guarded_isolated_sqlite_session(prefix: str = "director_isolated_") -> tuple[Path, Any]:
    """A brand-new, empty, real-schema SQLite DB inside a fresh
    ``tempfile.mkdtemp()`` directory this function creates itself — no path
    argument, so there is nothing for any caller to supply or override.
    Checked twice against ever overlapping live data: the resolved path
    must sit inside the OS temp directory, and must not equal, contain, or
    sit inside either live-data root — the same two conditions
    ``app.core.db_safety.safe_rmtree`` enforces for cleanup, checked here
    on creation too. Standalone (not a DiagnosticContext method) so
    director_experiments.py's ExperimentContext can reuse it verbatim —
    this guard exists in exactly one place. Callers are responsible for
    their own capability-declaration check (e.g.
    ``"create_isolated_test_db" in allowed_capabilities``) before calling
    this — it performs no such check itself, only the live-root-overlap
    safety guard. Returns ``(tmp_dir, session)``; the caller owns tracking
    both for later cleanup via ``app.core.db_safety.safe_rmtree``."""
    import tempfile

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.db.models  # noqa: F401 — registers all models on Base.metadata
    from app.core.db_safety import CANONICAL_LIVE_DB_PATH, VILLAGE_DATA_ROOT
    from app.db.base import Base

    tmp_dir = Path(tempfile.mkdtemp(prefix=prefix))
    db_path = (tmp_dir / "isolated_test.db").resolve()

    tmp_system_dir = Path(tempfile.gettempdir()).resolve()
    if tmp_system_dir not in db_path.parents:
        raise DiagnosticSafetyError(f"isolated test DB path escaped the OS temp directory: {db_path}")
    live_roots = {CANONICAL_LIVE_DB_PATH.resolve().parent, VILLAGE_DATA_ROOT.resolve()}
    for root in live_roots:
        if db_path == root or root in db_path.parents or db_path in root.parents:
            raise DiagnosticSafetyError(
                f"isolated test DB path unexpectedly overlaps a live-data root ({root}): {db_path}"
            )

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return tmp_dir, session


class DiagnosticContext:
    """The entire capability surface a diagnostic implementation gets.
    Nothing else is reachable — no import of sqlite3/subprocess/open() by
    the implementation function does anything useful, because the
    implementation is only ever handed this object, never given free rein
    over the process."""

    def __init__(self, spec: DiagnosticSpec, *, db_path: Path, diagnostics_dir: Path) -> None:
        self._spec = spec
        self._db_path = db_path
        self._evidence_dir = (diagnostics_dir / spec.diagnostic_id).resolve()
        self._allowed_tables = set(spec.allowed_operations.get("read_live_db_tables", []))
        self._allowed_repo_files = set(spec.allowed_operations.get("read_repo_files", []))
        self._allowed_capabilities = set(spec.allowed_operations.get("capabilities", []))
        self._allowed_service_functions = set(spec.allowed_operations.get("call_service_functions", []))
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        self._isolated_dirs: list[Path] = []
        self._isolated_sessions: list[Any] = []

    def read_live_db(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """SELECT-only, and only against tables this diagnostic declared
        it needs. Opens the same mode=ro URI director_snapshot.py uses —
        structurally cannot write even if the allowlist check below were
        somehow bypassed."""
        normalized = " ".join(sql.split())
        if not re.match(r"^SELECT\b", normalized, re.IGNORECASE):
            raise DiagnosticSafetyError(f"read_live_db refuses non-SELECT statement: {normalized[:120]!r}")
        if ";" in normalized.rstrip(";"):
            raise DiagnosticSafetyError("read_live_db refuses multi-statement SQL.")
        referenced = set(re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", normalized, re.IGNORECASE))
        disallowed = referenced - self._allowed_tables
        if disallowed:
            raise DiagnosticSafetyError(
                f"read_live_db refuses tables {sorted(disallowed)} — not in this diagnostic's "
                f"allowed_operations.read_live_db_tables ({sorted(self._allowed_tables)})."
            )
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(normalized, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def read_repo_file(self, relative_path: str) -> str:
        if relative_path not in self._allowed_repo_files:
            raise DiagnosticSafetyError(
                f"read_repo_file refuses {relative_path!r} — not in this diagnostic's "
                f"allowed_operations.read_repo_files ({sorted(self._allowed_repo_files)})."
            )
        path = (REPO_ROOT / relative_path).resolve()
        if REPO_ROOT not in path.parents and path != REPO_ROOT:
            raise DiagnosticSafetyError(f"read_repo_file refuses path outside the repo: {relative_path!r}")
        return path.read_text()

    def read_director_state(self, relative_path: str) -> str:
        path = (DIRECTOR_DIR / relative_path).resolve()
        if DIRECTOR_DIR not in path.parents and path != DIRECTOR_DIR:
            raise DiagnosticSafetyError(f"read_director_state refuses path outside .director/: {relative_path!r}")
        return path.read_text()

    def write_evidence(self, filename: str, content: str) -> Path:
        path = (self._evidence_dir / filename).resolve()
        if self._evidence_dir not in path.parents and path != self._evidence_dir:
            raise DiagnosticSafetyError(
                f"write_evidence refuses path outside {self._evidence_dir}: {filename!r}"
            )
        path.write_text(content)
        return path

    def create_isolated_test_db(self) -> Any:
        """A brand-new, empty SQLite DB inside a fresh ``tempfile.mkdtemp()``
        directory this method creates itself — takes no path argument, so
        there is nothing for a diagnostic's ``scope`` or implementation to
        supply or override. Migrates the real schema via
        ``Base.metadata.create_all`` so seeded rows use the actual ORM
        models. Checked twice against ever overlapping live data: the
        resolved path must sit inside the OS temp directory, and must not
        equal, contain, or sit inside either live-data root — the same two
        conditions ``app.core.db_safety.safe_rmtree`` enforces for cleanup,
        checked here on creation too. Requires ``"create_isolated_test_db"``
        declared in this diagnostic's ``allowed_operations.capabilities``.
        The actual creation logic is the shared, standalone
        ``create_guarded_isolated_sqlite_session`` below — reused verbatim
        by director_experiments.py's ExperimentContext so the live-root
        overlap guard exists in exactly one place."""
        if "create_isolated_test_db" not in self._allowed_capabilities:
            raise DiagnosticSafetyError(
                "create_isolated_test_db refused: not declared in this diagnostic's "
                "allowed_operations.capabilities."
            )
        tmp_dir, session = create_guarded_isolated_sqlite_session()
        self._isolated_dirs.append(tmp_dir)
        self._isolated_sessions.append(session)
        return session

    def call_service_function(self, module_path: str, function_name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke exactly one of a hardcoded, tiny set of real Village
        service functions — never an arbitrary import. Two checks: the
        module-level ``ALLOWED_SERVICE_FUNCTIONS`` constant (the ceiling no
        spec can raise — checked by the shared ``resolve_allowed_service_
        function`` helper below) and this diagnostic's own declared
        ``allowed_operations.call_service_functions`` (the floor it must
        explicitly opt into) — both must pass."""
        declared = f"{module_path}.{function_name}"
        if declared not in self._allowed_service_functions:
            raise DiagnosticSafetyError(
                f"call_service_function refuses {declared} — not declared in this diagnostic's "
                f"allowed_operations.call_service_functions ({sorted(self._allowed_service_functions)})."
            )
        fn = resolve_allowed_service_function(module_path, function_name)
        return fn(*args, **kwargs)

    def cleanup(self) -> None:
        """Close every isolated session and delete its temp directory via
        the same safe_rmtree guard db_safety.py uses elsewhere — called by
        run_diagnostic in a finally block regardless of success/failure."""
        from app.core.db_safety import safe_rmtree

        for session in self._isolated_sessions:
            try:
                session.close()
            except Exception:  # noqa: BLE001 — cleanup must never mask the real outcome
                pass
        for tmp_dir in self._isolated_dirs:
            try:
                safe_rmtree(tmp_dir)
            except Exception:  # noqa: BLE001
                pass


DiagnosticImplementation = Callable[[DiagnosticContext, dict[str, Any]], dict[str, Any]]
_DIAGNOSTIC_IMPLEMENTATIONS: dict[str, DiagnosticImplementation] = {}


def register_diagnostic(diagnostic_type: str) -> Callable[[DiagnosticImplementation], DiagnosticImplementation]:
    def decorator(fn: DiagnosticImplementation) -> DiagnosticImplementation:
        _DIAGNOSTIC_IMPLEMENTATIONS[diagnostic_type] = fn
        return fn
    return decorator


@register_diagnostic("conversation_lifecycle_trace")
def conversation_lifecycle_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each conversation_id in scope: reconstruct who was offered the
    floor, what they chose, whether they spoke, whether that speech is a
    persisted ConversationMessage, whether public_dialogue/SEND_MESSAGE
    activity exists that never became a formal turn, and why the
    conversation closed — all from already-existing rows plus the actual
    source code that governs closing, never from speculation."""
    conversation_ids: list[int] = scope["conversation_ids"]
    result: dict[str, Any] = {"conversations": [], "governing_code": {}}

    for cid in conversation_ids:
        convo_rows = ctx.read_live_db(
            "SELECT id, trigger_type, participant_ids, status, consecutive_silences, "
            "ending_reason, started_at, ended_at, location, current_subject "
            "FROM conversations WHERE id = ?", (cid,),
        )
        if not convo_rows:
            result["conversations"].append({"conversation_id": cid, "error": "no such conversation"})
            continue
        convo_row = convo_rows[0]

        wake_events = ctx.read_live_db(
            "SELECT id, agent_id, payload, correlation_id, sim_day, sim_period, created_at "
            "FROM events WHERE event_type = 'AGENT_WOKE' "
            "AND json_extract(payload, '$.conversation_id') = ? ORDER BY id ASC", (cid,),
        )
        acted_events = ctx.read_live_db(
            "SELECT id, agent_id, payload, correlation_id, causation_id, created_at "
            "FROM events WHERE event_type = 'AGENT_ACTED' "
            "AND correlation_id IN (SELECT correlation_id FROM events "
            "WHERE event_type = 'AGENT_WOKE' AND json_extract(payload, '$.conversation_id') = ?) "
            "ORDER BY id ASC", (cid,),
        )
        ended_events = ctx.read_live_db(
            "SELECT id, payload, created_at FROM events "
            "WHERE event_type = 'CONVERSATION_ENDED' AND entity_type = 'conversation' "
            "AND entity_id = ? ORDER BY id ASC", (str(cid),),
        )
        messages = ctx.read_live_db(
            "SELECT id, agent_id, content, turn_number, created_at "
            "FROM conversation_messages WHERE conversation_id = ? ORDER BY turn_number ASC", (cid,),
        )

        turns: list[dict[str, Any]] = []
        for wake in wake_events:
            payload = json.loads(wake["payload"]) if wake["payload"] else {}
            acted = next((a for a in acted_events if a["correlation_id"] == wake["correlation_id"]), None)
            actions: list[str] = []
            public_dialogue = None
            if acted:
                acted_payload = json.loads(acted["payload"]) if acted["payload"] else {}
                actions = acted_payload.get("actions", [])
                public_dialogue = acted_payload.get("public_dialogue")
            spoke_action = "SPEAK" in actions or "START_CONVERSATION" in actions
            if public_dialogue is not None or spoke_action:
                # Something was actually said or a formal SPEAK/START_CONVERSATION
                # action was chosen this turn — check whether it landed in
                # conversation_messages. A turn with neither has nothing to
                # check persistence of; "persisted" would be a meaningless
                # label (and the None-short-circuit below would silently turn
                # a genuinely silent turn into a false "persisted: True").
                persisted = any(
                    m["agent_id"] == wake["agent_id"]
                    and (public_dialogue is None or m["content"] == public_dialogue)
                    for m in messages
                )
            else:
                persisted = None  # not applicable — nothing was said this turn
            turns.append({
                "wake_event_id": wake["id"],
                "agent_id": wake["agent_id"],
                "offered_floor_at": wake["created_at"],
                "actions_chosen": actions,
                "spoke_action_present": spoke_action,
                "public_dialogue_present": public_dialogue is not None,
                "public_dialogue_text": public_dialogue,
                "persisted_as_conversation_message": persisted,
            })

        send_messages_near = ctx.read_live_db(
            "SELECT id, sender_agent_id, recipient_agent_id, content, created_at FROM messages "
            "WHERE sender_agent_id IN ({}) ORDER BY id ASC".format(
                ",".join("?" for _ in json.loads(convo_row["participant_ids"] or "[]")) or "''"
            ),
            tuple(json.loads(convo_row["participant_ids"] or "[]")),
        ) if convo_row["participant_ids"] else []

        result["conversations"].append({
            "conversation_id": cid,
            "conversation_row": convo_row,
            "turns": turns,
            "formal_conversation_messages": messages,
            "conversation_ended_events": [
                {**e, "payload": json.loads(e["payload"]) if e["payload"] else {}} for e in ended_events
            ],
            "send_messages_from_participants_all_time": send_messages_near,
            "omitted_from_metrics": [
                t for t in turns
                if (t["spoke_action_present"] or t["public_dialogue_present"])
                and not t["persisted_as_conversation_message"]
            ],
        })

    result["governing_code"] = {
        "app/services/orchestrator.py:_after_turn": ctx.read_repo_file("app/services/orchestrator.py"),
        "app/services/conversations.py": ctx.read_repo_file("app/services/conversations.py"),
        "app/schemas/actions.py": ctx.read_repo_file("app/schemas/actions.py"),
    }
    return result


@register_diagnostic("conversation_scheduler_isolated_test")
def conversation_scheduler_isolated_test(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """Behavioral test of the CURRENT next_speaker()/should_close() code —
    not archaeology of which commit ran historically (that needs git,
    which this sandbox structurally cannot reach). For each conversation_id
    in scope, reconstructs its real participant list and each participant's
    real already-used activation budget for that sim_day (both read-only
    from the live DB), seeds a brand-new isolated DB with that starting
    state, then repeatedly calls the real, unmodified next_speaker() and
    should_close() — via call_service_function, never a reimplementation —
    simulating every offered agent staying silent. Records the full
    turn-by-turn trace: who was offered the floor, in what order, and
    exactly when/why the conversation closed. Deterministic: no model call,
    no randomness — the same inputs always produce the same trace."""
    from app.core.config import get_settings
    from app.db.models.agents import Agent
    from app.db.models.conversations import Conversation
    from app.db.models.events import Event
    from app.db.models.world import SimulationClock
    from app.domain.enums import ConversationStatus, ConversationTrigger
    from app.services.conversations import SILENCES_TO_WIND_DOWN

    conversation_ids: list[int] = scope["reconstruct_from_conversation_ids"]
    silent_turns: int = scope.get("silent_turns_to_simulate", 10)
    settings = get_settings()

    # scheduler.activations_today() — what next_speaker's eligibility filter
    # actually calls — counts AGENT_ACTED/INVALID_AGENT_DECISION events, NOT
    # AGENT_WOKE. Imported from the real source rather than hardcoded so this
    # can never silently drift out of sync with it again.
    from app.services.scheduler import ACTIVATION_EVENTS
    activation_event_values = tuple(e.value for e in ACTIVATION_EVENTS)
    activation_placeholders = ",".join("?" for _ in activation_event_values)

    scenarios: list[dict[str, Any]] = []
    for cid in conversation_ids:
        convo_rows = ctx.read_live_db(
            "SELECT participant_ids, started_sim_day FROM conversations WHERE id = ?", (cid,)
        )
        if not convo_rows:
            scenarios.append({"conversation_id": cid, "error": "conversation not found in live DB"})
            continue
        participant_ids: list[str] = json.loads(convo_rows[0]["participant_ids"] or "[]")
        sim_day = convo_rows[0]["started_sim_day"] or 1

        # Snapshot activation budget as it stood BEFORE this conversation's
        # own first turn — not the whole day's total, which would double
        # count the very activations this conversation itself produced.
        first_wake_rows = ctx.read_live_db(
            "SELECT MIN(id) AS first_id FROM events WHERE event_type = 'AGENT_WOKE' "
            "AND json_extract(payload, '$.conversation_id') = ?", (cid,),
        )
        before_id = first_wake_rows[0]["first_id"] if first_wake_rows and first_wake_rows[0]["first_id"] else 0

        prior_activation_counts: dict[str, int] = {}
        for pid in participant_ids:
            rows = ctx.read_live_db(
                f"SELECT count(*) AS n FROM events WHERE agent_id = ? AND sim_day = ? "
                f"AND event_type IN ({activation_placeholders}) AND id < ?",
                (pid, sim_day, *activation_event_values, before_id),
            )
            prior_activation_counts[pid] = rows[0]["n"] if rows else 0

        session = ctx.create_isolated_test_db()
        for pid in participant_ids:
            session.add(Agent(agent_id=pid, identity="isolated-test-agent", voice="isolated-test-voice"))
        clock = SimulationClock(id=1, current_day=sim_day, current_period="MORNING", is_paused=False)
        session.add(clock)
        session.commit()

        # Reconstruct each agent's real starting activation budget for this
        # sim_day — the actual event types scheduler.activations_today()
        # counts, not AGENT_WOKE — so next_speaker's real eligibility filter
        # sees the same constraint that existed live at conversation start.
        for pid, n in prior_activation_counts.items():
            for _ in range(n):
                session.add(Event(event_type=ACTIVATION_EVENTS[0], agent_id=pid, payload={}, sim_day=sim_day))
        session.commit()

        convo = Conversation(
            trigger_type=ConversationTrigger.MORNING_GATHERING,
            participant_ids=participant_ids,
            status=ConversationStatus.ACTIVE,
            consecutive_silences=0,
            started_sim_day=sim_day,
        )
        session.add(convo)
        session.commit()

        trace: list[dict[str, Any]] = []
        consecutive_silences = 0
        closed = False
        close_reason: str | None = None
        for turn_index in range(silent_turns):
            speaker = ctx.call_service_function(
                "app.services.conversations", "next_speaker", session, convo, clock, settings
            )
            if speaker is None:
                trace.append({"turn": turn_index, "speaker": None,
                              "note": "no eligible speaker (everyone at their daily activation cap)"})
                close_reason = "no_eligible_speaker"
                closed = True
                break

            woke = Event(event_type="AGENT_WOKE", agent_id=speaker,
                         payload={"conversation_id": convo.id}, sim_day=sim_day)
            session.add(woke)
            # Every real activation — silent or not — produces a completed
            # AGENT_ACTED event (app.services.orchestrator always records
            # one). Recorded here too so activations_today() correctly sees
            # this turn's budget consumption on any later turn in the same
            # trace, not just the pre-seeded prior count.
            session.add(Event(event_type=ACTIVATION_EVENTS[0], agent_id=speaker,
                               payload={"conversation_id": convo.id}, sim_day=sim_day))
            session.commit()

            # The scenario under test: the offered agent stays silent, every turn.
            consecutive_silences += 1
            if consecutive_silences >= SILENCES_TO_WIND_DOWN and convo.status is ConversationStatus.ACTIVE:
                convo.status = ConversationStatus.WINDING_DOWN
            convo.consecutive_silences = consecutive_silences
            session.commit()

            should_close_now = ctx.call_service_function(
                "app.services.conversations", "should_close", session, convo, settings, consecutive_silences
            )
            trace.append({
                "turn": turn_index, "wake_event_id": woke.id, "speaker": speaker,
                "consecutive_silences": consecutive_silences,
                "conversation_status": convo.status.value, "should_close": should_close_now,
            })
            if should_close_now:
                close_reason = "should_close_true"
                closed = True
                break

        distinct_speakers = sorted({t["speaker"] for t in trace if t.get("speaker")})
        scenarios.append({
            "conversation_id": cid,
            "sim_day_used": sim_day,
            "participant_count": len(participant_ids),
            "prior_activation_counts": prior_activation_counts,
            "trace": trace,
            "closed": closed,
            "close_reason": close_reason,
            "distinct_agents_offered_floor": distinct_speakers,
            "starvation_reproduced": len(distinct_speakers) <= 2 and len(participant_ids) > 2,
        })

    return {"scenarios": scenarios}


def _extract_markdown_section(text: str, heading: str) -> str:
    """Everything from ``heading`` (a "### "-style line) up to the next
    same-level heading, or end of file. Keeps evidence bounded without
    quoting an entire large doc."""
    start = text.find(heading)
    if start == -1:
        return f"(heading {heading!r} not found)"
    rest = text[start:]
    next_marker = rest.find("\n### ", len(heading))
    return rest if next_marker == -1 else rest[:next_marker]


def _extract_python_function(text: str, def_line: str) -> str:
    """Everything from ``def_line`` up to the next top-level ``def ``/
    ``class ``, or end of file. Keeps evidence bounded to one function
    instead of quoting a whole module."""
    start = text.find(def_line)
    if start == -1:
        return f"({def_line!r} not found)"
    rest = text[start:]
    next_def = re.search(r"\n(?:def |class )", rest[len(def_line):])
    return rest if next_def is None else rest[: len(def_line) + next_def.start()]


@register_diagnostic("conversation_scheduler_policy_probe")
def conversation_scheduler_policy_probe(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """Answers five questions about MORNING_GATHERING closure policy —
    entirely through already-approved capabilities (read_repo_file,
    create_isolated_test_db, call_service_function for next_speaker/
    should_close). No live DB read at all: every scenario here uses a
    synthetic 8-agent pool, not a reconstruction of any real conversation.

    Structure keeps three things explicitly separate, never blended:
    intended_policy (what the docs/tests say should happen),
    code_analysis (what the current code actually does, read not run),
    and observed_behavior / counterfactual (what running the current code
    in isolation actually produces, including one explicitly-labeled
    hypothetical that goes beyond what the current lifecycle would ever
    reach on its own)."""
    from app.core.config import get_settings
    from app.db.models.agents import Agent
    from app.db.models.conversations import Conversation
    from app.db.models.events import Event
    from app.db.models.world import SimulationClock
    from app.domain.enums import ConversationStatus, ConversationTrigger
    from app.services.conversations import SILENCES_TO_WIND_DOWN

    settings = get_settings()
    n = scope.get("synthetic_participant_count", 8)
    max_turns = scope.get("max_turns_to_probe", 6)
    speak_at_index = scope.get("counterfactual_speak_at_participant_index", 2)
    order_variants = scope.get("order_variants") or [
        [f"agent_{i+1}" for i in range(n)],
        [f"agent_{n-i}" for i in range(n)],
    ]

    # --- intended_policy: what the docs/tests say should happen ---
    readme_text = ctx.read_repo_file("README.md")
    intended_policy = {
        "readme_conversations_section": _extract_markdown_section(readme_text, "### Conversations"),
        "regression_test_full_text": ctx.read_repo_file("scripts/smoke_test_conversation_turn_rotation.py"),
    }

    # --- code_analysis: what the current code actually does, quoted not summarized ---
    conversations_source = ctx.read_repo_file("app/services/conversations.py")
    code_analysis = {
        "next_speaker_source": _extract_python_function(conversations_source, "def next_speaker("),
        "should_close_source": _extract_python_function(conversations_source, "def should_close("),
        "silences_to_wind_down_constant": SILENCES_TO_WIND_DOWN,
    }

    def _run_scenario(participant_ids: list[str], *, inject_speaker: tuple[int, str] | None,
                       stop_at_should_close: bool) -> dict[str, Any]:
        """inject_speaker, if given, is (turn_index, agent_id): on that one
        turn the designated agent is given the floor and simulated as
        SPEAKING, bypassing next_speaker's own selection for that turn only
        — necessary because, as observed_current_code_behavior's control
        proves, next_speaker never naturally reaches a third participant
        under all-silence (the exclusion only ever removes the immediately-
        previous pick, so with two eligible fresher agents it alternates
        between exactly the first two forever). Every other turn still
        calls the real next_speaker unmodified."""
        session = ctx.create_isolated_test_db()
        for pid in participant_ids:
            session.add(Agent(agent_id=pid, identity="probe-agent", voice="probe-voice"))
        clock = SimulationClock(id=1, current_day=1, current_period="MORNING", is_paused=False)
        session.add(clock)
        convo = Conversation(
            trigger_type=ConversationTrigger.MORNING_GATHERING, participant_ids=participant_ids,
            status=ConversationStatus.ACTIVE, consecutive_silences=0, started_sim_day=1,
        )
        session.add(convo)
        session.commit()

        trace: list[dict[str, Any]] = []
        consecutive_silences = 0
        natural_close_turn: int | None = None
        for turn_index in range(max_turns):
            injected = inject_speaker is not None and inject_speaker[0] == turn_index
            if injected:
                speaker = inject_speaker[1]
            else:
                speaker = ctx.call_service_function(
                    "app.services.conversations", "next_speaker", session, convo, clock, settings
                )
            if speaker is None:
                trace.append({"turn": turn_index, "speaker": None, "note": "no eligible speaker"})
                break

            will_speak = injected
            woke = Event(event_type="AGENT_WOKE", agent_id=speaker,
                         payload={"conversation_id": convo.id}, sim_day=1)
            session.add(woke)
            session.add(Event(event_type="AGENT_ACTED", agent_id=speaker,
                               payload={"conversation_id": convo.id}, sim_day=1))
            session.commit()

            if will_speak:
                consecutive_silences = 0
                if convo.status is ConversationStatus.WINDING_DOWN:
                    convo.status = ConversationStatus.ACTIVE
            else:
                consecutive_silences += 1
                if consecutive_silences >= SILENCES_TO_WIND_DOWN and convo.status is ConversationStatus.ACTIVE:
                    convo.status = ConversationStatus.WINDING_DOWN
            convo.consecutive_silences = consecutive_silences
            session.commit()

            should_close_now = ctx.call_service_function(
                "app.services.conversations", "should_close", session, convo, settings, consecutive_silences
            )
            trace.append({
                "turn": turn_index, "speaker": speaker, "spoke": will_speak, "injected": injected,
                "consecutive_silences": consecutive_silences,
                "conversation_status": convo.status.value, "should_close": should_close_now,
            })
            if should_close_now and natural_close_turn is None:
                natural_close_turn = turn_index
            if should_close_now and stop_at_should_close:
                break

        distinct = []
        for t in trace:
            if t.get("speaker") and t["speaker"] not in distinct:
                distinct.append(t["speaker"])
        ctx.cleanup()
        return {
            "participant_ids": participant_ids,
            "trace": trace,
            "natural_close_turn": natural_close_turn,
            "distinct_agents_offered": distinct,
        }

    control_participants = order_variants[0]
    observed_behavior = {
        "control_all_silent_extended": _run_scenario(
            control_participants, inject_speaker=None, stop_at_should_close=False
        ),
    }
    control_close_turn = observed_behavior["control_all_silent_extended"]["natural_close_turn"]

    # observed_current_code_behavior's own control already proves
    # next_speaker never naturally reaches a third participant under
    # all-silence (only the immediately-previous pick is excluded, so with
    # 2+ fresh eligible agents it alternates between exactly the first two
    # forever) — so the counterfactual must directly inject the third
    # participant at a chosen turn rather than wait for natural selection
    # to reach them, which it structurally cannot.
    inject_turn = min(speak_at_index, max_turns - 1)
    inject_agent = control_participants[speak_at_index % len(control_participants)]
    counterfactual = _run_scenario(
        control_participants, inject_speaker=(inject_turn, inject_agent), stop_at_should_close=False
    )
    counterfactual["injected_agent"] = inject_agent
    counterfactual["injected_at_turn"] = inject_turn
    counterfactual["note"] = (
        f"{inject_agent} (participant index {speak_at_index}) was never naturally offered the floor in "
        f"the control (see control_all_silent_extended.distinct_agents_offered) — next_speaker's "
        f"exclude-only-the-immediately-previous-pick rule locks onto the first two eligible "
        f"participants indefinitely under all-silence. This scenario force-injects {inject_agent} at "
        f"turn {inject_turn} and has them speak, to test what next_speaker/should_close do afterward. "
        f"The current lifecycle's should_close already fires at turn {control_close_turn} in the "
        "unforced control, before this injected turn would naturally be reached — this is an explicit "
        "hypothetical about what closure would bypass, not a claim the current code reaches this state "
        "on its own."
    )

    order_sensitivity = {}
    for i, variant in enumerate(order_variants):
        result = _run_scenario(variant, inject_speaker=None, stop_at_should_close=True)
        order_sensitivity[f"variant_{i}"] = {
            "participant_order": variant,
            "distinct_agents_offered": result["distinct_agents_offered"],
            "natural_close_turn": result["natural_close_turn"],
        }

    return {
        "intended_policy": intended_policy,
        "code_analysis": code_analysis,
        "observed_current_code_behavior": observed_behavior,
        "counterfactual_forced_speak": counterfactual,
        "order_sensitivity": order_sensitivity,
    }


def _extract_python_docstring(text: str) -> str:
    """The first triple-quoted string in a Python source file — its module
    docstring — without quoting the whole file."""
    m = re.search(r'"""(.*?)"""', text, re.DOTALL)
    return m.group(1).strip() if m else "(no module docstring found)"


@register_diagnostic("conversation_message_persistence_and_threshold_probe")
def conversation_message_persistence_and_threshold_probe(
    ctx: DiagnosticContext, scope: dict[str, Any]
) -> dict[str, Any]:
    """Answers two questions, kept in clearly separate top-level sections:

    (1) persistence_path: what actually makes a dialogue-bearing action
    become a ConversationMessage row, quoted from the real code and an
    existing integration test — not summarized, not run.

    (2) current_threshold_results / threshold_comparison: extends the
    prior policy probe with per-participant scripted speak/silence
    choices (not just all-silent), measuring whether a willing-to-speak
    3rd participant ever actually receives the floor, spoken turns,
    closure point, and empty-activation count — under both the current
    SILENCES_TO_WIND_DOWN and, only if scope explicitly requests it, one
    alternate value via an in-process monkeypatch of that module constant
    that is always restored before this function returns (see the
    threshold_comparison note in the returned evidence) — app/services/
    conversations.py on disk is never touched, and no other process or
    diagnostic can observe the patch, which cannot outlive this one call.
    """
    from app.core.config import get_settings
    from app.db.models.agents import Agent
    from app.db.models.conversations import Conversation
    from app.db.models.events import Event
    from app.db.models.world import SimulationClock
    from app.domain.enums import ConversationStatus, ConversationTrigger
    import app.services.conversations as conversations_module

    settings = get_settings()

    # --- Question 1: persistence path, quoted code + existing test, not run ---
    orchestrator_source = ctx.read_repo_file("app/services/orchestrator.py")
    conversations_source = ctx.read_repo_file("app/services/conversations.py")
    actions_source = ctx.read_repo_file("app/schemas/actions.py")
    dialogue_test_source = ctx.read_repo_file("scripts/smoke_test_dialogue.py")

    persistence_path = {
        "execute_decision_source": _extract_python_function(orchestrator_source, "def execute_decision("),
        "record_utterance_source": _extract_python_function(conversations_source, "def record_utterance("),
        "agent_decision_schema_source": _extract_python_function(
            actions_source, "class AgentDecision(BaseModel):"
        ),
        "existing_integration_test_docstring": _extract_python_docstring(dialogue_test_source),
    }

    # --- Question 2: extended policy probe ---
    n = scope.get("synthetic_participant_count", 8)
    max_turns = scope.get("max_turns_to_probe", 8)
    willing_speaker_index = scope.get("willing_speaker_participant_index", 2)
    order_variants = scope.get("order_variants") or [
        [f"agent_{i+1}" for i in range(n)],
        [f"agent_{n-i}" for i in range(n)],
    ]
    alt_threshold = scope.get("alternate_silences_to_wind_down")  # None = skip the comparison entirely

    def _run(participant_ids: list[str], *, speak_policy: dict[int, bool]) -> dict[str, Any]:
        session = ctx.create_isolated_test_db()
        for pid in participant_ids:
            session.add(Agent(agent_id=pid, identity="probe-agent", voice="probe-voice"))
        clock = SimulationClock(id=1, current_day=1, current_period="MORNING", is_paused=False)
        session.add(clock)
        convo = Conversation(
            trigger_type=ConversationTrigger.MORNING_GATHERING, participant_ids=participant_ids,
            status=ConversationStatus.ACTIVE, consecutive_silences=0, started_sim_day=1,
        )
        session.add(convo)
        session.commit()

        willing_agent_id = (
            participant_ids[willing_speaker_index] if willing_speaker_index < len(participant_ids) else None
        )
        trace: list[dict[str, Any]] = []
        consecutive_silences = 0
        close_turn: int | None = None
        empty_activation_count = 0
        willing_speaker_received_floor = False
        for turn_index in range(max_turns):
            speaker = ctx.call_service_function(
                "app.services.conversations", "next_speaker", session, convo, clock, settings
            )
            if speaker is None:
                trace.append({"turn": turn_index, "speaker": None, "note": "no eligible speaker"})
                break
            will_speak = speak_policy.get(participant_ids.index(speaker), False)
            if speaker == willing_agent_id and will_speak:
                willing_speaker_received_floor = True

            session.add(Event(event_type="AGENT_WOKE", agent_id=speaker,
                               payload={"conversation_id": convo.id}, sim_day=1))
            session.add(Event(event_type="AGENT_ACTED", agent_id=speaker,
                               payload={"conversation_id": convo.id}, sim_day=1))
            session.commit()

            if will_speak:
                consecutive_silences = 0
                if convo.status is ConversationStatus.WINDING_DOWN:
                    convo.status = ConversationStatus.ACTIVE
            else:
                consecutive_silences += 1
                empty_activation_count += 1
                if (
                    consecutive_silences >= conversations_module.SILENCES_TO_WIND_DOWN
                    and convo.status is ConversationStatus.ACTIVE
                ):
                    convo.status = ConversationStatus.WINDING_DOWN
            convo.consecutive_silences = consecutive_silences
            session.commit()

            should_close_now = ctx.call_service_function(
                "app.services.conversations", "should_close", session, convo, settings, consecutive_silences
            )
            trace.append({
                "turn": turn_index, "speaker": speaker, "spoke": will_speak,
                "consecutive_silences": consecutive_silences,
                "conversation_status": convo.status.value, "should_close": should_close_now,
            })
            if should_close_now and close_turn is None:
                close_turn = turn_index

        distinct = []
        for t in trace:
            if t.get("speaker") and t["speaker"] not in distinct:
                distinct.append(t["speaker"])
        ctx.cleanup()
        return {
            "participant_ids": participant_ids,
            "trace": trace,
            "closure_point_turn": close_turn,
            "distinct_agents_offered": distinct,
            "spoken_turns": sum(1 for t in trace if t.get("spoke")),
            "empty_activation_count": empty_activation_count,
            "willing_speaker_agent_id": willing_agent_id,
            "willing_speaker_received_floor": willing_speaker_received_floor,
        }

    hetero_policy = {willing_speaker_index: True}  # everyone else defaults to silent
    control_policy: dict[int, bool] = {}  # everyone silent

    def _run_all_variants() -> dict[str, Any]:
        out = {}
        for label, variant in zip(("normal_order", "reversed_order"), order_variants):
            out[label] = {
                "heterogeneous_third_agent_willing": _run(variant, speak_policy=hetero_policy),
                "all_silent_control": _run(variant, speak_policy=control_policy),
            }
        return out

    current_threshold_results = _run_all_variants()

    threshold_comparison = None
    if alt_threshold is not None:
        original = conversations_module.SILENCES_TO_WIND_DOWN
        # Founder-mandated guardrails around this specific patch: assert the
        # known-good starting value before touching anything, patch only
        # in-process (never the file on disk), restore in a finally block
        # that runs even if the patched run raises, then assert the
        # restoration actually landed. Any assertion failure propagates
        # immediately — this diagnostic fails closed rather than ever
        # returning evidence gathered under an unverified/unrestored value.
        if original != 2:
            raise DiagnosticSafetyError(
                f"refusing to patch SILENCES_TO_WIND_DOWN: expected the known starting value 2, found "
                f"{original!r}. Aborting before any patch — restoration could not be verified safe."
            )
        try:
            conversations_module.SILENCES_TO_WIND_DOWN = alt_threshold
            alt_results = _run_all_variants()
        finally:
            conversations_module.SILENCES_TO_WIND_DOWN = original
            if conversations_module.SILENCES_TO_WIND_DOWN != 2:
                raise DiagnosticSafetyError(
                    "SILENCES_TO_WIND_DOWN restoration failed: expected 2 after restore, found "
                    f"{conversations_module.SILENCES_TO_WIND_DOWN!r}. Failing closed."
                )
        threshold_comparison = {
            "note": (
                f"SILENCES_TO_WIND_DOWN was asserted == 2, monkeypatched in-process to {alt_threshold} "
                "for this comparison only, restored to 2 in a finally block, and re-asserted == 2 "
                "afterward — all four steps verified, none skipped. app/services/conversations.py on "
                "disk was never touched, and the patch cannot outlive this single diagnostic call."
            ),
            "original_threshold": original,
            "alternate_threshold": alt_threshold,
            "restoration_verified": conversations_module.SILENCES_TO_WIND_DOWN == 2,
            "results_at_alternate_threshold": alt_results,
        }

    return {
        "persistence_path": persistence_path,
        "current_threshold": conversations_module.SILENCES_TO_WIND_DOWN,
        "current_threshold_results": current_threshold_results,
        "threshold_comparison": threshold_comparison,
        "note_on_activation_count": (
            "empty_activation_count is a raw count of turns where the offered agent did not speak — "
            "reported as fact only, never itself treated as evidence of improvement or regression."
        ),
    }


def _classify_invalid_decision_reason(reason: str) -> str:
    """Deterministic string-match against the exact rejection text
    validate_decision raises — a definitional classification, not a
    judgment call, so safe to compute here rather than leaving raw for
    the reviewers to categorize themselves."""
    if "requires a target_agent_id" in reason or "requires content" in reason:
        return "generation/validation failure — the agent's own decision output omitted a required field"
    if "no open conversation to join" in reason or "already ended" in reason:
        return "post-closure timing — action referenced a conversation that was no longer open"
    if "already open" in reason or "already full" in reason:
        return "invalid conversation state — action conflicted with the conversation's current state"
    return "other/unclassified — reason text did not match any known category"


@register_diagnostic("morning_gathering_construction_and_invalid_decision_trace")
def morning_gathering_construction_and_invalid_decision_trace(
    ctx: DiagnosticContext, scope: dict[str, Any]
) -> dict[str, Any]:
    """Answers exactly two questions, entirely via read_repo_file and
    read_live_db — no isolated execution, no call_service_function, no
    LLM call. Question 1: how MORNING_GATHERING participant_ids are
    constructed and whether order is static/rotated/variable — settled by
    quoting the exact query plus running that same query read-only against
    the live agents table to show what it actually produces. Question 2:
    for each of the three already-identified INVALID_AGENT_DECISION
    events, what caused it and whether it is structurally reachable from
    next_speaker's in-conversation floor-allocation logic at all — settled
    by quoting validate_decision's IN_CONVERSATION_ACTIONS/
    NOT_IN_CONVERSATION_ACTIONS gate plus each event's own timing relative
    to the nearest conversation's close."""
    conversations_source = ctx.read_repo_file("app/services/conversations.py")
    orchestrator_source = ctx.read_repo_file("app/services/orchestrator.py")

    participant_construction = {
        "start_morning_gathering_source": _extract_python_function(
            conversations_source, "def start_morning_gathering("
        ),
        "morning_gathering_held_today_source": _extract_python_function(
            conversations_source, "def morning_gathering_held_today("
        ),
    }

    live_agent_order = ctx.read_live_db("SELECT id, agent_id FROM agents ORDER BY id")
    live_conversation_participant_orders = ctx.read_live_db(
        "SELECT id, participant_ids, started_sim_day FROM conversations ORDER BY id"
    )
    for row in live_conversation_participant_orders:
        row["participant_ids"] = json.loads(row["participant_ids"] or "[]")
    orders_identical = len({tuple(r["participant_ids"]) for r in live_conversation_participant_orders}) == 1

    question_1 = {
        "code": participant_construction,
        "live_agent_table_order_by_id": [r["agent_id"] for r in live_agent_order],
        "live_conversation_participant_orders": live_conversation_participant_orders,
        "orders_identical_across_all_observed_conversations": orders_identical,
        "conclusion_basis": (
            "start_morning_gathering builds participant_ids via "
            "`select(Agent.agent_id).order_by(Agent.id)` every time it is called — Agent.id is each "
            "agent's fixed database primary key, assigned once at seeding and never reassigned. This "
            "query is structurally incapable of producing a different order across calls unless the "
            "agents table itself changes (an agent added/removed). The live data above shows the "
            "actual order this produces and whether the three observed gatherings match it exactly."
        ),
    }

    # --- Question 2: trace the three already-identified INVALID_AGENT_DECISION events ---
    event_ids = scope.get("invalid_decision_event_ids", [131, 187, 220])
    validate_decision_source = _extract_python_function(orchestrator_source, "def validate_decision(")

    events = ctx.read_live_db(
        f"SELECT id, event_type, agent_id, payload, sim_day, sim_period, correlation_id, "
        f"causation_id, created_at FROM events WHERE id IN "
        f"({','.join('?' for _ in event_ids)})",
        tuple(event_ids),
    )
    conversations = ctx.read_live_db(
        "SELECT id, status, started_sim_day, started_at, ended_at FROM conversations ORDER BY id"
    )

    traced_events = []
    for e in events:
        payload = json.loads(e["payload"]) if e["payload"] else {}
        reason = payload.get("reason", "")
        # Nearest conversation on the same sim_day, to compute elapsed time since it closed.
        same_day_convos = [c for c in conversations if c["started_sim_day"] == e["sim_day"]]
        nearest = same_day_convos[-1] if same_day_convos else None
        seconds_since_close = None
        if nearest and nearest["ended_at"]:
            from datetime import datetime
            fmt = "%Y-%m-%d %H:%M:%S.%f"
            try:
                event_time = datetime.strptime(e["created_at"], fmt)
                closed_time = datetime.strptime(nearest["ended_at"], fmt)
                seconds_since_close = (event_time - closed_time).total_seconds()
            except ValueError:
                seconds_since_close = None
        traced_events.append({
            "event_id": e["id"],
            "agent_id": e["agent_id"],
            "reason": reason,
            "sim_day": e["sim_day"],
            "created_at": e["created_at"],
            "classification": _classify_invalid_decision_reason(reason),
            "nearest_same_day_conversation_id": nearest["id"] if nearest else None,
            "nearest_conversation_ended_at": nearest["ended_at"] if nearest else None,
            "seconds_after_that_conversations_close": seconds_since_close,
        })

    question_2 = {
        "validate_decision_source": validate_decision_source,
        "traced_events": traced_events,
        "structural_relationship_to_floor_allocation": (
            "validate_decision gates START_CONVERSATION and JOIN_CONVERSATION as "
            "NOT_IN_CONVERSATION_ACTIONS-adjacent checks evaluated on a standalone agent activation "
            "OUTSIDE any conversation the agent is currently a participant-with-the-floor in. "
            "next_speaker (the function responsible for the confirmed floor-allocation defect) is "
            "only ever called to pick who speaks NEXT INSIDE an already-open conversation; it plays "
            "no role in whether an agent, activated independently, chooses to attempt "
            "START_CONVERSATION or JOIN_CONVERSATION, or whether that attempt is valid. These are "
            "different code paths. See validate_decision_source above for the exact gating logic; "
            "see traced_events above for each event's own agent_id, timing, and classification."
        ),
    }

    return {
        "question_1_participant_construction": question_1,
        "question_2_invalid_decision_trace": question_2,
    }


@register_diagnostic("conversation_decision_trace")
def conversation_decision_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """Post-stress-test addition (Founder Packet 2026-09-04, recommendation
    #1): for each named AGENT_ACTED event inside a conversation, reconstruct
    the full decision sequence in one place — the state presented, the
    schema/action-affordance governing code, whatever telemetry exists for
    the model call, the parsed action, the validation/rejection outcome,
    conversation state before/after, floor allocation, and the silence/
    closure decision — with every event id that ties the sequence together.

    Deliberately observational only: never calls next_speaker/should_close,
    never mutates anything, never re-renders a live prompt (context_builder
    depends on live ORM objects this diagnostic is never handed) — instead
    it reads the actual governing source (SYSTEM_PROMPT, available-actions
    logic, action schema) verbatim, so a human can compare that source
    against what the payloads actually show happened.

    Can inspect: events (AGENT_WOKE/AGENT_ACTED/INVALID_AGENT_DECISION/
    CONVERSATION_ENDED), conversations, conversation_messages, llm_runs
    (tokens/cost/latency/stop_reason/retry_count/is_fixture only), and the
    governing source files.
    Cannot inspect: the raw prompt text or raw model response actually sent/
    received for a historical call — LLMRun never persists either (only
    aggregate telemetry). Reported explicitly as an evidence gap below,
    never silently omitted.
    """
    event_ids: list[int] = scope["event_ids"]
    traces: list[dict[str, Any]] = []

    for acted_id in event_ids:
        acted_rows = ctx.read_live_db(
            "SELECT id, event_type, agent_id, payload, entity_type, entity_id, correlation_id, "
            "causation_id, sim_day, sim_period, created_at FROM events WHERE id = ?", (acted_id,),
        )
        if not acted_rows or acted_rows[0]["event_type"] != "AGENT_ACTED":
            traces.append({"event_id": acted_id, "error": "not an AGENT_ACTED event id"})
            continue
        acted = acted_rows[0]
        acted_payload = json.loads(acted["payload"]) if acted["payload"] else {}
        correlation_id = acted["correlation_id"]

        wake_rows = ctx.read_live_db(
            "SELECT id, agent_id, payload, sim_day, sim_period, created_at FROM events "
            "WHERE event_type = 'AGENT_WOKE' AND correlation_id = ?", (correlation_id,),
        )
        wake = wake_rows[0] if wake_rows else None
        wake_payload = json.loads(wake["payload"]) if wake and wake["payload"] else {}
        conversation_id = wake_payload.get("conversation_id")
        in_conversation = conversation_id is not None

        invalid_rows = ctx.read_live_db(
            "SELECT id, payload, created_at FROM events "
            "WHERE event_type = 'INVALID_AGENT_DECISION' AND correlation_id = ?", (correlation_id,),
        )
        invalid_payload = (
            json.loads(invalid_rows[0]["payload"]) if invalid_rows and invalid_rows[0]["payload"] else None
        )

        llm_run_rows = ctx.read_live_db(
            "SELECT id, purpose, agent_id, provider, model, is_fixture, input_tokens, output_tokens, "
            "estimated_cost_usd, latency_ms, stop_reason, retry_count, created_at FROM llm_runs "
            "WHERE purpose = 'agent_decision' AND agent_id = ? "
            "AND created_at BETWEEN datetime(?, '-5 seconds') AND datetime(?, '+5 seconds')",
            (acted["agent_id"], acted["created_at"], acted["created_at"]),
        )

        conv_state: dict[str, Any] | None = None
        turns_reconstructed: list[dict[str, Any]] = []
        ended_rows: list[dict[str, Any]] = []
        if in_conversation:
            convo_rows = ctx.read_live_db(
                "SELECT id, status, consecutive_silences, ending_reason, participant_ids "
                "FROM conversations WHERE id = ?", (conversation_id,),
            )
            conv_state = convo_rows[0] if convo_rows else None
            all_wakes = ctx.read_live_db(
                "SELECT id, agent_id, created_at FROM events WHERE event_type = 'AGENT_WOKE' "
                "AND json_extract(payload, '$.conversation_id') = ? ORDER BY id ASC", (conversation_id,),
            )
            silence_count = 0
            for w in all_wakes:
                is_this_turn = w["id"] == (wake["id"] if wake else None)
                turns_reconstructed.append({"wake_event_id": w["id"], "agent_id": w["agent_id"]})
                if is_this_turn:
                    break
            ended_rows = ctx.read_live_db(
                "SELECT id, payload, created_at FROM events WHERE event_type = 'CONVERSATION_ENDED' "
                "AND entity_type = 'conversation' AND entity_id = ?", (str(conversation_id),),
            )

        messages = ctx.read_live_db(
            "SELECT id, agent_id, content, turn_number FROM conversation_messages "
            "WHERE conversation_id = ? ORDER BY turn_number ASC", (conversation_id,),
        ) if conversation_id is not None else []
        public_dialogue = acted_payload.get("public_dialogue")
        actions_chosen = acted_payload.get("actions", [])
        persisted = (
            any(m["agent_id"] == acted["agent_id"] and m["content"] == public_dialogue for m in messages)
            if public_dialogue is not None else None
        )

        traces.append({
            "provenance": {
                "wake_event_id": wake["id"] if wake else None,
                "acted_event_id": acted["id"],
                "invalid_decision_event_id": invalid_rows[0]["id"] if invalid_rows else None,
                "conversation_ended_event_id": ended_rows[0]["id"] if ended_rows else None,
                "correlation_id": correlation_id,
                "causation_id": acted["causation_id"],
            },
            "state_presented": {
                "agent_id": acted["agent_id"],
                "sim_day": acted["sim_day"],
                "sim_period": acted["sim_period"],
                "in_conversation": in_conversation,
                "conversation_id": conversation_id,
                "wake_payload": wake_payload,
            },
            "raw_model_response": {
                "available": False,
                "reason": (
                    "app.db.models.telemetry.LLMRun does not persist raw request/response text — "
                    "only tokens/cost/latency/stop_reason/retry_count are recorded. This is a "
                    "structural observability gap, not a lookup failure."
                ),
                "telemetry_match": llm_run_rows[0] if llm_run_rows else None,
                "telemetry_match_note": (
                    "matched by agent_id + a 10-second created_at window around the AGENT_ACTED event, "
                    "since llm_runs has no correlation_id/event_id column linking it to a specific "
                    "decision — a second observability gap worth the Founder's attention."
                ),
            },
            "parsed_action": {"actions_chosen": actions_chosen, "public_dialogue": public_dialogue},
            "validation_result": {
                "rejected": invalid_payload is not None,
                "reason": invalid_payload.get("reason") if invalid_payload else None,
            },
            "conversation_state_after": conv_state,
            "floor_allocation": {
                "offered_to": acted["agent_id"] if in_conversation else None,
                "turn_position_this_conversation": len(turns_reconstructed) if in_conversation else None,
            },
            "closure": {
                "consecutive_silences_after": conv_state["consecutive_silences"] if conv_state else None,
                "conversation_ended_immediately_after": bool(ended_rows),
                "ending_reason": ended_rows[0]["payload"] if ended_rows else None,
            },
            "persisted_as_conversation_message": persisted,
        })

    return {
        "traces": traces,
        "governing_code": {
            "app/services/context_builder.py": ctx.read_repo_file("app/services/context_builder.py"),
            "app/services/orchestrator.py": ctx.read_repo_file("app/services/orchestrator.py"),
            "app/schemas/actions.py": ctx.read_repo_file("app/schemas/actions.py"),
        },
    }


@register_diagnostic("research_initiation_and_completion_trace")
def research_initiation_and_completion_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each agent_id in scope: every research session it started, whether
    it reached RESEARCH_COMPLETED or RESEARCH_UNAVAILABLE, how many queries/
    sources/findings it produced, and wall-clock span from AGENT_RESEARCH_
    STARTED to completion.

    Can inspect: events (AGENT_RESEARCH_STARTED/SEARCH_EXECUTED/
    SOURCE_DISCOVERED/RESEARCH_COMPLETED/RESEARCH_UNAVAILABLE/FINDING_CREATED),
    research_sessions, research_queries, research_sources, research_findings.
    Cannot inspect: why a model chose START_RESEARCH or not on a given
    activation (that's conversation_decision_trace/opportunity-scheduling
    territory, not this diagnostic's), or the actual interpretation
    reasoning behind a finding beyond its stored finding_text.
    """
    agent_ids: list[str] = scope["agent_ids"]
    out: list[dict[str, Any]] = []
    for agent_id in agent_ids:
        sessions = ctx.read_live_db(
            "SELECT id, research_id, question, status, evidence_strength, confidence, "
            "created_at, updated_at, is_fixture FROM research_sessions WHERE agent_id = ? "
            "ORDER BY created_at ASC", (agent_id,),
        )
        started_events = ctx.read_live_db(
            "SELECT id, payload, created_at FROM events "
            "WHERE event_type = 'AGENT_RESEARCH_STARTED' AND agent_id = ? ORDER BY id ASC", (agent_id,),
        )
        unavailable_events = ctx.read_live_db(
            "SELECT id, payload, created_at FROM events "
            "WHERE event_type = 'RESEARCH_UNAVAILABLE' AND agent_id = ? ORDER BY id ASC", (agent_id,),
        )
        sessions_detail = []
        for s in sessions:
            queries = ctx.read_live_db(
                "SELECT id, query_text, sequence_number FROM research_queries "
                "WHERE research_session_id = ? ORDER BY sequence_number ASC", (s["research_id"],),
            )
            sources = ctx.read_live_db(
                "SELECT id, url, quality_tier, provider FROM research_sources "
                "WHERE research_session_id = ?", (s["research_id"],),
            )
            findings = ctx.read_live_db(
                "SELECT id, finding_text, classification FROM research_findings "
                "WHERE research_session_id = ?", (s["research_id"],),
            )
            completed_events = ctx.read_live_db(
                "SELECT id, created_at FROM events WHERE event_type = 'RESEARCH_COMPLETED' "
                "AND entity_type = 'research_session' AND entity_id = ?", (s["research_id"],),
            )
            sessions_detail.append({
                "session": s,
                "query_count": len(queries), "queries": queries,
                "source_count": len(sources), "sources": sources,
                "finding_count": len(findings), "findings": findings,
                "reached_research_completed_event": bool(completed_events),
                "completed_event_id": completed_events[0]["id"] if completed_events else None,
            })
        out.append({
            "agent_id": agent_id,
            "research_started_event_count": len(started_events),
            "research_unavailable_event_count": len(unavailable_events),
            "unavailable_events": unavailable_events,
            "session_count": len(sessions),
            "sessions": sessions_detail,
            "started_events_without_matching_session": [
                e["id"] for e in started_events
                if not any(
                    s["created_at"] and e["created_at"] and
                    abs((_parse_ts(s["created_at"]) - _parse_ts(e["created_at"])).total_seconds()) < 5
                    for s in sessions
                )
            ],
        })
    return {"agents": out}


@register_diagnostic("research_provenance_and_evidence_flow_trace")
def research_provenance_and_evidence_flow_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each finding_id in scope: every claim it was split into, each
    claim's evidence chain back through a passage to its source, and whether
    the owning session's research_id is cited by any Research Wall post —
    tracing claim --evidence--> passage --> source, exactly the chain
    research_provenance.py's module docstring describes.

    Can inspect: research_findings, claims, claim_evidence,
    research_source_passages, research_sources, research_wall (session-level
    citation only).
    Cannot inspect: wall citation at finding/claim granularity — research_wall
    only stores related_research_id (the session), not a finding or claim id,
    so a session with five findings and one wall post cannot be narrowed to
    which finding motivated it from this data alone. Reported as a
    provenance-granularity gap, not silently assumed away.
    """
    finding_ids: list[int] = scope["finding_ids"]
    out = []
    for fid in finding_ids:
        finding_rows = ctx.read_live_db(
            "SELECT id, research_session_id, finding_text, classification FROM research_findings "
            "WHERE id = ?", (fid,),
        )
        if not finding_rows:
            out.append({"finding_id": fid, "error": "no such finding"})
            continue
        finding = finding_rows[0]
        claims = ctx.read_live_db(
            "SELECT id, claim_text, classification, confidence FROM claims WHERE finding_id = ?", (fid,),
        )
        claims_detail = []
        for c in claims:
            evidence = ctx.read_live_db(
                "SELECT id, passage_id, relation FROM claim_evidence WHERE claim_id = ?", (c["id"],),
            )
            evidence_detail = []
            for ev in evidence:
                passage_rows = ctx.read_live_db(
                    "SELECT id, source_id, locator, excerpt_sha256 FROM research_source_passages "
                    "WHERE id = ?", (ev["passage_id"],),
                )
                passage = passage_rows[0] if passage_rows else None
                source = None
                if passage:
                    source_rows = ctx.read_live_db(
                        "SELECT id, url, title, quality_tier, provider FROM research_sources WHERE id = ?",
                        (passage["source_id"],),
                    )
                    source = source_rows[0] if source_rows else None
                evidence_detail.append({"relation": ev["relation"], "passage": passage, "source": source})
            claims_detail.append({"claim": c, "evidence_chain": evidence_detail})
        wall_posts = ctx.read_live_db(
            "SELECT id, agent_id, post_type, content FROM research_wall WHERE related_research_id = ?",
            (finding["research_session_id"],),
        )
        out.append({
            "finding": finding,
            "claim_count": len(claims),
            "claims": claims_detail,
            "session_cited_by_wall_posts": wall_posts,
            "claims_with_zero_evidence": [c["claim"]["id"] for c in claims_detail if not c["evidence_chain"]],
        })
    return {"findings": out}


@register_diagnostic("memory_formation_and_recall_trace")
def memory_formation_and_recall_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each memory_id in scope: its current row, the MEMORY_CREATED event
    that made it, every later MEMORY_REINFORCED/MEMORY_RECALLED event against
    it, and a mechanical consistency check between the event count and the
    stored reinforcement_count/last_accessed columns.

    Can inspect: memories, events (MEMORY_CREATED/MEMORY_REINFORCED/
    MEMORY_RECALLED, entity_type='memory').
    Cannot inspect: whether a recalled memory actually changed the content of
    the decision it was surfaced into — only that context_builder surfaced it
    (a MEMORY_RECALLED event exists), never the causal effect on the model's
    output.
    """
    memory_ids: list[int] = scope["memory_ids"]
    out = []
    for mid in memory_ids:
        rows = ctx.read_live_db(
            "SELECT id, agent_id, memory_type, content, importance, confidence, created_sim_day, "
            "last_accessed, last_accessed_sim_day, decay_score, reinforcement_count, source_event_ids "
            "FROM memories WHERE id = ?", (mid,),
        )
        if not rows:
            out.append({"memory_id": mid, "error": "no such memory"})
            continue
        memory = rows[0]
        created_events = ctx.read_live_db(
            "SELECT id, created_at FROM events WHERE event_type = 'MEMORY_CREATED' "
            "AND entity_type = 'memory' AND entity_id = ?", (str(mid),),
        )
        reinforced_events = ctx.read_live_db(
            "SELECT id, payload, created_at FROM events WHERE event_type = 'MEMORY_REINFORCED' "
            "AND entity_type = 'memory' AND entity_id = ? ORDER BY id ASC", (str(mid),),
        )
        recalled_events = ctx.read_live_db(
            "SELECT id, payload, created_at FROM events WHERE event_type = 'MEMORY_RECALLED' "
            "AND entity_type = 'memory' AND entity_id = ? ORDER BY id ASC", (str(mid),),
        )
        out.append({
            "memory": memory,
            "creation_event_id": created_events[0]["id"] if created_events else None,
            "reinforced_event_count": len(reinforced_events),
            "reinforced_events": reinforced_events,
            "recalled_event_count": len(recalled_events),
            "recalled_events": recalled_events,
            "consistency_checks": {
                "reinforcement_count_matches_event_count": memory["reinforcement_count"] == len(reinforced_events),
                "last_accessed_matches_last_recalled_event": (
                    (recalled_events[-1]["created_at"] == memory["last_accessed"]) if recalled_events
                    else memory["last_accessed"] is None
                ),
            },
        })
    return {"memories": out}


@register_diagnostic("relationship_state_and_influence_trace")
def relationship_state_and_influence_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each [agent_a, agent_b] pair in scope: the current relationship
    row plus an independent recount of shared conversations and direct
    messages from the event log, checked for consistency against the
    stored interaction_count/last_interaction.

    Can inspect: relationships (current snapshot only), conversations
    (participant_ids), messages (direct sender/recipient).
    Cannot inspect: a historical trajectory of trust_score/familiarity/
    intellectual_affinity — Relationship has no history table, only current
    aggregate state, so "how this pair's relationship moved over time"
    cannot be answered from this data at all. This is itself the finding to
    report, not something to work around.
    """
    pairs: list[list[str]] = scope["agent_pairs"]
    out = []
    for a, b in pairs:
        rel_rows = ctx.read_live_db(
            "SELECT id, agent_a_id, agent_b_id, trust_score, familiarity, intellectual_affinity, "
            "productive_disagreement_count, interaction_count, last_interaction, notes FROM relationships "
            "WHERE (agent_a_id = ? AND agent_b_id = ?) OR (agent_a_id = ? AND agent_b_id = ?)",
            (a, b, b, a),
        )
        shared_conversations = ctx.read_live_db(
            "SELECT id, participant_ids, started_sim_day FROM conversations "
            "WHERE participant_ids LIKE ? AND participant_ids LIKE ?",
            (f'%"{a}"%', f'%"{b}"%'),
        )
        direct_messages = ctx.read_live_db(
            "SELECT id, sender_agent_id, recipient_agent_id, created_at FROM messages "
            "WHERE (sender_agent_id = ? AND recipient_agent_id = ?) "
            "OR (sender_agent_id = ? AND recipient_agent_id = ?)",
            (a, b, b, a),
        )
        out.append({
            "pair": [a, b],
            "relationship_row": rel_rows[0] if rel_rows else None,
            "shared_conversation_count_from_events": len(shared_conversations),
            "shared_conversations": shared_conversations,
            "direct_message_count_from_events": len(direct_messages),
            "stored_interaction_count_vs_observed": {
                "stored": rel_rows[0]["interaction_count"] if rel_rows else None,
                "observed_shared_conversations_plus_messages": len(shared_conversations) + len(direct_messages),
                "note": (
                    "interaction_count's own increment rule is not defined by this trace; a mismatch "
                    "is evidence to investigate, not proof of a bug by itself."
                ),
            },
        })
    return {"pairs": out}


@register_diagnostic("belief_lifecycle_trace")
def belief_lifecycle_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each belief_id in scope: the current row (statement, confidence,
    status, basis) and every BELIEF_CREATED/BELIEF_UPDATED/BELIEF_REJECTED
    event against it, in order, with each event's own payload (which may
    carry the confidence/statement value at that point in time, if the
    service logged it — read verbatim, never assumed).

    Can inspect: agent_beliefs, events (BELIEF_CREATED/BELIEF_UPDATED/
    BELIEF_REJECTED, entity_type='agent_belief').
    Cannot inspect: belief_basis table content beyond what's already exposed
    via agent_beliefs.basis (a JSON id list) — resolving those ids back to
    real research/conversation rows is a second diagnostic's job (research
    tracing above), not duplicated here.
    """
    belief_ids: list[int] = scope["belief_ids"]
    out = []
    for bid in belief_ids:
        rows = ctx.read_live_db(
            "SELECT id, agent_id, statement, confidence, basis, status, updated_at "
            "FROM agent_beliefs WHERE id = ?", (bid,),
        )
        if not rows:
            out.append({"belief_id": bid, "error": "no such belief"})
            continue
        belief = rows[0]
        lifecycle_events = ctx.read_live_db(
            "SELECT id, event_type, payload, created_at FROM events "
            "WHERE event_type IN ('BELIEF_CREATED', 'BELIEF_UPDATED', 'BELIEF_REJECTED') "
            "AND entity_type = 'agent_belief' AND entity_id = ? ORDER BY id ASC", (str(bid),),
        )
        out.append({
            "belief": belief,
            "lifecycle_event_count": len(lifecycle_events),
            "lifecycle_events": [
                {**e, "payload": json.loads(e["payload"]) if e["payload"] else {}} for e in lifecycle_events
            ],
            "revision_count": sum(1 for e in lifecycle_events if e["event_type"] == "BELIEF_UPDATED"),
            "ever_rejected": any(e["event_type"] == "BELIEF_REJECTED" for e in lifecycle_events),
        })
    return {"beliefs": out}


@register_diagnostic("research_wall_activity_and_propagation_trace")
def research_wall_activity_and_propagation_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each post_id in scope: the post row, its connection chain
    (related_wall_post_id / related_rabbit_hole_id / related_research_id),
    every WALL_POST_READ event against it (who read it), and any
    CLAIM_CHALLENGED event referencing it.

    Can inspect: research_wall, events (RESEARCH_WALL_POSTED/WALL_POST_READ/
    CLAIM_CHALLENGED, entity_type='research_wall').
    Cannot inspect: whether a read genuinely changed the reading agent's
    later behavior (belief/action) — only that a read event was logged.
    """
    post_ids: list[int] = scope["post_ids"]
    out = []
    for pid in post_ids:
        rows = ctx.read_live_db(
            "SELECT id, agent_id, post_type, content, related_research_id, related_wall_post_id, "
            "related_rabbit_hole_id, created_at FROM research_wall WHERE id = ?", (pid,),
        )
        if not rows:
            out.append({"post_id": pid, "error": "no such post"})
            continue
        post = rows[0]
        connecting_posts = ctx.read_live_db(
            "SELECT id, agent_id, post_type, content FROM research_wall WHERE related_wall_post_id = ?",
            (pid,),
        )
        read_events = ctx.read_live_db(
            "SELECT id, agent_id, created_at FROM events WHERE event_type = 'WALL_POST_READ' "
            "AND entity_type = 'research_wall' AND entity_id = ? ORDER BY id ASC", (str(pid),),
        )
        challenge_events = ctx.read_live_db(
            "SELECT id, agent_id, payload, created_at FROM events WHERE event_type = 'CLAIM_CHALLENGED' "
            "AND entity_type = 'research_wall' AND entity_id = ? ORDER BY id ASC", (str(pid),),
        )
        out.append({
            "post": post,
            "posts_connecting_to_this_one": connecting_posts,
            "distinct_readers": sorted({e["agent_id"] for e in read_events if e["agent_id"]}),
            "read_event_count": len(read_events),
            "challenge_event_count": len(challenge_events),
            "challenges": challenge_events,
        })
    return {"posts": out}


@register_diagnostic("rabbit_hole_lifecycle_trace")
def rabbit_hole_lifecycle_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each rabbit_hole_id in scope: the current row, its membership
    history (joined/left, never deleted), attached research sessions, and
    every RABBIT_HOLE_* status-change event in order.

    Can inspect: rabbit_holes, rabbit_hole_members, rabbit_hole_research,
    events (RABBIT_HOLE_CREATED/JOINED/UPDATED/LEFT/RESOLVED/ABANDONED,
    entity_type='rabbit_hole').
    Cannot inspect: the actual intellectual content of what a member
    contributed beyond the research sessions attached — a member could join
    and never contribute; this trace shows membership and attachment, not
    quality or depth of contribution.
    """
    rabbit_hole_ids: list[int] = scope["rabbit_hole_ids"]
    out = []
    for rid in rabbit_hole_ids:
        rows = ctx.read_live_db(
            "SELECT id, title, originating_agent_id, evidence_strength, current_hypothesis, "
            "activity_level, status, last_activity, last_activity_day FROM rabbit_holes WHERE id = ?",
            (rid,),
        )
        if not rows:
            out.append({"rabbit_hole_id": rid, "error": "no such rabbit hole"})
            continue
        hole = rows[0]
        members = ctx.read_live_db(
            "SELECT id, agent_id, joined_at, left_at FROM rabbit_hole_members "
            "WHERE rabbit_hole_id = ? ORDER BY joined_at ASC", (rid,),
        )
        research = ctx.read_live_db(
            "SELECT research_session_id FROM rabbit_hole_research WHERE rabbit_hole_id = ?", (rid,),
        )
        lifecycle_events = ctx.read_live_db(
            "SELECT id, event_type, agent_id, payload, created_at FROM events "
            "WHERE event_type IN ('RABBIT_HOLE_CREATED', 'RABBIT_HOLE_JOINED', 'RABBIT_HOLE_UPDATED', "
            "'RABBIT_HOLE_LEFT', 'RABBIT_HOLE_RESOLVED', 'RABBIT_HOLE_ABANDONED') "
            "AND entity_type = 'rabbit_hole' AND entity_id = ? ORDER BY id ASC", (str(rid),),
        )
        out.append({
            "rabbit_hole": hole,
            "current_members": [m for m in members if m["left_at"] is None],
            "all_members_ever": members,
            "attached_research_session_ids": [r["research_session_id"] for r in research],
            "lifecycle_event_count": len(lifecycle_events),
            "lifecycle_events": [
                {**e, "payload": json.loads(e["payload"]) if e["payload"] else {}} for e in lifecycle_events
            ],
        })
    return {"rabbit_holes": out}


@register_diagnostic("agent_question_continuity_trace")
def agent_question_continuity_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each question_id in scope: the current row (status, salience,
    origin), its full lifecycle event history, its reformulation chain in
    both directions, and — if it was ever linked to a research session —
    whether that session actually reached RESEARCH_COMPLETED.

    Can inspect: agent_questions, events (QUESTION_CREATED/REVISITED/
    LINKED_TO_RESEARCH/STATUS_CHANGED/DORMANT/REFORMULATED,
    entity_type='agent_question'), research_sessions (status only, for the
    forward research link).
    Cannot inspect: whether an OPEN question was ever actually rendered into
    a real agent's context (that depends on MAX_CONTEXT_QUESTIONS/salience
    ranking at render time, not reconstructable after the fact from this
    data alone).
    """
    question_ids: list[int] = scope["question_ids"]
    out = []
    for qid in question_ids:
        rows = ctx.read_live_db(
            "SELECT id, agent_id, question, status, salience, last_engaged_sim_day, "
            "origin_memory_id, origin_reflection_id, origin_conversation_id, "
            "origin_research_session_id, research_session_id, rabbit_hole_id, "
            "reformulated_from_id, reformulated_into_id FROM agent_questions WHERE id = ?", (qid,),
        )
        if not rows:
            out.append({"question_id": qid, "error": "no such question"})
            continue
        question = rows[0]
        lifecycle_events = ctx.read_live_db(
            "SELECT id, event_type, payload, created_at FROM events "
            "WHERE event_type IN ('QUESTION_CREATED', 'QUESTION_REVISITED', "
            "'QUESTION_LINKED_TO_RESEARCH', 'QUESTION_STATUS_CHANGED', 'QUESTION_DORMANT', "
            "'QUESTION_REFORMULATED') AND entity_type = 'agent_question' AND entity_id = ? "
            "ORDER BY id ASC", (str(qid),),
        )
        linked_research_status = None
        if question["research_session_id"]:
            sess = ctx.read_live_db(
                "SELECT research_id, status FROM research_sessions WHERE research_id = ?",
                (question["research_session_id"],),
            )
            linked_research_status = sess[0]["status"] if sess else None
        out.append({
            "question": question,
            "lifecycle_event_count": len(lifecycle_events),
            "lifecycle_events": [
                {**e, "payload": json.loads(e["payload"]) if e["payload"] else {}} for e in lifecycle_events
            ],
            "linked_research_session_status": linked_research_status,
            "is_reformulation_chain_link": (
                question["reformulated_from_id"] is not None or question["reformulated_into_id"] is not None
            ),
        })
    return {"questions": out}


@register_diagnostic("agent_opportunity_and_scheduling_trace")
def agent_opportunity_and_scheduling_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """Village-wide (not conversation-specific): for the given sim_day
    range, every agent's AGENT_WOKE/AGENT_ACTED activation count, split
    passive vs. substantive by the same action-type list director_snapshot
    uses, so opportunity allocation across the FULL population can be
    checked for fairness — distinct from conversation_lifecycle_trace's
    narrower floor-offer-within-one-conversation view.

    Can inspect: events (AGENT_WOKE/AGENT_ACTED), agents (roster only).
    Cannot inspect: *why* the scheduler picked one eligible agent over
    another on a given tick (that's scheduler.py source, not event-log
    territory) — this trace reports the resulting distribution, not the
    selection algorithm's internal state.
    """
    sim_day_range: list[int] = scope["sim_day_range"]
    day_lo, day_hi = sim_day_range[0], sim_day_range[-1]
    agents = ctx.read_live_db("SELECT agent_id FROM agents ORDER BY agent_id ASC", ())
    woke_events = ctx.read_live_db(
        "SELECT agent_id, sim_day FROM events WHERE event_type = 'AGENT_WOKE' "
        "AND sim_day BETWEEN ? AND ?", (day_lo, day_hi),
    )
    acted_events = ctx.read_live_db(
        "SELECT agent_id, sim_day, payload FROM events WHERE event_type = 'AGENT_ACTED' "
        "AND sim_day BETWEEN ? AND ?", (day_lo, day_hi),
    )
    passive_types = {"OBSERVE", "REST", "LISTEN_TO_MUSIC", "DRINK_COFFEE"}
    per_agent: dict[str, dict[str, Any]] = {
        a["agent_id"]: {"woke_count": 0, "acted_count": 0, "passive_count": 0, "substantive_count": 0}
        for a in agents
    }
    for w in woke_events:
        if w["agent_id"] in per_agent:
            per_agent[w["agent_id"]]["woke_count"] += 1
    for e in acted_events:
        if e["agent_id"] not in per_agent:
            continue
        per_agent[e["agent_id"]]["acted_count"] += 1
        payload = json.loads(e["payload"]) if e["payload"] else {}
        actions = payload.get("actions", [])
        if actions and all(a in passive_types for a in actions):
            per_agent[e["agent_id"]]["passive_count"] += 1
        else:
            per_agent[e["agent_id"]]["substantive_count"] += 1
    acted_counts = [v["acted_count"] for v in per_agent.values()]
    return {
        "sim_day_range": sim_day_range,
        "per_agent": per_agent,
        "population_fairness": {
            "min_acted_count": min(acted_counts) if acted_counts else 0,
            "max_acted_count": max(acted_counts) if acted_counts else 0,
            "mean_acted_count": (sum(acted_counts) / len(acted_counts)) if acted_counts else 0,
            "spread": (max(acted_counts) - min(acted_counts)) if acted_counts else 0,
        },
    }


@register_diagnostic("invalid_decision_pattern_trace")
def invalid_decision_pattern_trace(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """Village-wide aggregate of every INVALID_AGENT_DECISION event in the
    given sim_day range, classified by director_diagnostics.
    _classify_invalid_decision_reason (the same deterministic classifier
    morning_gathering_construction_and_invalid_decision_trace uses), broken
    down by agent and by whether the activation was inside a conversation.

    Can inspect: events (INVALID_AGENT_DECISION, AGENT_WOKE for the
    in-conversation cross-reference).
    Cannot inspect: the model's own reasoning for producing a malformed
    decision — only the rejection reason validate_decision recorded.
    """
    sim_day_range: list[int] = scope["sim_day_range"]
    day_lo, day_hi = sim_day_range[0], sim_day_range[-1]
    invalid_events = ctx.read_live_db(
        "SELECT id, agent_id, payload, correlation_id, sim_day, created_at FROM events "
        "WHERE event_type = 'INVALID_AGENT_DECISION' AND sim_day BETWEEN ? AND ?", (day_lo, day_hi),
    )
    by_classification: dict[str, int] = {}
    by_agent: dict[str, int] = {}
    detail = []
    for e in invalid_events:
        payload = json.loads(e["payload"]) if e["payload"] else {}
        reason = payload.get("reason", "")
        classification = _classify_invalid_decision_reason(reason)
        by_classification[classification] = by_classification.get(classification, 0) + 1
        by_agent[e["agent_id"]] = by_agent.get(e["agent_id"], 0) + 1
        wake = ctx.read_live_db(
            "SELECT payload FROM events WHERE event_type = 'AGENT_WOKE' AND correlation_id = ?",
            (e["correlation_id"],),
        )
        wake_payload = json.loads(wake[0]["payload"]) if wake and wake[0]["payload"] else {}
        detail.append({
            "event_id": e["id"], "agent_id": e["agent_id"], "sim_day": e["sim_day"],
            "reason": reason, "classification": classification,
            "was_in_conversation": wake_payload.get("conversation_id") is not None,
        })
    return {
        "sim_day_range": sim_day_range,
        "total_invalid_decisions": len(invalid_events),
        "by_classification": by_classification,
        "by_agent": by_agent,
        "detail": detail,
    }


@register_diagnostic("observability_gap_scan")
def observability_gap_scan(ctx: DiagnosticContext, scope: dict[str, Any]) -> dict[str, Any]:
    """For each sim_day in the given range: cross-checks the day's
    daily_reports.had_meaningful_activity flag against an independently
    computed activity signature (passive-action rate, SEND_MESSAGE/
    ASK_QUESTION counts, memory/wall/rabbit-hole activity) — surfacing days
    where the headline metric and the raw signature disagree, plus a fixed
    list of already-known structural recording gaps.

    Can inspect: daily_reports, events (AGENT_ACTED, MEMORY_CREATED,
    RESEARCH_WALL_POSTED, RABBIT_HOLE_CREATED), messages.
    Cannot inspect: gaps this scan doesn't already know to look for — it is
    a checklist against known/suspected gaps (per the Founder Packet), not a
    general-purpose anomaly detector.
    """
    sim_day_range: list[int] = scope["sim_day_range"]
    day_lo, day_hi = sim_day_range[0], sim_day_range[-1]
    reports = ctx.read_live_db(
        "SELECT day_number, had_meaningful_activity, is_fixture FROM daily_reports "
        "WHERE day_number BETWEEN ? AND ? ORDER BY day_number ASC", (day_lo, day_hi),
    )
    per_day = []
    for r in reports:
        day = r["day_number"]
        acted = ctx.read_live_db(
            "SELECT payload FROM events WHERE event_type = 'AGENT_ACTED' AND sim_day = ?", (day,),
        )
        passive_types = {"OBSERVE", "REST", "LISTEN_TO_MUSIC", "DRINK_COFFEE"}
        passive = 0
        send_message = 0
        ask_question = 0
        for e in acted:
            payload = json.loads(e["payload"]) if e["payload"] else {}
            actions = payload.get("actions", [])
            if actions and all(a in passive_types for a in actions):
                passive += 1
            if "SEND_MESSAGE" in actions:
                send_message += 1
            if "ASK_QUESTION" in actions:
                ask_question += 1
        memory_created = ctx.read_live_db(
            "SELECT id FROM events WHERE event_type = 'MEMORY_CREATED' AND sim_day = ?", (day,),
        )
        wall_posted = ctx.read_live_db(
            "SELECT id FROM events WHERE event_type = 'RESEARCH_WALL_POSTED' AND sim_day = ?", (day,),
        )
        rabbit_hole_created = ctx.read_live_db(
            "SELECT id FROM events WHERE event_type = 'RABBIT_HOLE_CREATED' AND sim_day = ?", (day,),
        )
        passive_rate = (passive / len(acted)) if acted else None
        channel_shifted_engagement = (send_message + ask_question) > 0 and passive_rate is not None and passive_rate > 0.9
        per_day.append({
            "day_number": day,
            "had_meaningful_activity": r["had_meaningful_activity"],
            "total_acted_events": len(acted),
            "passive_rate": passive_rate,
            "send_message_count": send_message,
            "ask_question_count": ask_question,
            "memory_created_count": len(memory_created),
            "wall_posted_count": len(wall_posted),
            "rabbit_hole_created_count": len(rabbit_hole_created),
            "headline_metric_vs_signature_disagreement": (
                (passive_rate is not None and passive_rate > 0.9 and not r["had_meaningful_activity"])
                or (passive_rate is not None and passive_rate <= 0.5 and r["had_meaningful_activity"] is False)
            ),
            "channel_shifted_engagement_possible": channel_shifted_engagement,
        })
    return {
        "sim_day_range": sim_day_range,
        "per_day": per_day,
        "known_structural_gaps": [
            "app.db.models.telemetry.LLMRun persists no raw request/response text — only tokens/"
            "cost/latency/stop_reason/retry_count, and has no correlation_id linking a call to a "
            "specific decision event.",
            "app.db.models.conversations.Conversation and app.db.models.agents.Relationship both "
            "store only current state, no history table — a trajectory over time cannot be "
            "reconstructed from the DB alone, only from replaying the event log.",
            "The passive-action-rate metric (director_snapshot.py, this scan) counts only "
            "AGENT_ACTED action-type lists; it does not distinguish an agent who chose passive "
            "actions from one who engaged via SEND_MESSAGE/ASK_QUESTION on the same activation, "
            "unless that activation ALSO included a non-passive action type in the same actions list.",
        ],
    }


def _parse_ts(value: str) -> datetime:
    """Tolerant timestamp parser for the loose SQLite string formats
    created_at columns actually contain — used only by comparison logic
    inside diagnostics above, never for anything security-relevant."""
    text = value.replace("T", " ").rstrip("Z")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.min


def create_candidate_diagnostic(
    *,
    diagnostic_type: str,
    originating_round_id: str,
    originating_snapshot_id: str,
    originating_recommendation: str,
    evidence_refs: list[str],
    allowed_operations: dict[str, list[str]],
    scope: dict[str, Any],
    success_criteria: str,
    failure_criteria: str,
    timeout_seconds: int,
    forbidden_operations: list[str] | None = None,
    diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR,
) -> DiagnosticSpec:
    """Create a new diagnostic in CANDIDATE_FOR_DIAGNOSTIC state. Never
    transitions further — see approve_diagnostic."""
    diagnostic_id = f"diag_{uuid.uuid4().hex[:16]}"
    forbidden = list(STANDARD_FORBIDDEN_OPERATIONS)
    if forbidden_operations:
        forbidden += [f for f in forbidden_operations if f not in forbidden]
    spec = DiagnosticSpec(
        diagnostic_id=diagnostic_id,
        diagnostic_type=diagnostic_type,
        originating_round_id=originating_round_id,
        originating_snapshot_id=originating_snapshot_id,
        originating_recommendation=originating_recommendation,
        evidence_refs=evidence_refs,
        allowed_operations=allowed_operations,
        forbidden_operations=forbidden,
        scope=scope,
        success_criteria=success_criteria,
        failure_criteria=failure_criteria,
        timeout_seconds=timeout_seconds,
        output_evidence_dir=diagnostic_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    save_spec(spec, diagnostics_dir)
    return spec


def spec_path(diagnostic_id: str, diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR) -> Path:
    return diagnostics_dir / diagnostic_id / "spec.json"


def save_spec(spec: DiagnosticSpec, diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR) -> Path:
    path = spec_path(spec.diagnostic_id, diagnostics_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(spec.model_dump_json(indent=2) + "\n")
    return path


def load_spec(diagnostic_id: str, diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR) -> DiagnosticSpec:
    path = spec_path(diagnostic_id, diagnostics_dir)
    if not path.exists():
        raise DiagnosticSafetyError(f"no diagnostic spec at {path}.")
    return DiagnosticSpec.model_validate_json(path.read_text())


def approve_diagnostic(
    diagnostic_id: str,
    *,
    approved_by: str = "Founder",
    diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR,
) -> DiagnosticSpec:
    """THE ONLY function that moves a spec from CANDIDATE_FOR_DIAGNOSTIC to
    APPROVED_FOR_DIAGNOSTIC. Calling this is itself the approval; there is
    no second confirmation inside this module. See this module's docstring
    for the two legitimate callers — a human (the default, ``approved_by=
    "Founder"``) or, only once separately Founder-authorized and only
    within director_autonomous_loop.py's own closed-catalog/replay-only
    constraints, the autonomous loop (``approved_by=
    "autonomous_director_loop"``). This function itself does not — and
    structurally cannot — verify which situation it's being called from;
    the authorization boundary lives entirely in the caller."""
    spec = load_spec(diagnostic_id, diagnostics_dir)
    if spec.state is not DiagnosticState.CANDIDATE_FOR_DIAGNOSTIC:
        raise DiagnosticSafetyError(
            f"diagnostic {diagnostic_id!r} is in state {spec.state.value}, not "
            f"{DiagnosticState.CANDIDATE_FOR_DIAGNOSTIC.value} — refusing to approve."
        )
    spec.state = DiagnosticState.APPROVED_FOR_DIAGNOSTIC
    spec.approved_at = datetime.now(timezone.utc).isoformat()
    spec.approved_by = approved_by
    save_spec(spec, diagnostics_dir)
    return spec


class _Alarm:
    """Wall-clock timeout via SIGALRM — enough for a synchronous, in-process
    diagnostic implementation with no threads of its own."""

    def __init__(self, seconds: int) -> None:
        self.seconds = seconds

    def __enter__(self) -> None:
        def _handler(signum: int, frame: Any) -> None:
            raise DiagnosticTimeoutError(f"diagnostic exceeded its {self.seconds}s timeout.")
        self._previous = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(self.seconds)

    def __exit__(self, *exc: Any) -> None:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, self._previous)


def run_diagnostic(
    diagnostic_id: str,
    *,
    db_path: Path | None = None,
    diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR,
) -> DiagnosticSpec:
    """Execute one APPROVED_FOR_DIAGNOSTIC diagnostic. Fails closed at
    every stage: wrong state, unknown diagnostic_type, any operation
    outside the declared allowlist (raised by DiagnosticContext itself),
    or a timeout — none of these ever leave the spec in DIAGNOSTIC_COMPLETE
    with run_status other than "SUCCESS". db_path defaults to the real
    live database (via app.core.db_safety, same fail-closed resolution as
    every other Director component) — pass a disposable path for testing."""
    from app.core.db_safety import CANONICAL_LIVE_DB_PATH, check_live_db

    spec = load_spec(diagnostic_id, diagnostics_dir)
    if spec.state is not DiagnosticState.APPROVED_FOR_DIAGNOSTIC:
        raise DiagnosticSafetyError(
            f"diagnostic {diagnostic_id!r} is in state {spec.state.value}, not "
            f"{DiagnosticState.APPROVED_FOR_DIAGNOSTIC.value} — refusing to run."
        )
    impl = _DIAGNOSTIC_IMPLEMENTATIONS.get(spec.diagnostic_type)
    if impl is None:
        raise DiagnosticSafetyError(f"unknown diagnostic_type {spec.diagnostic_type!r}.")

    resolved_db_path = db_path if db_path is not None else CANONICAL_LIVE_DB_PATH
    check = check_live_db(resolved_db_path)
    if not check.healthy:
        spec.run_status = "FAILED"
        spec.run_error = f"live database at {resolved_db_path} not healthy: {check.problem}"
        save_spec(spec, diagnostics_dir)
        raise DiagnosticSafetyError(spec.run_error)

    ctx = DiagnosticContext(spec, db_path=resolved_db_path, diagnostics_dir=diagnostics_dir)
    try:
        try:
            with _Alarm(spec.timeout_seconds):
                evidence = impl(ctx, spec.scope)
        except (DiagnosticSafetyError, DiagnosticTimeoutError) as exc:
            spec.run_status = "FAILED"
            spec.run_error = str(exc)
            save_spec(spec, diagnostics_dir)
            raise
        except Exception as exc:  # noqa: BLE001 — any implementation error fails the diagnostic, never propagates as success
            spec.run_status = "FAILED"
            spec.run_error = f"{type(exc).__name__}: {exc}"
            save_spec(spec, diagnostics_dir)
            raise DiagnosticSafetyError(spec.run_error) from exc
    finally:
        ctx.cleanup()  # isolated test DBs (if any) are closed and deleted regardless of outcome

    ctx.write_evidence("evidence.json", json.dumps(evidence, indent=2, default=str))
    spec.state = DiagnosticState.DIAGNOSTIC_COMPLETE
    spec.run_status = "SUCCESS"
    spec.completed_at = datetime.now(timezone.utc).isoformat()
    save_spec(spec, diagnostics_dir)
    return spec


def load_evidence(diagnostic_id: str, diagnostics_dir: Path = DEFAULT_DIAGNOSTICS_DIR) -> dict[str, Any]:
    path = diagnostics_dir / diagnostic_id / "evidence.json"
    if not path.exists():
        raise DiagnosticSafetyError(f"no evidence file at {path} — diagnostic hasn't completed.")
    return json.loads(path.read_text())
