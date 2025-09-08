from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.engine import Connection
from app.db.database import engine

MIGRATION_KEY_MULTI_DEPT = "2025-09-02_multi_department_reports"
MIGRATION_KEY_BACKFILL_USER_DEPTS = "2025-09-02_backfill_user_departments"


# ----------------- yardımcılar -----------------

def _exec(conn: Connection, sql: str, params: Optional[dict[str, Any]] = None):
    conn.exec_driver_sql(sql, params or {})

def _table_exists(conn: Connection, name: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n", {"n": name}
    ).fetchone()
    return row is not None

def _col_exists(conn: Connection, table: str, col: str) -> bool:
    rows = conn.exec_driver_sql(f"PRAGMA table_info('{table}')").fetchall()
    return any(r[1] == col for r in rows)

def _ensure_schema_migrations_table(conn: Connection):
    _exec(
        conn,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            key TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """,
    )

def _is_applied(conn: Connection, key: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM schema_migrations WHERE key=:k", {"k": key}
    ).fetchone()
    return row is not None

def _mark_applied(conn: Connection, key: str):
    _exec(
        conn,
        "INSERT OR IGNORE INTO schema_migrations (key, applied_at) VALUES (:k, :t)",
        {"k": key, "t": datetime.utcnow().isoformat()},
    )


# ----------------- migrations -----------------

def _apply_multi_department(conn: Connection):
    """
    1) user_departments (çoktan-çoka) tablosu yoksa oluştur.
    2) reports tablosunda department_id yoksa tabloyu yeniden kur ve veriyi taşı.
    """
    # 1) user_departments
    _exec(
        conn,
        """
        CREATE TABLE IF NOT EXISTS user_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            department_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, department_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(department_id) REFERENCES departments(id) ON DELETE CASCADE
        )
        """,
    )

    # 2) reports: department_id var mı?
    if _col_exists(conn, "reports", "department_id"):
        return  # zaten yeni şema

    # FK'leri kapat (SQLite alter sırasında)
    _exec(conn, "PRAGMA foreign_keys=OFF")

    # Varsayılan departman (yoksa oluştur)
    row = conn.exec_driver_sql("SELECT id FROM departments ORDER BY id LIMIT 1").fetchone()
    if row:
        default_dept_id = row[0]
    else:
        _exec(
            conn,
            "INSERT INTO departments (name, created_at) VALUES ('Genel', datetime('now'))",
        )
        default_dept_id = conn.exec_driver_sql(
            "SELECT id FROM departments WHERE name='Genel' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]

    # reports'u geçici isme taşı
    _exec(conn, "ALTER TABLE reports RENAME TO reports_old")

    # yeni reports tablosu
    _exec(
        conn,
        """
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            department_id INTEGER NOT NULL,
            date DATE NOT NULL,
            content TEXT NOT NULL,
            project VARCHAR(120),
            tags_json TEXT,
            created_at DATETIME NOT NULL DEFAULT (datetime('now')),
            updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(department_id) REFERENCES departments(id) ON DELETE CASCADE,
            UNIQUE(user_id, department_id, date)
        )
        """,
    )

    # veri taşı: department_id = users.department_id || user_departments[0] || default
    _exec(
        conn,
        """
        INSERT INTO reports (id, user_id, department_id, date, content, project, tags_json, created_at, updated_at)
        SELECT r.id,
               r.user_id,
               COALESCE(
                   u.department_id,
                   (SELECT ud.department_id FROM user_departments ud WHERE ud.user_id=r.user_id LIMIT 1),
                   :defid
               ) AS department_id,
               r.date, r.content, r.project, r.tags_json, r.created_at, r.updated_at
        FROM reports_old r
        LEFT JOIN users u ON u.id = r.user_id
        """,
        {"defid": default_dept_id},
    )

    _exec(conn, "DROP TABLE reports_old")
    _exec(conn, "PRAGMA foreign_keys=ON")


def _backfill_user_departments(conn: Connection):
    """
    Eski users.department_id değerlerini user_departments tablosuna kopyala.
    Idempotent: INSERT OR IGNORE.
    """
    _exec(
        conn,
        """
        INSERT OR IGNORE INTO user_departments (user_id, department_id, created_at)
        SELECT id AS user_id, department_id, datetime('now')
        FROM users
        WHERE department_id IS NOT NULL
        """
    )


# ----------------- dışa açık -----------------

def safe_run_migrations():
    """
    Uygulama başlangıcında çağrılır. Adımlar idempotent çalışır.
    """
    with engine.begin() as conn:
        _ensure_schema_migrations_table(conn)

        if not _is_applied(conn, MIGRATION_KEY_MULTI_DEPT):
            _apply_multi_department(conn)
            _mark_applied(conn, MIGRATION_KEY_MULTI_DEPT)

        if not _is_applied(conn, MIGRATION_KEY_BACKFILL_USER_DEPTS):
            _backfill_user_departments(conn)
            _mark_applied(conn, MIGRATION_KEY_BACKFILL_USER_DEPTS)
