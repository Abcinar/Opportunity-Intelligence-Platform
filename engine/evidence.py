"""
OIP Intelligence V2 – Evidence Model V1

Source-agnostic Evidence object as designed in docs/EVIDENCE_MODEL_DESIGN.md.
Compatible with docs/INTELLIGENCE_V2_DIMENSIONS.md.

This module is additive. It does not modify legacy pipeline contracts,
intelligence.py, scorer.py, recommender.py, dashboard.py, collectors,
or normalizer.py.

Representation: standard-library dataclasses (no new dependencies).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Union


# ---------------------------------------------------------------------------
# Controlled values (extensible)
# ---------------------------------------------------------------------------

class Polarity(str, Enum):
    """Semantic direction of contribution toward opportunity attractiveness."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class EvidenceType(str, Enum):
    """
    Controlled evidence types supporting both software/startup and
    e-commerce/product signals. Extensible: new members may be added
    without breaking existing consumers.
    """

    DEMAND_SIGNAL = "demand_signal"
    PAIN_SIGNAL = "pain_signal"
    COMPETITIVE_SIGNAL = "competitive_signal"
    MARKET_SIGNAL = "market_signal"
    PRODUCT_SIGNAL = "product_signal"
    PRICE_SIGNAL = "price_signal"
    REVIEW_SIGNAL = "review_signal"
    GROWTH_SIGNAL = "growth_signal"
    SEASONALITY_SIGNAL = "seasonality_signal"
    MARGIN_SIGNAL = "margin_signal"
    FEASIBILITY_SIGNAL = "feasibility_signal"
    TREND_SIGNAL = "trend_signal"
    OPPORTUNITY_GAP = "opportunity_gap"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Nested value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceRef:
    """Origin of an Evidence item. Provider-agnostic."""

    name: str
    collector: str
    collected_at: datetime
    url: Optional[str] = None
    region: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name or not str(self.name).strip():
            raise ValueError("SourceRef.name must be a non-empty string")
        if not self.collector or not str(self.collector).strip():
            raise ValueError("SourceRef.collector must be a non-empty string")
        if not isinstance(self.collected_at, datetime):
            raise TypeError("SourceRef.collected_at must be a datetime")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "collector": self.collector,
            "collected_at": _dt_to_iso(self.collected_at),
            "url": self.url,
            "region": self.region,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceRef":
        return cls(
            name=data["name"],
            collector=data["collector"],
            collected_at=_parse_datetime(data["collected_at"]),
            url=data.get("url"),
            region=data.get("region"),
        )


