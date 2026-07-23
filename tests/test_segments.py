"""Shared owned/external channel classification.

The dashboard and the nightly analysis job must agree on which channels are
'owned' so precomputed per-segment stats match what the live routes would
have produced. This logic used to live only in the dashboard.
"""

from src.segments import is_channel_owned, owned_subreddits_for


def test_owned_reddit_channel_with_hyphen():
    assert is_channel_owned("reddit-purepoolpro-hot", {"purepoolpro"}) is True


def test_owned_reddit_channel_with_underscore():
    assert is_channel_owned("reddit_purepoolpro_new", {"purepoolpro"}) is True


def test_external_reddit_channel():
    assert is_channel_owned("reddit-billiards-new", {"purepoolpro"}) is False


def test_non_reddit_channel_is_owned():
    # Discord and other non-reddit channels count as owned.
    assert is_channel_owned("general", {"purepoolpro"}) is True


def test_bare_reddit_prefix_is_external():
    assert is_channel_owned("reddit", {"purepoolpro"}) is False


def test_case_insensitive():
    assert is_channel_owned("Reddit-PurePoolPro-Hot", {"purepoolpro"}) is True


def test_owned_subreddits_for_reads_owned_flag():
    cfg = {
        "reddit": {
            "subreddits": {
                "PurePoolPro": {"owned": True},
                "billiards": {"owned": False},
                "snooker": {},
            }
        }
    }
    assert owned_subreddits_for(cfg) == {"purepoolpro"}


def test_owned_subreddits_for_empty_config():
    assert owned_subreddits_for({}) == set()
