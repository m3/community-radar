"""ConfigManager must notice edits made by another process.

The cache was populated once and never invalidated by mtime, and
clear_cache() had no caller. The web process and the worker process hold
independent ConfigManagers, so a config edit made through the dashboard was
invisible to the worker until it restarted, and vice versa.
"""

import os
import time

import yaml

from src.dashboard.config_manager import ConfigManager


def _write(path, data):
    with open(path, "w") as f:
        yaml.dump(data, f)
    # Nudge mtime so a same-second rewrite is still detectable.
    past = time.time() - 10
    os.utime(path, (past, past))


def test_reload_after_external_edit(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write(cfg, {"clients": {"a": {}}})

    mgr = ConfigManager(cfg)
    assert set(mgr.load()["clients"]) == {"a"}

    # A different process edits the file.
    other = ConfigManager(cfg)
    other.save({"clients": {"a": {}, "b": {}}})

    assert set(mgr.load()["clients"]) == {"a", "b"}


def test_cache_is_used_when_the_file_is_unchanged(tmp_path):
    cfg = tmp_path / "config.yaml"
    _write(cfg, {"clients": {"a": {}}})

    mgr = ConfigManager(cfg)
    first = mgr.load()
    second = mgr.load()
    assert first is second  # no re-parse when mtime is unchanged


def test_missing_file_does_not_poison_a_later_create(tmp_path):
    cfg = tmp_path / "config.yaml"
    mgr = ConfigManager(cfg)
    assert mgr.load() == {}

    _write(cfg, {"clients": {"a": {}}})
    assert set(mgr.load()["clients"]) == {"a"}
