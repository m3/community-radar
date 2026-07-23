"""The owned/external channel filter, extracted from eight copy-pasted blocks.

Each API endpoint appended the same ~12-line if/elif to restrict rows to a
client's owned or external channels. segment_filter() is that logic in one
place; these tests pin the exact SQL and params the blocks produced.
"""

from src.dashboard.app import segment_filter

OWNED = [1, 2, 3]
EXTERNAL = [4, 5]


def test_all_segment_adds_nothing():
    assert segment_filter("all", OWNED, EXTERNAL) == ("", [])


def test_unknown_segment_adds_nothing():
    assert segment_filter("bogus", OWNED, EXTERNAL) == ("", [])


def test_owned_segment():
    frag, params = segment_filter("owned", OWNED, EXTERNAL)
    assert frag == " AND m.channel_id IN (?, ?, ?)"
    assert params == [1, 2, 3]


def test_external_segment():
    frag, params = segment_filter("external", OWNED, EXTERNAL)
    assert frag == " AND m.channel_id IN (?, ?)"
    assert params == [4, 5]


def test_empty_owned_returns_no_rows():
    assert segment_filter("owned", [], EXTERNAL) == (" AND 1=0", [])


def test_empty_external_returns_no_rows():
    assert segment_filter("external", OWNED, []) == (" AND 1=0", [])


def test_connector_is_overridable():
    frag, _ = segment_filter("owned", OWNED, EXTERNAL, connector="WHERE")
    assert frag == " WHERE m.channel_id IN (?, ?, ?)"


def test_column_is_overridable():
    frag, _ = segment_filter("owned", OWNED, EXTERNAL, column="channel_id")
    assert frag == " AND channel_id IN (?, ?, ?)"


def test_params_are_a_fresh_list():
    """Callers extend the returned params; it must not alias the id list."""
    _, params = segment_filter("owned", OWNED, EXTERNAL)
    params.append(99)
    assert OWNED == [1, 2, 3]
