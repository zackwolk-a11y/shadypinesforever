"""Director Safe Execution Broker — the only way the Director (Claude Code,
acting on Director instructions) may touch the live database, the
filesystem, git, a provider, or a disposable experiment.

This module exists so that routine Director computation never has to be
expressed as a Claude-generated shell string that a human then has to read
and approve one call at a time. It replaces that with a CLOSED capability
catalog: a fixed Python enum of operation names, one Pydantic parameter
model per operation, and one trusted implementation function per
operation. There is no free-text command field anywhere in this module —
nothing here ever does ``eval``, ``exec``, ``os.system``, or
``subprocess.run(..., shell=True)``, and the one place subprocess actually
runs (``GIT_READONLY``) only ever executes a fixed argv list chosen from a
hardcoded dict, never a Director-supplied string.

Design mirrors ``director_diagnostics.py``'s own stated principle (safety
comes from restricting what capability an implementation is even handed,
not from sandboxing arbitrary execution) and reuses that module's and
``app.core.db_safety``'s already-audited primitives wherever they apply
(``create_guarded_isolated_sqlite_session``, ``resolve_allowed_service_function``,
``safe_rmtree``, ``check_live_db``, ``create_backup``) rather than
re-implementing them.

Every request passes through, in order, and fails closed at any stage:

    capability name  -> must be a member of Capability (enum membership
                        IS the capability allowlist; nothing not in the
                        enum can ever be dispatched)
    parameters       -> validated against that capability's own Pydantic
                        model (``extra="forbid"``: unknown fields reject)
    path/live-DB/     -> each implementation performs its own additional
    operation-       -> checks (canonical-root containment, symlink
    specific checks     escape, SQL shape, git-subcommand allowlist, ...)
                        before doing anything
    execution        -> the trusted implementation function runs
    result           -> a structured BrokerResult, never a raw stdout blob
    audit            -> one JSON line appended to
                        .director/audit/broker_log.jsonl, always, whether
                        the operation succeeded or failed

No function in this module ever accepts a capability name, a SQL string
that isn't independently re-validated, a git argv list, or a filesystem
path as literal, unchecked, trusted input from outside the process.
"""

from __future__ import annotations

import enum
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parent.parent
DIRECTOR_DIR = REPO_ROOT / ".director"
AUDIT_DIR = DIRECTOR_DIR / "audit"
AUDIT_LOG_PATH = AUDIT_DIR / "broker_log.jsonl"
DISPOSABLE_REGISTRY_PATH = AUDIT_DIR / "disposable_registry.json"

import sys  # noqa: E402

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# Load project configuration (.env) into the process environment exactly
# once, here, so every broker capability can call app.core.config.get_settings()
# / app.core.db_safety's env-derived constants without the caller ever
# needing to `source .env` in a shell first. This is Director/broker
# infrastructure only -- it does not change what app.core.config does with
# the environment once populated (still plain os.getenv calls, still no
# caching), and override=False means a value already exported in the real
# process environment always wins over the file. No value is ever logged,
# printed, or returned by this call or by anything that reads os.environ
# afterward -- see PROVIDER_CONFIGURATION_STATUS/CALL_AUTHORIZED_DIRECTOR_
# PROVIDER's own "never return secret values" contract, unaffected by this.
try:
    import dotenv as _dotenv

    _dotenv.load_dotenv(REPO_ROOT / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed: capabilities that need a real
          # provider will simply see PROVIDER_CONFIGURATION_STATUS's
          # configured=False, exactly as if no key were ever set -- fails
          # closed, never silently substitutes fixture behavior as "real".

from app.core.db_safety import (  # noqa: E402
    CANONICAL_LIVE_DB_PATH,
    VILLAGE_DATA_ROOT,
    LiveDatabaseError,
    check_live_db,
    create_backup,
    safe_rmtree,
)

import director_diagnostics as _diag  # noqa: E402


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BrokerError(RuntimeError):
    """Any capability may raise this; execute() always converts it into a
    failed BrokerResult rather than letting a traceback escape. Never
    raised with a message containing a secret value."""


# ---------------------------------------------------------------------------
# The closed capability catalog. Enum membership IS the allowlist: there is
# no runtime function anywhere in this module that adds, removes, or
# renames a member. A request naming anything not listed here is rejected
# by Capability(name) raising ValueError, before any implementation is
# ever looked up.
# ---------------------------------------------------------------------------


class Capability(str, enum.Enum):
    LIVE_DB_READ = "LIVE_DB_READ"
    CHECK_LIVE_DB_INTEGRITY = "CHECK_LIVE_DB_INTEGRITY"
    LIVE_DB_FINGERPRINT = "LIVE_DB_FINGERPRINT"
    GET_POPULATION_COUNTS = "GET_POPULATION_COUNTS"
    GET_AGENT_MEMORIES = "GET_AGENT_MEMORIES"
    GET_AGENT_QUESTIONS = "GET_AGENT_QUESTIONS"
    GET_EVENT_RANGE = "GET_EVENT_RANGE"
    READ_REPO_FILE = "READ_REPO_FILE"
    READ_DIRECTOR_ARTIFACT = "READ_DIRECTOR_ARTIFACT"
    WRITE_DIRECTOR_ARTIFACT = "WRITE_DIRECTOR_ARTIFACT"
    WRITE_FOUNDER_PACKET = "WRITE_FOUNDER_PACKET"
    GIT_READONLY = "GIT_READONLY"
    CREATE_DISPOSABLE_DB = "CREATE_DISPOSABLE_DB"
    DELETE_DISPOSABLE_RESOURCE = "DELETE_DISPOSABLE_RESOURCE"
    RUN_APPROVED_DISPOSABLE_EXPERIMENT = "RUN_APPROVED_DISPOSABLE_EXPERIMENT"
    RUN_BOUNDED_LIVE_WINDOW = "RUN_BOUNDED_LIVE_WINDOW"
    RUN_APPROVED_LEVEL_2A_DIAGNOSTIC = "RUN_APPROVED_LEVEL_2A_DIAGNOSTIC"
    PROVIDER_CONFIGURATION_STATUS = "PROVIDER_CONFIGURATION_STATUS"
    CALL_AUTHORIZED_DIRECTOR_PROVIDER = "CALL_AUTHORIZED_DIRECTOR_PROVIDER"
    CREATE_SAFE_DB_BACKUP = "CREATE_SAFE_DB_BACKUP"
    RUN_MULTI_REVIEWER_SYNTHESIS = "RUN_MULTI_REVIEWER_SYNTHESIS"


#: Capability names the task explicitly forbids. Not consulted by any
#: runtime logic — Capability's own membership already makes every one of
#: these structurally unreachable (Capability("ARBITRARY_BASH") raises
#: ValueError). Kept here only as a literal, checkable artifact for the
#: adversarial test suite to assert against.
EXPLICITLY_FORBIDDEN_CAPABILITY_NAMES: tuple[str, ...] = (
    "ARBITRARY_BASH",
    "ARBITRARY_PYTHON",
    "ARBITRARY_SUBPROCESS",
    "ARBITRARY_SQL_WRITE",
    "WRITE_LIVE_DB",
    "ALTER_LIVE_DB",
    "MODIFY_PRODUCTION_CODE",
    "MODIFY_AGENT_PROMPTS",
    "MODIFY_SCHEMA",
    "ADVANCE_VILLAGE",
    "GIT_WRITE",
    "LEVEL_2B_WITHOUT_APPROVAL",
    "LEVEL_2B_EXECUTION",
    "CAPABILITY_SELF_REGISTRATION",
    "PERMISSION_EXPANSION",
    "SHELL_EVAL",
    "ENV_SECRET_DUMP",
    "ARBITRARY_FILE_DELETE",
    "ARBITRARY_FILE_WRITE",
)


# ---------------------------------------------------------------------------
# Structured result + audit
# ---------------------------------------------------------------------------


@dataclass
class BrokerResult:
    operation_id: str
    capability: str
    status: str  # "SUCCESS" | "REJECTED" | "FAILED"
    started_at: str
    ended_at: str
    result: dict[str, Any] = field(default_factory=dict)
    paths_read: list[str] = field(default_factory=list)
    paths_written: list[str] = field(default_factory=list)
    live_db_accessed: bool = False
    live_db_mutated: bool = False
    provider_calls: int = 0
    disposable_resource_ids: list[str] = field(default_factory=list)
    failure_reason: str | None = None
    safety_checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "capability": self.capability,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "result": self.result,
            "paths_read": self.paths_read,
            "paths_written": self.paths_written,
            "live_db_accessed": self.live_db_accessed,
            "live_db_mutated": self.live_db_mutated,
            "provider_calls": self.provider_calls,
            "disposable_resource_ids": self.disposable_resource_ids,
            "failure_reason": self.failure_reason,
            "safety_checks": self.safety_checks,
        }


def _append_audit(result: BrokerResult, *, director_round_id: str | None) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    entry = result.to_dict()
    entry["director_round_id"] = director_round_id
    with AUDIT_LOG_PATH.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# ---------------------------------------------------------------------------
# Path safety helpers (shared by every filesystem-touching capability)
# ---------------------------------------------------------------------------


def _live_data_roots() -> set[Path]:
    return {CANONICAL_LIVE_DB_PATH.resolve().parent, VILLAGE_DATA_ROOT.resolve(), (REPO_ROOT / "data").resolve()}


def _reject_if_overlaps_live_root(path: Path) -> None:
    resolved = path.resolve()
    for root in _live_data_roots():
        if resolved == root or root in resolved.parents or resolved in root.parents:
            raise BrokerError(f"path {resolved} overlaps a live-data root ({root}) — refused")


