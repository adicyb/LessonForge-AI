"""
Comprehensive unit and integration tests for SQLite Storage & Persistence Layer.
Verifies database initialization, CRUD operations, version history immutability,
research source linkage, dual QC report persistence, foreign keys, transactional rollback,
and application restart simulation.
"""

from __future__ import annotations

import copy
import sqlite3
import pytest
from pathlib import Path

from core.exceptions import (
    LessonNotFoundError,
    StorageError,
    ValidationError,
)
from core.schemas import (
    LearnerLevel,
    LessonInput,
    LessonPlan,
    ProvenanceStatus,
    QCLayer,
    QCSeverity,
    QCStatus,
    Recommendation,
    RecommendationStatus,
    ResearchSource,
    SourceType,
)
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.qc_schemas import DetailedQCReport
from quality_control.research_auditor import ResearchAuditor
from storage.database import DatabaseManager
from storage.lesson_repository import LessonRepository


@pytest.fixture
def memory_db() -> DatabaseManager:
    """Provide an isolated in-memory DatabaseManager for testing."""
    return DatabaseManager(db_path=":memory:")


@pytest.fixture
def repo(memory_db: DatabaseManager) -> LessonRepository:
    """Provide a repository bound to the in-memory database."""
    return LessonRepository(db=memory_db)


@pytest.fixture
def sample_lesson() -> LessonPlan:
    """Generate a clean, valid benchmark lesson plan."""
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    return generator.generate(inp, force_offline=True).lesson_plan


# ---------------------------------------------------------------------------
# 1. Database Initialization Tests
# ---------------------------------------------------------------------------
def test_database_initialization_and_repeat_initialization(tmp_path: Path):
    db_file = tmp_path / "init_test.db"
    db = DatabaseManager(db_path=db_file)

    # Verify tables created
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cursor.fetchall()}
        required = {"lessons", "lesson_versions", "research_sources", "qc_reports", "recommendation_decisions", "schema_version"}
        assert required.issubset(tables)

        cursor.execute("SELECT version, description FROM schema_version")
        ver_row = cursor.fetchone()
        assert ver_row is not None
        assert ver_row["version"] == 1

    # Repeat initialization must be safe and idempotent
    db.init_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM schema_version")
        assert cursor.fetchone()["count"] == 1


# ---------------------------------------------------------------------------
# 2. Lesson CRUD Operations Tests
# ---------------------------------------------------------------------------
def test_crud_lesson_operations(repo: LessonRepository, sample_lesson: LessonPlan):
    # Create / Save
    saved = repo.save_lesson(sample_lesson, author="TEST_GENERATOR", change_summary="Unit test creation")
    assert saved.lesson_id == sample_lesson.lesson_id

    # Read
    retrieved = repo.get_lesson(sample_lesson.lesson_id)
    assert retrieved is not None
    assert retrieved.lesson_id == sample_lesson.lesson_id
    assert retrieved.title == sample_lesson.title
    assert retrieved.total_duration_minutes == sample_lesson.total_duration_minutes
    assert len(retrieved.sections) == len(sample_lesson.sections)

    # List
    lessons_list = repo.list_lessons()
    assert len(lessons_list) >= 1
    assert any(l["lesson_id"] == sample_lesson.lesson_id for l in lessons_list)

    # Delete
    deleted = repo.delete_lesson(sample_lesson.lesson_id)
    assert deleted is True
    assert repo.get_lesson(sample_lesson.lesson_id) is None


