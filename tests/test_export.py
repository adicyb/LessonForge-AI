"""
Comprehensive unit and integration tests for Multi-Format Export Engine.
Verifies Markdown generation, PDF compilation, selectable text extraction via pypdf,
Unicode resilience, table layout, version selection, and strict QC report traceability.
"""

from __future__ import annotations

import copy
from pathlib import Path
import pytest
from pypdf import PdfReader

from core.exceptions import ExportError, LessonNotFoundError, VersionNotFoundError
from core.schemas import (
    LessonInput,
    LessonPlan,
    ProvenanceStatus,
    QCLayer,
    QCSeverity,
    QCStatus,
    ResearchSource,
    SourceType,
    TimedSection,
)
from export.export_service import ExportService
from export.markdown_exporter import MarkdownExporter
from export.pdf_exporter import PDFExporter
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.qc_schemas import DetailedQCReport
from quality_control.research_auditor import ResearchAuditor
from storage.database import DatabaseManager
from storage.lesson_repository import LessonRepository


@pytest.fixture
def memory_db() -> DatabaseManager:
    return DatabaseManager(db_path=":memory:")


@pytest.fixture
def repo(memory_db: DatabaseManager) -> LessonRepository:
    return LessonRepository(db=memory_db)


@pytest.fixture
def export_service(repo: LessonRepository) -> ExportService:
    return ExportService(repo=repo)


@pytest.fixture
def sample_lesson() -> LessonPlan:
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    return generator.generate(inp, force_offline=True).lesson_plan


# ---------------------------------------------------------------------------
# 1. Markdown Export Completeness Tests
# ---------------------------------------------------------------------------
def test_markdown_export_structure_and_completeness(sample_lesson: LessonPlan, tmp_path: Path):
    exporter = MarkdownExporter()
    out_file = tmp_path / "test_lesson.md"
    content = exporter.export(sample_lesson, output_path=out_file)

    assert out_file.exists()
    assert len(content) > 1000

    # Verify all essential pedagogical sections
    assert f"# {sample_lesson.title}" in content
    assert "## Learning Objective" in content
    assert sample_lesson.learning_objective in content
    assert "## Timed Agenda (45-Minute Budget Allocation)" in content
    assert "## Introduction & Orientation" in content
    assert "## Hands-On Guided Activity:" in content
    assert "## Knowledge Checks" in content
    assert "## Summary & Key Takeaways" in content
    assert "## Research Bibliography & Source Provenance" in content

    # Verify GFM tables and provenance badges
    assert "| Phase / Module | Cognitive Focus | Duration | % Budget |" in content
    assert "`DISCOVERED`" in content or "`RETRIEVED`" in content or "`VERIFIED`" in content

    # Verify all sequential sections are included in original order
    for sec in sample_lesson.sections:
        assert f"## {sec.title}" in content
        assert sec.cognitive_focus in content


# ---------------------------------------------------------------------------
# 2. PDF Creation and Binary Structure Tests
# ---------------------------------------------------------------------------
def test_pdf_export_creation_and_binary_structure(sample_lesson: LessonPlan, tmp_path: Path):
    exporter = PDFExporter()
    out_file = tmp_path / "test_lesson.pdf"
    res_path = exporter.export(sample_lesson, output_path=out_file)

    assert res_path.exists()
    assert res_path == out_file

    pdf_bytes = out_file.read_bytes()
    # Check PDF magic header
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 15000  # Valid multi-page ReportLab document


# ---------------------------------------------------------------------------
# 3. Selectable Text Extraction via pypdf
# ---------------------------------------------------------------------------
def test_pdf_text_extraction_selectable_content(sample_lesson: LessonPlan, tmp_path: Path):
    exporter = PDFExporter()
    out_file = tmp_path / "test_selectable.pdf"
    exporter.export(sample_lesson, output_path=out_file)

    reader = PdfReader(str(out_file))
    assert len(reader.pages) >= 2  # Complete 45-min lesson spans multiple pages

    full_pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Verify core lesson elements are selectable and searchable
    assert "HTTP Requests and Responses" in full_pdf_text
    assert "Learning Objective" in full_pdf_text or "Core Learning Objective" in full_pdf_text
    assert "45 Minutes" in full_pdf_text or "45-Minute" in full_pdf_text
    assert "Hands-On" in full_pdf_text or "Guided" in full_pdf_text
    assert "Page 1 of" in full_pdf_text or "Page 2 of" in full_pdf_text


