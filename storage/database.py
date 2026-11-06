"""
SQLite database architecture and connection management for LessonForge AI.
Implements WAL mode, foreign key enforcement, schema versioning,
transactional rollbacks, and connection context management.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional, Union

from config import AppConfig
from core.exceptions import DatabaseConnectionError, StorageError

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL,
        description TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS lessons (
        lesson_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        learning_objective TEXT NOT NULL,
        learner_level TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL,
        current_version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        content_json TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS lesson_versions (
        version_id TEXT PRIMARY KEY,
        lesson_id TEXT NOT NULL,
        version_number INTEGER NOT NULL,
        snapshot_json TEXT NOT NULL,
        author TEXT NOT NULL,
        change_summary TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE,
        UNIQUE (lesson_id, version_number)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS research_sources (
        source_id TEXT NOT NULL,
        lesson_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        source_type TEXT NOT NULL,
        provenance_status TEXT NOT NULL,
        credibility_score REAL NOT NULL,
        relevance_score REAL NOT NULL,
        evidence_text TEXT,
        metadata_json TEXT,
        retrieved_at TEXT,
        PRIMARY KEY (source_id, lesson_id),
        FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS qc_reports (
        report_id TEXT PRIMARY KEY,
        lesson_id TEXT NOT NULL,
        version_audited INTEGER NOT NULL,
        layer TEXT NOT NULL,
        overall_score REAL NOT NULL,
        status TEXT NOT NULL,
        report_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS recommendation_decisions (
        recommendation_id TEXT PRIMARY KEY,
        lesson_id TEXT NOT NULL,
        version_number INTEGER NOT NULL,
        issue_summary TEXT NOT NULL,
        suggested_content TEXT NOT NULL,
        status TEXT NOT NULL,
        instructor_notes TEXT,
        decision_timestamp TEXT NOT NULL,
        applied_timestamp TEXT,
        recommendation_json TEXT NOT NULL,
        FOREIGN KEY (lesson_id) REFERENCES lessons(lesson_id) ON DELETE CASCADE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_lessons_updated ON lessons(updated_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_lesson_versions_lookup ON lesson_versions(lesson_id, version_number);",
    "CREATE INDEX IF NOT EXISTS idx_research_sources_lesson ON research_sources(lesson_id);",
    "CREATE INDEX IF NOT EXISTS idx_qc_reports_lookup ON qc_reports(lesson_id, version_audited);",
    "CREATE INDEX IF NOT EXISTS idx_recommendations_lookup ON recommendation_decisions(lesson_id, version_number);",
]


class DatabaseManager:
    """
    Manages SQLite connections, transactions, schema creation, and pragmas.
    Ensures safe single-user desktop durability with foreign keys and WAL mode.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is None:
            config = AppConfig()
            config.ensure_directories()
            self.db_path = config.DATABASE_PATH
        elif db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._is_memory = self.db_path == ":memory:"
        self._memory_conn: Optional[sqlite3.Connection] = None

        if self._is_memory:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._configure_connection(self._memory_conn)

        self.init_db()

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        """Apply mandatory pragmas: foreign keys, busy timeout, WAL mode (for file DBs)."""
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        if not self._is_memory:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Yield a configured SQLite connection.
        If in-memory, yields the persistent test connection without closing it.
        If file-backed, opens connection and guarantees closure upon exit.
        """
        if self._is_memory and self._memory_conn is not None:
            yield self._memory_conn
            return

        conn = None
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=10.0,
                check_same_thread=False,
            )
            self._configure_connection(conn)
            yield conn
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f"Failed to connect to SQLite database at {self.db_path}: {e}") from e
        finally:
            if conn is not None:
                conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for atomic transaction control.
        Executes BEGIN IMMEDIATE. Commits upon normal exit; rolls back upon exception.
        """
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction rolled back due to error: {e}")
                raise

    def init_db(self, force: bool = False) -> None:
        """
        Initialize database schema and record schema version.
        Safe for repeated executions (idempotent).
        """
        with self.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()

            for stmt in DDL_STATEMENTS:
                cursor.execute(stmt)

            # Check schema version
            cursor.execute("SELECT version FROM schema_version WHERE version = ?", (SCHEMA_VERSION,))
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                    (
                        SCHEMA_VERSION,
                        datetime.now(timezone.utc).isoformat(),
                        "Initial LessonForge AI schema: lessons, versions, sources, qc_reports, recommendations",
                    ),
                )
            conn.commit()

    def close(self) -> None:
        """Close persistent in-memory connection if active."""
        if self._is_memory and self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None