# ---------------------------------------------------------------------------
# 3. Version History & Snapshot Immutability Tests
# ---------------------------------------------------------------------------
def test_version_history_and_snapshot_immutability(repo: LessonRepository, sample_lesson: LessonPlan):
    # Save version 1
    repo.save_lesson(sample_lesson, author="AUTHOR_V1", change_summary="Draft 1")
    v1_original_title = sample_lesson.title
    v1_original_section_text = sample_lesson.sections[0].content_markdown

    # Modify and save version 2
    modified_lesson = copy.deepcopy(sample_lesson)
    modified_lesson.title = "HTTP Requests and Responses (Revised Edition)"
    modified_lesson.sections[0].content_markdown += "\n\nAdditional RFC 9110 architectural notes."
    modified_lesson.version = 2

    repo.save_lesson(modified_lesson, author="INSTRUCTOR", change_summary="Added RFC notes")

    # Current lesson must be Version 2
    current = repo.get_lesson(sample_lesson.lesson_id)
    assert current is not None
    assert current.version == 2
    assert current.title == "HTTP Requests and Responses (Revised Edition)"

    # Version history must have 2 entries
    versions = repo.get_lesson_versions(sample_lesson.lesson_id)
    assert len(versions) == 2
    assert versions[0]["version_number"] == 1
    assert versions[0]["author"] == "AUTHOR_V1"
    assert versions[1]["version_number"] == 2
    assert versions[1]["author"] == "INSTRUCTOR"

    # CRITICAL INVARIANT: Version 1 snapshot remains UNCHANGED
    v1_retrieved = repo.get_lesson_version(sample_lesson.lesson_id, 1)
    assert v1_retrieved is not None
    assert v1_retrieved.version == 1
    assert v1_retrieved.title == v1_original_title
    assert v1_retrieved.sections[0].content_markdown == v1_original_section_text
    assert "Additional RFC 9110 architectural notes" not in v1_retrieved.sections[0].content_markdown

    # Version 2 snapshot has modified content
    v2_retrieved = repo.get_lesson_version(sample_lesson.lesson_id, 2)
    assert v2_retrieved is not None
    assert v2_retrieved.version == 2
    assert "Additional RFC 9110 architectural notes" in v2_retrieved.sections[0].content_markdown


# ---------------------------------------------------------------------------
# 4. Research Sources Persistence Tests
# ---------------------------------------------------------------------------
def test_research_sources_persistence(repo: LessonRepository, sample_lesson: LessonPlan):
    repo.save_lesson(sample_lesson)

    sources = [
        ResearchSource(
            id="src_rfc9110",
            source_type=SourceType.WEB,
            title="RFC 9110: HTTP Semantics",
            url="https://www.rfc-editor.org/rfc/rfc9110",
            snippet_or_summary="Defines HTTP semantics including GET, POST, safety, and idempotency.",
            provenance=ProvenanceStatus.VERIFIED,
            credibility_score=0.98,
            metadata={"domain": "rfc-editor.org", "relevance_score": 0.95},
        ),
        ResearchSource(
            id="src_mdn_http",
            source_type=SourceType.WEB,
            title="MDN Web Docs: HTTP Overview",
            url="https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview",
            snippet_or_summary="Comprehensive guide to HTTP headers and status codes.",
            provenance=ProvenanceStatus.RETRIEVED,
            credibility_score=0.90,
            metadata={"domain": "developer.mozilla.org", "relevance_score": 0.88},
        ),
    ]

    saved_count = repo.save_research_sources(sample_lesson.lesson_id, sources)
    assert saved_count == 2

    retrieved = repo.get_research_sources(sample_lesson.lesson_id)
    assert len(retrieved) >= 2
    src_map = {s.id: s for s in retrieved}
    assert "src_rfc9110" in src_map
    assert src_map["src_rfc9110"].provenance == ProvenanceStatus.VERIFIED
    assert src_map["src_rfc9110"].credibility_score == 0.98
    assert src_map["src_rfc9110"].metadata["domain"] == "rfc-editor.org"


