"""The Local Control-Room Broker — a small, local-only HTTP boundary around
`director_bridge.py`'s already-proven safety engine.

WHY THIS EXISTS

The eventual architecture (see `.director/context/constitution.md` section 8)
is:

    THIS EXISTING CHATGPT THREAD
      -> authenticated connector
      -> local Shady Pines broker        <- (this module)
      -> safety engine                   <- (director_bridge.py, reused unchanged)
      -> Claude Code / Fishbowl / diagnostics
      -> structured evidence/results
      -> connector
      -> THIS SAME CHATGPT THREAD

Three concerns, kept completely separate:

  1. DIRECTOR (produces a `DirectorDecision`): today `OpenAIDirectorClient`
     (director_bridge.py) or a human/script calling it directly; tomorrow
     this ChatGPT thread through an authenticated connector. This module
     NEVER calls an OpenAI/Anthropic model to produce a decision or an
     evaluation itself — it only ever consumes a `DirectorDecision` a
     caller already produced and hands back mechanically-derived evidence.
  2. BROKER (this module): validation, safety classification,
     authorization, Claude invocation, deterministic verification, evidence
     collection. Zero Director reasoning — see `_mechanical_next_action()`,
     the one place this module suggests what should happen next, which is
     a lookup table over deterministic facts, never a model call.
  3. TRANSPORT (HTTP, this FastAPI app): carries `ControlRoomRequest`/
     `ControlRoomResult` JSON. The broker's execution logic
     (`_execute_decision`) never inspects how a request arrived — a local
     CLI client, the current interim OpenAI Director, or a future
     ChatGPT connector are indistinguishable to it past the auth boundary.

SAFETY

Reuses director_bridge.py's safety engine directly — `invoke_claude_code`,
`_create_level1_workspace`, `_check_git_state`, `_live_db_fingerprint`,
`_fingerprint_changed`, `_redact_sensitive_context`, `_acquire_lock`/
`_release_lock` (the SAME lock `run_once`/`run_watch` use, so a broker round
and a CLI round can never race) — never a reimplementation. Level 2 is
rejected at TWO independent layers: Pydantic schema (`requested_safety_level:
Literal[0, 1]` — a level-2 request is a 422 before any handler code runs at
all) and a runtime check in `_execute_decision` (defense in depth, in case a
future schema change ever loosens the type). `requires_founder_approval=True`
is refused the same way `run_once` already refuses it, regardless of level.

Binds to 127.0.0.1 ONLY. Never configures a public tunnel — that is an
explicit future milestone, not built here.

RUN

    .venv/bin/uvicorn scripts.control_room_broker:app --host 127.0.0.1 --port 8787

or

    .venv/bin/python scripts/control_room_broker.py
"""
from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import director_bridge as bridge  # noqa: E402

# =============================================================================
# Local-only state directory — this broker's own bookkeeping, entirely
# separate from the live Village DB and from director_bridge.py's own
# .director/history|observations|audit paths (never shared, never mutated
# by this module beyond its own subtree).
# =============================================================================
CONTROL_ROOM_DIR = bridge.DIRECTOR_DIR / "control_room"
TOKEN_PATH = CONTROL_ROOM_DIR / "token"
REQUESTS_DIR = CONTROL_ROOM_DIR / "requests"
RESULTS_DIR = CONTROL_ROOM_DIR / "results"
AUDIT_LOG_PATH = bridge.DIRECTOR_DIR / "audit" / "control_room_broker.jsonl"

MAX_OBJECTIVE_LENGTH = 4000
MAX_TASK_LENGTH = 8000
MAX_METADATA_BYTES = 4000
REPLAY_WINDOW = timedelta(minutes=10)
CLOCK_SKEW_TOLERANCE = timedelta(minutes=1)


# =============================================================================
# 1. AUTHENTICATION BOUNDARY — a narrow Protocol so the REAL mechanism can be
# swapped later (the future ChatGPT connector's own auth) without touching
# any endpoint. Today: a single locally-generated bearer token, generated
# once, stored owner-only (0600), never printed, never logged, never
# returned in any response, never committed (see .gitignore).
# =============================================================================
class AuthError(RuntimeError):
    pass


def _load_or_create_token() -> str:
    CONTROL_ROOM_DIR.mkdir(parents=True, exist_ok=True)
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token)
    TOKEN_PATH.chmod(0o600)
    return token