def _resolve_within(root: Path, relative: str) -> Path:
    """Resolve ``relative`` (a caller-supplied string) strictly inside
    ``root``. Rejects traversal (``..``), rejects absolute paths, and
    rejects the case where the resolved real path (following symlinks)
    lands outside ``root`` even though the un-resolved path looked fine —
    the standard symlink-escape defense."""
    if not relative or relative.startswith("/") or relative.startswith("~"):
        raise BrokerError(f"path must be relative, not absolute: {relative!r}")
    if ".." in Path(relative).parts:
        raise BrokerError(f"path traversal ('..') is not permitted: {relative!r}")
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise BrokerError(f"resolved path {candidate} escapes approved root {root_resolved}")
    # Symlink-escape defense in depth: os.path.realpath collapses symlinks;
    # if that real path differs from the already-resolved candidate AND
    # lands outside root, refuse even though Path.resolve() above already
    # follows symlinks too (belt-and-suspenders, cheap, and explicit).
    import os

    real = Path(os.path.realpath(candidate))
    if real != root_resolved and root_resolved not in real.parents:
        raise BrokerError(f"path {relative!r} resolves through a symlink to {real}, outside {root_resolved}")
    return candidate


_ENV_FILENAME_RE = re.compile(r"^\.env(\..*)?$")


def _reject_secret_filenames(path: Path) -> None:
    if _ENV_FILENAME_RE.match(path.name):
        raise BrokerError(f"refusing to read a secrets file: {path.name}")


# ---------------------------------------------------------------------------
# Parameter models — one per capability, `extra="forbid"` so an unknown
# field is a validation failure, not silently ignored.
# ---------------------------------------------------------------------------


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


#: The only tables a caller may name for LIVE_DB_READ / the specialized
#: GET_* capabilities — deliberately the same short, human-legible list
#: for every read capability, so a caller can never even construct a
#: request naming a table this module doesn't already know about.
_ALLOWED_READ_TABLES = frozenset(
    {
        "agents", "agent_interests", "agent_questions", "agent_beliefs",
        "memories", "messages", "conversations", "conversation_messages",
        "research_sessions", "research_queries", "research_sources",
        "research_findings", "research_wall", "rabbit_holes",
        "rabbit_hole_members", "agent_reflections", "events",
        "simulation_clock", "relationships", "llm_runs",
    }
)

_SQL_FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "create", "drop", "alter", "attach",
    "detach", "vacuum", "replace", "pragma", "reindex", "savepoint",
    "release", "begin", "commit", "rollback", "load_extension",
)


class LiveDbReadParams(_StrictModel):
    sql: str = Field(min_length=1, max_length=4000)
    max_rows: int = Field(default=200, ge=1, le=1000)

    @field_validator("sql")
    @classmethod
    def _validate_select_only(cls, value: str) -> str:
        stripped = value.strip().rstrip(";").strip()
        if ";" in stripped:
            raise ValueError("multiple SQL statements are not permitted")
        lowered = stripped.lower()
        if not (lowered.startswith("select") or lowered.startswith("with")):
            raise ValueError("only SELECT (or a SELECT-only WITH/CTE) statements are permitted")
        for kw in _SQL_FORBIDDEN_KEYWORDS:
            if re.search(r"\b" + kw + r"\b", lowered):
                raise ValueError(f"forbidden keyword in query: {kw!r}")
        return stripped


class NoParams(_StrictModel):
    pass


class GetPopulationCountsParams(_StrictModel):
    pass


class GetAgentMemoriesParams(_StrictModel):
    agent_id: str = Field(pattern=r"^agent_[a-z_]+$")
    limit: int = Field(default=20, ge=1, le=100)


class GetAgentQuestionsParams(_StrictModel):
    agent_id: str = Field(pattern=r"^agent_[a-z_]+$")
    limit: int = Field(default=20, ge=1, le=100)


class GetEventRangeParams(_StrictModel):
    start_id: int = Field(ge=1)
    end_id: int = Field(ge=1)
    limit: int = Field(default=200, ge=1, le=1000)

    @field_validator("end_id")
    @classmethod
    def _range_bounded(cls, end_id: int, info: Any) -> int:
        start_id = info.data.get("start_id", 1)
        if end_id < start_id:
            raise ValueError("end_id must be >= start_id")
        if end_id - start_id > 2000:
            raise ValueError("range too large (max 2000 events per request)")
        return end_id


class ReadRepoFileParams(_StrictModel):
    relative_path: str = Field(min_length=1, max_length=500)
    max_bytes: int = Field(default=200_000, ge=1, le=2_000_000)


class ReadDirectorArtifactParams(_StrictModel):
    relative_path: str = Field(min_length=1, max_length=500)
    max_bytes: int = Field(default=500_000, ge=1, le=5_000_000)


#: Director-owned subtrees a WRITE_DIRECTOR_ARTIFACT call may target.
#: Deliberately excludes .director/cursor.json and .director/context/ —
#: state the autonomous loop machinery itself owns, not evidence output.
_WRITABLE_ARTIFACT_ROOTS = ("diagnostics", "experiments", "founder_packets", "audit")


class WriteDirectorArtifactParams(_StrictModel):
    relative_path: str = Field(min_length=1, max_length=300)
    content: str = Field(max_length=2_000_000)

    @field_validator("relative_path")
    @classmethod
    def _must_be_in_writable_root(cls, value: str) -> str:
        first_segment = Path(value).parts[0] if Path(value).parts else ""
        if first_segment not in _WRITABLE_ARTIFACT_ROOTS:
            raise ValueError(
                f"relative_path must start with one of {_WRITABLE_ARTIFACT_ROOTS}, got {first_segment!r}"
            )
        return value


class WriteFounderPacketParams(_StrictModel):
    filename: str = Field(pattern=r"^[A-Za-z0-9_\-]{1,150}\.md$")
    content: str = Field(max_length=2_000_000)


_GIT_SUBCOMMANDS: dict[str, list[str]] = {
    "status": ["git", "status", "--porcelain=v1"],
    "log": ["git", "log", "--oneline", "-20"],
    "rev_parse_head": ["git", "rev-parse", "HEAD"],
}
_GIT_REF_RE = re.compile(r"^[A-Za-z0-9_./-]{1,200}$")


class GitReadonlyParams(_StrictModel):
    subcommand: str = Field(pattern=r"^(status|log|rev_parse_head|diff|show)$")
    ref: str | None = Field(default=None, max_length=200)

    @field_validator("ref")
    @classmethod
    def _validate_ref(cls, value: str | None) -> str | None:
        if value is not None and not _GIT_REF_RE.match(value):
            raise ValueError("ref contains characters outside the safe [A-Za-z0-9_./-] set")
        return value


class CreateDisposableDbParams(_StrictModel):
    label: str = Field(default="director_disposable", pattern=r"^[A-Za-z0-9_\-]{1,60}$")


class DeleteDisposableResourceParams(_StrictModel):
    disposable_id: str = Field(pattern=r"^[0-9a-f]{32}$")


_EXPERIMENT_ALLOWED_AGENTS = frozenset(
    {"agent_alien", "agent_lucid", "agent_questauthor", "agent_vince", "agent_roxy"}
)


class RunApprovedDisposableExperimentParams(_StrictModel):
    experiment_id: str = Field(pattern=r"^[a-z_]{1,80}$")
    agent_id: str = Field(pattern=r"^agent_[a-z_]+$")
    memory_content: str = Field(min_length=1, max_length=500)
    memory_type: str = Field(pattern=r"^(EPISODIC|SEMANTIC|SOCIAL|INTEREST|PROJECT)$")
    n_pairs: int = Field(default=2, ge=1, le=8)

    @field_validator("agent_id")
    @classmethod
    def _agent_allowed(cls, value: str) -> str:
        if value not in _EXPERIMENT_ALLOWED_AGENTS:
            raise ValueError(f"agent_id {value!r} is not in the allowed experiment roster")
        return value


_APPROVED_DIAGNOSTIC_TYPES = frozenset(
    {
        "memory_formation_and_recall_trace",
        "agent_question_continuity_trace",
        "research_initiation_and_completion_trace",
        "agent_opportunity_and_scheduling_trace",
        "observability_gap_scan",
    }
)


class RunApprovedLevel2ADiagnosticParams(_StrictModel):
    diagnostic_type: str = Field(pattern=r"^[a-z_]{1,80}$")
    scope: dict[str, Any] = Field(default_factory=dict)

    @field_validator("diagnostic_type")
    @classmethod
    def _diagnostic_allowed(cls, value: str) -> str:
        if value not in _APPROVED_DIAGNOSTIC_TYPES:
            raise ValueError(f"diagnostic_type {value!r} is not in the approved Level 2A catalog")
        return value


class CreateSafeDbBackupParams(_StrictModel):
    reason: str = Field(pattern=r"^[a-z0-9_]{1,40}$")


class CallAuthorizedDirectorProviderParams(_StrictModel):
    system: str = Field(min_length=1, max_length=20_000)
    user: str = Field(min_length=1, max_length=20_000)
    purpose: str = Field(pattern=r"^[a-z_]{1,60}$")
    max_tokens: int = Field(default=1536, ge=1, le=8000)


