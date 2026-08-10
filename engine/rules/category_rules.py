"""
category_rules.py

Immutable keyword-to-taxonomy mappings for the
Opportunity Intelligence Platform (OIP).

This module contains only static classification rules.
No classes, functions or business logic are permitted.
All keywords are lowercase and unique within their scope.
Categories, subcategories and keywords are alphabetically ordered.
"""

from __future__ import annotations

__all__ = [
    "CATEGORY_RULES",
]

CATEGORY_RULES: dict[str, dict[str, list[str]]] = {
    "AI": {
        "AI Agents": [
            "agent",
            "autogen",
            "crewai",
            "langgraph",
            "multi-agent",
        ],
        "AI Automation": [
            "ai automation",
            "ai workflow",
            "ai-powered automation",
        ],
        "Generative AI": [
            "anthropic",
            "chatgpt",
            "claude",
            "gemini",
            "gpt",
            "llama",
            "llm",
            "mistral",
            "openai",
            "stable diffusion",
        ],
        "Machine Learning": [
            "ml",
            "model training",
            "pytorch",
            "scikit",
            "tensorflow",
        ],
    },
    "Creator Economy": {
        "Audience Monetization": [
            "fan funding",
            "membership",
            "patreon",
            "sponsorship",
            "tip jar",
        ],
        "Creator Platforms": [
            "beacons",
            "carrd",
            "linktree",
            "substack",
        ],
        "Subscription Tools": [
            "memberful",
            "recurring billing",
            "subscription box",
            "subscription management",
        ],
    },
    "Developer Tools": {
        "API Tools": [
            "api",
            "fastapi",
            "flask",
            "graphql",
            "openapi",
            "rest",
            "sdk",
            "swagger",
        ],
        "CI/CD": [
            "circleci",
            "github actions",
            "gitlab ci",
            "jenkins",
            "pipeline",
        ],
        "Testing": [
            "cypress",
            "jest",
            "playwright",
            "pytest",
            "unit test",
        ],
    },
    "Ecommerce": {
        "Amazon FBA": [
            "amazon",
            "fba",
            "fulfillment",
            "seller central",
        ],
        "Etsy": [
            "digital download",
            "etsy",
            "handmade",
            "printable",
        ],
        "Shopify": [
            "liquid",
            "shopify",
            "shopify app",
            "shopify plus",
            "woocommerce",
        ],
    },
    "Marketing": {
        "Email Marketing": [
            "convertkit",
            "drip",
            "email sequence",
            "klaviyo",
            "newsletter",
        ],
        "SEO": [
            "backlink",
            "keyword research",
            "on-page",
            "search ranking",
            "serp",
        ],
        "Social Media Marketing": [
            "content calendar",
            "hashtag",
            "instagram growth",
            "social scheduler",
            "tiktok ads",
        ],
    },
    "Productivity": {
        "Note-taking": [
            "evernote",
            "notion",
            "obsidian",
            "roam",
            "second brain",
        ],
        "Project Management": [
            "asana",
            "clickup",
            "jira",
            "monday",
            "project management",
            "trello",
        ],
        "Task Management": [
            "gtd",
            "kanban",
            "todo",
            "todoist",
            "workflowy",
        ],
    },
    "SaaS": {
        "B2B SaaS": [
            "b2b",
            "crm",
            "enterprise software",
            "erp",
            "saas platform",
            "subscription software",
        ],
        "Customer Success": [
            "churn",
            "customer health",
            "onboarding",
            "retention",
        ],
        "Vertical SaaS": [
            "industry specific",
            "niche software",
            "vertical market",
            "vertical saas",
        ],
    },
}
