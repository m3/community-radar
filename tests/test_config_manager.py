import pytest
from pathlib import Path
from src.dashboard.config_manager import ConfigManager

def test_yaml_round_trip(tmp_path):
    config_path = tmp_path / "config.yaml"
    initial_content = "clients:\n  test-client:\n    name: Test Client\n"
    config_path.write_text(initial_content)
    
    cm = ConfigManager(config_path)
    config = cm.load()
    config['clients']['test-client']['name'] = 'Updated Name'
    cm.save(config)
    
    updated_content = config_path.read_text()
    assert "name: Updated Name" in updated_content

def test_config_backup_created(tmp_path):
    config_path = tmp_path / "config.yaml"
    initial_content = "clients: {}\n"
    config_path.write_text(initial_content)
    
    cm = ConfigManager(config_path)
    assert not cm.backup_path.exists()
    
    cm.save({'clients': {'new': 'client'}})
    assert cm.backup_path.exists()
    assert cm.backup_path.read_text() == initial_content