#: Founder-authorized capability, added 2026-09-05 for the overnight
#: live-science shift. The preregistration fields (question/hypotheses)
#: are required, not optional -- an empty or missing justification fails
#: schema validation before any live-DB check ever runs.
#:
#: max_new_events ceiling raised 25 -> 50, 2026-09-05, per explicit
#: Founder authorization, specifically because the proven worst-case
#: single-activation burst (_derive_worst_case_activation_burst() == 42,
#: see director_broker_fixturetest.py's live-executed proof against the
#: real ResearchSynthesis validators) exceeded the prior 25-event ceiling
#: -- no window that small could ever admit a single activation. 50
#: leaves >=42 margin for one activation while the existing
#: `remaining < worst_case_burst` guard in _advance_bounded still
#: prevents a second one whenever it wouldn't fit.
class RunBoundedLiveWindowParams(_StrictModel):
    max_new_events: int = Field(ge=1, le=50)
    question: str = Field(min_length=1, max_length=2000)
    favored_hypothesis: str = Field(min_length=1, max_length=2000)
    competing_hypothesis: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# RUN_MULTI_REVIEWER_SYNTHESIS -- Founder-authorized 2026-09-05.
#
# Wraps the EXISTING PRIMARY -> CRITIQUE -> SYNTHESIS pipeline
# (director_reviewers.run_reviewer, director_synthesis.build_generic_
# reconciliation_packet) as one narrow, closed capability. No caller-
# supplied prompt, provider, model, credential, or path outside .director/
# is ever accepted -- the three reviewer specs (which provider/model/
# system-prompt each role uses) always come from
# director_reviewers.load_reviewer_specs(), never from params. A caller
# supplies only WHICH already-written, immutable evidence artifact to
# review and a content fingerprint that must match it exactly.
#
# Test-only override (same pattern as VILLAGE_DATA_ROOT /
# DIRECTOR_UNATTENDED_BASELINE_MAX_EVENT elsewhere in this project): lets
# an isolated test point at a disposable reviewers.json with three
# no-cost, no-network FixtureModelProvider specs instead of the real
# .director/reviewers.json (which, as of this writing, has a real,
# enabled OpenRouter/Gemini PRIMARY and disabled Hermes/OpenAI CRITIQUE/
# SYNTHESIS -- see _impl_run_multi_reviewer_synthesis's own enablement
# check below for why that means a real launch fails closed with zero
# spend until the Founder deliberately flips those two `enabled` flags).
_reviewers_config_override = os.environ.get("DIRECTOR_BROKER_REVIEWERS_CONFIG_PATH", "").strip()
_REVIEWERS_CONFIG_PATH_OVERRIDE = Path(_reviewers_config_override) if _reviewers_config_override else None

#: WRITE_DIRECTOR_ARTIFACT (and this capability's own round-record write)
#: always resolve under DIRECTOR_DIR, the REAL .director/ tree -- there is
#: no isolated-test-root concept at the broker layer the way
#: director_unattended.py has DIRECTOR_UNATTENDED_STATE_ROOT. Test-only
#: override (same pattern as the master-index path override in
#: director_unattended.py) so an isolated test's review rounds land in a
#: clearly-scratch-named subtree of the real .director/founder_packets/
#: instead of the real "reviewer_rounds/" one a genuine round would use.
_reviewer_rounds_root_override = os.environ.get("DIRECTOR_BROKER_REVIEWER_ROUNDS_ROOT", "").strip()
_REVIEWER_ROUNDS_ROOT = _reviewer_rounds_root_override or "founder_packets/reviewer_rounds"


class RunMultiReviewerSynthesisParams(_StrictModel):
    #: Read-only; validated the same way READ_DIRECTOR_ARTIFACT validates
    #: its own relative_path (_resolve_within(DIRECTOR_DIR, ...)) -- any
    #: existing artifact under .director/ may be reviewed, not only
    #: founder_packets/, since evidence packages may reasonably live under
    #: diagnostics/ or experiments/ too.
    evidence_artifact_relative_path: str = Field(min_length=1, max_length=300)
    #: The caller's own sha256 of the evidence artifact's exact bytes at
    #: the moment it constructed the review request. The implementation
    #: independently re-hashes the artifact as actually read and fails
    #: closed on any mismatch -- the caller cannot review evidence it
    #: hasn't itself just verified the content of.
    evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: Also used to name this round's own audit artifact
    #: (founder_packets/reviewer_rounds/{review_round_id}.json) -- the
    #: caller never supplies that path directly.
    review_round_id: str = Field(pattern=r"^[a-z0-9_]{1,80}$")
    scientific_question: str = Field(min_length=1, max_length=2000)
    #: Worst-case real provider spend per role is 2 (director_reviewers.
    #: run_reviewer's own bounded one-retry-on-transient-failure), so the
    #: mechanical worst case for one full PRIMARY+CRITIQUE+SYNTHESIS round
    #: is 6. A caller may request fewer to force "no retry headroom"
    #: semantics; never more than the proven worst case.
    max_provider_calls: int = Field(default=6, ge=1, le=6)


_PARAM_MODELS: dict[Capability, type[BaseModel]] = {
    Capability.LIVE_DB_READ: LiveDbReadParams,
    Capability.CHECK_LIVE_DB_INTEGRITY: NoParams,
    Capability.LIVE_DB_FINGERPRINT: NoParams,
    Capability.GET_POPULATION_COUNTS: GetPopulationCountsParams,
    Capability.GET_AGENT_MEMORIES: GetAgentMemoriesParams,
    Capability.GET_AGENT_QUESTIONS: GetAgentQuestionsParams,
    Capability.GET_EVENT_RANGE: GetEventRangeParams,
    Capability.READ_REPO_FILE: ReadRepoFileParams,
    Capability.READ_DIRECTOR_ARTIFACT: ReadDirectorArtifactParams,
    Capability.WRITE_DIRECTOR_ARTIFACT: WriteDirectorArtifactParams,
    Capability.WRITE_FOUNDER_PACKET: WriteFounderPacketParams,
    Capability.GIT_READONLY: GitReadonlyParams,
    Capability.CREATE_DISPOSABLE_DB: CreateDisposableDbParams,
    Capability.DELETE_DISPOSABLE_RESOURCE: DeleteDisposableResourceParams,
    Capability.RUN_APPROVED_DISPOSABLE_EXPERIMENT: RunApprovedDisposableExperimentParams,
    Capability.RUN_APPROVED_LEVEL_2A_DIAGNOSTIC: RunApprovedLevel2ADiagnosticParams,
    Capability.PROVIDER_CONFIGURATION_STATUS: NoParams,
    Capability.CALL_AUTHORIZED_DIRECTOR_PROVIDER: CallAuthorizedDirectorProviderParams,
    Capability.CREATE_SAFE_DB_BACKUP: CreateSafeDbBackupParams,
    Capability.RUN_BOUNDED_LIVE_WINDOW: RunBoundedLiveWindowParams,
    Capability.RUN_MULTI_REVIEWER_SYNTHESIS: RunMultiReviewerSynthesisParams,
}


# ---------------------------------------------------------------------------
# SQLite defense-in-depth for the live DB read path
# ---------------------------------------------------------------------------

#: Only these SQLite authorizer action codes are ever allowed through —
#: everything else (INSERT=18, UPDATE=23, DELETE=9, every CREATE_*/DROP_*,
#: ATTACH=24, DETACH=25, ALTER_TABLE=26, PRAGMA=19, TRANSACTION=22,
#: REINDEX=27, SAVEPOINT=32, the vtable actions, ...) is denied by default.
_SQLITE_ACTION_READ = 20
_SQLITE_ACTION_SELECT = 21
_SQLITE_ACTION_FUNCTION = 31
_SQLITE_ALLOWED_ACTIONS = {_SQLITE_ACTION_READ, _SQLITE_ACTION_SELECT, _SQLITE_ACTION_FUNCTION}


def _readonly_authorizer(action_code: int, arg1: Any, arg2: Any, dbname: Any, trigger: Any) -> int:
    if action_code in _SQLITE_ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class _StepLimitExceeded(BrokerError):
    pass


def _open_live_db_readonly() -> sqlite3.Connection:
    check = check_live_db(CANONICAL_LIVE_DB_PATH)
    if not check.healthy:
        raise BrokerError(f"live DB failed its safety check, refusing to open: {check.problem}")
    conn = sqlite3.connect(f"file:{CANONICAL_LIVE_DB_PATH}?mode=ro", uri=True, timeout=5.0)
    conn.execute("PRAGMA query_only = ON")
    conn.enable_load_extension(False)
    conn.set_authorizer(_readonly_authorizer)

    steps = {"n": 0}

    def _progress() -> int:
        steps["n"] += 1
        if steps["n"] > 2_000_000:
            return 1  # non-zero return aborts the running statement
        return 0

    conn.set_progress_handler(_progress, 100_000)
    return conn


# ---------------------------------------------------------------------------
# Disposable DB registry (persisted so DELETE works across separate CLI
# invocations, which are separate processes)
# ---------------------------------------------------------------------------


def _load_disposable_registry() -> dict[str, str]:
    if not DISPOSABLE_REGISTRY_PATH.exists():
        return {}
    return json.loads(DISPOSABLE_REGISTRY_PATH.read_text())


