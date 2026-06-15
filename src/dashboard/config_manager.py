import yaml
import os
import shutil
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.backup_path = self.config_path.with_suffix('.yaml.bak')
        self._cache = None

    def load(self):
        if self._cache is not None:
            return self._cache
            
        if not self.config_path.exists():
            return {}
        with open(self.config_path, 'r') as f:
            self._cache = yaml.safe_load(f) or {}
        return self._cache

    def save(self, config_dict):
        # Create backup if not exists
        if self.config_path.exists() and not self.backup_path.exists():
            shutil.copy(self.config_path, self.backup_path)
            
        tmp_path = self.config_path.with_suffix('.yaml.tmp')
        with open(tmp_path, 'w') as f:
            yaml.dump(config_dict, f, sort_keys=False, default_flow_style=False)
        
        # Atomic rename
        os.replace(tmp_path, self.config_path)
        self._cache = config_dict

    def clear_cache(self):
        self._cache = None
