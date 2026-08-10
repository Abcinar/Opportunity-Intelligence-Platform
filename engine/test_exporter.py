import json

from engine import exporter


def test_daily_signals_export_and_load(tmp_path, monkeypatch):
    daily_file = tmp_path / "daily_signals.json"

    monkeypatch.setattr(
        exporter,
        "DAILY_SIGNALS_FILE",
        str(daily_file),
    )

    signals = [
        {
            "id": "test-001",
            "title": "AI automation opportunity",
            "source": "github",
        },
        {
            "id": "test-002",
            "title": "Project management opportunity",
            "source": "hackernews",
        },
    ]

    exporter.export_daily_signals(signals)

    loaded = exporter.load_daily_signals()

    assert loaded == signals
    assert daily_file.exists()


def test_daily_signals_file_contains_valid_json(tmp_path, monkeypatch):
    daily_file = tmp_path / "daily_signals.json"

    monkeypatch.setattr(
        exporter,
        "DAILY_SIGNALS_FILE",
        str(daily_file),
    )

    signals = [
        {
            "id": "test-001",
            "title": "AI automation opportunity",
        }
    ]

    exporter.export_daily_signals(signals)

    with open(daily_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data == signals
