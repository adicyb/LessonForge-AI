"""
LessonForge AI — Phase 6 Multi-Format Export Demonstration.
Demonstrates end-to-end export execution:
1. HTTP benchmark lesson (Version 1 historical) as Markdown & PDF.
2. HTTP benchmark lesson (Version 2 revised) as Markdown & PDF.
3. DNS benchmark lesson as Markdown & PDF.
4. Automated verification of file existence, PDF binary integrity, and selectable text extraction via pypdf.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from pypdf import PdfReader

from core.schemas import LessonInput, RecommendationStatus
from export.export_service import ExportService
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.recommendation_engine import RecommendationEngine
from quality_control.research_auditor import ResearchAuditor
from storage.database import DatabaseManager
from storage.lesson_repository import LessonRepository


def run_export_demo() -> None:
    demo_db_path = BASE_DIR / "data" / "demo_export.db"
    exports_dir = BASE_DIR / "exports" / "demo_artifacts"
    exports_dir.mkdir(parents=True, exist_ok=True)

    if demo_db_path.exists():
        demo_db_path.unlink()
    for suffix in ("-wal", "-shm"):
        p = demo_db_path.with_name(demo_db_path.name + suffix)
        if p.exists():
            p.unlink()

    print("=" * 80)
    print("LESSONFORGE AI — PHASE 6 MULTI-FORMAT EXPORT DEMONSTRATION")
    print("=" * 80)

    db = DatabaseManager(db_path=demo_db_path)
    repo = LessonRepository(db=db)
    service = ExportService(repo=repo)
    generator = LessonGenerator()
    auditor_qc1 = ResearchAuditor()
    auditor_qc2 = InstructionalAuditor()
    rec_engine = RecommendationEngine()

    # -----------------------------------------------------------------------
    # Setup Benchmark 1: HTTP Lesson (Version 1 & Version 2)
    # -----------------------------------------------------------------------
    print("\n[Step 1] Synthesizing HTTP benchmark lesson and simulating version history...")
    http_input = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    http_v1 = generator.generate(http_input, force_offline=True).lesson_plan
    flawed_stmt = "Note: In our web framework, POST is idempotent and safe."
    http_v1.sections[1].content_markdown += f"\n\n{flawed_stmt}"

    # Save v1
    repo.save_lesson(http_v1, author="AI_RESEARCH_ENGINE", change_summary="Initial benchmark draft with deliberate flaw")
    rep_http_qc1_v1 = auditor_qc1.audit(http_v1)
    rep_http_qc2_v1 = auditor_qc2.audit(http_v1)
    repo.save_qc_report(rep_http_qc1_v1)
    repo.save_qc_report(rep_http_qc2_v1)

    # Apply recommendation to produce v2
    rec = next(r for r in rep_http_qc1_v1.recommendations if "POST is idempotent" in r.issue_summary)
    rec_acc = rec_engine.accept_recommendation(rec, "Approved RFC 9110 correction")
    repo.save_recommendation(rec_acc, lesson_id=http_v1.lesson_id, version_number=1)
    http_v2, diff = rec_engine.apply_recommendation(http_v1, rec_acc)
    repo.save_lesson(http_v2, author="INSTRUCTOR_REVIEWER", change_summary="Remediated POST idempotency flaw")

    rep_http_qc1_v2 = auditor_qc1.audit(http_v2)
    rep_http_qc2_v2 = auditor_qc2.audit(http_v2)
    repo.save_qc_report(rep_http_qc1_v2)
    repo.save_qc_report(rep_http_qc2_v2)
    print(f"  HTTP Lesson: Created Version 1 (QC1={rep_http_qc1_v1.overall_score}) and Version 2 (QC1={rep_http_qc1_v2.overall_score})")

    # -----------------------------------------------------------------------
    # Setup Benchmark 2: DNS Lesson
    # -----------------------------------------------------------------------
    print("\n[Step 2] Synthesizing DNS benchmark lesson...")
    dns_input = LessonInput(
        title="DNS Resolution and DNS Record Types",
        learning_objective="Trace the step-by-step resolution process of a domain name and differentiate between A, AAAA, CNAME, and MX record types.",
        target_duration_minutes=45,
    )
    dns_v1 = generator.generate(dns_input, force_offline=True).lesson_plan
    repo.save_lesson(dns_v1, author="AI_RESEARCH_ENGINE", change_summary="Clean DNS synthesis")
    rep_dns_qc1 = auditor_qc1.audit(dns_v1)
    rep_dns_qc2 = auditor_qc2.audit(dns_v1)
    repo.save_qc_report(rep_dns_qc1)
    repo.save_qc_report(rep_dns_qc2)
    print(f"  DNS Lesson: Created Version 1 (QC1={rep_dns_qc1.overall_score}, QC2={rep_dns_qc2.overall_score})")

    # -----------------------------------------------------------------------
    # Step 3: Export Artifacts
    # -----------------------------------------------------------------------
    print(f"\n[Step 3] Exporting multi-format artifacts to {exports_dir}...")

    # A. HTTP Version 1 (Historical)
    http_v1_md = service.export_markdown(http_v1.lesson_id, version=1, output_dir=exports_dir)
    http_v1_pdf = service.export_pdf(http_v1.lesson_id, version=1, output_dir=exports_dir)
    print(f"  [Artifact 1] HTTP v1 (Historical) Markdown: {http_v1_md.name} ({http_v1_md.stat().st_size} bytes)")
    print(f"  [Artifact 2] HTTP v1 (Historical) PDF:      {http_v1_pdf.name} ({http_v1_pdf.stat().st_size} bytes)")

    # B. HTTP Version 2 (Remediated)
    http_v2_md = service.export_markdown(http_v1.lesson_id, version=2, output_dir=exports_dir)
    http_v2_pdf = service.export_pdf(http_v1.lesson_id, version=2, output_dir=exports_dir)
    print(f"  [Artifact 3] HTTP v2 (Remediated) Markdown: {http_v2_md.name} ({http_v2_md.stat().st_size} bytes)")
    print(f"  [Artifact 4] HTTP v2 (Remediated) PDF:      {http_v2_pdf.name} ({http_v2_pdf.stat().st_size} bytes)")

    # C. DNS Version 1
    dns_md = service.export_markdown(dns_v1.lesson_id, version=1, output_dir=exports_dir)
    dns_pdf = service.export_pdf(dns_v1.lesson_id, version=1, output_dir=exports_dir)
    print(f"  [Artifact 5] DNS v1 Markdown:               {dns_md.name} ({dns_md.stat().st_size} bytes)")
    print(f"  [Artifact 6] DNS v1 PDF:                    {dns_pdf.name} ({dns_pdf.stat().st_size} bytes)")

    # -----------------------------------------------------------------------
    # Step 4: Verification of Content, Structure & Selectable PDF Text
    # -----------------------------------------------------------------------
    print("\n[Step 4] Verifying exported artifact integrity and version traceability...")

    # Verify HTTP v1 vs v2 Markdown
    v1_md_text = http_v1_md.read_text(encoding="utf-8")
    v2_md_text = http_v2_md.read_text(encoding="utf-8")

    assert flawed_stmt in v1_md_text, "Error: HTTP v1 MD missing flawed statement!"
    assert flawed_stmt not in v2_md_text, "Error: HTTP v2 MD still contains flawed statement!"
    assert "RFC 9110 explicitly classifies POST as non-idempotent" in v2_md_text, "Error: HTTP v2 MD missing correction!"
    assert "Score: 74.0/100" in v1_md_text, "Error: HTTP v1 MD missing correct QC1 score!"
    assert "Score: 100.0/100" in v2_md_text, "Error: HTTP v2 MD missing correct QC1 score!"
    print("  [Pass] Markdown Content & QC Score Traceability verified.")

    # Verify PDF Selectable Text via pypdf
    v1_pdf_reader = PdfReader(str(http_v1_pdf))
    v2_pdf_reader = PdfReader(str(http_v2_pdf))
    dns_pdf_reader = PdfReader(str(dns_pdf))

    v1_pdf_text = "\n".join(p.extract_text() or "" for p in v1_pdf_reader.pages)
    v2_pdf_text = "\n".join(p.extract_text() or "" for p in v2_pdf_reader.pages)
    dns_pdf_text = "\n".join(p.extract_text() or "" for p in dns_pdf_reader.pages)

    print(f"  [PDF 1] HTTP v1 PDF: {len(v1_pdf_reader.pages)} pages, selectable text length: {len(v1_pdf_text)} chars")
    print(f"  [PDF 2] HTTP v2 PDF: {len(v2_pdf_reader.pages)} pages, selectable text length: {len(v2_pdf_text)} chars")
    print(f"  [PDF 3] DNS v1 PDF:  {len(dns_pdf_reader.pages)} pages, selectable text length: {len(dns_pdf_text)} chars")

    assert len(v1_pdf_reader.pages) >= 3
    assert len(v2_pdf_reader.pages) >= 3
    assert len(dns_pdf_reader.pages) >= 3

    assert flawed_stmt in v1_pdf_text, "Error: HTTP v1 PDF missing flawed text!"
    assert flawed_stmt not in v2_pdf_text, "Error: HTTP v2 PDF still contains flawed text!"
    assert "non-idempotent" in v2_pdf_text, "Error: HTTP v2 PDF missing correction!"
    assert "74.0" in v1_pdf_text, "Error: HTTP v1 PDF missing 74.0 QC score!"
    assert "100.0" in v2_pdf_text, "Error: HTTP v2 PDF missing 100.0 QC score!"

    # Verify DNS PDF
    assert "DNS Resolution" in dns_pdf_text
    assert "CNAME" in dns_pdf_text
    assert "Authoritative Citations" in dns_pdf_text or "RFC" in dns_pdf_text
    print("  [Pass] PDF Typography, Selectable Text & Vector Structure verified.")

    print("\n" + "=" * 80)
    print("ALL EXPORT DEMONSTRATION ARTIFACTS VERIFIED SUCCESSFULLY!")
    print("=" * 80)

    db.close()


if __name__ == "__main__":
    run_export_demo()
