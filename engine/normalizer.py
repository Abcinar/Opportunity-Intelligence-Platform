"""
Opportunity Intelligence Platform
Normalizer Engine v2

Responsibilities
----------------
- Convert raw source records into a common signal model.
- Normalize engagement into a 0-100 score.
- Preserve real momentum data when a source provides it.
- Never invent momentum.
- Keep source-specific raw values available where useful.
- Remove duplicate signals deterministically.

Important
---------
If a source does not provide real momentum information,
momentum remains None.

The normalizer must not invent business intelligence.
"""

import hashlib
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Source normalization
# ---------------------------------------------------------------------------

SOURCE_ALIASES = {
    "github_trending": "github",
    "github": "github",
    "hacker_news": "hackernews",
    "hackernews": "hackernews",
    "reddit": "reddit",
    "lobsters": "lobsters",
    "product_hunt": "producthunt",
    "producthunt": "producthunt",
    "betalist": "betalist",
    "beta_list": "betalist",
    "google_trends": "google_trends",
}


def normalize_source(value: Any) -> str:
    """Normalize source names into the platform's canonical names."""
    source = str(value or "").strip().lower()

    if not source:
        return "unknown"

    return SOURCE_ALIASES.get(source, source)


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def generate_id(source: str, title: str) -> str:
    """
    Generate a deterministic ID from source + title.

    MD5 is used only as a deterministic identifier here;
    it is not used for security purposes.
    """
    s = str(source or "").strip()
    t = str(title or "").strip()

    raw_string = f"{s}_{t}"

    return hashlib.md5(
        raw_string.encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    """Convert a value to float safely."""
    try:
        if value is None:
            return None

        result = float(value)

        if not math.isfinite(result):
            return None

        return result

    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    """Convert a value to int safely."""
    result = _safe_float(value)

    if result is None:
        return 0

    return int(result)


def normalize_engagement(value: Any) -> float:
    """
    Convert a raw engagement value into a 0-100 scale.

    Uses a logarithmic-style saturation curve so that very large
    raw values do not immediately produce a score of 100.

    Examples:
        50   -> 9.09
        100  -> 16.67
        659  -> 56.86
        2655 -> 84.15
    """
    raw_value = _safe_float(value)

    if raw_value is None or raw_value <= 0:
        return 0.0

    normalized = (raw_value / (raw_value + 500.0)) * 100.0

    return round(
        max(0.0, min(100.0, normalized)),
        2,
    )


def normalize_momentum(value: Any) -> Optional[float]:
    """
    Normalize a real momentum value when one is provided.

    Momentum is intentionally NOT inferred from engagement.

    If the source does not provide momentum, return None.
    """
    raw_value = _safe_float(value)

    if raw_value is None:
        return None

    return round(
        max(0.0, min(100.0, raw_value)),
        2,
    )


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_summary(post: Dict[str, Any]) -> str:
    """Extract the best available textual summary."""
    value = (
        post.get("summary")
        or post.get("content")
        or post.get("description")
        or ""
    )

    return str(value).strip()


# ---------------------------------------------------------------------------
# Single post normalization
# ---------------------------------------------------------------------------

def normalize_post(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize one raw source record into the common signal model.
    """

    if not isinstance(post, dict):
        return {}

    source = normalize_source(post.get("source"))

    title = str(
        post.get("title") or ""
    ).strip()

    record_id = generate_id(
        source,
        title,
    )

    summary = _extract_summary(post)

    # ------------------------------------------------------------------
    # Engagement
    # ------------------------------------------------------------------

    raw_points = post.get("points")

    if raw_points is None:
        raw_points = post.get("score")

    if raw_points is None:
        raw_points = post.get("upvotes")

    points = _safe_int(raw_points)

    engagement = normalize_engagement(points)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    raw_comments = post.get("comments")

    if raw_comments is None:
        raw_comments = post.get("num_comments")

    comments = _safe_int(raw_comments)

    # ------------------------------------------------------------------
    # Momentum
    # ------------------------------------------------------------------
    #
    # IMPORTANT:
    # We only accept an explicit momentum field.
    #
    # We DO NOT do:
    #
    #     momentum = points
    #
    # because that would count the same signal twice.
    #
    # A future source/fetcher can provide:
    #
    #     momentum
    #     momentum_score
    #     growth
    #     growth_rate
    #
    # and the normalizer will preserve it.
    # ------------------------------------------------------------------

    raw_momentum = post.get("momentum")

    if raw_momentum is None:
        raw_momentum = post.get("momentum_score")

    if raw_momentum is None:
        raw_momentum = post.get("growth_rate")

    momentum = normalize_momentum(raw_momentum)

    # ------------------------------------------------------------------
    # Other fields
    # ------------------------------------------------------------------

    tags = post.get("tags")

    if not isinstance(tags, list):
        tags = []

    language = str(
        post.get("language") or "unknown"
    ).strip()

    url = str(
        post.get("url") or ""
    ).strip()

    collected_at = str(
        post.get("fetched_at")
        or post.get("collected_at")
        or datetime.now(timezone.utc).isoformat()
    ).strip()

    # ------------------------------------------------------------------
    # Preserve useful raw source metadata
    # ------------------------------------------------------------------

    metadata = {}

    if "stars_today" in post:
        metadata["stars_today"] = post["stars_today"]

    if "votes" in post:
        metadata["votes"] = post["votes"]

    if "growth" in post:
        metadata["growth"] = post["growth"]

    # ------------------------------------------------------------------
    # Common normalized signal
    # ------------------------------------------------------------------

    result = {
        "id": record_id,
        "title": title,
        "summary": summary,
        "content": summary,
        "source": source,
        "url": url,

        # Normalized 0-100 engagement
        "engagement": engagement,

        # Raw engagement values retained for traceability
        "points": points,
        "upvotes": points,
        "comments": comments,

        # Real momentum only; otherwise None
        "momentum": momentum,

        "category": str(
            post.get("category") or "unknown"
        ).strip(),

        "tags": tags,

        "language": language,

        "collected_at": collected_at,
    }

    if metadata:
        result["metadata"] = metadata

    return result


# ---------------------------------------------------------------------------
# Duplicate removal
# ---------------------------------------------------------------------------

def remove_duplicates(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Remove duplicate records deterministically.

    Duplicate identity is based on normalized source + title.
    """

    seen_ids = set()

    unique_signals: List[Dict[str, Any]] = []

    for post in signals:

        if not isinstance(post, dict):
            continue

        post_id = post.get("id")

        if not post_id:
            source = normalize_source(
                post.get("source")
            )

            title = str(
                post.get("title") or ""
            ).strip()

            post_id = generate_id(
                source,
                title,
            )

        if post_id in seen_ids:
            continue

        seen_ids.add(post_id)

        unique_signals.append(post)

    return unique_signals


# ---------------------------------------------------------------------------
# Batch normalization
# ---------------------------------------------------------------------------

def normalize_posts(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Normalize all source records and remove duplicates.
    """

    normalized_signals: List[Dict[str, Any]] = []

    for post in signals:

        if not isinstance(post, dict):
            continue

        normalized = normalize_post(post)

        if normalized:
            normalized_signals.append(
                normalized
            )

    return remove_duplicates(
        normalized_signals
    )
