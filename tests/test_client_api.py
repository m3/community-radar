import pytest
import json
from src.dashboard.app import app
import os
from pathlib import Path
import yaml

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Save original config
    config_path = Path("config.yaml")
    original_content = None
    if config_path.exists():
        with open(config_path, "r") as f:
            original_content = f.read()
    
    with app.test_client() as client:
        yield client
        
    # Restore original config
    if original_content:
        with open(config_path, "w") as f:
            f.write(original_content)
    elif config_path.exists():
        config_path.unlink()

def test_get_clients(client):
    response = client.get('/api/clients')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'clients' in data

def test_create_client(client):
    payload = {
        "client_id": "test_client",
        "name": "Test Client"
    }
    response = client.post('/api/clients', json=payload)
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True

def test_update_client(client):
    # First create
    client.post('/api/clients', json={"client_id": "upd_client", "name": "Old Name"})
    
    # Then update
    payload = {
        "name": "New Name",
        "reddit": {"subreddits": ["test"]},
        "discord": {"servers": ["123"]}
    }
    response = client.post('/api/clients/upd_client/update', json=payload)
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True
    
    # Verify update
    get_resp = client.get('/api/clients')
    data = json.loads(get_resp.data)
    assert data["clients"]["upd_client"]["name"] == "New Name"
