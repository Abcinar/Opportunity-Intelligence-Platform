"""Tests for engine.intelligence_v2.aggregation (Phase A)."""

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
from engine.intelligence_v2.aggregation import (
    DEFAULT_DECAY_LAMBDA,
    aggregate_effective_score,
    age_in_days,
    diminishing_returns_sum,
    effective_strength,
    evidence_decay_factor,
    evidence_ids,
    filter_by_types,
    group_by_source_family,
    separate_by_polarity,
    source_diversity_score,
    source_family,
    temporal_decay,
)

NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


def _ev(
    *,
    eid: str = "e1",
    source_name: str = "github",
    strength: float = 0.8,
    reliability: float = 1.0,
    confidence: float = 1.0,
    polarity: Polarity = Polarity.POSITIVE,
    etype: EvidenceType = EvidenceType.DEMAND_SIGNAL,
    age_days: float = 0.0,
) -> Evidence:
    ts = NOW - timedelta(days=age_days)
    return Evidence.create(
        evidence_id=eid,
        evidence_type=etype,
        source=SourceRef(
            name=source_name,
            collector="test",
            collected_at=NOW,
        ),
        signal="test signal",
        strength=strength,
        reliability=reliability,
        confidence=confidence,
        polarity=polarity,
        provenance=Provenance(extraction_method="test"),
        raw_value={"v": 1},
        timestamp=ts,
        observed_at=NOW,
    )


# --- empty / valid ---

def test_empty_group_and_diversity():
    assert group_by_source_family([]) == {}
    assert source_diversity_score([]) == 0.0
    assert aggregate_effective_score([]) == 0.0


def test_valid_single_evidence_effective_strength():
    ev = _ev(strength=0.5, reliability=0.8, confidence=1.0, age_days=0)
    # decay ~ 1.0 at age 0
    assert effective_strength(ev, now=NOW) == pytest.approx(0.4, rel=1e-6)


# --- decay monotonicity ---

def test_decay_monotonicity():
    ages = [0, 1, 10, 45, 100, 365]
    factors = [temporal_decay(a) for a in ages]
    for i in range(len(factors) - 1):
        assert factors[i] >= factors[i + 1]


def test_decay_at_zero_is_one():
    assert temporal_decay(0.0) == pytest.approx(1.0)


def test_negative_age_clamped():
    # age_in_days with future timestamp → 0
    future = NOW + timedelta(days=5)
    assert age_in_days(future, now=NOW) == 0.0
    assert temporal_decay(-10.0) == pytest.approx(1.0)


def test_evidence_decay_does_not_mutate():
    ev = _ev(age_days=30)
    before = ev.strength
    _ = evidence_decay_factor(ev, now=NOW)
    assert ev.strength == before


def test_lambda_negative_raises():
    with pytest.raises(ValueError):
        temporal_decay(1.0, lambda_=-0.1)


# --- effective strength ---

def test_effective_strength_includes_decay():
    fresh = _ev(strength=1.0, reliability=1.0, confidence=1.0, age_days=0)
    old = _ev(
        eid="old",
        strength=1.0,
        reliability=1.0,
        confidence=1.0,
        age_days=45,
    )
    assert effective_strength(fresh, now=NOW) > effective_strength(old, now=NOW)


# --- source grouping ---

def test_source_family_and_grouping():
    a = _ev(eid="1", source_name="GitHub")
    b = _ev(eid="2", source_name="github")
    c = _ev(eid="3", source_name="amazon")
    assert source_family(a) == "github"
    groups = group_by_source_family([a, b, c])
    assert set(groups.keys()) == {"github", "amazon"}
    assert len(groups["github"]) == 2
    assert len(groups["amazon"]) == 1


# --- diversity ---

def test_diversity_single_source_low():
    items = [_ev(eid=str(i), source_name="same") for i in range(5)]
    assert source_diversity_score(items) == pytest.approx(1.0 / 5.0)


def test_diversity_many_sources_high():
    items = [_ev(eid=str(i), source_name=f"s{i}") for i in range(5)]
    assert source_diversity_score(items) == pytest.approx(1.0)


# --- diminishing returns / deterministic ---

def test_diminishing_returns_order_independent():
    v = [0.9, 0.5, 0.3]
    assert diminishing_returns_sum(v) == diminishing_returns_sum(list(reversed(v)))


def test_aggregate_deterministic():
    items = [
        _ev(eid="a", source_name="x", strength=0.9),
        _ev(eid="b", source_name="y", strength=0.7),
        _ev(eid="c", source_name="x", strength=0.4),
    ]
    s1 = aggregate_effective_score(items, now=NOW)
    s2 = aggregate_effective_score(list(reversed(items)), now=NOW)
    assert s1 == pytest.approx(s2)


# --- polarity separation ---

def test_separate_by_polarity_default():
    pos = _ev(eid="p", polarity=Polarity.POSITIVE)
    neg = _ev(eid="n", polarity=Polarity.NEGATIVE)
    neu = _ev(eid="u", polarity=Polarity.NEUTRAL)
    sup, con, neu_out = separate_by_polarity([pos, neg, neu])
    assert evidence_ids(sup) == ("p",)
    assert evidence_ids(con) == ("n",)
    assert evidence_ids(neu_out) == ("u",)


def test_separate_by_polarity_inverted():
    pos = _ev(eid="p", polarity=Polarity.POSITIVE)
    neg = _ev(eid="n", polarity=Polarity.NEGATIVE)
    sup, con, _ = separate_by_polarity(
        [pos, neg], positive_is_supporting=False
    )
    assert evidence_ids(sup) == ("n",)
    assert evidence_ids(con) == ("p",)


# --- filter / ids ---

def test_filter_by_types():
    d = _ev(eid="d", etype=EvidenceType.DEMAND_SIGNAL)
    p = _ev(eid="p", etype=EvidenceType.PAIN_SIGNAL)
    out = filter_by_types([d, p], ["demand_signal"])
    assert evidence_ids(out) == ("d",)


def test_default_lambda_positive():
    assert DEFAULT_DECAY_LAMBDA > 0.0
