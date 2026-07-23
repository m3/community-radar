"""Tests for how the dashboard dev server is launched.

The Werkzeug debugger must never be on by default: it returns tracebacks
with source and local variables to the caller, and the container entrypoint
used to run with debug=True.
"""

import pytest

from src.dashboard import app as app_module


@pytest.fixture
def captured_run(monkeypatch):
    """Capture the kwargs run_dashboard passes to app.run without serving."""
    calls = {}

    def fake_run(*args, **kwargs):
        calls.update(kwargs)

    monkeypatch.setattr(app_module.app, "run", fake_run)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.delenv("DASHBOARD_HOST", raising=False)
    return calls


def test_debug_is_off_by_default(captured_run):
    app_module.run_dashboard()
    assert captured_run["debug"] is False


def test_does_not_bind_all_interfaces_by_default(captured_run):
    app_module.run_dashboard()
    assert captured_run["host"] == "127.0.0.1"


def test_debug_can_be_enabled_explicitly(captured_run, monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "1")
    app_module.run_dashboard()
    assert captured_run["debug"] is True


def test_host_is_overridable(captured_run, monkeypatch):
    monkeypatch.setenv("DASHBOARD_HOST", "0.0.0.0")
    app_module.run_dashboard()
    assert captured_run["host"] == "0.0.0.0"
