import pytest
import sqlite3
import json
from src.db.queue import enqueue_task, QUEUE_DB_PATH
from src.db.models import sanitize_client_name
import os

@pytest.fixture
def clean_db():
    if QUEUE_DB_PATH.exists():
        os.remove(QUEUE_DB_PATH)
    yield
    if QUEUE_DB_PATH.exists():
        os.remove(QUEUE_DB_PATH)

def test_enqueue_task_success(clean_db):
    client = "Valid Client 123"
    cmd = "run_report"
    args = {"param": "value"}
    
    enqueue_task(client, cmd, args)
    
    conn = sqlite3.connect(str(QUEUE_DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tasks").fetchone()
    
    assert row["client_name"] == sanitize_client_name(client)
    assert row["command"] == cmd
    assert json.loads(row["args_json"]) == args
    assert row["status"] == "pending"
    conn.close()

def test_enqueue_task_none_client(clean_db):
    cmd = "migrate"
    
    enqueue_task(None, cmd)
    
    conn = sqlite3.connect(str(QUEUE_DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tasks").fetchone()
    
    assert row["client_name"] is None
    assert row["command"] == cmd
    conn.close()

def test_wal_mode(clean_db):
    enqueue_task("client", "cmd")
    conn = sqlite3.connect(str(QUEUE_DB_PATH))
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    conn.close()
