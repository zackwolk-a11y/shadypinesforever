"""Canon integrity: the founding nine, honest sourcing, no fabricated memories."""
import copy

import pytest
import yaml
from pydantic import ValidationError

from becoming import CANON_DIR
from becoming.canon import (
    RESIDENT_IDS, ResidentSpec, load_curriculum, load_residents, load_style_paragraph,
)


@pytest.fixture(scope="module")
def residents():
    return load_residents()


def test_exactly_the_founding_nine(residents):
    assert set(residents) == {"tony", "mark", "haize", "ashley", "ralph", "bernie", "mao", "pepper", "anna"}
    assert [residents[r].number for r in RESIDENT_IDS] == list(range(1, 10))


def _raw(name="01_tony.yaml"):
    return yaml.safe_load((CANON_DIR / "residents" / name).read_text())


@pytest.mark.parametrize("bad_id", ["paisley", "optimisto", "vince"])
def test_forbidden_or_legacy_roster_rejected(bad_id):
    raw = _raw()
    raw["id"] = bad_id
    raw["home"]["location_id"] = f"home_{bad_id}"
    with pytest.raises(ValidationError):
        ResidentSpec.model_validate(raw)


def test_canon_cannot_claim_a_verified_source():
    raw = _raw()
    raw["sources"][0]["status"] = "retrieved_verified"
    with pytest.raises(ValidationError, match="research pipeline"):
        ResidentSpec.model_validate(raw)


@pytest.mark.parametrize("field", ["memories", "individual_memories", "shared_memories", "development_history", "relationship_history"])
def test_canon_cannot_carry_event_memories(field):
    raw = _raw()
    raw[field] = [{"summary": "We talked by the fire"}]
    with pytest.raises(ValidationError):
        ResidentSpec.model_validate(raw)


def test_foundational_identity_separate_from_revisable_beliefs(residents):
    for spec in residents.values():
        assert spec.foundational_identity.recurring_tension
        assert all(0 <= b.confidence <= 1 for b in spec.revisable.beliefs)
        assert len({b.id for b in spec.revisable.beliefs}) == len(spec.revisable.beliefs)


def test_residents_are_not_interchangeable(residents):
    tensions = {s.foundational_identity.recurring_tension for s in residents.values()}
    interests = [frozenset(s.foundational_identity.central_interests) for s in residents.values()]
    assert len(tensions) == 9
    assert len(set(interests)) == 9


def test_every_resident_names_the_real_inspiration_as_non_participant(residents):
    for spec in residents.values():
        text = spec.inspiration.summary.lower()
        if spec.id == "pepper":
            assert "no biography" in text
        elif spec.id == "ralph":
            assert "emerson" in text and "thoreau" in text
        else:
            assert "not a participant" in text or "is not a participant" in text


def test_relationship_seeds_point_at_residents(residents):
    for spec in residents.values():
        for seed in spec.relationship_seeds:
            assert seed.with_ in residents and seed.with_ != spec.id


def test_curriculum_has_ten_multi_thread_questions():
    cur = load_curriculum()
    assert len(cur.questions) == 10
    assert all(len(q.threads) >= 2 for q in cur.questions)
    assert cur.provenance == "reconstructed_from_master_prompt"


def test_style_paragraph_is_canonical():
    text = load_style_paragraph()
    assert text.startswith("Create a cozy, ecologically rich 16-bit-inspired RPG world")
    assert text.endswith("sterile modern office design.")
