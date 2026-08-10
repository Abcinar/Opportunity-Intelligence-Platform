python - <<'PY'
from pathlib import Path

path = Path("engine/normalizer.py")

text = path.read_text()

# ------------------------------------------------------------
# 1. Canonical source mapping
# ------------------------------------------------------------

anchor = '''from typing import Dict, Any, List

'''

replacement = '''from typing import Dict, Any, List

# Canonical source names used across the Intelligence Platform.
SOURCE_ALIASES = {
    "github_trending": "github",
    "github": "github",
    "hacker_news": "hackernews",
    "hackernews": "hackernews",
    "reddit_posts": "reddit",
    "reddit": "reddit",
    "google_trends": "google_trends",
    "twitter": "twitter",
}

# Engagement normalization scale.
# Higher values produce diminishing returns instead of immediate saturation.
ENGAGEMENT_SCALE = 500.0

'''

if anchor not in text:
    raise SystemExit("Import bölümü bulunamadı.")

text = text.replace(anchor, replacement, 1)


# ------------------------------------------------------------
# 2. Add helper functions before normalize_post
# ------------------------------------------------------------

anchor = '''def normalize_post(post: Dict[str, Any]) -> Dict[str, Any]:
'''

helpers = '''def normalize_source(source: str) -> str:
    """Convert a raw source name into the platform canonical source name."""
    value = str(source or "").strip().lower()

    if not value:
        return "unknown"

    return SOURCE_ALIASES.get(value, value)


def normalize_engagement(value: Any) -> float:
    """
    Convert raw engagement into a deterministic 0-100 score.

    Uses diminishing returns so very large raw values do not
    immediately saturate the scoring engine.
    """
    try:
        raw_value = float(value)
    except (TypeError, ValueError):
        return 0.0

    if raw_value <= 0:
        return 0.0

    normalized = 100.0 * (
        raw_value / (raw_value + ENGAGEMENT_SCALE)
    )

    return round(min(normalized, 100.0), 2)


def normalize_post(post: Dict[str, Any]) -> Dict[str, Any]:
'''

if anchor not in text:
    raise SystemExit("normalize_post bulunamadı.")

text = text.replace(anchor, helpers, 1)


# ------------------------------------------------------------
# 3. Replace source normalization
# ------------------------------------------------------------

old = '''source = str(post.get("source") or "").strip()
    if not source:
        source = "unknown"
'''

new = '''source = normalize_source(post.get("source"))
'''

if old not in text:
    raise SystemExit("Source normalization bloğu bulunamadı.")

text = text.replace(old, new, 1)


# ------------------------------------------------------------
# 4. Replace engagement assignment
# ------------------------------------------------------------

old = '''    upvotes = points
    engagement = points
'''

new = '''    upvotes = points
    engagement = normalize_engagement(points)
'''

if old not in text:
    raise SystemExit("Engagement bloğu bulunamadı.")

text = text.replace(old, new, 1)


path.write_text(text)

print("Normalizer source canonicalization + engagement normalization eklendi.")
PY
