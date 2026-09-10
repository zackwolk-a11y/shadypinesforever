#!/usr/bin/env python3
"""Deterministic Packet 12 smoke test: The Fishbowl.

Drives a few real simulated days under the fixture providers so every kind
of record the Fishbowl displays actually exists (conversations, research
with provenance, wall posts, rabbit holes, a Founder report, LLM/research
telemetry), then exercises the FastAPI app exactly the way a browser would
— through Starlette's TestClient, real HTTP-shaped requests against
``app.main.app`` — and asserts every one of Part R's checkpoints.

Runs against its own throwaway SQLite database (deleted first, so it never
touches village.db), the same convention every other smoke_test_*.py in this
directory uses.

Usage::

    python scripts/test_fishbowl.py
    python scripts/test_fishbowl.py --keep-db   # inspect afterward
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "smoke_test_fishbowl.db"

# Must be set before anything under app/ is imported — the engine and every
# Settings snapshot are built from this at call time.
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ.setdefault("RESEARCH_PROVIDER", "fixture")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_SEED = "packet12-smoke"


def _clean_db() -> None:
    for suffix in ("", "-shm", "-wal"):
        p = Path(f"{DB_PATH}{suffix}")
        if p.exists():
            p.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--days", type=int, default=6, help="fixture days to seed the Fishbowl with")
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    _clean_db()

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    import seed_agents  # scripts/seed_agents.py

    from app.core.config import get_settings
    from app.db.models.agents import Agent
    from app.db.models.events import Event
    from app.db.models.rabbit_holes import RabbitHole
    from app.db.models.reports import DailyReport
    from app.db.models.research import ResearchSession
    from app.db.models.telemetry import LLMRun
    from app.db.models.research_usage import ResearchProviderUsage
    from app.db.session import SessionLocal
    from app.providers.llm import get_llm_provider
    from app.services.orchestrator import run_next_event
    from sqlalchemy import func, select

    settings = get_settings()
    print(f"Database: {settings.database_url}  (throwaway, deleted first)")
    if not settings.uses_fixture_llm or not settings.uses_fixture_research:
        print("This smoke test requires the fixture providers on both sides.")
        return 1

    session = SessionLocal()
    try:
        report = seed_agents.run(session)
        session.commit()
        print(f"Seeded: {len(report.created)} rows created.")

        provider = get_llm_provider(settings)
        print(f"Driving {args.days} fixture day(s) (seed={args.seed!r}) to populate real data...")
        for _ in range(args.days):
            from app.db.models.world import SimulationClock

            clock = session.scalars(select(SimulationClock).limit(1)).one()
            start_day = clock.current_day
            for _ in range(400):
                outcome = run_next_event(
                    session, settings=settings, provider=provider, seed=args.seed, auto_advance=True,
                )
                session.commit()
                if outcome.clock_advance:
                    session.refresh(clock)
                    if clock.current_day != start_day:
                        break

        research_count = session.scalar(select(func.count(ResearchSession.id))) or 0
        rabbit_hole_count = session.scalar(select(func.count(RabbitHole.id))) or 0
        report_count = session.scalar(select(func.count(DailyReport.id))) or 0
        llm_run_count_before = session.scalar(select(func.count(LLMRun.id))) or 0
        print(
            f"  research sessions: {research_count}, rabbit holes: {rabbit_hole_count}, "
            f"reports: {report_count}, llm_runs: {llm_run_count_before}\n"
        )

        # --------------------------------------------------------------
        # Now exercise the actual FastAPI app, the way a browser would.
        # --------------------------------------------------------------
        from starlette.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        checks: list[tuple[str, bool]] = []

        # ---- 1. Dashboard loads, all eight agents appear ------------------
        r = client.get("/fishbowl/")
        checks.append(("dashboard page loads (200)", r.status_code == 200))
        agent_ids = list(session.scalars(select(Agent.agent_id)))
        checks.append(("eight agents seeded", len(agent_ids) == 8))
        dash = client.get("/fishbowl/api/dashboard").json()
        checks.append(("dashboard API returns all eight agents", len(dash["agents"]) == 8))
        checks.append(
            ("every seeded agent_id appears on the dashboard",
             {a["agent_id"] for a in dash["agents"]} == set(agent_ids)),
        )

        # ---- 1b. World View: persistent per-agent status indicator ---------
        # The 2.5D World View (app/web/static/world/scene.mjs) draws an
        # always-on status chip per agent straight from AgentCard.status —
        # this checks the backend contract that chip depends on, and that
        # the World View page itself is reachable.
        r = client.get("/world/")
        checks.append(("World View page loads (200)", r.status_code == 200))
        checks.append(
            ("every dashboard agent carries a non-empty status label",
             all(isinstance(a.get("status"), str) and a["status"] for a in dash["agents"])),
        )
        checks.append(
            ("all eight agents have a distinct status entry on the dashboard",
             len({a["agent_id"] for a in dash["agents"] if a.get("status")}) == 8),
        )

        # ---- 1d. World View: data-freshness / connection status --------------
        # world.mjs's renderFreshness() shows a fresh / stale / unavailable
        # verdict in the header status line, derived ONLY from real Fishbowl
        # read outcomes (lastPollOk / consecutiveFailures) and the receipt
        # time of the last fully successful snapshot (lastSnapshotAt), via the
        # pure helper in app/web/static/world/freshness.mjs. It must never
        # substitute or invent Village activity when a read fails. These
        # checks pin down that contract from the actually-served assets.
        import json as _json
        import shutil
        import subprocess
        import tempfile

        fresh_res = client.get("/fishbowl/static/world/freshness.mjs")
        world_res = client.get("/fishbowl/static/world/world.mjs")
        checks.append(("freshness.mjs static module is served (200)", fresh_res.status_code == 200))
        checks.append(("world.mjs static module is served (200)", world_res.status_code == 200))
        fsrc = fresh_res.text
        wsrc = world_res.text

        # ---- source-path check: world.mjs sources its verdict from the helper.
        checks.append(("world.mjs imports the freshness verdict helper", "./freshness.mjs" in wsrc))

        # ---- no-fabrication check: the verdict function is pure — it reaches
        # for no Village data source at all, so it structurally cannot
        # substitute or invent activity.
        fsrc_preamble = fsrc.split("export", 1)[0]
        checks.append(
            ("freshness.mjs performs no network reads and imports no data module",
             "fetch(" not in fsrc
             and "adapter.mjs" not in fsrc
             and "scene.mjs" not in fsrc
             and "import " not in fsrc_preamble),
        )

        # ---- behavioural check: run the ACTUAL exported freshness() helper
        # (the exact module the app just served) through Node and assert its
        # three states and every boundary from real return values, not by
        # grepping the source.
        node_bin = shutil.which("node") or next(
            (c for c in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node")
             if Path(c).exists()),
            None,
        )
        checks.append(("a Node runtime is available to execute freshness.mjs", node_bin is not None))

        _driver = """
import {freshness, FRESH_AFTER_MS, STALE_AFTER_MS, FAILURES_BEFORE_UNAVAILABLE}
  from './freshness.mjs';

