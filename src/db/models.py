"""Database connection and models for CommunityRadar"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from .schema import SCHEMA_SQL

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "community_radar.db"


def get_db(client_name=None):
    """Get database connection, creating schema if needed"""
    if client_name:
        db_path = DATA_DIR / "clients" / f"{client_name}.db"
    else:
        # Fallback for now, but should eventually be deprecated
        db_path = DATA_DIR / "community_radar.db"
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    # Create tables
    db.executescript(SCHEMA_SQL)
    db.commit()
    return db


def upsert_server(db, server_id, name, **kwargs):
    """Insert or update a server record"""
    existing = db.execute("SELECT id FROM servers WHERE id = ?", (server_id,)).fetchone()
    if existing:
        if kwargs:
            fields = ", ".join(f"{k}=?" for k in kwargs)
            vals = list(kwargs.values()) + [server_id]
            db.execute(f"UPDATE servers SET {fields}, updated_at=datetime('now') WHERE id=?", vals)
        else:
            db.execute("UPDATE servers SET updated_at=datetime('now') WHERE id=?", (server_id,))
    else:
        fields = ["id", "name"] + list(kwargs.keys())
        placeholders = ["?", "?"] + ["?"] * len(kwargs)
        vals = [server_id, name] + list(kwargs.values())
        db.execute(f"INSERT INTO servers ({', '.join(fields)}) VALUES ({', '.join(placeholders)})", vals)
    db.commit()


def upsert_channel(db, channel_id, server_id, name, **kwargs):
    """Insert or update a channel record"""
    existing = db.execute("SELECT id FROM channels WHERE id = ?", (channel_id,)).fetchone()
    if existing:
        if kwargs:
            fields = ", ".join(f"{k}=?" for k in kwargs)
            vals = list(kwargs.values()) + [channel_id]
            db.execute(f"UPDATE channels SET {fields}, updated_at=datetime('now') WHERE id=?", vals)
        else:
            db.execute("UPDATE channels SET updated_at=datetime('now') WHERE id=?", (channel_id,))
    else:
        fields = ["id", "server_id", "name"] + list(kwargs.keys())
        placeholders = ["?", "?", "?"] + ["?"] * len(kwargs)
        vals = [channel_id, server_id, name] + list(kwargs.values())
        db.execute(f"INSERT INTO channels ({', '.join(fields)}) VALUES ({', '.join(placeholders)})", vals)
    db.commit()


def upsert_user(db, user_id, **kwargs):
    """Insert or update a user record"""
    existing = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if existing:
        if kwargs:
            fields = ", ".join(f"{k}=?" for k in kwargs)
            vals = list(kwargs.values()) + [user_id]
            db.execute(f"UPDATE users SET {fields}, updated_at=datetime('now') WHERE id=?", vals)
        else:
            db.execute("UPDATE users SET updated_at=datetime('now') WHERE id=?", (user_id,))
    else:
        fields = ["id"] + list(kwargs.keys())
        placeholders = ["?"] + ["?"] * len(kwargs)
        vals = [user_id] + list(kwargs.values())
        db.execute(f"INSERT INTO users ({', '.join(fields)}) VALUES ({', '.join(placeholders)})", vals)
    db.commit()


def log_export(db, server_id, channel_id, messages, new_users, duration_s, status="completed", notes=None):
    """Record an export run"""
    db.execute("""
        INSERT INTO exports (server_id, channel_id, export_ts, messages, new_users, duration_s, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (server_id, channel_id, datetime.now().isoformat(), messages, new_users, duration_s, status, notes))
    db.commit()