# ---------------------------------------------------------------------------
# 5. Independent QC Report Persistence Tests
# ---------------------------------------------------------------------------
def test_independent_qc_reports_persistence(repo: LessonRepository, sample_lesson: LessonPlan):
    repo.save_lesson(sample_lesson)

    auditor_qc1 = ResearchAuditor()
    auditor_qc2 = InstructionalAuditor()

    report_qc1 = auditor_qc1.audit(sample_lesson)
    report_qc2 = auditor_qc2.audit(sample_lesson)

    # Save both reports
    id1 = repo.save_qc_report(report_qc1)
    id2 = repo.save_qc_report(report_qc2)
    assert id1 == report_qc1.report_id
    assert id2 == report_qc2.report_id

    # Retrieve all reports
    all_reports = repo.get_qc_reports(sample_lesson.lesson_id)
    assert len(all_reports) == 2

    # Filter by layer
    factual_reports = repo.get_qc_reports(sample_lesson.lesson_id, layer=QCLayer.FACTUAL_ACCURACY)
    assert len(factual_reports) == 1
    assert factual_reports[0].layer == QCLayer.FACTUAL_ACCURACY
    assert factual_reports[0].overall_score == report_qc1.overall_score
    assert len(factual_reports[0].atomic_claims) > 0

    instructional_reports = repo.get_qc_reports(sample_lesson.lesson_id, layer=QCLayer.INSTRUCTIONAL_QUALITY)
    assert len(instructional_reports) == 1
    assert instructional_reports[0].layer == QCLayer.INSTRUCTIONAL_QUALITY
    assert instructional_reports[0].overall_score == report_qc2.overall_score


# ---------------------------------------------------------------------------
# 6. Recommendation Decision Persistence Tests
# ---------------------------------------------------------------------------
def test_recommendation_decision_persistence(repo: LessonRepository, sample_lesson: LessonPlan):
    repo.save_lesson(sample_lesson)

    rec = Recommendation(
        id="rec_storage_001",
        finding_id="find_storage_001",
        layer=QCLayer.FACTUAL_ACCURACY,
        severity=QCSeverity.CRITICAL,
        section_target="sec_http_2_methods",
        issue_summary="Clarify POST idempotency semantics",
        suggested_content="POST is non-idempotent under RFC 9110.",
        status=RecommendationStatus.PENDING,
    )

    # Save recommendation
    rec_id = repo.save_recommendation(rec, lesson_id=sample_lesson.lesson_id, version_number=1)
    assert rec_id == "rec_storage_001"

    # Retrieve and check PENDING status
    recs = repo.get_recommendations(sample_lesson.lesson_id)
    assert len(recs) == 1
    assert recs[0].status == RecommendationStatus.PENDING

    # Record instructor ACCEPTED decision
    repo.save_recommendation_decision(
        rec_id="rec_storage_001",
        status=RecommendationStatus.ACCEPTED,
        notes="Approved for integration in version 2",
    )

    recs_updated = repo.get_recommendations(sample_lesson.lesson_id)
    assert len(recs_updated) == 1
    assert recs_updated[0].status == RecommendationStatus.ACCEPTED
    assert recs_updated[0].instructor_notes == "Approved for integration in version 2"


# ---------------------------------------------------------------------------
# 7. Foreign Key Enforcement & Cascade Tests
# ---------------------------------------------------------------------------
def test_foreign_key_enforcement_and_cascade(repo: LessonRepository, sample_lesson: LessonPlan):
    # Attempting to save sources for a non-existent lesson must raise LessonNotFoundError
    sources = [
        ResearchSource(
            id="src_orphan",
            source_type=SourceType.WEB,
            title="Orphan Source",
            url="https://example.com/orphan",
            snippet_or_summary="Orphan snippet text.",
        )
    ]
    with pytest.raises(LessonNotFoundError):
        repo.save_research_sources("non_existent_lesson_uuid", sources)

    # Save lesson and child records
    repo.save_lesson(sample_lesson)
    repo.save_research_sources(sample_lesson.lesson_id, sources)

    # Ensure child record exists
    assert len(repo.get_research_sources(sample_lesson.lesson_id)) >= 1

    # Deleting lesson must cascade and remove child records
    repo.delete_lesson(sample_lesson.lesson_id)
    assert repo.get_lesson(sample_lesson.lesson_id) is None
    assert len(repo.get_research_sources(sample_lesson.lesson_id)) == 0
    with pytest.raises(LessonNotFoundError):
        repo.get_lesson_versions(sample_lesson.lesson_id)