const now = 1_700_000_000_000;
const at = (ageMs) => now - ageMs;
const cases = {
  // a snapshot that just landed on a successful poll
  recent_success: freshness({now, lastSnapshotAt: at(1000), lastPollOk: true, consecutiveFailures: 0}),
  // that same recent snapshot, but the most recent poll just failed
  success_then_failed_poll: freshness({now, lastSnapshotAt: at(1000), lastPollOk: false, consecutiveFailures: 1}),
  // no fully-successful poll has ever completed
  no_success: freshness({now, lastSnapshotAt: null, lastPollOk: false, consecutiveFailures: 0}),
  // snapshot age exactly at / one ms under the fresh->stale boundary
  fresh_age_exact: freshness({now, lastSnapshotAt: at(FRESH_AFTER_MS), lastPollOk: true, consecutiveFailures: 0}),
  fresh_age_just_under: freshness({now, lastSnapshotAt: at(FRESH_AFTER_MS - 1), lastPollOk: true, consecutiveFailures: 0}),
  // snapshot age exactly at / one ms under the stale->unavailable boundary
  stale_age_exact: freshness({now, lastSnapshotAt: at(STALE_AFTER_MS), lastPollOk: true, consecutiveFailures: 0}),
  stale_age_just_under: freshness({now, lastSnapshotAt: at(STALE_AFTER_MS - 1), lastPollOk: true, consecutiveFailures: 0}),
  // consecutive failures exactly at / one under the unavailable threshold,
  // with a recent snapshot and an otherwise-OK last poll so age plays no part
  failures_exact: freshness({now, lastSnapshotAt: at(1000), lastPollOk: true, consecutiveFailures: FAILURES_BEFORE_UNAVAILABLE}),
  failures_just_under: freshness({now, lastSnapshotAt: at(1000), lastPollOk: true, consecutiveFailures: FAILURES_BEFORE_UNAVAILABLE - 1}),
};
process.stdout.write(JSON.stringify({
  consts: {FRESH_AFTER_MS, STALE_AFTER_MS, FAILURES_BEFORE_UNAVAILABLE},
  cases,
}));
"""

        verdicts: dict = {}
        consts: dict = {}
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _td:
                _tdp = Path(_td)
                (_tdp / "freshness.mjs").write_text(fsrc)
                (_tdp / "driver.mjs").write_text(_driver)
                proc = subprocess.run(
                    [node_bin, str(_tdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            ran_ok = proc.returncode == 0 and proc.stdout.strip() != ""
            checks.append(
                ("the exported freshness() helper executes under Node"
                 + ("" if ran_ok else f" (stderr: {proc.stderr.strip()[:300]})"),
                 ran_ok),
            )
            if ran_ok:
                payload = _json.loads(proc.stdout)
                verdicts = payload["cases"]
                consts = payload["consts"]

        def _state(name: str):
            return (verdicts.get(name) or {}).get("state")

        def _reason(name: str):
            return (verdicts.get(name) or {}).get("reason")

        # Every freshness assertion below runs only against real return values.
        checks.append(("freshness.mjs was actually executed, not just inspected", bool(verdicts)))
        if verdicts:
            checks.append(
                ("thresholds are ordered 0 < FRESH_AFTER_MS < STALE_AFTER_MS",
                 0 < consts["FRESH_AFTER_MS"] < consts["STALE_AFTER_MS"]),
            )

            # ---- the three states, from the three canonical situations.
            checks.append(("recent successful poll -> fresh", _state("recent_success") == "fresh"))
            checks.append(
                ("recent snapshot but last poll failed -> stale",
                 _state("success_then_failed_poll") == "stale"),
            )
            checks.append(
                ("no successful poll ever completed -> unavailable",
                 _state("no_success") == "unavailable" and _reason("no_success") == "no-snapshot"),
            )
            checks.append(
                ("all three verdict states are reachable from real return values",
                 {_state("recent_success"), _state("success_then_failed_poll"), _state("no_success")}
                 == {"fresh", "stale", "unavailable"}),
            )

            # ---- age boundary: exact threshold and just-over both flip state.
            checks.append(
                ("snapshot age exactly at FRESH_AFTER_MS is no longer fresh (-> stale)",
                 _state("fresh_age_exact") == "stale"),
            )
            checks.append(
                ("snapshot age one ms under FRESH_AFTER_MS is still fresh",
                 _state("fresh_age_just_under") == "fresh"),
            )
            checks.append(
                ("snapshot age exactly at STALE_AFTER_MS -> unavailable (snapshot-too-old)",
                 _state("stale_age_exact") == "unavailable"
                 and _reason("stale_age_exact") == "snapshot-too-old"),
            )
            checks.append(
                ("snapshot age one ms under STALE_AFTER_MS is stale, not unavailable",
                 _state("stale_age_just_under") == "stale"),
            )

            # ---- failure-count boundary: exact threshold forces unavailable,
            # attributed to the failing polls (not age); one under does not.
            checks.append(
                ("consecutiveFailures exactly at FAILURES_BEFORE_UNAVAILABLE -> unavailable (polls-failing)",
                 _state("failures_exact") == "unavailable"
                 and _reason("failures_exact") == "polls-failing"),
            )
            checks.append(
                ("consecutiveFailures one under the threshold does not force unavailable",
                 _state("failures_just_under") == "fresh"),
            )

        # world.mjs: the freshness inputs are stamped only from real outcomes.
        wsrc_nospace = wsrc.replace(" ", "")
        checks.append(
            ("world.mjs stamps lastSnapshotAt only after a successful adapter.poll()",
             "lastSnapshotAt=Date.now();lastPollOk=true;consecutiveFailures=0;" in wsrc_nospace),
        )
        checks.append(
            ("world.mjs re-derives freshness on a timer independent of the network poll",
             "setInterval(renderFreshness,3000)" in wsrc_nospace),
        )
        checks.append(
            ("world.mjs no longer conflates provider liveness with connection status",
             "Connected to Village" not in wsrc),
        )
        checks.append(
            ("world.mjs applies a Village snapshot only on the successful poll path",
             wsrc.split("finally{polling=false", 1)[0].count("scene.apply(next)") == 1),
        )

        # The failed-read path must not fabricate anything: no snapshot swap,
        # no scene.apply(), only a downgraded verdict.
        poll_catch = wsrc.split("finally{polling=false", 1)[0].rsplit("catch(e){", 1)[1]
        checks.append(
            ("world.mjs poll() failure path never calls scene.apply()",
             "scene.apply(" not in poll_catch),
        )
        checks.append(
            ("world.mjs poll() failure path never reassigns the snapshot",
             "snapshot=" not in poll_catch.replace(" ", "")),
        )
        checks.append(
            ("world.mjs poll() failure path only downgrades the freshness verdict",
             "consecutiveFailures++" in poll_catch and "renderFreshness()" in poll_catch),
        )

        # The status line is a real, announced live region in the page.
        world_html = client.get("/world/").text
        conn_tag = world_html.split('id="connection"', 1)[1].split(">", 1)[0]
        checks.append(
            ("World View connection status is an announced ARIA live region",
             'id="connection"' in world_html and "aria-live" in conn_tag),
        )

        # ---- 1c. World View: transient conversation-participant connection ---
        # scene.mjs's activeConversationGroups()/drawConnections() draw a
        # transient line only between agents sharing a real, persisted
        # Conversation row — sourced live from ConversationDetail.participants
        # (app/web/api.py's /conversations/{id}) and, during replay, from the
        # CONVERSATION_STARTED/CONVERSATION_JOINED event payload actually
        # replayed — never a guess from proximity or activity text. These
        # checks pin down that backend contract on both sides.
        from app.db.models.conversations import Conversation as ConversationModel

        multi_party_conversations = [
            c for c in session.scalars(select(ConversationModel)) if len(c.participant_ids or []) >= 2
        ]
        checks.append(
            ("at least one persisted conversation has two or more real participants",
             len(multi_party_conversations) > 0),
        )
        if multi_party_conversations:
            sample_conv = multi_party_conversations[0]
            real_participants = set(sample_conv.participant_ids or [])
            conv_api = client.get(f"/fishbowl/api/conversations/{sample_conv.id}").json()
            checks.append(
                ("conversation detail API participants match the real persisted row exactly",
                 {p["agent_id"] for p in conv_api["participants"]} == real_participants),
            )

        # Every agent currently shown in a conversation must carry
        # conversation_partners that are exactly the OTHER real members of
        # that same persisted Conversation row — the field scene.mjs's live
        # (non-replay) connection grouping reads off AgentCard.
        # Whether any conversation is active AT THIS EXACT MOMENT is a timing
        # accident (by the time 6 fixture days finish, every conversation may
        # have already ended) — so this loop verifies the contract wherever
        # it applies, rather than asserting the transient state must exist.
        conversations_by_id = {c.id: c for c in session.scalars(select(ConversationModel))}
        agents_in_conversation = [a for a in dash["agents"] if a.get("conversation_id") is not None]
        for a in agents_in_conversation:
            real_conv = conversations_by_id.get(a["conversation_id"])
            checks.append(
                (f"agent {a['agent_id']}'s conversation_id refers to a real persisted conversation",
                 real_conv is not None),
            )
            if real_conv is not None:
                expected_partners = {p for p in (real_conv.participant_ids or []) if p != a["agent_id"]}
                actual_partners = {p["agent_id"] for p in a.get("conversation_partners", [])}
                checks.append(
                    (f"agent {a['agent_id']}'s conversation_partners match the real conversation's other members",
                     actual_partners == expected_partners),
                )

        # CONVERSATION_STARTED carries a real "participants" list — the exact
        # field scene.mjs's beginItem() reads to form the replay-time
        # connection group for a conversation's opening gather.
        from app.domain.enums import EventType as _EventType

        started_events = list(
            session.scalars(select(Event).where(Event.event_type == _EventType.CONVERSATION_STARTED))
        )
        checks.append(("at least one CONVERSATION_STARTED event was recorded", len(started_events) > 0))
        if started_events:
            sample_started = started_events[0]
            started_conv = session.get(ConversationModel, int(sample_started.entity_id))
            checks.append(
                ("CONVERSATION_STARTED payload's participants match the real conversation it started",
                 started_conv is not None
                 and set((sample_started.payload or {}).get("participants", []))
                 == set(started_conv.participant_ids or [])),
            )

        # ---- 1e. World View: prefers-reduced-motion accessibility -----------
        # scene.mjs already reads matchMedia('(prefers-reduced-motion: reduce)')
        # into this.reduce and uses it to flatten camera easing, freeze the
        # background ambience/idle sway, and fast-forward walking — but two
        # purely decorative animations (the pulsing conversation-connection
        # line and the founder-message screen-tint fade) were never gated by
        # it. These checks pin down that both are now suppressed under
        # reduced motion, and — just as importantly — that this.reduce is
        # never read from the methods that determine persisted-event-derived
        # positions, activity indicators, or replay state, i.e. the fix is
        # animation-only and never suppresses real data.
        scene_res = client.get("/fishbowl/static/world/scene.mjs")
        checks.append(("scene.mjs static module is served (200)", scene_res.status_code == 200))
        ssrc = scene_res.text.replace(" ", "")

        checks.append(
            ("scene.mjs detects prefers-reduced-motion via matchMedia",
             "matchMedia('(prefers-reduced-motion:reduce)').matches" in ssrc),
        )

        # ---- behavioural checks: run the ACTUAL drawConnections() method and
        # the ACTUAL founderTintAlpha() helper (the exact module the app just
        # served) under Node, and assert the real computed values — not by
        # grepping the source for one particular minified spelling of the
        # ternary. scene.mjs imports from adapter.mjs/navigation.mjs, so both
        # are fetched and written alongside it for the driver to resolve.
        adapter_res = client.get("/fishbowl/static/world/adapter.mjs")
        nav_res = client.get("/fishbowl/static/world/navigation.mjs")
        checks.append(("adapter.mjs static module is served (200)", adapter_res.status_code == 200))
        checks.append(("navigation.mjs static module is served (200)", nav_res.status_code == 200))
        checks.append(
            ("scene.mjs exports a founderTintAlpha helper for the founder-tint branch",
             "founderTintAlpha" in ssrc),
        )

        _scene_driver = """
import {WorldScene, founderTintAlpha} from './scene.mjs';

// drawConnections() is called with a fake `this` created off the real
// prototype (Object.create), so activeConversationGroups() and every other
// prototype method resolve exactly as they would on a real instance — no
// constructor, canvas, or matchMedia needed, since we only exercise this one
// method.
const fake = Object.create(WorldScene.prototype);
fake.residents = new Map([
  ['agent_a', {x: 100, y: 200}],
  ['agent_b', {x: 150, y: 220}],
]);
fake.snapshot = {conversations: [{participants: [{agent_id: 'agent_a'}, {agent_id: 'agent_b'}]}]};
fake.playing = null;

