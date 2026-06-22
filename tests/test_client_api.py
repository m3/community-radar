import pytest
import json
from src.dashboard.app import app, config_mgr
import os
from pathlib import Path
import yaml
from unittest.mock import MagicMock, patch

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

def test_api_market_intel(client, tmp_path):
    # Setup mock client config with data_dir pointing to tmp_path
    client_id = "intel_client"
    payload = {
        "client_id": client_id,
        "name": "Intel Client"
    }
    client.post('/api/clients', json=payload)
    
    # Update config to include data_dir
    config = config_mgr.load()
    config["data_dir"] = str(tmp_path)
    config_mgr.save(config)
    
    # Create a mock competitor_intel.json file
    reports_dir = tmp_path / "clients" / client_id / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    mock_intel_data = {
        "meta": {
            "pure_pool_mentions": 10,
            "competitor_mentions": 20,
            "unique_competitors": 2,
            "feature_requests": 5,
            "pain_points_flagged": 2
        },
        "pure_pool_mentions": []
    }
    with open(reports_dir / "competitor_intel.json", "w") as f:
        json.dump(mock_intel_data, f)
        
    # Mock database for domain monitoring query
    mock_db = MagicMock()
    mock_db.execute.return_value.fetchall.return_value = [
        {"channel_name": "domain:ripstone.com", "post_count": 3, "last_post": "2026-06-20 12:00:00"}
    ]
    
    with patch('src.dashboard.app.get_db', return_value=mock_db):
        response = client.get(f'/api/{client_id}/intel/market')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["competitors"]["meta"]["pure_pool_mentions"] == 10
        assert data["domains"][0]["post_count"] == 3


def test_update_client_validation_errors(client):
    # First create
    client.post('/api/clients', json={"client_id": "val_client", "name": "Old Name"})
    
    # Then update with invalid max_pages (greater than 20) and blank name
    payload = {
        "name": "",
        "reddit": {
            "subreddits": {"test": {"sorts": ["new"]}},
            "domain_monitoring": {
                "enabled": True,
                "domains": ["ripstone.com"],
                "max_pages": 99,  # Invalid: must be <= 20
                "sort": "relevance"
            }
        },
        "discord": {"servers": {}}
    }
    response = client.post('/api/clients/val_client/update', json=payload)
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["success"] is False
    assert "details" in data
    
    # Check field mappings
    fields = [d["field"] for d in data["details"]]
    assert "Client Display Name" in fields or any("Name" in f for f in fields)
    assert "Reddit -> Domain Monitoring -> Max Pages" in fields
