"""Database connection and models for CommunityRadar"""

import sqlite3
import os
import re
from datetime import datetime
from pathlib import Path
from .migrate import apply_migrations

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "community_radar.db"


def sanitize_client_name(name):
    """Sanitize client name to prevent path injection"""
    if not name:
        return None
    # Only allow alpha-numeric, hyphen, underscore
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return clean if clean else None


def get_db(client_name=None):
    """Get database connection, creating schema if needed"""
    clean_name = sanitize_client_name(client_name)
    if clean_name:
        db_path = DATA_DIR / "clients" / f"{clean_name}.db"
    else:
        # Fallback for now, but should eventually be deprecated
        db_path = DATA_DIR / "community_radar.db"

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    # Auto-migrate
    apply_migrations(db)
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