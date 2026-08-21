"""
Competition dimension producer (Intelligence V2).

Source-agnostic: evaluates competition-like Evidence via Phase A aggregation.
Produces competition INTENSITY only (higher score = denser / stronger competition).
Does not emit Opportunity Score, does not invert score, does not mutate Evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from engine.dimension_result import DataQuality, DimensionResult, TrendLabel
from engine.evidence import Evidence
from engine.intelligence_v2.aggregation import (
    aggregate_effective_score,
    evidence_ids,
    filter_by_types,
    separate_by_polarity,
    source_diversity_score,
)
from engine.intelligence_v2.base import empty_dimension_result

_COMPETITION_TYPES = (
    "competitive_signal",
    "market_signal",
    "product_signal",
    "price_signal",
    "review_signal",
    "opportunity_gap",
    "trend_signal",
)

# Maps aggregate mass into [0, 1]. Not a Scorer business weight.
_SCORE_SOFT_CAP: float = 2.0


class CompetitionProducer:
    """DimensionProducer for 'competition' (intensity)."""

    @property
    def dimension_name(self) -> str:
        return "competition"

    def produce(
        self,
        evidence: Sequence[Evidence],
        context: Optional[Mapping[str, Any]] = None,
    ) -> DimensionResult:
        ctx = context or {}
        now = ctx.get("now")
        if not isinstance(now, datetime):
            now = datetime.now(timezone.utc)

        relevant = filter_by_types(list(evidence), _COMPETITION_TYPES)
        if not relevant:
            return empty_dimension_result(
                self.dimension_name,
                explanation="No competition-related evidence available.",
            )

        # positive_is_supporting=True:
        #   POSITIVE polarity → supports higher intensity
        #   NEGATIVE polarity → supports lower intensity (contradicts intensity)
        #   NEUTRAL → excluded from signed mass, kept for quality metrics
        supporting, contradicting, neutral = separate_by_polarity(
            relevant, positive_is_supporting=True
        )

        # effective_strength already includes temporal_decay; do not re-apply.
        # aggregate_effective_score applies group_by_source_family + diminishing_returns.
        support_score = aggregate_effective_score(supporting, now=now)
        contra_score = aggregate_effective_score(contradicting, now=now)

        # Net intensity: positive mass increases, negative mass decreases (half weight).
        # Neutral contributes zero to signed intensity.
        net = max(0.0, support_score - 0.5 * contra_score)
        score = min(1.0, net / _SCORE_SOFT_CAP)

        # Mild extra uncertainty when both sides are material and balanced.
        if supporting and contradicting:
            ratio = min(support_score, contra_score) / max(support_score, contra_score, 1e-9)
            if ratio > 0.4:
                # Limited penalty; never discard evidence.
                score = max(0.0, score * (1.0 - 0.15 * ratio))

        diversity = source_diversity_score(relevant)
        avg_rel = _avg(relevant, "reliability")
        avg_conf = _avg(relevant, "confidence")

        # Source diversity affects confidence / data_quality only, not the intensity score.
        base_conf = (
            0.35 * avg_rel
            + 0.35 * avg_conf
            + 0.30 * min(1.0, len(relevant) / 3.0)
        )
        conf = base_conf * (0.6 + 0.4 * diversity)
        if supporting and contradicting:
            conf *= 0.75
        conf = max(0.0, min(1.0, conf))

        trend = _infer_trend(supporting, contradicting, now=now)
        flags: list[str] = []
        if supporting and contradicting:
            flags.append("contradiction_present")
        if len(relevant) < 2:
            flags.append("low_sample")
        if diversity < 0.35 and (supporting or contradicting):
            flags.append("low_source_diversity")

        explanation = _explain(score, supporting, contradicting, neutral, diversity)

        return DimensionResult.create(
            dimension=self.dimension_name,
            score=score,
            confidence=conf,
            explanation=explanation,
            supporting_evidence_ids=evidence_ids(supporting),
            contradicting_evidence_ids=evidence_ids(contradicting),
            trend=trend,
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


def _avg(items: Sequence[Evidence], attr: str) -> float:
    if not items:
        return 0.0
    return sum(float(getattr(ev, attr)) for ev in items) / float(len(items))


def _infer_trend(
    supporting: Sequence[Evidence],
    contradicting: Sequence[Evidence],
    *,
    now: datetime,
) -> Optional[str]:
    if not supporting and not contradicting:
        return None
    s = aggregate_effective_score(supporting, now=now)
    c = aggregate_effective_score(contradicting, now=now)
    if s > 0 and c > 0 and min(s, c) / max(s, c) > 0.6:
        return TrendLabel.VOLATILE.value
    if s > c * 1.25:
        return TrendLabel.RISING.value
    if c > s * 1.25:
        return TrendLabel.FALLING.value
    if s > 0 or c > 0:
        return TrendLabel.STABLE.value
    return None


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
    neutral: Sequence[Evidence],
    diversity: float,
) -> str:
    parts = [
        f"Competition intensity={score:.2f} from {len(supporting)} intensity-supporting "
        f"and {len(contradicting)} intensity-reducing evidence item(s)"
    ]
    if neutral:
        parts.append(f"({len(neutral)} neutral item(s) excluded from signed mass).")
    else:
        parts.append(".")
    if diversity < 0.35 and (supporting or contradicting):
        parts.append("Source diversity is low.")
    if supporting and contradicting:
        parts.append("Contradictory competition signals are present.")
    return " ".join(parts)
