"""The Director bridge: persistent context/history layer.

The continuity layer that eliminates the manual copy/paste workflow
between the Fishbowl, Claude Code, and every reviewer (Gemini, Hermes, and
whatever comes next). Two kinds of content, kept deliberately distinct:

- **Static**: the Village's goals, Founder authority, autonomy principles,
  safety rules, evaluation criteria, and architecture —
  `.director/context/constitution.md`, hand-curated, rarely changes.
- **Dynamic**: what actually happened — `.director/history/rounds.jsonl`
  (every past round: reviewers, recommendations, confidence — derived and
  rebuilt from the authoritative sources, `.director/observations.jsonl`
  and `.director/packets/`, never hand-edited) and
  `.director/history/decisions.jsonl` (Founder decisions on those rounds —
  append-only, and the one piece of history that is NOT derivable from
  anything else, since nothing else records what the Founder decided).

`get_relevant_history()` is the one function anything downstream (director
reviewers, a future synthesis reviewer) should call — it returns a bounded
package (the constitution plus a capped number of round summaries plus any
still-pending rounds plus recorded decisions), never the raw contents of
every stored snapshot, reviewer record, or packet.

Entirely outside the Village database — every path here is under
`.director/`, the same rule every other Director component follows.
"""

from __future__ import annotations

import argparse
import enum
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from director_providers import (  # noqa: E402
    ModelProviderError,
    StructuredCallSpec,
    get_model_provider,
)
import director_bridge_test_runner as _test_runner  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
DIRECTOR_DIR = REPO_ROOT / ".director"

# Load .env into the process environment exactly once, here, before ANYTHING
# below reads VILLAGE_DATA_ROOT/OPENAI_API_KEY/etc — mirrors
# director_broker.py's own identical pattern (see its comment there for
# the override=False rationale: an already-exported real env var always
# wins over the file; no value is ever logged or returned). This matters
# specifically for VILLAGE_DATA_ROOT: app.core.db_safety.CANONICAL_LIVE_DB_PATH
# is computed at import time from that var, so it must be set before the
# first import of app.core.db_safety anywhere in this process — never rely
# on a caller having sourced .env in their shell first.
try:
    import dotenv as _dotenv

    _dotenv.load_dotenv(REPO_ROOT / ".env", override=False)
except ImportError:
    pass

CONSTITUTION_PATH = DIRECTOR_DIR / "context" / "constitution.md"
ROUNDS_HISTORY_PATH = DIRECTOR_DIR / "history" / "rounds.jsonl"
DECISIONS_PATH = DIRECTOR_DIR / "history" / "decisions.jsonl"
OBSERVATIONS_PATH = DIRECTOR_DIR / "observations.jsonl"
PACKETS_DIR = DIRECTOR_DIR / "packets"

#: How many decision states a Founder decision may record. Kept separate
#: from RecommendationStatus (director_reviewers.py) on purpose: a
#: reviewer's status is what it proposes; a decision is what the Founder
#: did about it — two different vocabularies for two different actors.
DECISION_VALUES = ("APPROVED", "REJECTED", "DEFERRED")


class BridgeError(RuntimeError):
    """The bridge could not read or write its own state."""


class ReviewerBrief(BaseModel):
    reviewer_id: str
    role: str
    provider: str
    model: str | None
    confidence: float
    status: str


class RoundSummary(BaseModel):
    """A compact, bounded record of one round — never the full reviewer
    text. Derived entirely from observations.jsonl + packets/; rebuilt
    fresh each time, never hand-edited."""

    round_id: str
    snapshot_id: str
    snapshot_version: int
    first_recorded_at: str
    reviewers: list[ReviewerBrief]
    has_synthesis: bool
    recommendation_type: str | None
    recommendation_status: str | None
    founder_approval_required: bool | None
    summary: str


class FounderDecision(BaseModel):
    round_id: str
    decision: str  # one of DECISION_VALUES
    rationale: str
    decided_at: str
    decided_by: str = "Founder"


#: 2026-09-09 context-leak hardening: the bridge itself must keep resolving
#: the REAL canonical live-data path/DB path/secrets for its own fingerprint
#: and env-exclusion logic (never break that) — but nothing that reaches a
#: model, whether the OpenAI Director or a Claude subprocess, should ever
#: see those literal values. `_redact_sensitive_context` is the one choke
#: point both paths go through: `load_constitution()` (the leak this was
#: written for — constitution.md names the live-data path directly, and
#: that text flows into `get_relevant_history()` -> `collect_bridge_state()`
#: -> the Director's own prompt), `call_openai_director`/
#: `call_openai_director_evaluation` (defense in depth over the whole JSON
#: payload, not just the constitution text within it), and
#: `invoke_claude_code`'s `full_prompt` (the actual text a Claude subprocess
#: receives — the most important one, since that model can echo back
#: whatever it was shown). Computed fresh every call, never cached, so a rotated
#: key or relocated live-data root is picked up immediately.
_REDACTION_PLACEHOLDER_LIVE_DATA_ROOT = "[CANONICAL_LIVE_DATA_ROOT]"
_REDACTION_PLACEHOLDER_LIVE_DB = "[CANONICAL_LIVE_DB]"
_REDACTION_PLACEHOLDER_SECRET = "[REDACTED_SECRET]"


def _sensitive_strings_to_redact() -> list[tuple[str, str]]:
    """Real, resolved secret-shaped strings paired with their semantic
    replacement, longest-first (so a full path is masked before a shorter
    substring of it could partially match). Best-effort: any resolution
    failure here means fewer redactions, never a crash — this function is
    never load-bearing for the bridge's own correctness, only for what
    outbound text does NOT contain."""
    pairs: list[tuple[str, str]] = []
    try:
        from app.core.db_safety import CANONICAL_LIVE_DB_PATH

        db_path = str(CANONICAL_LIVE_DB_PATH)
        pairs.append((db_path, _REDACTION_PLACEHOLDER_LIVE_DB))
        root = str(Path(db_path).parent.parent)
        if len(root) > 3:
            pairs.append((root, _REDACTION_PLACEHOLDER_LIVE_DATA_ROOT))
    except Exception:  # noqa: BLE001
        pass
    village_root_env = os.getenv("VILLAGE_DATA_ROOT")
    if village_root_env:
        pairs.append((village_root_env, _REDACTION_PLACEHOLDER_LIVE_DATA_ROOT))
    for key in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TAVILY_API_KEY",
        "OPENROUTER_API_KEY", "BRAVE_SEARCH_API_KEY", "DATABASE_URL",
    ):
        value = os.getenv(key)
        if value and len(value) >= 8:
            pairs.append((value, _REDACTION_PLACEHOLDER_SECRET))
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs


def _redact_sensitive_context(text: str) -> str:
    """Apply every known real->placeholder substitution to outbound text
    headed for a model (OpenAI Director or Claude). Never applied to
    anything the bridge uses for its own fingerprinting/safety checks."""
    for real_value, placeholder in _sensitive_strings_to_redact():
        if real_value and real_value in text:
            text = text.replace(real_value, placeholder)
    return text


def load_constitution(path: Path = CONSTITUTION_PATH) -> str:
    if not path.exists():
        raise BridgeError(f"no constitution found at {path}.")
    return _redact_sensitive_context(path.read_text())


def _load_all_observations(observations_path: Path) -> list[dict[str, Any]]:
    if not observations_path.exists():
        return []
    records = []
    with observations_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def rebuild_rounds_history(
    *,
    observations_path: Path = OBSERVATIONS_PATH,
    packets_dir: Path = PACKETS_DIR,
    history_path: Path = ROUNDS_HISTORY_PATH,
) -> list[RoundSummary]:
    """Regenerate .director/history/rounds.jsonl from the authoritative
    sources. Deterministic and idempotent — safe to call after every round
    (director_loop.py and director_synthesis.py both do, automatically) or
    by hand at any time. Never trust a hand edit to this file; it will be
    silently overwritten on the next call."""
    records = _load_all_observations(observations_path)
    by_round: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        by_round.setdefault(rec["round_id"], []).append(rec)

    summaries: list[RoundSummary] = []
    for round_id, recs in by_round.items():
        successful = [r for r in recs if "output" in r]
        if not successful:
            continue  # every attempt for this round failed; nothing to summarize
        reviewers = [
            ReviewerBrief(
                reviewer_id=r["reviewer_id"], role=r["reviewer_role"], provider=r["provider"],
                model=r.get("model"), confidence=r["output"]["confidence"], status=r["output"]["status"],
            )
            for r in successful
        ]
        primary = next((r for r in successful if r["reviewer_role"] == "PRIMARY"), successful[0])
        first_recorded_at = min(r["recorded_at"] for r in recs)

        packet_path = packets_dir / f"{round_id}.json"
        has_synthesis = packet_path.exists()
        recommendation_type = recommendation_status = None
        founder_approval_required = None
        summary_text = primary["output"].get("interpretation", "")[:280]
        if has_synthesis:
            packet = json.loads(packet_path.read_text())
            recommendation_type = packet.get("recommendation_type")
            recommendation_status = packet.get("recommendation_status")
            founder_approval_required = packet.get("founder_approval_required")
            summary_text = packet.get("smallest_safe_next_diagnostic_step", summary_text)[:280]
        else:
            recommendation_type = primary["output"].get("recommendation_type")
            recommendation_status = primary["output"].get("status")

        summaries.append(
            RoundSummary(
                round_id=round_id,
                snapshot_id=primary["snapshot_id"],
                snapshot_version=primary["snapshot_version"],
                first_recorded_at=first_recorded_at,
                reviewers=reviewers,
                has_synthesis=has_synthesis,
                recommendation_type=recommendation_type,
                recommendation_status=recommendation_status,
                founder_approval_required=founder_approval_required,
                summary=summary_text,
            )
        )

    summaries.sort(key=lambda s: s.first_recorded_at)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w") as f:
        for s in summaries:
            f.write(s.model_dump_json() + "\n")
    return summaries


def record_founder_decision(
    round_id: str,
    decision: str,
    rationale: str,
    *,
    decided_by: str = "Founder",
    decisions_path: Path = DECISIONS_PATH,
) -> FounderDecision:
    """Append one Founder decision. The only history component here that
    is NOT derived/rebuildable — nothing else records what the Founder
    actually decided, so this is a real, authoritative, append-only
    ledger. Never called automatically; a decision is a human act."""
    if decision not in DECISION_VALUES:
        raise BridgeError(f"decision must be one of {DECISION_VALUES}, got {decision!r}.")
    record = FounderDecision(
        round_id=round_id, decision=decision, rationale=rationale,
        decided_at=datetime.now(timezone.utc).isoformat(), decided_by=decided_by,
    )
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    with decisions_path.open("a") as f:
        f.write(record.model_dump_json() + "\n")
    return record


def _load_decisions(decisions_path: Path) -> list[FounderDecision]:
    if not decisions_path.exists():
        return []
    out = []
    with decisions_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(FounderDecision.model_validate_json(line))
    return out


def get_relevant_history(
    *,
    max_recent_rounds: int = 5,
    max_pending_rounds: int = 10,
    constitution_path: Path = CONSTITUTION_PATH,
    history_path: Path = ROUNDS_HISTORY_PATH,
    decisions_path: Path = DECISIONS_PATH,
) -> dict[str, Any]:
    """The one bounded package any downstream reviewer should be given —
    never the raw contents of every snapshot/observation/packet ever
    produced. Three parts:

    - constitution: the full (short, hand-curated) static document.
    - recent_rounds: the last `max_recent_rounds` rounds, most recent
      first — bounded recency window.
    - pending_rounds: any round whose recommendation_status is not
      OBSERVATION_ONLY and has no recorded Founder decision yet, capped at
      `max_pending_rounds` — bounded by relevance (still awaiting a
      decision) rather than by recency, so an old undecided round is never
      silently dropped just because newer rounds pushed it out of the
      recency window. De-duplicated against recent_rounds.
    - decisions: every recorded Founder decision — inherently small and
      high-value, kept unbounded (there will never be many).
    """
    if not history_path.exists():
        rebuild_rounds_history(history_path=history_path)

    constitution = load_constitution(constitution_path)

    rounds: list[RoundSummary] = []
    if history_path.exists():
        with history_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rounds.append(RoundSummary.model_validate_json(line))
    rounds.sort(key=lambda s: s.first_recorded_at, reverse=True)

    decisions = _load_decisions(decisions_path)
    decided_round_ids = {d.round_id for d in decisions}

    recent = rounds[:max_recent_rounds]
    recent_ids = {r.round_id for r in recent}

    pending = [
        r for r in rounds
        if r.round_id not in recent_ids
        and r.round_id not in decided_round_ids
        and r.recommendation_status not in (None, "OBSERVATION_ONLY")
    ][:max_pending_rounds]

    return {
        "constitution": constitution,
        "recent_rounds": [r.model_dump() for r in recent],
        "pending_rounds": [r.model_dump() for r in pending],
        "decisions": [d.model_dump() for d in decisions],
    }


# =============================================================================
# Closed-loop round orchestration: Claude Code <-> OpenAI Director.
#
# Everything above this line is the pre-existing context/history layer for
# the reviewer pipeline (director_reviewers.py/director_loop.py) — read,
# never duplicated. Everything below is new: it replaces the Founder
# manually copying Claude Code's output into ChatGPT and its instructions
# back into Claude Code with one local process that does both hops itself,
# while the Founder supervises rather than transports.
#
# `BridgeSafetyLevel` (0/1/2) is a DELIBERATELY SEPARATE axis from the
# constitution's existing "Level 1 observation / Level 2A/2B" language
# (section 4 above) — that numbering governs what the *reviewer/broker*
# system may do to the Village; this one governs what *Claude Code*, when
# invoked as a subprocess by this bridge, is permitted to do on one round.
# They are not the same scale and are never printed without the
# disambiguating "Bridge" qualifier.
# =============================================================================


class BridgeError2(RuntimeError):
    """Round orchestration failed. Distinct from BridgeError (the
    context/history layer above) so a caller can tell "the history store
    is broken" apart from "this round could not complete" without either
    exception type silently swallowing the other."""


class BridgeSafetyLevel(int, enum.Enum):
    #: Inspect only: code, git, Fishbowl GET APIs, logs, non-mutating
    #: tests. No code changes, no live DB writes, no control endpoints.
    READ_ONLY = 0
    #: Edit working-tree code, run tests, use fixture/temp DBs, start
    #: isolated servers. Never the canonical live DB, never a live
    #: control endpoint, never commit or push.
    SANDBOX = 1
    #: Live Run Event/Period/Day, canonical DB mutation, migration,
    #: commit, push, deploy. Always requires Founder approval; never
    #: executed autonomously by this bridge in this phase, approved or not.
    CONSEQUENTIAL = 2


