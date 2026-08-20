"""Tests for engine.intelligence_v2.base (Phase A)."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from engine.dimension_result import DimensionResult
from engine.evidence import Evidence
from engine.intelligence_v2.base import (
    DimensionProducer,
    empty_dimension_result,
)


class _StubProducer:
    """Minimal concrete producer satisfying the protocol."""

    @property
    def dimension_name(self) -> str:
        return "demand"

    def produce(
        self,
        evidence: Sequence[Evidence],
        context: Optional[Mapping[str, Any]] = None,
    ) -> DimensionResult:
        if not evidence:
            return empty_dimension_result(self.dimension_name)
        return DimensionResult.create(
            dimension=self.dimension_name,
            score=0.5,
            confidence=0.5,
            explanation="stub",
            supporting_evidence_ids=[e.evidence_id for e in evidence],
        )


def test_empty_dimension_result_shape():
    dr = empty_dimension_result("pain")
    assert dr.dimension == "pain"
    assert dr.score == 0.0
    assert dr.confidence == 0.0
    assert dr.supporting_evidence_ids == ()
    assert dr.contradicting_evidence_ids == ()
    assert "insufficient_evidence" in dr.flags
    assert dr.data_quality.evidence_count == 0


def test_empty_dimension_result_custom_explanation():
    dr = empty_dimension_result("market", explanation="No market signals.")
    assert dr.explanation == "No market signals."


def test_stub_producer_is_protocol_instance():
    producer = _StubProducer()
    assert isinstance(producer, DimensionProducer)


def test_stub_producer_empty_input():
    producer = _StubProducer()
    dr = producer.produce([])
    assert dr.dimension == "demand"
    assert dr.score == 0.0
    assert "insufficient_evidence" in dr.flags


def test_stub_producer_with_context_none():
    producer = _StubProducer()
    dr = producer.produce([], context=None)
    assert isinstance(dr, DimensionResult)


def test_protocol_dimension_name_property():
    producer = _StubProducer()
    assert producer.dimension_name == "demand"
