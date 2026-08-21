"""Focused tests for Market dimension producer (attractiveness)."""

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
from engine.intelligence_v2.producers.market import MarketProducer

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def _ev(
    *,
    eid: str,
    source: str = "github",
    strength: float = 0.8,
    reliability: float = 0.9,
    confidence: float = 0.9,
    polarity: Polarity = Polarity.POSITIVE,
    etype: EvidenceType = EvidenceType.MARKET_SIGNAL,
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
    assert MarketProducer().dimension_name == "market"


def test_empty_evidence():
    dr = MarketProducer().produce([])
    assert dr.dimension == "market"
    assert dr.score == 0.0
    assert dr.confidence == 0.0
    assert dr.supporting_evidence_ids == ()
    assert "insufficient_evidence" in dr.flags


def test_irrelevant_evidence_ignored():
    items = [
        _ev(eid="demand", etype=EvidenceType.DEMAND_SIGNAL, strength=1.0),
        _ev(eid="pain", etype=EvidenceType.PAIN_SIGNAL, strength=1.0),
        _ev(eid="comp", etype=EvidenceType.COMPETITIVE_SIGNAL, strength=1.0),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert dr.score == 0.0
    assert dr.supporting_evidence_ids == ()
    assert "insufficient_evidence" in dr.flags


def test_positive_market_evidence():
    items = [
        _ev(eid="m1", strength=0.9, polarity=Polarity.POSITIVE),
        _ev(
            eid="g1",
            source="trends",
            strength=0.75,
            polarity=Polarity.POSITIVE,
            etype=EvidenceType.GROWTH_SIGNAL,
        ),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert dr.confidence > 0.0
    assert "m1" in dr.supporting_evidence_ids
    assert "g1" in dr.supporting_evidence_ids
    assert dr.contradicting_evidence_ids == ()
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0
    assert dr.data_quality.evidence_count == 2


def test_negative_market_evidence():
    items = [
        _ev(eid="n1", strength=0.9, polarity=Polarity.NEGATIVE),
        _ev(
            eid="n2",
            source="reports",
            strength=0.8,
            polarity=Polarity.NEGATIVE,
            etype=EvidenceType.TREND_SIGNAL,
        ),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert dr.score == 0.0
    assert "n1" in dr.contradicting_evidence_ids
    assert "n2" in dr.contradicting_evidence_ids
    assert dr.supporting_evidence_ids == ()


def test_neutral_evidence_excluded_from_signed_mass():
    items = [
        _ev(eid="neu1", strength=1.0, polarity=Polarity.NEUTRAL),
        _ev(eid="neu2", source="other", strength=1.0, polarity=Polarity.NEUTRAL),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert dr.score == 0.0
    assert dr.supporting_evidence_ids == ()
    assert dr.contradicting_evidence_ids == ()
    assert dr.data_quality.evidence_count == 2
    assert dr.confidence > 0.0


def test_mixed_contradictory_evidence():
    items = [
        _ev(eid="up", polarity=Polarity.POSITIVE, strength=0.95, source="a"),
        _ev(eid="down", polarity=Polarity.NEGATIVE, strength=0.85, source="b"),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert "up" in dr.supporting_evidence_ids
    assert "down" in dr.contradicting_evidence_ids
    assert dr.has_contradiction is True
    assert "contradiction_present" in dr.flags
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0


def test_source_diversity_affects_confidence():
    single = [_ev(eid=str(i), source="same", strength=0.85) for i in range(3)]
    multi = [
        _ev(eid="a", source="amazon", strength=0.85),
        _ev(eid="b", source="etsy", strength=0.85),
        _ev(eid="c", source="shopify", strength=0.85),
    ]
    p = MarketProducer()
    c_single = p.produce(single, context={"now": NOW}).confidence
    c_multi = p.produce(multi, context={"now": NOW}).confidence
    assert c_multi >= c_single


def test_same_source_diminishing_returns():
    many_same = [
        _ev(eid=f"s{i}", source="same_provider", strength=0.9) for i in range(8)
    ]
    few_diverse = [
        _ev(eid="d1", source="amazon", strength=0.9),
        _ev(eid="d2", source="etsy", strength=0.9),
        _ev(eid="d3", source="shopify", strength=0.9),
    ]
    p = MarketProducer()
    s_many = p.produce(many_same, context={"now": NOW}).score
    s_few = p.produce(few_diverse, context={"now": NOW}).score
    assert 0.0 <= s_many <= 1.0
    assert s_few > 0.0
    even_more = many_same + [
        _ev(eid=f"extra{i}", source="same_provider", strength=0.9) for i in range(5)
    ]
    s_even = p.produce(even_more, context={"now": NOW}).score
    assert s_even == s_many


def test_temporal_decay_lowers_old_signal():
    fresh = [
        _ev(eid="f", strength=1.0, reliability=1.0, confidence=1.0, age_days=0)
    ]
    old = [
        _ev(eid="o", strength=1.0, reliability=1.0, confidence=1.0, age_days=120)
    ]
    p = MarketProducer()
    s_fresh = p.produce(fresh, context={"now": NOW}).score
    s_old = p.produce(old, context={"now": NOW}).score
    assert s_fresh > s_old


def test_ecommerce_shaped_evidence():
    items = [
        _ev(
            eid="cat_size",
            source="amazon",
            strength=0.9,
            etype=EvidenceType.MARKET_SIGNAL,
            polarity=Polarity.POSITIVE,
        ),
        _ev(
            eid="growth",
            source="amazon",
            strength=0.8,
            etype=EvidenceType.GROWTH_SIGNAL,
            polarity=Polarity.POSITIVE,
        ),
        _ev(
            eid="season",
            source="etsy",
            strength=0.7,
            etype=EvidenceType.SEASONALITY_SIGNAL,
            polarity=Polarity.POSITIVE,
        ),
        _ev(
            eid="review_mkt",
            source="shopify",
            strength=0.65,
            etype=EvidenceType.REVIEW_SIGNAL,
            polarity=Polarity.POSITIVE,
        ),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert dr.dimension == "market"
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0
    assert dr.data_quality.evidence_count == 4
    assert len(dr.supporting_evidence_ids) == 4


def test_dimension_result_contract():
    items = [_ev(eid="m1", strength=0.8)]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert dr.dimension == "market"
    assert isinstance(dr.score, float)
    assert isinstance(dr.confidence, float)
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0
    assert isinstance(dr.explanation, str)
    assert isinstance(dr.supporting_evidence_ids, tuple)
    assert isinstance(dr.contradicting_evidence_ids, tuple)
    assert isinstance(dr.flags, tuple)
    assert dr.data_quality.evidence_count >= 1


def test_score_confidence_bounds():
    items = [
        _ev(eid="x", strength=1.0, reliability=1.0, confidence=1.0),
        _ev(eid="y", source="other", strength=1.0, reliability=1.0, confidence=1.0),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0


def test_no_mutation():
    ev = _ev(eid="m", strength=0.5)
    before = ev.strength
    MarketProducer().produce([ev], context={"now": NOW})
    assert ev.strength == before


def test_deterministic_output():
    items = [
        _ev(eid="b", source="b"),
        _ev(eid="a", source="a"),
    ]
    p = MarketProducer()
    d1 = p.produce(items, context={"now": NOW}).to_dict()
    d2 = p.produce(list(reversed(items)), context={"now": NOW}).to_dict()
    assert d1["score"] == d2["score"]
    assert d1["confidence"] == d2["confidence"]
    assert set(d1["supporting_evidence_ids"]) == set(d2["supporting_evidence_ids"])


def test_evidence_ids_preserved():
    items = [
        _ev(eid="keep-me", strength=0.9),
        _ev(eid="also-keep", source="other", strength=0.7),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert "keep-me" in dr.supporting_evidence_ids
    assert "also-keep" in dr.supporting_evidence_ids


def test_data_quality_and_confidence():
    items = [
        _ev(eid="a", source="s1", strength=0.8, reliability=0.9, confidence=0.85),
        _ev(eid="b", source="s2", strength=0.7, reliability=0.8, confidence=0.8),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert dr.data_quality.evidence_count == 2
    assert dr.data_quality.source_diversity > 0.0
    assert 0.0 < dr.data_quality.avg_reliability <= 1.0
    assert 0.0 < dr.data_quality.avg_confidence <= 1.0
    assert dr.confidence > 0.0


def test_low_sample_flag():
    items = [_ev(eid="only-one", strength=0.9)]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert "low_sample" in dr.flags
    assert dr.data_quality.evidence_count == 1


def test_supporting_evidence_types():
    """Supporting types (trend, seasonality, review, product) are accepted."""
    items = [
        _ev(eid="t", etype=EvidenceType.TREND_SIGNAL, strength=0.8),
        _ev(eid="s", source="s2", etype=EvidenceType.SEASONALITY_SIGNAL, strength=0.7),
        _ev(eid="r", source="s3", etype=EvidenceType.REVIEW_SIGNAL, strength=0.75),
        _ev(eid="p", source="s4", etype=EvidenceType.PRODUCT_SIGNAL, strength=0.7),
    ]
    dr = MarketProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert dr.data_quality.evidence_count == 4
    assert len(dr.supporting_evidence_ids) == 4
