#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Opportunity Intelligence Platform (OIP) – Production Dashboard V1.1.1.

Pure presentation layer. Loads pipeline outputs, normalises field names for
display, filters, visualises and exports. Contains zero business logic,
scoring, confidence calculation, recommendation or trend analysis.

Data sources (read-only):
    data/opportunities.json
    data/daily_signals.json
    (fallback: root-level opportunities.json / tracked_opportunities.json /
     daily_signals.json)

Missing files or missing Score/Confidence fields produce clear warnings.
The Dashboard never invents Opportunity Score or Confidence values.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION: str = "1.1.1"
APP_TITLE: str = "Opportunity Intelligence Platform"
APP_SHORT: str = "OIP"
PAGE_ICON: str = "🎯"

DATA_DIR: Path = Path("data")
PRIMARY_PATHS: Tuple[Path, ...] = (
    DATA_DIR / "opportunities.json",
    DATA_DIR / "daily_signals.json",
)
FALLBACK_PATHS: Tuple[Path, ...] = (
    Path("opportunities.json"),
    Path("tracked_opportunities.json"),
    Path("daily_signals.json"),
)

HIGH_CONFIDENCE_THRESHOLD: float = 75.0
CACHE_TTL_SECONDS: int = 60
LOG_DIR: Path = Path("logs")
LOG_FILE: str = "dashboard.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging() -> logging.Logger:
    """Configure application logging.

    Returns:
        Configured logger instance.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("oip.dashboard")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh = logging.FileHandler(LOG_DIR / LOG_FILE, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger


logger = setup_logging()

# ---------------------------------------------------------------------------
# Data loading (no business logic)
# ---------------------------------------------------------------------------


def load_json_safely(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    """Load a JSON file without raising.

    Args:
        path: Filesystem path.

    Returns:
        Tuple of (parsed object or None, error message or None).
    """
    if not path.is_file():
        return None, f"Dosya bulunamadı: `{path}`"
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), None
    except json.JSONDecodeError as exc:
        logger.error("JSON decode error in %s: %s", path, exc)
        return None, f"Geçersiz JSON: `{path.name}`"
    except OSError as exc:
        logger.error("I/O error reading %s: %s", path, exc)
        return None, f"Okuma hatası: `{path.name}`"


def extract_records(raw: Any) -> List[Dict[str, Any]]:
    """Extract a flat list of dict records from heterogeneous JSON shapes.

    Args:
        raw: Parsed JSON content.

    Returns:
        List of dictionaries (may be empty).
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("opportunities", "signals", "items", "data", "results"):
            candidate = raw.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        return [raw]
    return []


def _safe_str(value: Any, default: str = "") -> str:
    """Coerce a value to string safely.

    Args:
        value: Any input.
        default: Fallback when value is None or unusable.

    Returns:
        String representation or default.
    """
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return default
    text = str(value).strip()
    return text if text else default


