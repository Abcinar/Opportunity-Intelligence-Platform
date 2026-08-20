"""
Focused tests for the OIP Evidence Model V1.

Covers:
1. valid Evidence creation
2. invalid strength
3. invalid reliability
4. invalid confidence
5. missing required fields
6. serialization
7. deserialization
8. deterministic ID
9. round-trip equality
10. provenance preservation
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from engine.evidence import (
    Evidence,
    EvidenceType,
    Polarity,
    Provenance,
    SourceRef,
    compute_evidence_id,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def _source(**kwargs: Any) -> SourceRef:
    defaults = {
        "name": "github_trending",
        "collector": "collector.github",
        "collected_at": NOW,
        "url": "https://github.com/trending",
    }
    defaults.update(kwargs)
    return SourceRef(**defaults)


def _provenance(**kwargs: Any) -> Provenance:
    defaults = {
        "extraction_method": "api_field",
        "pipeline_stage": "collector",
        "rule_id": "stars_v1",
        "model_version": None,
        "raw_observation_id": "obs-001",
    }
    defaults.update(kwargs)
    return Provenance(**defaults)


def _valid_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "evidence_type": EvidenceType.DEMAND_SIGNAL,
        "source": _source(),
        "signal": "Star count increased by 120 in 7 days",
        "strength": 0.75,
        "reliability": 0.90,
        "confidence": 0.95,
        "polarity": Polarity.POSITIVE,
        "provenance": _provenance(),
        "raw_value": {"stars_delta": 120, "window_days": 7},
        "normalized_value": 0.72,
        "timestamp": NOW,
        "observed_at": NOW,
        "tags": ["stars", "velocity"],
        "related_entities": ["repo:example/project"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Valid creation
# ---------------------------------------------------------------------------

def test_valid_evidence_creation():
    ev = Evidence.create(**_valid_kwargs())
    assert ev.evidence_id
    assert ev.evidence_type is EvidenceType.DEMAND_SIGNAL
    assert ev.source.name == "github_trending"
    assert ev.signal.startswith("Star count")
    assert ev.strength == 0.75
    assert ev.reliability == 0.90
    assert ev.confidence == 0.95
    assert ev.polarity is Polarity.POSITIVE
    assert ev.normalized_value == 0.72
    assert ev.tags == ("stars", "velocity")
    assert ev.related_entities == ("repo:example/project",)
    assert isinstance(ev.provenance, Provenance)


def test_create_accepts_string_enums():
    ev = Evidence.create(
        **_valid_kwargs(
            evidence_type="pain_signal",
            polarity="negative",
        )
    )
    assert ev.evidence_type is EvidenceType.PAIN_SIGNAL
    assert ev.polarity is Polarity.NEGATIVE


# ---------------------------------------------------------------------------
# 2-4. Invalid quality axes
# ---------------------------------------------------------------------------

def test_invalid_strength_too_high():
    with pytest.raises(ValueError, match="strength"):
        Evidence.create(**_valid_kwargs(strength=1.5))


def test_invalid_strength_negative():
    with pytest.raises(ValueError, match="strength"):
        Evidence.create(**_valid_kwargs(strength=-0.1))


def test_invalid_reliability():
    with pytest.raises(ValueError, match="reliability"):
        Evidence.create(**_valid_kwargs(reliability=2.0))


def test_invalid_confidence():
    with pytest.raises(ValueError, match="confidence"):
        Evidence.create(**_valid_kwargs(confidence=-0.01))


def test_boundary_values_accepted():
    ev = Evidence.create(**_valid_kwargs(strength=0.0, reliability=1.0, confidence=0.0))
    assert ev.strength == 0.0
    assert ev.reliability == 1.0
    assert ev.confidence == 0.0


# ---------------------------------------------------------------------------
# 5. Missing / invalid required fields
# ---------------------------------------------------------------------------

def test_empty_evidence_id_rejected():
    with pytest.raises(ValueError, match="evidence_id"):
        Evidence(
            evidence_id="",
            evidence_type=EvidenceType.OTHER,
            source=_source(),
            signal="x",
            strength=0.5,
            reliability=0.5,
            confidence=0.5,
            polarity=Polarity.NEUTRAL,
            provenance=_provenance(),
        )


def test_empty_signal_rejected():
    with pytest.raises(ValueError, match="signal"):
        Evidence.create(**_valid_kwargs(signal=""))


def test_empty_source_name_rejected():
    with pytest.raises(ValueError, match="name"):
        _source(name="")


def test_empty_provenance_method_rejected():
    with pytest.raises(ValueError, match="extraction_method"):
        _provenance(extraction_method="")


# ---------------------------------------------------------------------------
# 6-7. Serialization / deserialization
# ---------------------------------------------------------------------------

def test_to_dict_is_json_compatible():
    ev = Evidence.create(**_valid_kwargs())
    d = ev.to_dict()
    serialized = json.dumps(d)
    assert isinstance(serialized, str)
    assert d["evidence_type"] == "demand_signal"
    assert d["polarity"] == "positive"
    assert d["source"]["name"] == "github_trending"
    assert d["provenance"]["extraction_method"] == "api_field"


def test_from_dict_round_trip():
    ev = Evidence.create(**_valid_kwargs())
    d = ev.to_dict()
    restored = Evidence.from_dict(d)
    assert restored.evidence_id == ev.evidence_id
    assert restored.evidence_type == ev.evidence_type
    assert restored.source.name == ev.source.name
    assert restored.signal == ev.signal
    assert restored.strength == ev.strength
    assert restored.reliability == ev.reliability
    assert restored.confidence == ev.confidence
    assert restored.polarity == ev.polarity
    assert restored.raw_value == ev.raw_value
    assert restored.normalized_value == ev.normalized_value
    assert restored.tags == ev.tags
    assert restored.related_entities == ev.related_entities
    assert restored.provenance.extraction_method == ev.provenance.extraction_method
    assert restored.provenance.rule_id == ev.provenance.rule_id


# ---------------------------------------------------------------------------
# 8. Deterministic ID
# ---------------------------------------------------------------------------

def test_deterministic_id_same_inputs():
    kwargs = _valid_kwargs()
    ev1 = Evidence.create(**kwargs)
    ev2 = Evidence.create(**kwargs)
    assert ev1.evidence_id == ev2.evidence_id


def test_deterministic_id_changes_with_raw_value():
    ev1 = Evidence.create(**_valid_kwargs(raw_value={"a": 1}))
    ev2 = Evidence.create(**_valid_kwargs(raw_value={"a": 2}))
    assert ev1.evidence_id != ev2.evidence_id


def test_compute_evidence_id_direct():
    id1 = compute_evidence_id(
        evidence_type=EvidenceType.DEMAND_SIGNAL,
        source_name="github_trending",
        signal="test",
        raw_value=10,
        timestamp=NOW,
    )
    id2 = compute_evidence_id(
        evidence_type=EvidenceType.DEMAND_SIGNAL,
        source_name="github_trending",
        signal="test",
        raw_value=10,
        timestamp=NOW,
    )
    assert id1 == id2
    assert len(id1) == 64


def test_explicit_evidence_id_respected():
    ev = Evidence.create(**_valid_kwargs(evidence_id="custom-id-123"))
    assert ev.evidence_id == "custom-id-123"


# ---------------------------------------------------------------------------
# 9. Round-trip equality
# ---------------------------------------------------------------------------

def test_round_trip_field_equality():
    ev = Evidence.create(**_valid_kwargs())
    restored = Evidence.from_dict(ev.to_dict())
    assert restored.to_dict() == ev.to_dict()


# ---------------------------------------------------------------------------
# 10. Provenance preservation
# ---------------------------------------------------------------------------

def test_provenance_preserved():
    prov = _provenance(
        extraction_method="regex",
        rule_id="pain_v2",
        model_version="2026.08",
        raw_observation_id="raw-999",
        pipeline_stage="normalizer",
    )
    ev = Evidence.create(**_valid_kwargs(provenance=prov))
    d = ev.to_dict()
    restored = Evidence.from_dict(d)
    assert restored.provenance.extraction_method == "regex"
    assert restored.provenance.rule_id == "pain_v2"
    assert restored.provenance.model_version == "2026.08"
    assert restored.provenance.raw_observation_id == "raw-999"
    assert restored.provenance.pipeline_stage == "normalizer"


# ---------------------------------------------------------------------------
# Extra: e-commerce shaped evidence uses the same model
# ---------------------------------------------------------------------------

def test_ecommerce_shaped_evidence():
    """Amazon-style demand signal uses identical schema - no special fields."""
    src = _source(name="amazon", collector="collector.amazon", url=None)
    ev = Evidence.create(
        evidence_type=EvidenceType.DEMAND_SIGNAL,
        source=src,
        signal="Sales rank improved from 12400 to 3100",
        strength=0.82,
        reliability=0.90,
        confidence=0.95,
        polarity=Polarity.POSITIVE,
        provenance=_provenance(extraction_method="api_field", rule_id="rank_delta_v1"),
        raw_value={"rank_before": 12400, "rank_after": 3100},
        normalized_value=0.78,
        timestamp=NOW,
        observed_at=NOW,
        tags=["sales_rank", "home_kitchen"],
        related_entities=["B0XXXXXXX"],
    )
    assert ev.source.name == "amazon"
    assert ev.evidence_type is EvidenceType.DEMAND_SIGNAL
    assert Evidence.from_dict(ev.to_dict()).evidence_id == ev.evidence_id