const mockCtx = () => {
  const strokes = [];
  return {
    strokes,
    save(){}, restore(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){},
    set strokeStyle(v){ strokes.push(v); }, get strokeStyle(){ return strokes.at(-1); },
    set lineWidth(_v){}, get lineWidth(){ return 1; },
    set lineCap(_v){}, get lineCap(){ return 'round'; },
  };
};

fake.reduce = true;
const reduceA = mockCtx(); fake.drawConnections(reduceA, 0);
const reduceB = mockCtx(); fake.drawConnections(reduceB, 1000);

fake.reduce = false;
const motionA = mockCtx(); fake.drawConnections(motionA, 0);
const motionB = mockCtx(); fake.drawConnections(motionB, 1000);

process.stdout.write(JSON.stringify({
  connectionPulse: {
    reduceStrokes: [reduceA.strokes[0], reduceB.strokes[0]],
    motionStrokes: [motionA.strokes[0], motionB.strokes[0]],
  },
  founderTint: {
    reduceLow: founderTintAlpha(true, 0.9),
    reduceHigh: founderTintAlpha(true, 0.1),
    motionLow: founderTintAlpha(false, 0.9),
    motionHigh: founderTintAlpha(false, 0.1),
  },
}));
"""

        scene_verdicts: dict = {}
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _std:
                _stdp = Path(_std)
                (_stdp / "scene.mjs").write_text(scene_res.text)
                (_stdp / "adapter.mjs").write_text(adapter_res.text)
                (_stdp / "navigation.mjs").write_text(nav_res.text)
                (_stdp / "driver.mjs").write_text(_scene_driver)
                sproc = subprocess.run(
                    [node_bin, str(_stdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            sran_ok = sproc.returncode == 0 and sproc.stdout.strip() != ""
            checks.append(
                ("scene.mjs's drawConnections()/founderTintAlpha() execute under Node"
                 + ("" if sran_ok else f" (stderr: {sproc.stderr.strip()[:300]})"),
                 sran_ok),
            )
            if sran_ok:
                scene_verdicts = _json.loads(sproc.stdout)

        if scene_verdicts:
            pulse = scene_verdicts["connectionPulse"]
            tint = scene_verdicts["founderTint"]

            # ---- connection pulse: constant under reduced motion, but the
            # underlying grouping/drawing indicator (one stroke per real
            # conversation group) still fires — it's only the sine animation
            # that's suppressed, confirmed by contrast against motion-on.
            checks.append(
                ("conversation-connection pulse is drawn at all (real group -> a stroke)",
                 pulse["reduceStrokes"][0] is not None and pulse["motionStrokes"][0] is not None),
            )
            checks.append(
                ("reduced motion: connection pulse opacity is constant across different frame times",
                 pulse["reduceStrokes"][0] == pulse["reduceStrokes"][1] == "rgba(230,212,158,0.5)"),
            )
            checks.append(
                ("motion allowed: connection pulse opacity still varies across different frame times",
                 pulse["motionStrokes"][0] != pulse["motionStrokes"][1]),
            )

            # ---- founder tint: constant/non-fading under reduced motion, but
            # still fades (varies with remaining time) otherwise — same
            # contrast structure, straight off the real exported helper.
            checks.append(
                ("reduced motion: founder tint alpha is constant regardless of time remaining",
                 tint["reduceLow"] == tint["reduceHigh"] == 0.03),
            )
            checks.append(
                ("motion allowed: founder tint alpha still fades with time remaining",
                 tint["motionLow"] != tint["motionHigh"]
                 and tint["motionLow"] == 0.06 * 0.9
                 and tint["motionHigh"] == 0.06 * 0.1),
            )

        def _method_body(start_anchor: str, end_anchor: str) -> str:
            return ssrc.split(start_anchor.replace(" ", ""), 1)[1].split(end_anchor.replace(" ", ""), 1)[0]

        # ---- persisted-event-derived positions / replay state: untouched -----
        for name, start, end in [
            ("apply() (live snapshot -> resident state)", " apply(snapshot){", " isReplaying(){"),
            ("beginItem() (stages one persisted event)", " beginItem(event,now){", " onArrived(p,now){"),
            ("onArrived() (arrival-triggered bubbles/state)", " onArrived(p,now){", " reconcile(){"),
            ("reconcile() (final reconciliation to live snapshot)", " reconcile(){", " advanceQueue(now){"),
            ("advanceQueue() (replay queue progression)", " advanceQueue(now){", " skipToLive(){"),
            ("skipToLive() (jump to live positions)", " skipToLive(){", " frame(now){"),
        ]:
            body = _method_body(start, end)
            checks.append(
                (f"{name} never reads this.reduce — reduced motion never suppresses real state",
                 "this.reduce" not in body),
            )

        # ---- activity indicators / conversation-social visualization: untouched
        conn_body = _method_body(" activeConversationGroups(){", " drawConnections(c,now){")
        checks.append(
            ("activeConversationGroups() (real conversation grouping) never reads this.reduce",
             "this.reduce" not in conn_body),
        )
        wall_body = _method_body(" drawWall(c){", " drawAmbience(c,t){")
        checks.append(
            ("drawWall() (Research Wall / Rabbit Hole pulse activity indicators) never reads this.reduce",
             "this.reduce" not in wall_body),
        )

        # founderTintAlpha() is verified above only as a standalone import —
        # this pins down that production draw() actually calls it for the
        # founder screen tint, not just that the helper exists and behaves.
        draw_body = _method_body(" draw(t){", " drawResident(c,id,a,t){")
        checks.append(
            ("draw() (production render path) actually invokes founderTintAlpha for the founder screen tint",
             "founderTintAlpha(" in draw_body),
        )

        # ---- 1e2. World View: replay pause/resume never drops, duplicates, ---
        # reorders, or invents queued events, and never touches the backend or
        # poll()'s fetching — it only freezes scene.mjs's advanceQueue() from
        # consuming the already-fetched, already-persisted event queue. Run
        # the ACTUAL exported WorldScene class (the exact module the app just
        # served) under Node: enqueue a small fixed batch of events, drive an
        # item into its holding phase, pause, hammer the (mocked)
        # performance.now() forward while paused, then resume and drain the
        # rest — asserting every step off real return values, never source
        # grepping.
        checks.append(
            ("world.mjs wires a click handler to scene.pauseReplay()/resumeReplay()",
             "scene.pauseReplay()" in wsrc and "scene.resumeReplay()" in wsrc),
        )
        replay_pause_tag = world_html.split('id="replay-pause"', 1)[1].split(">", 1)[0]
        checks.append(
            ("the replay pause/resume control is a real, keyboard-focusable <button> with toggle state",
             world_html.split('id="replay-pause"', 1)[0].rstrip().endswith("<button")
             and 'aria-pressed' in replay_pause_tag),
        )

        _pause_driver = """
import {WorldScene} from './scene.mjs';

let clock = 0;
Object.defineProperty(performance, 'now', {value: () => clock, writable: true, configurable: true});

const fake = Object.create(WorldScene.prototype);
fake.residents = new Map([['agent_a', {x: 100, y: 200, path: []}]]);
fake.slots = new Map();
fake.snapshot = {agents: [{agent_id: 'agent_a'}], conversations: []};
fake.playing = null;
fake.queue = [];
fake.speed = 1;
fake.replayDone = 0;
fake.replayTotal = 0;
fake.replayPaused = false;
fake.pauseStartedAt = null;
fake.pulses = new Map();
fake.bubbles = new Map();

const order = [];
const realBeginItem = WorldScene.prototype.beginItem;
fake.beginItem = function (event, now) {
  order.push(event.entity_id);
  return realBeginItem.call(this, event, now);
};

const events = [0, 1, 2, 3].map(i => ({
  event_type: 'RESEARCH_COMPLETED',
  agent_id: 'agent_a',
  entity_id: String(i),
  payload: {finding_count: i, evidence_strength: 'weak'},
}));
fake.enqueue(events);

const step = (deltaMs) => { clock += deltaMs; fake.advanceQueue(clock); };

// Drive the queue until the third event (index 2) is mid-hold.
for (let i = 0; i < 5; i++) step(2000);
const beforePause = {
  order: [...order], queueLen: fake.queue.length, done: fake.replayDone,
  holdStart: fake.playing && fake.playing.holdStart,
};

fake.pauseReplay();
const pausedSnapshot = {
  order: [...order], queueLen: fake.queue.length, done: fake.replayDone,
  playing: JSON.stringify(fake.playing), status: fake.replayStatus(),
};

// Advance the (mocked) clock heavily while paused: must not progress at all.
for (let i = 0; i < 10; i++) step(5000);
const frozenSnapshot = {
  order: [...order], queueLen: fake.queue.length, done: fake.replayDone,
  playing: JSON.stringify(fake.playing),
};

fake.resumeReplay();
const holdStartAfterResume = fake.playing.holdStart;
const statusAfterResume = fake.replayStatus();

// A small step right after resume must NOT complete the resumed hold — its
// full remaining dwell survived the pause, unaffected by the ~50s the tab
// spent paused.
step(50);
const stillHoldingRightAfterResume = fake.playing !== null;

for (let i = 0; i < 20; i++) step(2000);
const finalSnapshot = {
  order: [...order], queueLen: fake.queue.length, done: fake.replayDone,
  total: fake.replayTotal, playing: fake.playing,
};

