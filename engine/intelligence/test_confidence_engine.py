from engine.intelligence.confidence_engine import ConfidenceEngine


def test_github_complete_opportunity():
    engine = ConfidenceEngine()

    opportunity = {
        "title": "AI SaaS automation tool",
        "description": "Automation platform for solo founders",
        "source": "github",
    }

    result = engine.process(opportunity)

    assert result["confidence"] == 97.5
    assert result["confidence_level"] == "VERY_HIGH"


def test_reddit_complete_opportunity():
    engine = ConfidenceEngine()

    opportunity = {
        "title": "Creator automation tool",
        "description": "Tool for content creators",
        "source": "reddit",
    }

    result = engine.process(opportunity)

    assert result["confidence"] == 90.0
    assert result["confidence_level"] == "VERY_HIGH"


def test_unknown_source_complete_opportunity():
    engine = ConfidenceEngine()

    opportunity = {
        "title": "AI productivity tool",
        "description": "Productivity software",
        "source": "unknown_source",
    }

    result = engine.process(opportunity)

    assert result["confidence"] == 75.0
    assert result["confidence_level"] == "HIGH"


def test_missing_description_reduces_completeness():
    engine = ConfidenceEngine()

    opportunity = {
        "title": "AI automation tool",
        "source": "github",
    }

    result = engine.process(opportunity)

    assert result["confidence"] == 87.5
    assert result["confidence_level"] == "VERY_HIGH"


def test_missing_required_fields():
    engine = ConfidenceEngine()

    opportunity = {}

    result = engine.process(opportunity)

    assert result["confidence"] == 45.0
    assert result["confidence_level"] == "MEDIUM"


def test_max_current_github_confidence_is_very_high():
    engine = ConfidenceEngine()

    opportunity = {
        "title": "Complete opportunity",
        "description": "Complete description",
        "source": "github",
    }

    result = engine.process(opportunity)

    assert result["confidence"] == 97.5
    assert result["confidence_level"] == "VERY_HIGH"
