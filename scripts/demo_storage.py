"""
LessonForge AI — Phase 5 Storage & Persistence Demonstration.
Demonstrates end-to-end SQLite persistence:
1. Lesson creation & initial versioning (v1).
2. Research source persistence.
3. Dual independent QC reports (Layer 1 & Layer 2).
4. Recommendation acceptance, patch application, and versioning (v2).
5. Database connection closure.
6. Database reconnection.
7. Verification of immutability, relational integrity, and survivability across restarts.
"""

from __future__ import annotations

import copy
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.schemas import (
    LessonInput,
    QCLayer,
    RecommendationStatus,
)
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.recommendation_engine import RecommendationEngine
from quality_control.research_auditor import ResearchAuditor
from storage.database import DatabaseManager
from storage.lesson_repository import LessonRepository


def run_storage_demo() -> None:
    demo_db_path = BASE_DIR / "data" / "demo_storage.db"
    if demo_db_path.exists():
        demo_db_path.unlink()
    # Also clean any wal/shm files if present
    for suffix in ("-wal", "-shm"):
        p = demo_db_path.with_name(demo_db_path.name + suffix)
        if p.exists():
            p.unlink()

    print("=" * 80)
    print("LESSONFORGE AI — PHASE 5 STORAGE & PERSISTENCE VERIFICATION")
    print("=" * 80)

    # -----------------------------------------------------------------------
    # Step 1: Generate Benchmark Lesson & Introduce Audited Flaw
    # -----------------------------------------------------------------------
    print("\n[Step 1] Synthesizing HTTP benchmark lesson and introducing known flaw...")
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    gen_result = generator.generate(inp, force_offline=True)
    lesson_v1 = gen_result.lesson_plan

    flawed_statement = "Note: In our web framework, POST is idempotent and safe."
    lesson_v1.sections[1].content_markdown += f"\n\n{flawed_statement}"
    print(f"  Lesson ID: {lesson_v1.lesson_id}")
    print(f"  Title: {lesson_v1.title}")
    print(f"  Duration: {lesson_v1.total_duration_minutes} minutes")
    print(f"  Initial Version: {lesson_v1.version}")

    # -----------------------------------------------------------------------
    # Step 2: Open SQLite Database & Save Lesson
    # -----------------------------------------------------------------------
    print(f"\n[Step 2] Initializing SQLite database at {demo_db_path}...")
    db_session1 = DatabaseManager(db_path=demo_db_path)
    repo_session1 = LessonRepository(db=db_session1)

    repo_session1.save_lesson(lesson_v1, author="AI_RESEARCH_ENGINE", change_summary="Initial benchmark synthesis")
    print(f"  Saved lesson '{lesson_v1.lesson_id}' to 'lessons' and 'lesson_versions' (v1).")

    # -----------------------------------------------------------------------
    # Step 3: Save Research Sources
    # -----------------------------------------------------------------------
    print("\n[Step 3] Persisting research bibliography sources...")
    saved_sources_count = repo_session1.save_research_sources(lesson_v1.lesson_id, lesson_v1.references)
    print(f"  Persisted {saved_sources_count} sources with full provenance tracking.")

    # -----------------------------------------------------------------------
    # Step 4: Audit Lesson with Dual Independent QC & Save Reports
    # -----------------------------------------------------------------------
    print("\n[Step 4] Executing independent dual QC audits...")
    auditor_qc1 = ResearchAuditor()
    auditor_qc2 = InstructionalAuditor()

    report_qc1 = auditor_qc1.audit(lesson_v1)
    report_qc2 = auditor_qc2.audit(lesson_v1)

    print(f"  QC Layer 1 (Factual Accuracy): Score = {report_qc1.overall_score} ({report_qc1.status.value})")
    print(f"  QC Layer 2 (Instructional Quality): Score = {report_qc2.overall_score} ({report_qc2.status.value})")

    repo_session1.save_qc_report(report_qc1)
    repo_session1.save_qc_report(report_qc2)
    print("  Persisted both independent QC reports to 'qc_reports'.")

    # -----------------------------------------------------------------------
    # Step 5: Accept Recommendation, Apply Patch & Save as Version 2
    # -----------------------------------------------------------------------
    print("\n[Step 5] Processing recommendation decision and creating Version 2...")
    rec_engine = RecommendationEngine()
    post_rec = next(r for r in report_qc1.recommendations if "POST is idempotent" in r.issue_summary)

    # Instructor accepts recommendation
    rec_accepted = rec_engine.accept_recommendation(
        post_rec,
        instructor_notes="Approved RFC 9110 non-idempotent semantics correction for Section 2.",
    )
    repo_session1.save_recommendation(rec_accepted, lesson_id=lesson_v1.lesson_id, version_number=1)
    print(f"  Recommendation '{post_rec.id}' accepted by instructor.")

    # Apply recommendation
    lesson_v2, diff = rec_engine.apply_recommendation(lesson_v1, rec_accepted)
    print(f"  Recommendation applied. Target: {diff.target_section}.")

    # Save revised lesson as Version 2
    repo_session1.save_lesson(
        lesson_v2,
        author="INSTRUCTOR_REVIEWER",
        change_summary="Remediated RFC 9110 POST idempotency contradiction in Section 2",
    )
    repo_session1.save_recommendation_decision(
        rec_id=post_rec.id,
        status=RecommendationStatus.APPLIED,
        notes="Applied to create Version 2",
    )
    print(f"  Saved revised lesson '{lesson_v2.lesson_id}' as Version {lesson_v2.version}.")

    # -----------------------------------------------------------------------
    # Step 6: Close Session 1 Database Connection
    # -----------------------------------------------------------------------
    print("\n[Step 6] Closing Session 1 database connection (simulating app shutdown)...")
    db_session1.close()
    del repo_session1
    del db_session1
    print("  Connection closed cleanly. Memory cleared.")

    # -----------------------------------------------------------------------
    # Step 7: Open Session 2 (New Process / Restart Simulation)
    # -----------------------------------------------------------------------
    print("\n[Step 7] Reopening database from disk with fresh Session 2 repository...")
    db_session2 = DatabaseManager(db_path=demo_db_path)
    repo_session2 = LessonRepository(db=db_session2)
    print("  Connected to existing SQLite database successfully.")

    # -----------------------------------------------------------------------
    # Step 8: Verify Complete Entity Retrieval
    # -----------------------------------------------------------------------
    print("\n[Step 8] Retrieving all entities and verifying state...")
    current_lesson = repo_session2.get_lesson(lesson_v1.lesson_id)
    assert current_lesson is not None
    print(f"  Current Active Version: {current_lesson.version}")
    print(f"  Current Title: {current_lesson.title}")

    versions = repo_session2.get_lesson_versions(lesson_v1.lesson_id)
    print(f"  Retrieved {len(versions)} immutable version snapshots:")
    for v in versions:
        print(f"    - Version {v['version_number']}: by {v['author']} | Summary: {v['change_summary']}")

    sources = repo_session2.get_research_sources(lesson_v1.lesson_id)
    print(f"  Retrieved {len(sources)} research citations from storage.")

    reports = repo_session2.get_qc_reports(lesson_v1.lesson_id)
    print(f"  Retrieved {len(reports)} independent QC audit reports:")
    for r in reports:
        print(f"    - Layer: {r.layer.value} | Version Audited: {r.version_audited} | Score: {r.overall_score} ({r.status.value})")

    recs = repo_session2.get_recommendations(lesson_v1.lesson_id)
    print(f"  Retrieved {len(recs)} recommendation decisions:")
    for rc in recs:
        print(f"    - ID: {rc.id} | Status: {rc.status.value} | Notes: {rc.instructor_notes}")

    # -----------------------------------------------------------------------
    # Step 9: Verify Immutability Invariant (Version 1 vs Version 2)
    # -----------------------------------------------------------------------
    print("\n[Step 9] Verifying Critical Invariant: Version 1 vs Version 2 Content...")
    v1_reloaded = repo_session2.get_lesson_version(lesson_v1.lesson_id, 1)
    v2_reloaded = repo_session2.get_lesson_version(lesson_v1.lesson_id, 2)

    assert v1_reloaded is not None
    assert v2_reloaded is not None

    v1_has_flaw = flawed_statement in v1_reloaded.sections[1].content_markdown
    v2_has_flaw = flawed_statement in v2_reloaded.sections[1].content_markdown
    v2_has_fix = "RFC 9110 explicitly classifies POST as non-idempotent" in v2_reloaded.sections[1].content_markdown

    print(f"  Version 1 contains original flawed statement: {v1_has_flaw} (Expected: True)")
    print(f"  Version 2 contains original flawed statement: {v2_has_flaw} (Expected: False)")
    print(f"  Version 2 contains peer-reviewed correction:  {v2_has_fix} (Expected: True)")

    assert v1_has_flaw, "CRITICAL ERROR: Version 1 was mutated!"
    assert not v2_has_flaw, "CRITICAL ERROR: Version 2 still contains flawed statement!"
    assert v2_has_fix, "CRITICAL ERROR: Version 2 does not contain the correction!"

    print("\n" + "=" * 80)
    print("ALL STORAGE PERSISTENCE & IMMUTABILITY INVARIANTS VERIFIED!")
    print("=" * 80)

    db_session2.close()


if __name__ == "__main__":
    run_storage_demo()