process.stdout.write(JSON.stringify({
  beforePause, pausedSnapshot, frozenSnapshot,
  holdStartAfterResume, statusAfterResume, stillHoldingRightAfterResume,
  finalSnapshot,
}));
"""
        pause_verdicts: dict = {}
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _ptd:
                _ptdp = Path(_ptd)
                (_ptdp / "scene.mjs").write_text(scene_res.text)
                (_ptdp / "adapter.mjs").write_text(adapter_res.text)
                (_ptdp / "navigation.mjs").write_text(nav_res.text)
                (_ptdp / "driver.mjs").write_text(_pause_driver)
                pproc = subprocess.run(
                    [node_bin, str(_ptdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            pran_ok = pproc.returncode == 0 and pproc.stdout.strip() != ""
            checks.append(
                ("WorldScene's pauseReplay()/resumeReplay()/advanceQueue() execute under Node"
                 + ("" if pran_ok else f" (stderr: {pproc.stderr.strip()[:300]})"),
                 pran_ok),
            )
            if pran_ok:
                pause_verdicts = _json.loads(pproc.stdout)

        if pause_verdicts:
            before = pause_verdicts["beforePause"]
            paused = pause_verdicts["pausedSnapshot"]
            frozen = pause_verdicts["frozenSnapshot"]
            final = pause_verdicts["finalSnapshot"]

            checks.append(
                ("before pausing, the queue was already mid-drain (one item held, none dropped)",
                 before["order"] == ["0", "1", "2"] and before["queueLen"] == 1
                 and before["done"] == 2 and before["holdStart"] is not None),
            )
            checks.append(
                ("pauseReplay() is reflected in replayStatus().paused",
                 paused["status"]["paused"] is True and paused["status"]["active"] is True),
            )
            checks.append(
                ("pausing freezes the queue instantly: no new item consumed, none completed",
                 paused["order"] == before["order"] and paused["queueLen"] == before["queueLen"]
                 and paused["done"] == before["done"]),
            )
            checks.append(
                ("a heavily-advanced clock while paused causes zero progress "
                 "(no drop, no duplicate, no reorder, no early completion)",
                 frozen["order"] == paused["order"] and frozen["queueLen"] == paused["queueLen"]
                 and frozen["done"] == paused["done"] and frozen["playing"] == paused["playing"]),
            )
            checks.append(
                ("resumeReplay() compensates the in-flight hold so its full remaining "
                 "dwell survives the paused interval, rather than being force-completed",
                 pause_verdicts["stillHoldingRightAfterResume"] is True),
            )
            checks.append(
                ("resumeReplay() clears the paused flag in replayStatus()",
                 pause_verdicts["statusAfterResume"]["paused"] is False),
            )
            checks.append(
                ("after resuming, the queue drains to completion with the exact original "
                 "event order — nothing dropped, duplicated, reordered, or invented",
                 final["order"] == ["0", "1", "2", "3"]),
            )
            checks.append(
                ("after resuming, every queued event is accounted for exactly once",
                 final["done"] == final["total"] == 4 and final["queueLen"] == 0
                 and final["playing"] is None),
            )

        # ---- 1f. World View: compact current-activity label ------------------
        # adapter.mjs's activityLabel() reads ONLY AgentCard.current_activity
        # (never the conversation/research-aware AgentCard.status precedence),
        # so scene.mjs's drawLabel() can show a literal, compact reflection of
        # that one persisted field, with a neutral 'Unknown activity' fallback
        # for an absent or malformed value. Run the ACTUAL exported helper
        # (the exact module the app just served) under Node against a real
        # activity string and against every absent/malformed shape.
        label_body = _method_body(" drawLabel(c,id,a){", " activeConversationGroups(){")
        checks.append(
            ("drawLabel() (production render path) resolves its status/activity pills via agentLabelParts",
             "agentLabelParts(" in label_body),
        )

        _activity_driver = """
import {activityLabel} from './adapter.mjs';
process.stdout.write(JSON.stringify({
  real_activity: activityLabel({current_activity: 'reading_a_book'}),
  null_value: activityLabel({current_activity: null}),
  missing_field: activityLabel({}),
  blank_string: activityLabel({current_activity: '   '}),
  malformed_number: activityLabel({current_activity: 42}),
  malformed_object: activityLabel({current_activity: {oops: true}}),
  no_card: activityLabel(null),
}));
"""
        activity_verdicts: dict = {}
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _atd:
                _atdp = Path(_atd)
                (_atdp / "adapter.mjs").write_text(adapter_res.text)
                (_atdp / "driver.mjs").write_text(_activity_driver)
                aproc = subprocess.run(
                    [node_bin, str(_atdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            aran_ok = aproc.returncode == 0 and aproc.stdout.strip() != ""
            checks.append(
                ("adapter.mjs's activityLabel() executes under Node"
                 + ("" if aran_ok else f" (stderr: {aproc.stderr.strip()[:300]})"),
                 aran_ok),
            )
            if aran_ok:
                activity_verdicts = _json.loads(aproc.stdout)

        if activity_verdicts:
            checks.append(
                ("a real current_activity value renders as a compact, readable label",
                 activity_verdicts["real_activity"] == "reading a book"),
            )
            checks.append(
                ("every absent or malformed current_activity value falls back to "
                 "the neutral 'Unknown activity' label, never fabricated text",
                 all(
                     activity_verdicts[case] == "Unknown activity"
                     for case in (
                         "null_value", "missing_field", "blank_string",
                         "malformed_number", "malformed_object", "no_card",
                     )
                 )),
            )

        # ---- 1g. World View: pill de-duplication, max width, truncation ------
        # The clustered-resident "wall of text" fix, all frontend:
        #   * adapter.mjs's agentLabelParts(card) decides what drawLabel()
        #     draws — {state} always, {detail} only when current_activity adds
        #     information beyond status (case/whitespace-insensitive), so an
        #     agent whose status == activity gets ONE pill, not two.
        #   * scene.mjs's clampText(c, text, maxW) bounds every pill's text to
        #     a fixed on-screen width (LABEL_MAX_SCREEN_PX ÷ scale), truncating
        #     with a trailing ellipsis and never returning glyphs wider than
        #     the pill.
        # Both are pure functions of persisted state / the real font metrics —
        # run the ACTUAL exported helpers (the exact modules the app served)
        # under Node and assert real return values.
        checks.append(
            ("scene.mjs exports a clampText helper and a LABEL_MAX_SCREEN_PX cap",
             "clampText" in ssrc and "LABEL_MAX_SCREEN_PX" in ssrc),
        )
        checks.append(
            ("drawLabel() clamps every pill's text to the shared max width",
             "clampText(c,a.card.name,maxLabelW)" in ssrc.replace(" ", "")
             or "clampText(c,nameText" in ssrc.replace(" ", "")
             or "maxLabelW=LABEL_MAX_SCREEN_PX" in ssrc.replace(" ", "")),
        )
        checks.append(
            ("drawLabel() builds the activity pill only when agentLabelParts gives a detail",
             "if(detail&&" in ssrc.replace(" ", "")),
        )

        _label_driver = """
import {agentLabelParts, activityLabel} from './adapter.mjs';
import {clampText, LABEL_MAX_SCREEN_PX} from './scene.mjs';

// Deterministic monospace-ish metric: every glyph is 6 units wide. Enough
// to exercise clampText's boundary behaviour exactly.
const c = {measureText: (t) => ({width: String(t).length * 6})};
const widthOf = (t) => c.measureText(t).width;

const long = 'continuing research conversation; pivoting from search to direct community outreach';
const short = 'morning coffee';
const maxW = 90;  // 15 glyphs

process.stdout.write(JSON.stringify({
  cap_px: LABEL_MAX_SCREEN_PX,
  // --- duplicate suppression
  identical: agentLabelParts({status: 'reading a book', current_activity: 'reading a book'}),
  case_ws_equivalent: agentLabelParts({status: 'Reading A Book', current_activity: 'reading_a_book  '}),
  distinct: agentLabelParts({status: 'in conversation', current_activity: 'debating radio formats'}),
  status_only: agentLabelParts({status: 'resting', current_activity: null}),
  no_status: agentLabelParts({status: null, current_activity: 'writing in journal'}),
  unknown_activity: agentLabelParts({status: 'observing', current_activity: '   '}),
  // --- clampText
  long_clamped: clampText(c, long, maxW),
  long_clamped_width: widthOf(clampText(c, long, maxW)),
  long_ends_ellipsis: clampText(c, long, maxW).endsWith('…'),
  long_keeps_head: long.startsWith(clampText(c, long, maxW).replace(/…$/, '').trimEnd()),
  short_untouched: clampText(c, short, maxW) === short,
  short_no_ellipsis: !clampText(c, short, maxW).includes('…'),
  tiny_cap_bounded: widthOf(clampText(c, long, 6)),
}));
"""
        label_verdicts: dict = {}
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _ltd:
                _ltdp = Path(_ltd)
                (_ltdp / "scene.mjs").write_text(scene_res.text)
                (_ltdp / "adapter.mjs").write_text(adapter_res.text)
                (_ltdp / "navigation.mjs").write_text(nav_res.text)
                (_ltdp / "driver.mjs").write_text(_label_driver)
                lproc = subprocess.run(
                    [node_bin, str(_ltdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            lran_ok = lproc.returncode == 0 and lproc.stdout.strip() != ""
            checks.append(
                ("agentLabelParts()/clampText() execute under Node"
                 + ("" if lran_ok else f" (stderr: {lproc.stderr.strip()[:300]})"),
                 lran_ok),
            )
            if lran_ok:
                label_verdicts = _json.loads(lproc.stdout)

        if label_verdicts:
            lv = label_verdicts
            checks.append(
                ("status == current_activity -> exactly one pill (no activity detail)",
                 lv["identical"]["state"] == "reading a book" and lv["identical"]["detail"] is None),
            )
            checks.append(
                ("case- and whitespace-equivalent status/activity are treated as duplicates",
                 lv["case_ws_equivalent"]["detail"] is None),
            )
            checks.append(
                ("a genuinely distinct status and activity both render",
                 lv["distinct"]["state"] == "in conversation"
                 and lv["distinct"]["detail"] == "debating radio formats"),
            )
            checks.append(
                ("absent current_activity -> status pill only, no fabricated detail",
                 lv["status_only"]["state"] == "resting" and lv["status_only"]["detail"] is None),
            )
            checks.append(
                ("absent status falls back to 'idle' as the state line",
                 lv["no_status"]["state"] == "idle" and lv["no_status"]["detail"] == "writing in journal"),
            )
            checks.append(
                ("a blank/unknown current_activity never becomes an activity detail pill",
                 lv["unknown_activity"]["detail"] is None),
            )
            checks.append(
                ("clampText truncates a long string with a trailing ellipsis",
                 lv["long_ends_ellipsis"] is True and lv["long_clamped"] != ""),
            )
            checks.append(
                ("clampText keeps the useful head of the phrase (it is a real prefix)",
                 lv["long_keeps_head"] is True),
            )
            checks.append(
                ("clampText output never exceeds the max width (bounded geometry)",
                 lv["long_clamped_width"] <= 90 and lv["tiny_cap_bounded"] <= 6 + 6),
            )
            checks.append(
                ("clampText leaves a short string exactly as-is (no ellipsis, no change)",
                 lv["short_untouched"] is True and lv["short_no_ellipsis"] is True),
            )
            checks.append(
                ("the on-screen pill width cap is a sane, sub-'wall of text' value",
                 0 < lv["cap_px"] <= 220),
            )

        # ---- 1g2. drawLabel() geometry under a clustered snapshot ------------
        # Run the ACTUAL WorldScene.prototype.drawLabel() (the served module)
        # for a resident carrying the exact kind of long full-sentence status
        # the visual review flagged, capture every roundRect it emits, and
        # assert: no pill exceeds the on-screen cap (+ its fixed chrome
        # padding) once converted back to screen px, the text drawn inside
        # each pill fits within that pill, and a status==activity resident
        # emits one fewer pill than a distinct one.
        _geom_driver = """
