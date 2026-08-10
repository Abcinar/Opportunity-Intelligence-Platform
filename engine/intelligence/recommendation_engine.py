"""
Recommendation Engine

Generates deterministic founder-oriented recommendations for the
Opportunity Intelligence Platform (OIP).

This engine does not collect data or calculate scores.
It consumes signals already produced by previous intelligence engines.
"""

from typing import Any

from .base_engine import BaseEngine


class RecommendationEngine(BaseEngine):
    """Generate actionable recommendations from an enriched opportunity."""

    def process(self, opportunity: Any) -> Any:
        """
        Process an opportunity and attach a deterministic recommendation.

        The engine uses existing intelligence fields such as:
        - opportunity_score
        - confidence
        - founder_fit_score
        - founder_fit_level
        - category
        """

        recommendation = self._build_recommendation(opportunity)

        if isinstance(opportunity, dict):
            opportunity["recommendation"] = recommendation
            return opportunity

        setattr(opportunity, "recommendation", recommendation)
        return opportunity

    @staticmethod
    def _get(opportunity: Any, key: str, default: Any = None) -> Any:
        """Safely read a field from dicts or objects."""
        if isinstance(opportunity, dict):
            return opportunity.get(key, default)

        return getattr(opportunity, key, default)

    def _build_recommendation(self, opportunity: Any) -> dict[str, Any]:
        """Build a deterministic recommendation payload."""

        score = float(
            self._get(opportunity, "opportunity_score", 0.0) or 0.0
        )

        confidence = float(
            self._get(opportunity, "confidence", 0.0) or 0.0
        )

        founder_fit_score = float(
            self._get(opportunity, "founder_fit_score", 0.0) or 0.0
        )

        founder_fit_level = self._get(
            opportunity,
            "founder_fit_level",
            "Unknown",
        )

        category = self._get(
            opportunity,
            "category",
            "Unknown",
        )

        if score >= 80 and founder_fit_score >= 70:
            action = "HIGH_PRIORITY"
            recommendation = (
                "Strong opportunity. Validate the market quickly and "
                "consider building a focused MVP."
            )

        elif score >= 60 and founder_fit_score >= 60:
            action = "VALIDATE"
            recommendation = (
                "Promising opportunity. Run targeted customer and "
                "market validation before investing heavily."
            )

        elif confidence < 50:
            action = "MONITOR"
            recommendation = (
                "Insufficient confidence. Monitor additional signals "
                "before making a decision."
            )

        else:
            action = "RESEARCH"
            recommendation = (
                "Interesting signal. Research the problem, competitors "
                "and demand before taking action."
            )

        return {
            "action": action,
            "message": recommendation,
            "category": category,
            "founder_fit_level": founder_fit_level,
            "opportunity_score": round(score, 2),
            "confidence": round(confidence, 2),
            "founder_fit_score": round(founder_fit_score, 2),
        }


__all__ = ["RecommendationEngine"]
