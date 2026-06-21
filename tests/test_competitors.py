import pytest
from unittest.mock import MagicMock, patch
from src.analysis.competitors import (
    search_keywords,
    classify_message,
    extract_quote,
    run_analysis
)

def test_search_keywords():
    keywords = ["pure pool", "snooker 19"]
    # Case insensitivity
    assert search_keywords("I like Pure Pool", keywords) == ["pure pool"]
    # Word boundary
    assert search_keywords("I like purepool", keywords) == []
    # Match multiple
    assert search_keywords("I play pure pool and snooker 19", keywords) == ["pure pool", "snooker 19"]

def test_classify_message():
    # Pure Pool mention
    cls, hits = classify_message("I am playing pure pool")
    assert cls == "pure_pool_mention"
    assert "pure pool" in hits

    # Competitor mention
    cls, hits = classify_message("I like snooker 19")
    assert cls == "competitor_mention"
    assert "snooker 19" in hits

    # Neutral
    cls, hits = classify_message("Just general discussion")
    assert cls is None
    assert hits == []

def test_extract_quote():
    text = "This is a very long string designed to test the extraction of a quote based on a keyword. We want to see how it formats."
    quote = extract_quote(text, "extraction", context=20)
    assert "extraction" in quote
    assert quote.startswith("...")
    assert quote.endswith("...")

    # Not found fallback
    quote_missing = extract_quote(text, "missing")
    assert quote_missing == text[:300]

@patch("src.analysis.competitors.get_db")
@patch("src.analysis.competitors.load_config")
def test_run_analysis(mock_load_config, mock_get_db, tmp_path):
    # Mock config
    mock_load_config.return_value = {
        "data_dir": str(tmp_path),
        "clients": {
            "test-client": {
                "reddit": {
                    "subreddits": {
                        "billiards": {
                            "track_keywords": ["pure pool"]
                        }
                    }
                }
            }
        }
    }

    # Mock DB
    mock_db = MagicMock()
    mock_msg_pure_pool = {
        "message_id": "pp1",
        "content": "This pure pool game is amazing!",
        "timestamp": "2023-01-01 10:00:00",
        "reactions": None,  # Test reactions is None
        "platform": "reddit",
        "channel_name": "reddit_billiards"
    }
    mock_msg_competitor = {
        "message_id": "comp1",
        "content": "I prefer Snooker 19.",
        "timestamp": None,  # Test timestamp is None
        "reactions": 5,
        "platform": "reddit",
        "channel_name": "reddit_billiards"
    }
    
    class MockRow(dict):
        pass

    mock_db.execute.return_value.all.return_value = [
        MockRow(mock_msg_pure_pool),
        MockRow(mock_msg_competitor)
    ]
    mock_get_db.return_value = mock_db

    # Overwrite the global DATA_DIR in the test context (since it is resolved at import time)
    with patch("src.analysis.competitors.DATA_DIR", tmp_path):
        report = run_analysis("test-client")
        
        assert report is not None
        assert report["meta"]["total_messages_scanned"] == 2
        assert report["meta"]["pure_pool_mentions"] == 1
        assert report["meta"]["competitor_mentions"] == 1
        
        # Verify JSON report structure
        json_file = tmp_path / "clients" / "test-client" / "reports" / "competitor_intel.json"
        assert json_file.exists()
        
        # Verify MD report structure
        md_file = tmp_path / "clients" / "test-client" / "reports" / "competitor_intel.md"
        assert md_file.exists()
