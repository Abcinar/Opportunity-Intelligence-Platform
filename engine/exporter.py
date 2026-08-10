"""
Opportunity Intelligence Platform - Exporter Engine
---------------------------------------
Verileri yapılandırılmış JSON dosyalarına kaydetmekten sorumludur.
Single Source of Truth (opportunities.json) kuralına uyar.
"""

import json
import os
import logging
from typing import List, Dict, Any

from config import (
    OPPORTUNITIES_FILE,
    DAILY_SIGNALS_FILE,
    TRACKED_OPPORTUNITIES_FILE
)

logger = logging.getLogger(__name__)


def _save_json(filepath: str, data: Any) -> None:
    """Belirtilen veriyi güvenli bir şekilde JSON dosyasına yazar."""
    try:
        # Klasör yoksa oluştur
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Veri başarıyla dışa aktarıldı: {filepath}")
    except Exception as e:
        logger.error(f"JSON kaydetme hatası ({filepath}): {str(e)}")


def _load_json(filepath: str) -> Any:
    """Belirtilen JSON dosyasını okur. Dosya yoksa boş liste döner."""
    if not os.path.exists(filepath):
        logger.warning(f"Dosya bulunamadı, yeni oluşturulacak: {filepath}")
        return []
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"JSON okuma hatası ({filepath}): {str(e)}")
        return []


def export_opportunities(opportunities: List[Dict[str, Any]]) -> None:
    """
    Sistemin ana veri kaynağını (opportunities.json) günceller.
    Single Source of Truth prensibi gereği tüm platform bu dosyayı okur.
    """
    _save_json(OPPORTUNITIES_FILE, opportunities)


def export_daily_signals(signals: List[Dict[str, Any]]) -> None:
    """Günlük ham veya yarı-işlenmiş sinyal listesini kaydeder."""
    _save_json(DAILY_SIGNALS_FILE, signals)


def load_daily_signals() -> Any:
    """Günlük sinyalleri (daily_signals.json) okur."""
    return _load_json(DAILY_SIGNALS_FILE)


def export_tracked_opportunities(tracked_data: List[Dict[str, Any]]) -> None:
    """
    Kullanıcının takibe aldığı (Tracked) fırsatları kaydeder.
    Eski adıyla TRACKED_FILE, yeni adıyla TRACKED_OPPORTUNITIES_FILE kullanır.
    """
    _save_json(TRACKED_OPPORTUNITIES_FILE, tracked_data)


def load_opportunities() -> List[Dict[str, Any]]:
    """Mevcut fırsatları (opportunities.json) okur ve döndürür."""
    return _load_json(OPPORTUNITIES_FILE)


def load_tracked_opportunities() -> List[Dict[str, Any]]:
    """Mevcut takip edilen fırsatları okur ve döndürür."""
    return _load_json(TRACKED_OPPORTUNITIES_FILE)
# ==========================================
# BACKWARD COMPATIBILITY (Geriye Dönük Uyumluluk)
# main.py ve diğer eski modüllerin bozulmaması için:
# ==========================================
save_daily_signals = export_daily_signals
save_opportunities = export_opportunities
save_tracked_opportunities = export_tracked_opportunities 
# ========================================== 
