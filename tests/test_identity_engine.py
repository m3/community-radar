import pytest
from src.analysis.identity import match_identities

def test_match_identities_exact():
    users = [
        {"id": "123", "username": "JohnDoe", "display_name": "John"},
        {"id": "reddit_JohnDoe", "username": "JohnDoe", "display_name": "JD"}
    ]
    matches = match_identities(users)
    assert len(matches) == 1
    assert matches[0]["match_type"] == "exact"
    assert matches[0]["confidence"] == 1.0
    assert matches[0]["user_id"] == "123"
    assert matches[0]["username1"] == "JohnDoe"
    assert matches[0]["platform1"] == "discord"
    assert matches[0]["username2"] == "JohnDoe"
    assert matches[0]["platform2"] == "reddit"

def test_match_identities_fuzzy():
    users = [
        {"id": "456", "username": "JaneDoe", "display_name": "Jane"},
        {"id": "reddit_Jane_Doe", "username": "Jane_Doe", "display_name": "JaneD"}
    ]
    matches = match_identities(users)
    assert len(matches) == 1
    assert matches[0]["match_type"] == "fuzzy"
    assert matches[0]["confidence"] > 0.85
    assert matches[0]["user_id"] == "456"
