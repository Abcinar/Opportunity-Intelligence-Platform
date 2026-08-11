"""
Momentum Engine
===============

Opportunity Intelligence Platform

Görevi:
- Önceki sinyal snapshotlarını okumak
- Mevcut engagement ile karşılaştırmak
- Deterministik momentum değeri üretmek
- Yeni snapshotları kaydetmek

Bu modül:
- kategori sınıflandırmaz
- opportunity score hesaplamaz
- recommendation üretmez
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from engine.exporter import (
    load_signal_snapshots,
    save_signal_snapshots,
)


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """Değeri [0, 100] aralığında tutar."""
    return max(minimum, min(maximum, value))


def _read_engagement(signal: Dict[str, Any]) -> float:
    """Signal içindeki engagement değerini güvenli şekilde okur."""
    value = signal.get("engagement")

    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _calculate_momentum(
    previous_engagement: float,
    current_engagement: float,
) -> float | None:
    """
    Önceki ve mevcut engagement değerlerinden momentum hesaplar.

    Stabil sinyal:
        50

    Yükseliş:
        50 - 100

    Düşüş:
        0 - 50

    İlk kez görülen sinyal:
        None
    """
    if previous_engagement <= 0:
        return None

    change_percent = (
        (current_engagement - previous_engagement)
        / previous_engagement
    ) * 100.0

    momentum = 50.0 + (change_percent / 2.0)

    return round(_clamp(momentum), 2)


def calculate_momentum(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Tüm sinyaller için momentum hesaplar
    ve yeni snapshot oluşturur.
    """
    if not isinstance(signals, list):
        raise ValueError("signals must be a list")

    previous_snapshots = load_signal_snapshots()

    previous_by_id: Dict[str, Dict[str, Any]] = {}

    for snapshot in previous_snapshots:
        if not isinstance(snapshot, dict):
            continue

        signal_id = snapshot.get("id")

        if signal_id:
            previous_by_id[str(signal_id)] = snapshot

    new_snapshots: List[Dict[str, Any]] = []

    for signal in signals:
        if not isinstance(signal, dict):
            continue

        signal_id = signal.get("id")

        if not signal_id:
            continue

        signal_id = str(signal_id)

        current_engagement = _read_engagement(signal)

        previous = previous_by_id.get(signal_id)

        if previous is None:
            momentum = None
        else:
            try:
                previous_engagement = float(
                    previous.get("engagement", 0.0)
                )
            except (TypeError, ValueError):
                previous_engagement = 0.0

            momentum = _calculate_momentum(
                previous_engagement,
                current_engagement,
            )

        signal["momentum"] = momentum

        new_snapshots.append(
            {
                "id": signal_id,
                "engagement": current_engagement,
                "captured_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

    save_signal_snapshots(new_snapshots)

    return signals
