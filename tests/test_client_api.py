import pytest
import json
from src.dashboard.app import app, config_mgr
import os
from pathlib import Path
import yaml

@pytest.fixture
def client(tmp_path):
    app.config['TESTING'] = True
    
    # Create a temporary config file
    temp_config = tmp_path / "config.yaml"
    initial_config = {"clients": {}}
    with open(temp_config, "w") as f:
        yaml.dump(initial_config, f)
    
    # Save old config_mgr state
    old_path = config_mgr.config_path
    
    # Point config_mgr to temp file
    config_mgr.config_path = temp_config
    config_mgr.clear_cache()
    
    with app.test_client() as client:
        yield client
        
    # Restore config_mgr state
    config_mgr.config_path = old_path
    config_mgr.clear_cache()

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
        "reddit": {"subreddits": {"test": {"sorts": ["new"]}}},
        "discord": {"servers": {"123": {"name": "Test Server", "channels": {}}}}
    }
    response = client.post('/api/clients/upd_client/update', json=payload)
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True
    
    # Verify update
    get_resp = client.get('/api/clients')
    data = json.loads(get_resp.data)
    assert data["clients"]["upd_client"]["name"] == "New Name"
