"""Focused tests for Pain dimension producer."""

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
from engine.intelligence_v2.producers.pain import PainProducer

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def _ev(
    *,
    eid: str,
    source: str = "github",
    strength: float = 0.8,
    reliability: float = 0.9,
    confidence: float = 0.9,
    polarity: Polarity = Polarity.POSITIVE,
    etype: EvidenceType = EvidenceType.PAIN_SIGNAL,
    age_days: float = 0.0,
    signal: str | None = None,
    tags: list[str] | None = None,
) -> Evidence:
    ts = NOW - timedelta(days=age_days)
    return Evidence.create(
        evidence_id=eid,
        evidence_type=etype,
        source=SourceRef(name=source, collector="test", collected_at=NOW),
        signal=signal or f"pain-{eid}",
        strength=strength,
        reliability=reliability,
        confidence=confidence,
        polarity=polarity,
        provenance=Provenance(extraction_method="test"),
        raw_value={"id": eid},
        timestamp=ts,
        observed_at=NOW,
        tags=tags or [],
    )


def test_dimension_name():
    assert PainProducer().dimension_name == "pain"


def test_empty_evidence():
    dr = PainProducer().produce([])
    assert dr.dimension == "pain"
    assert dr.score == 0.0
    assert dr.confidence == 0.0
    assert "insufficient_evidence" in dr.flags


def test_valid_pain():
    items = [
        _ev(eid="p1", strength=0.9, signal="app crashes on export every time"),
        _ev(eid="p2", source="forum", strength=0.7, signal="export still broken after update"),
    ]
    dr = PainProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert "p1" in dr.supporting_evidence_ids
    assert dr.data_quality.evidence_count >= 1


def test_volume_alone_not_enough():
    """Many weak/generic signals should not dominate a single specific strong pain."""
    weak = [
        _ev(eid=f"w{i}", source="same", strength=0.2, signal="meh")
        for i in range(8)
    ]
    specific = [
        _ev(
            eid="s1",
            source="reviews",
            strength=0.95,
            reliability=0.95,
            confidence=0.9,
            signal="battery swells and device shuts down after two weeks",
            tags=["severity", "severe"],
        )
    ]
    p = PainProducer()
    score_weak = p.produce(weak, context={"now": NOW}).score
    score_specific = p.produce(specific, context={"now": NOW}).score
    assert score_specific > score_weak


def test_mixed_polarity():
    items = [
        _ev(eid="hurt", polarity=Polarity.POSITIVE, strength=0.9),
        _ev(eid="resolved", polarity=Polarity.NEGATIVE, strength=0.7, source="changelog"),
    ]
    dr = PainProducer().produce(items, context={"now": NOW})
    assert "hurt" in dr.supporting_evidence_ids
    assert "resolved" in dr.contradicting_evidence_ids
    assert dr.has_contradiction is True


def test_irrelevant_types_ignored():
    items = [_ev(eid="d", etype=EvidenceType.DEMAND_SIGNAL, strength=1.0)]
    dr = PainProducer().produce(items, context={"now": NOW})
    assert dr.score == 0.0


def test_negative_review_type_accepted():
    items = [
        _ev(
            eid="r1",
            etype=EvidenceType.REVIEW_SIGNAL,
            polarity=Polarity.POSITIVE,
            strength=0.85,
            signal="1-star: product broke after one wash",
            tags=["1star", "defect"],
        )
    ]
    dr = PainProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert "r1" in dr.supporting_evidence_ids


def test_temporal_decay():
    fresh = [_ev(eid="f", strength=1.0, reliability=1.0, confidence=1.0, age_days=0)]
    old = [_ev(eid="o", strength=1.0, reliability=1.0, confidence=1.0, age_days=150)]
    p = PainProducer()
    assert p.produce(fresh, context={"now": NOW}).score > p.produce(
        old, context={"now": NOW}
    ).score


def test_source_diversity():
    single = [_ev(eid=str(i), source="only") for i in range(3)]
    multi = [
        _ev(eid="a", source="github"),
        _ev(eid="b", source="reddit"),
        _ev(eid="c", source="amazon"),
    ]
    p = PainProducer()
    assert p.produce(multi, context={"now": NOW}).confidence >= p.produce(
        single, context={"now": NOW}
    ).confidence


def test_deterministic():
    items = [_ev(eid="b"), _ev(eid="a", source="other")]
    p = PainProducer()
    d1 = p.produce(items, context={"now": NOW}).to_dict()
    d2 = p.produce(list(reversed(items)), context={"now": NOW}).to_dict()
    assert d1["score"] == d2["score"]
    assert set(d1["supporting_evidence_ids"]) == set(d2["supporting_evidence_ids"])


def test_no_mutation():
    ev = _ev(eid="m")
    s = ev.strength
    PainProducer().produce([ev], context={"now": NOW})
    assert ev.strength == s


def test_ecommerce_shaped_pain():
    items = [
        _ev(
            eid="amz1",
            source="amazon",
            etype=EvidenceType.REVIEW_SIGNAL,
            strength=0.9,
            signal="1-star: straps tore within a week of normal use",
            tags=["1star", "durability"],
        ),
        _ev(
            eid="etsy1",
            source="etsy",
            etype=EvidenceType.PAIN_SIGNAL,
            strength=0.75,
            signal="shipping delay of 6 weeks with no update",
            tags=["shipping"],
        ),
    ]
    dr = PainProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert set(dr.supporting_evidence_ids) >= {"amz1", "etsy1"}


def test_data_quality():
    items = [_ev(eid="x"), _ev(eid="y", source="hn")]
    dr = PainProducer().produce(items, context={"now": NOW})
    assert dr.data_quality.evidence_count == 2
    assert 0.0 <= dr.data_quality.source_diversity <= 1.0
