"""
OIP Intelligence V2 – DimensionResult V1

Canonical contract for a single intelligence dimension output.
Designed in docs/INTELLIGENCE_V2_DIMENSIONS.md.
Compatible with Evidence Model V1 (engine/evidence.py).

Additive only. Does not modify intelligence.py, scorer.py,
recommender.py, dashboard.py, collectors, or normalizer.

Standard-library dataclasses; no new dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Union


# ---------------------------------------------------------------------------
# Controlled values
# ---------------------------------------------------------------------------

class DimensionName(str, Enum):
    """The ten Intelligence V2 dimensions (Task 03)."""

    DEMAND = "demand"
    PAIN = "pain"
    COMPETITION = "competition"
    OPPORTUNITY_GAP = "opportunity_gap"
    MARKET = "market"
    MOMENTUM = "momentum"
    NOVELTY = "novelty"
    FEASIBILITY = "feasibility"
    MONETIZATION = "monetization"
    FOUNDER_FIT = "founder_fit"


class TrendLabel(str, Enum):
    """Momentum / temporal direction labels."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    VOLATILE = "volatile"
    EMERGING = "emerging"


# ---------------------------------------------------------------------------
# DataQuality nested object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DataQuality:
    """Quality metadata for the evidence supporting a dimension."""

    evidence_count: int = 0
    source_diversity: float = 0.0
    avg_reliability: float = 0.0
    avg_confidence: float = 0.0
    temporal_coverage: str = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_count, int) or isinstance(self.evidence_count, bool):
            raise TypeError("evidence_count must be an int")
        if self.evidence_count < 0:
            raise ValueError("evidence_count must be >= 0")
        _clamp("source_diversity", self.source_diversity)
        _clamp("avg_reliability", self.avg_reliability)
        _clamp("avg_confidence", self.avg_confidence)
        if not isinstance(self.temporal_coverage, str) or not self.temporal_coverage.strip():
            raise ValueError("temporal_coverage must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_count": self.evidence_count,
            "source_diversity": self.source_diversity,
            "avg_reliability": self.avg_reliability,
            "avg_confidence": self.avg_confidence,
            "temporal_coverage": self.temporal_coverage,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DataQuality":
        return cls(
            evidence_count=int(data.get("evidence_count", 0)),
            source_diversity=float(data.get("source_diversity", 0.0)),
            avg_reliability=float(data.get("avg_reliability", 0.0)),
            avg_confidence=float(data.get("avg_confidence", 0.0)),
            temporal_coverage=str(data.get("temporal_coverage", "unknown")),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")


def _normalize_ids(ids: Optional[Sequence[str]]) -> tuple[str, ...]:
    if ids is None:
        return ()
    result = []
    for item in ids:
        s = str(item).strip()
        if not s:
            raise ValueError("evidence ID entries must be non-empty strings")
        result.append(s)
    return tuple(result)


def _normalize_flags(flags: Optional[Sequence[str]]) -> tuple[str, ...]:
    if flags is None:
        return ()
    return tuple(str(f) for f in flags)


def _parse_dimension(value: Union[DimensionName, str]) -> str:
    if isinstance(value, DimensionName):
        return value.value
    s = str(value).strip()
    if not s:
        raise ValueError("dimension must be a non-empty string")
    return s


def _parse_trend(
    value: Optional[Union[TrendLabel, str]],
) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, TrendLabel):
        return value.value
    s = str(value).strip()
    if not s:
        return None
    return s


# ---------------------------------------------------------------------------
# DimensionResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DimensionResult:
    """
    Output of one Intelligence V2 dimension analysis.

    score / confidence are independent [0, 1] floats.
    supporting_evidence_ids and contradicting_evidence_ids preserve
    contradictions explicitly; they are never silently merged.
    """

    dimension: str
    score: float
    confidence: float
    explanation: str
    supporting_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    contradicting_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    trend: Optional[str] = None
    label: Optional[str] = None
    data_quality: DataQuality = field(default_factory=DataQuality)
    flags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.dimension or not str(self.dimension).strip():
            raise ValueError("dimension must be a non-empty string")

        _clamp("score", self.score)
        _clamp("confidence", self.confidence)

        if not isinstance(self.explanation, str):
            raise TypeError("explanation must be a string")

        if not isinstance(self.data_quality, DataQuality):
            raise TypeError(
                f"data_quality must be DataQuality, got {type(self.data_quality).__name__}"
            )

        object.__setattr__(
            self, "supporting_evidence_ids", _normalize_ids(self.supporting_evidence_ids)
        )
        object.__setattr__(
            self,
            "contradicting_evidence_ids",
            _normalize_ids(self.contradicting_evidence_ids),
        )
        object.__setattr__(self, "flags", _normalize_flags(self.flags))

        if self.trend is not None and not isinstance(self.trend, str):
            raise TypeError("trend must be str or None")
        if self.label is not None and not isinstance(self.label, str):
            raise TypeError("label must be str or None")

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        dimension: Union[DimensionName, str],
        score: float,
        confidence: float,
        explanation: str,
        supporting_evidence_ids: Optional[Sequence[str]] = None,
        contradicting_evidence_ids: Optional[Sequence[str]] = None,
        trend: Optional[Union[TrendLabel, str]] = None,
        label: Optional[str] = None,
        data_quality: Optional[DataQuality] = None,
        flags: Optional[Sequence[str]] = None,
    ) -> "DimensionResult":
        """Build a DimensionResult with light normalization."""
        return cls(
            dimension=_parse_dimension(dimension),
            score=float(score),
            confidence=float(confidence),
            explanation=explanation,
            supporting_evidence_ids=_normalize_ids(supporting_evidence_ids),
            contradicting_evidence_ids=_normalize_ids(contradicting_evidence_ids),
            trend=_parse_trend(trend),
            label=label,
            data_quality=data_quality if data_quality is not None else DataQuality(),
            flags=_normalize_flags(flags),
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Stable, JSON-compatible dictionary."""
        return {
            "dimension": self.dimension,
            "score": self.score,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "trend": self.trend,
            "label": self.label,
            "data_quality": self.data_quality.to_dict(),
            "flags": list(self.flags),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DimensionResult":
        """Reconstruct from a dictionary produced by to_dict()."""
        dq_raw = data.get("data_quality")
        if isinstance(dq_raw, Mapping):
            dq = DataQuality.from_dict(dq_raw)
        elif dq_raw is None:
            dq = DataQuality()
        else:
            raise TypeError("data_quality must be a mapping or None")

        return cls(
            dimension=str(data["dimension"]),
            score=float(data["score"]),
            confidence=float(data["confidence"]),
            explanation=str(data.get("explanation", "")),
            supporting_evidence_ids=tuple(data.get("supporting_evidence_ids") or ()),
            contradicting_evidence_ids=tuple(
                data.get("contradicting_evidence_ids") or ()
            ),
            trend=data.get("trend"),
            label=data.get("label"),
            data_quality=dq,
            flags=tuple(data.get("flags") or ()),
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def has_contradiction(self) -> bool:
        """True when both supporting and contradicting evidence are present."""
        return bool(self.supporting_evidence_ids) and bool(
            self.contradicting_evidence_ids
        )
