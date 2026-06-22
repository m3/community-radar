import pytest
import json
import yaml
from unittest.mock import MagicMock, patch
from src.dashboard.app import app, config_mgr

@pytest.fixture
def client(tmp_path):
    app.config['TESTING'] = True
    temp_config = tmp_path / "config.yaml"
    initial_config = {
        "clients": {
            "test-client": {
                "name": "Test Client",
                "reddit": {
                    "subreddits": {
                        "owned_sub": {"owned": True},
                        "external_sub": {"owned": False}
                    }
                }
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

def test_api_sentiment_by_channel_segmentation(client):
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
        # segment = owned: should only return reddit-owned_sub-hot and discord-general
        response = client.get('/api/test-client/sentiment/by_channel?segment=owned')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "reddit-owned_sub-hot" in data
        assert "discord-general" in data
        assert "reddit-external_sub-hot" not in data
        
        # segment = external: should only return reddit-external_sub-hot
        response = client.get('/api/test-client/sentiment/by_channel?segment=external')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "reddit-external_sub-hot" in data
        assert "reddit-owned_sub-hot" not in data
        assert "discord-general" not in data

def test_api_overview_segmentation(client):
    with patch("src.dashboard.app.get_channel_segmentation", return_value=(["owned_id"], ["external_id"])):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = [{"platform": "discord", "count": 5}]
        # mock returns for MIN/MAX ts, channels, users
        mock_db.execute.return_value.fetchone.return_value = {"min_ts": "2026-06-20", "max_ts": "2026-06-22", "c": 1}
        
        with patch("src.dashboard.app.get_db", return_value=mock_db):
            response = client.get('/api/test-client/overview?segment=owned')
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data["channels"] == 1
            
            called_args = mock_db.execute.call_args_list
            query_passed = any("channel_id IN" in args[0][0] for args in called_args)
            assert query_passed is True
