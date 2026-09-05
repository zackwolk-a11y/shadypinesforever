"""Permanent registry of known-invalid live-event intervals.

Director/evidence infrastructure only. Never touches the Village database,
never changes Village behavior, never mutates a single Event row -- the
contaminated rows stay exactly where they are, in the immutable event log,
forever (per the Founder's explicit "do not rewrite live history"
instruction). This module exists solely so that ANY future Director
analysis -- a Level 2A diagnostic, a broker capability, an ad hoc
read-only query, a Founder Packet's own hand-written SQL -- has one
canonical place to check "is this event id part of a known-contaminated
interval" rather than each tool re-deriving or forgetting the exclusion
independently.

First (and, as of this writing, only) entry: 2026-09-05's real incident,
documented in full in
``.director/founder_packets/incident_contaminated_fixture_interval_2026-09-05.md``.
A fixture-provider run of ``director_unattended_fixturetest.py`` (before
that suite redirected ``VILLAGE_DATA_ROOT`` for every subprocess it
launched) advanced the real canonical live Village by 10 events -- a
single MORNING_GATHERING conversation continuing for 4 fixture-generated
turns before ending naturally. Every one of the 10 rows carries
``payload.is_fixture: true``; none involved a real Anthropic call, real
research, or real agent-to-agent content. The Founder's explicit decision
(2026-09-05): do not restore (no exact event-623 backup exists), do not
delete, do not rewrite -- classify, exclude from science, and move the
Village's operating baseline forward from 623 to 633.

Adding a new entry here is itself a Director/evidence-infrastructure
change (like everything else in this module) -- it never requires
touching ``app/``, but it IS a permanent, git-tracked fact about the
Village's history and should be treated with the same care as any other
row in this file: real, verified, dated, and never silently edited after
the fact. If a future incident needs to reclassify or narrow ``624-633``
specifically, add a NEW entry documenting the correction rather than
editing this one in place -- the same evidence-hygiene discipline this
whole project already applies to claims and hypotheses.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContaminatedRange:
    start_event_id: int
    end_event_id: int
    label: str
    reason: str
    discovered_date: str
    detail_packet: str

    def contains(self, event_id: int) -> bool:
        return self.start_event_id <= event_id <= self.end_event_id


#: Append-only. Every entry here is a permanent, factual record of a real
#: incident -- never edited after the fact (see module docstring).
CONTAMINATED_EVENT_RANGES: tuple[ContaminatedRange, ...] = (
    ContaminatedRange(
        start_event_id=624,
        end_event_id=633,
        label="CONTAMINATED_FIXTURE_TEST_INTERVAL",
        reason=(
            "A fixture-provider test run (director_unattended_fixturetest.py, "
            "before it redirected VILLAGE_DATA_ROOT per-subprocess) advanced the "
            "real canonical live Village by 10 events: one MORNING_GATHERING "
            "conversation continuing 4 fixture-generated turns. Every row carries "
            "payload.is_fixture=true; no real Anthropic call, real research, or "
            "real cross-agent content is present in this interval. Founder "
            "decision 2026-09-05: preserve in immutable history, exclude from all "
            "scientific analysis, do not restore or rewrite."
        ),
        discovered_date="2026-09-05",
        detail_packet="incident_contaminated_fixture_interval_2026-09-05.md",
    ),
)


def is_contaminated(event_id: int) -> bool:
    """True if event_id falls inside any registered contaminated range."""
    return any(r.contains(event_id) for r in CONTAMINATED_EVENT_RANGES)


def contamination_label(event_id: int) -> str | None:
    """The label of the contaminated range event_id falls in, or None."""
    for r in CONTAMINATED_EVENT_RANGES:
        if r.contains(event_id):
            return r.label
    return None


def filter_out_contaminated(rows: list[dict], id_key: str = "id") -> list[dict]:
    """Returns only the rows whose id_key is NOT inside any contaminated
    range -- the direct, reusable exclusion any analysis script should
    call on rows read from the events table (or anything joined to it)
    before treating them as scientific evidence."""
    return [r for r in rows if not is_contaminated(r[id_key])]


def annotate_contamination(rows: list[dict], id_key: str = "id") -> list[dict]:
    """Returns rows unchanged except for one added key, 'contaminated'
    (True/False) and 'contamination_label' (str or None) -- for callers
    that want to SHOW contaminated rows (e.g. an audit trace) rather than
    silently drop them, while still making their status explicit and
    impossible to overlook."""
    out = []
    for r in rows:
        row = dict(r)
        row["contaminated"] = is_contaminated(r[id_key])
        row["contamination_label"] = contamination_label(r[id_key]) if row["contaminated"] else None
        out.append(row)
    return out
