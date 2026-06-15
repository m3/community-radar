# Multi-Tenant Migrations Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a lightweight, custom migration runner for SQLite that handles schema versioning across multiple isolated client databases.

**Architecture:** We use raw `sqlite3`, so Alembic is unnecessary overhead. We will move the hardcoded schema into `src/db/migrations/001_initial_schema.sql`. A new `src/db/migrate.py` module will apply un-run `.sql` files sequentially and record them in a `schema_migrations` table. `get_db()` will automatically apply pending migrations upon connection to ensure schemas are always up-to-date.

**Tech Stack:** Python, SQLite, standard library.

---

### Task 1: Establish Migrations Directory & Initial Schema

**Files:**
- Create: `src/db/migrations/001_initial_schema.sql`
- Modify: `src/db/schema.py` (Delete or hollow out)

- [ ] **Step 1: Extract `SCHEMA_SQL` to migration file**

Create `src/db/migrations/001_initial_schema.sql` and copy the contents of `SCHEMA_SQL` from `src/db/schema.py` into it.

- [ ] **Step 2: Add `schema_migrations` table**

At the top of `001_initial_schema.sql`, add:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);
```

- [ ] **Step 3: Remove `SCHEMA_SQL` from `src/db/schema.py`**

Delete `src/db/schema.py` or clear its contents, as it is no longer the source of truth for the schema. (Let's delete it if it's empty, or remove the `SCHEMA_SQL` constant). Since it's only `SCHEMA_SQL`, you can delete the file and update `models.py` imports in the next task.

- [ ] **Step 4: Commit**

```bash
git add src/db/migrations/001_initial_schema.sql src/db/schema.py
git commit -m "feat(db): establish migrations directory and initial schema"
```

---

### Task 2: Build the Migration Runner

**Files:**
- Create: `src/db/migrate.py`

- [ ] **Step 1: Implement `apply_migrations` logic**

```python
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

def apply_migrations(db: sqlite3.Connection):
    """Apply all pending migrations to the provided database connection."""
    # Ensure migrations table exists (catch-22 for fresh DBs, so we run a raw CREATE first)
    db.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    
    # Get applied migrations
    applied = set(row[0] for row in db.execute("SELECT version FROM schema_migrations").fetchall())
    
    # Get available migrations
    if not MIGRATIONS_DIR.exists():
        return
        
    migration_files = sorted(f for f in MIGRATIONS_DIR.glob("*.sql"))
    
    for mf in migration_files:
        version = mf.stem
        if version not in applied:
            print(f"    Applying migration {version}...")
            with open(mf, "r") as f:
                script = f.read()
            
            # Use transaction
            try:
                db.executescript(script)
                db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"    ✗ Failed to apply {version}: {e}")
                raise
```

- [ ] **Step 2: Commit**

```bash
git add src/db/migrate.py
git commit -m "feat(db): build lightweight sqlite migration runner"
```

---

### Task 3: Integrate Auto-Migration into `get_db`

**Files:**
- Modify: `src/db/models.py`

- [ ] **Step 1: Update `get_db` to use `apply_migrations`**

Remove the import of `SCHEMA_SQL`. Import `apply_migrations` from `.migrate`. 
Replace `db.executescript(SCHEMA_SQL)` with `apply_migrations(db)`.

```python
# Remove: from .schema import SCHEMA_SQL
from .migrate import apply_migrations

def get_db(client_name=None):
    # ... connection setup ...
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    
    # Auto-migrate
    apply_migrations(db)
    
    return db
```

- [ ] **Step 2: Handle legacy `community_radar.db` case gracefully**

If an old database exists that has the schema but NO `schema_migrations` table, `apply_migrations` running `001_initial_schema.sql` is safe because all the `CREATE TABLE` statements use `IF NOT EXISTS`.

- [ ] **Step 3: Test connection**

Run: `uv run python -c "from src.db.models import get_db; db = get_db('pure-pool-pro'); print('DB OK')"`
Expected: Output showing migration applied (or just "DB OK" if already schema complete, but it should insert `001_initial_schema` into the new tracking table).

- [ ] **Step 4: Commit**

```bash
git add src/db/models.py
git commit -m "feat(db): integrate auto-migration into database connection"
```

---

### Task 4: Add CLI Migration Tool

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Add `migrate` command to `src/main.py`**

```python
def migrate_dbs(args):
    """Run database migrations for all clients or a specific client"""
    from src.db.models import get_db
    config = load_config()
    
    clients_to_migrate = [args.client] if args.client else get_available_clients(config)
    
    for client in clients_to_migrate:
        print(f"\nMigrating database for {client}...")
        # get_db automatically applies migrations
        db = get_db(client)
        db.close()
        print(f"✅ {client} migration complete.")
```

- [ ] **Step 2: Register command in parser**

```python
    migrate_parser = subparsers.add_parser("migrate", help="Run database migrations (can be scoped with --client)")
    # Note: 'migrate' does not require --client, it defaults to all if omitted.
```

- [ ] **Step 3: Add to `commands` mapping**

```python
    commands = {
        # ...
        "migrate": migrate_dbs,
    }
```

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat(cli): add migrate command for bulk schema updates"
```