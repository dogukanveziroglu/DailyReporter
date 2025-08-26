from __future__ import annotations
from sqlalchemy import text, inspect
from app.db.database import engine
import sys
import traceback

MIGRATION_KEY = "20250820_add_parent_comment_id"

def _ensure_schema_migrations_table(conn) -> None:
    conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            key TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    """)

def _is_applied(conn, key: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM schema_migrations WHERE key = :k",
        {"k": key}
    ).fetchone()
    return bool(row)

def _mark_applied(conn, key: str) -> None:
    conn.exec_driver_sql(
        "INSERT OR IGNORE INTO schema_migrations(key) VALUES (:k)",
        {"k": key}
    )

def _comments_has_parent_column(conn) -> bool:
    # SQLite: PRAGMA table_info
    rows = conn.exec_driver_sql("PRAGMA table_info('comments')").fetchall()
    cols = [r[1] for r in rows]  # (cid, name, type, notnull, dflt_value, pk)
    return "parent_comment_id" in cols

def _apply_20250820_add_parent_comment_id(conn) -> None:
    """comments.parent_comment_id sütununu ve indexini ekler (varsa atlar)."""
    if not _comments_has_parent_column(conn):
        conn.exec_driver_sql("ALTER TABLE comments ADD COLUMN parent_comment_id INTEGER NULL")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_comment_id)")

def run_one_time_migrations() -> None:
    """İlk açılışta çalışır, uygulandıysa tekrar çalışmaz."""
    with engine.begin() as conn:
        _ensure_schema_migrations_table(conn)
        if _is_applied(conn, MIGRATION_KEY):
            # Daha önce uygulanmış → çık
            return
        # Tablolar kurulduktan sonra comments’e ek sütunu uygula
        _apply_20250820_add_parent_comment_id(conn)
        _mark_applied(conn, MIGRATION_KEY)

def safe_run_migrations() -> None:
    """Hata durumunda uygulamayı çökertmez; loglar ve devam eder."""
    try:
        run_one_time_migrations()
    except Exception as e:
        print("[migrations] WARNING:", e)
        traceback.print_exc(file=sys.stdout)

if __name__ == "__main__":
    # Manuel çalıştırmak istersen: python -m app.db.migrations
    safe_run_migrations()
    print("Done.")