#: HARD SAFETY BOUNDARY — read this before touching anything below.
#:
#: The acceptance round on 2026-09-09 discovered that `--permission-mode
#: bypassPermissions` does exactly what its name says: it skips permission
#: *checking* entirely, so --allowedTools/--disallowedTools were being
#: enforced by nothing. Empirically verified replacement (two real,
#: isolated `claude -p` probes, not just documentation):
#:
#:   --permission-mode dontAsk --setting-sources ""
#:
#: - `dontAsk` is genuine default-deny: any tool not explicitly present in
#:   --allowedTools is denied outright (`permission_denials` populated,
#:   nothing executes, no prompt to hang on). Probe: Bash entirely absent
#:   from --allowedTools -> `echo hello > file` was denied, file never
#:   created.
#: - `--setting-sources ""` is required alongside it: this repo's own
#:   .claude/settings.local.json grants broad standing permissions
#:   (`Bash(git commit -m ' *)`, `Bash(.venv/bin/python *)`, etc.) that a
#:   nested session would otherwise inherit and that would silently
#:   override anything this bridge tries to restrict. Never omit this flag.
#: - Fine-grained Bash(<pattern>) denial also verified for real: with Edit/
#:   Write allowed and `Bash(git commit:*)` disallowed, in an isolated
#:   throwaway repo, a file edit succeeded and `git commit -am` was denied
#:   outright — no commit appeared in `git log`.
#:
#: Design principle for both levels below: ALLOWLIST, not denylist. Level 0
#: and Level 1 both enumerate exactly what may run; anything unlisted is
#: denied by `dontAsk` regardless of how it's spelled — this is what "do
#: not rely only on command spelling" actually requires structurally,
#: rather than trying to enumerate every dangerous phrasing. The
#: --disallowedTools entries that remain are a second, redundant layer
#: (defense in depth / self-documentation), never the only layer.
#:
#: Three layers protect the canonical live DB / control endpoints / git
#: history specifically, because tool-name pattern matching alone cannot
#: be perfectly robust against a sufficiently creative command:
#:   1. Tool allowlist (this dict) — mechanical, proven above.
#:   2. Environment isolation (invoke_claude_code) — the subprocess never
#:      receives VILLAGE_DATA_ROOT or a live DATABASE_URL, so even
#:      legitimate app code run inside the sandbox resolves to the
#:      harmless repo-root stub, never the real external canonical path.
#:   3. Deterministic post-round verification (run_once) — the
#:      authoritative backstop: simulation day/period/max-event-id and a
#:      live-DB fingerprint (size + mtime + integrity + table count) are
#:      compared before/after every round, live, regardless of what the
#:      first two layers did or didn't catch. This is the layer the
#:      Founder/Director's own textual judgment may never override.
#:
#: 2026-09-09 permission-escape investigation (real, isolated `claude -p`
#: probes — see scripts/director_bridge_permission_escape_probe.py):
#: prompted by a real DirectorEvaluation flagging `Bash(find:*)` during the
#: first watch acceptance test. Two things were CONFIRMED (independently
#: verified via git log/branch/filesystem state, never by trusting Claude's
#: own narrative):
#:   - Shell CHAINING (`&&`, `;`, `|`, redirects `>`/`>>`) through an
#:     allowed prefix is correctly DENIED — Claude Code's matcher decomposes
#:     a compound command line and checks each part, it is not a naive
#:     whole-string prefix match. `git status && touch x`, `cat f; touch
#:     x`, `ls | tee x`, `cat f > x` were all denied outright; not a
#:     bypass.
#:   - The matcher checks only the LEADING subcommand, never git's own
#:     flags/positional args: `git log --output=FILE` / `git diff
#:     --output=FILE` really did write an arbitrary file (git's own
#:     `--output` flag, not a shell trick), and `git branch NEWNAME` really
#:     did create a branch — both proceeded with ZERO permission_denials,
#:     confirmed by independently reading the resulting file/branch, not by
#:     trusting the CLI's stdout. `find`'s `-exec`/`-execdir`/`-delete` were
#:     never actually executed in the probe (Claude itself declined, having
#:     recognized the request as a likely prompt-injection pattern once it
#:     was bundled with enough other items) — but by the SAME mechanism
#:     that broke `git branch`/`git log --output`, a subcommand-only match
#:     gives `find`'s own flags no scrutiny either, and `find . -type f`/
#:     `find . -name "*.txt"` ran with the identical zero-denial signature
#:     as the confirmed bypasses. Treated as confirmed by structural
#:     equivalence, not "unconfirmed" — see the module's investigation
#:     report for the full reasoning.
#: Resolution: Level 0 now grants NO Bash at all (Read/Grep/Glob only) —
#: collect_bridge_state() already hands Claude a bounded git status/log/
#: diff summary as TEXT in the prompt, so live Bash git access was never
#: actually necessary for a read-only round, and removing it removes the
#: entire class of "matcher only checks the leading subcommand" risk in one
#: move rather than trying to enumerate every dangerous flag. Level 1 lost
#: `Bash(find:*)`, `Bash(git branch:*)`, `Bash(git log:*)`, `Bash(git
#: diff:*)` for the same confirmed reasons, AND `Bash(python3:*)` /
#: `Bash(.venv/bin/python:*)` — CONFIRMED (independently: a real HTTP
#: response body, a real file on disk outside the sandbox dir, a real git
#: commit that appeared in `git log`) to let arbitrary Python reach the
#: network, write anywhere the OS permits, and invoke `subprocess` to run
#: literally anything on the denylist, including `git commit`. Unlike shell
#: chaining, this is NOT a matcher gap — the matcher correctly identifies
#: and allows the single command `python3 -c "..."`; everything after `-c`
#: is opaque Python semantics no external command matcher can inspect, so
#: no flag-level fix exists here the way `--output=` could theoretically be
#: individually blocked. `pytest`/`.venv/bin/pytest` are kept (Level 1's
#: whole purpose is running tests) despite sharing the same opacity in
#: principle — a real test file's content is at least visible in the
#: round's own diff evidence, unlike a one-shot inline `-c` string; this is
#: a disclosed, accepted residual, not a claim that pytest is fully safe.
#: 2026-09-09 workspace-isolation hardening: real, isolated `claude -p`
#: probes (see scripts/director_bridge_permission_escape_probe.py and this
#: module's investigation report) CONFIRMED that Claude Code's tool
#: permission syntax supports path-scoped grants for file tools —
#: `Tool(<glob-relative-to-cwd>)`, e.g. `Read(./**)` — not just command-
#: prefix scoping for Bash. This closes the exact gap the prior pass left
#: open: Read/Grep/Glob (and, for Level 1, Edit/Write) were previously
#: granted WITHOUT any path restriction, so a session that somehow learned
#: an absolute path outside its intended scope (e.g. the live-data root,
#: if it ever leaked into context — see _redact_sensitive_context) could
#: still read or, at Level 1, write it. Real probe evidence: `Read(./**)`
#: let an in-workspace read through and denied an absolute out-of-workspace
#: read outright (`permission_denials` populated); `Edit(./**)`/
#: `Write(./**)`/`Glob(./**)`/`Grep(./**)` behaved identically. `./**` is
#: resolved against the session's cwd — Level 0 keeps cwd=REPO_ROOT (it
#: legitimately inspects the real project), so `./**` there scopes reads to
#: the repo itself, excluding sibling directories like the live-data root
#: entirely. Level 1 now ALWAYS runs inside a freshly created, disposable
#: workspace (see _create_level1_workspace) — `./**` there scopes Claude to
#: that throwaway copy alone; it never has any path-based reason to reach
#: the real repo, the live data root, or anything else on the filesystem.
#: Each entry is (builtin_toolset, allowed, disallowed):
#:   - builtin_toolset -> the CLI's `--tools` flag: the exhaustive set of
#:     built-in tools the session may even be AWARE of. "default" means "all
#:     built-in tools" (byte-for-byte the pre-2026-09-10 behavior — the flag
#:     is not emitted at all in that case; see invoke_claude_code). Anything
#:     else is a hard, mechanical ceiling: a tool absent from this string is
#:     never registered for the session, so the model cannot emit a tool_use
#:     for it and there is nothing for the permission layer to allow or deny.
#:   - allowed / disallowed -> `--allowedTools` / `--disallowedTools`: the
#:     permission-layer allowlist and (redundant, defense-in-depth) denylist,
#:     operating on whatever survived the `--tools` ceiling.
#:
#: 2026-09-10 Level-0 Bash proof hardening: Level 0's builtin_toolset is now
#: an explicit "Read Grep Glob" rather than "default" + a Bash denylist
#: entry. This makes "Level 0 cannot invoke Bash" a TOOL-REGISTRATION fact,
#: not a permission-matching outcome — verified mechanically two ways in the
#: real CLI probe: (a) argv shows `--tools "Read Grep Glob"` with Bash
#: absent, and (b) the `claude` stream-json `system/init` event enumerates
#: the live session toolset as exactly ["Glob","Grep","Read"], Bash not
#: present. The `--disallowedTools` "Bash" entry is KEPT purely as
#: belt-and-suspenders self-documentation; it is no longer the load-bearing
#: mechanism. Background: round bd046f7218294d50 proved that merely omitting
#: Bash from --allowedTools was not sufficient (a bare Bash("true") executed
#: with no permission_denials entry); `--tools` closes that gap at the
#: registration layer instead of the matcher layer.
#:
#: 2026-09-10 test-runner hardening: `Bash(pytest:*)` / `Bash(.venv/bin/
#: pytest:*)` were dead weight — `.venv` is excluded from every Level-1
#: workspace (see _WORKSPACE_RSYNC_EXCLUDES) and neither binary exists
#: there, confirmed by the first real Level-1 acceptance round finding no
#: way to execute scripts/test_fishbowl.py at all. They are also, on their
#: own terms, exactly the kind of wildcard grant this module's own design
#: principle above rejects: `pytest:*` would let Claude supply arbitrary
#: flags (`-p`, `--doctest-modules`, arbitrary node-ids reaching outside
#: the intended target) the instant pytest became reachable any other way.
#: Replaced by `_level1_test_runner_allowed_tools()`: one EXACT (no `:*`)
#: Bash permission string per entry in director_bridge_test_runner.
#: ALLOWED_TEST_TARGETS, invoking the real repo's own `.venv/bin/python`
#: (never copied into the workspace, referenced by absolute path) against
#: that bridge-owned script. Exact-match means Claude's Bash tool_use
#: command must reproduce the string byte-for-byte — no extra flag,
#: alternate target, or shell metacharacter survives that comparison, and
#: the script itself independently re-validates the target, cwd, and
#: interpreter identity regardless (see its module docstring). This is not
#: "python3 access" in any general sense: the only Python this session can
#: ever invoke is this one fixed script with this one fixed argument.
def _level1_test_runner_allowed_tools() -> str:
    return " ".join(
        f"Bash({_test_runner.REAL_HOST_PYTHON} scripts/director_bridge_test_runner.py "
        f"--target {target})"
        for target in _test_runner.ALLOWED_TEST_TARGETS
    )


def _level1_test_runner_instructions() -> str:
    commands = "\n".join(
        f"  {_test_runner.REAL_HOST_PYTHON} scripts/director_bridge_test_runner.py --target {target}"
        for target in _test_runner.ALLOWED_TEST_TARGETS
    )
    return (
        "To run a test, invoke ONE of the following commands EXACTLY as written below — "
        "reproduced verbatim, no added flags, no different target, no shell operators. "
        "Anything else is denied at the permission layer before it runs, and the script "
        "itself independently refuses any other target or environment regardless:\n"
        f"{commands}\n"
        "This is the ONLY way to run a test or reach a Python interpreter this session — "
        "there is no general pytest, python3, or .venv/bin/python access."
    )


_LEVEL_TOOLS: dict[BridgeSafetyLevel, tuple[str, str, str]] = {
    BridgeSafetyLevel.READ_ONLY: (
        "Read Grep Glob",
        "Read(./**) Grep(./**) Glob(./**)",
        # Redundant belt-and-suspenders: with the `--tools` ceiling above,
        # Bash/Edit/Write are never registered for a Level-0 session at all,
        # so this denylist has nothing to act on. Kept as explicit,
        # self-documenting defense in depth, not as the enforcement path.
        "Edit Write NotebookEdit Bash",
    ),
    BridgeSafetyLevel.SANDBOX: (
        # Unchanged (2026-09-10): Level 1 keeps the full built-in toolset;
        # its restriction is entirely at the --allowedTools/--disallowedTools
        # permission layer, exactly as before. "default" makes
        # invoke_claude_code omit the --tools flag entirely, so Level 1's
        # argv is byte-for-byte identical to the prior implementation.
        "default",
        "Read(./**) Grep(./**) Glob(./**) Edit(./**) Write(./**) "
        "Bash(git status:*) Bash(git stash:*) Bash(git add:*) "
        "Bash(.venv/bin/uvicorn:*) " + _level1_test_runner_allowed_tools(),
        # cat/ls/mkdir/touch removed 2026-09-09: Read/Write/Glob (path-
        # scoped to the isolated workspace) already cover every legitimate
        # need those four commands served, without Bash's total lack of
        # path scoping for their arguments.
        "Bash(git commit:*) Bash(git push:*) Bash(git reset:*) Bash(git checkout:*) "
        "Bash(git branch:*) Bash(git log:*) Bash(git diff:*) Bash(find:*) "
        "Bash(python3:*) Bash(.venv/bin/python:*) "
        "Bash(rm:*) Bash(rm -rf:*) Bash(curl:*) Bash(wget:*) Bash(sqlite3:*) "
        "Bash(scp:*) Bash(ssh:*) Bash(alembic:*) "
        "Bash(sh:*) Bash(bash:*) Bash(zsh:*) Bash(chmod:*) Bash(chown:*) Bash(perl:*) Bash(node:*) "
        "Bash(cat:*) Bash(ls:*) Bash(mkdir:*) Bash(touch:*)",
    ),
}

_SAFETY_PREAMBLE = {
    BridgeSafetyLevel.READ_ONLY: (
        "SAFETY LEVEL 0 — READ ONLY, MECHANICALLY ENFORCED. Your tool access this "
        "session is restricted at the permission layer (not just by instruction) to "
        "Read/Grep/Glob ONLY — there is no Bash tool in this session at all, so there is "
        "nothing to attempt via git, find, cat, ls, or any other shell command; all of "
        "them will be denied outright. This is enforced by the CLI itself, not by your "
        "judgment. Relevant Village/Fishbowl state and a git status/log/diff summary "
        "have already been collected and are included below; you do not have live "
        "network access this round. Report findings only."
    ),
    BridgeSafetyLevel.SANDBOX: (
        "SAFETY LEVEL 1 — SANDBOX DEVELOPMENT, MECHANICALLY ENFORCED. You may edit "
        "working-tree files. The following are not in your allowlist and will be denied "
        "at the permission layer if attempted, regardless of how you phrase them: git "
        "commit, git push, git reset, git checkout, git branch, git log, git diff, find, "
        "python3, .venv/bin/python, .venv/bin/pytest, bare pytest, or any other Python "
        "interpreter, rm, curl, wget, sqlite3 (CLI), scp, ssh, alembic. General Python "
        "access is unavailable specifically because it can run arbitrary code this "
        "permission layer cannot inspect, including making network requests or invoking "
        "subprocesses that defeat every other restriction here — this is not an "
        "oversight. There is exactly ONE narrow exception: a fixed, bridge-owned test "
        "runner, described below, that lets you execute (never author or modify the "
        "invocation of) one approved test target.\n\n"
        f"{_level1_test_runner_instructions()}\n\n"
        "You also do not have VILLAGE_DATA_ROOT or a live DATABASE_URL in your "
        "environment this round — any database path you resolve through normal app code "
        "will be a harmless local stub, never the canonical live database; the test "
        "runner above additionally points VILLAGE_DATA_ROOT at a fixture directory "
        "inside this workspace for anything it runs. If your task requires anything on "
        "the denied list above, or a test target not on the runner's allowlist, say so "
        "and stop instead of working around the restriction."
    ),
}

#: 2026-09-10: per-level bounded timeouts, replacing one global 300s
#: constant after round bd046f7218294d50 was hard-killed mid-task (a
#: legitimate, still-progressing Level-0 read-only inspection, not a hang)
#: at exactly the old 300s ceiling. Both remain hard subprocess kills —
#: `subprocess.run(..., timeout=...)` — never an unlimited execution, never
#: retried automatically, and a timeout is still always a deterministic
#: failure (`stopped_claude_timeout` -> `CLAUDE_FAILED`; see
#: deterministic_safety_failure below), regardless of which bound applies.
#: Level 1 gets a longer bound because engineering rounds (edit + run
#: pytest inside the isolated workspace) legitimately take longer than
#: Level 0's read-only inspection.
CLAUDE_LEVEL0_TIMEOUT_SECONDS = 420
CLAUDE_LEVEL1_TIMEOUT_SECONDS = 1200

_CLAUDE_TIMEOUT_BY_LEVEL: dict[BridgeSafetyLevel, int] = {
    BridgeSafetyLevel.READ_ONLY: CLAUDE_LEVEL0_TIMEOUT_SECONDS,
    BridgeSafetyLevel.SANDBOX: CLAUDE_LEVEL1_TIMEOUT_SECONDS,
}

BRIDGE_LOCK_PATH = DIRECTOR_DIR / "autonomous" / "bridge.lock"
BRIDGE_LOG_PATH = DIRECTOR_DIR / "audit" / "bridge_rounds.jsonl"
#: Where a Level-1 round's full sandbox diff is preserved before the
#: workspace is destroyed. Under .director/ (bridge bookkeeping, never a
#: tracked source path); a read-only audit artifact, never auto-applied.
WORKSPACE_DIFF_DIR = DIRECTOR_DIR / "audit" / "workspace_diffs"

DIRECTOR_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["continue", "stop", "request_approval"]},
        "task_for_claude": {
            "type": "string",
            "description": "A specific, scoped instruction for Claude Code to execute this round. "
            "Empty string if decision is 'stop'.",
        },
        "reason": {"type": "string"},
        "required_checks": {"type": "array", "items": {"type": "string"}},
        "safety_level": {
            "type": "integer",
            "enum": [0, 1, 2],
            "description": "0=read-only, 1=sandbox development, 2=consequential (always requires approval).",
        },
        "requires_founder_approval": {"type": "boolean"},
        "stop_conditions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Conditions under which Claude's result should be rejected rather than trusted.",
        },
    },
    "required": [
        "decision", "task_for_claude", "reason", "required_checks",
        "safety_level", "requires_founder_approval", "stop_conditions",
    ],
}

_DIRECTOR_SYSTEM_PROMPT = """You are the OpenAI Director for a local development bridge that supervises \
one Claude Code CLI session per round on The Internal Village codebase. You are given compact, \
structured project and Village state (never raw transcripts). Respond with exactly one structured \
decision for this round.

Safety levels available to you:
0 (READ_ONLY): Claude may only inspect — no file edits, no DB writes, no control endpoints.
1 (SANDBOX): Claude may edit the working tree and run tests, but never touch the canonical live \
database, never call a live control endpoint, never commit or push.
2 (CONSEQUENTIAL): live simulation control, live DB mutation, migration, commit, push, deploy. \
This bridge NEVER executes level 2 autonomously in its current phase, no matter what you decide — \
always set requires_founder_approval=true if you believe level 2 is warranted, and expect it to \
stop there.

task_for_claude must be a single, specific, boundedly-scoped instruction — not a vague goal. If you \
have nothing useful for Claude to do this round, set decision="stop" and leave task_for_claude empty.
Never ask Claude to run a live control endpoint, touch the canonical live database, commit, or push \
unless safety_level=2 and requires_founder_approval=true."""


DIRECTOR_EVALUATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "outcome": {"type": "string", "enum": ["accepted", "needs_revision", "blocked"]},
        "summary": {"type": "string"},
        "evidence_assessment": {
            "type": "string",
            "description": "What the deterministic evidence (exit code, changed files, DB fingerprint) "
            "actually supports about Claude's claimed result.",
        },
        "remaining_risks": {"type": "array", "items": {"type": "string"}},
        "recommended_next_task": {
            "type": "string",
            "description": "A specific instruction for a possible follow-up round. Not executed "
            "automatically this phase.",
        },
        "recommended_safety_level": {"type": "integer", "enum": [0, 1, 2]},
        "requires_founder_approval": {"type": "boolean"},
        "stop_reason": {
            "type": "string",
            "description": "Why this round is ending here rather than continuing automatically.",
        },
    },
    "required": [
        "outcome", "summary", "evidence_assessment", "remaining_risks",
        "recommended_next_task", "recommended_safety_level", "requires_founder_approval", "stop_reason",
    ],
}

_DIRECTOR_EVALUATION_SYSTEM_PROMPT = """You are the OpenAI Director evaluating the result of a Claude \
Code round you previously requested, for the same local development bridge. You are given: your own \
prior decision, Claude's captured result (its own text/exit code — untrusted claims), and a set of \
DETERMINISTIC, MECHANICALLY-VERIFIED facts about what actually happened (changed files, live-DB \
fingerprint before/after, whether a safety violation was flagged, exit code, timeout, and — for a \
Level-1 round — the bridge-owned test runner's own captured result: which approved test target ran, \
its exit code/timeout/stdout/stderr, or its absence if no approved test was executed this round). The \
test-runner result is captured independently of anything Claude claims in its own summary — treat it, \
like the other deterministic facts, as authoritative over Claude's narrative, and treat the ABSENCE of \
a test-runner result as meaning no approved test actually ran this round, regardless of what Claude's \
own text claims about testing.

The deterministic facts are authoritative and you must never contradict them: if a safety violation \
was mechanically flagged, or Claude's process failed/timed out, outcome MUST be "blocked" regardless of \
how plausible Claude's own narrative sounds. Your job is to judge the QUALITY and MEANING of Claude's \
work — is the reasoning sound, is the evidence sufficient, what would a competent reviewer still want \
checked — not to re-verify mechanical facts you're already given.

recommended_next_task is advisory only — nothing in this bridge executes it automatically this phase.
Never recommend safety_level=2 without requires_founder_approval=true."""


