"""
End-to-End Integration Tests for LessonForge AI UI and Full Workflow.
Verifies the complete integration lifecycle:
1. Creation & persistence in SQLite.
2. Retrieval across simulated app restart.
3. Independent QC1 & QC2 audits and persistence.
4. Recommendation review, non-destructive patching, and version immutability.
5. Multi-format Markdown & PDF export with exact-version audit traceability.
6. Input validation and error handling resilience.
"""

from __future__ import annotations

import copy
from pathlib import Path
import pytest
from pypdf import PdfReader

from core.exceptions import (
    DurationExceededError,
    EmptyInputError,
    LessonNotFoundError,
    ValidationError,
    VersionNotFoundError,
)
from core.schemas import (
    LearnerLevel,
    LessonInput,
    LessonPlan,
    QCLayer,
    QCStatus,
    RecommendationStatus,
)
from export.export_service import ExportService
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.recommendation_engine import RecommendationEngine
from quality_control.research_auditor import ResearchAuditor
from storage.database import DatabaseManager
from storage.lesson_repository import LessonRepository


# ---------------------------------------------------------------------------
# 1. Full Lifecycle: Creation, Persistence & Restart Simulation
# ---------------------------------------------------------------------------
def test_end_to_end_lesson_creation_persistence_and_restart(tmp_path: Path):
    db_file = tmp_path / "e2e_test.db"

    # Session 1: Synthesis and Save
    db1 = DatabaseManager(db_path=db_file)
    repo1 = LessonRepository(db=db1)

    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
        learner_level=LearnerLevel.BEGINNER,
    )
    generator = LessonGenerator()
    gen_res = generator.generate(inp, force_offline=True)
    lesson = gen_res.lesson_plan

    saved_lesson = repo1.save_lesson(lesson, author="E2E_SYNTHESIZER", change_summary="Session 1 initial draft")
    assert saved_lesson.lesson_id == lesson.lesson_id

    # Verify sources saved
    saved_sources = repo1.save_research_sources(lesson.lesson_id, lesson.references)
    assert saved_sources >= 4

    # Close Session 1
    db1.close()
    del repo1
    del db1

    # Session 2: Connect from fresh instance on disk
    db2 = DatabaseManager(db_path=db_file)
    repo2 = LessonRepository(db=db2)

    retrieved = repo2.get_lesson(lesson.lesson_id)
    assert retrieved is not None
    assert retrieved.lesson_id == lesson.lesson_id
    assert retrieved.title == "HTTP Requests and Responses"
    assert retrieved.total_duration_minutes == 45
    assert len(retrieved.sections) == 3

    sources_reloaded = repo2.get_research_sources(lesson.lesson_id)
    assert len(sources_reloaded) >= 4
    assert any(s.provenance.value in ("VERIFIED", "RETRIEVED") for s in sources_reloaded)

    db2.close()


# ---------------------------------------------------------------------------
# 2. Independent QC Audits and Persistence
# ---------------------------------------------------------------------------
def test_end_to_end_independent_qc_audits_and_persistence(tmp_path: Path):
    db_file = tmp_path / "qc_e2e.db"
    db = DatabaseManager(db_path=db_file)
    repo = LessonRepository(db=db)

    inp = LessonInput(
        title="DNS Resolution and DNS Record Types",
        learning_objective="Trace the step-by-step resolution process of a domain name and differentiate between A, AAAA, CNAME, and MX record types.",
        target_duration_minutes=45,
        learner_level=LearnerLevel.BEGINNER,
    )
    lesson = LessonGenerator().generate(inp, force_offline=True).lesson_plan
    repo.save_lesson(lesson)

    auditor_qc1 = ResearchAuditor()
    auditor_qc2 = InstructionalAuditor()

    # Run QC1 independently
    rep1 = auditor_qc1.audit(lesson)
    assert rep1.layer == QCLayer.FACTUAL_ACCURACY
    assert rep1.overall_score >= 80.0
    repo.save_qc_report(rep1)

    # Run QC2 independently (guaranteed zero crosstalk)
    rep2 = auditor_qc2.audit(lesson)
    assert rep2.layer == QCLayer.INSTRUCTIONAL_QUALITY
    assert rep2.overall_score >= 80.0
    repo.save_qc_report(rep2)

    # Reload from DB
    reloaded_reports = repo.get_qc_reports(lesson.lesson_id)
    assert len(reloaded_reports) == 2
    rep_map = {r.layer.value: r for r in reloaded_reports}
    assert "FACTUAL_ACCURACY" in rep_map
    assert "INSTRUCTIONAL_QUALITY" in rep_map
    assert rep_map["FACTUAL_ACCURACY"].overall_score == rep1.overall_score
    assert rep_map["INSTRUCTIONAL_QUALITY"].overall_score == rep2.overall_score

    db.close()


