import sqlite3
import json
from pathlib import Path
from datetime import datetime

QUEUE_DB_PATH = Path(__file__).parent.parent.parent / "data" / "queue.db"

def get_queue_db():
    QUEUE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(QUEUE_DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            command     TEXT NOT NULL,
            args_json   TEXT,
            status      TEXT DEFAULT 'pending',
            error_log   TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            started_at  TEXT,
            finished_at TEXT
        )
    ''')
    db.commit()
    return db

def enqueue_task(client_name, command, args_dict=None):
    db = get_queue_db()
    args_json = json.dumps(args_dict) if args_dict else None
    db.execute(
        "INSERT INTO tasks (client_name, command, args_json) VALUES (?, ?, ?)",
        (client_name, command, args_json)
    )
    db.commit()
    db.close()
