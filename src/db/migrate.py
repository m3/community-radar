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
            
            # Use transaction for atomicity
            try:
                db.executescript("BEGIN;\n" + script)
                db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"    ✗ Failed to apply {version}: {e}")
                raise
