"""Focused tests for Demand dimension producer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from engine.evidence import (
    Evidence,
    EvidenceType,
    Polarity,
    Provenance,
    SourceRef,
)
from engine.intelligence_v2.producers.demand import DemandProducer

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def _ev(
    *,
    eid: str,
    source: str = "github",
    strength: float = 0.8,
    reliability: float = 0.9,
    confidence: float = 0.9,
    polarity: Polarity = Polarity.POSITIVE,
    etype: EvidenceType = EvidenceType.DEMAND_SIGNAL,
    age_days: float = 0.0,
) -> Evidence:
    ts = NOW - timedelta(days=age_days)
    return Evidence.create(
        evidence_id=eid,
        evidence_type=etype,
        source=SourceRef(name=source, collector="test", collected_at=NOW),
        signal=f"signal-{eid}",
        strength=strength,
        reliability=reliability,
        confidence=confidence,
        polarity=polarity,
        provenance=Provenance(extraction_method="test"),
        raw_value={"id": eid},
        timestamp=ts,
        observed_at=NOW,
    )


def test_dimension_name():
    assert DemandProducer().dimension_name == "demand"


def test_empty_evidence():
    dr = DemandProducer().produce([])
    assert dr.dimension == "demand"
    assert dr.score == 0.0
    assert dr.confidence == 0.0
    assert dr.supporting_evidence_ids == ()
    assert "insufficient_evidence" in dr.flags


def test_valid_positive_demand():
    items = [
        _ev(eid="d1", strength=0.9),
        _ev(eid="d2", source="trends", strength=0.7, etype=EvidenceType.TREND_SIGNAL),
    ]
    dr = DemandProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert dr.confidence > 0.0
    assert "d1" in dr.supporting_evidence_ids
    assert "d2" in dr.supporting_evidence_ids
    assert dr.contradicting_evidence_ids == ()
    assert dr.data_quality.evidence_count >= 2


def test_mixed_polarity():
    items = [
        _ev(eid="up", polarity=Polarity.POSITIVE, strength=0.9),
        _ev(eid="down", polarity=Polarity.NEGATIVE, strength=0.8, source="amazon"),
    ]
    dr = DemandProducer().produce(items, context={"now": NOW})
    assert "up" in dr.supporting_evidence_ids
    assert "down" in dr.contradicting_evidence_ids
    assert dr.has_contradiction is True
    assert "contradiction_present" in dr.flags


def test_irrelevant_types_ignored():
    items = [
        _ev(eid="pain", etype=EvidenceType.PAIN_SIGNAL, strength=1.0),
    ]
    dr = DemandProducer().produce(items, context={"now": NOW})
    assert dr.score == 0.0
    assert dr.supporting_evidence_ids == ()


def test_temporal_decay_lowers_old_signal():
    fresh = [_ev(eid="f", strength=1.0, reliability=1.0, confidence=1.0, age_days=0)]
    old = [_ev(eid="o", strength=1.0, reliability=1.0, confidence=1.0, age_days=120)]
    p = DemandProducer()
    s_fresh = p.produce(fresh, context={"now": NOW}).score
    s_old = p.produce(old, context={"now": NOW}).score
    assert s_fresh > s_old


def test_source_diversity_affects_confidence():
    single = [
        _ev(eid=str(i), source="same", strength=0.8) for i in range(3)
    ]
    multi = [
        _ev(eid="a", source="github", strength=0.8),
        _ev(eid="b", source="trends", strength=0.8),
        _ev(eid="c", source="amazon", strength=0.8),
    ]
    p = DemandProducer()
    c_single = p.produce(single, context={"now": NOW}).confidence
    c_multi = p.produce(multi, context={"now": NOW}).confidence
    assert c_multi >= c_single


def test_deterministic_output():
    items = [
        _ev(eid="b", source="b"),
        _ev(eid="a", source="a"),
    ]
    p = DemandProducer()
    d1 = p.produce(items, context={"now": NOW}).to_dict()
    d2 = p.produce(list(reversed(items)), context={"now": NOW}).to_dict()
    assert d1["score"] == d2["score"]
    assert d1["confidence"] == d2["confidence"]
    assert set(d1["supporting_evidence_ids"]) == set(d2["supporting_evidence_ids"])


def test_no_mutation():
    ev = _ev(eid="m", strength=0.5)
    before = ev.strength
    DemandProducer().produce([ev], context={"now": NOW})
    assert ev.strength == before


def test_ecommerce_shaped_evidence():
    """Amazon-shaped demand uses same path — no provider branch."""
    items = [
        _ev(
            eid="rank",
            source="amazon",
            strength=0.85,
            etype=EvidenceType.DEMAND_SIGNAL,
            polarity=Polarity.POSITIVE,
        ),
        _ev(
            eid="vel",
            source="amazon",
            strength=0.7,
            etype=EvidenceType.GROWTH_SIGNAL,
        ),
    ]
    dr = DemandProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert "rank" in dr.supporting_evidence_ids
    assert dr.dimension == "demand"


def test_trend_label_present_when_signal():
    items = [_ev(eid="t1", strength=0.9, polarity=Polarity.POSITIVE)]
    dr = DemandProducer().produce(items, context={"now": NOW})
    assert dr.trend in ("rising", "stable", "falling", "volatile", "emerging", None)


def test_data_quality_fields():
    items = [_ev(eid="q1"), _ev(eid="q2", source="hn")]
    dr = DemandProducer().produce(items, context={"now": NOW})
    assert dr.data_quality.evidence_count == 2
    assert 0.0 <= dr.data_quality.source_diversity <= 1.0
    assert 0.0 <= dr.data_quality.avg_reliability <= 1.0
