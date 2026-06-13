import sqlite3
import pytest
from pathlib import Path
from src.db.migrate import apply_migrations

def test_apply_migrations(tmp_path):
    # Setup temporary migrations directory
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    
    # Create a test migration
    migration_file = migrations_dir / "001_test.sql"
    migration_file.write_text("CREATE TABLE test_table (id INTEGER PRIMARY KEY);")
    
    # Mock MIGRATIONS_DIR in migrate module
    import src.db.migrate
    original_dir = src.db.migrate.MIGRATIONS_DIR
    src.db.migrate.MIGRATIONS_DIR = migrations_dir
    
    try:
        # Create in-memory DB
        db = sqlite3.connect(":memory:")
        
        # Apply migrations
        apply_migrations(db)
        
        # Verify table exists
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
        assert cursor.fetchone() is not None
        
        # Verify migration recorded
        cursor = db.execute("SELECT version FROM schema_migrations WHERE version='001_test'")
        assert cursor.fetchone() is not None
        
        # Apply again, should not fail or duplicate
        apply_migrations(db)
        
    finally:
        src.db.migrate.MIGRATIONS_DIR = original_dir
        db.close()

def test_apply_migrations_rollback(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    
    # Create a failing migration (invalid SQL)
    migration_file = migrations_dir / "001_fail.sql"
    migration_file.write_text("CREATE TABLE fail_table (id INTEGER PRIMARY KEY); INVALID SQL;")
    
    import src.db.migrate
    original_dir = src.db.migrate.MIGRATIONS_DIR
    src.db.migrate.MIGRATIONS_DIR = migrations_dir
    
    try:
        db = sqlite3.connect(":memory:")
        
        with pytest.raises(sqlite3.Error):
            apply_migrations(db)
            
        # Table should NOT exist because of rollback
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fail_table'")
        assert cursor.fetchone() is None
        
        # Migration should NOT be recorded
        cursor = db.execute("SELECT version FROM schema_migrations WHERE version='001_fail'")
        assert cursor.fetchone() is None
        
    finally:
        src.db.migrate.MIGRATIONS_DIR = original_dir
        db.close()
