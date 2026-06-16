"""Database connection and models for CommunityRadar"""

import os
import re
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update, insert, func
from .orm import Client, Server, Channel, User, Export, Topic
from .session import SessionLocal, DATABASE_URL

def sanitize_client_name(name):
    """Sanitize client name to prevent path injection"""
    if not name:
        return None
    # Only allow alpha-numeric, hyphen, underscore
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    return clean if clean else None


class LegacySessionWrapper:
    """
    Wraps an SQLAlchemy Session to provide a sqlite3-like interface
    for legacy code using .execute() and .commit().
    """
    def __init__(self, session, client_id):
        self.session = session
        self.client_id = client_id

    def execute(self, sql, params=None):
        from sqlalchemy import text
        
        # Convert ? placeholders to :param placeholders for SQLAlchemy
        if isinstance(sql, str) and "?" in sql:
            count = 1
            while "?" in sql:
                sql = sql.replace("?", f":p{count}", 1)
                count += 1
            
            if params:
                if isinstance(params, (list, tuple)):
                    params = {f"p{i+1}": v for i, v in enumerate(params)}
                elif not isinstance(params, dict):
                    params = {"p1": params}
        
        if not params:
            params = {}
            
        # Inject client_id if not present
        if ":client_id" in sql or "client_id" in sql.lower():
            if "client_id" not in params:
                params["client_id"] = self.client_id
        else:
            # Try to inject client_id into WHERE clause
            # This is very simplified but works for many of our queries
            if " WHERE " in sql.upper():
                sql = sql.replace(" WHERE ", f" WHERE client_id = {self.client_id} AND ", 1)
            elif " GROUP BY " in sql.upper():
                sql = sql.replace(" GROUP BY ", f" WHERE client_id = {self.client_id} GROUP BY ", 1)
            elif " ORDER BY " in sql.upper():
                sql = sql.replace(" ORDER BY ", f" WHERE client_id = {self.client_id} ORDER BY ", 1)
            elif "SELECT " in sql.upper() and " FROM " in sql.upper():
                # No WHERE/GROUP/ORDER, just append at end
                sql = sql.strip()
                if sql.endswith(";"):
                    sql = sql[:-1] + f" WHERE client_id = {self.client_id};"
                else:
                    sql += f" WHERE client_id = {self.client_id}"

        # Fix SQLite-specific functions
        sql = sql.replace("datetime('now')", "func.now()") # text() doesn't understand func.now()
        sql = sql.replace("date(timestamp)", "timestamp::date") # PG syntax

        result = self.session.execute(text(sql), params)
        if sql.strip().upper().startswith("SELECT"):
            return result.mappings()
        return result

    def commit(self):
        self.session.commit()

    def close(self):
        self.session.close()


def get_db(client_name=None):
    """Get database session, resolving client_id"""
    clean_name = sanitize_client_name(client_name)
    session = SessionLocal()
    
    if clean_name:
        client = session.query(Client).filter_by(name=clean_name).first()
        if not client:
            # For now, auto-create client if it doesn't exist (to support easy onboarding)
            client = Client(name=clean_name)
            session.add(client)
            session.commit()
            session.refresh(client)
        client_id = client.id
    else:
        # Default/system client
        client_id = 0 

    return LegacySessionWrapper(session, client_id)


def upsert_server(db, server_id, name, **kwargs):
    """Insert or update a server record"""
    session = db.session
    client_id = db.client_id
    
    existing = session.query(Server).filter_by(id=server_id, client_id=client_id).first()
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
        existing.updated_at = func.now()
    else:
        server = Server(id=server_id, client_id=client_id, name=name, **kwargs)
        session.add(server)
    session.commit()


def upsert_channel(db, channel_id, server_id, name, **kwargs):
    """Insert or update a channel record"""
    session = db.session
    client_id = db.client_id
    
    existing = session.query(Channel).filter_by(id=channel_id, client_id=client_id).first()
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
        existing.updated_at = func.now()
    else:
        channel = Channel(id=channel_id, client_id=client_id, server_id=server_id, name=name, **kwargs)
        session.add(channel)
    session.commit()


def upsert_user(db, user_id, **kwargs):
    """Insert or update a user record"""
    session = db.session
    client_id = db.client_id
    
    existing = session.query(User).filter_by(id=user_id, client_id=client_id).first()
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
        existing.updated_at = func.now()
    else:
        user = User(id=user_id, client_id=client_id, **kwargs)
        session.add(user)
    session.commit()


def log_export(db, server_id, channel_id, messages, new_users, duration_s, status="completed", notes=None):
    """Record an export run"""
    session = db.session
    client_id = db.client_id
    
    export = Export(
        client_id=client_id,
        server_id=server_id,
        channel_id=channel_id,
        messages=messages,
        new_users=new_users,
        duration_s=duration_s,
        status=status,
        notes=notes
    )
    session.add(export)
    session.commit()