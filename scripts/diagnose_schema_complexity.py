#!/usr/bin/env python3
"""Isolated live diagnostic for the "schema is too complex" hypothesis.

Submits THREE candidate output_config.format json_schema payloads straight to
POST /v1/messages, using the EXACT transform AnthropicLLMProvider._schema_for
already uses (app/providers/llm/anthropic.py) -- never a hand-reconstructed
approximation. Each call sends a trivial one-line user message and a small
max_tokens, purely to see whether the API *accepts the schema* -- it never
runs app.services.orchestrator, never touches any village database (this
script imports nothing from app.db/app.services), never advances a
simulated day, and generates no substantive model output beyond whatever a
tiny forced completion needs to satisfy the schema.

  A. AgentDecision exactly as deployed today (schema unmodified).
  B. AgentDecision with ONLY AgentAction.target_question_id removed.
  C. A candidate reduced schema: target_question_id and every other
     target_*_id/target_agent_id field on AgentAction collapsed into one
     generic `target_id: str | None`.

Requires ANTHROPIC_API_KEY (or an `ant auth login` profile) in the
environment -- refuses to run without one rather than silently skipping.

Usage::

    ANTHROPIC_API_KEY=... python scripts/diagnose_schema_complexity.py
    python scripts/diagnose_schema_complexity.py --offline   # schema-only, no network
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# This script deliberately never imports app.db or app.services -- only the
# pure-Pydantic schema module and the provider's own schema-transform helper.
from app.schemas.actions import ActionType, AgentAction, AgentDecision  # noqa: E402
from app.providers.llm.anthropic import AnthropicLLMProvider  # noqa: E402

MODEL = "claude-opus-5"
TRIVIAL_SYSTEM = "Return the smallest valid instance of the given schema. Do not add commentary."
TRIVIAL_USER = "Return a minimal, valid decision: DO_NOTHING, no actions, no dialogue."
MAX_TOKENS = 256  # generous enough for a trivial DO_NOTHING decision, nothing more


def _complexity_metrics(schema: dict) -> dict:
    """Cheap, real, reproducible complexity proxies -- not Anthropic's
    internal ceiling (undocumented), but the same shape of measurement a
    schema-compilation cost would plausibly scale with: how many properties
    exist across the whole $defs graph, how deep it nests, how many
    enum/anyOf branch points it has, and its raw serialized size."""

    def walk(node, depth: int) -> tuple[int, int, int, int]:
        if not isinstance(node, dict):
            return 0, depth, 0, 0
        props = node.get("properties", {})
        prop_count = len(props)
        branch_count = len(node.get("enum", [])) and 1 or 0
        branch_count += len(node.get("anyOf", [])) or len(node.get("oneOf", []))
        max_depth = depth
        total_props = prop_count
        total_branches = branch_count
        total_refs = 1 if "$ref" in node else 0
        for value in list(props.values()) + list(node.get("$defs", {}).values()):
            p, d, b, r = walk(value, depth + 1)
            total_props += p
            max_depth = max(max_depth, d)
            total_branches += b
            total_refs += r
        for item in node.get("anyOf", []) + node.get("oneOf", []):
            p, d, b, r = walk(item, depth + 1)
            total_props += p
            max_depth = max(max_depth, d)
            total_branches += b
            total_refs += r
        items = node.get("items")
        if items:
            p, d, b, r = walk(items, depth + 1)
            total_props += p
            max_depth = max(max_depth, d)
            total_branches += b
            total_refs += r
        return total_props, max_depth, total_branches, total_refs

    total_props, max_depth, total_branches, total_refs = walk(schema, 0)
    return {
        "total_properties_incl_defs": total_props,
        "max_nesting_depth": max_depth,
        "enum_or_anyof_branch_points": total_branches,
        "ref_count": total_refs,
        "top_level_defs": len(schema.get("$defs", {})),
        "serialized_bytes": len(json.dumps(schema)),
    }


def _schema_a() -> dict:
    """A. AgentDecision exactly as deployed -- the real transform, the real model."""
    provider = AnthropicLLMProvider.__new__(AnthropicLLMProvider)  # no client needed for _schema_for
    return provider._schema_for(AgentDecision)


def _schema_b() -> dict:
    """B. The same schema with ONLY AgentAction.target_question_id removed."""
    from pydantic import create_model

    fields = {
        name: (f.annotation, f)
        for name, f in AgentAction.model_fields.items()
        if name != "target_question_id"
    }
    ActionWithoutQuestionId = create_model(
        "AgentActionWithoutQuestionId", __base__=None, **fields
    )
    ActionWithoutQuestionId.model_config = AgentAction.model_config

    DecisionB = create_model(
        "AgentDecisionSchemaB",
        __base__=None,
        summary=(str, AgentDecision.model_fields["summary"]),
        activity=(str, AgentDecision.model_fields["activity"]),
        location=(str | None, AgentDecision.model_fields["location"]),
        actions=(list[ActionWithoutQuestionId], AgentDecision.model_fields["actions"]),
        public_dialogue=(str | None, AgentDecision.model_fields["public_dialogue"]),
        reflection=(AgentDecision.model_fields["reflection"].annotation, AgentDecision.model_fields["reflection"]),
    )
    DecisionB.model_config = AgentDecision.model_config

    provider = AnthropicLLMProvider.__new__(AnthropicLLMProvider)
    return provider._schema_for(DecisionB)


def _schema_c() -> dict:
    """C. Candidate consolidation: every target_*_id field (including
    target_question_id) collapsed into one generic `target_id: str | None`.
    A stand-in for the "smallest safe fix" question -- NOT a proposal to
    actually ship this; see the design comparison in the report."""
    from pydantic import create_model

    collapsed_out = {
        "target_agent_id", "target_research_id", "target_wall_post_id",
        "target_rabbit_hole_id", "target_claim_id", "target_belief_id",
        "target_question_id",
    }
    fields = {
        name: (f.annotation, f)
        for name, f in AgentAction.model_fields.items()
        if name not in collapsed_out
    }
    fields["target_id"] = (str | None, None)
    ActionConsolidated = create_model("AgentActionConsolidated", __base__=None, **fields)
    ActionConsolidated.model_config = AgentAction.model_config

    DecisionC = create_model(
        "AgentDecisionSchemaC",
        __base__=None,
        summary=(str, AgentDecision.model_fields["summary"]),
        activity=(str, AgentDecision.model_fields["activity"]),
        location=(str | None, AgentDecision.model_fields["location"]),
        actions=(list[ActionConsolidated], AgentDecision.model_fields["actions"]),
        public_dialogue=(str | None, AgentDecision.model_fields["public_dialogue"]),
        reflection=(AgentDecision.model_fields["reflection"].annotation, AgentDecision.model_fields["reflection"]),
    )
    DecisionC.model_config = AgentDecision.model_config

    provider = AnthropicLLMProvider.__new__(AnthropicLLMProvider)
    return provider._schema_for(DecisionC)


def _try_live_call(client, schema: dict, label: str) -> dict:
    """One minimal, isolated call. Returns a small result dict -- never
    raises past this function, so A/B/C can all be attempted even if an
    earlier one fails."""
    try:
        raw = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=TRIVIAL_SYSTEM,
            messages=[{"role": "user", "content": TRIVIAL_USER}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        return {
            "label": label, "accepted": True, "stop_reason": raw.stop_reason,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - report the exact error text, never swallow it
        message = getattr(exc, "message", None) or str(exc)
        return {"label": label, "accepted": False, "stop_reason": None, "error": message}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline", action="store_true",
        help="compute and compare the three schemas only -- no network call, no key required",
    )
    args = parser.parse_args()

    schemas = {"A (deployed, unmodified)": _schema_a(), "B (target_question_id removed)": _schema_b(),
               "C (candidate target_id consolidation)": _schema_c()}

    print("=" * 70)
    print("STRUCTURAL COMPARISON (no network -- computed from the real")
    print("AnthropicLLMProvider._schema_for transform, the real Pydantic models)")
    print("=" * 70)
    for label, schema in schemas.items():
        m = _complexity_metrics(schema)
        print(f"\n{label}:")
        for k, v in m.items():
            print(f"  {k}: {v}")

    if args.offline:
        print("\n--offline: skipping live calls. Structural numbers above are NOT proof")
        print("of the live complexity-ceiling hypothesis -- only Anthropic's own")
        print("acceptance/rejection of each payload settles that.")
        return 0

    import os
    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
        print("\nFAIL: no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN in the environment, and no")
        print("`ant auth login` profile could be assumed present -- refusing to guess at a")
        print("result. Export a credential and re-run, or pass --offline for the schema-only")
        print("comparison above.")
        return 1

    import anthropic

    client = anthropic.Anthropic()

    print("\n" + "=" * 70)
    print("LIVE CALLS (minimal, isolated -- no simulation, no DB writes)")
    print("=" * 70)
    results = []
    for label, schema in schemas.items():
        print(f"\nSubmitting {label} ...")
        result = _try_live_call(client, schema, label)
        results.append(result)
        if result["accepted"]:
            print(f"  ACCEPTED (stop_reason={result['stop_reason']})")
        else:
            print(f"  REJECTED: {result['error']}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for r in results:
        print(f"  {r['label']}: {'ACCEPTED' if r['accepted'] else 'REJECTED'}"
              + (f" -- {r['error']}" if r["error"] else ""))

    a_rejected = not results[0]["accepted"]
    b_accepted = results[1]["accepted"]
    threshold_confirmed = a_rejected and b_accepted
    print(f"\nThreshold hypothesis (A rejected AND B accepted): "
          f"{'CONFIRMED' if threshold_confirmed else 'NOT CONFIRMED'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
