"""
Opportunity Intelligence Platform - Main Orchestration Layer
============================================================

Production-ready entry point that wires the existing engine modules
into a single deterministic pipeline.

Pipeline:

1. collect_signals()
2. normalize_posts()
3. calculate_momentum()
4. analyze_signals()
5. export (daily signals + opportunities)

Momentum is calculated before the Intelligence pipeline because
ScoreEngine consumes the momentum metric.

This file must never modify engine modules or invent new public APIs.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from engine.collector import collect_signals
from engine.normalizer import normalize_posts
from engine.momentum import calculate_momentum
from engine.intelligence.pipeline import analyze_signals
from engine.exporter import (
    save_daily_signals,
    save_opportunities,
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("opportunity_intelligence_platform")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_signals(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ensure every item is a non-empty dict with at least an 'id' or 'title'.

    Malformed records are dropped and a warning is logged.
    """

    valid: List[Dict[str, Any]] = []

    for idx, item in enumerate(signals):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict signal at index %d",
                idx,
            )
            continue

        if not (item.get("id") or item.get("title")):
            logger.warning(
                "Skipping signal without id/title at index %d",
                idx,
            )
            continue

        valid.append(item)

    return valid


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def run_collection() -> Dict[str, Any]:
    """Stage 1 – Collect raw signals from all configured sources."""

    logger.info("Stage 1/5 – Collecting signals")

    start = time.perf_counter()

    raw = collect_signals()

    elapsed = (time.perf_counter() - start) * 1000

    logger.info(
        "Collected %d signals from %s (%.1f ms)",
        raw.get("total_signals", 0),
        raw.get("sources", {}),
        elapsed,
    )

    return raw


def run_normalization(
    posts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Stage 2 – Normalize and de-duplicate signals."""

    logger.info(
        "Stage 2/5 – Normalizing %d posts",
        len(posts),
    )

    start = time.perf_counter()

    normalized = normalize_posts(posts)

    elapsed = (time.perf_counter() - start) * 1000

    logger.info(
        "Normalized to %d unique signals (%.1f ms)",
        len(normalized),
        elapsed,
    )

    return normalized


def run_momentum(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Stage 3 – Calculate momentum from historical signal snapshots.

    Momentum compares current engagement against the previous snapshot
    for the same signal ID.
    """

    logger.info(
        "Stage 3/5 – Calculating momentum for %d signals",
        len(signals),
    )

    start = time.perf_counter()

    enriched = calculate_momentum(signals)

    elapsed = (time.perf_counter() - start) * 1000

    logger.info(
        "Momentum calculation completed (%.1f ms)",
        elapsed,
    )

    return enriched


def run_intelligence(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Stage 4 – Run the rule-based Intelligence pipeline.

    The Intelligence pipeline is responsible for:
    - category
    - score
    - confidence
    - founder fit
    - recommendation
    """

    logger.info(
        "Stage 4/5 – Analyzing %d signals",
        len(signals),
    )

    start = time.perf_counter()

    enriched = analyze_signals(signals)

    elapsed = (time.perf_counter() - start) * 1000

    logger.info(
        "Intelligence analysis completed (%.1f ms)",
        elapsed,
    )

    return enriched


# ---------------------------------------------------------------------------
# Export stage
# ---------------------------------------------------------------------------

def run_export(
    daily_payload: Dict[str, Any],
    opportunities: List[Dict[str, Any]],
) -> None:
    """Stage 5 – Persist daily signals and opportunities."""

    logger.info("Stage 5/5 – Exporting results")

    if not isinstance(daily_payload, dict):
        raise ValueError("daily_payload must be a dict")

    if not isinstance(opportunities, list):
        raise ValueError("opportunities must be a list")

    save_daily_signals(daily_payload)
    save_opportunities(opportunities)

    logger.info(
        "Exported %d daily signals and %d opportunities",
        daily_payload.get("total_signals", 0),
        len(opportunities),
    )


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------

def print_summary(
    opportunities: List[Dict[str, Any]],
    total_runtime_ms: float,
) -> None:
    """Print a concise human-readable summary of the run."""

    decisions: Dict[str, int] = {}

    for opportunity in opportunities:
        recommendation = opportunity.get(
            "recommendation",
            {},
        )

        if isinstance(recommendation, dict):
            decision = recommendation.get(
                "action",
                "UNKNOWN",
            )
        else:
            decision = "UNKNOWN"

        decisions[decision] = decisions.get(decision, 0) + 1

    print("\n" + "=" * 60)
    print("  AI OPPORTUNITY HUNTER – RUN SUMMARY")
    print("=" * 60)

    print(
        f"  Total opportunities processed : "
        f"{len(opportunities)}"
    )

    print(
        f"  Total runtime                 : "
        f"{total_runtime_ms:,.0f} ms"
    )

    print("-" * 60)
    print("  Decision breakdown:")

    for decision, count in sorted(decisions.items()):
        print(
            f"    {decision:12s} : {count}"
        )

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """
    Orchestrate the full pipeline end-to-end.

    Returns
    -------
    int
        0 = success
        1 = failure
        130 = interrupted by user
    """

    pipeline_start = time.perf_counter()

    logger.info(
        "Opportunity Intelligence Platform started"
    )

    try:

        # ================================================================
        # 1. Collect
        # ================================================================

        raw = run_collection()

        posts = raw.get("posts", [])

        if not posts:
            logger.warning(
                "No posts returned from collectors – exiting early"
            )
            return 0

        # ================================================================
        # 2. Normalize
        # ================================================================

        normalized = run_normalization(posts)

        normalized = _validate_signals(normalized)

        if not normalized:
            logger.warning(
                "No valid signals after normalization – exiting"
            )
            return 0

        # ================================================================
        # 3. Momentum
        # ================================================================

        momentum_signals = run_momentum(normalized)

        # ================================================================
        # 4. Intelligence
        # ================================================================

        enriched = run_intelligence(momentum_signals)

        # Intelligence pipeline already produces:
        # - category
        # - opportunity score
        # - confidence
        # - founder fit
        # - recommendation

        opportunities = enriched

        # ================================================================
        # 5. Export
        # ================================================================

        daily_payload = {
            "fetched_at": raw.get("fetched_at"),
            "total_signals": len(momentum_signals),
            "sources": raw.get("sources", {}),
            "posts": momentum_signals,
        }

        run_export(
            daily_payload,
            opportunities,
        )

        # ================================================================
        # Summary
        # ================================================================

        total_ms = (
            time.perf_counter() - pipeline_start
        ) * 1000

        print_summary(
            opportunities,
            total_ms,
        )

        logger.info(
            "Pipeline finished successfully in %.1f ms",
            total_ms,
        )

        return 0

    except KeyboardInterrupt:
        logger.warning(
            "Interrupted by user (KeyboardInterrupt)"
        )
        return 130

    except Exception as exc:
        logger.exception(
            "Unhandled exception in pipeline: %s",
            exc,
        )
        return 1


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