# ---------------------------------------------------------------------------
# 3. Recommendation Review, True Replacement & Version Immutability
# ---------------------------------------------------------------------------
def test_end_to_end_recommendation_lifecycle_and_version_immutability(tmp_path: Path):
    db_file = tmp_path / "recs_e2e.db"
    db = DatabaseManager(db_path=db_file)
    repo = LessonRepository(db=db)

    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    lesson_v1 = LessonGenerator().generate(inp, force_offline=True).lesson_plan

    # Introduce deliberate RFC contradiction in Version 1
    flawed_stmt = "Note: In our web framework, POST is idempotent and safe."
    lesson_v1.sections[1].content_markdown += f"\n\n{flawed_stmt}"
    repo.save_lesson(lesson_v1, author="INITIAL", change_summary="Flawed v1")

    # Audit v1: Must catch contradiction
    rep_v1 = ResearchAuditor().audit(lesson_v1)
    assert rep_v1.overall_score < 75.0
    assert rep_v1.status in (QCStatus.NEEDS_REVISION, QCStatus.FAILED)
    repo.save_qc_report(rep_v1)

    # Locate recommendation
    rec = next(r for r in rep_v1.recommendations if "POST is idempotent" in r.issue_summary)
    repo.save_recommendation(rec, lesson_id=lesson_v1.lesson_id, version_number=1)

    # Accept recommendation
    engine = RecommendationEngine()
    rec_acc = engine.accept_recommendation(rec, instructor_notes="Approved RFC 9110 fix")
    repo.save_recommendation_decision(rec.id, RecommendationStatus.ACCEPTED, notes="Approved RFC 9110 fix")

    # Apply recommendation
    lesson_v2, diff = engine.apply_recommendation(lesson_v1, rec_acc)
    assert flawed_stmt not in lesson_v2.sections[1].content_markdown
    assert "RFC 9110" in lesson_v2.sections[1].content_markdown

    # Save as Version 2
    new_v = repo.save_lesson_version(lesson_v2, author="INSTRUCTOR", change_summary="Remediated POST flaw")
    assert new_v == 2

    # CRITICAL INVARIANT: Version 1 remains UNMUTATED in database
    v1_reloaded = repo.get_lesson_version(lesson_v1.lesson_id, 1)
    v2_reloaded = repo.get_lesson_version(lesson_v1.lesson_id, 2)

    assert v1_reloaded is not None
    assert v2_reloaded is not None
    assert flawed_stmt in v1_reloaded.sections[1].content_markdown
    assert flawed_stmt not in v2_reloaded.sections[1].content_markdown

    # Re-audit Version 2: Score strictly improves to >= 90
    rep_v2 = ResearchAuditor().audit(v2_reloaded)
    assert rep_v2.overall_score >= 90.0
    assert rep_v2.status == QCStatus.PASSED
    repo.save_qc_report(rep_v2)

    db.close()


# ---------------------------------------------------------------------------
# 4. Multi-Format Export with Exact-Version Traceability
# ---------------------------------------------------------------------------
def test_end_to_end_multi_format_export_traceability(tmp_path: Path):
    db_file = tmp_path / "export_e2e.db"
    exports_dir = tmp_path / "exports"
    db = DatabaseManager(db_path=db_file)
    repo = LessonRepository(db=db)
    service = ExportService(repo=repo)

    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    lesson = LessonGenerator().generate(inp, force_offline=True).lesson_plan
    repo.save_lesson(lesson)

    # Attach QC report
    rep = ResearchAuditor().audit(lesson)
    repo.save_qc_report(rep)

    # Export all formats
    results = service.export_lesson(lesson.lesson_id, format="all", output_dir=exports_dir)
    assert "markdown" in results
    assert "pdf" in results

    md_file = results["markdown"]
    pdf_file = results["pdf"]

    assert md_file.exists()
    assert pdf_file.exists()

    # Verify Markdown
    md_text = md_file.read_text(encoding="utf-8")
    assert "HTTP Requests and Responses" in md_text
    assert "Timed Agenda" in md_text
    assert f"Score: {rep.overall_score}/100" in md_text

    # Verify PDF selectable text via pypdf
    reader = PdfReader(str(pdf_file))
    assert len(reader.pages) >= 2
    pdf_text = "\n".join(p.extract_text() or "" for p in reader.pages)
    assert "HTTP Requests and Responses" in pdf_text
    assert "Learning Objective" in pdf_text or "Core Learning Objective" in pdf_text
    assert "Page 1 of" in pdf_text

    db.close()


from pydantic import ValidationError as PydanticValidationError


# ---------------------------------------------------------------------------
# 5. Input Validation and Domain Error Handling Resilience
# ---------------------------------------------------------------------------
def test_input_validation_and_domain_error_handling():
    # Empty Title
    with pytest.raises((EmptyInputError, PydanticValidationError)):
        LessonInput(title="   ", learning_objective="Valid objective text goes here.")

    # Empty Objective
    with pytest.raises((EmptyInputError, PydanticValidationError)):
        LessonInput(title="Valid Title", learning_objective="   ")

    # Duration Exceeding 45 mins
    with pytest.raises((ValidationError, PydanticValidationError)):
        LessonInput(title="Valid Title", learning_objective="Valid objective text goes here.", target_duration_minutes=50)

    # Duration < 10 mins
    with pytest.raises((ValidationError, PydanticValidationError)):
        LessonInput(title="Valid Title", learning_objective="Valid objective text goes here.", target_duration_minutes=5)