# ---------------------------------------------------------------------------
# 4. Long Sections and Table Overflow Resilience
# ---------------------------------------------------------------------------
def test_export_long_sections_and_complex_tables(sample_lesson: LessonPlan, tmp_path: Path):
    stress_lesson = copy.deepcopy(sample_lesson)

    # Add a massive markdown table and long preformatted code block
    long_table = "\n\n| Col A | Col B | Col C | Col D | Col E |\n| :--- | :--- | :--- | :--- | :--- |\n"
    for r in range(15):
        long_table += f"| Cell A{r} | Parameter descriptor for row {r} | 0x{r:04X} | Verified Active | Standard RFC Spec |\n"

    long_code = "\n\n```python\n# Architectural verification client\n" + "\n".join(f"client.send_packet(seq={i})" for i in range(25)) + "\n```\n"

    stress_lesson.sections[0].content_markdown += long_table + long_code

    pdf_file = tmp_path / "stress_test.pdf"
    md_file = tmp_path / "stress_test.md"

    # Both must export without crashing
    pdf_exporter = PDFExporter()
    md_exporter = MarkdownExporter()

    pdf_path = pdf_exporter.export(stress_lesson, output_path=pdf_file)
    md_content = md_exporter.export(stress_lesson, output_path=md_file)

    assert pdf_path.exists()
    assert md_file.exists()
    assert len(md_content) > 0
    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) >= 3


# ---------------------------------------------------------------------------
# 5. Unicode and XML Special Characters Resilience
# ---------------------------------------------------------------------------
def test_unicode_and_special_characters_resilience(sample_lesson: LessonPlan, tmp_path: Path):
    unicode_lesson = copy.deepcopy(sample_lesson)
    unicode_snippet = (
        "Special Entities: <script>alert('test')</script> &amp; 'quotes' \"double\" "
        "Math: ≤ 45 min, ≥ 10 min, λ -> α != β. "
        "Unicode text: café, résumé, 🚀 rocket."
    )
    unicode_lesson.sections[0].content_markdown += f"\n\n{unicode_snippet}"

    pdf_file = tmp_path / "unicode_test.pdf"
    pdf_exporter = PDFExporter()
    pdf_path = pdf_exporter.export(unicode_lesson, output_path=pdf_file)

    assert pdf_path.exists()
    reader = PdfReader(str(pdf_path))
    extracted = "\n".join(p.extract_text() or "" for p in reader.pages)
    assert "Special Entities" in extracted


# ---------------------------------------------------------------------------
# 6. Correct Lesson Version Selection
# ---------------------------------------------------------------------------
def test_correct_lesson_version_selection(export_service: ExportService, sample_lesson: LessonPlan, tmp_path: Path):
    repo = export_service.repo

    # Save Version 1
    v1_title = "HTTP Requests v1 Original Draft"
    sample_lesson.title = v1_title
    repo.save_lesson(sample_lesson, author="INITIAL", change_summary="Draft 1")

    # Save Version 2
    v2_lesson = copy.deepcopy(sample_lesson)
    v2_lesson.version = 2
    v2_title = "HTTP Requests v2 Remediated Edition"
    v2_lesson.title = v2_title
    repo.save_lesson(v2_lesson, author="INSTRUCTOR", change_summary="Draft 2")

    # Export Version 1 explicitly
    v1_md = export_service.export_markdown(sample_lesson.lesson_id, version=1, output_dir=tmp_path)
    v1_pdf = export_service.export_pdf(sample_lesson.lesson_id, version=1, output_dir=tmp_path)

    v1_md_text = v1_md.read_text(encoding="utf-8")
    assert v1_title in v1_md_text
    assert v2_title not in v1_md_text

    v1_pdf_reader = PdfReader(str(v1_pdf))
    v1_pdf_text = "\n".join(p.extract_text() or "" for p in v1_pdf_reader.pages)
    assert v1_title in v1_pdf_text
    assert v2_title not in v1_pdf_text

    # Export Version 2 explicitly
    v2_md = export_service.export_markdown(sample_lesson.lesson_id, version=2, output_dir=tmp_path)
    v2_pdf = export_service.export_pdf(sample_lesson.lesson_id, version=2, output_dir=tmp_path)

    v2_md_text = v2_md.read_text(encoding="utf-8")
    assert v2_title in v2_md_text

    v2_pdf_reader = PdfReader(str(v2_pdf))
    v2_pdf_text = "\n".join(p.extract_text() or "" for p in v2_pdf_reader.pages)
    assert v2_title in v2_pdf_text