# ---------------------------------------------------------------------------
# 8. Transaction Rollback on Failure Tests
# ---------------------------------------------------------------------------
def test_transaction_rollback_on_failure(memory_db: DatabaseManager, sample_lesson: LessonPlan):
    repo = LessonRepository(db=memory_db)
    repo.save_lesson(sample_lesson)

    # Verify initial count
    with memory_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM lessons")
        initial_count = cursor.fetchone()["count"]

    # Execute a failing transaction
    with pytest.raises(RuntimeError):
        with memory_db.transaction() as conn:
            conn.execute(
                "INSERT INTO lessons (lesson_id, title, learning_objective, learner_level, duration_minutes, current_version, created_at, updated_at, content_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("failed_lesson_tx", "Fail Title", "Objective", "BEGINNER", 45, 1, "2026-01-01", "2026-01-01", "{}"),
            )
            # Deliberately raise exception inside transaction block
            raise RuntimeError("Simulated mid-transaction crash")

    # Verify rollback: failed_lesson_tx must NOT exist
    with memory_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM lessons WHERE lesson_id = 'failed_lesson_tx'")
        assert cursor.fetchone()["count"] == 0
        cursor.execute("SELECT COUNT(*) as count FROM lessons")
        assert cursor.fetchone()["count"] == initial_count


# ---------------------------------------------------------------------------
# 9. Application Restart Simulation Tests
# ---------------------------------------------------------------------------
def test_application_restart_simulation(tmp_path: Path, sample_lesson: LessonPlan):
    db_file = tmp_path / "lessons_restart_test.db"

    # Session 1: Write data
    db1 = DatabaseManager(db_path=db_file)
    repo1 = LessonRepository(db=db1)

    repo1.save_lesson(sample_lesson, author="INITIAL_SESSION", change_summary="Session 1 initial draft")

    # Create Version 2
    v2_lesson = copy.deepcopy(sample_lesson)
    v2_lesson.version = 2
    v2_lesson.title = "HTTP Requests and Responses (Session 2 Restart Test)"
    repo1.save_lesson(v2_lesson, author="INSTRUCTOR_SESSION_1", change_summary="Session 1 revised draft")

    # Add QC report
    auditor = ResearchAuditor()
    qc_rep = auditor.audit(v2_lesson)
    repo1.save_qc_report(qc_rep)

    # Add recommendation decision
    rec = Recommendation(
        id="rec_restart_001",
        finding_id="find_restart_001",
        layer=QCLayer.FACTUAL_ACCURACY,
        severity=QCSeverity.MINOR,
        section_target="sec_http_1_foundations",
        issue_summary="Enhance protocol diagram description",
        suggested_content="Detailed description of TCP handshake.",
        status=RecommendationStatus.ACCEPTED,
        instructor_notes="Retained across restart",
    )
    repo1.save_recommendation(rec, lesson_id=sample_lesson.lesson_id, version_number=2)

    # Session 1 closes
    db1.close()
    del repo1
    del db1

    # Session 2: Connect with new instance on same file
    db2 = DatabaseManager(db_path=db_file)
    repo2 = LessonRepository(db=db2)

    # Verify current lesson
    loaded_lesson = repo2.get_lesson(sample_lesson.lesson_id)
    assert loaded_lesson is not None
    assert loaded_lesson.version == 2
    assert loaded_lesson.title == "HTTP Requests and Responses (Session 2 Restart Test)"

    # Verify both version snapshots survive restart
    versions = repo2.get_lesson_versions(sample_lesson.lesson_id)
    assert len(versions) == 2
    assert versions[0]["version_number"] == 1
    assert versions[1]["version_number"] == 2

    # Verify QC report survived restart
    reports = repo2.get_qc_reports(sample_lesson.lesson_id)
    assert len(reports) == 1
    assert reports[0].report_id == qc_rep.report_id

    # Verify recommendation decision survived restart
    recs = repo2.get_recommendations(sample_lesson.lesson_id)
    assert len(recs) == 1
    assert recs[0].id == "rec_restart_001"
    assert recs[0].status == RecommendationStatus.ACCEPTED
    assert recs[0].instructor_notes == "Retained across restart"

    db2.close()