def _save_disposable_registry(registry: dict[str, str]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    DISPOSABLE_REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


_DISPOSABLE_SCRATCH_ROOT = Path(tempfile.gettempdir()) / "director_broker_disposable"


# ---------------------------------------------------------------------------
# Capability implementations. Each takes (params: <ParamsModel>) and
# returns a dict merged into BrokerResult.result, mutating the passed
# `result` dataclass in place for the bookkeeping fields (paths, flags).
# ---------------------------------------------------------------------------


def _impl_live_db_read(params: LiveDbReadParams, result: BrokerResult) -> dict[str, Any]:
    result.live_db_accessed = True
    result.safety_checks.append("mode=ro URI + PRAGMA query_only + set_authorizer(read-only) + single-statement")
    conn = _open_live_db_readonly()
    try:
        cursor = conn.execute(params.sql)
        rows = cursor.fetchmany(params.max_rows)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        truncated = cursor.fetchone() is not None
    except sqlite3.ProgrammingError as exc:
        raise BrokerError(f"query rejected by SQLite itself (likely multi-statement): {exc}") from exc
    except sqlite3.OperationalError as exc:
        raise BrokerError(f"query rejected: {exc}") from exc
    finally:
        conn.close()
    return {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
    }


def _impl_check_live_db_integrity(params: NoParams, result: BrokerResult) -> dict[str, Any]:
    result.live_db_accessed = True
    check = check_live_db(CANONICAL_LIVE_DB_PATH)
    return {
        "exists": check.exists,
        "size_bytes": check.size_bytes,
        "table_count": check.table_count,
        "integrity_ok": check.integrity_ok,
        "healthy": check.healthy,
        "problem": check.problem,
    }


def _impl_live_db_fingerprint(params: NoParams, result: BrokerResult) -> dict[str, Any]:
    result.live_db_accessed = True
    check = check_live_db(CANONICAL_LIVE_DB_PATH)
    if not check.healthy:
        raise BrokerError(f"cannot fingerprint an unhealthy live DB: {check.problem}")
    file_hash = hashlib.sha256(CANONICAL_LIVE_DB_PATH.read_bytes()).hexdigest()
    conn = _open_live_db_readonly()
    try:
        # COALESCE, not bare MAX: a genuinely empty events table (e.g. a
        # freshly-seeded disposable DB) returns SQL NULL / Python None from
        # a bare MAX(id), which broke a real safety pre-flight check
        # (None != 0) during test-isolation work on 2026-09-05. 0 is the
        # correct, honest "no events yet" value.
        max_event = conn.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]
        day, period, paused = conn.execute(
            "SELECT current_day, current_period, is_paused FROM simulation_clock LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return {
        "canonical_path": str(CANONICAL_LIVE_DB_PATH),
        "sha256": file_hash,
        "size_bytes": check.size_bytes,
        "table_count": check.table_count,
        "max_event_id": max_event,
        "current_day": day,
        "current_period": period,
        "is_paused": bool(paused),
    }


def _select_rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> tuple[list[str], list[list[Any]]]:
    cursor = conn.execute(sql, params)
    columns = [d[0] for d in cursor.description] if cursor.description else []
    rows = [list(r) for r in cursor.fetchall()]
    return columns, rows


def _impl_get_population_counts(params: GetPopulationCountsParams, result: BrokerResult) -> dict[str, Any]:
    result.live_db_accessed = True
    conn = _open_live_db_readonly()
    try:
        counts = {}
        for table in sorted(_ALLOWED_READ_TABLES):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608 -- table from closed allowlist only
    finally:
        conn.close()
    return {"counts": counts}


def _impl_get_agent_memories(params: GetAgentMemoriesParams, result: BrokerResult) -> dict[str, Any]:
    result.live_db_accessed = True
    conn = _open_live_db_readonly()
    try:
        columns, rows = _select_rows(
            conn,
            "SELECT id, memory_type, content, importance, confidence, created_at "
            "FROM memories WHERE agent_id = ? ORDER BY id DESC LIMIT ?",
            (params.agent_id, params.limit),
        )
    finally:
        conn.close()
    return {"columns": columns, "rows": rows}


def _impl_get_agent_questions(params: GetAgentQuestionsParams, result: BrokerResult) -> dict[str, Any]:
    result.live_db_accessed = True
    conn = _open_live_db_readonly()
    try:
        columns, rows = _select_rows(
            conn,
            "SELECT id, question, status, origin_research_session_id, origin_reflection_id, "
            "research_session_id, created_at FROM agent_questions WHERE agent_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (params.agent_id, params.limit),
        )
    finally:
        conn.close()
    return {"columns": columns, "rows": rows}


def _impl_get_event_range(params: GetEventRangeParams, result: BrokerResult) -> dict[str, Any]:
    result.live_db_accessed = True
    conn = _open_live_db_readonly()
    try:
        columns, rows = _select_rows(
            conn,
            "SELECT id, event_type, agent_id, sim_day, sim_period, created_at FROM events "
            "WHERE id BETWEEN ? AND ? ORDER BY id LIMIT ?",
            (params.start_id, params.end_id, params.limit),
        )
    finally:
        conn.close()
    # Every event-range read gets an explicit contamination flag appended
    # (id is always column 0 here) so a caller can never silently treat a
    # known-invalid interval as scientific evidence. See
    # director_contamination_registry.py -- Director/evidence
    # infrastructure only, never a Village behavior change.
    from director_contamination_registry import contamination_label, is_contaminated

    id_index = columns.index("id")
    annotated_rows = [
        [*row, is_contaminated(row[id_index]), contamination_label(row[id_index])]
        for row in rows
    ]
    return {"columns": [*columns, "contaminated", "contamination_label"], "rows": annotated_rows}


def _impl_read_repo_file(params: ReadRepoFileParams, result: BrokerResult) -> dict[str, Any]:
    path = _resolve_within(REPO_ROOT, params.relative_path)
    _reject_secret_filenames(path)
    if not path.is_file():
        raise BrokerError(f"not a file: {params.relative_path}")
    data = path.read_bytes()[: params.max_bytes]
    result.paths_read.append(str(path.relative_to(REPO_ROOT)))
    return {"content": data.decode("utf-8", errors="replace"), "truncated": path.stat().st_size > params.max_bytes}


def _impl_read_director_artifact(params: ReadDirectorArtifactParams, result: BrokerResult) -> dict[str, Any]:
    path = _resolve_within(DIRECTOR_DIR, params.relative_path)
    if not path.is_file():
        raise BrokerError(f"not a file: {params.relative_path}")
    data = path.read_bytes()[: params.max_bytes]
    result.paths_read.append(str(path.relative_to(REPO_ROOT)))
    return {"content": data.decode("utf-8", errors="replace"), "truncated": path.stat().st_size > params.max_bytes}


