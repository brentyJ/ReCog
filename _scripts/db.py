"""
ReCog Database Utilities

Copyright (c) 2025 Brent Lefebure / EhkoLabs

Initialize and manage the ReCog database.
"""

import sqlite3
from pathlib import Path
from typing import Optional


# Default database location
DEFAULT_DB_NAME = "recog.db"


def get_schema_path() -> Path:
    """Get path to the schema SQL file."""
    return Path(__file__).parent / "migrations" / "schema_v0_1.sql"


def get_migrations_dir() -> Path:
    """Get path to migrations directory."""
    return Path(__file__).parent / "migrations"


def apply_migrations(db_path: Path) -> list:
    """
    Apply any pending migrations to the database.
    
    Migrations are SQL files named migration_v*.sql in the migrations directory.
    
    Args:
        db_path: Path to database
        
    Returns:
        List of applied migration names
    """
    migrations_dir = get_migrations_dir()
    applied = []
    
    # Find all migration files
    migration_files = sorted(migrations_dir.glob("migration_v*.sql"))
    
    if not migration_files:
        return applied
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    for mig_path in migration_files:
        try:
            sql = mig_path.read_text(encoding="utf-8")
            cursor.executescript(sql)
            applied.append(mig_path.name)
        except sqlite3.OperationalError as e:
            # Table already exists or similar - skip silently
            pass
        except Exception as e:
            print(f"Warning: Migration {mig_path.name} failed: {e}")
    
    conn.commit()
    conn.close()
    
    return applied


def init_database(db_path: Optional[Path] = None, force: bool = False) -> Path:
    """
    Initialize a new ReCog database.
    
    Args:
        db_path: Path for the database file (defaults to ./recog.db)
        force: If True, overwrite existing database
        
    Returns:
        Path to the created database
    """
    if db_path is None:
        db_path = Path.cwd() / DEFAULT_DB_NAME
    else:
        db_path = Path(db_path)
    
    # Check if exists
    if db_path.exists() and not force:
        print(f"Database already exists: {db_path}")
        print("Use --force to overwrite")
        return db_path
    
    # Create parent directories
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing if force
    if db_path.exists() and force:
        db_path.unlink()
        print(f"Removed existing database: {db_path}")
    
    # Read schema
    schema_path = get_schema_path()
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    
    schema_sql = schema_path.read_text(encoding="utf-8")
    
    # Create database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Execute schema
    cursor.executescript(schema_sql)
    
    conn.commit()
    conn.close()
    
    # Apply any migrations
    applied = apply_migrations(db_path)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    
    print(f"Database initialized: {db_path}")
    return db_path


def check_database(db_path: Path) -> dict:
    """
    Check database status and table counts.
    
    Args:
        db_path: Path to database
        
    Returns:
        Dict with table names and row counts
    """
    if not db_path.exists():
        return {"error": "Database not found"}
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get table list
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    result = {"tables": {}}
    
    for table in tables:
        if table.startswith("sqlite_"):
            continue
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        result["tables"][table] = count
    
    conn.close()
    
    result["total_tables"] = len(result["tables"])
    result["total_rows"] = sum(result["tables"].values())
    
    return result


def get_database_path(data_dir: Optional[Path] = None) -> Path:
    """
    Get the standard database path for a project.
    
    Args:
        data_dir: Optional data directory (defaults to ./_data)
        
    Returns:
        Path to database file
    """
    if data_dir is None:
        data_dir = Path.cwd() / "_data"
    
    return data_dir / DEFAULT_DB_NAME


# =============================================================================
# CLI
# =============================================================================

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python db.py <command> [options]")
        print()
        print("Commands:")
        print("  init [path]    Initialize new database")
        print("  check [path]   Check database status")
        print("  schema         Show schema path")
        print()
        print("Options:")
        print("  --force        Overwrite existing database")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "migrate":
        path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd() / DEFAULT_DB_NAME
        if not path.exists():
            print(f"Database not found: {path}")
            return
        applied = apply_migrations(path)
        if applied:
            print(f"Applied: {', '.join(applied)}")
        else:
            print("No migrations to apply")
    
    elif cmd == "init":
        path = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
        force = "--force" in sys.argv
        init_database(path, force=force)
    
    elif cmd == "check":
        path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd() / DEFAULT_DB_NAME
        result = check_database(path)
        
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        print(f"Database: {path}")
        print(f"Tables: {result['total_tables']}")
        print(f"Total rows: {result['total_rows']}")
        print()
        
        for table, count in sorted(result["tables"].items()):
            print(f"  {table}: {count}")
    
    elif cmd == "schema":
        print(get_schema_path())
    
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
