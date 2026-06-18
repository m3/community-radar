import pytest
import json
import os
from pathlib import Path
import yaml
from src.dashboard.app import app, config_mgr

# Mock load_report inside app.py
from unittest.mock import patch

@pytest.fixture
def client(tmp_path):
    app.config['TESTING'] = True
    
    temp_config = tmp_path / "config.yaml"
    initial_config = {
        "clients": {
            "test_client": {
                "name": "Test Client",
                "reddit": {
                    "subreddits": {
                        "owned_sub": {"owned": True},
                        "external_sub": {"owned": False}
                    }
                },
                "discord": {"servers": {}}
            }
        }
    }
    with open(temp_config, "w") as f:
        yaml.dump(initial_config, f)
    
    old_path = config_mgr.config_path
    config_mgr.config_path = temp_config
    config_mgr.clear_cache()
    
    with app.test_client() as client:
        yield client
        
    config_mgr.config_path = old_path
    config_mgr.clear_cache()

def test_api_ecosystem_summary_balanced(client):
    mock_report = {
        "sentiment": {
            "by_channel": {
                "reddit-owned_sub-hot": {"total": 10, "positive": 6, "negative": 2},
                "reddit-external_sub-hot": {"total": 15, "positive": 9, "negative": 3},
                "discord-general": {"total": 5, "positive": 3, "negative": 1}
            }
        }
    }
    
    with patch("src.dashboard.app.load_report", return_value=mock_report):
        response = client.get('/api/test_client/ecosystem')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # discord-general + reddit-owned_sub-hot
        # total: 10 + 5 = 15
        # pos: 6 + 3 = 9
        # neg: 2 + 1 = 3
        # ratio: 9 / 3 = 3.0
        assert data["owned"]["total"] == 15
        assert data["owned"]["positive"] == 9
        assert data["owned"]["negative"] == 3
        assert data["owned"]["ratio"] == 3.0
        
        # reddit-external_sub-hot
        # total: 15
        # pos: 9
        # neg: 3
        # ratio: 9 / 3 = 3.0
        assert data["external"]["total"] == 15
        assert data["external"]["positive"] == 9
        assert data["external"]["negative"] == 3
        assert data["external"]["ratio"] == 3.0
        
        assert "Ecosystem is balanced" in data["insight"]

def test_api_ecosystem_summary_external_volume_dwarfs(client):
    mock_report = {
        "sentiment": {
            "by_channel": {
                "reddit-owned_sub-hot": {"total": 10, "positive": 5, "negative": 5},
                "reddit-external_sub-hot": {"total": 40, "positive": 20, "negative": 20}
            }
        }
    }
    
    with patch("src.dashboard.app.load_report", return_value=mock_report):
        response = client.get('/api/test_client/ecosystem')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "External conversation volume dwarfs owned channels" in data["insight"]

def test_api_ecosystem_summary_owned_ratio_high(client):
    mock_report = {
        "sentiment": {
            "by_channel": {
                "reddit-owned_sub-hot": {"total": 20, "positive": 15, "negative": 2}, # ratio: 15/2 = 7.5
                "reddit-external_sub-hot": {"total": 20, "positive": 6, "negative": 2} # ratio: 6/2 = 3.0
            }
        }
    }
    
    with patch("src.dashboard.app.load_report", return_value=mock_report):
        response = client.get('/api/test_client/ecosystem')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "outpaces external market" in data["insight"]

def test_api_ecosystem_summary_external_ratio_high(client):
    mock_report = {
        "sentiment": {
            "by_channel": {
                "reddit-owned_sub-hot": {"total": 20, "positive": 5, "negative": 5}, # ratio: 5/5 = 1.0
                "reddit-external_sub-hot": {"total": 20, "positive": 10, "negative": 2} # ratio: 10/2 = 5.0
            }
        }
    }
    
    with patch("src.dashboard.app.load_report", return_value=mock_report):
        response = client.get('/api/test_client/ecosystem')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert "External sentiment is noticeably higher" in data["insight"]
