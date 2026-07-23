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


class UnknownClientError(ValueError):
    """Raised when a client name is not declared in config.yaml."""


class TenantIsolationError(RuntimeError):
    """Raised when a tenant-scoped query would run without a client_id filter."""


# Tables without a client_id column — exempt from the tenant-predicate guard.
_NON_TENANT_TABLES = {"tasks", "clients", "alembic_version", "schema_migrations"}

# Tables whose rows belong to a specific client and must always be filtered.
_TENANT_TABLES = {
    "messages", "users", "channels", "servers", "exports", "topics",
    "cross_references",
}


def tenant_guard_mode():
    """How to react to a tenant-scoped query with no client_id predicate.

    'enforce' (default) raises, 'log' warns and continues, 'off' disables the
    check. Overridable with COMMUNITY_RADAR_TENANT_GUARD for a staged rollout.
    """
    return os.environ.get("COMMUNITY_RADAR_TENANT_GUARD", "enforce").lower()


def _references_tenant_table(sql):
    lowered = sql.lower()
    return any(re.search(rf'\b{t}\b', lowered) for t in _TENANT_TABLES)


def _has_client_id_predicate(sql):
    # A predicate, not a mention: client_id compared or matched against something.
    return re.search(r'client_id\s*(=|<>|!=|\bin\b)', sql, re.IGNORECASE) is not None


def known_client_names():
    """The set of client names declared in config.yaml — the tenant authority.

    Read fresh each call: the config is editable through the dashboard, and a
    stale cache here would reject a client that was just added.
    """
    import yaml

    config_path = os.environ.get(
        "COMMUNITY_RADAR_CONFIG",
        str(os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")),
    )
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return set()
    return set(config.get("clients", {}).keys())


class LegacySessionWrapper:
    """
    Wraps an SQLAlchemy Session to provide a sqlite3-like interface
    for legacy code using .execute() and .commit().
    """
    def __init__(self, session, client_id, conn=None):
        self.session = session
        self.client_id = client_id
        # The dedicated connection the session is bound to (holds the tenant
        # GUC for RLS). Closed alongside the session.
        self._conn = conn

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
            
        # Inject client_id if not present (skip for tasks table which is global)
        is_tasks = isinstance(sql, str) and re.search(r'\b(FROM|UPDATE|INSERT\s+INTO|JOIN)\s+tasks\b', sql, re.IGNORECASE) is not None
        
        if is_tasks:
            pass
        elif ":client_id" in sql or "client_id" in sql.lower():
            if "client_id" not in params:
                params["client_id"] = self.client_id
        else:
            # Detect table aliases for qualified client_id injection
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

        self._guard_tenant_isolation(sql)

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

        # Match: INSERT INTO table (col1, col2, ...) VALUES (val1, val2, ...)
        pattern = r'(INSERT\s+(?:INTO|OR\s+IGNORE\s+INTO)\s+\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if not match:
            return sql, params

        prefix = match.group(1)  # INSERT INTO table
        cols = match.group(2)    # col1, col2, ...
        vals = match.group(3)    # val1, val2, ...

        # Only the column list decides this. Testing the whole statement would
        # also match a client_id in a trailing ON CONFLICT target, which
        # _fix_insert_or_ignore may have just added.
        if not self._is_client_scoped_insert(sql, cols):
            return sql, params

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

    def _is_client_scoped_insert(self, sql, cols):
        """Whether client_id gets injected into this INSERT's column list.

        The ON CONFLICT target must name the same columns as the unique
        constraint the row is checked against, so this single predicate decides
        both the target and the injection. `cols` is the column list only —
        `sql` is used just to spot the global `tasks` table.
        """
        if "client_id" in cols.lower():
            return False  # caller already supplied it
        if "tasks" in sql.lower():
            return False  # tasks is global and has no client_id
        return True

    def _fix_insert_or_ignore(self, sql):
        """Convert SQLite INSERT OR IGNORE to PostgreSQL INSERT ... ON CONFLICT DO NOTHING."""
        import re
        # Match: INSERT OR IGNORE INTO table (cols) VALUES (...)
        pattern = r'INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            table = match.group(1)
            cols = match.group(2).strip()
            # Build ON CONFLICT clause — use the first column as the conflict
            # target, prefixed with client_id when the row is tenant-scoped so
            # it matches UNIQUE(client_id, ...) rather than a global unique.
            first_col = cols.split(",")[0].strip()
            if self._is_client_scoped_insert(sql, cols):
                target = f"client_id, {first_col}"
            else:
                target = first_col
            sql = re.sub(pattern,
                         f'INSERT INTO {table} ({cols}) VALUES ({match.group(3)}) ON CONFLICT ({target}) DO NOTHING',
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

    def _guard_tenant_isolation(self, sql):
        """Refuse a tenant-scoped read/write that carries no client_id predicate.

        Runs on the fully rewritten SQL. INSERTs are exempt: client_id is added
        to their column list, not a WHERE clause, by _inject_client_id_insert.
        """
        mode = tenant_guard_mode()
        if mode == "off":
            return

        verb = sql.lstrip().upper()
        if not verb.startswith(("SELECT", "WITH", "UPDATE", "DELETE")):
            return
        if not _references_tenant_table(sql):
            return
        if _has_client_id_predicate(sql):
            return

        message = (
            "Tenant-scoped query has no client_id predicate after rewriting; "
            f"refusing to run it for client {self.client_id}: {' '.join(sql.split())[:200]}"
        )
        if mode == "log":
            import logging
            logging.getLogger(__name__).warning("tenant-guard: %s", message)
            return
        raise TenantIsolationError(message)

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def close(self):
        self.session.close()
        if self._conn is not None:
            self._conn.close()


def get_db(client_name=None):
    """Get database session scoped to a client, resolving client_id.

    The session is bound to one explicit connection so the tenant GUC
    (app.current_client_id) it sets stays put across commits — the row-level
    security policies read it per connection. A pooled Session that returned
    its connection on commit would otherwise leave later statements unscoped
    (RLS fails closed → zero rows). See tests/test_rls.py.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from .session import engine

    clean_name = sanitize_client_name(client_name)
    conn = engine.connect()
    session = Session(bind=conn)

    try:
        if clean_name:
            if clean_name not in known_client_names():
                raise UnknownClientError(
                    f"Unknown client '{clean_name}'. Declare it in config.yaml first."
                )
            client = session.query(Client).filter_by(name=clean_name).first()
            if not client:
                # First use of a client that is declared in config.yaml — create
                # its row. A name absent from config was rejected above, so this
                # can no longer be reached by a typo.
                client = Client(name=clean_name)
                session.add(client)
                session.commit()
                session.refresh(client)
            client_id = client.id
        else:
            # Default/system client
            client_id = 0

        # Scope this connection for RLS. Runtime connects as the non-superuser
        # radar_app role, for which the policies apply; the superuser owner used
        # by migrations and local/test runs bypasses RLS (SQL-level client_id
        # injection still enforces isolation there). Run through the session so
        # it shares the session's transaction on the bound connection; the GUC
        # is connection-level (not transaction-local) so it survives commits.
        session.execute(
            text("SELECT set_config('app.current_client_id', :cid, false)"),
            {"cid": str(client_id)},
        )
    except Exception:
        session.close()
        conn.close()
        raise

    return LegacySessionWrapper(session, client_id, conn)


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