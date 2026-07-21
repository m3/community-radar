"""Timestamp formatting helpers.

Columns like messages.timestamp and topics.first_seen were TEXT under
SQLite and are DateTime under Postgres, so psycopg returns datetime
objects. Code that still slices them as strings (ts[:10]) raises
TypeError. Six sites guard with isinstance and four did not; this
centralises the guard.
"""

from datetime import datetime

from src.timeutils import to_day, to_month, to_seconds

DT = datetime(2026, 3, 9, 14, 5, 33)
ISO = "2026-03-09T14:05:33.123456"


def test_to_day_formats_a_datetime():
    assert to_day(DT) == "2026-03-09"


def test_to_day_slices_an_iso_string():
    assert to_day(ISO) == "2026-03-09"


def test_to_month_formats_a_datetime():
    assert to_month(DT) == "2026-03"


def test_to_month_slices_an_iso_string():
    assert to_month(ISO) == "2026-03"


def test_to_seconds_formats_a_datetime():
    assert to_seconds(DT) == "2026-03-09 14:05:33"


def test_to_seconds_slices_an_iso_string():
    assert to_seconds(ISO) == "2026-03-09T14:05:33"


def test_none_returns_the_default():
    assert to_day(None) == "unknown"
    assert to_month(None) == "unknown"
    assert to_seconds(None) == "unknown"


def test_default_is_overridable():
    assert to_day(None, default="N/A") == "N/A"
    assert to_seconds(None, default="?") == "?"


def test_empty_string_is_treated_as_missing():
    assert to_day("") == "unknown"


def test_date_objects_work_too():
    assert to_day(DT.date()) == "2026-03-09"
