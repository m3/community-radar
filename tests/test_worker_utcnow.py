"""The worker's UTC clock must stay naive.

The tasks table stores `timestamp without time zone`, and the zombie-reset
query compares heartbeat_at against this value. datetime.utcnow() is
deprecated, but its replacement datetime.now(timezone.utc) is tz-aware —
mixing that with the naive column risks silent offset shifts. The helper
keeps naive-UTC semantics without the deprecation.
"""

from datetime import datetime, timezone

from src.queue_worker import _utcnow


def test_utcnow_is_naive():
    assert _utcnow().tzinfo is None


def test_utcnow_is_utc():
    # Within a second of a known-good tz-aware UTC reading, stripped of tzinfo.
    reference = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs((_utcnow() - reference).total_seconds()) < 1