# ---------------------------------------------------------------------------
# 7. Exact QC Report Version Association & No Cross-Talk
# ---------------------------------------------------------------------------
def test_correct_qc_report_version_association(export_service: ExportService, sample_lesson: LessonPlan, tmp_path: Path):
    repo = export_service.repo

    # Save Version 1 with flawed score
    repo.save_lesson(sample_lesson, author="SYS", change_summary="Draft 1")
    report_v1 = DetailedQCReport.from_report_components(
        report_id="rep_http_v1",
        lesson_id=sample_lesson.lesson_id,
        version_audited=1,
        layer=QCLayer.FACTUAL_ACCURACY,
        overall_score=74.0,
        status=QCStatus.NEEDS_REVISION,
        criterion_scores=[],
        findings=[],
        summary="Initial draft contains RFC contradiction in Section 2.",
    )
    repo.save_qc_report(report_v1)

    # Save Version 2 with perfected score
    v2_lesson = copy.deepcopy(sample_lesson)
    v2_lesson.version = 2
    repo.save_lesson(v2_lesson, author="INSTRUCTOR", change_summary="Draft 2")
    report_v2 = DetailedQCReport.from_report_components(
        report_id="rep_http_v2",
        lesson_id=sample_lesson.lesson_id,
        version_audited=2,
        layer=QCLayer.FACTUAL_ACCURACY,
        overall_score=100.0,
        status=QCStatus.PASSED,
        criterion_scores=[],
        findings=[],
        summary="All contradictions resolved. Perfect score achieved.",
    )
    repo.save_qc_report(report_v2)

    # Export Version 1: MUST include report_v1 (74.0) and NEVER report_v2 (100.0)
    v1_md = export_service.export_markdown(sample_lesson.lesson_id, version=1, output_dir=tmp_path)
    v1_text = v1_md.read_text(encoding="utf-8")
    assert "Score: 74.0/100" in v1_text
    assert "Score: 100.0/100" not in v1_text
    assert "rep_http_v1" in v1_text
    assert "rep_http_v2" not in v1_text

    # Export Version 2: MUST include report_v2 (100.0) and NEVER report_v1 (74.0)
    v2_md = export_service.export_markdown(sample_lesson.lesson_id, version=2, output_dir=tmp_path)
    v2_text = v2_md.read_text(encoding="utf-8")
    assert "Score: 100.0/100" in v2_text
    assert "Score: 74.0/100" not in v2_text
    assert "rep_http_v2" in v2_text
    assert "rep_http_v1" not in v2_text


# ---------------------------------------------------------------------------
# 8. Missing Audit Reports Handled Transparently
# ---------------------------------------------------------------------------
def test_missing_audit_reports_handling(export_service: ExportService, sample_lesson: LessonPlan, tmp_path: Path):
    repo = export_service.repo
    repo.save_lesson(sample_lesson)

    # No QC report saved
    md_file = export_service.export_markdown(sample_lesson.lesson_id, output_dir=tmp_path)
    md_text = md_file.read_text(encoding="utf-8")

    assert "Notice: Quality Control audit has not yet been conducted" in md_text
    # Must never fabricate an audit score
    assert "Score: 100.0" not in md_text


# ---------------------------------------------------------------------------
# 9. Error Handling on Non-Existent IDs or Versions
# ---------------------------------------------------------------------------
def test_export_error_handling(export_service: ExportService):
    with pytest.raises(LessonNotFoundError):
        export_service.export_markdown("ghost_lesson_id_9999")

    with pytest.raises(VersionNotFoundError):
        export_service.export_markdown(export_service.repo.save_lesson(LessonGenerator().generate(LessonInput(title="Dummy Topic", learning_objective="Dummy objective 12345")).lesson_plan).lesson_id, version=99)

    with pytest.raises(ExportError):
        export_service.export_lesson("dummy_id", format="invalid_format_xyz")


# ---------------------------------------------------------------------------
# 10. No Modification of Stored Lesson Data During Export
# ---------------------------------------------------------------------------
def test_no_modification_of_stored_lesson_during_export(export_service: ExportService, sample_lesson: LessonPlan, tmp_path: Path):
    repo = export_service.repo
    repo.save_lesson(sample_lesson)

    before_lesson = repo.get_lesson(sample_lesson.lesson_id)
    assert before_lesson is not None
    before_json = before_lesson.model_dump_json()

    # Perform both exports
    export_service.export_lesson(sample_lesson.lesson_id, format="all", output_dir=tmp_path)

    # Stored lesson must remain bitwise identical
    after_lesson = repo.get_lesson(sample_lesson.lesson_id)
    assert after_lesson is not None
    assert after_lesson.model_dump_json() == before_json