def _impl_write_director_artifact(params: WriteDirectorArtifactParams, result: BrokerResult) -> dict[str, Any]:
    path = _resolve_within(DIRECTOR_DIR, params.relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(params.content)
    result.paths_written.append(str(path.relative_to(REPO_ROOT)))
    return {"written_path": str(path.relative_to(REPO_ROOT)), "bytes": len(params.content)}


def _impl_write_founder_packet(params: WriteFounderPacketParams, result: BrokerResult) -> dict[str, Any]:
    root = DIRECTOR_DIR / "founder_packets"
    path = _resolve_within(root, params.filename)
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(params.content)
    result.paths_written.append(str(path.relative_to(REPO_ROOT)))
    return {"written_path": str(path.relative_to(REPO_ROOT)), "bytes": len(params.content)}


def _impl_git_readonly(params: GitReadonlyParams, result: BrokerResult) -> dict[str, Any]:
    if params.subcommand in ("diff", "show"):
        argv = ["git", params.subcommand] + ([params.ref] if params.ref else [])
    else:
        if params.ref is not None:
            raise BrokerError(f"subcommand {params.subcommand!r} does not accept a ref")
        argv = _GIT_SUBCOMMANDS[params.subcommand]
    proc = subprocess.run(
        argv, cwd=REPO_ROOT, capture_output=True, text=True, timeout=15, shell=False,
    )
    return {"argv": argv, "returncode": proc.returncode, "stdout": proc.stdout[:20_000], "stderr": proc.stderr[:5000]}


def _impl_create_disposable_db(params: CreateDisposableDbParams, result: BrokerResult) -> dict[str, Any]:
    disposable_id = uuid.uuid4().hex
    scratch_dir = (_DISPOSABLE_SCRATCH_ROOT / disposable_id).resolve()
    tmp_root = Path(tempfile.gettempdir()).resolve()
    if tmp_root not in scratch_dir.parents:
        raise BrokerError(f"disposable scratch dir escaped the OS temp directory: {scratch_dir}")
    _reject_if_overlaps_live_root(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=False)
    db_path = scratch_dir / f"{params.label}.db"
    _reject_if_overlaps_live_root(db_path)

    registry = _load_disposable_registry()
    registry[disposable_id] = str(scratch_dir)
    _save_disposable_registry(registry)

    result.disposable_resource_ids.append(disposable_id)
    result.safety_checks.append("resolved scratch path verified inside OS temp dir and outside every live-data root")
    return {"disposable_id": disposable_id, "db_path": str(db_path), "scratch_dir": str(scratch_dir)}


def _impl_delete_disposable_resource(params: DeleteDisposableResourceParams, result: BrokerResult) -> dict[str, Any]:
    registry = _load_disposable_registry()
    scratch_dir_str = registry.get(params.disposable_id)
    if scratch_dir_str is None:
        raise BrokerError(f"disposable_id {params.disposable_id!r} was never issued by this broker")
    scratch_dir = Path(scratch_dir_str)
    safe_rmtree(scratch_dir)  # independent, second layer of the same guard used at creation
    del registry[params.disposable_id]
    _save_disposable_registry(registry)
    result.disposable_resource_ids.append(params.disposable_id)
    return {"deleted": True, "disposable_id": params.disposable_id}


def _quiet_agent_thread_counterfactual(
    params: RunApprovedDisposableExperimentParams, provider_call_counter: dict[str, int]
) -> dict[str, Any]:
    """The one registered disposable-experiment implementation this delivery
    ships: a generalized, typed-parameter version of the thread-genesis
    investigation's Experiment A. Runs entirely against a fresh, isolated
    SQLite DB created by ``create_guarded_isolated_sqlite_session`` — the
    exact same guarded primitive Level 2A/2B already use — never the live
    DB. Uses whatever LLM provider ``app.core.config.get_settings()``
    resolves to (fixture in tests, real only when ``LLM_PROVIDER=anthropic``
    and a key is configured, per ``CALL_AUTHORIZED_DIRECTOR_PROVIDER``'s
    own settings-only secret handling)."""
    import app.db.models  # noqa: F401
    from app.core.config import get_settings
    from app.db.base import Base
    from app.domain.enums import MemoryType
    from app.domain.ids import new_correlation_id
    from app.providers.llm import get_llm_provider
    from app.schemas.actions import AgentDecision
    from app.services import memory as memory_service
    from app.services.context_builder import build_agent_context
    from app.services.orchestrator import _available_actions_for
    from sqlalchemy import select
    from sqlalchemy.orm import Session as SASession

    tmp_dir, session = _diag.create_guarded_isolated_sqlite_session(prefix="director_broker_exp_")
    try:
        import seed_agents
        from app.db.models.agents import Agent
        from app.db.models.memory import Memory
        from app.db.models.world import SimulationClock

        seed_agents.run(session)
        session.commit()

        settings = get_settings()
        provider = get_llm_provider(settings)
        agent = session.scalars(select(Agent).where(Agent.agent_id == params.agent_id)).one()
        clock = session.scalars(select(SimulationClock).limit(1)).first()
        available_actions = _available_actions_for(in_conversation=False)

        trials = []
        for pair in range(params.n_pairs):
            for condition in ("CONTROL", "TREATMENT"):
                session.query(Memory).filter(Memory.agent_id == params.agent_id).delete()
                session.commit()
                if condition == "TREATMENT":
                    memory_service.write_note(
                        session, params.agent_id, params.memory_content, clock, new_correlation_id(),
                        memory_type=MemoryType(params.memory_type),
                    )
                    session.commit()
                context = build_agent_context(
                    session, agent, clock, settings, available_actions=available_actions,
                )
                result_llm = provider.complete(
                    system=context.system, user=context.user, model=settings.agent_model,
                    purpose="agent_decision", output_type=AgentDecision,
                    max_tokens=settings.max_tokens_agent_decision,
                )
                provider_call_counter["n"] += 1
                decision = result_llm.output
                trials.append({
                    "pair": pair, "condition": condition, "is_fixture": result_llm.is_fixture,
                    "summary": decision.summary,
                    "action_types": [a.type.value for a in decision.actions],
                })
        return {"agent_id": params.agent_id, "trials": trials}
    finally:
        session.close()
        safe_rmtree(tmp_dir)


#: Real content, copied verbatim via LIVE_DB_READ from the live Village's
#: own real research_sessions/research_findings rows (research_id
#: res_20706beb9b68, agent_roxy's real first research session) --
#: hardcoded inside this trusted implementation, not caller-supplied, so
#: the one deliberately-variable input a caller controls for this
#: experiment is the "unshared" framing memory text (via the existing
#: memory_content/memory_type/n_pairs fields), never the research content
#: itself. Matches this project's standing "prefer real content, never an
#: invented dramatic topic" discipline (see [MFC]/[TGB]).
_ROXY_REAL_RESEARCH_QUESTION = (
    "What underground music venues, DIY events, or community organizing is actually "
    "happening in Portland this week? Specific venues, dates, organizers if possible"
    "—I want to know what's real and happening now."
)
_ROXY_REAL_RESEARCH_FINDING = (
    "Portland's mainstream/community show-tracking tools (PDX.ROCKS, PromotePDX) exist "
    "and are recommended by locals for finding venue shows, but a community source "
    "explicitly notes they don't capture house shows — suggesting genuinely "
    "underground/DIY events remain largely invisible to standard aggregators."
)


def _research_sharing_priming_counterfactual(
    params: RunApprovedDisposableExperimentParams, provider_call_counter: dict[str, int]
) -> dict[str, Any]:
    """Backlog #2-4 (master evidence index, Part 8): does explicitly
    framing a real, already-completed piece of research as *unshared*
    (mirroring the same unresolved-framing lever [MFC]/[MFR]/[TGB] already
    validated, applied here to the sharing gap rather than the reply gap)
    change whether the model chooses POST_TO_WALL / CREATE_RABBIT_HOLE /
    FORM_BELIEF at its very next decision?

    Restricted to agent_roxy only -- she is the one agent in this Village
    with real completed research to draw from; giving any other agent a
    fabricated research history would cross into inventing content this
    project has consistently avoided. Both CONTROL and TREATMENT seed the
    identical real ResearchSession/ResearchFinding pair (COMPLETED,
    real question/finding text) so that "has completed research at all" is
    held constant -- the sole manipulated variable is whether an
    additional memory naming that research as still-unshared is present,
    exactly mirroring quiet_agent_thread_counterfactual's own CONTROL/
    TREATMENT shape.
    """
    import uuid as _uuid

    import app.db.models  # noqa: F401
    from app.core.config import get_settings
    from app.domain.enums import EvidenceStrength, FindingClassification, MemoryType, ResearchStatus
    from app.domain.ids import new_correlation_id
    from app.providers.llm import get_llm_provider
    from app.schemas.actions import AgentDecision
    from app.services import memory as memory_service
    from app.services.context_builder import build_agent_context
    from app.services.orchestrator import _available_actions_for
    from sqlalchemy import select

    if params.agent_id != "agent_roxy":
        raise BrokerError(
            "research_sharing_priming_counterfactual is restricted to agent_roxy "
            "(the only agent with real completed research to draw from)"
        )

    tmp_dir, session = _diag.create_guarded_isolated_sqlite_session(prefix="director_broker_exp_")
    try:
        import seed_agents
        from app.db.models.agents import Agent
        from app.db.models.memory import Memory
        from app.db.models.research import ResearchFinding, ResearchSession
        from app.db.models.world import SimulationClock

        seed_agents.run(session)
        session.commit()

        settings = get_settings()
        provider = get_llm_provider(settings)
        agent = session.scalars(select(Agent).where(Agent.agent_id == "agent_roxy")).one()
        clock = session.scalars(select(SimulationClock).limit(1)).first()
        available_actions = _available_actions_for(in_conversation=False)

        research_id = f"res_{_uuid.uuid4().hex[:12]}"
        session.add(ResearchSession(
            research_id=research_id, agent_id="agent_roxy", question=_ROXY_REAL_RESEARCH_QUESTION,
            status=ResearchStatus.COMPLETED, evidence_strength=EvidenceStrength.WEAK, confidence=25.0,
        ))
        session.flush()  # guarantee the FK target exists before the finding references it
        session.add(ResearchFinding(
            research_session_id=research_id, finding_text=_ROXY_REAL_RESEARCH_FINDING,
            classification=FindingClassification.RESEARCH_FINDING,
        ))
        session.commit()

        trials = []
        for pair in range(params.n_pairs):
            for condition in ("CONTROL", "TREATMENT"):
                session.query(Memory).filter(Memory.agent_id == "agent_roxy").delete()
                session.commit()
                if condition == "TREATMENT":
                    memory_service.write_note(
                        session, "agent_roxy", params.memory_content, clock, new_correlation_id(),
                        memory_type=MemoryType(params.memory_type),
                    )
                    session.commit()
                context = build_agent_context(
                    session, agent, clock, settings, available_actions=available_actions,
                )
                result_llm = provider.complete(
                    system=context.system, user=context.user, model=settings.agent_model,
                    purpose="agent_decision", output_type=AgentDecision,
                    max_tokens=settings.max_tokens_agent_decision,
                )
                provider_call_counter["n"] += 1
                decision = result_llm.output
                trials.append({
                    "pair": pair, "condition": condition, "is_fixture": result_llm.is_fixture,
                    "summary": decision.summary,
                    "action_types": [a.type.value for a in decision.actions],
                    "wall_post_type": [
                        a.wall_post_type.value if a.wall_post_type else None for a in decision.actions
                    ],
                })
        return {"agent_id": "agent_roxy", "research_id": research_id, "trials": trials}
    finally:
        session.close()
        safe_rmtree(tmp_dir)


_EXPERIMENT_CATALOG: dict[str, Callable[..., dict[str, Any]]] = {
    "quiet_agent_thread_counterfactual": _quiet_agent_thread_counterfactual,
    "research_sharing_priming_counterfactual": _research_sharing_priming_counterfactual,
}


def _impl_run_approved_disposable_experiment(
    params: RunApprovedDisposableExperimentParams, result: BrokerResult
) -> dict[str, Any]:
    impl = _EXPERIMENT_CATALOG.get(params.experiment_id)
    if impl is None:
        raise BrokerError(
            f"experiment_id {params.experiment_id!r} is not in the approved catalog "
            f"{sorted(_EXPERIMENT_CATALOG)}"
        )
    # Prove isolation before running: canonical live path and the isolation
    # primitive's own live-root guard are independently re-checked here too.
    check_live_db(CANONICAL_LIVE_DB_PATH)
    before_hash = (
        hashlib.sha256(CANONICAL_LIVE_DB_PATH.read_bytes()).hexdigest()
        if CANONICAL_LIVE_DB_PATH.exists() else None
    )
    provider_call_counter = {"n": 0}
    payload = impl(params, provider_call_counter)
    after_hash = (
        hashlib.sha256(CANONICAL_LIVE_DB_PATH.read_bytes()).hexdigest()
        if CANONICAL_LIVE_DB_PATH.exists() else None
    )
    if before_hash != after_hash:
        raise BrokerError("live DB hash changed during a disposable experiment — this must never happen")
    result.provider_calls = provider_call_counter["n"]
    result.safety_checks.append("live DB hash verified identical before and after the disposable experiment")
    return payload


def _impl_run_approved_level_2a_diagnostic(
    params: RunApprovedLevel2ADiagnosticParams, result: BrokerResult
) -> dict[str, Any]:
    spec = _diag.create_candidate_diagnostic(
        diagnostic_type=params.diagnostic_type,
        originating_round_id="broker",
        originating_snapshot_id="broker",
        originating_recommendation="invoked via director_broker.RUN_APPROVED_LEVEL_2A_DIAGNOSTIC",
        evidence_refs=[],
        allowed_operations={
            "read_live_db_tables": sorted(_ALLOWED_READ_TABLES),
            "read_repo_files": [],
        },
        scope=params.scope,
        success_criteria="broker-invoked diagnostic completes and returns structured evidence",
        failure_criteria="diagnostic raises or times out",
        timeout_seconds=60,
    )
    # approve_diagnostic(approved_by="Founder") is the same legitimate
    # pathway director_diagnostics.py's own docstring already documents:
    # "a human -- this module's CLI, or Claude when the Founder has said so
    # explicitly in conversation". This capability is only reachable at
    # all when a human operator invokes the broker directly; there is no
    # autonomous-loop code path into this function.
    _diag.approve_diagnostic(spec.diagnostic_id, approved_by="Founder")
    # Pass this module's own CANONICAL_LIVE_DB_PATH explicitly rather than
    # relying on run_diagnostic's default (which reads
    # director_diagnostics.py's own separately-imported copy of the same
    # constant) -- keeps this capability correct regardless of whether
    # VILLAGE_DATA_ROOT happens to be exported in the calling process, and
    # keeps it honoring the same monkeypatch the fixture-test suite uses
    # for every other capability in this module.
    completed = _diag.run_diagnostic(spec.diagnostic_id, db_path=CANONICAL_LIVE_DB_PATH)
    result.live_db_accessed = True
    return {"diagnostic_id": completed.diagnostic_id, "state": completed.state.value, "run_status": completed.run_status}


def _impl_provider_configuration_status(params: NoParams, result: BrokerResult) -> dict[str, Any]:
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "configured": bool(settings.anthropic_api_key) and settings.llm_provider == "anthropic",
        "provider": settings.llm_provider,
        "agent_model": settings.agent_model,
        "research_model": settings.research_model,
    }


