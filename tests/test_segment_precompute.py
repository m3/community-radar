"""Per-segment precompute for the dashboard.

The topics/power_words/purpose/timeseries/overview routes re-scanned every
message and re-ran lexicon classification on each request for the owned and
external segments. compute_segment_stats does that once in the nightly job so
the routes can read the result. Its output must mirror the shapes those
routes already return for segment=all.
"""

from src.analysis.sentiment import compute_segment_stats


def _msg(content, channel_name, platform="reddit", timestamp="2026-03-09T10:00:00"):
    return {
        "content": content,
        "channel_name": channel_name,
        "platform": platform,
        "timestamp": timestamp,
    }


OWNED = {"purepoolpro"}


def test_splits_by_owned_and_external():
    msgs = [
        _msg("great game", "reddit-purepoolpro-hot"),
        _msg("terrible bug", "reddit-billiards-new"),
    ]
    stats = compute_segment_stats(msgs, {}, OWNED)
    assert set(stats.keys()) == {"owned", "external"}


def test_sentiment_ratio_per_segment():
    # Two positive owned messages, one negative external.
    msgs = [
        _msg("love this great awesome", "reddit-purepoolpro-hot"),
        _msg("love this great awesome", "reddit-purepoolpro-new"),
        _msg("hate terrible awful broken", "reddit-billiards-new"),
    ]
    stats = compute_segment_stats(msgs, {}, OWNED)
    assert stats["owned"]["sentiment_ratio"] >= 1.0
    assert stats["external"]["sentiment_ratio"] < 1.0


def test_topic_sentiment_shape_matches_route():
    msgs = [_msg("the physics are great", "reddit-purepoolpro-hot")]
    stats = compute_segment_stats(msgs, {"physics": "gameplay"}, OWNED)
    topic = stats["owned"]["topic_sentiment"]["physics"]
    assert set(topic.keys()) == {"total", "pos_pct", "neg_pct", "net_sentiment"}
    assert topic["total"] == 1


def test_power_words_are_counted_per_segment():
    msgs = [_msg("bug bug crash", "reddit-billiards-new")]
    stats = compute_segment_stats(msgs, {}, OWNED)
    assert isinstance(stats["external"]["power_words"], dict)
    assert stats["owned"]["power_words"] == {}


def test_purpose_distribution_shape():
    msgs = [_msg("how do I fix this?", "reddit-purepoolpro-hot")]
    stats = compute_segment_stats(msgs, {}, OWNED)
    dist = stats["owned"]["purpose"]["distribution"]
    assert dist  # non-empty
    first = next(iter(dist.values()))
    assert set(first.keys()) == {"count", "pct"}


def test_series_grouped_by_platform_and_day():
    msgs = [
        _msg("great", "reddit-purepoolpro-hot", platform="reddit", timestamp="2026-03-09T10:00:00"),
        _msg("great", "reddit-purepoolpro-hot", platform="reddit", timestamp="2026-03-09T12:00:00"),
    ]
    stats = compute_segment_stats(msgs, {}, OWNED)
    day = stats["owned"]["series"]["reddit"]["2026-03-09"]
    assert day["total"] == 2


def test_datetime_timestamps_supported():
    from datetime import datetime
    msgs = [_msg("great", "reddit-purepoolpro-hot", timestamp=datetime(2026, 3, 9, 10))]
    stats = compute_segment_stats(msgs, {}, OWNED)
    assert "2026-03-09" in stats["owned"]["series"]["reddit"]


def test_empty_messages_yields_empty_segments():
    stats = compute_segment_stats([], {}, OWNED)
    assert stats["owned"]["topic_sentiment"] == {}
    assert stats["external"]["series"] == {}
