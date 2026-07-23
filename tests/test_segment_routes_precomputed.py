"""The heavy analytics routes read precomputed segment stats when present.

When the report carries a `segments` block, topics/power_words/purpose/
timeseries/overview must serve it directly rather than scanning the database
and re-classifying every message. Patching get_db to raise proves no scan.
"""

import pytest
import yaml
from unittest.mock import patch

from src.dashboard.app import app, config_mgr


@pytest.fixture
def client(tmp_path, monkeypatch):
    app.config["TESTING"] = True
    cfg = tmp_path / "config.yaml"
    with open(cfg, "w") as f:
        yaml.dump({"clients": {"test-client": {"name": "Test Client"}}}, f)
    monkeypatch.setenv("COMMUNITY_RADAR_CONFIG", str(cfg))
    old = config_mgr.config_path
    config_mgr.config_path = cfg
    config_mgr.clear_cache()
    with app.test_client() as c:
        yield c
    config_mgr.config_path = old
    config_mgr.clear_cache()


REPORT = {
    "segments": {
        "owned": {
            "sentiment_ratio": 3.5,
            "topic_sentiment": {"physics": {"total": 9, "pos_pct": 80.0, "neg_pct": 10.0, "net_sentiment": 70.0}},
            "power_words": {"bug": 4},
            "purpose": {"distribution": {"question": {"count": 5, "pct": 50.0}}, "by_channel": {}},
            "series": {"reddit": {"2026-03-09": {"positive": 3, "negative": 0, "neutral": 1, "total": 4}}},
        },
        "external": {
            "sentiment_ratio": 1.1,
            "topic_sentiment": {},
            "power_words": {},
            "purpose": {"distribution": {}, "by_channel": {}},
            "series": {},
        },
    },
    "sentiment": {"overall": {"sentiment_ratio": 2.0}},
    "meta": {"generated_at": "2026-03-09T00:00:00"},
}


def _boom(*a, **k):
    raise AssertionError("route hit the database instead of reading precomputed segments")


def test_topics_reads_precomputed(client):
    with patch("src.dashboard.api_analytics.load_report", return_value=REPORT), \
         patch("src.dashboard.api_analytics.get_db", _boom):
        resp = client.get("/api/test-client/topics?segment=owned")
    assert resp.status_code == 200
    assert resp.get_json()["physics"]["total"] == 9


def test_power_words_reads_precomputed(client):
    with patch("src.dashboard.api_analytics.load_report", return_value=REPORT), \
         patch("src.dashboard.api_analytics.get_db", _boom):
        resp = client.get("/api/test-client/power_words?segment=owned")
    assert resp.get_json() == {"bug": 4}


def test_purpose_reads_precomputed(client):
    with patch("src.dashboard.api_analytics.load_report", return_value=REPORT), \
         patch("src.dashboard.api_analytics.get_db", _boom):
        resp = client.get("/api/test-client/purpose?segment=external")
    assert resp.get_json()["distribution"] == {}


def test_timeseries_reads_precomputed(client):
    with patch("src.dashboard.api_analytics.load_report", return_value=REPORT), \
         patch("src.dashboard.api_analytics.get_db", _boom):
        resp = client.get("/api/test-client/sentiment/timeseries?segment=owned")
    series = resp.get_json()["series"]
    assert series["reddit"]["2026-03-09"]["total"] == 4


def test_overview_ratio_reads_precomputed(client):
    # Overview still needs the DB for cheap platform/user counts; the win is
    # reading the precomputed sentiment_ratio instead of a scan+classify.
    with patch("src.dashboard.api_analytics.load_report", return_value=REPORT), \
         patch("src.dashboard.api_analytics.get_channel_segmentation", return_value=([], [])):
        resp = client.get("/api/test-client/overview?segment=owned")
    assert resp.status_code == 200
    assert resp.get_json()["report_meta"]["sentiment_ratio"] == 3.5


def test_falls_back_to_scan_when_no_segments(client):
    """A report without a segments block must still work (old reports)."""
    with patch("src.dashboard.api_analytics.load_report", return_value={"topic_sentiment": {}}), \
         patch("src.dashboard.api_analytics.get_channel_segmentation", return_value=([], [])):
        # segment=owned with empty ids -> scan path returns empty, no crash
        resp = client.get("/api/test-client/topics?segment=owned")
    assert resp.status_code == 200
