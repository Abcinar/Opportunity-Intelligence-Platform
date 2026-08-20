"""
Focused tests for OIP DimensionResult V1.

Minimum coverage (20+ tests):
- valid creation
- score validation
- confidence validation
- empty dimension rejection
- evidence ID handling
- supporting / contradicting evidence
- serialization
- deserialization
- round-trip equality
- deterministic / stable serialization
- trend
- data_quality
- flags
- contradiction preservation
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from engine.dimension_result import (
    DataQuality,
    DimensionName,
    DimensionResult,
    TrendLabel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "dimension": DimensionName.DEMAND,
        "score": 0.72,
        "confidence": 0.85,
        "explanation": "Rising star velocity and search interest indicate demand.",
        "supporting_evidence_ids": ["ev-001", "ev-002"],
        "contradicting_evidence_ids": [],
        "trend": TrendLabel.RISING,
        "label": None,
        "data_quality": DataQuality(
            evidence_count=2,
            source_diversity=0.5,
            avg_reliability=0.9,
            avg_confidence=0.88,
            temporal_coverage="last_90d",
        ),
        "flags": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Valid creation
# ---------------------------------------------------------------------------

def test_valid_creation():
    dr = DimensionResult.create(**_valid_kwargs())
    assert dr.dimension == "demand"
    assert dr.score == 0.72
    assert dr.confidence == 0.85
    assert "Rising star" in dr.explanation
    assert dr.supporting_evidence_ids == ("ev-001", "ev-002")
    assert dr.contradicting_evidence_ids == ()
    assert dr.trend == "rising"
    assert dr.label is None
    assert dr.data_quality.evidence_count == 2
    assert dr.flags == ()


def test_create_accepts_string_dimension_and_trend():
    dr = DimensionResult.create(
        **_valid_kwargs(dimension="pain", trend="falling")
    )
    assert dr.dimension == "pain"
    assert dr.trend == "falling"


def test_all_ten_dimension_names():
    for name in DimensionName:
        dr = DimensionResult.create(**_valid_kwargs(dimension=name))
        assert dr.dimension == name.value


# ---------------------------------------------------------------------------
# 2. Score validation
# ---------------------------------------------------------------------------

def test_score_too_high():
    with pytest.raises(ValueError, match="score"):
        DimensionResult.create(**_valid_kwargs(score=1.5))


def test_score_negative():
    with pytest.raises(ValueError, match="score"):
        DimensionResult.create(**_valid_kwargs(score=-0.1))


def test_score_boundaries():
    lo = DimensionResult.create(**_valid_kwargs(score=0.0))
    hi = DimensionResult.create(**_valid_kwargs(score=1.0))
    assert lo.score == 0.0
    assert hi.score == 1.0


# ---------------------------------------------------------------------------
# 3. Confidence validation
# ---------------------------------------------------------------------------

def test_confidence_too_high():
    with pytest.raises(ValueError, match="confidence"):
        DimensionResult.create(**_valid_kwargs(confidence=2.0))


def test_confidence_negative():
    with pytest.raises(ValueError, match="confidence"):
        DimensionResult.create(**_valid_kwargs(confidence=-0.01))


def test_confidence_boundaries():
    lo = DimensionResult.create(**_valid_kwargs(confidence=0.0))
    hi = DimensionResult.create(**_valid_kwargs(confidence=1.0))
    assert lo.confidence == 0.0
    assert hi.confidence == 1.0


# ---------------------------------------------------------------------------
# 4. Empty dimension rejection
# ---------------------------------------------------------------------------

def test_empty_dimension_rejected():
    with pytest.raises(ValueError, match="dimension"):
        DimensionResult.create(**_valid_kwargs(dimension=""))


def test_whitespace_dimension_rejected():
    with pytest.raises(ValueError, match="dimension"):
        DimensionResult.create(**_valid_kwargs(dimension="   "))


# ---------------------------------------------------------------------------
# 5. Evidence ID handling
# ---------------------------------------------------------------------------

def test_empty_evidence_id_entry_rejected():
    with pytest.raises(ValueError, match="evidence ID"):
        DimensionResult.create(
            **_valid_kwargs(supporting_evidence_ids=["ev-001", ""])
        )


def test_evidence_ids_normalized_to_tuple():
    dr = DimensionResult.create(
        **_valid_kwargs(supporting_evidence_ids=["a", "b"])
    )
    assert isinstance(dr.supporting_evidence_ids, tuple)
    assert dr.supporting_evidence_ids == ("a", "b")


# ---------------------------------------------------------------------------
# 6. Supporting / contradicting evidence
# ---------------------------------------------------------------------------

def test_supporting_and_contradicting_independent():
    dr = DimensionResult.create(
        **_valid_kwargs(
            supporting_evidence_ids=["s1", "s2"],
            contradicting_evidence_ids=["c1"],
        )
    )
    assert dr.supporting_evidence_ids == ("s1", "s2")
    assert dr.contradicting_evidence_ids == ("c1",)


def test_has_contradiction_property():
    with_c = DimensionResult.create(
        **_valid_kwargs(
            supporting_evidence_ids=["s1"],
            contradicting_evidence_ids=["c1"],
        )
    )
    without = DimensionResult.create(
        **_valid_kwargs(
            supporting_evidence_ids=["s1"],
            contradicting_evidence_ids=[],
        )
    )
    assert with_c.has_contradiction is True
    assert without.has_contradiction is False


# ---------------------------------------------------------------------------
# 7-9. Serialization, deserialization, round-trip
# ---------------------------------------------------------------------------

def test_to_dict_json_compatible():
    dr = DimensionResult.create(**_valid_kwargs())
    d = dr.to_dict()
    serialized = json.dumps(d)
    assert isinstance(serialized, str)
    assert d["dimension"] == "demand"
    assert d["score"] == 0.72
    assert d["supporting_evidence_ids"] == ["ev-001", "ev-002"]
    assert d["data_quality"]["evidence_count"] == 2


def test_from_dict_round_trip():
    dr = DimensionResult.create(**_valid_kwargs())
    restored = DimensionResult.from_dict(dr.to_dict())
    assert restored.dimension == dr.dimension
    assert restored.score == dr.score
    assert restored.confidence == dr.confidence
    assert restored.explanation == dr.explanation
    assert restored.supporting_evidence_ids == dr.supporting_evidence_ids
    assert restored.contradicting_evidence_ids == dr.contradicting_evidence_ids
    assert restored.trend == dr.trend
    assert restored.label == dr.label
    assert restored.flags == dr.flags
    assert restored.data_quality.evidence_count == dr.data_quality.evidence_count
    assert restored.data_quality.source_diversity == dr.data_quality.source_diversity


def test_round_trip_dict_equality():
    dr = DimensionResult.create(**_valid_kwargs())
    assert DimensionResult.from_dict(dr.to_dict()).to_dict() == dr.to_dict()


# ---------------------------------------------------------------------------
# 10. Deterministic / stable serialization
# ---------------------------------------------------------------------------

def test_stable_serialization_key_order():
    dr = DimensionResult.create(**_valid_kwargs())
    d1 = dr.to_dict()
    d2 = dr.to_dict()
    assert list(d1.keys()) == list(d2.keys())
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)


# ---------------------------------------------------------------------------
# 11. Trend
# ---------------------------------------------------------------------------

def test_all_trend_labels():
    for label in TrendLabel:
        dr = DimensionResult.create(**_valid_kwargs(trend=label))
        assert dr.trend == label.value


def test_trend_none_allowed():
    dr = DimensionResult.create(**_valid_kwargs(trend=None))
    assert dr.trend is None


# ---------------------------------------------------------------------------
# 12. DataQuality
# ---------------------------------------------------------------------------

def test_data_quality_defaults():
    dq = DataQuality()
    assert dq.evidence_count == 0
    assert dq.source_diversity == 0.0
    assert dq.temporal_coverage == "unknown"


def test_data_quality_validation():
    with pytest.raises(ValueError, match="source_diversity"):
        DataQuality(source_diversity=1.5)
    with pytest.raises(ValueError, match="evidence_count"):
        DataQuality(evidence_count=-1)


def test_data_quality_round_trip():
    dq = DataQuality(
        evidence_count=5,
        source_diversity=0.8,
        avg_reliability=0.7,
        avg_confidence=0.6,
        temporal_coverage="last_30d",
    )
    restored = DataQuality.from_dict(dq.to_dict())
    assert restored.to_dict() == dq.to_dict()


# ---------------------------------------------------------------------------
# 13. Flags
# ---------------------------------------------------------------------------

def test_flags_preserved():
    dr = DimensionResult.create(
        **_valid_kwargs(flags=["contradiction_present", "low_sample"])
    )
    assert dr.flags == ("contradiction_present", "low_sample")
    restored = DimensionResult.from_dict(dr.to_dict())
    assert restored.flags == ("contradiction_present", "low_sample")


# ---------------------------------------------------------------------------
# 14. Contradiction preservation (end-to-end)
# ---------------------------------------------------------------------------

def test_contradiction_preserved_through_round_trip():
    dr = DimensionResult.create(
        **_valid_kwargs(
            supporting_evidence_ids=["demand-up-001"],
            contradicting_evidence_ids=["sales-down-002"],
            flags=["contradiction_present"],
            explanation=(
                "Search interest is rising but sales-rank proxy is declining."
            ),
        )
    )
    assert dr.has_contradiction is True
    restored = DimensionResult.from_dict(dr.to_dict())
    assert restored.supporting_evidence_ids == ("demand-up-001",)
    assert restored.contradicting_evidence_ids == ("sales-down-002",)
    assert "contradiction_present" in restored.flags
    assert restored.has_contradiction is True


# ---------------------------------------------------------------------------
# Extra: opportunity_gap and competition archetypes remain expressible
# ---------------------------------------------------------------------------

def test_opportunity_gap_dimension():
    dr = DimensionResult.create(
        dimension=DimensionName.OPPORTUNITY_GAP,
        score=0.68,
        confidence=0.7,
        explanation="Recurring durability pain with mediocre incumbent ratings.",
        supporting_evidence_ids=["pain-1", "review-2"],
        label="quality_gap",
    )
    assert dr.dimension == "opportunity_gap"
    assert dr.label == "quality_gap"


def test_competition_not_automatically_negative():
    """High density + weak solutions can still score favourably."""
    dr = DimensionResult.create(
        dimension=DimensionName.COMPETITION,
        score=0.6,
        confidence=0.75,
        explanation=(
            "Crowded category but existing solutions have consistently "
            "poor ratings and unresolved pain themes."
        ),
        supporting_evidence_ids=["comp-density", "poor-ratings"],
        flags=["crowded_weak_solutions"],
    )
    assert dr.score == 0.6
    assert "crowded_weak_solutions" in dr.flags
