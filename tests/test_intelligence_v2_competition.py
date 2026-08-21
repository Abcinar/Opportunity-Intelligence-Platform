"""Focused tests for Competition dimension producer (intensity)."""

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
from engine.intelligence_v2.producers.competition import CompetitionProducer

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def _ev(
    *,
    eid: str,
    source: str = "github",
    strength: float = 0.8,
    reliability: float = 0.9,
    confidence: float = 0.9,
    polarity: Polarity = Polarity.POSITIVE,
    etype: EvidenceType = EvidenceType.COMPETITIVE_SIGNAL,
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
    assert CompetitionProducer().dimension_name == "competition"


def test_empty_evidence():
    dr = CompetitionProducer().produce([])
    assert dr.dimension == "competition"
    assert dr.score == 0.0
    assert dr.confidence == 0.0
    assert dr.supporting_evidence_ids == ()
    assert "insufficient_evidence" in dr.flags


def test_irrelevant_evidence_ignored():
    items = [
        _ev(eid="demand", etype=EvidenceType.DEMAND_SIGNAL, strength=1.0),
        _ev(eid="pain", etype=EvidenceType.PAIN_SIGNAL, strength=1.0),
    ]
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    assert dr.score == 0.0
    assert dr.supporting_evidence_ids == ()
    assert "insufficient_evidence" in dr.flags


def test_competitive_positive_evidence():
    items = [
        _ev(eid="c1", strength=0.9, polarity=Polarity.POSITIVE),
        _ev(
            eid="c2",
            source="marketplace",
            strength=0.7,
            polarity=Polarity.POSITIVE,
            etype=EvidenceType.MARKET_SIGNAL,
        ),
    ]
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert dr.confidence > 0.0
    assert "c1" in dr.supporting_evidence_ids
    assert "c2" in dr.supporting_evidence_ids
    assert dr.contradicting_evidence_ids == ()
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0
    assert dr.data_quality.evidence_count == 2


def test_competitive_negative_evidence():
    """Negative polarity reduces intensity (appears as contradicting)."""
    items = [
        _ev(eid="gap1", strength=0.9, polarity=Polarity.NEGATIVE),
        _ev(
            eid="gap2",
            source="reviews",
            strength=0.8,
            polarity=Polarity.NEGATIVE,
            etype=EvidenceType.OPPORTUNITY_GAP,
        ),
    ]
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    # No positive mass → net intensity near 0
    assert dr.score == 0.0
    assert "gap1" in dr.contradicting_evidence_ids
    assert "gap2" in dr.contradicting_evidence_ids
    assert dr.supporting_evidence_ids == ()


def test_neutral_evidence_excluded_from_signed_mass():
    items = [
        _ev(eid="n1", strength=1.0, polarity=Polarity.NEUTRAL),
        _ev(eid="n2", source="other", strength=1.0, polarity=Polarity.NEUTRAL),
    ]
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    assert dr.score == 0.0
    assert dr.supporting_evidence_ids == ()
    assert dr.contradicting_evidence_ids == ()
    # Neutral still counted in data quality
    assert dr.data_quality.evidence_count == 2
    assert dr.confidence > 0.0


def test_mixed_contradictory_evidence():
    items = [
        _ev(eid="strong", polarity=Polarity.POSITIVE, strength=0.95, source="a"),
        _ev(eid="weak", polarity=Polarity.NEGATIVE, strength=0.9, source="b"),
    ]
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    assert "strong" in dr.supporting_evidence_ids
    assert "weak" in dr.contradicting_evidence_ids
    assert dr.has_contradiction is True
    assert "contradiction_present" in dr.flags
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0


def test_multiple_source_families():
    items = [
        _ev(eid="a1", source="amazon", strength=0.8),
        _ev(eid="b1", source="etsy", strength=0.8),
        _ev(eid="c1", source="shopify", strength=0.8),
    ]
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    assert dr.score > 0.0
    assert dr.data_quality.source_diversity > 0.5
    assert len(dr.supporting_evidence_ids) == 3


def test_repeated_same_source_diminishing_returns():
    """Many items from one family should not unbounded-grow the score."""
    many_same = [
        _ev(eid=f"s{i}", source="same_provider", strength=0.9) for i in range(8)
    ]
    few_diverse = [
        _ev(eid="d1", source="amazon", strength=0.9),
        _ev(eid="d2", source="etsy", strength=0.9),
        _ev(eid="d3", source="shopify", strength=0.9),
    ]
    p = CompetitionProducer()
    s_many = p.produce(many_same, context={"now": NOW}).score
    s_few = p.produce(few_diverse, context={"now": NOW}).score
    # Score is always capped at 1.0; diminishing returns prevent unbounded growth
    assert 0.0 <= s_many <= 1.0
    # Diverse set of similar strength should be competitive
    assert s_few > 0.0
    # Adding more from the same family after saturation does not exceed 1.0
    even_more = many_same + [
        _ev(eid=f"extra{i}", source="same_provider", strength=0.9) for i in range(5)
    ]
    s_even = p.produce(even_more, context={"now": NOW}).score
    assert s_even == s_many  # already saturated / diminishing


def test_temporal_decay_lowers_old_signal():
    fresh = [
        _ev(
            eid="f",
            strength=1.0,
            reliability=1.0,
            confidence=1.0,
            age_days=0,
        )
    ]
    old = [
        _ev(
            eid="o",
            strength=1.0,
            reliability=1.0,
            confidence=1.0,
            age_days=120,
        )
    ]
    p = CompetitionProducer()
    s_fresh = p.produce(fresh, context={"now": NOW}).score
    s_old = p.produce(old, context={"now": NOW}).score
    assert s_fresh > s_old


def test_source_diversity_affects_confidence_not_score_directly():
    """Low diversity may lower confidence; intensity score still reflects mass."""
    single = [_ev(eid=str(i), source="same", strength=0.85) for i in range(3)]
    multi = [
        _ev(eid="a", source="amazon", strength=0.85),
        _ev(eid="b", source="etsy", strength=0.85),
        _ev(eid="c", source="shopify", strength=0.85),
    ]
    p = CompetitionProducer()
    dr_single = p.produce(single, context={"now": NOW})
    dr_multi = p.produce(multi, context={"now": NOW})
    # Confidence should prefer diversity
    assert dr_multi.confidence >= dr_single.confidence
    # Both should have positive intensity
    assert dr_single.score > 0.0
    assert dr_multi.score > 0.0


def test_ecommerce_shaped_evidence():
    """Amazon/Etsy-style competition signals use the same path."""
    items = [
        _ev(
            eid="rank",
            source="amazon",
            strength=0.9,
            etype=EvidenceType.COMPETITIVE_SIGNAL,
            polarity=Polarity.POSITIVE,
        ),
        _ev(
            eid="price",
            source="amazon",
            strength=0.7,
            etype=EvidenceType.PRICE_SIGNAL,
            polarity=Polarity.POSITIVE,
        ),
        _ev(
            eid="review_vs",
            source="etsy",
            strength=0.75,
            etype=EvidenceType.REVIEW_SIGNAL,
            polarity=Polarity.POSITIVE,
        ),
        _ev(
            eid="gap",
            source="shopify",
            strength=0.6,
            etype=EvidenceType.OPPORTUNITY_GAP,
            polarity=Polarity.NEGATIVE,
        ),
    ]
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    assert dr.dimension == "competition"
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0
    assert dr.data_quality.evidence_count == 4
    assert "rank" in dr.supporting_evidence_ids
    assert "gap" in dr.contradicting_evidence_ids


def test_dimension_result_contract():
    items = [_ev(eid="c1", strength=0.8)]
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    assert dr.dimension == "competition"
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
    dr = CompetitionProducer().produce(items, context={"now": NOW})
    assert 0.0 <= dr.score <= 1.0
    assert 0.0 <= dr.confidence <= 1.0


def test_no_mutation():
    ev = _ev(eid="m", strength=0.5)
    before = ev.strength
    CompetitionProducer().produce([ev], context={"now": NOW})
    assert ev.strength == before


def test_deterministic_output():
    items = [
        _ev(eid="b", source="b"),
        _ev(eid="a", source="a"),
    ]
    p = CompetitionProducer()
    d1 = p.produce(items, context={"now": NOW}).to_dict()
    d2 = p.produce(list(reversed(items)), context={"now": NOW}).to_dict()
    assert d1["score"] == d2["score"]
    assert d1["confidence"] == d2["confidence"]
    assert set(d1["supporting_evidence_ids"]) == set(d2["supporting_evidence_ids"])
