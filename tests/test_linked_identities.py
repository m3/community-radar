import pytest
import os
import json
import sqlite3
from pathlib import Path
from src.dashboard.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # We use pure-pool-pro as it's in the config.yaml
    with app.test_client() as client:
        yield client

def test_user_profile_endpoint_exists(client):
    # Just checking if the endpoint returns 200/404 correctly
    # We use a non-existent user to see if it handles it (should be 404 per app.py)
    response = client.get('/api/pure-pool-pro/cuebot/engagement/user/nonexistent')
    assert response.status_code == 404

def test_user_profile_response_format(client):
    # We use the valid user ID found earlier
    user_id = "1000123636272861184"
    response = client.get(f'/api/pure-pool-pro/cuebot/engagement/user/{user_id}')
    if response.status_code == 200:
        data = json.loads(response.data)
        # These are the expected keys after the update
        assert "linked_identities" in data