import {WorldScene, clampText, LABEL_MAX_SCREEN_PX} from './scene.mjs';

const long = 'continuing research conversation; pivoting from search to direct community outreach';
const CARDS = {
  agent_optimisto: {name: 'Optimisto', status: 'sipping espresso', current_activity: long, current_location: 'espresso_counter'},
  agent_vince: {name: 'Vince', status: 'people-watching', current_activity: 'morning coffee and observation', current_location: 'espresso_counter'},
  agent_alien: {name: 'The Alien', status: 'listening', current_activity: 'listening in on the debate', current_location: 'espresso_counter'},
};

// `residents` is a Map of id -> {x, y, card}; drawLabel reads x/y off it for
// the cluster cascade and card off the per-call `a`. Build one fake scene
// and draw every resident through the real prototype method.
function scene(positions, scale, selected) {
  const fake = Object.create(WorldScene.prototype);
  fake.scale = scale;
  fake.selected = selected || null;
  fake.frames = Array.from({length: 8}, () => ({w: 120, h: 200}));
  fake.hit = [];
  fake.residents = new Map(Object.entries(positions).map(([id, p]) => [id, {...p, card: CARDS[id]}]));
  const draw = (id) => {
    const rects = [], texts = [];
    let font = '';
    const c = {
      save(){}, restore(){}, beginPath(){}, fill(){}, stroke(){}, ellipse(){},
      translate(){}, scale(){}, rotate(){}, drawImage(){}, moveTo(){}, lineTo(){},
      set font(v){ font = v; }, get font(){ return font; },
      set fillStyle(_v){}, get fillStyle(){ return '#000'; },
      set strokeStyle(_v){}, get strokeStyle(){ return '#000'; },
      set lineWidth(_v){}, get lineWidth(){ return 1; },
      set textAlign(_v){}, get textAlign(){ return 'center'; },
      measureText: (t) => ({width: String(t).length * 6}),
      roundRect(x, y, w, h, r){ rects.push({x, y, w, h, r}); },
      fillText(t, x, y){ texts.push({t, x, y, w: String(t).length * 6}); },
    };
    const r = fake.residents.get(id);
    WorldScene.prototype.drawLabel.call(fake, c, id, {x: r.x, y: r.y, card: r.card});
    return {rects, texts};
  };
  return {fake, draw};
}

// solo resident, distinct status/activity -> 3 pills (name + state + detail)
const solo = scene({agent_optimisto: {x: 500, y: 400}}, 1).draw('agent_optimisto');
// solo resident, status == activity -> 2 pills (activity detail suppressed)
const soloDup = (() => {
  const s = scene({agent_optimisto: {x: 500, y: 400}}, 1);
  s.fake.residents.get('agent_optimisto').card = {name: 'Optimisto', status: long, current_activity: long};
  return s.draw('agent_optimisto');
})();
// three residents sharing one zone but spread ~150 world px apart — too far
// for the proximity fallback, so this exercises the current_location group.
const CLUSTER_POS = {agent_optimisto: {x: 400, y: 400}, agent_vince: {x: 550, y: 402}, agent_alien: {x: 700, y: 401}};
const clusterScene = scene(CLUSTER_POS, 1);
const cO = clusterScene.draw('agent_optimisto');
const cV = clusterScene.draw('agent_vince');
const cA = clusterScene.draw('agent_alien');
// same cluster, but Vince is the selected resident
const cVsel = scene(CLUSTER_POS, 1, 'agent_vince').draw('agent_vince');
const zoomed = scene({agent_optimisto: {x: 500, y: 400}}, 2.3).draw('agent_optimisto');

const topY = (res) => Math.min(...res.rects.map(r => r.y));

process.stdout.write(JSON.stringify({
  cap: LABEL_MAX_SCREEN_PX,
  soloPillCount: solo.rects.length,
  soloDupPillCount: soloDup.rects.length,
  clusterNonSelPillCounts: [cO.rects.length, cV.rects.length, cA.rects.length],
  clusterSelectedPillCount: cVsel.rects.length,
  // the cascade: each successive clustered label starts lower than the last
  cascadeTopYs: [topY(cO), topY(cV), topY(cA)],
  cascadeStrictlyDescending: topY(cO) < topY(cV) && topY(cV) < topY(cA),
  widestScreenPx: Math.max(...solo.rects.map(r => r.w)) * 1,
  zoomedWidestScreenPx: Math.max(...zoomed.rects.map(r => r.w)) * 2.3,
  soloTextFits: solo.texts.every((t, i) => t.w <= solo.rects[i].w),
  clusterTextFits: [cO, cV, cA].every(res => res.texts.every((t, i) => t.w <= res.rects[i].w)),
}));
"""
        geom_verdicts: dict = {}
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _gtd:
                _gtdp = Path(_gtd)
                (_gtdp / "scene.mjs").write_text(scene_res.text)
                (_gtdp / "adapter.mjs").write_text(adapter_res.text)
                (_gtdp / "navigation.mjs").write_text(nav_res.text)
                (_gtdp / "driver.mjs").write_text(_geom_driver)
                gproc = subprocess.run(
                    [node_bin, str(_gtdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            gran_ok = gproc.returncode == 0 and gproc.stdout.strip() != ""
            checks.append(
                ("WorldScene.drawLabel() executes under Node with a clustered snapshot"
                 + ("" if gran_ok else f" (stderr: {gproc.stderr.strip()[:300]})"),
                 gran_ok),
            )
            if gran_ok:
                geom_verdicts = _json.loads(gproc.stdout)

        if geom_verdicts:
            gv = geom_verdicts
            checks.append(
                ("a solo resident with distinct status/activity draws 3 pills; "
                 "status==activity draws 2 (activity detail suppressed)",
                 gv["soloPillCount"] == 3 and gv["soloDupPillCount"] == 2),
            )
            checks.append(
                ("clustered non-selected residents drop the activity-detail row (name + state only)",
                 gv["clusterNonSelPillCounts"] == [2, 2, 2]),
            )
            checks.append(
                ("the selected resident keeps its activity-detail row even inside a cluster",
                 gv["clusterSelectedPillCount"] == 3),
            )
            checks.append(
                ("clustered labels cascade downward — each starts strictly below the previous",
                 gv["cascadeStrictlyDescending"] is True
                 and gv["cascadeTopYs"] == sorted(gv["cascadeTopYs"])),
            )
            checks.append(
                ("no drawLabel pill exceeds the on-screen cap plus its fixed chrome, at scale 1",
                 gv["widestScreenPx"] <= gv["cap"] + 24),
            )
            checks.append(
                ("the on-screen pill width stays bounded when zoomed in (scale 2.3)",
                 gv["zoomedWidestScreenPx"] <= gv["cap"] + 60),
            )
            checks.append(
                ("every string drawLabel() renders sits within its own pill — no overflow, "
                 "solo or clustered",
                 gv["soloTextFits"] is True and gv["clusterTextFits"] is True),
            )

        # ---- 1h. World View: top-right HUD stays inside the viewport --------
        # The clock / connection / replay-control column (.top-right, inside
        # .mast) must never clip past the right edge or overlap the wordmark
        # at a narrow desktop width. The fix is pure CSS: the mast wraps, the
        # column may shrink to nothing (min-width:0) and drop to its own row,
        # and the replay bar wraps its buttons rather than overflowing.
        # jsdom has no layout engine, so these are served-asset contract
        # checks; the pixel-level behaviour is covered by the Playwright
        # sweep at 1520/1280/1024/900 px in the change's manual verification.
        css_res = client.get("/fishbowl/static/world/world.css")
        checks.append(("world.css static asset is served (200)", css_res.status_code == 200))
        css = css_res.text
        css_ns = css.replace(" ", "").replace("\n", "")
        checks.append(
            ("world.css lets the mast wrap so the top-right column can drop to its own row",
             ".mast{flex-wrap:wrap" in css_ns),
        )
        checks.append(
            ("world.css lets the top-right column shrink instead of forcing overflow",
             ".top-right{min-width:0" in css_ns),
        )
        checks.append(
            ("world.css lets the replay bar wrap its controls onto extra rows",
             "#replay-bar{flex-wrap:wrap" in css_ns),
        )
        checks.append(
            ("world.css lets the replay status text wrap rather than force a wide nowrap box",
             "#replay-status{white-space:normal" in css_ns),
        )
        # No control is removed or display:none'd to make it fit — every
        # replay/HUD control still ships in the template and stays a real
        # focusable element.
        world_html_now = client.get("/world/").text
        for _cid in ("replay-status", "replay-pause", "skip-live"):
            checks.append(
                (f"world.html still ships the '{_cid}' control (nothing hidden to fit)",
                 f'id="{_cid}"' in world_html_now),
            )
        for _spd in ("1", "2", "4"):
            checks.append(
                (f"world.html still ships the {_spd}x replay-speed button",
                 f'data-speed="{_spd}"' in world_html_now),
            )
        checks.append(
            ("world.css never hides a replay control with display:none to fit",
             "#replay-status{display:none" not in css_ns
             and "#skip-live{display:none" not in css_ns
             and "#replay-pause{display:none" not in css_ns),
        )

        # ---- 1i. World View: every control actually has a live click handler -
        # Presence + focusability is not enough — assert the served world.mjs
        # binds a handler to each control and routes it to the right scene
        # method / control() call, and that scene.mjs actually exports those
        # methods so the handler can't be a silent no-op. (Backend behaviour
        # of the founder controls is covered by section 5's live-control
        # checks below.)
        wsrc_ns = wsrc.replace(" ", "").replace("\n", "")
        checks.append(
            ("world.mjs binds a click handler to every camera control (zoom-in/out, reset, sound)",
             "$('zoom-in').onclick=" in wsrc and "$('zoom-out').onclick=" in wsrc
             and "$('reset').onclick=" in wsrc and "$('sound').onclick=" in wsrc),
        )
        checks.append(
            ("world.mjs zoom / reset handlers call the real WorldScene methods",
             "scene.zoom(" in wsrc and "scene.reset()" in wsrc),
        )
        checks.append(
            ("world.mjs binds the replay pause/resume handler and routes it to "
             "scene.pauseReplay()/resumeReplay()",
             "$('replay-pause').onclick=" in wsrc
             and "scene.resumeReplay()" in wsrc and "scene.pauseReplay()" in wsrc),
        )
        checks.append(
            ("world.mjs binds every .speed-btn to scene.setSpeed(Number(dataset.speed))",
             ".speed-btn')" in wsrc
             and "scene.setSpeed(Number(b.dataset.speed))" in wsrc_ns),
        )
        checks.append(
            ("world.mjs binds #skip-live to scene.skipToLive()",
             "$('skip-live').onclick=()=>scene.skipToLive()" in wsrc_ns),
        )
        checks.append(
            ("world.mjs binds every [data-control] founder button to control(dataset.control)",
             "document.querySelectorAll('[data-control]'))b.onclick=()=>control(b.dataset.control)" in wsrc_ns),
        )
        checks.append(
            ("world.mjs binds #message-open to open the message dialog",
             "$('message-open').onclick=" in wsrc),
        )
        checks.append(
            ("scene.mjs exports the methods those handlers call (no silent no-ops)",
             all(f" {m}(" in scene_res.text for m in
                 ("zoom", "reset", "setSpeed", "skipToLive", "pauseReplay", "resumeReplay"))),
        )
        # The only thing that disables a control is the documented busy /
        # no-snapshot / stale gate — never a stray always-true disable.
        checks.append(
            ("world.mjs only disables controls on the busy || !snapshot || scene.stale gate",
             "b.disabled=busy||!snapshot||scene.stale" in wsrc_ns),
        )

        _ctl_driver = """
