"""Timestamp formatting that tolerates both storage shapes.

Timestamp columns were TEXT under SQLite and are DateTime under Postgres,
so a row value may be either an ISO string or a datetime depending on the
column and the code path. Slicing a datetime raises TypeError, so every
display site needs the same guard — it lives here rather than being
rewritten at each one.
"""

from datetime import date, datetime

_DAY = "%Y-%m-%d"
_MONTH = "%Y-%m"
_SECONDS = "%Y-%m-%d %H:%M:%S"


def _format(ts, fmt, length, default):
    if not ts:
        return default
    if isinstance(ts, (datetime, date)):
        return ts.strftime(fmt)
    return str(ts)[:length]


def to_day(ts, default="unknown"):
    """YYYY-MM-DD."""
    return _format(ts, _DAY, 10, default)


def to_month(ts, default="unknown"):
    """YYYY-MM."""
    return _format(ts, _MONTH, 7, default)


def to_seconds(ts, default="unknown"):
    """Date down to the second.

    An ISO string keeps its 'T' separator — this is a display helper, not a
    parser, and rewriting the separator would be a lie about the stored value.
    """
    return _format(ts, _SECONDS, 19, default)
