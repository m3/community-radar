import pytest
import json
from src.dashboard.app import app, config_mgr
import yaml
from unittest.mock import MagicMock, patch

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
                        "billiards": {
                            "track_keywords": ["pure pool", "snooker"]
                        }
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

def test_api_raw_messages_flags_external_mention(client):
    # Mock DB response
    mock_db = MagicMock()
    mock_row_external = {
        "message_id": "1",
        "content": "I love playing pure pool on my PC",
        "channel_name": "reddit_billiards",
        "platform": "reddit",
        "timestamp": "2023-01-01T00:00:00",
        "display_name": "user1",
        "reactions": None,
        "channel_id": 1,
        "reply_to": None,
        "role": None
    }
    mock_row_normal = {
        "message_id": "2",
        "content": "Hello world",
        "channel_name": "general",
        "platform": "discord",
        "timestamp": "2023-01-01T00:00:01",
        "display_name": "user2",
        "reactions": None,
        "channel_id": 2,
        "reply_to": None,
        "role": None
    }
    
    class MockRow(dict):
        pass

    mock_db.execute.return_value.fetchall.return_value = [MockRow(mock_row_external), MockRow(mock_row_normal)]
    
    with patch('src.dashboard.app.get_db', return_value=mock_db):
        response = client.get('/api/test-client/raw_messages')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data[0]["message_id"] == "1"
        assert data[0]["is_external_mention"] is True
        
        assert data[1]["message_id"] == "2"
        assert data[1]["is_external_mention"] is False

def test_api_raw_messages_no_keywords_no_flag(client):
    # Mock DB response
    mock_db = MagicMock()
    mock_row = {
        "message_id": "3",
        "content": "just some random text",
        "channel_name": "reddit_billiards",
        "platform": "reddit",
        "timestamp": "2023-01-01T00:00:02",
        "display_name": "user3",
        "reactions": None,
        "channel_id": 1,
        "reply_to": None,
        "role": None
    }
    
    class MockRow(dict):
        pass

    mock_db.execute.return_value.fetchall.return_value = [MockRow(mock_row)]
    
    with patch('src.dashboard.app.get_db', return_value=mock_db):
        response = client.get('/api/test-client/raw_messages')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data[0]["is_external_mention"] is False