import {WorldScene} from './scene.mjs';
const s = Object.create(WorldScene.prototype);
s.camera = {x: 768, y: 515, zoom: 1};
s.target = {x: 768, y: 515, zoom: 1};
s.follow = 'agent_sol';
s.queue = [{}, {}];
s.playing = {};
s.replayDone = 3; s.replayTotal = 9; s.speed = 1; s.replayPaused = false; s.pauseStartedAt = null;
s.snapshot = null;

// setSpeed
s.setSpeed(4);
const speedSet = s.speed === 4;
// zoom is clamped, reset recentres and drops follow
s.zoom(1.15); const zoomedIn = s.target.zoom > 1;
s.zoom(0.0001); const zoomClamped = s.target.zoom >= 0.6;  // clamp floor
s.reset(); const resetDroppedFollow = s.follow === null && s.target.zoom === 1;
// pauseReplay flips the flag; advanceQueue respects it
Object.defineProperty(performance, 'now', {value: () => 1000, writable: true, configurable: true});
s.pauseReplay(); const paused = s.replayPaused === true;
s.resumeReplay(); const resumed = s.replayPaused === false;

process.stdout.write(JSON.stringify({speedSet, zoomedIn, zoomClamped, resetDroppedFollow, paused, resumed}));
"""
        ctl_verdicts: dict = {}
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _ctd:
                _ctdp = Path(_ctd)
                (_ctdp / "scene.mjs").write_text(scene_res.text)
                (_ctdp / "adapter.mjs").write_text(adapter_res.text)
                (_ctdp / "navigation.mjs").write_text(nav_res.text)
                (_ctdp / "driver.mjs").write_text(_ctl_driver)
                cproc = subprocess.run(
                    [node_bin, str(_ctdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            cran_ok = cproc.returncode == 0 and cproc.stdout.strip() != ""
            checks.append(
                ("the WorldScene control methods execute under Node"
                 + ("" if cran_ok else f" (stderr: {cproc.stderr.strip()[:300]})"),
                 cran_ok),
            )
            if cran_ok:
                ctl_verdicts = _json.loads(cproc.stdout)

        if ctl_verdicts:
            cv = ctl_verdicts
            checks.append(("setSpeed(4) actually sets scene.speed to 4", cv["speedSet"] is True))
            checks.append(("zoom(1.15) actually raises the camera target zoom", cv["zoomedIn"] is True))
            checks.append(("zoom() clamps to a sane floor rather than going to ~0", cv["zoomClamped"] is True))
            checks.append(
                ("reset() recentres the camera and drops any followed resident",
                 cv["resetDroppedFollow"] is True),
            )
            checks.append(("pauseReplay() sets the paused flag", cv["paused"] is True))
            checks.append(("resumeReplay() clears the paused flag", cv["resumed"] is True))

        # ---- 1j. World View: responsive composition (world dominance) --------
        # The clubhouse is the primary content: WorldScene.resize() sizes it to
        # COVER the usable frame (viewport minus only the gutters the UI needs),
        # and below 1200px the roster collapses to a drawer so the room takes
        # that width back. Run the ACTUAL served resize() across representative
        # viewports under Node and assert the room stays dominant, keeps its
        # aspect ratio, uses height as well as width, and never crops its
        # horizontal edges past the safe margin.
        checks.append(
            ("world.css ships the roster-drawer composition rules",
             "roster drawer" in css_ns.lower() or ".roster-toggle{" in css_ns),
        )
        checks.append(
            ("world.html ships the roster drawer toggle + scrim",
             'id="roster-toggle"' in world_html_now and 'id="roster-scrim"' in world_html_now),
        )
        checks.append(
            ("world.mjs wires the roster drawer toggle and closes it on select",
             "$('roster-toggle').onclick" in wsrc and "setRosterOpen(false)" in wsrc),
        )
        checks.append(
            ("scene.mjs resize() sizes the room to cover the frame (no plain fit-with-margins)",
             "Math.max(this.roomBox.w/W,this.roomBox.h/H)" in scene_res.text.replace(" ", "")
             and "rosterDocked" in scene_res.text),
        )

        _resp_driver = """
import {WorldScene} from './scene.mjs';
const W=1536, H=1024;

function box(vw, vh){
  global.innerWidth = vw; global.innerHeight = vh; global.devicePixelRatio = 1;
  const s = Object.create(WorldScene.prototype);
  s.canvas = {width:0, height:0, getContext(){return {};}};
  s.camera = {x:768, y:515, zoom:1};
  s.resize();
  // replicate draw()'s framing math (the part that positions the room)
  const scale = s.baseScale * s.camera.zoom;
  const f = s.roomBox;
  const cropY = Math.max(0, H*scale - f.h);
  const offX = f.x + f.w/2 - s.camera.x*scale;
  const offY = f.y + f.h/2 + 12 - s.camera.y*scale - cropY*0.42;
  const roomW = W*scale, roomH = H*scale;
  // every zone spot lies within x∈[120,1400], y∈[300,960]; check the extremes
  const corners = [[120,300],[1400,300],[120,960],[1400,960]];
  const cornersOnScreen = corners.every(([wx,wy]) => {
    const sx = offX + wx*scale, sy = offY + wy*scale;
    return sx > -30 && sx < vw+30 && sy > -30 && sy < vh+30;
  });
  return {
    vw, vh, rosterDocked: s.rosterDocked, baseScale: s.baseScale, scale,
    roomBox: s.roomBox,
    roomW, roomH,
    aspect: roomW / roomH,
    areaPctViewport: (roomW*roomH)/(vw*vh)*100,
    // fraction of the usable frame the room covers in each axis
    coversW: roomW / f.w, coversH: roomH / f.h,
    horizCropPerEdgePct: Math.max(0, (roomW - f.w)/2) / W * 100,
    cornersOnScreen,
  };
}

