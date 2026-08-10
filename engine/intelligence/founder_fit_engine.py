"""
Founder Fit Intelligence Engine
================================

Evaluates how well an opportunity fits the target
founder profile of the Opportunity Intelligence Platform (OIP).
"""

from __future__ import annotations

from typing import Any
import re

from .base_engine import BaseEngine


class FounderFitEngine(BaseEngine):
    """Evaluate opportunity fit for solo founders and indie builders."""

    HIGH_FIT_KEYWORDS = {
        "saas",
        "micro saas",
        "automation",
        "ai",
        "artificial intelligence",
        "developer tool",
        "devtool",
        "api",
        "productivity",
        "workflow",
        "no-code",
        "low-code",
        "open source",
        "agent",
        "agents",
        "startup",
        "indie hacker",
        "solo founder",
        "small business",
    }

    LOW_FIT_KEYWORDS = {
        "hardware",
        "manufacturing",
        "biotech",
        "pharmaceutical",
        "deep infrastructure",
        "capital intensive",
        "semiconductor",
        "logistics",
        "mining",
        "real estate",
    }

    def process(self, opportunity: Any) -> Any:
        """Process an opportunity and attach founder-fit metadata."""

        text = self._extract_text(opportunity)

        high_fit_matches = self._find_matches(
            text,
            self.HIGH_FIT_KEYWORDS,
        )

        low_fit_matches = self._find_matches(
            text,
            self.LOW_FIT_KEYWORDS,
        )

        score = self._calculate_score(
            high_fit_matches,
            low_fit_matches,
        )

        self._set_value(opportunity, "founder_fit_score", score)
        self._set_value(
            opportunity,
            "founder_fit_level",
            self._fit_level(score),
        )
        self._set_value(
            opportunity,
            "founder_fit_matches",
            high_fit_matches,
        )
        self._set_value(
            opportunity,
            "founder_fit_risks",
            low_fit_matches,
        )

        return opportunity

    @staticmethod
    def _extract_text(opportunity: Any) -> str:
        """Build searchable text from common opportunity fields."""

        fields = (
            "title",
            "description",
            "summary",
            "category",
            "tags",
        )

        values: list[str] = []

        if isinstance(opportunity, dict):
            for field in fields:
                value = opportunity.get(field)

                if value is None:
                    continue

                if isinstance(value, (list, tuple, set)):
                    values.extend(str(item) for item in value)
                else:
                    values.append(str(value))
        else:
            for field in fields:
                value = getattr(opportunity, field, None)

                if value is None:
                    continue

                if isinstance(value, (list, tuple, set)):
                    values.extend(str(item) for item in value)
                else:
                    values.append(str(value))

        return " ".join(values).lower()

    @staticmethod
    def _find_matches(
        text: str,
        keywords: set[str],
    ) -> list[str]:
        """Return detected keywords using word-boundary matching."""

        matches: list[str] = []

        for keyword in keywords:
            pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"

            if re.search(pattern, text, flags=re.IGNORECASE):
                matches.append(keyword)

        return sorted(matches)

    @staticmethod
    def _calculate_score(
        high_fit_matches: list[str],
        low_fit_matches: list[str],
    ) -> float:
        """Calculate deterministic founder-fit score from 0 to 100."""

        score = 50.0
        score += min(len(high_fit_matches) * 10.0, 50.0)
        score -= min(len(low_fit_matches) * 15.0, 50.0)

        return max(0.0, min(100.0, round(score, 2)))

    @staticmethod
    def _fit_level(score: float) -> str:
        """Convert numeric score into a readable level."""

        if score >= 80:
            return "High"

        if score >= 60:
            return "Medium"

        if score >= 40:
            return "Neutral"

        return "Low"

    @staticmethod
    def _set_value(
        opportunity: Any,
        key: str,
        value: Any,
    ) -> None:
        """Set value on either a dictionary or an object."""

        if isinstance(opportunity, dict):
            opportunity[key] = value
        else:
            setattr(opportunity, key, value)
