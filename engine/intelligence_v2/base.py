"""
OIP Intelligence V2 – DimensionProducer contract (Phase A).

Minimal, source-agnostic protocol. Concrete producers (Demand, Pain, …)
are implemented in later phases.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from engine.dimension_result import DimensionResult
from engine.evidence import Evidence


@runtime_checkable
class DimensionProducer(Protocol):
    """
    Contract for one intelligence dimension.

    Input:
      evidence – sequence of Evidence (may be empty)
      context  – optional opaque mapping (entity focus, time window,
                 FounderProfile, etc.). Producers must tolerate None/empty.

    Output:
      DimensionResult for this producer's dimension.

    Producers must:
    - never mutate Evidence
    - never emit an Opportunity Score
    - remain source-agnostic (no provider-specific branches)
    - return a valid DimensionResult even for empty input
      (typically score=0, confidence=0, explanation stating insufficient data)
    """

    @property
    def dimension_name(self) -> str:
        """Canonical dimension key (e.g. 'demand', 'pain')."""
        ...

    def produce(
        self,
        evidence: Sequence[Evidence],
        context: Optional[Mapping[str, Any]] = None,
    ) -> DimensionResult:
        """Analyze evidence and return a DimensionResult."""
        ...


def empty_dimension_result(
    dimension: str,
    *,
    explanation: str = "Insufficient evidence.",
) -> DimensionResult:
    """
    Shared helper for empty / no-signal outcomes.

    Uses DimensionResult.create for validation.
    """
    from engine.dimension_result import DataQuality, DimensionResult

    return DimensionResult.create(
        dimension=dimension,
        score=0.0,
        confidence=0.0,
        explanation=explanation,
        supporting_evidence_ids=[],
        contradicting_evidence_ids=[],
        trend=None,
        label=None,
        data_quality=DataQuality(
            evidence_count=0,
            source_diversity=0.0,
            avg_reliability=0.0,
            avg_confidence=0.0,
            temporal_coverage="none",
        ),
        flags=["insufficient_evidence"],
    )
