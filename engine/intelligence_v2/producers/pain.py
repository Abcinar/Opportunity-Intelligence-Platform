"""
Pain dimension producer (Intelligence V2).

Source-agnostic. Privileges specificity / severity / repetition over raw volume.
Does not emit Opportunity Score. Does not mutate Evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from engine.dimension_result import DataQuality, DimensionResult
from engine.evidence import Evidence
from engine.intelligence_v2.aggregation import (
    aggregate_effective_score,
    effective_strength,
    evidence_ids,
    filter_by_types,
    separate_by_polarity,
    source_diversity_score,
)
from engine.intelligence_v2.base import empty_dimension_result

_PAIN_TYPES = (
    "pain_signal",
    "review_signal",
    "product_signal",
)

_SCORE_SOFT_CAP: float = 2.0

# Tokens that boost specificity / severity (language-agnostic-ish heuristics).
_SEVERITY_TOKENS = frozenset(
    {
        "crash",
        "crashes",
        "broken",
        "broke",
        "fail",
        "fails",
        "failed",
        "defect",
        "defective",
        "swell",
        "swelling",
        "fire",
        "burn",
        "unsafe",
        "refund",
        "return",
        "unusable",
        "never works",
        "still broken",
        "data loss",
        "lost data",
    }
)

_SPECIFICITY_MIN_LEN = 24  # short generic phrases get less weight


class PainProducer:
    """DimensionProducer for 'pain'."""

    @property
    def dimension_name(self) -> str:
        return "pain"

    def produce(
        self,
        evidence: Sequence[Evidence],
        context: Optional[Mapping[str, Any]] = None,
    ) -> DimensionResult:
        ctx = context or {}
        now = ctx.get("now")
        if not isinstance(now, datetime):
            now = datetime.now(timezone.utc)

        relevant = filter_by_types(list(evidence), _PAIN_TYPES)
        if not relevant:
            return empty_dimension_result(
                self.dimension_name,
                explanation="No pain-related evidence available.",
            )

        supporting, contradicting, _neutral = separate_by_polarity(
            relevant, positive_is_supporting=True
        )

        # Weight each supporting item by specificity/severity factor.
        support_mass = _weighted_mass(supporting, now=now)
        contra_mass = _weighted_mass(contradicting, now=now)

        net = max(0.0, support_mass - 0.5 * contra_mass)
        score = min(1.0, net / _SCORE_SOFT_CAP)

        diversity = source_diversity_score(relevant)
        avg_rel = _avg(relevant, "reliability")
        avg_conf = _avg(relevant, "confidence")

        # Repetition across sources boosts confidence more than volume alone.
        base_conf = (
            0.30 * avg_rel
            + 0.30 * avg_conf
            + 0.20 * min(1.0, len(supporting) / 3.0)
            + 0.20 * diversity
        )
        if supporting and contradicting:
            base_conf *= 0.75
        conf = max(0.0, min(1.0, base_conf))

        flags: list[str] = []
        if supporting and contradicting:
            flags.append("contradiction_present")
        if len(relevant) < 2:
            flags.append("low_sample")
        if _mostly_generic(supporting):
            flags.append("low_specificity")

        explanation = _explain(score, supporting, contradicting, diversity)

        return DimensionResult.create(
            dimension=self.dimension_name,
            score=score,
            confidence=conf,
            explanation=explanation,
            supporting_evidence_ids=evidence_ids(supporting),
            contradicting_evidence_ids=evidence_ids(contradicting),
            trend=None,
            label=None,
            data_quality=DataQuality(
                evidence_count=len(relevant),
                source_diversity=diversity,
                avg_reliability=avg_rel,
                avg_confidence=avg_conf,
                temporal_coverage=_temporal_coverage(relevant, now),
            ),
            flags=flags,
        )


def _specificity_factor(ev: Evidence) -> float:
    """
    Map text length + severity tokens + tags into a multiplier in [0.4, 1.35].

    Volume alone does not raise this factor.
    """
    text = (ev.signal or "").lower()
    factor = 0.7
    if len(text) >= _SPECIFICITY_MIN_LEN:
        factor += 0.2
    if len(text) >= 60:
        factor += 0.1
    if any(tok in text for tok in _SEVERITY_TOKENS):
        factor += 0.25
    tag_l = {t.lower() for t in ev.tags}
    if tag_l & {"severe", "1star", "defect", "durability", "crash"}:
        factor += 0.1
    return max(0.4, min(1.35, factor))


def _weighted_mass(
    items: Sequence[Evidence],
    *,
    now: datetime,
) -> float:
    """Sum of effective_strength * specificity_factor, with diversity via aggregation path."""
    if not items:
        return 0.0
    # Apply specificity by scaling a temporary view through aggregate on
    # effective strengths manually to keep source diminishing returns.
    from engine.intelligence_v2.aggregation import (
        family_contribution,
        group_by_source_family,
    )

    # Build per-item weighted strength, then reuse family diminishing returns.
    groups = group_by_source_family(items)
    total = 0.0
    for family in sorted(groups.keys()):
        weighted = [
            effective_strength(ev, now=now) * _specificity_factor(ev)
            for ev in groups[family]
        ]
        # Inline diminishing returns (same expo as aggregation)
        from engine.intelligence_v2.aggregation import diminishing_returns_sum

        total += diminishing_returns_sum(weighted)
    return total


def _mostly_generic(items: Sequence[Evidence]) -> bool:
    if not items:
        return False
    factors = [_specificity_factor(ev) for ev in items]
    return sum(1 for f in factors if f < 0.85) >= max(1, len(factors) // 2)


def _avg(items: Sequence[Evidence], attr: str) -> float:
    if not items:
        return 0.0
    return sum(float(getattr(ev, attr)) for ev in items) / float(len(items))


def _temporal_coverage(items: Sequence[Evidence], now: datetime) -> str:
    ages: list[float] = []
    for ev in items:
        if ev.timestamp is None:
            continue
        ts = ev.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ages.append(abs((now - ts).total_seconds()) / 86400.0)
    if not ages:
        return "unknown"
    span = max(ages) - min(ages) if len(ages) > 1 else max(ages)
    if span <= 7:
        return "last_7d"
    if span <= 30:
        return "last_30d"
    if span <= 90:
        return "last_90d"
    return "broad"


def _explain(
    score: float,
    supporting: Sequence[Evidence],
    contradicting: Sequence[Evidence],
    diversity: float,
) -> str:
    parts = [
        f"Pain score={score:.2f} from {len(supporting)} supporting "
        f"and {len(contradicting)} contradicting evidence item(s)."
    ]
    if _mostly_generic(supporting):
        parts.append("Many signals lack specificity.")
    if diversity < 0.35 and supporting:
        parts.append("Source diversity is low.")
    if supporting and contradicting:
        parts.append("Contradictory pain signals are present.")
    return " ".join(parts)