const vps = [[1920,1080],[1520,900],[1280,800],[1100,800],[900,700]];
process.stdout.write(JSON.stringify(vps.map(([w,h]) => box(w,h))));
"""
        resp_verdicts: list = []
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _rtd:
                _rtdp = Path(_rtd)
                (_rtdp / "scene.mjs").write_text(scene_res.text)
                (_rtdp / "adapter.mjs").write_text(adapter_res.text)
                (_rtdp / "navigation.mjs").write_text(nav_res.text)
                (_rtdp / "driver.mjs").write_text(_resp_driver)
                rproc = subprocess.run(
                    [node_bin, str(_rtdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            rran_ok = rproc.returncode == 0 and rproc.stdout.strip() != ""
            checks.append(
                ("scene.mjs resize() executes under Node across viewports"
                 + ("" if rran_ok else f" (stderr: {rproc.stderr.strip()[:300]})"),
                 rran_ok),
            )
            if rran_ok:
                resp_verdicts = _json.loads(rproc.stdout)

        if resp_verdicts:
            for v in resp_verdicts:
                tag = f"{v['vw']}x{v['vh']}"
                checks.append(
                    (f"{tag}: room aspect ratio is preserved (3:2, no distortion)",
                     abs(v["aspect"] - 1536 / 1024) < 0.001),
                )
                checks.append(
                    (f"{tag}: room covers the usable frame in at least one axis "
                     "(no fit-with-margins shrink)",
                     v["coversW"] >= 0.999 or v["coversH"] >= 0.999),
                )
                checks.append(
                    (f"{tag}: room occupies a dominant share of the viewport (>=70% area)",
                     v["areaPctViewport"] >= 70),
                )
                checks.append(
                    (f"{tag}: every zone's residents stay on screen (horizontal crop <= 14%/edge)",
                     v["cornersOnScreen"] is True and v["horizCropPerEdgePct"] <= 14.01),
                )
            # the roster only holds width on wide screens; below 1200 it is a drawer
            docked = {f"{v['vw']}x{v['vh']}": v["rosterDocked"] for v in resp_verdicts}
            checks.append(
                ("roster stays docked at >=1200px and becomes a drawer below it",
                 docked["1920x1080"] and docked["1520x900"] and docked["1280x800"]
                 and not docked["1100x800"] and not docked["900x700"]),
            )
            # height genuinely participates: the two 800px-tall viewports differ
            # in room height only because their widths differ, and the short
            # 900x700 frame yields a smaller room than the wide ones
            heights = {f"{v['vw']}x{v['vh']}": v["roomH"] for v in resp_verdicts}
            checks.append(
                ("scene sizing is height-aware (900x700 room is shorter than 1920x1080)",
                 heights["900x700"] < heights["1920x1080"]),
            )

        # ---- 1k. World View: render-layer ordering (environment vs character)
        # Environmental signage ("RESEARCH WALL", "RABBIT HOLES", the
        # conversations plaque) is painted INTO the room and must sit BELOW
        # the moving characters and every piece of character UI. Instrument
        # the canvas 2D context, run the ACTUAL served draw() once with a
        # resident standing on the Research Wall plaque, and assert the real
        # emitted op sequence is: room art -> environment label -> character
        # sprite -> character name/activity -> speech bubble. Also assert the
        # click hit-test now resolves that overlap to the resident.
        _layer_driver = """
import {WorldScene} from './scene.mjs';

const scene = Object.create(WorldScene.prototype);
scene.room = {__tag:'room'};
scene.atlas = {__tag:'atlas'};
scene.frames = Array.from({length:8}, () => ({x:0,y:0,w:120,h:200}));
scene.width = 1536; scene.height = 1024; scene.dpr = 1;
scene.scale = 1; scene.baseScale = 1;
scene.roomBox = {x:0, y:0, w:1536, h:1024};
scene.camera = {x:768, y:515, zoom:1};
scene.reduce = true;
scene.founderCueUntil = 0;
scene.playing = null;
scene.selected = null;
scene.hit = [];
scene.bubbles = new Map();
scene.pulses = new Map();
scene.slots = new Map();
// one resident standing exactly on the RESEARCH WALL plaque (1045,258) and
// speaking, so sprite, name label and speech bubble all overlap the sign
scene.residents = new Map([
  ['agent_optimisto', {x:1045, y:258, path:[], face:1, phase:0, walking:false,
    card:{name:'Optimisto', status:'presenting a finding', current_activity:'presenting a finding',
          current_location:'research_wall', motion:'idle', current_research_id:null}}],
]);
scene.bubbles.set('agent_optimisto', {text:'Here is what I found', kind:'speech', detail:null, until:1e15});
scene.snapshot = {
  dashboard:{clock:{period:'MORNING'}},
  wall:[], holes:[],
  conversations:[{id:1, participants:[{agent_id:'agent_optimisto'},{agent_id:'agent_vince'}], status:'ACTIVE', message_count:1}],
};

const ops = [];
const grad = {addColorStop(){}};
const ctx = {
  setTransform(){}, save(){}, restore(){}, translate(){}, scale(){}, rotate(){},
  beginPath(){}, closePath(){}, moveTo(){}, lineTo(){}, arc(){}, ellipse(){},
  roundRect(){}, rect(){}, clip(){}, fill(){}, stroke(){}, strokeRect(){},
  fillRect(){}, bezierCurveTo(){}, quadraticCurveTo(){}, arcTo(){},
  createRadialGradient(){ return grad; }, createLinearGradient(){ return grad; },
  createPattern(){ return null; },
  measureText:(t)=>({width:String(t).length*6}),
  set font(v){}, get font(){return '10px system-ui';},
  set fillStyle(v){}, get fillStyle(){return '#000';},
  set strokeStyle(v){}, get strokeStyle(){return '#000';},
  set lineWidth(v){}, get lineWidth(){return 1;},
  set lineCap(v){}, get lineCap(){return 'round';},
  set lineJoin(v){}, get lineJoin(){return 'round';},
  set textAlign(v){}, get textAlign(){return 'center';},
  set textBaseline(v){}, get textBaseline(){return 'alphabetic';},
  set globalAlpha(v){}, get globalAlpha(){return 1;},
  set globalCompositeOperation(v){}, get globalCompositeOperation(){return 'source-over';},
  set shadowBlur(v){}, get shadowBlur(){return 0;},
  set shadowColor(v){}, get shadowColor(){return '#000';},
  drawImage(img){ ops.push({op:'img', tag: img && img.__tag}); },
  fillText(txt){ ops.push({op:'text', text:String(txt)}); },
  strokeText(txt){ ops.push({op:'text', text:String(txt)}); },
};
scene.ctx = ctx;

scene.draw(0);

const first = (pred) => ops.findIndex(pred);
const iRoom   = first(o => o.op==='img' && o.tag==='room');
const iWall   = first(o => o.op==='text' && o.text==='RESEARCH WALL');
const iHoles  = first(o => o.op==='text' && o.text==='RABBIT HOLES');
const iConv   = first(o => o.op==='text' && /CONVERSATION/.test(o.text));
const iSprite = first(o => o.op==='img' && o.tag==='atlas');
const iName   = first(o => o.op==='text' && o.text==='Optimisto');
const iActivity = ops.map((o,ix)=>({o,ix})).filter(x=>x.o.op==='text' && /presenting a finding/.test(x.o.text)).map(x=>x.ix);
const iBubble = first(o => o.op==='text' && /Here is what I found/.test(o.text));

// hit-test: with the resident on the plaque, the reverse scan the click
// handler runs (`[...this.hit].reverse().find(...)`) must land on the agent
const reversed = [...scene.hit].reverse();
const hitAtPlaque = reversed.find(h => 1045 >= h.x && 1045 <= h.x + h.w && 258 >= h.y && 258 <= h.y + (h.h||0));

