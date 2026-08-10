from engine.intelligence.category_engine import CategoryEngine


def classify(title: str) -> dict:
    engine = CategoryEngine()
    return engine.process({"title": title})


def test_saas_crm():
    result = classify("SaaS CRM platform for small businesses")

    assert result["category"] == "SaaS"
    assert result["subcategory"] == "B2B SaaS"
    assert "crm" in result["tags"]


def test_developer_api_tool():
    result = classify("GitHub developer API tool")

    assert result["category"] == "Developer Tools"
    assert result["subcategory"] == "API Tools"


def test_etsy_digital_products():
    result = classify("Etsy printable digital downloads")

    assert result["category"] == "Ecommerce"
    assert result["subcategory"] == "Etsy"


def test_seo_keyword_research():
    result = classify("SEO keyword research platform")

    assert result["category"] == "Marketing"
    assert result["subcategory"] == "SEO"


def test_ai_agent():
    result = classify("AI agent for developers")

    assert result["category"] == "AI"
    assert result["subcategory"] == "AI Agents"


def test_unknown_opportunity():
    result = classify("Random business opportunity with no clear category")

    assert result["category"] == "Unknown"
    assert result["subcategory"] == "Unknown"
    assert result["tags"] == []

def test_ai_automation():
    result = classify("AI automation tool for solo founders")

    assert result["category"] == "AI"
    assert result["subcategory"] == "AI Automation"
    assert "ai automation" in result["tags"]


def test_project_management_phrase():
    result = classify("Project management tool for remote teams")

    assert result["category"] == "Productivity"
    assert result["subcategory"] == "Project Management"
    assert "project management" in result["tags"]