class DirectorDecision(BaseModel):
    decision: str
    task_for_claude: str
    reason: str
    required_checks: list[str] = Field(default_factory=list)
    safety_level: int
    requires_founder_approval: bool
    stop_conditions: list[str] = Field(default_factory=list)


class DirectorEvaluation(BaseModel):
    outcome: str
    summary: str
    evidence_assessment: str
    remaining_risks: list[str] = Field(default_factory=list)
    recommended_next_task: str
    recommended_safety_level: int
    requires_founder_approval: bool
    stop_reason: str
    overridden_by_deterministic_check: bool = False


class ClaudeInvocationResult(BaseModel):
    invoked: bool
    argv: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0


class BridgeRoundRecord(BaseModel):
    round_id: str
    #: None for a standalone `run_once` call or the first round of a watch
    #: run; the previous round's `round_id` for every subsequent watch
    #: round — the auditable parent/child chain Step 8 requires. Set only
    #: by `run_watch`; `run_once` itself never sets this (it has no notion
    #: of being part of a sequence).
    parent_round_id: str | None = None
    timestamp: str
    objective: str
    director_input: dict[str, Any]
    director_decision: dict[str, Any] | None = None
    director_error: str | None = None
    claude_task: str | None = None
    claude_result: ClaudeInvocationResult | None = None
    #: Extracted from claude_result.stdout for audit convenience (Step 8)
    #: -- never load-bearing; the authoritative source is still
    #: claude_result itself.
    claude_session_id: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    diff_stat: str | None = None
    #: For a Level-1 (SANDBOX) round only: repo-relative path to the full
    #: unified diff of exactly what Claude changed inside the disposable
    #: workspace, written to .director/audit/workspace_diffs/<round_id>.patch
    #: BEFORE the workspace is destroyed. None if Claude changed nothing (or
    #: the round was not Level 1). This file is a READ-ONLY audit artifact —
    #: nothing in this bridge ever applies it to REPO_ROOT; adopting an
    #: accepted sandbox implementation is a separate, deliberate, manual step.
    workspace_diff_path: str | None = None
    #: For a Level-1 round only: the JSON text director_bridge_test_runner.py
    #: itself wrote to <workspace>/.director/level1_test_result.json this
    #: round (see _read_level1_test_result) — target, exit_code, timed_out,
    #: stdout/stderr tails. None if no approved test target was invoked this
    #: round. Captured mechanically, independent of anything Claude's own
    #: summary claims; also forwarded into the second DirectorEvaluation
    #: call's deterministic_evidence.
    test_results: str | None = None
    #: 2026-09-10 cumulative staging workspace: for a Level-1 round that
    #: used a persistent Level1StagingSession only (None otherwise,
    #: including every Level-1 round that got its own ephemeral
    #: create/destroy workspace as before). level1_checkpoint_before is the
    #: staging workspace's own git HEAD immediately before this round ran —
    #: the exact rollback target if this round turns out unsafe.
    #: level1_retained records the retain/rollback decision made right
    #: before this record is persisted (True = this round's changed_files
    #: were committed into the staging workspace's own history; False = the
    #: workspace was `git reset --hard`+cleaned back to
    #: level1_checkpoint_before). level1_commit_after is the resulting
    #: staging workspace HEAD either way — equal to level1_checkpoint_before
    #: on rollback, or the new commit on retain (see
    #: _level1_round_is_retainable / _level1_commit_round / _level1_rollback).
    level1_checkpoint_before: str | None = None
    level1_retained: bool | None = None
    level1_commit_after: str | None = None
    safety_level: int | None = None
    founder_approval: dict[str, Any] | None = None
    live_db_snapshot_before: dict[str, Any] | None = None
    live_db_snapshot_after: dict[str, Any] | None = None
    live_db_involvement_suspected: bool = False
    director_evaluation: dict[str, Any] | None = None
    evaluation_error: str | None = None
    errors: list[str] = Field(default_factory=list)
    final_state: str = "unknown"