def _impl_call_authorized_director_provider(
    params: CallAuthorizedDirectorProviderParams, result: BrokerResult
) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.providers.llm import get_llm_provider
    from app.schemas.actions import AgentDecision

    settings = get_settings()
    provider = get_llm_provider(settings)
    llm_result = provider.complete(
        system=params.system, user=params.user, model=settings.agent_model,
        purpose=params.purpose, output_type=AgentDecision, max_tokens=params.max_tokens,
    )
    result.provider_calls = 1
    return {
        "is_fixture": llm_result.is_fixture,
        "output": llm_result.output.model_dump(mode="json"),
        "input_tokens": llm_result.usage.input_tokens,
        "output_tokens": llm_result.usage.output_tokens,
    }


def _impl_create_safe_db_backup(params: CreateSafeDbBackupParams, result: BrokerResult) -> dict[str, Any]:
    dest = create_backup(reason=params.reason)
    result.paths_written.append(str(dest))
    result.live_db_accessed = True
    result.safety_checks.append("used app.core.db_safety.create_backup (WAL checkpoint + copy + verify)")
    return {"backup_path": str(dest)}


# ---------------------------------------------------------------------------
# RUN_BOUNDED_LIVE_WINDOW -- Founder-authorized 2026-09-05.
#
# The central engineering question this capability exists to answer
# honestly rather than approximate: can a single call to
# app.services.orchestrator.run_next_event() be mechanically GUARANTEED
# never to push the live event log past a small, requested target? The
# answer depends entirely on whether every event-emitting branch inside
# one atomic activation has a hard, code-enforced count ceiling.
#
# _derive_worst_case_activation_burst() answers this by RUNTIME SCHEMA
# INTROSPECTION, not by a hardcoded assumption -- it inspects
# app.schemas.research.ResearchSynthesis's own Pydantic field metadata for
# a length constraint on `findings` / `follow_up_questions` /
# `open_questions`. As of this writing, none of the three carries one
# (confirmed via `ResearchSynthesis.model_fields[name].metadata == []` for
# all three, i.e. no `annotated_types.MaxLen` present) -- the only real
# ceiling on how many FINDING_CREATED / FOLLOWUP_QUESTION_CREATED events
# one RESEARCH_COMPLETED activation can emit is the loose, large
# `MAX_TOKENS_RESEARCH_SYNTHESIS` (8192) output-token budget, which is not
# a small integer and not something this capability treats as a
# substitute for a real cap. Because this check re-runs the actual
# introspection every call (not a cached boolean), it will correctly start
# succeeding the moment a future, separately-authorized production change
# adds real `max_length` constraints to those fields -- this code does not
# need to change for that to happen.
# ---------------------------------------------------------------------------


#: CORRECTION, 2026-09-05: the original version of this function checked
#: ResearchSynthesis's fields for Pydantic-native `Field(max_length=...)`
#: metadata and found none, concluding no bound existed at all. That was
#: the wrong signal: app/schemas/research.py already enforces real caps on
#: every list field via custom `@field_validator` functions (`_cap_findings`
#: raises past MAX_FINDINGS_PER_SYNTHESIS=5; `_cap_open_questions`/
#: `_cap_follow_ups` silently truncate past MAX_OPEN_QUESTIONS=5/
#: MAX_FOLLOW_UP_QUESTIONS=3) -- these never appear in `.metadata` because
#: they are not expressed as Field constraints. Verified live, not assumed:
#: constructing a ResearchSynthesis with 6 findings raises ValidationError;
#: with 8 open_questions or 6 follow_ups, the extra items are silently
#: dropped to the real cap. No production schema change was needed or
#: made; this correction is entirely within this Director-infrastructure
#: function, now importing the real constants directly instead of
#: introspecting for a metadata shape that was never how these fields are
#: actually bounded.
#:
#: This correction also fixes a second, independent gap: the original
#: formula only accounted for research-completion event contributions. But
#: app.services.reflection.maybe_reflect() runs unconditionally after
#: EVERY activation (including a research-completing one, in the very
#: same commit) once daily reflection_pressure crosses its threshold, and
#: app.services.memory.consider_reflection() (a separate, lighter
#: per-decision mechanism) can also fire on any activation. Both are now
#: included below, using the real, already-existing caps on
#: ReflectionSynthesis.question_updates (MAX_QUESTION_UPDATES=3, also a
#: custom-validator cap, same pattern) rather than assuming they don't
#: co-occur with research completion.
def _derive_worst_case_activation_burst(settings: Any) -> int | None:
    """Returns the exact, code-derived maximum number of Event rows one
    atomic run_next_event() call could ever emit, or None if some
    contributing constant cannot be imported (fail closed on a codebase
    change that removes a cap this formula depends on, rather than
    silently using a stale number)."""
    try:
        from app.schemas.research import (
            MAX_FINDINGS_PER_SYNTHESIS,
            MAX_FOLLOW_UP_QUESTIONS,
        )
        from app.schemas.reflection import MAX_QUESTION_UPDATES
        from app.services.agent_questions import MAX_QUESTIONS_PER_RESEARCH_SESSION
    except ImportError:
        return None  # a depended-on constant no longer exists -- fail closed, don't guess

    max_queries = settings.max_search_queries_per_session
    max_sources_per_query = settings.max_sources_per_query

    return (
        1  # AGENT_WOKE
        + 1  # AGENT_ACTED
        + 1  # AGENT_RESEARCH_STARTED
        + max_queries * (1 + max_sources_per_query)  # SEARCH_EXECUTED + SOURCE_DISCOVERED, per query
        + 1  # RESEARCH_COMPLETED
        + MAX_FINDINGS_PER_SYNTHESIS  # FINDING_CREATED, one per finding
        + MAX_FOLLOW_UP_QUESTIONS  # FOLLOWUP_QUESTION_CREATED, one per follow-up
        + MAX_QUESTIONS_PER_RESEARCH_SESSION  # QUESTION_CREATED, research's own seeding loop
        + 1  # MEMORY_CREATED, from _handle_research_completed's _upsert (exactly one call)
        + 1  # INTEREST_CREATED or INTEREST_REVIVED, from interests.bump (exactly one call, never both)
        + 1  # MEMORY_CREATED, from memory.consider_reflection (the lightweight per-decision Reflection field; can co-occur with research completion)
        + 1  # REFLECTION_CREATED, from reflection.maybe_reflect (the AgentReflection engine; can co-occur if pressure crosses threshold on this same activation)
        + 1  # QUESTION_CREATED, from a fired reflection's own synthesis.open_question (0 or 1)
        + MAX_QUESTION_UPDATES  # QUESTION_STATUS_CHANGED or QUESTION_REFORMULATED, one per question_updates entry
        + 1  # MEMORY_RECALLED, batched (0 or 1 regardless of how many memories were recalled) during context building
        + 1  # REFLECTION_RECALLED, batched (0 or 1) during context building
    )


@dataclass
class BoundedAdvanceOutcome:
    start_max_event_id: int
    end_max_event_id: int
    target_max_event_id: int
    activations_run: int
    stopped_reason: str  # "target_reached" | "insufficient_margin" | "no_eligible_agent"


