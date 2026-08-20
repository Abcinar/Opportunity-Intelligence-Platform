"""
OIP Intelligence V2 package (Phase A).

Public API limited to symbols that exist in Phase A:
- DimensionProducer protocol
- empty_dimension_result helper
- aggregation helpers

Concrete dimension producers and orchestrator arrive in later phases.
This package is additive and does not alter the legacy pipeline.
"""

from engine.intelligence_v2.aggregation import (
    DEFAULT_DECAY_LAMBDA,
    DIVERSITY_EXPO,
    aggregate_effective_score,
    age_in_days,
    diminishing_returns_sum,
    effective_strength,
    evidence_decay_factor,
    evidence_ids,
    family_contribution,
    filter_by_types,
    group_by_source_family,
    separate_by_polarity,
    source_diversity_score,
    source_family,
    temporal_decay,
)
from engine.intelligence_v2.base import (
    DimensionProducer,
    empty_dimension_result,
)

__all__ = [
    # base
    "DimensionProducer",
    "empty_dimension_result",
    # aggregation constants
    "DEFAULT_DECAY_LAMBDA",
    "DIVERSITY_EXPO",
    # aggregation functions
    "age_in_days",
    "temporal_decay",
    "evidence_decay_factor",
    "effective_strength",
    "source_family",
    "group_by_source_family",
    "source_diversity_score",
    "diminishing_returns_sum",
    "family_contribution",
    "aggregate_effective_score",
    "separate_by_polarity",
    "evidence_ids",
    "filter_by_types",
]
