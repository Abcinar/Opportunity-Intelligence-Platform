"""
Opportunity Intelligence Platform - Configuration
"""
import os

# ==========================================
# SYSTEM & FILE SETTINGS
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OPPORTUNITIES_FILE = os.path.join(DATA_DIR, "opportunities.json")
DAILY_SIGNALS_FILE = os.path.join(DATA_DIR, "daily_signals.json")
TRACKED_OPPORTUNITIES_FILE = os.path.join(DATA_DIR, "tracked_opportunities.json")
SIGNAL_SNAPSHOTS_FILE = os.path.join(DATA_DIR, "signal_snapshots.json")

# ==========================================
# COLLECTOR ENGINE SETTINGS
# ==========================================
GITHUB_LIMIT = 10
GOOGLE_LIMIT = 10
HN_LIMIT = 30
REDDIT_LIMIT = 30
PRODUCTHUNT_LIMIT = 10
LOBSTERS_LIMIT = 10
BETALIST_LIMIT = 10

# ==========================================
# INTELLIGENCE ENGINE SETTINGS
# ==========================================
INTELLIGENCE_ENGINE_VERSION = "2.1.0"
RULES_VERSION = "1.1.0"

TREND_HIGH_ENGAGEMENT_THRESHOLD = 100
TREND_MEDIUM_ENGAGEMENT_THRESHOLD = 20

CONFIDENCE_WEIGHTS = {
    "evidence": 0.35,
    "problem": 0.20,
    "opportunity": 0.20,
    "market": 0.15,
    "category": 0.10
}
