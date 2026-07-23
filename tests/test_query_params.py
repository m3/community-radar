"""Pagination parameters must not turn into 500s.

int(request.args.get("limit")) raises ValueError on any non-numeric value,
and there is no error handler registered, so ?limit=abc surfaced as an
unhandled 500 rather than a 400.
"""

import pytest
import yaml

from src.dashboard.app import app, config_mgr


@pytest.fixture
def client(tmp_path, monkeypatch):
    app.config["TESTING"] = True
    temp_config = tmp_path / "config.yaml"
    with open(temp_config, "w") as f:
        yaml.dump({"clients": {"test-client": {"name": "Test Client"}}}, f)

    # Point both the app's config manager and the model layer's tenant
    # authority at the temp config so get_db recognises test-client.
    monkeypatch.setenv("COMMUNITY_RADAR_CONFIG", str(temp_config))
    old_path = config_mgr.config_path
    config_mgr.config_path = temp_config
    config_mgr.clear_cache()

    with app.test_client() as c:
        yield c

    config_mgr.config_path = old_path
    config_mgr.clear_cache()


BAD = ["abc", "1.5", "9e9", "--1", "0x10"]

PAGINATED = [
    "/api/test-client/raw_messages",
    "/api/test-client/cuebot/engagement/leaderboard",
]


@pytest.mark.parametrize("route", PAGINATED)
@pytest.mark.parametrize("value", BAD)
def test_non_numeric_limit_is_a_client_error(client, route, value):
    resp = client.get(f"{route}?limit={value}")
    assert resp.status_code == 400, f"{route}?limit={value} returned {resp.status_code}"


@pytest.mark.parametrize("value", BAD)
def test_non_numeric_offset_is_a_client_error(client, value):
    resp = client.get(f"/api/test-client/raw_messages?offset={value}")
    assert resp.status_code == 400


@pytest.mark.parametrize("value", ["-1", "-100"])
def test_negative_pagination_is_a_client_error(client, value):
    assert client.get(f"/api/test-client/raw_messages?limit={value}").status_code == 400
    assert client.get(f"/api/test-client/raw_messages?offset={value}").status_code == 400


@pytest.mark.parametrize("route", PAGINATED)
def test_an_empty_parameter_falls_back_to_the_default(client, route):
    """?limit= is treated as unset rather than as a malformed value."""
    assert client.get(f"{route}?limit=").status_code != 400


def test_limit_above_the_cap_is_clamped_not_rejected(client):
    """The cap has always been silently applied; keep that contract."""
    assert client.get("/api/test-client/raw_messages?limit=99999").status_code != 400
