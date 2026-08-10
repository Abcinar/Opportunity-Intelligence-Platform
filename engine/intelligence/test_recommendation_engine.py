"""
Tests for RecommendationEngine.

Covers:
- HIGH_PRIORITY
- VALIDATE
- MONITOR
- RESEARCH
- dict input
- object input
- recommendation payload integrity
"""

from dataclasses import dataclass

from engine.intelligence.recommendation_engine import RecommendationEngine


@dataclass
class Opportunity:
    opportunity_score: float = 0.0
    confidence: float = 0.0
    founder_fit_score: float = 0.0
    founder_fit_level: str = "Unknown"
    category: str = "Unknown"


def test_high_priority():
    engine = RecommendationEngine()

    opportunity = {
        "opportunity_score": 85,
        "confidence": 80,
        "founder_fit_score": 75,
        "founder_fit_level": "High",
        "category": "AI SaaS",
    }

    result = engine.process(opportunity)

    assert result["recommendation"]["action"] == "HIGH_PRIORITY"


def test_validate():
    engine = RecommendationEngine()

    opportunity = {
        "opportunity_score": 65,
        "confidence": 70,
        "founder_fit_score": 65,
        "founder_fit_level": "Medium",
        "category": "Automation",
    }

    result = engine.process(opportunity)

    assert result["recommendation"]["action"] == "VALIDATE"


def test_monitor():
    engine = RecommendationEngine()

    opportunity = {
        "opportunity_score": 40,
        "confidence": 30,
        "founder_fit_score": 40,
        "founder_fit_level": "Low",
        "category": "Developer Tools",
    }

    result = engine.process(opportunity)

    assert result["recommendation"]["action"] == "MONITOR"


def test_research():
    engine = RecommendationEngine()

    opportunity = {
        "opportunity_score": 50,
        "confidence": 70,
        "founder_fit_score": 40,
        "founder_fit_level": "Low",
        "category": "Marketplace",
    }

    result = engine.process(opportunity)

    assert result["recommendation"]["action"] == "RESEARCH"


def test_dict_input_preserves_existing_fields():
    engine = RecommendationEngine()

    opportunity = {
        "title": "AI SaaS Tool",
        "opportunity_score": 85,
        "confidence": 90,
        "founder_fit_score": 80,
        "founder_fit_level": "High",
        "category": "AI",
    }

    result = engine.process(opportunity)

    assert result["title"] == "AI SaaS Tool"
    assert result["category"] == "AI"
    assert "recommendation" in result


def test_object_input():
    engine = RecommendationEngine()

    opportunity = Opportunity(
        opportunity_score=85,
        confidence=90,
        founder_fit_score=80,
        founder_fit_level="High",
        category="AI",
    )

    result = engine.process(opportunity)

    assert result.recommendation["action"] == "HIGH_PRIORITY"


def test_recommendation_payload():
    engine = RecommendationEngine()

    opportunity = {
        "opportunity_score": 82.456,
        "confidence": 76.789,
        "founder_fit_score": 74.321,
        "founder_fit_level": "High",
        "category": "AI SaaS",
    }

    result = engine.process(opportunity)
    recommendation = result["recommendation"]

    assert recommendation["action"] == "HIGH_PRIORITY"
    assert recommendation["category"] == "AI SaaS"
    assert recommendation["founder_fit_level"] == "High"
    assert recommendation["opportunity_score"] == 82.46
    assert recommendation["confidence"] == 76.79
    assert recommendation["founder_fit_score"] == 74.32
    assert "message" in recommendation


if __name__ == "__main__":
    print("RecommendationEngine tests ready.")