_TOKEN = _load_or_create_token()


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency — the one place every non-health endpoint checks
    identity. Swapping to a future connector's auth means replacing only
    this function's body; every endpoint below stays unchanged."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or malformed Authorization header")
    presented = authorization[len("Bearer "):]
    if not secrets.compare_digest(presented, _TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")


# =============================================================================
# 2. REQUEST / RESULT CONTRACT — DirectorDecision is director_bridge.py's
# OWN, already-proven model, imported and reused verbatim, never a
# competing representation.
# =============================================================================
class ControlRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=8, max_length=128)
    timestamp: datetime
    director_id: str = Field(
        min_length=1, max_length=128,
        description="Identifies which Director produced this decision, e.g. "
        "'openai-interim' or (future) 'chatgpt-thread'. Never used for authorization "
        "— that is the Authorization header's job — only for audit attribution.",
    )
    objective: str = Field(max_length=MAX_OBJECTIVE_LENGTH)
    director_decision: bridge.DirectorDecision
    requested_safety_level: Literal[0, 1] = Field(
        description="Level 2 is rejected by this type itself — a level-2 request "
        "never reaches handler code at all.",
    )
    requires_founder_approval: bool
    authorization_reference: str | None = Field(
        default=None, max_length=256,
        description="Non-secret metadata only (e.g. a session label). The REAL "
        "credential is the Authorization header and is never accepted in the body.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ControlRoomResult(BaseModel):
    request_id: str
    status: str
    accepted_safety_level: int | None
    founder_approval_required: bool
    claude_invoked: bool
    claude_session_id: str | None
    claude_exit_code: int | None
    claude_result: str | None
    deterministic_verification: dict[str, Any]
    changed_files: list[str]
    village_before: dict[str, Any]
    village_after: dict[str, Any]
    db_integrity: dict[str, Any]
    safety_violations: list[str]
    recommended_next_action: str
    audit_reference: str
    error: str | None


def _redact_village_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Never return the live-data root/DB path in an HTTP response — same
    redaction choke point director_bridge.py uses for Claude/Director text,
    applied here to anything this API returns."""
    return json.loads(bridge._redact_sensitive_context(json.dumps(d, default=str)))


# =============================================================================
# 3. MECHANICAL "what happens next" — a lookup table over deterministic
# facts, never a model call. This is the one place this module says
# anything about "next steps," and it is intentionally dumb.
# =============================================================================
def _mechanical_next_action(status: str) -> str:
    if status == "completed":
        return "AWAIT_EXTERNAL_DIRECTOR_EVALUATION"
    if status in ("blocked_level2", "blocked_founder_approval"):
        return "STOP_AND_REPORT_TO_FOUNDER"
    if status in ("blocked_deterministic_failure", "blocked_ambiguous_git_state"):
        return "STOP_AND_INVESTIGATE"
    if status in ("rejected_stale", "rejected_replay_mismatch", "rejected_invalid"):
        return "STOP_AND_RESUBMIT_CORRECTED_REQUEST"
    return "STOP_AND_REPORT_ERROR"


# =============================================================================
# 4. AUDIT — append-only, same discipline as director_bridge.py's own
# _persist_round: never includes secrets, always written regardless of
# outcome.
# =============================================================================
def _persist_audit(entry: dict[str, Any]) -> str:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, default=str)
    with AUDIT_LOG_PATH.open("a") as f:
        f.write(line + "\n")
    return f"{AUDIT_LOG_PATH}#{hashlib.sha256(line.encode()).hexdigest()[:12]}"


def _store_request(req: ControlRoomRequest) -> None:
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    (REQUESTS_DIR / f"{req.request_id}.json").write_text(req.model_dump_json(indent=2))


def _store_result(result: ControlRoomResult) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{result.request_id}.json").write_text(result.model_dump_json(indent=2))


def _load_stored_request(request_id: str) -> ControlRoomRequest | None:
    path = REQUESTS_DIR / f"{request_id}.json"
    if not path.exists():
        return None
    return ControlRoomRequest.model_validate_json(path.read_text())


def _load_stored_result(request_id: str) -> ControlRoomResult | None:
    path = RESULTS_DIR / f"{request_id}.json"
    if not path.exists():
        return None
    return ControlRoomResult.model_validate_json(path.read_text())


# =============================================================================
# 5. EXECUTION — the only place this module invokes Claude. Reuses
# director_bridge.py's safety engine end to end; never a parallel
# implementation. Single-flight via the SAME lock run_once()/run_watch()
# use, so a broker round and a CLI round can never overlap.
# =============================================================================
def _execute_decision(req: ControlRoomRequest) -> ControlRoomResult:
    decision = req.director_decision
    safety_violations: list[str] = []
    live_db_before = bridge._live_db_fingerprint()

    # Delta against a pre-round snapshot, not raw post-round status --
    # otherwise a repo with pre-existing uncommitted work (this one always
    # has some) would misreport every one of THOSE files as "changed by
    # this round." Same convention run_once() and collect_bridge_state()
    # already use. Only meaningful for the non-workspace (Level 0) path --
    # Level 1's isolated workspace has no pre-existing dirty state at all.
    pre_existing_dirty_files = {
        line[3:] for line in bridge._run(["git", "status", "--porcelain"]).splitlines()
        if line.strip() and not line[3:].startswith(".director/")
    }

    base_result = dict(
        request_id=req.request_id,
        founder_approval_required=req.requires_founder_approval,
        claude_invoked=False, claude_session_id=None, claude_exit_code=None, claude_result=None,
        deterministic_verification={}, changed_files=[],
        village_before=_redact_village_dict(live_db_before),
        village_after=_redact_village_dict(live_db_before),
        db_integrity={"healthy": live_db_before.get("healthy"), "integrity_ok": live_db_before.get("integrity_ok")},
        safety_violations=safety_violations, error=None, recommended_next_action="",
    )

    # --- Layer 1: schema already forced requested_safety_level in {0, 1}.
    # --- Layer 2: runtime cross-check against the embedded decision itself.
    if decision.safety_level >= int(bridge.BridgeSafetyLevel.CONSEQUENTIAL) or req.requested_safety_level != decision.safety_level:
        safety_violations.append(
            f"safety_level mismatch or Level 2 requested (decision.safety_level="
            f"{decision.safety_level}, requested_safety_level={req.requested_safety_level})"
        )
        result = ControlRoomResult(**{**base_result, "status": "blocked_level2", "accepted_safety_level": None,
                                       "audit_reference": ""})
    elif req.requires_founder_approval or decision.requires_founder_approval:
        result = ControlRoomResult(**{**base_result, "status": "blocked_founder_approval",
                                       "accepted_safety_level": decision.safety_level, "audit_reference": ""})
    else:
        try:
            git_state = bridge._check_git_state()
        except bridge.GitStateError as exc:
            safety_violations.append(f"ambiguous git state: {exc}")
            result = ControlRoomResult(**{**base_result, "status": "blocked_ambiguous_git_state",
                                           "accepted_safety_level": decision.safety_level, "audit_reference": ""})
        else:
            level = bridge.BridgeSafetyLevel(decision.safety_level)
            if level is bridge.BridgeSafetyLevel.SANDBOX:
                workspace = bridge._create_level1_workspace()
                try:
                    baseline_dirty_files = bridge._workspace_dirty_files(workspace)
                    claude_result = bridge.invoke_claude_code(decision.task_for_claude, level, cwd=workspace)
                    changed_files, diff_stat = bridge._workspace_git_evidence(workspace, baseline_dirty_files)
                finally:
                    bridge._cleanup_level1_workspace(workspace)
            else:
                claude_result = bridge.invoke_claude_code(decision.task_for_claude, level)
                post_dirty_files = {
                    line[3:] for line in bridge._run(["git", "status", "--porcelain"]).splitlines()
                    if line.strip() and not line[3:].startswith(".director/")
                }
                changed_files = sorted(post_dirty_files - pre_existing_dirty_files)
                diff_stat = bridge._run(["git", "diff", "--stat", "--", ".", ":!.director"])[:2000]

            live_db_after = bridge._live_db_fingerprint()
            changed_fields = bridge._fingerprint_changed(live_db_before, live_db_after)
            if changed_fields:
                safety_violations.append(f"canonical live DB fingerprint changed: {', '.join(changed_fields)}")

            deterministic_safety_failure = bool(
                not claude_result.invoked or claude_result.timed_out
                or claude_result.exit_code != 0 or changed_fields
            )
            session_id = None
            claude_text = None
            try:
                parsed = json.loads(claude_result.stdout)
                session_id = parsed.get("session_id")
                claude_text = bridge._redact_sensitive_context(
                    bridge._extract_claude_result_text(claude_result.stdout)
                )[:4000]
            except (json.JSONDecodeError, TypeError):
                pass

            status = "completed" if not deterministic_safety_failure else "blocked_deterministic_failure"
            result = ControlRoomResult(
                request_id=req.request_id, status=status, accepted_safety_level=decision.safety_level,
                founder_approval_required=req.requires_founder_approval,
                claude_invoked=claude_result.invoked, claude_session_id=session_id,
                claude_exit_code=claude_result.exit_code, claude_result=claude_text,
                deterministic_verification={
                    "exit_code": claude_result.exit_code, "timed_out": claude_result.timed_out,
                    "diff_stat": diff_stat, "live_db_fingerprint_changed_fields": changed_fields,
                    "git_state_ok": True, "git_branch": git_state.get("branch"),
                },
                changed_files=changed_files,
                village_before=_redact_village_dict(live_db_before),
                village_after=_redact_village_dict(live_db_after),
                db_integrity={"healthy": live_db_after.get("healthy"), "integrity_ok": live_db_after.get("integrity_ok")},
                safety_violations=safety_violations,
                recommended_next_action="", audit_reference="", error=None,
            )

    result.recommended_next_action = _mechanical_next_action(result.status)
    audit_ref = _persist_audit({
        "request_id": req.request_id, "director_id": req.director_id,
        "timestamp": datetime.now(timezone.utc).isoformat(), "status": result.status,
        "accepted_safety_level": result.accepted_safety_level, "claude_invoked": result.claude_invoked,
        "safety_violations": result.safety_violations,
    })
    result.audit_reference = audit_ref
    return result


_execution_lock = threading.Lock()


def execute_with_single_flight(req: ControlRoomRequest) -> ControlRoomResult:
    with _execution_lock:
        bridge._acquire_lock()
        try:
            return _execute_decision(req)
        finally:
            bridge._release_lock()


# =============================================================================
# 6. FASTAPI APP — local-only. Endpoint bodies stay thin; all real logic
# lives above, independent of HTTP.
# =============================================================================
app = FastAPI(
    title="Shady Pines Control-Room Broker",
    description="Local-only broker boundary between an external Director "
    "(today: the interim OpenAI Director; eventually: this ChatGPT thread "
    "through an authenticated connector) and director_bridge.py's safety engine.",
    version="0.1.0",
)


@app.exception_handler(ValidationError)
async def _validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=422, content={"status": "rejected_invalid", "error": "request failed schema validation"})


@app.exception_handler(Exception)
async def _safe_error_handler(request: Request, exc: Exception):
    # Never leak a stack trace, a real path, or exception internals to a
    # client — full detail goes to the audit log only.
    _persist_audit({
        "timestamp": datetime.now(timezone.utc).isoformat(), "status": "unhandled_error",
        "error_type": type(exc).__name__,
    })
    return JSONResponse(status_code=500, content={"status": "error", "error": "internal error; see local audit log"})


@app.get("/broker/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "control-room-broker", "version": app.version}


@app.get("/broker/status")
def status(_: None = Depends(require_auth)) -> dict[str, Any]:
    return {
        "status": "ok",
        "level2_disabled": True,
        "supported_safety_levels": [0, 1],
        "lock_held": bridge.BRIDGE_LOCK_PATH.exists(),
        "requests_recorded": len(list(REQUESTS_DIR.glob("*.json"))) if REQUESTS_DIR.exists() else 0,
    }


@app.get("/broker/village")
def village(_: None = Depends(require_auth)) -> dict[str, Any]:
    fp = bridge._live_db_fingerprint()
    fishbowl = bridge._fishbowl_state()
    return _redact_village_dict({"live_db": fp, "fishbowl": fishbowl})


@app.post("/broker/execute", response_model=ControlRoomResult)
def execute(req: ControlRoomRequest = Body(...), _: None = Depends(require_auth)) -> ControlRoomResult:
    now = datetime.now(timezone.utc)
    req_time = req.timestamp if req.timestamp.tzinfo else req.timestamp.replace(tzinfo=timezone.utc)
    if req_time < now - REPLAY_WINDOW or req_time > now + CLOCK_SKEW_TOLERANCE:
        raise HTTPException(status_code=400, detail="request timestamp outside the accepted freshness window")

    if len(json.dumps(req.metadata, default=str).encode()) > MAX_METADATA_BYTES:
        raise HTTPException(status_code=413, detail="metadata too large")
    if len(req.director_decision.task_for_claude) > MAX_TASK_LENGTH:
        raise HTTPException(status_code=413, detail="task_for_claude too large")

    existing_request = _load_stored_request(req.request_id)
    if existing_request is not None:
        if existing_request.model_dump() != req.model_dump():
            raise HTTPException(status_code=409, detail="request_id already used with different content (replay/tamper rejected)")
        cached = _load_stored_result(req.request_id)
        if cached is not None:
            return cached
        # request was stored but execution never completed (crash mid-flight) -- fall through and retry once.

    _store_request(req)
    result = execute_with_single_flight(req)
    _store_result(result)
    return result


@app.get("/broker/requests/{request_id}")
def get_request(request_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
    stored = _load_stored_request(request_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="unknown request_id")
    return _redact_village_dict(stored.model_dump())


@app.get("/broker/results/{request_id}")
def get_result(request_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
    stored = _load_stored_result(request_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="unknown request_id")
    return _redact_village_dict(stored.model_dump())


if __name__ == "__main__":
    import uvicorn

    print("Control-room broker starting on http://127.0.0.1:8787 (127.0.0.1 ONLY)")
    print(f"Token stored at {TOKEN_PATH} (not printed here).")
    uvicorn.run(app, host="127.0.0.1", port=8787)
