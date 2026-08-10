"""
pipeline.py

Orchestration layer for Intelligence Engines in the
Opportunity Intelligence Platform (OIP).

This module replaces the legacy analyze_signals() implementation.
It contains only sequencing logic; no business rules, scoring formulas
or recommendation logic belong here.
"""

from __future__ import annotations

from typing import Any

from .category_engine import CategoryEngine
from .score_engine import ScoreEngine
from .confidence_engine import ConfidenceEngine
from .founder_fit_engine import FounderFitEngine

__all__ = [
    "analyze_signal",
    "analyze_signals",
]

# ---------------------------------------------------------------------------
# Engine instances (created once)
# ---------------------------------------------------------------------------

_category_engine = CategoryEngine()
_score_engine = ScoreEngine()
_confidence_engine = ConfidenceEngine()
_founder_fit_engine = FounderFitEngine()
# TODO: _recommendation_engine = RecommendationEngine()

_ENGINES = (
    _category_engine,
    _score_engine,
    _confidence_engine,
    _founder_fit_engine,
)

# Future engines:
# - FounderFitEngine
# - RecommendationEngine


def analyze_signal(opportunity: Any) -> Any:
    """
    Run the full intelligence pipeline on a single opportunity.

    Order
    -----
    1. CategoryEngine
    2. ScoreEngine
    3. ConfidenceEngine
    4. FounderFitEngine
    5. RecommendationEngine (TODO)

    Parameters
    ----------
    opportunity : Any
        Opportunity instance (dict or object).

    Returns
    -------
    Any
        The enriched opportunity.
    """

    for engine in _ENGINES:
        opportunity = engine.process(opportunity)

    return opportunity


def analyze_signals(opportunities: list[Any]) -> list[Any]:
    """
    Run the intelligence pipeline on a list of opportunities.

    Parameters
    ----------
    opportunities : list[Any]
        List of opportunity instances.

    Returns
    -------
    list[Any]
        List of enriched opportunities.
    """

    return [analyze_signal(opportunity) for opportunity in opportunities]