@dataclass(frozen=True)
class Provenance:
    """
    Traceability for an Evidence item.

    Records how the observation was extracted without embedding
    provider-specific fields on the main Evidence object.
    """

    extraction_method: str
    pipeline_stage: str = "collector"
    rule_id: Optional[str] = None
    model_version: Optional[str] = None
    raw_observation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.extraction_method or not str(self.extraction_method).strip():
            raise ValueError("Provenance.extraction_method must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "extraction_method": self.extraction_method,
            "pipeline_stage": self.pipeline_stage,
            "rule_id": self.rule_id,
            "model_version": self.model_version,
            "raw_observation_id": self.raw_observation_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Provenance":
        return cls(
            extraction_method=data["extraction_method"],
            pipeline_stage=data.get("pipeline_stage", "collector"),
            rule_id=data.get("rule_id"),
            model_version=data.get("model_version"),
            raw_observation_id=data.get("raw_observation_id"),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt_to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_datetime(value: Union[str, datetime]) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid datetime value: {value!r}")
    text = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _clamp_unit_interval(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")


def _normalize_tags(tags: Optional[Sequence[str]]) -> tuple[str, ...]:
    if tags is None:
        return ()
    return tuple(str(t) for t in tags)


def _normalize_entities(entities: Optional[Sequence[str]]) -> tuple[str, ...]:
    if entities is None:
        return ()
    return tuple(str(e) for e in entities)


def _json_safe(value: Any) -> Any:
    """Convert value to a JSON-serializable form (best-effort for raw_value)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return _dt_to_iso(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def compute_evidence_id(
    *,
    evidence_type: Union[EvidenceType, str],
    source_name: str,
    signal: str,
    raw_value: Any,
    timestamp: Optional[datetime],
) -> str:
    """
    Deterministic evidence_id.

    Strategy: SHA-256 over a canonical JSON payload of
    (evidence_type, source_name, signal, raw_value, timestamp_iso).
    Same logical observation -> same ID. No random UUIDs.
    """
    et = evidence_type.value if isinstance(evidence_type, EvidenceType) else str(evidence_type)
    ts = _dt_to_iso(timestamp) if timestamp is not None else ""
    payload = {
        "evidence_type": et,
        "source_name": source_name,
        "signal": signal,
        "raw_value": _json_safe(raw_value),
        "timestamp": ts,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """
    Atomic, source-agnostic unit of intelligence for OIP V2.

    strength    - magnitude of the observed phenomenon [0, 1]
    reliability - trustworthiness of source + collection method [0, 1]
    confidence  - certainty of extraction / interpretation [0, 1]

    These three axes are independent and must not be collapsed.
    """

    evidence_id: str
    evidence_type: EvidenceType
    source: SourceRef
    signal: str
    strength: float
    reliability: float
    confidence: float
    polarity: Polarity
    provenance: Provenance
    raw_value: Any = None
    normalized_value: Optional[Union[float, str]] = None
    timestamp: Optional[datetime] = None
    observed_at: Optional[datetime] = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    related_entities: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.evidence_id or not str(self.evidence_id).strip():
            raise ValueError("evidence_id must be a non-empty string")

        if not isinstance(self.evidence_type, EvidenceType):
            raise TypeError(
                f"evidence_type must be EvidenceType, got {type(self.evidence_type).__name__}"
            )

        if not isinstance(self.source, SourceRef):
            raise TypeError(f"source must be SourceRef, got {type(self.source).__name__}")

        if not self.signal or not str(self.signal).strip():
            raise ValueError("signal must be a non-empty string")

        _clamp_unit_interval("strength", self.strength)
        _clamp_unit_interval("reliability", self.reliability)
        _clamp_unit_interval("confidence", self.confidence)

        if not isinstance(self.polarity, Polarity):
            raise TypeError(f"polarity must be Polarity, got {type(self.polarity).__name__}")

        if not isinstance(self.provenance, Provenance):
            raise TypeError(
                f"provenance must be Provenance, got {type(self.provenance).__name__}"
            )

        if self.timestamp is not None and not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be datetime or None")
        if self.observed_at is not None and not isinstance(self.observed_at, datetime):
            raise TypeError("observed_at must be datetime or None")

        object.__setattr__(self, "tags", _normalize_tags(self.tags))
        object.__setattr__(self, "related_entities", _normalize_entities(self.related_entities))

    @classmethod
    def create(
        cls,
        *,
        evidence_type: Union[EvidenceType, str],
        source: SourceRef,
        signal: str,
        strength: float,
        reliability: float,
        confidence: float,
        polarity: Union[Polarity, str],
        provenance: Provenance,
        raw_value: Any = None,
        normalized_value: Optional[Union[float, str]] = None,
        timestamp: Optional[datetime] = None,
        observed_at: Optional[datetime] = None,
        tags: Optional[Sequence[str]] = None,
        related_entities: Optional[Sequence[str]] = None,
        evidence_id: Optional[str] = None,
    ) -> "Evidence":
        """
        Build an Evidence item.

        If evidence_id is omitted, a deterministic ID is computed from
        (evidence_type, source.name, signal, raw_value, timestamp).
        """
        if isinstance(evidence_type, EvidenceType):
            et = evidence_type
        else:
            et = EvidenceType(evidence_type)

        if isinstance(polarity, Polarity):
            pol = polarity
        else:
            pol = Polarity(polarity)

        if evidence_id:
            eid = evidence_id
        else:
            eid = compute_evidence_id(
                evidence_type=et,
                source_name=source.name,
                signal=signal,
                raw_value=raw_value,
                timestamp=timestamp,
            )

        return cls(
            evidence_id=eid,
            evidence_type=et,
            source=source,
            signal=signal,
            strength=float(strength),
            reliability=float(reliability),
            confidence=float(confidence),
            polarity=pol,
            provenance=provenance,
            raw_value=raw_value,
            normalized_value=normalized_value,
            timestamp=timestamp,
            observed_at=observed_at,
            tags=_normalize_tags(tags),
            related_entities=_normalize_entities(related_entities),
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-compatible dictionary."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "source": self.source.to_dict(),
            "signal": self.signal,
            "strength": self.strength,
            "reliability": self.reliability,
            "confidence": self.confidence,
            "polarity": self.polarity.value,
            "raw_value": _json_safe(self.raw_value),
            "normalized_value": self.normalized_value,
            "timestamp": _dt_to_iso(self.timestamp) if self.timestamp else None,
            "observed_at": _dt_to_iso(self.observed_at) if self.observed_at else None,
            "tags": list(self.tags),
            "related_entities": list(self.related_entities),
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Evidence":
        """Reconstruct Evidence from a dictionary produced by to_dict()."""
        ts_raw = data.get("timestamp")
        oa_raw = data.get("observed_at")
        return cls(
            evidence_id=data["evidence_id"],
            evidence_type=EvidenceType(data["evidence_type"]),
            source=SourceRef.from_dict(data["source"]),
            signal=data["signal"],
            strength=float(data["strength"]),
            reliability=float(data["reliability"]),
            confidence=float(data["confidence"]),
            polarity=Polarity(data["polarity"]),
            provenance=Provenance.from_dict(data["provenance"]),
            raw_value=data.get("raw_value"),
            normalized_value=data.get("normalized_value"),
            timestamp=_parse_datetime(ts_raw) if ts_raw else None,
            observed_at=_parse_datetime(oa_raw) if oa_raw else None,
            tags=tuple(data.get("tags") or ()),
            related_entities=tuple(data.get("related_entities") or ()),
        )