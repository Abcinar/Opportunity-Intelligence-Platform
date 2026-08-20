"""
OIP Intelligence V2 – aggregation helpers (Phase A).

Pure, deterministic, source-agnostic functions used by dimension producers.
Evidence objects are never mutated.

Numeric constants are centralized below and documented. They are starting
defaults chosen for monotonic, testable behaviour; they are not final
business weights (those belong to the Scorer / later tuning).
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional, Sequence

from engine.evidence import Evidence, Polarity


# ---------------------------------------------------------------------------
# Centralized constants (Phase A defaults – documented, not magic)
# ---------------------------------------------------------------------------

# Temporal decay rate λ in decay = exp(-λ * age_days).
# Default half-life ≈ ln(2)/λ ≈ 45 days when λ = 0.0154.
DEFAULT_DECAY_LAMBDA: float = 0.0154

# Ages at or below this (days) receive full weight (no decay).
DECAY_FLOOR_DAYS: float = 0.0

# Maximum age contribution considered for decay (caps extreme old evidence).
DECAY_AGE_CAP_DAYS: float = 3650.0  # ~10 years

# Diminishing-returns exponent for intra-source stacking.
# contribution_k = max_item * (1 / k ** DIVERSITY_EXPO) style soft stack.
# 0.5 ≈ square-root diminishing; higher → stronger penalty for duplicates.
DIVERSITY_EXPO: float = 0.5

# Minimum source-diversity score when at least one source is present.
MIN_DIVERSITY_SCORE: float = 0.0


# ---------------------------------------------------------------------------
# Temporal decay
# ---------------------------------------------------------------------------

def age_in_days(
    timestamp: Optional[datetime],
    *,
    now: Optional[datetime] = None,
    fallback_observed_at: Optional[datetime] = None,
) -> float:
    """
    Non-negative age in days.

    Preference: timestamp → fallback_observed_at → 0.0.
    Future timestamps clamp to 0.0 (zero/negative age handling).
    """
    ref = timestamp or fallback_observed_at
    if ref is None:
        return 0.0
    if now is None:
        now = datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = (now - ref).total_seconds() / 86400.0
    if delta < 0.0:
        return 0.0
    return min(delta, DECAY_AGE_CAP_DAYS)


def temporal_decay(
    age_days: float,
    *,
    lambda_: float = DEFAULT_DECAY_LAMBDA,
) -> float:
    """
    Decay factor in (0, 1].

    decay = exp(-λ * max(age_days, DECAY_FLOOR_DAYS))
    Monotonic non-increasing in age_days for λ > 0.
    """
    if lambda_ < 0.0:
        raise ValueError("lambda_ must be >= 0")
    age = max(float(age_days), DECAY_FLOOR_DAYS)
    if age > DECAY_AGE_CAP_DAYS:
        age = DECAY_AGE_CAP_DAYS
    return math.exp(-lambda_ * age)


def evidence_decay_factor(
    evidence: Evidence,
    *,
    now: Optional[datetime] = None,
    lambda_: float = DEFAULT_DECAY_LAMBDA,
) -> float:
    """Decay factor for one Evidence item (does not mutate Evidence)."""
    age = age_in_days(
        evidence.timestamp,
        now=now,
        fallback_observed_at=evidence.observed_at,
    )
    return temporal_decay(age, lambda_=lambda_)


# ---------------------------------------------------------------------------
# Effective strength
# ---------------------------------------------------------------------------

def effective_strength(
    evidence: Evidence,
    *,
    now: Optional[datetime] = None,
    lambda_: float = DEFAULT_DECAY_LAMBDA,
) -> float:
    """
    strength * reliability * confidence * decay_factor

    Result is in [0, 1] when inputs are valid Evidence.
    """
    decay = evidence_decay_factor(evidence, now=now, lambda_=lambda_)
    return float(evidence.strength) * float(evidence.reliability) * float(
        evidence.confidence
    ) * decay


# ---------------------------------------------------------------------------
# Source-family grouping
# ---------------------------------------------------------------------------

def source_family(evidence: Evidence) -> str:
    """
    Source-agnostic family key.

    Uses source.name only. No provider-specific branches.
    Empty name is not expected (Evidence validates non-empty).
    """
    return evidence.source.name.strip().lower()


def group_by_source_family(
    evidence_list: Sequence[Evidence],
) -> dict[str, list[Evidence]]:
    """Group Evidence items by source_family. Deterministic key set."""
    groups: dict[str, list[Evidence]] = defaultdict(list)
    for ev in evidence_list:
        groups[source_family(ev)].append(ev)
    return dict(groups)


# ---------------------------------------------------------------------------
# Source diversity / diminishing returns
# ---------------------------------------------------------------------------

def source_diversity_score(evidence_list: Sequence[Evidence]) -> float:
    """
    Diversity in [0, 1].

    Uses unique source families over total items:
      unique / max(len, 1)
    One family with many items → low diversity.
    Many families → high diversity.
    """
    if not evidence_list:
        return MIN_DIVERSITY_SCORE
    families = {source_family(ev) for ev in evidence_list}
    return len(families) / float(len(evidence_list))


def diminishing_returns_sum(
    values: Sequence[float],
    *,
    expo: float = DIVERSITY_EXPO,
) -> float:
    """
    Combine multiple non-negative contributions from the same family.

    Sort descending, then sum v_i / (i+1) ** expo.
    Deterministic given the same multiset of values.
    """
    if not values:
        return 0.0
    if expo < 0.0:
        raise ValueError("expo must be >= 0")
    ordered = sorted((max(0.0, float(v)) for v in values), reverse=True)
    total = 0.0
    for i, v in enumerate(ordered):
        total += v / ((i + 1) ** expo)
    return total


def family_contribution(
    evidence_list: Sequence[Evidence],
    *,
    now: Optional[datetime] = None,
    lambda_: float = DEFAULT_DECAY_LAMBDA,
    expo: float = DIVERSITY_EXPO,
) -> float:
    """
    Per-family contribution after effective strength + diminishing returns.
    """
    strengths = [
        effective_strength(ev, now=now, lambda_=lambda_) for ev in evidence_list
    ]
    return diminishing_returns_sum(strengths, expo=expo)


def aggregate_effective_score(
    evidence_list: Sequence[Evidence],
    *,
    now: Optional[datetime] = None,
    lambda_: float = DEFAULT_DECAY_LAMBDA,
    expo: float = DIVERSITY_EXPO,
) -> float:
    """
    Cross-family aggregate: sum of per-family contributions.

    Not normalized to [0,1] here; callers / dimension producers normalize.
    Deterministic for a fixed evidence multiset and now/lambda/expo.
    """
    groups = group_by_source_family(evidence_list)
    total = 0.0
    # Sort families for deterministic iteration
    for family in sorted(groups.keys()):
        total += family_contribution(
            groups[family], now=now, lambda_=lambda_, expo=expo
        )
    return total


# ---------------------------------------------------------------------------
# Supporting / contradicting separation helpers
# ---------------------------------------------------------------------------

def separate_by_polarity(
    evidence_list: Sequence[Evidence],
    *,
    positive_is_supporting: bool = True,
) -> tuple[list[Evidence], list[Evidence], list[Evidence]]:
    """
    Split into (supporting, contradicting, neutral).

    When positive_is_supporting=True (default for Demand-like dimensions):
      POSITIVE → supporting, NEGATIVE → contradicting, NEUTRAL → neutral.

    When False (e.g. some competition density views):
      NEGATIVE → supporting, POSITIVE → contradicting.

    Pure function; does not mutate Evidence.
    """
    supporting: list[Evidence] = []
    contradicting: list[Evidence] = []
    neutral: list[Evidence] = []

    for ev in evidence_list:
        if ev.polarity is Polarity.NEUTRAL:
            neutral.append(ev)
        elif ev.polarity is Polarity.POSITIVE:
            if positive_is_supporting:
                supporting.append(ev)
            else:
                contradicting.append(ev)
        elif ev.polarity is Polarity.NEGATIVE:
            if positive_is_supporting:
                contradicting.append(ev)
            else:
                supporting.append(ev)
        else:
            neutral.append(ev)

    return supporting, contradicting, neutral


def evidence_ids(evidence_list: Iterable[Evidence]) -> tuple[str, ...]:
    """Stable tuple of evidence_id values in input order."""
    return tuple(ev.evidence_id for ev in evidence_list)


def filter_by_types(
    evidence_list: Sequence[Evidence],
    types: Sequence[str],
) -> list[Evidence]:
    """
    Keep items whose evidence_type.value is in types.

    types are plain strings (EvidenceType values) for source-agnostic use.
    """
    allowed = {t for t in types}
    return [ev for ev in evidence_list if ev.evidence_type.value in allowed]