process.stdout.write(JSON.stringify({
  totalOps: ops.length,
  iRoom, iWall, iHoles, iConv, iSprite, iName, iActivity, iBubble,
  hitKindAtPlaque: hitAtPlaque ? hitAtPlaque.kind : null,
  wallHitPresent: scene.hit.some(h => h.kind === 'wall'),
}));
"""
        layer_verdict: dict = {}
        if node_bin is not None:
            with tempfile.TemporaryDirectory() as _ltd:
                _ltdp = Path(_ltd)
                (_ltdp / "scene.mjs").write_text(scene_res.text)
                (_ltdp / "adapter.mjs").write_text(adapter_res.text)
                (_ltdp / "navigation.mjs").write_text(nav_res.text)
                (_ltdp / "driver.mjs").write_text(_layer_driver)
                lproc = subprocess.run(
                    [node_bin, str(_ltdp / "driver.mjs")],
                    capture_output=True, text=True, timeout=30,
                )
            lran_ok = lproc.returncode == 0 and lproc.stdout.strip() != ""
            checks.append(
                ("scene.mjs draw() executes under an instrumented 2D context"
                 + ("" if lran_ok else f" (stderr: {lproc.stderr.strip()[:400]})"),
                 lran_ok),
            )
            if lran_ok:
                layer_verdict = _json.loads(lproc.stdout)

        if layer_verdict:
            lv = layer_verdict
            checks.append(
                ("draw() emits an image+text op stream and finds every layer landmark",
                 lv["totalOps"] >= 10 and min(lv["iRoom"], lv["iWall"], lv["iHoles"],
                                              lv["iConv"], lv["iSprite"], lv["iName"],
                                              lv["iBubble"]) >= 0 and bool(lv["iActivity"])),
            )
            checks.append(
                ("environment art (room image) is painted before any location label",
                 lv["iRoom"] < lv["iWall"] and lv["iRoom"] < lv["iHoles"]),
            )
            checks.append(
                ("RESEARCH WALL label is painted BEFORE the character sprite (it can be occluded)",
                 lv["iWall"] < lv["iSprite"]),
            )
            checks.append(
                ("RABBIT HOLES label is painted BEFORE the character sprite",
                 lv["iHoles"] < lv["iSprite"]),
            )
            checks.append(
                ("the conversations plaque is painted BEFORE the character sprite",
                 lv["iConv"] >= 0 and lv["iConv"] < lv["iSprite"]),
            )
            checks.append(
                ("the character sprite is painted BEFORE its name label (character UI on top)",
                 lv["iSprite"] < lv["iName"]),
            )
            checks.append(
                ("the character sprite is painted BEFORE its activity label",
                 bool(lv["iActivity"]) and lv["iSprite"] < min(lv["iActivity"])),
            )
            checks.append(
                ("the character sprite is painted BEFORE its speech bubble",
                 lv["iSprite"] < lv["iBubble"]),
            )
            checks.append(
                ("full stack order holds: room < location label < sprite < name < speech",
                 lv["iRoom"] < lv["iWall"] < lv["iSprite"] < lv["iName"] < lv["iBubble"]),
            )
            checks.append(
                ("a resident standing on the Research Wall sign resolves the click to the resident",
                 lv["wallHitPresent"] is True and lv["hitKindAtPlaque"] == "agent"),
            )

        # ---- 2. Event feed reads real event rows --------------------------
        feed = client.get("/fishbowl/api/events?limit=20").json()
        checks.append(("event feed returns events", len(feed["events"]) > 0))
        feed_ids = {e["id"] for e in feed["events"]}
        real_ids_matching = set(session.scalars(select(Event.id).where(Event.id.in_(feed_ids))))
        checks.append(("every feed event id is a real row in `events`", feed_ids == real_ids_matching))

        # ---- 3. Agent detail reads real stored data ------------------------
        sample_agent = agent_ids[0]
        detail = client.get(f"/fishbowl/api/agents/{sample_agent}").json()
        checks.append(("agent detail returns the requested agent_id", detail["agent_id"] == sample_agent))
        from app.db.models.agents import Agent as AgentModel

        real_agent = session.scalars(select(AgentModel).where(AgentModel.agent_id == sample_agent)).one()
        checks.append(("agent detail identity matches the real seeded row", detail["identity"] == real_agent.identity))
        r = client.get(f"/fishbowl/agents/{sample_agent}")
        checks.append(("agent detail page loads (200)", r.status_code == 200))

        # ---- 4. Research provenance renders from real fixture records -----
        checks.append(("at least one research session exists to test against", research_count > 0))
        if research_count > 0:
            rid = session.scalars(select(ResearchSession.research_id).limit(1)).first()
            rd = client.get(f"/fishbowl/api/research/{rid}").json()
            checks.append(("research detail question matches a real row", bool(rd["question"])))
            checks.append(
                ("research provenance chain has at least one query, source, or finding",
                 bool(rd["queries"] or rd["sources"] or rd["findings"])),
            )
            r = client.get(f"/fishbowl/research/{rid}")
            checks.append(("research detail page loads (200)", r.status_code == 200))
        r = client.get("/fishbowl/research")
        checks.append(("research list page loads (200)", r.status_code == 200))

        # ---- 5. Research Wall renders ---------------------------------------
        r = client.get("/fishbowl/wall")
        checks.append(("Research Wall page loads (200)", r.status_code == 200))
        wall_api = client.get("/fishbowl/api/wall").json()
        checks.append(("Research Wall API returns a list", isinstance(wall_api["posts"], list)))

        # ---- 6. Rabbit Holes render -----------------------------------------
        r = client.get("/fishbowl/rabbit-holes")
        checks.append(("Rabbit Holes page loads (200)", r.status_code == 200))
        if rabbit_hole_count > 0:
            hid = session.scalars(select(RabbitHole.id).limit(1)).first()
            r = client.get(f"/fishbowl/rabbit-holes/{hid}")
            checks.append(("Rabbit Hole detail page loads (200)", r.status_code == 200))
            rh_api = client.get(f"/fishbowl/api/rabbit-holes/{hid}").json()
            checks.append(("Rabbit Hole detail has a real title", bool(rh_api["title"])))

        # ---- 7. Founder Report renders --------------------------------------
        checks.append(("at least one Founder report was generated", report_count > 0))
        if report_count > 0:
            day = session.scalars(select(DailyReport.day_number).limit(1)).first()
            r = client.get(f"/fishbowl/reports/{day}")
            checks.append(("Founder report detail page loads (200)", r.status_code == 200))
            rep_api = client.get(f"/fishbowl/api/reports/{day}").json()
            checks.append(("Founder report summary_text is non-empty", bool(rep_api["summary_text"])))
        r = client.get("/fishbowl/reports")
        checks.append(("Founder reports list page loads (200)", r.status_code == 200))

        # ---- 8. Usage telemetry renders --------------------------------------
        tel = client.get("/fishbowl/api/telemetry").json()
        checks.append(("telemetry shows LLM calls", tel["llm_total_calls"] > 0))
        checks.append(
            ("telemetry LLM total calls matches the real llm_runs table",
             tel["llm_total_calls"] == llm_run_count_before),
        )
        r = client.get("/fishbowl/telemetry")
        checks.append(("telemetry page loads (200)", r.status_code == 200))

        # ---- 9. Fixture/live indicators are correct --------------------------
        checks.append(("dashboard reports LLM provider as fixture", dash["providers"]["llm_is_live"] is False))
        checks.append(("dashboard reports research provider as fixture", dash["providers"]["research_is_live"] is False))
        checks.append(
            ("every recent LLM run is flagged is_fixture", all(run["is_fixture"] for run in tel["recent_llm_runs"])),
        )

        # ---- 10/11. Read-only polling never touches a provider ----------------
        # app/web/reads.py, api.py, pages.py must never import a provider
        # module at all — checked structurally (not just "count didn't move",
        # which a lazy import could still satisfy).
        import inspect

        import app.web.api as fb_api
        import app.web.pages as fb_pages
        import app.web.reads as fb_reads

        def _imports_a_provider(module) -> bool:
            """Parses the module's actual import statements (via ast) rather
            than substring-matching the raw source — a docstring is allowed
            to *mention* app.providers.llm/research while explaining why the
            module doesn't import it; only a real import statement counts."""
            import ast

            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(alias.name.startswith("app.providers.") for alias in node.names):
                        return True
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("app.providers."):
                        return True
            return False

        checks.append(
            ("app/web/reads.py never imports a provider module", not _imports_a_provider(fb_reads)),
        )
        checks.append(
            ("app/web/api.py never imports a provider module", not _imports_a_provider(fb_api)),
        )
        checks.append(
            ("app/web/pages.py never imports a provider module", not _imports_a_provider(fb_pages)),
        )

        llm_before = session.scalar(select(func.count(LLMRun.id))) or 0
        research_before = session.scalar(select(func.count(ResearchProviderUsage.id))) or 0
        for _ in range(3):
            client.get("/fishbowl/")
            client.get("/fishbowl/api/dashboard")
            client.get("/fishbowl/api/events")
            client.get("/fishbowl/api/telemetry")
            client.get("/fishbowl/research")
            client.get("/fishbowl/wall")
        session.expire_all()
        llm_after = session.scalar(select(func.count(LLMRun.id))) or 0
        research_after = session.scalar(select(func.count(ResearchProviderUsage.id))) or 0
        checks.append(("repeated read-only polling creates zero new llm_runs rows", llm_after == llm_before))
        checks.append(
            ("repeated read-only polling creates zero new research_provider_usage rows",
             research_after == research_before),
        )

        # ---- 12. Control endpoints invoke existing simulation boundaries ------
        event_count_before_control = session.scalar(select(func.count(Event.id))) or 0
        cr = client.post("/fishbowl/api/control/next-event")
        checks.append(("next-event control returns 200", cr.status_code == 200))
        session.expire_all()
        event_count_after_control = session.scalar(select(func.count(Event.id))) or 0
        checks.append(
            ("next-event control actually advanced the real event log",
             event_count_after_control > event_count_before_control),
        )
        pr = client.post("/fishbowl/api/control/pause")
        checks.append(("pause control returns 200 and reports paused", pr.status_code == 200 and pr.json()["is_paused"] is True))
        rr = client.post("/fishbowl/api/control/resume")
        checks.append(("resume control returns 200 and reports resumed", rr.status_code == 200 and rr.json()["is_paused"] is False))
        fm = client.post(
            "/fishbowl/api/control/founder-message",
            json={"content": "Testing the Fishbowl.", "target_agent_id": None},
        )
        checks.append(("founder-message control returns 200", fm.status_code == 200))
        from app.db.models.reports import FounderMessage

        checks.append(
            ("founder-message control inserted a real FounderMessage row",
             session.scalars(
                 select(FounderMessage).where(FounderMessage.content == "Testing the Fishbowl.")
             ).first() is not None),
        )

        # ---- 13. Duplicate control submission protection ------------------------
        results: list[int] = []

        def _hit():
            results.append(client.post("/fishbowl/api/control/run-period").status_code)

        threads = [threading.Thread(target=_hit) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        checks.append(("concurrent control submissions: exactly one succeeds (200)", results.count(200) == 1))
        checks.append(
            ("concurrent control submissions: the rest are rejected (409)", results.count(409) == len(results) - 1),
        )

        # ---- 14. Responsive HTML contains required viewport metadata -----------
        pages_to_check = ["/fishbowl/", "/fishbowl/wall", "/fishbowl/rabbit-holes", "/fishbowl/reports", "/fishbowl/telemetry"]
        checks.append(
            ("every page carries the responsive viewport meta tag",
             all('name="viewport"' in client.get(p).text for p in pages_to_check)),
        )

        # ---- Bonus: LIVE-mode confirmation gate on RUN DAY ------------------
        os.environ["LLM_PROVIDER"] = "anthropic"
        try:
            live_rd = client.post("/fishbowl/api/control/run-day")
            checks.append(
                ("RUN DAY in LIVE mode without confirmation is refused (409)", live_rd.status_code == 409),
            )
        finally:
            os.environ["LLM_PROVIDER"] = "fixture"

        print("Fishbowl checks:")
        all_ok = True
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
            all_ok &= ok

        if not all_ok:
            print("\nFAIL: one or more Fishbowl assertions failed. See above.")
            return 1

        print(f"\nPASS: The Fishbowl ({len(checks)} checks) renders real data end to end and never mutates on read.")
        return 0
    finally:
        session.close()
        if not args.keep_db:
            _clean_db()
        else:
            print(f"\nDatabase kept at {DB_PATH}")


if __name__ == "__main__":
    raise SystemExit(main())
