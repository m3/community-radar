import yaml
import os
import shutil
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.backup_path = self.config_path.with_suffix('.yaml.bak')
        self._cache = None
        self._cache_mtime = None

    def load(self):
        # Reload when the file's mtime has moved since we cached it. The web
        # and worker processes each hold their own ConfigManager, so an edit
        # made by one must be picked up by the other without a restart.
        try:
            mtime = os.path.getmtime(self.config_path)
        except OSError:
            return {} if self._cache is None else self._cache

        if self._cache is not None and mtime == self._cache_mtime:
            return self._cache

        with open(self.config_path, 'r') as f:
            self._cache = yaml.safe_load(f) or {}
        self._cache_mtime = mtime
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
        try:
            self._cache_mtime = os.path.getmtime(self.config_path)
        except OSError:
            self._cache_mtime = None

    def clear_cache(self):
        self._cache = None
        self._cache_mtime = None
