"""
Lesson repository and SQLite persistence layer for LessonForge AI.
Handles transactional CRUD operations for lessons, immutable version history,
research citations, dual QC reports, and instructor recommendation decisions.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Union

from core.exceptions import (
    LessonNotFoundError,
    StorageError,
    ValidationError,
    VersionNotFoundError,
)
from core.schemas import (
    LearnerLevel,
    LessonPlan,
    ProvenanceStatus,
    QCLayer,
    QCReport,
    Recommendation,
    RecommendationStatus,
    ResearchSource,
    SourceType,
)
from quality_control.qc_schemas import DetailedQCReport
from storage.database import DatabaseManager

logger = logging.getLogger(__name__)


class LessonRepository:
    """
    Repository interface for LessonForge AI domain entities.
    Enforces relational invariants, versioning immutability, and transactional rollbacks.
    """

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self.db = db or DatabaseManager()

    # -----------------------------------------------------------------------
    # Lesson CRUD & Versioning Operations
    # -----------------------------------------------------------------------
    def save_lesson(
        self,
        lesson_plan: LessonPlan,
        author: str = "SYSTEM_GENERATOR",
        change_summary: str = "Initial lesson synthesis",
    ) -> LessonPlan:
        """
        Persist a lesson plan.
        - If new, creates the base record in `lessons` and inserts version 1 in `lesson_versions`.
        - If existing and content changed, creates a new immutable version in `lesson_versions`
          and updates `lessons` to point to the latest version.
        - If existing and content is unchanged, returns idempotently without creating duplicate versions.
        """
        if not isinstance(lesson_plan, LessonPlan):
            raise ValidationError("Expected a valid LessonPlan instance.")

        lesson_id = lesson_plan.lesson_id
        content_json = lesson_plan.model_dump_json()
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_version, content_json FROM lessons WHERE lesson_id = ?", (lesson_id,))
            existing = cursor.fetchone()

            if existing is None:
                # 1. New Lesson: Insert into lessons
                cursor.execute(
                    """
                    INSERT INTO lessons (
                        lesson_id, title, learning_objective, learner_level,
                        duration_minutes, current_version, created_at, updated_at, content_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lesson_id,
                        lesson_plan.title,
                        lesson_plan.learning_objective,
                        lesson_plan.learner_level.value,
                        lesson_plan.total_duration_minutes,
                        lesson_plan.version,
                        lesson_plan.created_at or now_iso,
                        now_iso,
                        content_json,
                    ),
                )

                # 2. Insert initial version into lesson_versions
                version_id = f"ver_{lesson_id}_v{lesson_plan.version}_{uuid.uuid4().hex[:6]}"
                cursor.execute(
                    """
                    INSERT INTO lesson_versions (
                        version_id, lesson_id, version_number, snapshot_json, author, change_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        lesson_id,
                        lesson_plan.version,
                        content_json,
                        author,
                        change_summary,
                        now_iso,
                    ),
                )
            else:
                current_ver = existing["current_version"]
                existing_json = existing["content_json"]

                # If content is identical, do nothing (idempotent)
                if existing_json == content_json and current_ver == lesson_plan.version:
                    return lesson_plan

                # Calculate target version: always strictly greater than current
                target_ver = max(current_ver + 1, lesson_plan.version)
                lesson_plan.version = target_ver
                updated_content_json = lesson_plan.model_dump_json()

                # Insert new version record
                version_id = f"ver_{lesson_id}_v{target_ver}_{uuid.uuid4().hex[:6]}"
                cursor.execute(
                    """
                    INSERT INTO lesson_versions (
                        version_id, lesson_id, version_number, snapshot_json, author, change_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        lesson_id,
                        target_ver,
                        updated_content_json,
                        author,
                        change_summary,
                        now_iso,
                    ),
                )

                # Update current record in lessons
                cursor.execute(
                    """
                    UPDATE lessons SET
                        title = ?,
                        learning_objective = ?,
                        learner_level = ?,
                        duration_minutes = ?,
                        current_version = ?,
                        updated_at = ?,
                        content_json = ?
                    WHERE lesson_id = ?
                    """,
                    (
                        lesson_plan.title,
                        lesson_plan.learning_objective,
                        lesson_plan.learner_level.value,
                        lesson_plan.total_duration_minutes,
                        target_ver,
                        now_iso,
                        updated_content_json,
                        lesson_id,
                    ),
                )

            # Automatically persist bibliography sources if present
            if lesson_plan.references:
                self._save_sources_internal(cursor, lesson_id, lesson_plan.references)

        return lesson_plan

    def get_lesson(self, lesson_id: str) -> Optional[LessonPlan]:
        """Retrieve the current active version of a lesson."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content_json FROM lessons WHERE lesson_id = ?", (lesson_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return LessonPlan.model_validate_json(row["content_json"])

    def list_lessons(self) -> List[dict[str, Any]]:
        """List summary metadata for all stored lessons, sorted by updated_at DESC."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT lesson_id, title, learning_objective, learner_level,
                       duration_minutes, current_version, created_at, updated_at
                FROM lessons
                ORDER BY updated_at DESC
                """
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def save_lesson_version(
        self,
        lesson_plan: LessonPlan,
        author: str = "INSTRUCTOR",
        change_summary: str = "Manual edit applied",
    ) -> int:
        """
        Explicitly create a new immutable version snapshot for an existing lesson.
        Returns the created version number.
        """
        lesson_id = lesson_plan.lesson_id
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_version FROM lessons WHERE lesson_id = ?", (lesson_id,))
            row = cursor.fetchone()
            if row is None:
                raise LessonNotFoundError(f"Cannot save version for non-existent lesson '{lesson_id}'.")

            current_ver = row["current_version"]
            next_ver = max(current_ver + 1, lesson_plan.version)
            lesson_plan.version = next_ver
            snapshot_json = lesson_plan.model_dump_json()

            version_id = f"ver_{lesson_id}_v{next_ver}_{uuid.uuid4().hex[:6]}"
            cursor.execute(
                """
                INSERT INTO lesson_versions (
                    version_id, lesson_id, version_number, snapshot_json, author, change_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    lesson_id,
                    next_ver,
                    snapshot_json,
                    author,
                    change_summary,
                    now_iso,
                ),
            )

            cursor.execute(
                """
                UPDATE lessons SET
                    title = ?,
                    learning_objective = ?,
                    learner_level = ?,
                    duration_minutes = ?,
                    current_version = ?,
                    updated_at = ?,
                    content_json = ?
                WHERE lesson_id = ?
                """,
                (
                    lesson_plan.title,
                    lesson_plan.learning_objective,
                    lesson_plan.learner_level.value,
                    lesson_plan.total_duration_minutes,
                    next_ver,
                    now_iso,
                    snapshot_json,
                    lesson_id,
                ),
            )

            return next_ver

    def get_lesson_versions(self, lesson_id: str) -> List[dict[str, Any]]:
        """Retrieve complete version history for a lesson."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Ensure lesson exists
            cursor.execute("SELECT 1 FROM lessons WHERE lesson_id = ?", (lesson_id,))
            if cursor.fetchone() is None:
                raise LessonNotFoundError(f"Lesson '{lesson_id}' not found.")

            cursor.execute(
                """
                SELECT version_id, version_number, author, change_summary, created_at, snapshot_json
                FROM lesson_versions
                WHERE lesson_id = ?
                ORDER BY version_number ASC
                """,
                (lesson_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "version_id": r["version_id"],
                    "version_number": r["version_number"],
                    "author": r["author"],
                    "change_summary": r["change_summary"],
                    "created_at": r["created_at"],
                    "lesson_plan": LessonPlan.model_validate_json(r["snapshot_json"]),
                }
                for r in rows
            ]

    def get_lesson_version(self, lesson_id: str, version_number: int) -> Optional[LessonPlan]:
        """Retrieve a specific historical immutable version snapshot of a lesson."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT snapshot_json FROM lesson_versions WHERE lesson_id = ? AND version_number = ?",
                (lesson_id, version_number),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return LessonPlan.model_validate_json(row["snapshot_json"])

    def delete_lesson(self, lesson_id: str) -> bool:
        """
        Delete a lesson and all cascading child entities (versions, sources, QC reports, decisions).
        Returns True if deleted, False if not found.
        """
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM lessons WHERE lesson_id = ?", (lesson_id,))
            return cursor.rowcount > 0

    # -----------------------------------------------------------------------
    # Research Sources Persistence
    # -----------------------------------------------------------------------
    def _save_sources_internal(self, cursor: sqlite3.Cursor, lesson_id: str, sources: List[ResearchSource]) -> int:
        """Internal helper to upsert research sources using an active cursor."""
        for src in sources:
            metadata_str = json.dumps(src.metadata) if src.metadata else None
            cursor.execute(
                """
                INSERT OR REPLACE INTO research_sources (
                    source_id, lesson_id, url, title, source_type,
                    provenance_status, credibility_score, relevance_score,
                    evidence_text, metadata_json, retrieved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    src.id,
                    lesson_id,
                    src.url,
                    src.title,
                    src.source_type.value,
                    src.provenance.value,
                    src.credibility_score,
                    float(src.metadata.get("relevance_score", 0.8)),
                    src.snippet_or_summary,
                    metadata_str,
                    src.retrieval_date,
                ),
            )
        return len(sources)

    def save_research_sources(self, lesson_id: str, sources: List[ResearchSource]) -> int:
        """Persist a list of research sources linked to a lesson."""
        if not sources:
            return 0

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM lessons WHERE lesson_id = ?", (lesson_id,))
            if cursor.fetchone() is None:
                raise LessonNotFoundError(f"Cannot link research sources to non-existent lesson '{lesson_id}'.")

            return self._save_sources_internal(cursor, lesson_id, sources)

    def get_research_sources(self, lesson_id: str) -> List[ResearchSource]:
        """Retrieve all research citations associated with a lesson."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT source_id, url, title, source_type, provenance_status,
                       credibility_score, evidence_text, metadata_json, retrieved_at
                FROM research_sources
                WHERE lesson_id = ?
                ORDER BY credibility_score DESC
                """,
                (lesson_id,),
            )
            rows = cursor.fetchall()

            results: List[ResearchSource] = []
            for r in rows:
                meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
                results.append(
                    ResearchSource(
                        id=r["source_id"],
                        source_type=SourceType(r["source_type"]),
                        title=r["title"],
                        url=r["url"],
                        snippet_or_summary=r["evidence_text"] or "",
                        provenance=ProvenanceStatus(r["provenance_status"]),
                        credibility_score=r["credibility_score"],
                        retrieval_date=r["retrieved_at"] or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        metadata=meta,
                    )
                )
            return results

    # -----------------------------------------------------------------------
    # QC Reports Persistence
    # -----------------------------------------------------------------------
    def save_qc_report(self, report: Union[DetailedQCReport, QCReport]) -> str:
        """Persist an independent QC audit report linked to a lesson and version."""
        if not isinstance(report, (DetailedQCReport, QCReport)):
            raise ValidationError("Expected a valid QCReport or DetailedQCReport.")

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM lessons WHERE lesson_id = ?", (report.lesson_id,))
            if cursor.fetchone() is None:
                raise LessonNotFoundError(f"Cannot save QC report for non-existent lesson '{report.lesson_id}'.")

            report_json = report.model_dump_json()
            cursor.execute(
                """
                INSERT OR REPLACE INTO qc_reports (
                    report_id, lesson_id, version_audited, layer,
                    overall_score, status, report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.lesson_id,
                    report.version_audited,
                    report.layer.value,
                    report.overall_score,
                    report.status.value,
                    report_json,
                    report.evaluated_at or datetime.now(timezone.utc).isoformat(),
                ),
            )
            return report.report_id

    def get_qc_reports(
        self,
        lesson_id: str,
        version_number: Optional[int] = None,
        layer: Optional[Union[QCLayer, str]] = None,
    ) -> List[DetailedQCReport]:
        """
        Retrieve QC reports for a lesson, with optional filtering by version and layer.
        Deserializes reports into DetailedQCReport models.
        """
        query = "SELECT report_json FROM qc_reports WHERE lesson_id = ?"
        params: List[Any] = [lesson_id]

        if version_number is not None:
            query += " AND version_audited = ?"
            params.append(version_number)

        if layer is not None:
            layer_val = layer.value if isinstance(layer, QCLayer) else str(layer)
            query += " AND layer = ?"
            params.append(layer_val)

        query += " ORDER BY created_at ASC"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [DetailedQCReport.model_validate_json(r["report_json"]) for r in rows]

    # -----------------------------------------------------------------------
    # Recommendation Decisions Persistence
    # -----------------------------------------------------------------------
    def save_recommendation(
        self,
        recommendation: Recommendation,
        lesson_id: str,
        version_number: int = 1,
    ) -> str:
        """Insert or update a full recommendation record linked to a lesson."""
        if not isinstance(recommendation, Recommendation):
            raise ValidationError("Expected a valid Recommendation instance.")

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM lessons WHERE lesson_id = ?", (lesson_id,))
            if cursor.fetchone() is None:
                raise LessonNotFoundError(f"Cannot save recommendation for non-existent lesson '{lesson_id}'.")

            now_iso = datetime.now(timezone.utc).isoformat()
            rec_json = recommendation.model_dump_json()

            cursor.execute(
                """
                INSERT OR REPLACE INTO recommendation_decisions (
                    recommendation_id, lesson_id, version_number, issue_summary,
                    suggested_content, status, instructor_notes, decision_timestamp,
                    applied_timestamp, recommendation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation.id,
                    lesson_id,
                    version_number,
                    recommendation.issue_summary,
                    recommendation.suggested_content,
                    recommendation.status.value,
                    recommendation.instructor_notes,
                    now_iso,
                    now_iso if recommendation.status == RecommendationStatus.APPLIED else None,
                    rec_json,
                ),
            )
            return recommendation.id

    def save_recommendation_decision(
        self,
        rec_id: Union[str, Recommendation],
        status: Optional[Union[RecommendationStatus, str]] = None,
        notes: Optional[str] = None,
        lesson_id: Optional[str] = None,
        version_number: int = 1,
    ) -> str:
        """
        Record or update an instructor's decision for a recommendation.
        Supports both Recommendation object or (rec_id, status, notes) signature.
        """
        if isinstance(rec_id, Recommendation):
            target_lesson = lesson_id or getattr(rec_id, "lesson_id", None)
            if not target_lesson:
                raise ValidationError("lesson_id required when passing Recommendation object without attached lesson_id.")
            return self.save_recommendation(rec_id, target_lesson, version_number)

        # Updating existing recommendation decision by ID
        target_id = str(rec_id)
        status_val = status.value if isinstance(status, RecommendationStatus) else str(status)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT recommendation_json FROM recommendation_decisions WHERE recommendation_id = ?", (target_id,))
            row = cursor.fetchone()
            if row is None:
                raise StorageError(f"Recommendation '{target_id}' not found to record decision.")

            # Update embedded JSON model
            rec_obj = Recommendation.model_validate_json(row["recommendation_json"])
            rec_obj.status = RecommendationStatus(status_val)
            if notes is not None:
                rec_obj.instructor_notes = notes

            updated_json = rec_obj.model_dump_json()

            applied_time = now_iso if status_val == RecommendationStatus.APPLIED.value else None
            cursor.execute(
                """
                UPDATE recommendation_decisions SET
                    status = ?,
                    instructor_notes = COALESCE(?, instructor_notes),
                    decision_timestamp = ?,
                    applied_timestamp = COALESCE(?, applied_timestamp),
                    recommendation_json = ?
                WHERE recommendation_id = ?
                """,
                (
                    status_val,
                    notes,
                    now_iso,
                    applied_time,
                    updated_json,
                    target_id,
                ),
            )
            return target_id

    def get_recommendations(
        self,
        lesson_id: str,
        version_number: Optional[int] = None,
    ) -> List[Recommendation]:
        """Retrieve recommendations for a lesson, optionally filtered by version."""
        query = "SELECT recommendation_json FROM recommendation_decisions WHERE lesson_id = ?"
        params: List[Any] = [lesson_id]

        if version_number is not None:
            query += " AND version_number = ?"
            params.append(version_number)

        query += " ORDER BY decision_timestamp ASC"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [Recommendation.model_validate_json(r["recommendation_json"]) for r in rows]