def _safe_float(value: Any) -> Optional[float]:
    """Coerce a value to float; return None on failure.

    Args:
        value: Any input.

    Returns:
        Float or None.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_provider(rec: Dict[str, Any]) -> str:
    """Extract provider name from common field variants.

    Args:
        rec: Raw opportunity/signal dictionary.

    Returns:
        Provider name or \"unknown\".
    """
    for key in ("provider", "source", "provider_origin"):
        val = rec.get(key)
        if val is None:
            continue
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
        if isinstance(val, dict):
            name = val.get("name") or val.get("id")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return "unknown"


def normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility layer: map pipeline JSON fields to a stable display schema.

    This function performs field renaming and type coercion only.
    It never calculates Opportunity Score, Confidence, recommendations,
    trends or categories. Missing Score/Confidence remain None.

    display_score is a visual-only proxy used when the pipeline has not
    produced a real Score. It is NEVER presented as Opportunity Score.

    Args:
        rec: Raw dictionary from pipeline output.

    Returns:
        Normalised dictionary ready for DataFrame construction.
    """
    intel = rec.get("intelligence") if isinstance(rec.get("intelligence"), dict) else {}
    cat_block = intel.get("category") if isinstance(intel.get("category"), dict) else {}

    # Real Score / Confidence from pipeline (may be absent)
    score_block = rec.get("score") if isinstance(rec.get("score"), dict) else {}

    score = _safe_float(
        rec.get("opportunity_score")
        if rec.get("opportunity_score") is not None
        else score_block.get("overall_score")
    )

    confidence = _safe_float(
        rec.get("confidence")
        if rec.get("confidence") is not None
        else score_block.get("confidence")
    )

    engagement = _safe_float(
        rec.get("engagement") or rec.get("points") or rec.get("upvotes")
    )

    # display_score: real score if present, else engagement proxy, else 0.0
    # NEVER treated as Opportunity Score from the Intelligence Engine.
    display_score: float
    if score is not None:
        display_score = score
    elif engagement is not None and engagement > 0:
        display_score = round(min(100.0, max(0.0, (engagement ** 0.5) * 2.5)), 1)
    else:
        display_score = 0.0

    category = (
        _safe_str(rec.get("category"))
        or _safe_str(cat_block.get("primary_category"))
        or "unknown"
    )

    ts_raw = (
        rec.get("timestamp")
        or rec.get("collected_at")
        or rec.get("created_at")
        or ""
    )
    try:
        timestamp = pd.to_datetime(ts_raw, utc=True) if ts_raw else pd.NaT
    except (ValueError, TypeError, OverflowError):
        timestamp = pd.NaT

    reason_parts: List[str] = []
    trend = intel.get("trend_strength") if isinstance(intel.get("trend_strength"), dict) else {}
    if trend.get("trend_strength"):
        reason_parts.append(f"Trend: {trend.get('trend_strength')}")
    if cat_block.get("primary_category"):
        reason_parts.append(f"Category: {cat_block.get('primary_category')}")
    market = intel.get("market_type") if isinstance(intel.get("market_type"), dict) else {}
    if market.get("market_type"):
        reason_parts.append(f"Market: {market.get('market_type')}")

    return {
        "id": _safe_str(rec.get("id")),
        "title": _safe_str(rec.get("title") or rec.get("name"), "Untitled")[:400],
        "description": _safe_str(
            rec.get("summary") or rec.get("content") or rec.get("description")
        )[:600],
        "score": score,
        "display_score": display_score,
        "confidence": confidence,
        "provider": _extract_provider(rec),
        "category": category,
        "reason": " | ".join(reason_parts),
        "url": _safe_str(rec.get("url")),
        "status": _safe_str(rec.get("status") or rec.get("decision")),
        "timestamp": timestamp,
        "engagement": engagement if engagement is not None else 0,
        "has_real_score": score is not None,
        "has_real_confidence": confidence is not None,
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_all_data() -> Tuple[pd.DataFrame, List[str], Dict[str, int]]:
    """Load and normalise all available pipeline outputs.

    Returns:
        Tuple of (DataFrame, warning messages, stats dict).
    """
    warnings: List[str] = []
    records: List[Dict[str, Any]] = []
    stats = {
        "files_loaded": 0,
        "records_raw": 0,
        "missing_score": 0,
        "missing_confidence": 0,
    }

    for path in PRIMARY_PATHS + FALLBACK_PATHS:
        raw, err = load_json_safely(path)
        if err:
            if path in PRIMARY_PATHS:
                warnings.append(err)
            continue
        extracted = extract_records(raw)
        if extracted:
            records.extend(extracted)
            stats["files_loaded"] += 1
            logger.info("Loaded %d records from %s", len(extracted), path)

    stats["records_raw"] = len(records)

    empty_cols = [
        "id", "title", "description", "score", "display_score", "confidence",
        "provider", "category", "reason", "url", "status", "timestamp",
        "engagement", "has_real_score", "has_real_confidence",
    ]

    if not records:
        return pd.DataFrame(columns=empty_cols), warnings, stats

    normalised = [normalize_record(r) for r in records]
    df = pd.DataFrame(normalised)

    stats["missing_score"] = int((~df["has_real_score"]).sum())
    stats["missing_confidence"] = int((~df["has_real_confidence"]).sum())

    if "id" in df.columns and df["id"].ne("").any():
        df = (
            df.sort_values("display_score", ascending=False, na_position="last")
            .drop_duplicates(subset=["id"], keep="first")
            .reset_index(drop=True)
        )
    else:
        df = (
            df.drop_duplicates(subset=["title", "provider"], keep="first")
            .reset_index(drop=True)
        )

    return df, warnings, stats


# ---------------------------------------------------------------------------
# Filtering (presentation only)
# ---------------------------------------------------------------------------


def apply_filters(
    df: pd.DataFrame,
    min_display_score: float,
    providers: Sequence[str],
    search: str,
) -> pd.DataFrame:
    """Apply UI filters. No business logic.

    Args:
        df: Source DataFrame.
        min_display_score: Minimum display_score threshold.
        providers: Selected provider names (empty = all).
        search: Free-text search.

    Returns:
        Filtered DataFrame.
    """
    if df.empty:
        return df.copy()

    out = df.copy()

    # fillna(0) so that min_score=0 keeps every row (including pure 0.0)
    out = out[out["display_score"].fillna(0.0) >= min_display_score]

    if providers:
        out = out[out["provider"].isin(list(providers))]

    term = search.strip().lower()
    if term:
        mask = (
            out["title"].str.lower().str.contains(term, na=False)
            | out["description"].str.lower().str.contains(term, na=False)
            | out["provider"].str.lower().str.contains(term, na=False)
            | out["category"].str.lower().str.contains(term, na=False)
            | out["reason"].str.lower().str.contains(term, na=False)
        )
        out = out[mask]

    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def inject_css() -> None:
    """Inject dark-theme CSS."""
    st.markdown(
        """
        <style>
        .stApp { background-color: #0e1117; color: #e6edf3; }
        section[data-testid="stSidebar"] {
            background-color: #161b22; border-right: 1px solid #30363d;
        }
        div[data-testid="stMetric"] {
            background-color: #1c2128; border: 1px solid #30363d;
            border-radius: 10px; padding: 14px 18px;
        }
        div[data-testid="stMetric"] label { color: #8b949e !important; }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            color: #f0f6fc !important; font-weight: 600;
        }
        h1, h2, h3 { color: #f0f6fc !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(last_refresh: str, record_count: int) -> None:
    """Render page header."""
    status = "Operational" if record_count > 0 else "No data"
    colour = "#3fb950" if record_count > 0 else "#d29922"
    st.markdown(
        f"""
        <div style="display:flex;justify-content:space-between;align-items:center;
                    margin-bottom:1.2rem;flex-wrap:wrap;gap:10px;">
          <div>
            <h1 style="margin:0;font-size:1.8rem;">{PAGE_ICON} {APP_TITLE}</h1>
            <p style="margin:4px 0 0;color:#8b949e;">
              AI-powered startup opportunity intelligence
            </p>
          </div>
          <div style="text-align:right;font-size:0.9rem;color:#8b949e;">
            Last refresh · {last_refresh}<br>
            <span style="color:{colour};">●</span> {status}
            &nbsp;|&nbsp; v{VERSION}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df: pd.DataFrame) -> None:
    """Render KPI metric cards."""
    total = len(df)
    real_scores = df.loc[df["has_real_score"], "score"] if total else pd.Series(dtype=float)
    if len(real_scores) > 0:
        avg = float(real_scores.mean())
        avg_label = "Avg Score"
    else:
        avg = float(df["display_score"].mean()) if total else 0.0
        avg_label = "Avg Display Score"

    providers = int(df["provider"].nunique()) if total else 0
    high = 0
    if total and df["has_real_confidence"].any():
        high = int(
            (df.loc[df["has_real_confidence"], "confidence"] >= HIGH_CONFIDENCE_THRESHOLD).sum()
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Opportunities", f"{total:,}")
    c2.metric(avg_label, f"{avg:.1f}")
    c3.metric("Providers", f"{providers}")
    c4.metric("High Confidence", f"{high}")


def render_charts(df: pd.DataFrame) -> None:
    """Render distribution and timeline charts."""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Score Distribution")
        use_real = df["has_real_score"].any() if not df.empty else False
        plot_col = "score" if use_real else "display_score"
        label = "Score" if use_real else "Display Score (proxy)"
        if df.empty or df[plot_col].isna().all():
            st.info("Skor dağılımı için veri yok.")
        else:
            fig = px.histogram(
                df.dropna(subset=[plot_col]),
                x=plot_col,
                nbins=20,
                labels={plot_col: label},
                color_discrete_sequence=["#388bfd"],
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
                margin=dict(t=30, b=20, l=10, r=10),
            )
            st.plotly_chart(fig, use_container_width=True)
            if not use_real:
                st.caption(
                    "⚠ Display Score is a visual proxy only — "
                    "not Opportunity Score from the Intelligence Engine."
                )

    with col2:
        st.subheader("Provider Distribution")
        if df.empty:
            st.info("Provider dağılımı için veri yok.")
        else:
            counts = df["provider"].value_counts().reset_index()
            counts.columns = ["Provider", "Count"]
            fig = px.bar(
                counts,
                x="Provider",
                y="Count",
                color="Count",
                color_continuous_scale="Blues",
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
                margin=dict(t=30, b=20, l=10, r=10),
                xaxis_tickangle=-25,
            )
            st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Confidence Distribution")
        if df.empty or not df["has_real_confidence"].any():
            st.info("Pipeline henüz Confidence üretmemiş.")
        else:
            fig = px.histogram(
                df.dropna(subset=["confidence"]),
                x="confidence",
                nbins=20,
                color_discrete_sequence=["#3fb950"],
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
                margin=dict(t=30, b=20, l=10, r=10),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Timeline")
        if df.empty or df["timestamp"].isna().all():
            st.info("Zaman çizelgesi için geçerli timestamp verisi yok.")
        else:
            tl = (
                df.dropna(subset=["timestamp"])
                .assign(date=lambda x: x["timestamp"].dt.date)
                .groupby("date")
                .size()
                .reset_index(name="count")
                .sort_values("date")
            )
            fig = px.area(
                tl, x="date", y="count", color_discrete_sequence=["#a371f7"]
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
                margin=dict(t=30, b=20, l=10, r=10),
            )
            st.plotly_chart(fig, use_container_width=True)


def render_tables(df: pd.DataFrame) -> None:
    """Render top-N and full opportunity tables plus CSV export."""
    st.subheader("Top Opportunities")
    if df.empty:
        st.info("Henüz opportunity yok.")
    else:
        sort_col = "score" if df["has_real_score"].any() else "display_score"
        top = df.nlargest(10, sort_col)[
            [
                "title", "score", "display_score", "confidence", "provider",
                "category", "engagement", "url", "reason",
            ]
        ].copy()
        st.dataframe(
            top,
            use_container_width=True,
            hide_index=True,
            column_config={
                "title": st.column_config.TextColumn("Title", width="large"),
                "score": st.column_config.NumberColumn("Score (pipeline)", format="%.1f"),
                "display_score": st.column_config.NumberColumn("Display Score", format="%.1f"),
                "confidence": st.column_config.NumberColumn("Confidence", format="%.1f"),
                "url": st.column_config.LinkColumn("URL"),
            },
        )
        if not df["has_real_score"].any():
            st.caption(
                "⚠ Score (pipeline) is empty. Display Score is a visual proxy "
                "derived from engagement for charting only — it is NOT Opportunity Score."
            )

    st.divider()
    st.subheader("All Opportunities")
    if df.empty:
        st.info("Görüntülenecek kayıt yok.")
        return

    display = df[
        [
            "title", "score", "display_score", "confidence", "provider",
            "category", "status", "engagement", "timestamp", "url", "reason",
        ]
    ].copy()
    display["timestamp"] = display["timestamp"].apply(
        lambda x: x.strftime("%Y-%m-%d %H:%M") if pd.notna(x) else "—"
    )
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=420,
        column_config={
            "title": st.column_config.TextColumn("Title", width="medium"),
            "score": st.column_config.NumberColumn("Score (pipeline)", format="%.1f"),
            "display_score": st.column_config.NumberColumn("Display Score", format="%.1f"),
            "confidence": st.column_config.NumberColumn("Confidence", format="%.1f"),
            "url": st.column_config.LinkColumn("URL"),
        },
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Export CSV",
        data=csv_bytes,
        file_name=f"oip_opportunities_{ts}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Dashboard entry point: Load → Normalise → Filter → Visualise → Export."""
    st.set_page_config(
        page_title=f"{APP_SHORT} – {APP_TITLE}",
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    with st.sidebar:
        st.markdown(f"### {PAGE_ICON} {APP_SHORT} Controls")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        min_score = st.slider(
            "Minimum Display Score",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            help=(
                "Filters on Display Score (visual proxy). "
                "Real Opportunity Score is produced by the Intelligence Engine."
            ),
        )

        df_raw, load_warnings, stats = load_all_data()
        all_providers = (
            sorted(df_raw["provider"].dropna().unique().tolist())
            if not df_raw.empty
            else []
        )
        selected_providers = st.multiselect(
            "Provider Filter",
            options=all_providers,
            default=[],
            help="Leave empty to include all providers",
        )
        search_query = st.text_input(
            "Search",
            placeholder="Title, description, category…",
        )
        st.divider()
        st.caption(f"Files loaded: {stats['files_loaded']}")
        st.caption(f"Raw records: {stats['records_raw']}")
        st.caption(f"Missing Score: {stats['missing_score']}")
        st.caption(f"Missing Confidence: {stats['missing_confidence']}")
        st.caption(f"Version: {VERSION}")

    for msg in load_warnings:
        st.warning(msg)

    if stats["records_raw"] > 0 and stats["missing_score"] == stats["records_raw"]:
        st.warning(
            "Pipeline henüz Opportunity Score üretmemiş. "
            "Tabloda görünen Display Score yalnızca görselleştirme amaçlı bir proxy’dir "
            "ve gerçek AI Score değildir."
        )
    if stats["records_raw"] > 0 and stats["missing_confidence"] == stats["records_raw"]:
        st.warning(
            "Pipeline henüz Confidence üretmemiş. High Confidence KPI sıfır görünecektir."
        )

    df = apply_filters(df_raw, min_score, selected_providers, search_query)
    last_refresh = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    render_hero(last_refresh, len(df_raw))
    render_kpis(df)
    st.divider()
    render_charts(df)
    st.divider()
    render_tables(df)

    st.caption(
        f"{APP_TITLE} · Dashboard v{VERSION} · "
        f"{len(df_raw)} records loaded · filtered view: {len(df)}"
    )


if __name__ == "__main__":
    main()