def _run(cmd: list[str], timeout: int = 15) -> str:
    """A bounded, read-only-by-construction helper — every call site below
    only ever passes read-only git/inspection commands, never anything the
    Director or Claude supplied. Never raises; returns '' on any failure
    so a missing git binary or a cold-start repo never crashes a round."""
    try:
        result = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout,
        )
        return (result.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001 - deliberately broad; this is best-effort context, never load-bearing
        return f"<unavailable: {exc}>"


class GitStateError(RuntimeError):
    """The repository's git state cannot be trusted this round — a hard
    safety stop, never a soft warning. Raised by `_check_git_state()` only;
    deliberately a SEPARATE code path from `_run()` above, which exists
    specifically to swallow git failures into best-effort text for
    Director/reviewer context and must never be reused here — a failed git
    command must never be silently reinterpreted as "no changes" or as an
    ordinary line of evidence text."""


#: git-dir marker files whose mere presence means an operation is mid-flight
#: and the working tree's apparent state cannot be trusted as a clean
#: baseline — checked as files, not by parsing `git status` output, since
#: some of these (e.g. an in-progress rebase) barely show up in porcelain
#: status at all.
_GIT_IN_PROGRESS_MARKERS: tuple[tuple[str, str], ...] = (
    ("MERGE_HEAD", "merge in progress"),
    ("rebase-merge", "rebase in progress"),
    ("rebase-apply", "rebase in progress"),
    ("CHERRY_PICK_HEAD", "cherry-pick in progress"),
    ("REVERT_HEAD", "revert in progress"),
)


def _check_git_state(*, allow_detached_head: bool = False) -> dict[str, Any]:
    """Hard, structural sanity check of the repo's own state — call before
    every watch round (see `run_watch`). Raises `GitStateError` (never
    returns a soft warning, never falls back to `_run()`'s best-effort
    text) on any condition that makes git status/diff output untrustworthy:
    a failed git command, an unresolvable repository, a detached HEAD
    (unless `allow_detached_head=True`, off by default pending a future
    config surface), an in-progress merge/rebase/cherry-pick/revert, an
    unresolved merge conflict, or `git status` output that cannot be
    reliably parsed as ordinary porcelain lines. Returns a dict with
    `detached_head`, `branch`, and `dirty_files` (paths only, `.director/`
    included — callers filter that out themselves, same convention as
    `collect_bridge_state`) only when every check above passes."""

    def _git(*args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
            )
        except Exception as exc:  # noqa: BLE001 - converted to a hard stop below, never swallowed
            raise GitStateError(f"git command failed to execute: {exc}") from exc

    rev_parse = _git("rev-parse", "--git-dir")
    if rev_parse.returncode != 0:
        raise GitStateError(f"repository cannot be resolved: {rev_parse.stderr.strip() or rev_parse.stdout.strip()}")

    git_dir = Path(rev_parse.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = REPO_ROOT / git_dir

    for marker, label in _GIT_IN_PROGRESS_MARKERS:
        if (git_dir / marker).exists():
            raise GitStateError(f"{label} ({marker} present under {git_dir}) — ambiguous git state")

    branch_result = _git("symbolic-ref", "-q", "HEAD")
    detached = branch_result.returncode != 0
    if detached and not allow_detached_head:
        raise GitStateError("HEAD is detached — ambiguous git state, not explicitly allowed")

    status_result = _git("status", "--porcelain=v1", "--untracked-files=all")
    if status_result.returncode != 0:
        raise GitStateError(f"git status failed: {status_result.stderr.strip()}")

    dirty_files: list[str] = []
    for line in status_result.stdout.splitlines():
        if not line.strip():
            continue
        if len(line) < 4 or line[2] != " ":
            raise GitStateError(f"git status output could not be reliably parsed: {line!r}")
        code, path = line[:2], line[3:]
        if "U" in code or code in ("AA", "DD"):
            raise GitStateError(f"unresolved merge conflict in git status: {line!r}")
        dirty_files.append(path)

    return {
        "detached_head": detached,
        "branch": None if detached else branch_result.stdout.strip(),
        "dirty_files": sorted(dirty_files),
    }


def _live_db_fingerprint() -> dict[str, Any]:
    """Best-effort, read-only fingerprint of the canonical live database —
    resolved the same way app.core.db_safety resolves it, never a
    hardcoded or .env-trusted path (see the module's own docstring on why
    that historically went wrong). This is the authoritative before/after
    safety net for this bridge's own rounds (see the HARD SAFETY BOUNDARY
    comment above _LEVEL_TOOLS) — deliberately broader than just file size,
    since an equal-size in-place mutation would pass a size-only check:
    size, mtime, integrity_ok, table_count, and the simulation clock/max
    event id are all compared before vs. after. Never a substitute for
    scripts/director_safe_checks.py's own real integrity check."""
    try:
        from app.core.db_safety import CANONICAL_LIVE_DB_PATH, check_live_db

        check = check_live_db(CANONICAL_LIVE_DB_PATH)
        fingerprint: dict[str, Any] = {
            "path": str(CANONICAL_LIVE_DB_PATH),
            "exists": check.exists,
            "size_bytes": check.size_bytes,
            "healthy": check.healthy,
            "table_count": check.table_count,
            "integrity_ok": check.integrity_ok,
            "mtime": CANONICAL_LIVE_DB_PATH.stat().st_mtime if check.exists else None,
        }
        if check.healthy:
            import sqlite3

            conn = sqlite3.connect(f"file:{CANONICAL_LIVE_DB_PATH}?mode=ro", uri=True)
            try:
                row = conn.execute(
                    "SELECT current_day, current_period, is_paused FROM simulation_clock LIMIT 1"
                ).fetchone()
                fingerprint["current_day"] = row[0] if row else None
                fingerprint["current_period"] = row[1] if row else None
                fingerprint["is_paused"] = bool(row[2]) if row else None
                fingerprint["max_event_id"] = conn.execute("SELECT max(id) FROM events").fetchone()[0]
            finally:
                conn.close()
        return fingerprint
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


#: Every field a mismatch in which means "the live Village moved or the
#: canonical file changed" — checked as a set, not just size_bytes, so an
#: equal-size in-place edit or a simulation advance with no size change
#: can never slip past this net. See the HARD SAFETY BOUNDARY comment
#: above _LEVEL_TOOLS for why this is the authoritative layer.
_FINGERPRINT_INVARIANT_FIELDS = (
    "size_bytes", "mtime", "table_count", "integrity_ok",
    "current_day", "current_period", "is_paused", "max_event_id",
)


def _fingerprint_changed(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return [f for f in _FINGERPRINT_INVARIANT_FIELDS if before.get(f) != after.get(f)]


def _fishbowl_state(base_url: str = "http://127.0.0.1:8000") -> dict[str, Any]:
    """Best-effort GET-only read of the running Fishbowl API — never
    required for a round to proceed (the Village need not even be
    running), so any failure here is captured as a note, not an
    exception."""
    try:
        import httpx

        with httpx.Client(timeout=3.0) as client:
            dashboard = client.get(f"{base_url}/fishbowl/api/dashboard").json()
            events = client.get(f"{base_url}/fishbowl/api/events?limit=3").json()
        clock = dashboard.get("clock") or {}
        return {
            "reachable": True,
            "day": clock.get("day"),
            "period": clock.get("period"),
            "is_paused": clock.get("is_paused"),
            "providers": dashboard.get("providers"),
            "latest_events": [
                {"id": e["id"], "event_type": e["event_type"]} for e in events.get("events", [])
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"reachable": False, "note": str(exc)}


def collect_bridge_state(objective: str) -> dict[str, Any]:
    """The compact, structured input handed to the OpenAI Director —
    deliberately NOT raw diffs or transcripts. Every field here is either
    a bounded summary (log -5, diff --stat, last 3 events) or already
    a bounded package (get_relevant_history())."""
    # .director/** is this bridge's (and the pre-existing reviewer
    # pipeline's) own bookkeeping, not project state — hundreds of
    # diagnostic artifacts there would otherwise crowd out every
    # genuinely meaningful line. Excluded here, never in raw `git status`
    # itself, and the exclusion is disclosed via director_noise_excluded
    # rather than silently shrinking the count.
    all_lines = [
        line for line in _run(["git", "status", "--porcelain"]).splitlines() if line.strip()
    ]
    project_lines = [line for line in all_lines if not line[3:].startswith(".director/")]
    changed_files = [line[3:] for line in project_lines]
    return {
        "objective": objective,
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_status_summary": "\n".join(project_lines)[:2000],
        "changed_files": changed_files[:50],
        "director_noise_excluded": len(all_lines) - len(project_lines),
        "latest_commits": _run(["git", "log", "--oneline", "-5"]),
        "diff_summary": _run(["git", "diff", "--stat", "--", ".", ":!.director"])[:2000],
        "village": _fishbowl_state(),
        "history": get_relevant_history(),
    }


class DirectorClient(Protocol):
    """The interface between this broker and whatever is actually producing
    DirectorDecision/DirectorEvaluation objects for a round.

    This is the seam the module docstring's target architecture depends on:

        THIS CHATGPT THREAD
        -> authenticated ChatGPT-to-broker connector
        -> local Director Bridge / safety broker   <- (this module)
        -> Claude Code + Internal Village
        -> structured evidence/result
        -> connector
        -> THIS CHATGPT THREAD

    `OpenAIDirectorClient` below is the only implementation today — the
    OpenAI Director is an INTERIM automation layer standing in for the
    Founder's own ChatGPT thread. `run_once()` never calls
    `call_openai_director`/`call_openai_director_evaluation` (or any
    provider/HTTP concept) directly; it only ever calls a `DirectorClient`.
    A future connector that submits this exact ChatGPT thread's own
    decisions (typed as the same DirectorDecision/DirectorEvaluation
    Pydantic models, over whatever transport that connector uses) is a
    SECOND implementation of exactly this interface — a peer of
    OpenAIDirectorClient, not a special case threaded through run_once's
    control flow. See constitution.md section 8 for that connector as an
    explicit future milestone: NOT built in this phase, deliberately.

    Round orchestration (run_once), the safety gate, and the mechanical
    deterministic-evidence layer are all independent of which
    DirectorClient is plugged in — swapping the client changes WHO is
    reasoning about a round, never what the round is mechanically allowed
    to do."""

    def decide(self, state: dict[str, Any]) -> DirectorDecision: ...

    def evaluate(
        self,
        *,
        decision: DirectorDecision,
        claude_result: ClaudeInvocationResult,
        deterministic: dict[str, Any],
    ) -> DirectorEvaluation: ...


class OpenAIDirectorClient:
    """The interim automation layer: a `DirectorClient` backed by the real
    OpenAI Director (`call_openai_director`/`call_openai_director_evaluation`
    below, unchanged). Constructed once per round in `run_once()`'s default
    argument; a caller wanting a different client (a fixture for tests, or
    eventually the exact-ChatGPT-thread connector) passes its own
    `director_client=` instead — `run_once()` itself never needs to change."""

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name or os.getenv("DIRECTOR_BRIDGE_PROVIDER", "openai")

    def decide(self, state: dict[str, Any]) -> DirectorDecision:
        return call_openai_director(state, provider_name=self.provider_name)

    def evaluate(
        self,
        *,
        decision: DirectorDecision,
        claude_result: ClaudeInvocationResult,
        deterministic: dict[str, Any],
    ) -> DirectorEvaluation:
        return call_openai_director_evaluation(
            decision=decision, claude_result=claude_result, deterministic=deterministic,
            provider_name=self.provider_name,
        )


def call_openai_director(state: dict[str, Any], *, provider_name: str | None = None) -> DirectorDecision:
    """The one call to the OpenAI Director for this round. Reuses
    director_providers.py's ModelProvider abstraction unchanged — no new
    HTTP client, no new auth handling. Raises BridgeError2 on anything
    that isn't a validated DirectorDecision; a round never proceeds on a
    guessed or partially-parsed response."""
    provider_name = provider_name or os.getenv("DIRECTOR_BRIDGE_PROVIDER", "openai")
    try:
        provider = get_model_provider(provider_name)
    except ModelProviderError as exc:
        raise BridgeError2(f"could not construct Director provider {provider_name!r}: {exc}") from exc

    spec = StructuredCallSpec(
        system_prompt=_DIRECTOR_SYSTEM_PROMPT,
        user_content=_redact_sensitive_context(json.dumps(state, default=str)),
        tool_name="submit_director_decision",
        tool_description="Submit this round's decision for the local Director bridge.",
        schema=DIRECTOR_DECISION_SCHEMA,
    )
    try:
        raw = provider.complete_structured(spec)
    except ModelProviderError as exc:
        raise BridgeError2(f"Director provider call failed: {exc}") from exc
    try:
        return DirectorDecision.model_validate(raw)
    except ValidationError as exc:
        raise BridgeError2(f"Director response failed schema validation: {exc}") from exc


def call_openai_director_evaluation(
    *,
    decision: DirectorDecision,
    claude_result: ClaudeInvocationResult,
    deterministic: dict[str, Any],
    provider_name: str | None = None,
) -> DirectorEvaluation:
    """The second Director call: closes the loop the acceptance test's
    architecture describes (state -> decision -> Claude -> deterministic
    verification -> Director evaluation -> structured next recommendation
    -> STOP). `deterministic` carries only mechanically-verified facts
    (changed files, live-DB fingerprint diff, safety-violation flag, exit
    code) — never raw stdout — and the system prompt tells the model those
    facts are authoritative. run_once() enforces that authority in code
    too (see the hard override below it), so this function's contract
    doesn't rely on the model actually honoring the instruction."""
    provider_name = provider_name or os.getenv("DIRECTOR_BRIDGE_PROVIDER", "openai")
    try:
        provider = get_model_provider(provider_name)
    except ModelProviderError as exc:
        raise BridgeError2(f"could not construct Director provider {provider_name!r}: {exc}") from exc

    payload = {
        "prior_decision": decision.model_dump(),
        "claude_result_summary": {
            "invoked": claude_result.invoked,
            "exit_code": claude_result.exit_code,
            "timed_out": claude_result.timed_out,
            "duration_seconds": claude_result.duration_seconds,
            # Bounded: Claude's own claimed result text, truncated — never the
            # full raw stdout/stderr, and never trusted as fact on its own.
            "claimed_result_text": _extract_claude_result_text(claude_result.stdout)[:4000],
        },
        "deterministic_evidence": deterministic,
    }
    spec = StructuredCallSpec(
        system_prompt=_DIRECTOR_EVALUATION_SYSTEM_PROMPT,
        user_content=_redact_sensitive_context(json.dumps(payload, default=str)),
        tool_name="submit_director_evaluation",
        tool_description="Submit this round's evaluation of Claude's result for the local Director bridge.",
        schema=DIRECTOR_EVALUATION_SCHEMA,
    )
    try:
        raw = provider.complete_structured(spec)
    except ModelProviderError as exc:
        raise BridgeError2(f"Director evaluation call failed: {exc}") from exc
    try:
        return DirectorEvaluation.model_validate(raw)
    except ValidationError as exc:
        raise BridgeError2(f"Director evaluation response failed schema validation: {exc}") from exc


def _extract_claude_result_text(stdout: str) -> str:
    """Claude's --output-format json wraps its answer in a larger object
    (token usage, session id, etc.) — this pulls just the human-readable
    `result` field so the Director's second call sees Claude's actual
    claim, not accounting metadata. Falls back to the raw text if the
    JSON shape isn't what's expected, rather than raising."""
    try:
        parsed = json.loads(stdout)
        if isinstance(parsed, dict) and isinstance(parsed.get("result"), str):
            return parsed["result"]
    except (json.JSONDecodeError, TypeError):
        pass
    return stdout


def request_founder_approval(decision: DirectorDecision, state: dict[str, Any]) -> dict[str, Any]:
    """Exactly the UX specified: one specific action, default No, never a
    blanket grant. In this phase, Level 2 is never executed by this
    bridge regardless of the answer — see the module docstring — so this
    function's real job right now is to prove the prompt exists and
    behaves correctly, and to record what the Founder actually said."""
    village = state.get("village", {})
    print("\nFOUNDER APPROVAL REQUIRED\n")
    print(f"Requested: {decision.task_for_claude!r} (safety_level={decision.safety_level})")
    print(f"Reason: {decision.reason}")
    print(
        f"\nCurrent Village: Day {village.get('day')} / {village.get('period')}\n"
        "Expected effect: may advance simulation, may call paid AI/research services, "
        "will persist canonical Village state.\n"
    )
    try:
        answer = input("Approve? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    approved = answer == "y"
    record = {
        "requested_action": decision.task_for_claude,
        "safety_level": decision.safety_level,
        "approved": approved,
        "answered_at": datetime.now(timezone.utc).isoformat(),
    }
    if approved:
        print(
            "Approval recorded, but this bridge phase does not execute level-2 actions "
            "autonomously — stopping the round without acting."
        )
    return record


#: Named vars excluded from every nested `claude` subprocess's environment
#: regardless of pattern-matching below — VILLAGE_DATA_ROOT/DATABASE_URL so
#: app code resolves a harmless local stub rather than the canonical live
#: path; ALLOW_FRESH_LIVE_INIT for the same reason; ANTHROPIC_API_KEY
#: because this repo's own .env carries one with an exhausted credit
#: balance, and a nested session that inherits it fails immediately with
#: an api_error before attempting any tool call at all — discovered
#: empirically (2026-09-09) when a negative-control probe's "no denied
#: file" result turned out to mean nothing had been attempted, not that
#: anything was blocked. Excluding it lets the nested session fall back to
#: the invoking user's own claude.ai login, the same auth this bridge
#: process itself runs under.
_EXCLUDED_ENV_VAR_NAMES = ("VILLAGE_DATA_ROOT", "DATABASE_URL", "ALLOW_FRESH_LIVE_INIT", "ANTHROPIC_API_KEY")

#: 2026-09-09 context-leak hardening: the exclusion list above is a
#: DENYLIST of specific known-dangerous names — it does nothing for a
#: secret added to .env tomorrow under a name nobody thought to enumerate
#: here. This is a defense-in-depth NAME-PATTERN catch-all on top of it:
#: any environment variable whose name contains one of these substrings
#: (case-insensitive) is excluded regardless of whether it's explicitly
#: named above. Verified empirically not to break the nested `claude`
#: session (PATH/HOME/etc. never match); a coincidental false-positive
#: strip (e.g. SSH_AUTH_SOCK, matching "AUTH") is an acceptable, safe-
#: direction cost — nothing this bridge's Level 0/1 sessions are allowed
#: to do needs ssh anyway.
_SECRET_LIKE_ENV_NAME_MARKERS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL")


def _is_excluded_env_var(name: str) -> bool:
    if name in _EXCLUDED_ENV_VAR_NAMES:
        return True
    upper = name.upper()
    return any(marker in upper for marker in _SECRET_LIKE_ENV_NAME_MARKERS)


def _live_data_deny_patterns() -> str:
    """Defense-in-depth ON TOP of cwd-scoping (Level 0 -> repo root only,
    Level 1 -> an isolated workspace, neither of which contains the live
    data root at all): an explicit, resolved-path denylist for the file
    tools, so even a misconfigured cwd could not grant access to the
    canonical live-data root or DB. These patterns are argv, never model-
    visible text (the model never sees its own CLI invocation), so putting
    the real resolved path here does not violate 'Claude should not receive
    the live path' — that's enforced separately by
    _redact_sensitive_context on the actual prompt text."""
    patterns = []
    for real_value, _ in _sensitive_strings_to_redact():
        if real_value.startswith("/") and len(real_value) > 3:
            patterns.append(
                f"Read({real_value}/**) Edit({real_value}/**) Write({real_value}/**) "
                f"Glob({real_value}/**) Grep({real_value}/**)"
            )
    return " ".join(patterns)


def invoke_claude_code(
    task_prompt: str,
    level: BridgeSafetyLevel,
    *,
    timeout: int | None = None,
    cwd: Path | None = None,
) -> ClaudeInvocationResult:
    """The one place this bridge shells out to a fresh, non-interactive
    Claude Code CLI process — see the HARD SAFETY BOUNDARY comment above
    _LEVEL_TOOLS for the empirically-verified reasoning behind every flag
    here. `-p` (print-and-exit) skips the interactive trust dialog.
    `--permission-mode dontAsk` is genuine default-deny (proven, not
    assumed): anything not in --allowedTools is denied outright, no
    prompt, nothing executes. `--setting-sources ""` is not optional —
    without it this repo's own permissive .claude/settings.local.json
    would silently override everything else here. `timeout=` on
    subprocess.run, not a CLI flag, is what prevents a hang from blocking
    the round forever; `timeout=None` (the default) resolves to the
    level-specific bound in `_CLAUDE_TIMEOUT_BY_LEVEL` rather than one
    global constant — callers (tests, probes) may still pass an explicit
    override. The subprocess environment deliberately omits
    VILLAGE_DATA_ROOT and any live DATABASE_URL (layer 2 of the three-
    layer defense) so even legitimate app code the sandboxed session runs
    can only ever resolve a harmless local stub."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return ClaudeInvocationResult(invoked=False, stderr="claude CLI not found on PATH.")
    if level not in _LEVEL_TOOLS:
        return ClaudeInvocationResult(
            invoked=False, stderr=f"safety level {level} is not invokable by this bridge phase.",
        )
    if timeout is None:
        timeout = _CLAUDE_TIMEOUT_BY_LEVEL[level]

    builtin_toolset, allowed, disallowed = _LEVEL_TOOLS[level]
    live_data_deny = _live_data_deny_patterns()
    if live_data_deny:
        disallowed = f"{disallowed} {live_data_deny}"
    full_prompt = _redact_sensitive_context(f"{_SAFETY_PREAMBLE[level]}\n\nTASK:\n{task_prompt}")
    cmd = [
        claude_bin, "-p", full_prompt,
        "--output-format", "json",
        "--permission-mode", "dontAsk",
        "--setting-sources", "",
    ]
    # `--tools` is the built-in tool REGISTRATION ceiling — a tool absent
    # from it is never exposed to the model, so there is no tool_use to
    # allow or deny. "default" == "every built-in tool" == the historical
    # behavior, expressed by omitting the flag so the argv stays identical
    # to the pre-2026-09-10 implementation for that level (Level 1).
    if builtin_toolset != "default":
        cmd += ["--tools", builtin_toolset]
    cmd += [
        "--allowedTools", allowed,
        "--disallowedTools", disallowed,
    ]
    env = {k: v for k, v in os.environ.items() if not _is_excluded_env_var(k)}
    env["APP_ENV"] = "development"
    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True, timeout=timeout, env=env,
        )
        return ClaudeInvocationResult(
            invoked=True, argv=cmd, exit_code=result.returncode,
            stdout=result.stdout, stderr=result.stderr,
            duration_seconds=time.monotonic() - start,
        )
    except subprocess.TimeoutExpired as exc:
        return ClaudeInvocationResult(
            invoked=True, argv=cmd, timed_out=True,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=f"timed out after {timeout}s",
            duration_seconds=time.monotonic() - start,
        )


def _acquire_lock() -> None:
    BRIDGE_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if BRIDGE_LOCK_PATH.exists():
        try:
            pid = int(BRIDGE_LOCK_PATH.read_text().strip() or 0)
        except ValueError:
            pid = 0
        if pid:
            try:
                os.kill(pid, 0)
                raise BridgeError2(f"another bridge round is already running (pid {pid}).")
            except ProcessLookupError:
                pass  # stale lock from a crashed round; safe to reclaim
            except PermissionError:
                raise BridgeError2(f"another bridge round is already running (pid {pid}).") from None
    BRIDGE_LOCK_PATH.write_text(str(os.getpid()))


def _release_lock() -> None:
    BRIDGE_LOCK_PATH.unlink(missing_ok=True)


def _persist_round(record: BridgeRoundRecord) -> None:
    """Durable audit trail. Deliberately excludes API keys/secrets — the
    record only ever holds git text, Director/Claude text output, and
    counts; nothing here ever touches os.environ."""
    BRIDGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BRIDGE_LOG_PATH.open("a") as f:
        f.write(record.model_dump_json() + "\n")


#: 2026-09-09 workspace-isolation hardening: Level 1 no longer trusts
#: Claude not to leave the repo — it operates inside a freshly created,
#: external, disposable copy instead, per the architecture:
#:   REAL REPO -> controlled temporary working copy -> ISOLATED WORKSPACE
#:   -> Claude edits/tests -> deterministic diff/evidence -> Director eval
#: The copy is a real `git clone --local` (so `git status`/`git add`/
#: `git stash`/`pytest` all work exactly as they would in the real repo,
#: against the workspace's own independent .git/index — never the real
#: repo's) with the CURRENT working tree state (including uncommitted
#: changes) rsynced on top, excluding `.git`/`.venv`/`.director`/
#: `node_modules`/`__pycache__`/`.env*`/DB artifacts (`*.db`/`*.sqlite3` +
#: `-wal`/`-shm` sidecars — see _WORKSPACE_RSYNC_EXCLUDES) — never the real repo's own
#: directories, never a `--worktree`-style checkout nested inside the real
#: repo (a real `claude --worktree` probe during this investigation showed
#: that flag creates its linked worktree INSIDE the project tree and can
#: leave a locked directory needing a forced removal — an operationally
#: fragile mechanism for something this safety-critical). A round never
#: edits the real repo directly at Level 1 any more; the round's evidence
#: is the workspace's own diff, and adopting it into the real repo is a
#: separate, deliberate, NOT-automated step this bridge does not perform.
#:
#: `.env*` is excluded for a CONFIRMED real reason, not caution: the first
#: real run of the workspace-isolation probe (2026-09-09) found that
#: without this exclusion, `.env` (with real API keys and the real
#: VILLAGE_DATA_ROOT value) was copied straight into the "isolated"
#: workspace — and since Read/Glob are correctly scoped to that workspace
#: (`./**`), Claude could legitimately read it; it did, and reported
#: (truncated, but real) key prefixes back in its own output before this
#: fix. Path-scoping alone cannot protect a secret that gets copied INSIDE
#: the scope — it has to never be copied there at all.
#:
#: 2026-09-10 database-artifact hardening: the same rsync step (`rsync -a`
#: does NOT consult .gitignore) was ALSO copying the repo's local,
#: gitignored SQLite dev stubs — `village.db`, `internal_village_live.db`,
#: `data/live/quarantine/.../internal_village.db` — and their `-wal`/`-shm`
#: sidecars straight into the "isolated" workspace, where scoped Read/Glob
#: can legitimately open them (the 2026-09-10 isolation-probe run confirmed
#: Claude locating all three). None is the canonical live DB (that lives
#: outside the repo under VILLAGE_DATA_ROOT and is separately blocked three
#: ways), but a throwaway sandbox has no business carrying stale simulation
#: data either. `*.db` / `*.sqlite3` and every SQLite sidecar spelling are
#: now excluded. An rsync pattern with no `/` matches the basename at every
#: depth, so the nested `quarantine/...` copy is covered by the same entry.
#:
#: The explicit unlink sweep after rsync — not `rsync --delete-excluded` —
#: is deliberate: `--delete-excluded` also matches the workspace's OWN
#: freshly-cloned `.git` directory against the `--exclude=.git` pattern
#: and deletes it too (an exclude pattern matches identically on both the
#: source and destination side), breaking every git command for the rest
#: of the round. Caught by this module's own fixture suite regressing
#: immediately after that flag was added; a targeted removal of only the
#: leak-vector patterns (`.env*` + DB artifacts), never the infra dirs,
#: avoids the footgun entirely. The sweep is recursive and belt-and-
#: suspenders: `git clone` checks out HEAD first, so a *tracked* `.env*`
#: or DB fixture would land before rsync (whose `--exclude` then neither
#: re-copies NOR deletes it); the sweep removes those too, while skipping
#: the workspace's own `.git`.

#: Never copied into a Level-1 workspace. Infra dirs plus the two CONFIRMED
#: data-leak vector classes (`.env*`, DB artifacts). No `/` in a pattern ->
#: rsync matches the basename at every depth.
_WORKSPACE_RSYNC_EXCLUDES: tuple[str, ...] = (
    ".git", ".venv", ".director", "node_modules", "__pycache__",
    ".env*",
    "*.db", "*.db-wal", "*.db-shm",
    "*.sqlite3", "*.sqlite3-wal", "*.sqlite3-shm",
)

#: Post-`git clone` recursive unlink sweep — only the leak-vector patterns
#: (a subset of the excludes above; never the infra dirs, never `.git`).
_WORKSPACE_LEAK_SWEEP_GLOBS: tuple[str, ...] = (
    ".env*",
    "*.db", "*.db-wal", "*.db-shm",
    "*.sqlite3", "*.sqlite3-wal", "*.sqlite3-shm",
)


def _create_level1_workspace() -> Path:
    workspace = Path(tempfile.mkdtemp(prefix="director_bridge_level1_workspace_"))
    subprocess.run(
        ["git", "clone", "--local", "--quiet", str(REPO_ROOT), str(workspace)],
        check=True, timeout=120,
    )
    subprocess.run(
        [
            "rsync", "-a", "--delete",
            *(f"--exclude={pattern}" for pattern in _WORKSPACE_RSYNC_EXCLUDES),
            f"{REPO_ROOT}/", f"{workspace}/",
        ],
        check=True, timeout=120,
    )
    workspace_git_dir = workspace / ".git"
    for pattern in _WORKSPACE_LEAK_SWEEP_GLOBS:
        for leftover in workspace.rglob(pattern):
            if workspace_git_dir == leftover or workspace_git_dir in leftover.parents:
                continue
            if leftover.is_file() or leftover.is_symlink():
                leftover.unlink()
    return workspace


def _cleanup_level1_workspace(workspace: Path) -> None:
    shutil.rmtree(workspace, ignore_errors=True)


#: 2026-09-10 cumulative Level-1 staging workspace. Fixes the architectural
#: gap the first two real acceptance runs both hit: `_create_level1_workspace`
#: cloning fresh from REPO_ROOT on EVERY round meant round N+1 could never see
#: round N's work (it only ever survived as a destroyed workspace's preserved
#: .patch). A `run_watch()` call may now create ONE persistent workspace,
#: lazily, the first time a round actually needs it (Level1StagingSession
#: below), and reuse it for every subsequent Level-1 round in that SAME watch
#: run. Level-0 rounds never touch it (they never receive `cwd=workspace` at
#: all — see invoke_claude_code's Level-0 branch, unchanged). Nothing here
#: EVER runs against REPO_ROOT's own git history; every git command below is
#: explicitly `-C <staging workspace>`, the same throwaway `_create_level1_
#: workspace()` clone as always, just kept alive across rounds instead of
#: destroyed after one.
#:
#: Round-transaction model: the workspace's own HEAD is always, by
#: construction, "the last known-good state" between rounds — retaining a
#: round advances it (a workspace-local commit); rejecting a round resets it
#: back (a workspace-local `git reset --hard` + `clean`). No separate
#: checkpoint bookkeeping is needed beyond reading HEAD immediately before a
#: round runs (BridgeRoundRecord.level1_checkpoint_before) and deciding
#: retain-vs-rollback immediately after (_level1_round_is_retainable), both
#: inside run_once() — see its SANDBOX branch and the retain/rollback block
#: right before its final `return record`. run_watch() itself only creates
#: the session, threads it through repeated run_once() calls unchanged, and
#: finalizes it (cumulative patch + cleanup) once, in a `finally` wrapping its
#: whole round loop, regardless of which of its several stop paths fires.


class Level1StagingSession:
    """Mutable, per-watch-run holder for at most one persistent Level-1
    workspace. Deliberately NOT a pydantic model — plain bookkeeping that
    run_once() mutates in place (lazy-create on first use) and run_watch()
    reads back; never serialized directly (see _register_disposable_workspace
    for the durable, crash-recoverable record instead). `workspace is None`
    is the "not created yet" state a fresh watch run starts in and the state
    a run with only Level-0 rounds (or none at all) stays in forever."""

    def __init__(
        self, session_id: str, *, seed_patch_path: Path | None = None, seed_patch_sha256: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.workspace: Path | None = None
        self.baseline_commit: str | None = None
        #: 2026-09-10 safe cumulative session seeding — set by the caller
        #: (run_watch) BEFORE the first run_once() call; consumed exactly
        #: once, at workspace-creation time, by _seed_level1_staging_
        #: workspace via run_once's lazy-create branch. seed_provenance is
        #: the full result dict (ok, sha256, files, test_ok, error) —
        #: recorded on WatchRunResult regardless of outcome, so a rejected
        #: seed is still durably auditable.
        self.seed_patch_path = seed_patch_path
        self.seed_patch_sha256 = seed_patch_sha256
        self.seeded = False
        self.seed_provenance: dict[str, Any] | None = None


DISPOSABLE_REGISTRY_PATH = DIRECTOR_DIR / "audit" / "disposable_registry.json"


def _read_disposable_registry() -> dict[str, Any]:
    try:
        return json.loads(DISPOSABLE_REGISTRY_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _write_disposable_registry(registry: dict[str, Any]) -> None:
    try:
        DISPOSABLE_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        DISPOSABLE_REGISTRY_PATH.write_text(json.dumps(registry, indent=2, default=str))
    except OSError:
        pass


def _register_disposable_workspace(session_id: str, workspace: Path, baseline_commit: str) -> None:
    """Written the moment a persistent staging workspace is created — BEFORE
    any round runs against it — so a hard crash (not an ordinary exception;
    those still reach run_watch's `finally` and unregister normally) leaves
    enough here for a human to find and reconcile the orphaned temp
    directory: its exact path, the commit its cumulative diff should be
    measured from, and which watch run it belonged to."""
    registry = _read_disposable_registry()
    registry[session_id] = {
        "workspace": str(workspace),
        "baseline_commit": baseline_commit,
        "watch_run_id": session_id,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_disposable_registry(registry)


def _unregister_disposable_workspace(session_id: str) -> None:
    registry = _read_disposable_registry()
    registry.pop(session_id, None)
    _write_disposable_registry(registry)


def _level1_current_head(workspace: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=15,
    ).stdout.strip()


def _level1_init_staging_baseline(workspace: Path) -> str:
    """Commits the freshly created/rsynced workspace's own starting content
    (whatever pre-existing REPO_ROOT dirty-file noise the rsync carried in,
    same as every ephemeral Level-1 workspace already starts with) as ONE
    workspace-local commit — entirely inside the throwaway clone, never
    REPO_ROOT's real git history. This becomes the staging session's
    baseline: the end-of-run cumulative diff is measured from here to
    whatever HEAD retained rounds advance it to, so it only ever shows what
    Level-1 rounds themselves changed, never the pre-existing noise."""
    subprocess.run(["git", "-C", str(workspace), "add", "-A"], check=False, timeout=60)
    subprocess.run(
        ["git", "-C", str(workspace), "commit", "-q", "--allow-empty",
         "-m", "director-bridge: staging session baseline"],
        check=False, timeout=30,
    )
    return _level1_current_head(workspace)


def _level1_commit_round(workspace: Path, round_id: str, changed_files: list[str]) -> str:
    """Commits EXACTLY this round's own changed files — never `git add -A`,
    so director_bridge_test_runner.py's .director/level1_test_result.json
    marker (already excluded from changed_files by _workspace_dirty_files'
    own filter) or anything else never enters the staging workspace's commit
    history, and therefore never the cumulative patch either. Porcelain
    renames arrive as 'old -> new'; both concrete paths are staged, same
    convention as _preserve_workspace_diff."""
    pathspec: list[str] = []
    for f in changed_files:
        if " -> " in f:
            pathspec.extend(part.strip() for part in f.split(" -> "))
        else:
            pathspec.append(f)
    subprocess.run(["git", "-C", str(workspace), "add", "--", *pathspec], check=False, timeout=30)
    subprocess.run(
        ["git", "-C", str(workspace), "commit", "-q", "-m", f"director-bridge round {round_id}: retained"],
        check=False, timeout=30,
    )
    return _level1_current_head(workspace)


def _level1_rollback(workspace: Path, checkpoint_commit: str) -> None:
    """Restores the staging workspace to EXACTLY its pre-round checkpoint —
    tracked changes via `git reset --hard`, untracked new files/dirs via
    `git clean` — discarding a rejected round's edits entirely so the NEXT
    round (if any) starts from the last retained state, never the rejected
    one. Only ever invoked by run_once() with a Level-1 staging workspace
    path; REPO_ROOT is never passed here."""
    subprocess.run(["git", "-C", str(workspace), "reset", "-q", "--hard", checkpoint_commit], check=False, timeout=30)
    subprocess.run(["git", "-C", str(workspace), "clean", "-q", "-fd"], check=False, timeout=30)


def _level1_round_is_retainable(record: "BridgeRoundRecord") -> tuple[bool, str]:
    """A narrower sibling of _watch_continuation_decision (defined further
    below): whether THIS round's own changes were safe enough to keep in the
    staging workspace, independent of whether the watch loop goes on to
    another round. A round can be retainable even though the loop is about
    to stop (e.g. an accepted round with nothing further to do) —
    retainability is about this round's own outcome, not about
    continuation. Deliberately does NOT check recommended_next_task
    emptiness or task repetition; those are run_watch's own loop-control
    concerns and have nothing to do with whether this round's code was
    safe. Every other condition mirrors _watch_continuation_decision's
    'accepted or safely-continuable needs_revision' definition exactly, on
    purpose — this bridge only ever has ONE definition of 'safe enough',
    reused for two different decisions (continue vs. retain)."""
    if record.final_state != "completed":
        return False, f"final_state is {record.final_state!r}, not 'completed'"
    if record.errors:
        return False, f"round recorded {len(record.errors)} error/stop condition(s): {record.errors}"
    if record.live_db_involvement_suspected:
        return False, "live DB involvement was suspected during this round"
    evaluation = record.director_evaluation
    if evaluation is None:
        return False, "no DirectorEvaluation was recorded for this round"
    outcome = evaluation.get("outcome")
    if outcome not in ("accepted", "needs_revision"):
        return False, f"DirectorEvaluation.outcome is {outcome!r}, not 'accepted' or 'needs_revision'"
    if evaluation.get("overridden_by_deterministic_check"):
        return False, "DirectorEvaluation was overridden by a deterministic safety check"
    if evaluation.get("requires_founder_approval"):
        return False, "DirectorEvaluation.requires_founder_approval is true"
    recommended_level = evaluation.get("recommended_safety_level")
    if recommended_level is None or recommended_level > 1:
        return False, f"DirectorEvaluation.recommended_safety_level is {recommended_level!r}, not Level 0 or 1"
    return (
        True,
        "final_state=='completed', clean deterministic pass, DirectorEvaluation exists with outcome "
        "'accepted' or 'needs_revision', not overridden by a deterministic safety check, no founder "
        "approval required, recommended_safety_level is Level 0 or 1, and no error/stop condition recorded",
    )


def _level1_cumulative_diff(workspace: Path, baseline_commit: str) -> str:
    """The full unified diff from the staging session's baseline commit to
    its current (final retained) HEAD. Because ONLY _level1_commit_round
    ever advances HEAD (a rejected round's commit, if any, is always reset
    away by _level1_rollback before the next round can build on it), this
    is exactly and only the accumulated set of retained rounds' changes —
    no extra filtering needed."""
    return subprocess.run(
        ["git", "-C", str(workspace), "diff", baseline_commit, "HEAD"],
        capture_output=True, text=True, timeout=30,
    ).stdout


#: 2026-09-10 safe cumulative session seeding — `--seed-patch` lets a NEW
#: watch run continue from a PRIOR run's durable cumulative patch (e.g.
#: .director/audit/workspace_diffs/<old_watch_run_id>_cumulative.patch)
#: without ever touching REPO_ROOT: the seed is verified, then applied and
#: committed ONLY inside the brand-new staging workspace, on top of (never
#: instead of) that workspace's own pristine baseline commit — so the final
#: cumulative diff (baseline_commit -> final HEAD) naturally includes the
#: seed's own changes plus everything this session itself retains. Mirrors
#: the manual Gate-1 promotion preflight exactly, just automated and
#: required before every seed, not only a human-run one-off.
def _validate_seed_patch(patch_path: Path, expected_sha256: str | None) -> tuple[bool, str, list[str]]:
    """Read-only inspection — never applies anything. Returns (ok,
    error_or_empty, touched_files). Rejects: a sha256 mismatch (when an
    expected hash is supplied), no touched files at all, any absolute
    path, any path-traversal component, .env/.director/DB-or-sqlite-
    artifact/secret-shaped paths, binary diffs, and symlink mode changes —
    the same categories the Gate-1 promotion checklist covered by hand."""
    try:
        text = patch_path.read_text()
    except OSError as exc:
        return False, f"cannot read seed patch: {exc}", []
    if expected_sha256:
        actual = hashlib.sha256(patch_path.read_bytes()).hexdigest()
        if actual != expected_sha256:
            return False, f"sha256 mismatch: expected {expected_sha256}, got {actual}", []
    touched: list[str] = []
    for line in text.splitlines():
        if line.startswith("diff --git a/"):
            a_path = line[len("diff --git a/"):].split(" b/", 1)[0]
            touched.append(a_path)
    if not touched:
        return False, "seed patch touches no files — nothing to seed", []
    for path in touched:
        if path.startswith("/"):
            return False, f"seed patch touches an absolute path: {path!r}", touched
        if ".." in Path(path).parts:
            return False, f"seed patch touches a path-traversal component: {path!r}", touched
        lower = path.lower()
        if (
            lower.endswith(".env") or lower.split("/")[-1].startswith(".env")
            or lower.endswith((".db", ".db-wal", ".db-shm", ".sqlite3", ".sqlite3-wal", ".sqlite3-shm"))
            or path == ".director" or path.startswith(".director/") or "/.director/" in path
            or any(marker in lower for marker in ("secret", "credential", "api_key", "apikey", "password"))
        ):
            return False, f"seed patch touches a disallowed path: {path!r}", touched
    if "GIT binary patch" in text or "\nBinary files " in text or text.startswith("Binary files "):
        return False, "seed patch contains a binary diff — rejected", touched
    if "\nnew file mode 120000" in text or "\nnew mode 120000" in text or "\nold mode 120000" in text:
        return False, "seed patch creates or modifies a symlink (mode 120000) — rejected", touched
    return True, "", touched


def _seed_level1_staging_workspace(
    workspace: Path, patch_path: Path, expected_sha256: str | None,
) -> dict[str, Any]:
    """Applies a verified prior cumulative patch ONLY inside this freshly
    created Level-1 staging workspace — never REPO_ROOT — as one
    workspace-local commit on top of the workspace's own baseline, then
    runs every approved test target directly (mechanically, not via
    Claude) to confirm the seeded state is actually healthy before any
    round builds on it. Returns a provenance dict; `ok=False` at any stage
    means the caller (run_once's SANDBOX branch) aborts the round rather
    than let anything build on an unverified or unhealthy seed."""
    ok, error, touched = _validate_seed_patch(patch_path, expected_sha256)
    provenance: dict[str, Any] = {
        "ok": False, "patch_path": str(patch_path), "sha256": None, "files": touched,
        "error": error, "applied": False, "test_ok": None,
    }
    if not ok:
        return provenance
    provenance["sha256"] = hashlib.sha256(patch_path.read_bytes()).hexdigest()

    check = subprocess.run(
        ["git", "-C", str(workspace), "apply", "--check", str(patch_path)],
        capture_output=True, text=True, timeout=30,
    )
    if check.returncode != 0:
        provenance["error"] = f"seed patch does not apply cleanly: {check.stderr.strip()[:500]}"
        return provenance

    apply_result = subprocess.run(
        ["git", "-C", str(workspace), "apply", str(patch_path)],
        capture_output=True, text=True, timeout=30,
    )
    if apply_result.returncode != 0:
        provenance["error"] = f"seed patch apply failed: {apply_result.stderr.strip()[:500]}"
        return provenance
    provenance["applied"] = True

    subprocess.run(["git", "-C", str(workspace), "add", "--", *touched], check=False, timeout=30)
    subprocess.run(
        ["git", "-C", str(workspace), "commit", "-q", "-m",
         f"director-bridge: seeded from {patch_path.name} (sha256={provenance['sha256'][:12]}...)"],
        check=False, timeout=30,
    )

    test_ok = True
    test_details: list[dict[str, Any]] = []
    for target in _test_runner.ALLOWED_TEST_TARGETS:
        cmd = [str(_test_runner.REAL_HOST_PYTHON), "scripts/director_bridge_test_runner.py", "--target", target]
        try:
            proc = subprocess.run(cmd, cwd=str(workspace), capture_output=True, text=True, timeout=300)
            result = json.loads(proc.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            result = {"ok": False, "exit_code": None, "error": str(exc)}
        test_details.append({"target": target, "result": result})
        if not (result.get("ok") and result.get("exit_code") == 0):
            test_ok = False
    provenance["test_ok"] = test_ok
    provenance["test_details"] = test_details
    if not test_ok:
        provenance["error"] = "seeded workspace failed its post-seed test run"
        return provenance

    provenance["ok"] = True
    return provenance


def _finalize_level1_session(level1_session: Level1StagingSession, watch_run_id: str) -> tuple[str | None, str | None, int | None]:
    """run_watch()'s end-of-run teardown for its staging session — called
    from a `finally` wrapping the whole round loop, so it runs exactly once
    regardless of which of run_watch's several stop paths fired. Writes the
    cumulative patch durably BEFORE destroying the workspace (never after —
    the diff needs the workspace to exist), unregisters the session from the
    disposable registry (normal-completion path; a hard crash before this
    point leaves the registry entry for manual recovery instead), then
    deletes the workspace. No-op if no Level-1 round ever actually created
    one this run. Returns (repo-relative patch path, sha256, size in bytes) —
    all None if there was nothing to retain (no session, or a session whose
    HEAD never moved past its own baseline)."""
    if level1_session.workspace is None:
        return None, None, None
    patch_path: str | None = None
    patch_sha: str | None = None
    patch_size: int | None = None
    try:
        diff_text = _level1_cumulative_diff(level1_session.workspace, level1_session.baseline_commit)
        if diff_text.strip():
            WORKSPACE_DIFF_DIR.mkdir(parents=True, exist_ok=True)
            out_path = WORKSPACE_DIFF_DIR / f"{watch_run_id}_cumulative.patch"
            out_path.write_text(diff_text)
            patch_size = out_path.stat().st_size
            patch_sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
            try:
                patch_path = str(out_path.relative_to(REPO_ROOT))
            except ValueError:
                patch_path = str(out_path)
    except Exception:  # noqa: BLE001 - an audit-artifact failure must never block workspace teardown
        pass
    finally:
        _unregister_disposable_workspace(level1_session.session_id)
        _cleanup_level1_workspace(level1_session.workspace)
    return patch_path, patch_sha, patch_size


def _workspace_dirty_files(workspace: Path) -> frozenset[str]:
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True, timeout=15,
    ).stdout
    return frozenset(
        line[3:] for line in status.splitlines() if line.strip() and not line[3:].startswith(".director/")
    )


def _workspace_git_evidence(
    workspace: Path, baseline_dirty_files: frozenset[str] = frozenset(),
) -> tuple[list[str], str]:
    """changed_files/diff_stat computed as a DELTA against
    `baseline_dirty_files` — the workspace's own dirty-file set captured
    immediately after `_create_level1_workspace()` returns, BEFORE Claude
    ever runs. This is not optional: `_create_level1_workspace()` rsyncs
    the real repo's CURRENT uncommitted working-tree state on top of a
    fresh clone, so a brand-new workspace already starts dirty whenever
    the real repo has any uncommitted work (which, during active
    development, is close to always) — a single post-round snapshot would
    misreport every one of those pre-existing files as "changed by this
    round," exactly as `run_once`'s own Level-0 path already learned to
    avoid via its own pre/post delta. Found by the watch-loop's repeated-
    no-change-result regression test reporting non-empty changed_files
    for a Level-1 round whose fixture Claude touched nothing at all."""
    current_dirty = _workspace_dirty_files(workspace)
    changed_files = sorted(current_dirty - baseline_dirty_files)
    diff_stat = subprocess.run(
        ["git", "diff", "--stat"], cwd=workspace, capture_output=True, text=True, timeout=15,
    ).stdout.strip()[:2000]
    return changed_files[:50], diff_stat


def _preserve_workspace_diff(
    workspace: Path, round_id: str, baseline_dirty_files: frozenset[str],
) -> tuple[str | None, str | None]:
    """Write the FULL unified diff of exactly what Claude changed this round
    (the same delta `_workspace_git_evidence` reports as `changed_files` —
    files dirty now that were NOT already dirty from the rsync of the real
    repo's uncommitted state) to
    `.director/audit/workspace_diffs/<round_id>.patch`, BEFORE
    `_cleanup_level1_workspace` destroys the workspace. Also returns a clean
    `--stat` scoped to that same delta (the bare `git diff --stat` in
    `_workspace_git_evidence` still carries the rsync'd baseline noise —
    left untouched so its existing tests hold; callers prefer this one for
    a Level-1 round).

    Read-only audit artifact: NOTHING in this bridge ever `git apply`s it —
    promoting an accepted sandbox implementation into REPO_ROOT is a
    separate, deliberate, human-gated step. Returns
    `(repo_relative_patch_path, scoped_stat)`, or `(None, None)` if Claude
    changed nothing beyond the baseline. Best-effort: any failure returns
    `(None, None)` and never breaks the round (the workspace is about to be
    deleted regardless)."""
    try:
        ws = str(workspace)
        claude_files = sorted(_workspace_dirty_files(workspace) - baseline_dirty_files)
        if not claude_files:
            return None, None
        # Porcelain renames arrive as "old -> new"; split them into both
        # concrete paths so the pathspec below still scopes the diff to
        # exactly Claude's files and never to the rsync'd baseline noise.
        pathspec: list[str] = []
        for f in claude_files:
            if " -> " in f:
                pathspec.extend(part.strip() for part in f.split(" -> "))
            else:
                pathspec.append(f)
        subprocess.run(["git", "-C", ws, "add", "-A"], check=False, timeout=30)
        diff = subprocess.run(
            ["git", "-C", ws, "diff", "--cached", "HEAD", "--", *pathspec],
            capture_output=True, text=True, timeout=30,
        ).stdout
        stat = subprocess.run(
            ["git", "-C", ws, "diff", "--cached", "HEAD", "--stat", "--", *pathspec],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()[:2000]
        # Leave the workspace exactly as Claude left it (it is about to be
        # rmtree'd, but keep this side-effect-free in case that ever changes).
        subprocess.run(["git", "-C", ws, "reset", "-q"], check=False, timeout=30)
        if not diff.strip():
            return None, None
        WORKSPACE_DIFF_DIR.mkdir(parents=True, exist_ok=True)
        out_path = WORKSPACE_DIFF_DIR / f"{round_id}.patch"
        out_path.write_text(diff)
        try:
            rel = str(out_path.relative_to(REPO_ROOT))
        except ValueError:
            rel = str(out_path)
        return rel, (stat or None)
    except Exception:  # noqa: BLE001 - never let audit-artifact capture break a round
        return None, None


def _read_level1_test_result(workspace: Path) -> str | None:
    """Mechanical, independent capture of director_bridge_test_runner.py's
    own result for this round — read directly from
    `<workspace>/.director/level1_test_result.json`, NEVER parsed or
    inferred from Claude's own prose. `.director/` inside a Level-1
    workspace is already excluded from every changed-files/diff
    computation by `_workspace_dirty_files`'s own filter, so this file
    never pollutes changed_files, diff_stat, or the durable patch. Returns
    None if the runner never ran this round (Claude didn't invoke it, or
    invoked something denied before the script could write anything) —
    that absence is itself meaningful evidence, not a failure of this
    function, so it is never retried or treated as an error."""
    marker = workspace / ".director" / "level1_test_result.json"
    try:
        return marker.read_text()[:8000]
    except OSError:
        return None


def _clear_stale_level1_test_result(workspace: Path) -> None:
    """2026-09-10 cumulative staging workspace correction: a persistent
    workspace can carry a PRIOR round's marker into a round that never
    re-invokes the test runner at all — without this, _read_level1_test_
    result would misreport that stale result as this round's own. No-op
    (and harmless) for a fresh ephemeral workspace, which never has one."""
    (workspace / ".director" / "level1_test_result.json").unlink(missing_ok=True)


def run_once(
    objective: str,
    *,
    director_client: DirectorClient | None = None,
    max_safety_level: int | None = None,
    level1_session: Level1StagingSession | None = None,
) -> BridgeRoundRecord:
    """One full round: lock -> collect state -> Director -> safety gate
    -> (maybe) Claude -> evidence -> persist -> unlock -> return. Never
    loops, never recurses, never calls itself — the `once` CLI mode is
    exactly this function called exactly once.

    `director_client` defaults to `OpenAIDirectorClient()` — today's interim
    automation layer — but this function never imports or names OpenAI
    directly; it only calls `director_client.decide()`/`.evaluate()`. A
    future exact-ChatGPT-thread connector plugs in here by constructing its
    own `DirectorClient` and passing it, with zero changes to this
    function's control flow, safety gating, or deterministic evidence
    layer.

    `max_safety_level`, when given, is a caller-imposed ceiling BELOW
    Level 2 (which is always refused regardless of this parameter) — e.g.
    `run_watch(..., max_safety_level=0)` for a Level-0-only supervised
    session. A decision above the ceiling is treated as an unexpected
    safety-level escalation: refused before Claude is ever invoked, exactly
    like the existing Level-2 refusal below.

    `level1_session`, when given, makes a Level-1 round use (lazily
    creating on first use, per-round retain/rollback via workspace-local
    git commit/reset) that session's ONE persistent staging workspace
    instead of always creating and destroying its own — see the
    Level1StagingSession module comment above _cleanup_level1_workspace.
    `None` (the default) preserves this function's exact prior behavior:
    every Level-1 round gets its own fresh, disposable workspace, created
    and destroyed within this one call — what the standalone `once` CLI
    mode and every existing caller that doesn't pass this still get."""
    director_client = director_client or OpenAIDirectorClient()
    round_id = uuid.uuid4().hex[:16]
    record = BridgeRoundRecord(
        round_id=round_id, timestamp=datetime.now(timezone.utc).isoformat(), objective=objective,
        director_input={}, live_db_snapshot_before=_live_db_fingerprint(),
    )
    _acquire_lock()
    try:
        state = collect_bridge_state(objective)
        record.director_input = state

        try:
            decision = director_client.decide(state)
        except BridgeError2 as exc:
            record.director_error = str(exc)
            record.errors.append(str(exc))
            record.final_state = "stopped_invalid_director_response"
            return record
        record.director_decision = decision.model_dump()

        if decision.decision == "stop" or not decision.task_for_claude.strip():
            record.final_state = "stopped_by_director"
            return record

        try:
            level = BridgeSafetyLevel(decision.safety_level)
        except ValueError:
            record.errors.append(f"unrecognized safety_level {decision.safety_level!r}")
            record.final_state = "stopped_unsafe_level"
            return record

        if level is BridgeSafetyLevel.CONSEQUENTIAL or decision.requires_founder_approval:
            record.safety_level = int(level)
            record.founder_approval = request_founder_approval(decision, state)
            record.final_state = "stopped_pending_level2_not_executed"
            return record

        if max_safety_level is not None and int(level) > max_safety_level:
            record.safety_level = int(level)
            record.errors.append(
                f"decision safety_level {int(level)} exceeds this run's max_safety_level "
                f"{max_safety_level} — treated as an unexpected safety-level escalation and "
                "refused before Claude was invoked."
            )
            record.final_state = "stopped_safety_level_escalation"
            return record

        record.safety_level = int(level)
        record.claude_task = decision.task_for_claude

        if level is BridgeSafetyLevel.SANDBOX:
            # Level 1 never touches the real repo directly any more — see
            # the _create_level1_workspace module comment. The round's
            # evidence is the isolated workspace's own diff; nothing here
            # applies it back to REPO_ROOT.
            #
            # 2026-09-10 cumulative staging: when level1_session is given,
            # this round uses (lazily creating on first use) ITS ONE
            # persistent workspace instead of a fresh disposable one, and
            # this function does NOT destroy it at the end — ownership
            # (including eventual cleanup) belongs to whoever passed
            # level1_session in (run_watch), for exactly as long as that
            # caller's whole session lasts, not just this one round.
            owns_workspace = level1_session is None
            if level1_session is not None:
                if level1_session.workspace is None:
                    level1_session.workspace = _create_level1_workspace()
                    level1_session.baseline_commit = _level1_init_staging_baseline(level1_session.workspace)
                    _register_disposable_workspace(
                        level1_session.session_id, level1_session.workspace, level1_session.baseline_commit,
                    )
                    # 2026-09-10 safe cumulative session seeding — applied
                    # and tested exactly once, right here, ON TOP OF the
                    # pristine baseline commit above (never instead of it),
                    # so the eventual cumulative diff (baseline -> final
                    # HEAD) naturally includes the seed. A rejected/unhealthy
                    # seed aborts THIS round outright — never partially
                    # builds on an unverified starting point.
                    if level1_session.seed_patch_path is not None:
                        level1_session.seed_provenance = _seed_level1_staging_workspace(
                            level1_session.workspace, level1_session.seed_patch_path, level1_session.seed_patch_sha256,
                        )
                        level1_session.seeded = True
                        if not level1_session.seed_provenance["ok"]:
                            record.errors.append(
                                f"seed patch rejected or failed verification: {level1_session.seed_provenance['error']}"
                            )
                            record.final_state = "stopped_seed_rejected"
                            return record
                workspace = level1_session.workspace
                record.level1_checkpoint_before = _level1_current_head(workspace)
            else:
                workspace = _create_level1_workspace()
            try:
                # A persistent workspace can carry a prior round's test-
                # runner marker forward; clear it so this round's
                # test_results reflects only what THIS round actually ran
                # (see _clear_stale_level1_test_result — harmless no-op on
                # a fresh ephemeral workspace, which never has one).
                _clear_stale_level1_test_result(workspace)
                baseline_dirty_files = _workspace_dirty_files(workspace)
                claude_result = invoke_claude_code(decision.task_for_claude, level, cwd=workspace)
                record.claude_result = claude_result
                record.changed_files, record.diff_stat = _workspace_git_evidence(workspace, baseline_dirty_files)
                # Mechanical, Claude-independent capture of whatever the
                # bridge-owned test runner itself recorded this round (see
                # _read_level1_test_result) — BEFORE the workspace is
                # destroyed, same as the diff preservation immediately below.
                record.test_results = _read_level1_test_result(workspace)
                # Preserve the full sandbox patch BEFORE the workspace is
                # destroyed — read-only audit artifact, never auto-applied
                # (see _preserve_workspace_diff). Prefer its baseline-noise-
                # free --stat for the record when it produced one.
                record.workspace_diff_path, _scoped_stat = _preserve_workspace_diff(
                    workspace, round_id, baseline_dirty_files,
                )
                if _scoped_stat:
                    record.diff_stat = _scoped_stat
            finally:
                if owns_workspace:
                    _cleanup_level1_workspace(workspace)
        else:
            claude_result = invoke_claude_code(decision.task_for_claude, level)
            record.claude_result = claude_result

            # Delta against the pre-round snapshot (state["changed_files"]),
            # not the raw post-round status — otherwise this round's
            # evidence would be swamped by whatever was already dirty
            # before it ever ran (as the acceptance test's first real pass
            # discovered: 700+ pre-existing .director/ diagnostic
            # artifacts, none of which this round touched). Same
            # .director/ exclusion as collect_bridge_state. Level 0 has no
            # Edit/Write/Bash at all, so this is expected to always be
            # empty — kept as a defense-in-depth check, not a no-op.
            post_lines = [
                line for line in _run(["git", "status", "--porcelain"]).splitlines()
                if line.strip() and not line[3:].startswith(".director/")
            ]
            post_files = {line[3:] for line in post_lines}
            pre_files = set(state.get("changed_files", []))
            record.changed_files = sorted(post_files - pre_files)[:50]
            record.diff_stat = _run(["git", "diff", "--stat", "--", ".", ":!.director"])[:2000]

        try:
            record.claude_session_id = json.loads(claude_result.stdout).get("session_id")
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

        record.live_db_snapshot_after = _live_db_fingerprint()
        before, after = record.live_db_snapshot_before or {}, record.live_db_snapshot_after or {}
        changed_fields = _fingerprint_changed(before, after)
        if changed_fields:
            record.live_db_involvement_suspected = True
            record.errors.append(
                f"canonical live DB fingerprint changed during this round ({', '.join(changed_fields)}) "
                "— treat as a safety-policy violation and investigate before trusting this round's result."
            )

        deterministic_safety_failure = bool(
            not claude_result.invoked or claude_result.timed_out
            or claude_result.exit_code != 0 or record.live_db_involvement_suspected
        )
        if not claude_result.invoked:
            record.final_state = "stopped_claude_not_invoked"
        elif claude_result.timed_out:
            record.final_state = "stopped_claude_timeout"
        elif claude_result.exit_code != 0:
            record.final_state = "stopped_claude_nonzero_exit"
        elif record.live_db_involvement_suspected:
            record.final_state = "stopped_safety_violation"
        else:
            record.final_state = "completed"

        # Second Director call: evaluate what Claude actually did, using
        # only mechanically-verified facts (never raw stdout) as the
        # authoritative evidence. Runs even on a deterministic failure —
        # a failure has meaning worth evaluating too — but the model's
        # own outcome can never override what was already mechanically
        # established; see the hard override immediately below.
        if claude_result.invoked:
            deterministic_evidence = {
                "changed_files": record.changed_files,
                "diff_stat": record.diff_stat,
                "live_db_fingerprint_changed_fields": changed_fields,
                "live_db_involvement_suspected": record.live_db_involvement_suspected,
                "claude_exit_code": claude_result.exit_code,
                "claude_timed_out": claude_result.timed_out,
                "deterministic_safety_failure": deterministic_safety_failure,
                # Level-1 only; None means no approved test-runner target
                # actually ran this round — see _read_level1_test_result.
                "test_results": record.test_results,
            }
            try:
                evaluation = director_client.evaluate(
                    decision=decision, claude_result=claude_result, deterministic=deterministic_evidence,
                )
                if deterministic_safety_failure and evaluation.outcome != "blocked":
                    evaluation.outcome = "blocked"
                    evaluation.overridden_by_deterministic_check = True
                    evaluation.stop_reason = (
                        "Overridden: a deterministic safety check failed "
                        f"({', '.join(deterministic_evidence['live_db_fingerprint_changed_fields']) or 'claude process failure'}). "
                        "The Director's own textual outcome may never override a mechanically-verified failure."
                    )
                record.director_evaluation = evaluation.model_dump()
            except BridgeError2 as exc:
                record.evaluation_error = str(exc)
                record.errors.append(f"Director evaluation call failed: {exc}")

        # 2026-09-10 cumulative staging: retain-or-rollback happens HERE,
        # before persistence, so the durable audit record already reflects
        # the decision — never mutated by a caller after the fact. Only
        # applies to a Level-1 round that actually used a persistent
        # session (level1_checkpoint_before is None for every Level-0
        # round and every Level-1 round using its own disposable
        # workspace, by construction — see the SANDBOX branch above).
        if level1_session is not None and record.level1_checkpoint_before is not None:
            retainable, _reason = _level1_round_is_retainable(record)
            if retainable:
                if record.changed_files:
                    record.level1_commit_after = _level1_commit_round(
                        level1_session.workspace, round_id, record.changed_files,
                    )
                else:
                    record.level1_commit_after = record.level1_checkpoint_before
                record.level1_retained = True
            else:
                _level1_rollback(level1_session.workspace, record.level1_checkpoint_before)
                record.level1_commit_after = record.level1_checkpoint_before
                record.level1_retained = False
        return record
    finally:
        _persist_round(record)
        _release_lock()


def _watch_continuation_decision(record: BridgeRoundRecord, *, max_safety_level: int = 1) -> tuple[bool, str]:
    """The ONLY function that decides whether `run_watch` may proceed to
    another automatic round. Every condition below must hold; a single
    failure stops watch mode and returns control to the Founder. Purely a
    boolean gate over an already-completed round record — never triggers,
    schedules, or executes anything itself. `recommended_next_task` IS now
    read by `run_watch` (2026-09 activation) to become the next round's
    objective, but ONLY after every condition here — including this
    function's own non-empty check — has already passed; this function
    still never acts on it directly.

    outcome=='accepted' is the ordinary continuation case. As of 2026-09-09,
    outcome=='needs_revision' can ALSO continue automatically — a Director
    revision request is not inherently unsafe, and stopping the whole watch
    loop for every routine revision defeats the purpose of supervised
    autonomy. A needs_revision round continues ONLY when it passes every
    other gate below exactly like an accepted one would: clean deterministic
    pass, no error/stop condition, not overridden by a deterministic safety
    check, requested level is Level 0 or Level 1 AND within the caller's
    configured `max_safety_level`, no founder approval required, and a
    non-empty `recommended_next_task`. outcome=='blocked' never continues,
    regardless of these other conditions."""
    if record.final_state != "completed":
        return False, f"final_state is {record.final_state!r}, not 'completed'"
    if record.errors:
        return False, f"round recorded {len(record.errors)} error/stop condition(s): {record.errors}"
    if record.live_db_involvement_suspected:
        return False, "live DB involvement was suspected during this round"
    cr = record.claude_result
    if cr is None or not cr.invoked or cr.timed_out or cr.exit_code != 0:
        return False, "Claude's result does not represent a clean deterministic pass"
    evaluation = record.director_evaluation
    if evaluation is None:
        return False, "no DirectorEvaluation was recorded for this round"
    outcome = evaluation.get("outcome")
    if outcome not in ("accepted", "needs_revision"):
        return False, f"DirectorEvaluation.outcome is {outcome!r}, not 'accepted' or a safely-continuable 'needs_revision'"
    if evaluation.get("overridden_by_deterministic_check"):
        return False, "DirectorEvaluation was overridden by a deterministic safety check"
    if evaluation.get("requires_founder_approval"):
        return False, "DirectorEvaluation.requires_founder_approval is true"
    recommended_level = evaluation.get("recommended_safety_level")
    if recommended_level is None or recommended_level > 1:
        return False, f"DirectorEvaluation.recommended_safety_level is {recommended_level!r}, not Level 0 or Level 1"
    if recommended_level > max_safety_level:
        return False, (
            f"DirectorEvaluation.recommended_safety_level ({recommended_level}) exceeds this watch "
            f"run's configured max_safety_level ({max_safety_level})"
        )
    if not (evaluation.get("recommended_next_task") or "").strip():
        return False, "DirectorEvaluation.recommended_next_task is empty — nothing further to do"
    if outcome == "needs_revision":
        return (
            True,
            f"outcome=='needs_revision' but is itself safely continuable: final_state=='completed', "
            "deterministic verification passed, not overridden by a deterministic safety check, "
            f"recommended_safety_level ({recommended_level}) is Level 0 or Level 1 and within "
            f"max_safety_level={max_safety_level}, requires_founder_approval is false, and "
            "recommended_next_task is non-empty",
        )
    return (
        True,
        "final_state=='completed', deterministic verification passed, DirectorEvaluation "
        f"exists with outcome=='accepted', recommended_safety_level ({recommended_level}) is Level 0 "
        f"or Level 1 and within max_safety_level={max_safety_level}, requires_founder_approval "
        "is false, recommended_next_task is non-empty, and no error/stop condition was recorded",
    )


#: The watch-level stop-reason taxonomy (distinct from a single round's own
#: `final_state`, which is a lower-level, round-orchestration vocabulary —
#: see `_classify_round_stop_reason` for the mapping between the two).
WATCH_STOP_REASONS = (
    "COMPLETED", "MAX_ROUNDS_REACHED", "DIRECTOR_STOPPED", "DIRECTOR_REJECTED_RESULT",
    "DIRECTOR_NEEDS_REVISION", "FOUNDER_APPROVAL_REQUIRED", "LEVEL_2_REQUESTED",
    "CLAUDE_FAILED", "VERIFICATION_FAILED", "SAFETY_VIOLATION", "LIVE_DB_CHANGED",
    "LIVE_VILLAGE_CHANGED", "GIT_STATE_UNSAFE", "INVALID_DIRECTOR_RESPONSE",
    "REPEATED_TASK_LOOP", "BROKER_ERROR",
    # 2026-09-10 task-exhaustion hardening + safe cumulative session seeding:
    # BACKLOG_EXHAUSTED is the "no useful work remains" case (multiple
    # distinct tasks stalled, or a hard global no-progress backstop was
    # hit) — deliberately distinct from REPEATED_TASK_LOOP, which still
    # means literally the same recommended task text reappeared. See
    # _is_repeated_task (unchanged) vs. the per-task stall tracking in
    # run_watch. SEED_REJECTED means --seed-patch failed verification,
    # failed to apply cleanly, or failed its post-seed test run — the
    # session never proceeds past round 1 on an unverified starting point.
    "BACKLOG_EXHAUSTED", "SEED_REJECTED",
)

#: Fingerprint fields that describe simulation STATE (what the Village is
#: doing) rather than the DB FILE itself — used only to choose between the
#: LIVE_VILLAGE_CHANGED and LIVE_DB_CHANGED labels below; both are already
#: caught by the exact same `_fingerprint_changed` mechanism either way.
_SIMULATION_FINGERPRINT_FIELDS = ("current_day", "current_period", "is_paused", "max_event_id")


def _classify_round_stop_reason(record: BridgeRoundRecord) -> str:
    """Maps one round's final_state/evaluation onto the watch-level
    taxonomy above — a LABEL for the audit trail and Founder summary,
    never a second decision mechanism (`_watch_continuation_decision`
    alone still decides continue-vs-stop)."""
    fs = record.final_state
    if fs in ("stopped_invalid_director_response", "stopped_unsafe_level"):
        return "INVALID_DIRECTOR_RESPONSE"
    if fs == "stopped_by_director":
        return "DIRECTOR_STOPPED"
    if fs == "stopped_seed_rejected":
        return "SEED_REJECTED"
    if fs == "stopped_pending_level2_not_executed":
        decision = record.director_decision or {}
        if decision.get("safety_level", 0) >= int(BridgeSafetyLevel.CONSEQUENTIAL):
            return "LEVEL_2_REQUESTED"
        return "FOUNDER_APPROVAL_REQUIRED"
    if fs == "stopped_safety_level_escalation":
        decision = record.director_decision or {}
        if decision.get("safety_level", 0) >= int(BridgeSafetyLevel.CONSEQUENTIAL):
            return "LEVEL_2_REQUESTED"
        return "SAFETY_VIOLATION"
    if fs in ("stopped_claude_not_invoked", "stopped_claude_timeout", "stopped_claude_nonzero_exit"):
        return "CLAUDE_FAILED"
    if fs == "stopped_safety_violation":
        before, after = record.live_db_snapshot_before or {}, record.live_db_snapshot_after or {}
        changed = set(_fingerprint_changed(before, after))
        if changed and changed.issubset(_SIMULATION_FINGERPRINT_FIELDS):
            return "LIVE_VILLAGE_CHANGED"
        return "LIVE_DB_CHANGED"
    if record.evaluation_error:
        return "VERIFICATION_FAILED"
    evaluation = record.director_evaluation
    if evaluation is not None:
        outcome = evaluation.get("outcome")
        if outcome == "blocked":
            return "DIRECTOR_REJECTED_RESULT"
        if outcome == "needs_revision":
            return "DIRECTOR_NEEDS_REVISION"
        if evaluation.get("requires_founder_approval"):
            return "FOUNDER_APPROVAL_REQUIRED"
        recommended_level = evaluation.get("recommended_safety_level")
        if recommended_level is not None and recommended_level > 1:
            return "LEVEL_2_REQUESTED"
        if not (evaluation.get("recommended_next_task") or "").strip():
            return "COMPLETED"
    if fs == "completed":
        return "COMPLETED"
    return "BROKER_ERROR"


def _project_dirty_files(paths: list[str]) -> set[str]:
    """`.director/**` is this bridge's own bookkeeping (see
    `collect_bridge_state`'s identical exclusion) — its constant background
    churn would otherwise make every watch round look like an "unexpected
    working-tree change" regardless of anything this bridge actually did."""
    return {p for p in paths if not p.startswith(".director/")}


def _normalize_task_text(text: str | None) -> str:
    """Whitespace/case-insensitive normalization for loop detection —
    deliberately crude (not semantic similarity) so its behavior stays
    predictable and auditable rather than another judgment call."""
    return " ".join((text or "").strip().lower().split())


def _is_repeated_task(task_history: list[str], candidate_normalized: str, *, max_repeats: int = 1) -> bool:
    """True once `candidate_normalized` would be appearing for more than
    `max_repeats` time(s) in `task_history`. Default 1: a task may appear
    once before being flagged on a second appearance — a small safe
    threshold, not zero tolerance, per the spec."""
    return bool(candidate_normalized) and task_history.count(candidate_normalized) >= max_repeats


WATCH_MAX_ROUNDS_DEFAULT = 3
#: Hard ceiling for this milestone — there is no unlimited mode. A caller
#: asking for more is refused outright (see run_watch), never silently
#: clamped, so a misconfigured caller finds out immediately rather than
#: getting a quietly-shortened run.
WATCH_MAX_ROUNDS_CEILING = 10

#: 2026-09-10 task-exhaustion hardening. When ONE task stalls (the Director
#: recommends repeating a task already seen this run, OR
#: `WATCH_NO_CHANGE_STREAK_EXHAUSTS_TASK` consecutive Level-1 rounds on the
#: current objective produced zero changed files), watch mode no longer
#: ends the whole session — it marks that individual task exhausted and
#: redirects the Director to a DIFFERENT backlog area (see
#: `_backlog_redirect_objective`). The session only stops with
#: `BACKLOG_EXHAUSTED` once `WATCH_MAX_BACKLOG_REDIRECTS` such redirects
#: have been spent — i.e. several attempts to move the Director onto
#: genuinely different work all failed to produce progress, which is the
#: real "no useful Level-1 work remains" signal. Bounded well below
#: `WATCH_MAX_ROUNDS_CEILING` so a redirect storm can never consume a whole
#: long run.
WATCH_NO_CHANGE_STREAK_EXHAUSTS_TASK = 2
WATCH_MAX_BACKLOG_REDIRECTS = 3

#: 2026-09-10 Director-stop policy. A round that ends cleanly and safely
#: with "nothing more to do" — an accepted round with an empty
#: `recommended_next_task` (classified COMPLETED), or a `decision="stop"`
#: with no safety/correctness fault (classified DIRECTOR_STOPPED) — no
#: longer ends the whole watch session on its own. Instead the Director is
#: re-prompted with the explicit backlog and the rule that it must confirm
#: NO other worthwhile, bounded, safe Level-1 task exists before it may
#: stop. A *productive* round (retained, with changed files) always resets
#: this. Only `WATCH_MAX_CONSECUTIVE_BARREN_STOPS` such "I inspected the
#: backlog and there is nothing" rounds IN A ROW — with no productive round
#: between them — end the run with `BACKLOG_EXHAUSTED`. Genuine
#: safety/correctness stops (blocked evaluation, live-DB change, Claude
#: failure, verification failure, Level 2, founder approval, unsafe git)
#: are NEVER soft and still stop immediately.
WATCH_MAX_CONSECUTIVE_BARREN_STOPS = 2

#: The exact stop-classifications (see `_classify_round_stop_reason`) that
#: represent a safe "no further work on THIS task" signal rather than a
#: fault. Everything else in `WATCH_STOP_REASONS` is terminal on sight.
_WATCH_SOFT_STOP_REASONS = frozenset({"COMPLETED", "DIRECTOR_STOPPED"})

#: Priority backlog areas for the autonomous Shady Pines / Internal Village
#: 2.5D-experience work. Used ONLY to redirect the Director after an
#: individual task stalls — deliberately phrased as broad areas, never
#: prescriptive tasks: the Director still picks the concrete next step and
#: the same Level-0/Level-1 safety gate still applies to whatever it picks.
WATCH_BACKLOG_AREAS: tuple[str, ...] = (
    "conversation visualization — who is talking to whom",
    "movement / activity clarity in the World View",
    "research visualization and the Research Wall",
    "Rabbit Holes visualization",
    "agent location / current-activity clarity",
    "semantic event replay",
    "Founder observability",
    "character differentiation",
    "interaction feedback",
    "frontend robustness",
    "useful World View controls",
    "readability / accessibility",
    "visual polish grounded in real persisted simulation state",
    "regression coverage for any of the above",
)


def _backlog_redirect_objective(
    *, exhausted_task: str, rejected_next_task: str, already_stalled: list[str],
    trigger: str = "stalled",
) -> str:
    """The next-round objective handed to the Director after the current
    task is finished-or-stuck. A plain string (never shell-concatenated,
    never re-parsed — exactly like every other objective this loop
    assigns); it only ADDS constraints, never relaxes any.

    `trigger`:
      - "stalled": the task made no progress / was a repeat — the Director
        is told to pick genuinely DIFFERENT work.
      - "feature_complete": the previous feature finished cleanly and the
        Director either returned no next task or chose to stop — the
        Director is told a normal completion should lead to the NEXT
        backlog item, and that it must explicitly confirm NO worthwhile
        bounded safe Level-1 task remains before it may stop the session.
    """
    stalled_list = "\n".join(f"  - {s}" for s in already_stalled) or "  (none yet)"
    areas = "\n".join(f"  - {a}" for a in WATCH_BACKLOG_AREAS)
    if trigger == "feature_complete":
        head = (
            "The previous Level-1 round finished cleanly, but you either returned no "
            "next task or chose to stop the whole watch session. Per the run's "
            "Director-stop policy: a normal feature completion should lead to "
            "SELECTING THE NEXT BACKLOG ITEM, not ending the session. You may only "
            "return a stop decision after inspecting the backlog below and explicitly "
            "determining that NO other worthwhile, bounded, safe Level-1 task remains "
            "(a genuine safety or correctness reason is always still grounds to stop "
            "immediately).\n"
            f"Just-completed objective (already done — do not repeat):\n  {(exhausted_task or '').strip()[:400]}\n"
        )
    else:
        head = (
            "The previous Level-1 task is EXHAUSTED: it either produced no changes "
            "across consecutive rounds, or you recommended repeating a task already "
            "attempted this session. Pick DIFFERENT work now — do not return to it.\n"
            f"Exhausted objective (do not repeat):\n  {(exhausted_task or '').strip()[:400]}\n"
            f"Rejected next-task suggestion (do not repeat):\n  {(rejected_next_task or '').strip()[:400]}\n"
        )
    return (
        head
        + "Tasks already completed or stalled this session — do NOT recommend any of "
        f"these or close variants:\n{stalled_list}\n"
        "First INSPECT the current cumulative staging state to see what already "
        "exists, then choose ONE concrete, safe, bounded improvement to the Shady "
        "Pines / Internal Village 2.5D World View from one of these priority "
        f"areas that is NOT already done:\n{areas}\n"
        "Hard constraints (unchanged): Level 0 or Level 1 only; grounded strictly in "
        "real persisted simulation state; never advance the live Village, mutate the "
        "canonical DB, run migrations, commit, push, or deploy; completable in a "
        "single round. Only if NO genuinely useful and distinct Level-1 work remains "
        "in ANY of these areas, say so explicitly and recommend stopping rather than "
        "inventing busywork."
    )


def _is_soft_backlog_stop(record: "BridgeRoundRecord", stop_reason_code: str) -> bool:
    """True when a `not may_continue` round is a SAFE 'nothing more to do on
    this task' signal (eligible for a backlog redirect) rather than a
    genuine safety/correctness fault (which must end the run immediately).
    Deliberately conservative: only the two soft classifications, and only
    when no error/stop condition and no suspected live-DB involvement were
    recorded for the round."""
    if stop_reason_code not in _WATCH_SOFT_STOP_REASONS:
        return False
    if record.errors:
        return False
    if record.live_db_involvement_suspected:
        return False
    return True


class WatchRunResult(BaseModel):
    """Everything a Founder or an automated caller needs to know about one
    supervised watch run, without re-deriving anything from raw per-round
    JSON. `rounds` preserves full BridgeRoundRecord detail (including the
    parent_round_id chain) for anyone who does need to dig in."""

    watch_run_id: str
    initial_objective: str
    rounds: list[BridgeRoundRecord] = Field(default_factory=list)
    stop_reason: str
    stop_detail: str
    max_rounds: int
    max_safety_level: int
    #: 2026-09-10 cumulative Level-1 staging workspace. level1_staging_
    #: workspace_used is False for a run with no Level-1 rounds at all
    #: (nothing was ever created). The cumulative_patch fields are None
    #: whenever no round's changes were ever retained (every Level-1 round
    #: was rolled back, or there were none) — see _finalize_level1_session.
    level1_staging_workspace_used: bool = False
    level1_cumulative_patch_path: str | None = None
    level1_cumulative_patch_sha256: str | None = None
    level1_cumulative_patch_size_bytes: int | None = None
    #: 2026-09-10 safe cumulative session seeding. Non-None whenever this
    #: run was started with a `--seed-patch`: the full provenance dict from
    #: `_seed_level1_staging_workspace` (ok, sha256, files, applied,
    #: test_ok, error) — recorded even when the seed was REJECTED (in which
    #: case the run also stops with `SEED_REJECTED`), so an unverified or
    #: unhealthy seed is still durably auditable.
    seed_provenance: dict[str, Any] | None = None
    #: 2026-09-10 task-exhaustion hardening. Normalized signatures of tasks
    #: that stalled (no progress / repeat) this run and were redirected away
    #: from.
    stalled_tasks: list[str] = Field(default_factory=list)
    #: 2026-09-10 Director-stop policy. Normalized signatures of tasks that
    #: finished cleanly (retained, with changed files) this run, after which
    #: the Director was redirected to the next backlog item rather than the
    #: session ending.
    completed_tasks: list[str] = Field(default_factory=list)


def run_watch(
    objective: str,
    *,
    max_rounds: int = WATCH_MAX_ROUNDS_DEFAULT,
    poll_seconds: int = 30,
    max_safety_level: int = 1,
    allow_detached_head: bool = False,
    director_client: DirectorClient | None = None,
    seed_patch: str | Path | None = None,
    seed_patch_sha256: str | None = None,
) -> WatchRunResult:
    """Supervised watch mode: repeats `run_once()` up to `max_rounds` times
    (hard-bounded at `WATCH_MAX_ROUNDS_CEILING`; there is no unlimited mode
    for this milestone), each round's objective coming from the PREVIOUS
    round's `DirectorEvaluation.recommended_next_task` — structurally
    (a plain string assignment; never shell-concatenated, never re-parsed)
    — once `_watch_continuation_decision()` has confirmed that round was
    fully clean. Returns a `WatchRunResult`; never raises for an ordinary
    stop condition (only truly unexpected exceptions are caught and
    reported as `BROKER_ERROR`, never left to crash the loop).

    Hard gates run BEFORE every round, including the first:

    1. `_check_git_state()` — ambiguous git state hard-stops immediately.
    2. A working-tree drift check against the dirty-file set captured at
       watch start, extended only by what each already-accepted round
       itself legitimately changed — any other unexpected dirty file stops
       watch mode (`GIT_STATE_UNSAFE`).

    After each round, `_watch_continuation_decision()` — not just
    `final_state` — decides whether to continue. A `blocked` evaluation
    always stops the loop. A `needs_revision` evaluation stops the loop
    UNLESS the requested revision is itself safely continuable (Level 0 or
    Level 1, within this run's `max_safety_level`, no Founder approval
    required, a non-empty `recommended_next_task`, and a clean deterministic
    pass) — in which case watch mode automatically starts another round
    using that recommended task, without Founder intervention. A missing/
    empty `recommended_next_task`, a Level-2 request, or a required Founder
    approval always stop the loop and return control to the Founder,
    regardless of outcome.

    Task-exhaustion handling runs on top of that gate: if the next task
    (normalized) has already appeared in this run's history, or
    `WATCH_NO_CHANGE_STREAK_EXHAUSTS_TASK` consecutive Level-1 rounds on
    the current objective produced zero changed files, that INDIVIDUAL task
    is marked exhausted and the Director is redirected to a different
    backlog area (`_backlog_redirect_objective`) — the run does NOT end.
    Only once `WATCH_MAX_BACKLOG_REDIRECTS` such redirects have been spent
    without the Director finding distinct, progress-making work does the
    run stop with `BACKLOG_EXHAUSTED`.

    Director-stop policy: a SAFE "nothing more to do on this task" stop —
    an accepted round with an empty `recommended_next_task` (COMPLETED), or
    a fault-free `decision="stop"` (DIRECTOR_STOPPED) — also does NOT end
    the session by itself. The Director is re-prompted with the explicit
    backlog and told it must confirm no other worthwhile bounded safe
    Level-1 task remains before stopping. A productive round (retained,
    with changed files) resets this; only `WATCH_MAX_CONSECUTIVE_BARREN_
    STOPS` such stops in a row (no productive round between) end the run
    with `BACKLOG_EXHAUSTED`. Genuine safety/correctness stops (blocked
    evaluation, live-DB change, Claude/verification failure, Level 2,
    founder approval, unsafe git) are never soft and stop immediately.

    `seed_patch` (with optional `seed_patch_sha256`) lets a NEW watch run
    continue from a PRIOR run's durable cumulative patch. It is verified
    early (fail fast → `SEED_REJECTED`) and then verified again and applied
    ONLY inside the isolated staging workspace, never REPO_ROOT — see
    `_seed_level1_staging_workspace`. `WatchRunResult.seed_provenance`
    records the outcome either way.

    `max_safety_level` (default 1: Level 0 and Level 1 both allowed, Level 2
    always refused regardless) is passed straight through to `run_once()` —
    pass `max_safety_level=0` for a Level-0-only supervised session."""
    watch_run_id = uuid.uuid4().hex[:16]
    result = WatchRunResult(
        watch_run_id=watch_run_id, initial_objective=objective, rounds=[],
        stop_reason="BROKER_ERROR", stop_detail="watch run did not complete initialization",
        max_rounds=max_rounds, max_safety_level=max_safety_level,
    )

    if not (1 <= max_rounds <= WATCH_MAX_ROUNDS_CEILING):
        result.stop_detail = (
            f"max_rounds={max_rounds} is outside the allowed range [1, {WATCH_MAX_ROUNDS_CEILING}] "
            "— refusing to start rather than silently clamping."
        )
        print(f"watch mode refusing to start: {result.stop_detail}")
        return result

    # 2026-09-10 safe cumulative session seeding — fail fast, before any
    # round or workspace, if the seed patch was named but is unreadable or
    # (when an expected hash was supplied) does not match. The full
    # verify-and-apply pass still happens later, ONLY inside the isolated
    # staging workspace (_seed_level1_staging_workspace via run_once); this
    # is just an early, cheap "don't even start" check.
    seed_patch_path: Path | None = None
    if seed_patch is not None:
        seed_patch_path = Path(seed_patch).expanduser().resolve()
        ok, error, _touched = _validate_seed_patch(seed_patch_path, seed_patch_sha256)
        if not ok:
            result.stop_reason = "SEED_REJECTED"
            result.stop_detail = f"seed patch {seed_patch_path} rejected before start: {error}"
            result.seed_provenance = {
                "ok": False, "patch_path": str(seed_patch_path), "sha256": None,
                "error": error, "applied": False, "test_ok": None,
            }
            print(f"watch mode refusing to start: {result.stop_detail}")
            return result

    print(
        f"\n=== WATCH MODE START: watch_run_id={watch_run_id}, max_rounds={max_rounds}, "
        f"max_safety_level={max_safety_level}"
        + (f", seed_patch={seed_patch_path.name}" if seed_patch_path else "")
        + " ==="
    )
    try:
        baseline_state = _check_git_state(allow_detached_head=allow_detached_head)
    except GitStateError as exc:
        result.stop_reason, result.stop_detail = "GIT_STATE_UNSAFE", f"git state is not trustworthy at watch start: {exc}"
        print(f"watch mode refusing to start: {result.stop_detail}")
        return result
    expected_dirty = _project_dirty_files(baseline_state["dirty_files"])
    print(f"baseline git state OK: branch={baseline_state['branch']!r}, "
          f"{len(expected_dirty)} pre-existing dirty project file(s) recorded as the expected baseline.")

    # 2026-09-10 cumulative staging: ONE Level1StagingSession per watch run,
    # threaded unchanged through every run_once() call below — see the
    # Level1StagingSession module comment (above _cleanup_level1_workspace)
    # for the full round-transaction model. Everything from here down is
    # wrapped in try/finally purely so _finalize_level1_session() (cumulative
    # patch + cleanup + registry unregister) runs exactly once no matter
    # which of this loop's several `return result` points fires.
    level1_session = Level1StagingSession(
        watch_run_id, seed_patch_path=seed_patch_path, seed_patch_sha256=seed_patch_sha256,
    )
    #: normalized signatures of tasks that stalled / were completed this run.
    #: Defined before the try/finally so the finally can always read them.
    stalled_task_signatures: list[str] = []
    completed_task_signatures: list[str] = []
    try:
        current_objective = objective
        task_history = [_normalize_task_text(objective)]
        parent_round_id: str | None = None
        no_change_streak = 0
        redirect_count = 0
        #: consecutive clean "nothing more to do" stops with no productive
        #: (retained + changed-files) round between them — Director-stop policy.
        barren_soft_stops = 0

        for i in range(max_rounds):
            print(f"\n--- watch round {i + 1}/{max_rounds} (parent_round_id={parent_round_id}) ---")
            try:
                git_state = _check_git_state(allow_detached_head=allow_detached_head)
            except GitStateError as exc:
                result.stop_reason = "GIT_STATE_UNSAFE"
                result.stop_detail = f"git state is not trustworthy before round {i + 1}: {exc}"
                print(f"watch mode stopping: {result.stop_detail}")
                return result
            current_dirty = _project_dirty_files(git_state["dirty_files"])
            unexpected = current_dirty - expected_dirty
            if unexpected:
                result.stop_reason = "GIT_STATE_UNSAFE"
                result.stop_detail = (
                    f"working tree changed outside the expected scope before round {i + 1}: {sorted(unexpected)}"
                )
                print(f"watch mode stopping: {result.stop_detail}")
                return result

            try:
                record = run_once(
                    current_objective, director_client=director_client, max_safety_level=max_safety_level,
                    level1_session=level1_session,
                )
            except Exception as exc:  # noqa: BLE001 - the supervised loop must never crash; classify and stop instead
                result.stop_reason = "BROKER_ERROR"
                result.stop_detail = f"run_once raised an unexpected exception: {type(exc).__name__}: {exc}"
                print(f"watch mode stopping: {result.stop_detail}")
                return result

            record.parent_round_id = parent_round_id
            result.rounds.append(record)
            parent_round_id = record.round_id
            print(f"round_id={record.round_id} final_state={record.final_state}")

            may_continue, reason = _watch_continuation_decision(record, max_safety_level=max_safety_level)
            stop_reason_code = _classify_round_stop_reason(record)
            print(f"continuation decision: {'CONTINUE' if may_continue else 'STOP'} ({stop_reason_code}) — {reason}")

            round_was_productive = bool(record.level1_retained) and bool(record.changed_files)

            if not may_continue:
                # 2026-09-10 Director-stop policy: a SAFE "nothing more to do
                # on this task" stop (COMPLETED / DIRECTOR_STOPPED, no fault)
                # does not end the session by itself — re-prompt the Director
                # with the explicit backlog first. Only WATCH_MAX_CONSECUTIVE_
                # BARREN_STOPS such stops in a row (no productive round
                # between) become BACKLOG_EXHAUSTED. Genuine faults are never
                # soft (see _is_soft_backlog_stop) and fall straight through.
                if _is_soft_backlog_stop(record, stop_reason_code) and i + 1 < max_rounds:
                    if round_was_productive:
                        expected_dirty |= set(record.changed_files)
                        done_label = _normalize_task_text(
                            (record.director_decision or {}).get("task_for_claude") or current_objective
                        )[:200]
                        if done_label and done_label not in completed_task_signatures:
                            completed_task_signatures.append(done_label)
                        barren_soft_stops = 0
                    else:
                        barren_soft_stops += 1

                    if barren_soft_stops >= WATCH_MAX_CONSECUTIVE_BARREN_STOPS:
                        result.stalled_tasks = list(stalled_task_signatures)
                        result.stop_reason = "BACKLOG_EXHAUSTED"
                        result.stop_detail = (
                            f"{barren_soft_stops} consecutive clean rounds where the Director inspected "
                            f"the backlog and found no worthwhile bounded safe Level-1 task remaining "
                            f"(last: {stop_reason_code} — {reason})."
                        )
                        print(f"watch mode stopping: {result.stop_detail}")
                        return result

                    print(
                        f"soft stop ({stop_reason_code}); Director-stop policy: re-prompting with the "
                        f"explicit backlog [barren streak {barren_soft_stops}/{WATCH_MAX_CONSECUTIVE_BARREN_STOPS}, "
                        f"{len(completed_task_signatures)} task(s) completed so far]"
                    )
                    redirect = _backlog_redirect_objective(
                        exhausted_task=current_objective,
                        rejected_next_task=(record.director_evaluation or {}).get("recommended_next_task") or "",
                        already_stalled=completed_task_signatures + stalled_task_signatures,
                        trigger="feature_complete",
                    )
                    task_history.append(_normalize_task_text(redirect))
                    no_change_streak = 0
                    current_objective = redirect
                    time.sleep(poll_seconds)
                    continue

                result.stop_reason, result.stop_detail = stop_reason_code, reason
                return result

            barren_soft_stops = 0
            expected_dirty |= set(record.changed_files)

            if record.safety_level == int(BridgeSafetyLevel.SANDBOX) and not record.changed_files:
                no_change_streak += 1
            else:
                no_change_streak = 0

            evaluation = record.director_evaluation or {}
            next_task = (evaluation.get("recommended_next_task") or "").strip()
            normalized_next = _normalize_task_text(next_task)
            current_signature = _normalize_task_text(current_objective)

            # 2026-09-10 task-exhaustion hardening. A stalled INDIVIDUAL task
            # no longer ends the whole session: it is recorded as exhausted
            # and the Director is redirected to a different backlog area
            # (_backlog_redirect_objective). Only once WATCH_MAX_BACKLOG_
            # REDIRECTS such redirects have been spent — i.e. several
            # attempts to move onto genuinely different work all failed —
            # does the run stop with BACKLOG_EXHAUSTED. That covers both the
            # "distinct tasks each stall" case and the "Director keeps
            # recommending an already-exhausted task" case with one bound.
            next_task_repeats = _is_repeated_task(task_history, normalized_next)
            no_progress_streak_hit = no_change_streak >= WATCH_NO_CHANGE_STREAK_EXHAUSTS_TASK
            if next_task_repeats or no_progress_streak_hit:
                if no_progress_streak_hit and current_signature and current_signature not in stalled_task_signatures:
                    stalled_task_signatures.append(current_signature)
                if next_task_repeats and normalized_next and normalized_next not in stalled_task_signatures:
                    stalled_task_signatures.append(normalized_next)
                result.stalled_tasks = list(stalled_task_signatures)
                redirect_count += 1

                why = (
                    "the next recommended task repeats one already attempted this run"
                    if next_task_repeats else
                    f"{no_change_streak} consecutive Level-1 rounds on this task produced no changed files"
                )

                if redirect_count > WATCH_MAX_BACKLOG_REDIRECTS:
                    result.stop_reason = "BACKLOG_EXHAUSTED"
                    result.stop_detail = (
                        f"exhausted {WATCH_MAX_BACKLOG_REDIRECTS} backlog redirect(s) without the "
                        f"Director finding distinct, progress-making Level-1 work "
                        f"(stalled tasks: {stalled_task_signatures or 'none recorded'}); last trigger: {why}."
                    )
                    print(f"watch mode stopping: {result.stop_detail}")
                    return result

                print(
                    f"task exhausted ({why}); redirecting the Director to a different backlog area "
                    f"[redirect {redirect_count}/{WATCH_MAX_BACKLOG_REDIRECTS}]"
                )
                no_change_streak = 0
                redirect = _backlog_redirect_objective(
                    exhausted_task=current_objective,
                    rejected_next_task=next_task,
                    already_stalled=stalled_task_signatures,
                )
                task_history.append(_normalize_task_text(redirect))
                if i + 1 < max_rounds:
                    current_objective = redirect
                    time.sleep(poll_seconds)
                continue

            task_history.append(normalized_next)

            if i + 1 < max_rounds:
                current_objective = next_task
                time.sleep(poll_seconds)

        result.stop_reason = "MAX_ROUNDS_REACHED"
        result.stop_detail = f"completed {max_rounds} round(s) without an unsafe or terminal condition; more work may remain."
        print(f"\nwatch mode reached max_rounds; stopping. ({result.stop_reason})")
        return result
    finally:
        workspace_was_created = level1_session.workspace is not None
        patch_path, patch_sha, patch_size = _finalize_level1_session(level1_session, watch_run_id)
        result.level1_staging_workspace_used = workspace_was_created
        result.level1_cumulative_patch_path = patch_path
        result.level1_cumulative_patch_sha256 = patch_sha
        result.level1_cumulative_patch_size_bytes = patch_size
        if level1_session.seed_provenance is not None:
            result.seed_provenance = level1_session.seed_provenance
        result.stalled_tasks = list(stalled_task_signatures)
        result.completed_tasks = list(completed_task_signatures)


def print_founder_summary(result: WatchRunResult) -> None:
    """Step 7's exact template. Reads only already-computed fields; never
    calls a model, never re-derives anything, never dumps a raw
    transcript — the whole point is that the Founder does not need to."""
    rounds = result.rounds
    last = rounds[-1] if rounds else None
    last_evaluation = (last.director_evaluation or {}) if last else {}
    changed_files = sorted({f for r in rounds for f in r.changed_files})
    live_before = rounds[0].live_db_snapshot_before if rounds else None
    live_after = last.live_db_snapshot_after if last else None
    healthy_reasons = ("COMPLETED", "MAX_ROUNDS_REACHED", "DIRECTOR_STOPPED", "BACKLOG_EXHAUSTED")

    print("\n" + "=" * 70)
    print("SUPERVISED DIRECTOR RUN")
    print("=" * 70)
    print(f"\nRounds completed: {len(rounds)}/{result.max_rounds}")
    print(f"Final status: {'HEALTHY' if result.stop_reason in healthy_reasons else 'STOPPED'}")
    print(f"Stop reason: {result.stop_reason}")
    print(f"  {result.stop_detail}")
    print(f"\nStarting objective: {result.initial_objective}")
    print(f"Final Director assessment: {last_evaluation.get('summary', '(none)')}")
    print(f"\nFiles changed: {changed_files or []}")
    print("Tests: see deterministic_verification/diff_stat per round in the audit log")
    if live_before and live_after:
        print(
            f"\nLive Village: Day {live_before.get('current_day')} {live_before.get('current_period')} "
            f"(event {live_before.get('max_event_id')}) -> "
            f"Day {live_after.get('current_day')} {live_after.get('current_period')} "
            f"(event {live_after.get('max_event_id')})"
        )
        print(f"DB integrity: {live_after.get('integrity_ok')}")
    print(f"\nRecommended next action: {last_evaluation.get('recommended_next_task') or '(none)'}")
    print(f"Founder approval required: {last_evaluation.get('requires_founder_approval', False)}")
    print(f"Requested safety level: {last_evaluation.get('recommended_safety_level', 'n/a')}")
    if result.seed_provenance is not None:
        sp = result.seed_provenance
        print(
            f"\nSeed patch: {sp.get('patch_path')}\n"
            f"  ok={sp.get('ok')} applied={sp.get('applied')} test_ok={sp.get('test_ok')} "
            f"sha256={sp.get('sha256')}"
        )
        if sp.get("error"):
            print(f"  error: {sp['error']}")
        print("  verified + applied ONLY inside the isolated staging workspace — never REPO_ROOT.")
    if result.completed_tasks:
        print(f"\nTasks completed then redirected to the next backlog item ({len(result.completed_tasks)}):")
        for s in result.completed_tasks:
            print(f"  - {s}")
    if result.stalled_tasks:
        print(f"\nStalled/exhausted tasks ({len(result.stalled_tasks)}):")
        for s in result.stalled_tasks:
            print(f"  - {s}")
    if result.level1_staging_workspace_used:
        print(f"\nLevel-1 cumulative patch: {result.level1_cumulative_patch_path or '(nothing retained)'}")
        if result.level1_cumulative_patch_sha256:
            print(f"  sha256={result.level1_cumulative_patch_sha256} size={result.level1_cumulative_patch_size_bytes}B")
        print("  read-only audit artifact — never auto-applied to the main repo.")
    print(f"\nAudit location: {BRIDGE_LOG_PATH} (watch_run_id={result.watch_run_id})")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Director bridge: Claude Code <-> OpenAI Director.")
    parser.add_argument("mode", choices=["once", "watch"])
    parser.add_argument(
        "--objective", default="Advance The Internal Village's development safely.",
        help="The objective handed to the OpenAI Director as context for this round.",
    )
    parser.add_argument(
        "--max-safety-level", type=int, default=1, choices=[0, 1],
        help="Ceiling below Level 2 (always refused regardless). Default 1 (Level 0/1 both allowed).",
    )
    parser.add_argument(
        "--max-rounds", type=int, default=WATCH_MAX_ROUNDS_DEFAULT,
        help=f"watch mode only. Default {WATCH_MAX_ROUNDS_DEFAULT}; hard ceiling {WATCH_MAX_ROUNDS_CEILING} "
        "(there is no unlimited mode for this milestone).",
    )
    parser.add_argument("--poll-seconds", type=int, default=30, help="watch mode only.")
    parser.add_argument(
        "--allow-detached-head", action="store_true",
        help="watch mode only. Off by default: a detached HEAD is treated as ambiguous git state.",
    )
    parser.add_argument(
        "--seed-patch", default=None,
        help="watch mode only. Path to a PRIOR watch run's cumulative .patch to seed the "
        "persistent Level-1 staging workspace with. Verified (path-safety + optional "
        "--seed-patch-sha256) and applied ONLY inside the isolated workspace, never REPO_ROOT; "
        "the seeded state must pass every approved test before any round builds on it.",
    )
    parser.add_argument(
        "--seed-patch-sha256", default=None,
        help="watch mode only. Expected SHA-256 of --seed-patch; a mismatch refuses to start "
        "(SEED_REJECTED) rather than seeding an unverified starting point.",
    )
    args = parser.parse_args()

    if args.mode == "once":
        record = run_once(args.objective, max_safety_level=args.max_safety_level)
        print(json.dumps(record.model_dump(), indent=2, default=str))
        return 0 if record.final_state in ("completed", "stopped_by_director") else 1

    result = run_watch(
        args.objective, max_rounds=args.max_rounds, poll_seconds=args.poll_seconds,
        max_safety_level=args.max_safety_level, allow_detached_head=args.allow_detached_head,
        seed_patch=args.seed_patch, seed_patch_sha256=args.seed_patch_sha256,
    )
    print_founder_summary(result)
    return 0 if result.stop_reason in (
        "COMPLETED", "MAX_ROUNDS_REACHED", "DIRECTOR_STOPPED", "BACKLOG_EXHAUSTED",
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
