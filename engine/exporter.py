"""
Opportunity Intelligence Platform - Exporter Engine
----------------------------------------------------

Verileri yapılandırılmış JSON dosyalarına kaydetmekten sorumludur.

Single Source of Truth:
    opportunities.json

Ayrıca momentum motoru için sinyal snapshotlarını
kaydetme ve yükleme desteği sağlar.
"""

import json
import os
import logging
from typing import List, Dict, Any

from config import (
    OPPORTUNITIES_FILE,
    DAILY_SIGNALS_FILE,
    TRACKED_OPPORTUNITIES_FILE,
    SIGNAL_SNAPSHOTS_FILE,
)

logger = logging.getLogger(__name__)


def _save_json(filepath: str, data: Any) -> None:
    """Belirtilen veriyi güvenli bir şekilde JSON dosyasına yazar."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False,
            )

        logger.info(
            f"Veri başarıyla dışa aktarıldı: {filepath}"
        )

    except Exception as e:
        logger.error(
            f"JSON kaydetme hatası ({filepath}): {str(e)}"
        )


def _load_json(filepath: str) -> Any:
    """Belirtilen JSON dosyasını okur. Dosya yoksa boş liste döner."""
    if not os.path.exists(filepath):
        logger.warning(
            f"Dosya bulunamadı, yeni oluşturulacak: {filepath}"
        )
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        logger.error(
            f"JSON okuma hatası ({filepath}): {str(e)}"
        )
        return []


def export_opportunities(
    opportunities: List[Dict[str, Any]],
) -> None:
    """
    Sistemin ana veri kaynağını opportunities.json olarak günceller.
    """
    _save_json(
        OPPORTUNITIES_FILE,
        opportunities,
    )


def export_daily_signals(
    signals: List[Dict[str, Any]],
) -> None:
    """Günlük ham veya yarı-işlenmiş sinyal listesini kaydeder."""
    _save_json(
        DAILY_SIGNALS_FILE,
        signals,
    )


def load_daily_signals() -> Any:
    """Günlük sinyalleri daily_signals.json dosyasından okur."""
    return _load_json(
        DAILY_SIGNALS_FILE,
    )


def export_tracked_opportunities(
    tracked_data: List[Dict[str, Any]],
) -> None:
    """Kullanıcının takip ettiği fırsatları kaydeder."""
    _save_json(
        TRACKED_OPPORTUNITIES_FILE,
        tracked_data,
    )


def load_opportunities() -> List[Dict[str, Any]]:
    """Mevcut fırsatları opportunities.json dosyasından okur."""
    data = _load_json(OPPORTUNITIES_FILE)

    if not isinstance(data, list):
        logger.warning(
            "Opportunities JSON liste formatında değil; "
            "boş liste kullanılıyor."
        )
        return []

    return data


def load_tracked_opportunities() -> List[Dict[str, Any]]:
    """Mevcut takip edilen fırsatları okur."""
    data = _load_json(
        TRACKED_OPPORTUNITIES_FILE,
    )

    if not isinstance(data, list):
        logger.warning(
            "Tracked opportunities JSON liste formatında değil; "
            "boş liste kullanılıyor."
        )
        return []

    return data


# ============================================================
# SIGNAL SNAPSHOT API
# ============================================================


def save_signal_snapshots(
    snapshots: List[Dict[str, Any]],
) -> None:
    """
    Sinyallerin geçmiş engagement değerlerini snapshot olarak kaydeder.

    Momentum motoru bir sonraki çalışmada bu veriyi
    önceki değerlerle karşılaştırmak için kullanır.
    """
    if not isinstance(snapshots, list):
        raise ValueError("snapshots must be a list")

    _save_json(
        SIGNAL_SNAPSHOTS_FILE,
        snapshots,
    )


def load_signal_snapshots() -> List[Dict[str, Any]]:
    """
    Daha önce kaydedilmiş sinyal snapshotlarını yükler.
    """
    data = _load_json(
        SIGNAL_SNAPSHOTS_FILE,
    )

    if not isinstance(data, list):
        logger.warning(
            "Signal snapshots JSON liste formatında değil; "
            "boş liste kullanılıyor."
        )
        return []

    return data


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

save_daily_signals = export_daily_signals
save_opportunities = export_opportunities
save_tracked_opportunities = export_tracked_opportunities
