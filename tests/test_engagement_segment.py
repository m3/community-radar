"""api_engagement's owned/external path must not 500.

The active-users subquery used `HAVING cnt >= 5`, referencing the SELECT
alias `cnt`. Postgres does not allow a SELECT alias in HAVING, so both
segmented variants raised UndefinedColumn (a 500). The `segment=all` path
avoided it by reading the precomputed report instead of the database.
"""

from datetime import datetime

import pytest
import yaml

from src.dashboard.app import app, config_mgr
from src.db.models import get_db


CLIENT = "engagement-client"


@pytest.fixture
def client(tmp_path, monkeypatch):
    app.config["TESTING"] = True
    cfg = tmp_path / "config.yaml"
    with open(cfg, "w") as f:
        yaml.dump({"clients": {CLIENT: {"name": "Engagement Client"}}}, f)

    monkeypatch.setenv("COMMUNITY_RADAR_CONFIG", str(cfg))
    old = config_mgr.config_path
    config_mgr.config_path = cfg
    config_mgr.clear_cache()

    _seed()

    with app.test_client() as c:
        yield c

    config_mgr.config_path = old
    config_mgr.clear_cache()


def _seed():
    """One user with 6 messages in one channel — enough to exercise HAVING."""
    db = get_db(CLIENT)
    # The test database persists across the session; start from a clean slate
    # for this client so re-seeding per test does not collide on primary keys.
    for table in ("messages", "channels", "users", "servers"):
        db.execute(f"DELETE FROM {table} WHERE client_id = :client_id")
    db.commit()
    db.execute(
        "INSERT INTO servers (id, name, data_source, total_messages, total_users, created_at, updated_at) "
        "VALUES (?, ?, 'reddit', 0, 0, ?, ?)",
        ("srv1", "server", datetime.now(), datetime.now()),
    )
    db.execute(
        "INSERT INTO channels (id, server_id, name, message_count, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 0, 'ok', ?, ?)",
        ("chan1", "srv1", "reddit-general", datetime.now(), datetime.now()),
    )
    db.execute(
        "INSERT INTO users (id, role, messages, reactions_given, reactions_received, created_at, updated_at) "
        "VALUES (?, 'x', 0, 0, 0, ?, ?)",
        ("user1", datetime.now(), datetime.now()),
    )
    for i in range(6):
        db.execute(
            "INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, content, timestamp, reactions, platform, created_at) "
            "VALUES (?, ?, ?, ?, ?, 0, 'reddit', ?)",
            (f"m{i}", "chan1", "user1", "hi", datetime.now(), datetime.now()),
        )
    db.commit()
    db.close()


@pytest.mark.parametrize("segment", ["all", "owned", "external"])
def test_engagement_endpoint_succeeds(client, segment):
    resp = client.get(f"/api/{CLIENT}/engagement?segment={segment}")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:200]


def test_active_users_counts_the_5plus_user(client):
    # chan1 is external (reddit-general, not owned), so the external segment
    # sees the 6-message user.
    resp = client.get(f"/api/{CLIENT}/engagement?segment=external")
    assert resp.get_json()["active_users_5plus"] == 1
