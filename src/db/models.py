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
            # Detect table aliases for qualified client_id injection
            import re
            # Find first table alias: "FROM table_name alias" or "FROM table_name AS alias"
            alias_match = re.search(r'\bFROM\s+\w+\s+(?:AS\s+)?(\w+)', sql, re.IGNORECASE)
            first_alias = alias_match.group(1) if alias_match else None

            # Check if there's a JOIN — if so, we need qualified column reference
            has_join = " JOIN " in sql.upper()

            if has_join and first_alias:
                qual = f"{first_alias}.client_id"
            else:
                qual = "client_id"

            client_id_sql = f"{qual} = {self.client_id}"

            if " WHERE " in sql.upper():
                sql = sql.replace(" WHERE ", f" WHERE {client_id_sql} AND ", 1)
            elif " GROUP BY " in sql.upper():
                sql = sql.replace(" GROUP BY ", f" WHERE {client_id_sql} GROUP BY ", 1)
            elif " ORDER BY " in sql.upper():
                sql = sql.replace(" ORDER BY ", f" WHERE {client_id_sql} ORDER BY ", 1)
            elif "SELECT " in sql.upper() and " FROM " in sql.upper():
                sql = sql.strip()
                if sql.endswith(";"):
                    sql = sql[:-1] + f" WHERE {client_id_sql};"
                else:
                    sql += f" WHERE {client_id_sql}"

        # Fix SQLite-specific functions
        sql = sql.replace("datetime('now')", "NOW()")
        sql = sql.replace("date(timestamp)", "timestamp::date") # PG syntax

        # Fix SQLite INSERT OR IGNORE → PostgreSQL INSERT ... ON CONFLICT DO NOTHING
        sql = self._fix_insert_or_ignore(sql)

        # Inject client_id into INSERT statements that don't include it
        sql, params = self._inject_client_id_insert(sql, params)

        result = self.session.execute(text(sql), params)
        if sql.strip().upper().startswith(("SELECT", "WITH")):
            return result.mappings()
        return result

    def _inject_client_id_insert(self, sql, params):
        """For INSERT statements without client_id, inject it into cols and values."""
        import re
        upper = sql.upper().strip()
        if not upper.startswith("INSERT "):
            return sql, params
        if "client_id" in sql.lower():
            return sql, params  # already has client_id

        # Match: INSERT INTO table (col1, col2, ...) VALUES (val1, val2, ...)
        pattern = r'(INSERT\s+(?:INTO|OR\s+IGNORE\s+INTO)\s+\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if not match:
            return sql, params

        prefix = match.group(1)  # INSERT INTO table
        cols = match.group(2)    # col1, col2, ...
        vals = match.group(3)    # val1, val2, ...

        new_cols = "client_id, " + cols
        new_vals = ":client_id, " + vals

        sql = sql[:match.start()] + f"{prefix} ({new_cols}) VALUES ({new_vals})" + sql[match.end():]

        # Add client_id to params
        if isinstance(params, dict):
            params["client_id"] = self.client_id
        elif isinstance(params, (list, tuple)):
            params = (self.client_id,) + tuple(params)
        elif params is None:
            params = {"client_id": self.client_id}

        return sql, params

    def _fix_insert_or_ignore(self, sql):
        """Convert SQLite INSERT OR IGNORE to PostgreSQL INSERT ... ON CONFLICT DO NOTHING."""
        import re
        # Match: INSERT OR IGNORE INTO table (cols) VALUES (...)
        pattern = r'INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            table = match.group(1)
            cols = match.group(2).strip()
            # Build ON CONFLICT clause — use the first column as the conflict target
            first_col = cols.split(",")[0].strip()
            sql = re.sub(pattern,
                         f'INSERT INTO {table} ({cols}) VALUES ({match.group(3)}) ON CONFLICT ({first_col}) DO NOTHING',
                         sql, flags=re.IGNORECASE)
        return sql

    def executemany(self, sql, params_list):
        """Execute the same SQL statement against a list of parameter tuples."""
        from sqlalchemy import text

        for params in params_list:
            # Reuse the same placeholder conversion logic from execute()
            sql_converted = sql
            if isinstance(sql_converted, str) and "?" in sql_converted:
                count = 1
                while "?" in sql_converted:
                    sql_converted = sql_converted.replace("?", f":p{count}", 1)
                    count += 1
                if isinstance(params, (list, tuple)):
                    params = {f"p{i+1}": v for i, v in enumerate(params)}
                elif not isinstance(params, dict):
                    params = {"p1": params}
            if not params:
                params = {}
            # Apply the same SQLite→PG fixes
            sql_converted = self._fix_insert_or_ignore(sql_converted)
            sql_converted, params = self._inject_client_id_insert(sql_converted, params)
            self.session.execute(text(sql_converted), params)

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