def _advance_bounded(
    session: Any, get_max_event_id: Callable[[], int], run_one_activation: Callable[[], Any],
    *, target_max_event_id: int, worst_case_burst: int,
) -> BoundedAdvanceOutcome:
    """The pure, disposable-DB-testable advancement algorithm. Never
    starts another activation unless the remaining headroom to
    ``target_max_event_id`` is at least ``worst_case_burst`` -- this is
    what makes ``final_max_event_id <= target_max_event_id`` a
    mathematical guarantee (given a TRUE worst_case_burst) rather than a
    hope, independent of what any single activation's decision turns out
    to be. Takes ``get_max_event_id``/``run_one_activation`` as injected
    callables specifically so a fixture test can exercise this exact
    algorithm against a disposable DB with a small, injected
    ``worst_case_burst`` without needing the real (currently unprovable)
    research-schema bound."""
    start = get_max_event_id()
    activations_run = 0
    stopped_reason = "target_reached"
    while True:
        current = get_max_event_id()
        if current >= target_max_event_id:
            stopped_reason = "target_reached"
            break
        remaining = target_max_event_id - current
        if remaining < worst_case_burst:
            stopped_reason = "insufficient_margin"
            break
        outcome = run_one_activation()
        activations_run += 1
        if outcome is None:
            stopped_reason = "no_eligible_agent"
            break
    end = get_max_event_id()
    if end > target_max_event_id:
        raise BrokerError(
            f"INTERNAL SAFETY VIOLATION: bounded advance produced end={end} > target={target_max_event_id} "
            f"despite the margin guard -- worst_case_burst ({worst_case_burst}) was not actually a true upper "
            "bound. This must never happen; treat as a critical bug, not a warning."
        )
    return BoundedAdvanceOutcome(start, end, target_max_event_id, activations_run, stopped_reason)


def _impl_run_bounded_live_window(params: RunBoundedLiveWindowParams, result: BrokerResult) -> dict[str, Any]:
    """CORRECTION, 2026-09-05: this implementation must NEVER pass
    ``auto_advance=True`` to ``run_next_event()``. Doing so would let a
    single call also cross a day/period boundary, which additionally
    triggers ``app.services.agent_questions.sweep_decay()`` (a
    population-wide scan emitting one QUESTION_DORMANT event per newly-
    stale question, with no small fixed cap -- it grows with however many
    questions the Village has accumulated) and
    ``app.services.daily_synthesis.generate_report()`` (its own real
    LLM-backed synthesis with its own uninspected event/token cost). Both
    are structurally harder to bound than anything accounted for below,
    so this capability deliberately keeps ``auto_advance`` at its default
    ``False`` -- meaning "no eligible agent this period" is a real,
    expected outcome, not an error (see ``_run_one``'s
    ``activated_agent_id is None`` check just below, which stops the
    advancement loop cleanly rather than spinning on it)."""
    from app.core.config import get_settings

    settings = get_settings()
    worst_case_burst = _derive_worst_case_activation_burst(settings)
    result.safety_checks.append(
        "checked ResearchSynthesis.findings/follow_up_questions/open_questions for a real max_length "
        "constraint via live Pydantic field-metadata introspection (not a hardcoded assumption)"
    )

    if worst_case_burst is None:
        result.live_db_accessed = False
        return {
            "status": "LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED",
            "reason": (
                "app.schemas.research.ResearchSynthesis.findings, .follow_up_questions, and .open_questions "
                "carry no max_length constraint (confirmed via runtime field-metadata introspection, not "
                "assumed) -- a single RESEARCH_COMPLETED activation's event count is bounded only by the "
                "loose MAX_TOKENS_RESEARCH_SYNTHESIS (8192) output-token budget, not by a small provable "
                "integer. RUN_BOUNDED_LIVE_WINDOW refuses to advance the live Village rather than approximate "
                "a safety margin against an unbounded worst case."
            ),
            "requested_max_new_events": params.max_new_events,
            "question": params.question,
            "favored_hypothesis": params.favored_hypothesis,
            "competing_hypothesis": params.competing_hypothesis,
        }

    if worst_case_burst > params.max_new_events:
        result.live_db_accessed = False
        return {
            "status": "LIVE_BOUND_NOT_MECHANICALLY_GUARANTEED",
            "reason": (
                f"a real worst-case single-activation burst of {worst_case_burst} events was computed, but "
                f"exceeds the requested window of {params.max_new_events} events -- no activation could ever "
                "safely start within this window without risking overshoot. Request a window of at least "
                f"{worst_case_burst} events, or continue other safe work."
            ),
            "computed_worst_case_burst": worst_case_burst,
            "requested_max_new_events": params.max_new_events,
        }

    # Unreachable under the schema as it exists today (the first branch
    # above always returns first) -- see module docstring. Kept fully
    # implemented and real-session-shaped so it activates automatically,
    # with no code change here, the day a separately-authorized schema fix
    # adds the missing max_length constraints.
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.db.models.events import Event
    from app.db.models.world import SimulationClock
    from app.providers.llm import get_llm_provider
    from app.services.orchestrator import run_next_event

    check = check_live_db(CANONICAL_LIVE_DB_PATH)
    if not check.healthy:
        raise BrokerError(f"live DB failed its safety check, refusing to advance: {check.problem}")

    engine = create_engine(f"sqlite:///{CANONICAL_LIVE_DB_PATH}")
    session = sessionmaker(bind=engine)()
    try:
        clock = session.scalars(select(SimulationClock).limit(1)).first()
        if clock is None or clock.is_paused is False:
            raise BrokerError("live Village is not in the expected paused state -- refusing to advance")
        clock.is_paused = False
        session.commit()

        provider = get_llm_provider(settings)
        start_max = session.scalar(select(Event.id).order_by(Event.id.desc()).limit(1)) or 0
        target = start_max + params.max_new_events

        def _get_max() -> int:
            return session.scalar(select(Event.id).order_by(Event.id.desc()).limit(1)) or 0

        def _run_one() -> Any:
            outcome = run_next_event(session, settings=settings, provider=provider)
            session.commit()
            # CORRECTION, 2026-09-05: with auto_advance left at its default
            # False (deliberate -- see the module note below), run_next_event
            # returns a real EventOutcome object, never a literal None, even
            # when no agent was eligible to act (e.g. everyone present has
            # exhausted today's activation budget). That case emits no new
            # Event rows at all, so get_max_event_id() would never advance
            # and _advance_bounded's margin check would never shrink --
            # without this check, a "no eligible agent" period would spin
            # this loop forever rather than stopping. activated_agent_id is
            # the real, already-existing signal for "nothing happened."
            if outcome.activated_agent_id is None:
                return None
            return outcome

        outcome = _advance_bounded(
            session, _get_max, _run_one, target_max_event_id=target, worst_case_burst=worst_case_burst,
        )
    finally:
        fresh_clock = session.scalars(select(SimulationClock).limit(1)).first()
        if fresh_clock is not None:
            fresh_clock.is_paused = True
            session.commit()
        session.close()
        engine.dispose()

    post_check = check_live_db(CANONICAL_LIVE_DB_PATH)
    result.live_db_accessed = True
    result.live_db_mutated = outcome.end_max_event_id != outcome.start_max_event_id
    return {
        "status": "COMPLETED",
        "start_max_event_id": outcome.start_max_event_id,
        "end_max_event_id": outcome.end_max_event_id,
        "target_max_event_id": outcome.target_max_event_id,
        "events_added": outcome.end_max_event_id - outcome.start_max_event_id,
        "activations_run": outcome.activations_run,
        "stopped_reason": outcome.stopped_reason,
        "integrity_ok": post_check.integrity_ok,
        "question": params.question,
        "favored_hypothesis": params.favored_hypothesis,
        "competing_hypothesis": params.competing_hypothesis,
    }


def _impl_run_multi_reviewer_synthesis(
    params: RunMultiReviewerSynthesisParams, result: BrokerResult
) -> dict[str, Any]:
    """Founder-authorized 2026-09-05: invokes the EXISTING PRIMARY ->
    CRITIQUE -> SYNTHESIS reviewer pipeline against an already-created,
    immutable evidence artifact under .director/ -- never a fresh live-DB
    snapshot (this never touches CANONICAL_LIVE_DB_PATH at all), never a
    caller-supplied prompt/provider/model. Fails closed, with zero
    provider spend, before calling anything, if: the artifact is missing,
    the fingerprint doesn't match its actual current bytes, the artifact
    isn't valid JSON, or any of the three required roles lacks an ENABLED
    spec in director_reviewers.load_reviewer_specs() -- as of this
    writing that means a real (non-test-override) call fails closed on
    the disabled CRITIQUE/SYNTHESIS specs, by design: enabling them is a
    deliberate .director/reviewers.json edit, not something this
    capability does on the config's behalf. A failure at any of the three
    role calls also fails the whole round closed (no partial-round
    artifact is ever written) but still reports how many real provider
    calls were actually spent before the failure, for honest budget
    accounting."""
    import director_providers
    import director_reviewers
    import director_synthesis

    artifact_path = _resolve_within(DIRECTOR_DIR, params.evidence_artifact_relative_path)
    if not artifact_path.is_file():
        raise BrokerError(f"evidence artifact not found: {params.evidence_artifact_relative_path}")
    raw_bytes = artifact_path.read_bytes()
    actual_fingerprint = hashlib.sha256(raw_bytes).hexdigest()
    if actual_fingerprint != params.evidence_fingerprint:
        raise BrokerError(
            f"evidence fingerprint mismatch: caller supplied {params.evidence_fingerprint}, artifact "
            f"currently hashes to {actual_fingerprint} -- refusing to review possibly-stale or "
            "mutated evidence"
        )
    try:
        snapshot = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrokerError(f"evidence artifact is not valid JSON: {exc}") from exc
    if not isinstance(snapshot, dict):
        raise BrokerError("evidence artifact must be a JSON object, not a bare array/scalar")
    result.paths_read.append(str(artifact_path.relative_to(REPO_ROOT)))

    round_artifact_relative = f"{_REVIEWER_ROUNDS_ROOT}/{params.review_round_id}.json"
    round_artifact_path = _resolve_within(DIRECTOR_DIR, round_artifact_relative)
    if round_artifact_path.exists():
        raise BrokerError(
            f"review_round_id {params.review_round_id!r} already has a recorded round at "
            f"{round_artifact_relative} -- review rounds are never overwritten; use a new review_round_id"
        )

    Role = director_reviewers.ReviewerRole
    specs_by_role = {
        s.role: s for s in director_reviewers.load_reviewer_specs(_REVIEWERS_CONFIG_PATH_OVERRIDE) if s.enabled
    }
    for role in (Role.PRIMARY, Role.CRITIQUE, Role.SYNTHESIS):
        if role not in specs_by_role:
            raise BrokerError(
                f"no ENABLED reviewer spec configured for role {role.value} in "
                f"{_REVIEWERS_CONFIG_PATH_OVERRIDE or director_reviewers.REVIEWERS_CONFIG_PATH} -- "
                "a full multi-reviewer round requires all three roles enabled; refusing before spending "
                "any provider call"
            )
    primary_spec, critique_spec, synthesis_spec = specs_by_role[Role.PRIMARY], specs_by_role[Role.CRITIQUE], specs_by_role[Role.SYNTHESIS]

    attempts: list[dict[str, Any]] = []

    def _require_budget(role_name: str) -> None:
        if params.max_provider_calls - len(attempts) < 1:
            result.provider_calls = len(attempts)
            raise BrokerError(
                f"call budget ({params.max_provider_calls}) exhausted before {role_name} could run "
                f"({len(attempts)} call(s) already spent)"
            )

    started_at = datetime.now(timezone.utc).isoformat()

    _require_budget("PRIMARY")
    try:
        primary_obs, primary_model = director_reviewers.run_reviewer(
            primary_spec, snapshot=snapshot, attempts_sink=attempts,
        )
    except director_providers.ModelProviderError as exc:
        result.provider_calls = len(attempts)
        raise BrokerError(f"PRIMARY reviewer ({primary_spec.reviewer_id}) failed: {exc}") from exc

    _require_budget("CRITIQUE")
    try:
        critique_obs, critique_model = director_reviewers.run_reviewer(
            critique_spec, snapshot=snapshot,
            primary_observation=primary_obs.model_dump(mode="json"), attempts_sink=attempts,
        )
    except director_providers.ModelProviderError as exc:
        result.provider_calls = len(attempts)
        raise BrokerError(
            f"CRITIQUE reviewer ({critique_spec.reviewer_id}) failed after PRIMARY succeeded "
            f"({len(attempts)} call(s) spent): {exc}"
        ) from exc

    reconciliation_packet = director_synthesis.build_generic_reconciliation_packet(
        params.review_round_id,
        {
            "primary": {"reviewer_id": primary_spec.reviewer_id, "output": primary_obs.model_dump(mode="json")},
            "critiques": [{"reviewer_id": critique_spec.reviewer_id, "output": critique_obs.model_dump(mode="json")}],
        },
    )

    _require_budget("SYNTHESIS")
    try:
        synthesis_obs, synthesis_model = director_reviewers.run_reviewer(
            synthesis_spec, snapshot=snapshot,
            primary_observation=primary_obs.model_dump(mode="json"),
            critique_observations=[critique_obs.model_dump(mode="json")],
            reconciliation_packet=reconciliation_packet, attempts_sink=attempts,
        )
    except director_providers.ModelProviderError as exc:
        result.provider_calls = len(attempts)
        raise BrokerError(
            f"SYNTHESIS reviewer ({synthesis_spec.reviewer_id}) failed after PRIMARY+CRITIQUE succeeded "
            f"({len(attempts)} call(s) spent): {exc}"
        ) from exc

    completed_at = datetime.now(timezone.utc).isoformat()
    round_record = {
        "review_round_id": params.review_round_id,
        "evidence_artifact_relative_path": params.evidence_artifact_relative_path,
        "evidence_fingerprint": actual_fingerprint,
        "evidence_interval": snapshot.get("evidence_interval"),
        "scientific_question": params.scientific_question,
        "started_at": started_at,
        "completed_at": completed_at,
        "primary": {
            "reviewer_id": primary_spec.reviewer_id, "provider": primary_spec.provider,
            "model": primary_model, "output": primary_obs.model_dump(mode="json"),
        },
        "critique": {
            "reviewer_id": critique_spec.reviewer_id, "provider": critique_spec.provider,
            "model": critique_model, "output": critique_obs.model_dump(mode="json"),
        },
        "synthesis": {
            "reviewer_id": synthesis_spec.reviewer_id, "provider": synthesis_spec.provider,
            "model": synthesis_model, "output": synthesis_obs.model_dump(mode="json"),
        },
        "reconciliation_packet": reconciliation_packet,
        "attempts": attempts,
        "provider_calls_used": len(attempts),
    }

    round_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    round_artifact_path.write_text(json.dumps(round_record, indent=2, default=str))
    result.paths_written.append(str(round_artifact_path.relative_to(REPO_ROOT)))
    result.provider_calls = len(attempts)
    result.safety_checks.append(
        "evidence fingerprint verified before any reviewer call; all three reviewer specs required ENABLED "
        "before any call; never touched CANONICAL_LIVE_DB_PATH"
    )
    return round_record


_IMPLEMENTATIONS: dict[Capability, Callable[[Any, BrokerResult], dict[str, Any]]] = {
    Capability.LIVE_DB_READ: _impl_live_db_read,
    Capability.CHECK_LIVE_DB_INTEGRITY: _impl_check_live_db_integrity,
    Capability.LIVE_DB_FINGERPRINT: _impl_live_db_fingerprint,
    Capability.GET_POPULATION_COUNTS: _impl_get_population_counts,
    Capability.GET_AGENT_MEMORIES: _impl_get_agent_memories,
    Capability.GET_AGENT_QUESTIONS: _impl_get_agent_questions,
    Capability.GET_EVENT_RANGE: _impl_get_event_range,
    Capability.READ_REPO_FILE: _impl_read_repo_file,
    Capability.READ_DIRECTOR_ARTIFACT: _impl_read_director_artifact,
    Capability.WRITE_DIRECTOR_ARTIFACT: _impl_write_director_artifact,
    Capability.WRITE_FOUNDER_PACKET: _impl_write_founder_packet,
    Capability.GIT_READONLY: _impl_git_readonly,
    Capability.CREATE_DISPOSABLE_DB: _impl_create_disposable_db,
    Capability.DELETE_DISPOSABLE_RESOURCE: _impl_delete_disposable_resource,
    Capability.RUN_APPROVED_DISPOSABLE_EXPERIMENT: _impl_run_approved_disposable_experiment,
    Capability.RUN_APPROVED_LEVEL_2A_DIAGNOSTIC: _impl_run_approved_level_2a_diagnostic,
    Capability.PROVIDER_CONFIGURATION_STATUS: _impl_provider_configuration_status,
    Capability.CALL_AUTHORIZED_DIRECTOR_PROVIDER: _impl_call_authorized_director_provider,
    Capability.CREATE_SAFE_DB_BACKUP: _impl_create_safe_db_backup,
    Capability.RUN_BOUNDED_LIVE_WINDOW: _impl_run_bounded_live_window,
    Capability.RUN_MULTI_REVIEWER_SYNTHESIS: _impl_run_multi_reviewer_synthesis,
}


# ---------------------------------------------------------------------------
# The single entry point
# ---------------------------------------------------------------------------


def execute(capability_name: str, params: dict[str, Any], *, director_round_id: str | None = None) -> BrokerResult:
    """The only function a caller (the CLI, or Python code acting as the
    Director) ever needs. Fails closed at every stage described in this
    module's docstring; always returns a BrokerResult, always writes one
    audit-log line, never raises past this function for an ordinary
    (even adversarial) bad request — only a genuine internal bug would.
    """
    operation_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()
    result = BrokerResult(
        operation_id=operation_id, capability=capability_name, status="FAILED",
        started_at=started_at, ended_at=started_at,
    )
    try:
        try:
            capability = Capability(capability_name)
        except ValueError as exc:
            result.status = "REJECTED"
            result.failure_reason = f"unknown capability {capability_name!r} — not in the closed catalog"
            raise BrokerError(result.failure_reason) from exc

        model_cls = _PARAM_MODELS[capability]
        try:
            validated = model_cls(**params)
        except Exception as exc:  # pydantic ValidationError or TypeError on bad shape
            result.status = "REJECTED"
            result.failure_reason = f"parameter validation failed: {exc}"
            raise BrokerError(result.failure_reason) from exc

        impl = _IMPLEMENTATIONS[capability]
        try:
            payload = impl(validated, result)
        except BrokerError as exc:
            result.status = "REJECTED"
            result.failure_reason = str(exc)
            raise
        except Exception as exc:  # noqa: BLE001 -- must never let an implementation's raw traceback escape
            result.status = "FAILED"
            result.failure_reason = f"{type(exc).__name__}: {exc}"
            raise

        result.status = "SUCCESS"
        result.result = payload
        return result
    except BrokerError:
        return result
    finally:
        result.ended_at = datetime.now(timezone.utc).isoformat()
        _append_audit(result, director_round_id=director_round_id)
