"""
Unit and integration tests for the Instructor Recommendation and Patch Engine.
Tests recommendation review lifecycle (PENDING -> ACCEPTED / REJECTED -> APPLIED),
non-destructive lesson copying, duplicate application guards, and diff generation.
"""

from __future__ import annotations

import copy
import pytest

from core.exceptions import RecommendationError
from core.schemas import (
    LessonInput,
    LessonPlan,
    QCLayer,
    QCSeverity,
    QCStatus,
    Recommendation,
    RecommendationStatus,
)
from generation.lesson_generator import LessonGenerator
from quality_control.recommendation_engine import RecommendationEngine


@pytest.fixture
def sample_lesson() -> LessonPlan:
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    return generator.generate(inp, force_offline=True).lesson_plan


@pytest.fixture
def sample_recommendation() -> Recommendation:
    return Recommendation(
        id="rec_test_001",
        finding_id="find_001",
        layer=QCLayer.FACTUAL_ACCURACY,
        severity=QCSeverity.MAJOR,
        section_target="sec_http_2_methods",
        issue_summary="Clarify idempotency guarantees for GET vs POST.",
        suggested_content="Note: Under RFC 9110, GET is safe and idempotent, while POST is inherently non-idempotent.",
        status=RecommendationStatus.PENDING,
    )


def test_recommendation_lifecycle_transitions(sample_recommendation: Recommendation):
    engine = RecommendationEngine()

    # Initial state
    assert sample_recommendation.status == RecommendationStatus.PENDING

    # Instructor accepts
    rec_acc = engine.accept_recommendation(sample_recommendation, instructor_notes="Approved for integration.")
    assert rec_acc.status == RecommendationStatus.ACCEPTED
    assert rec_acc.instructor_notes == "Approved for integration."

    # Instructor modifies content
    rec_mod = engine.modify_recommendation(sample_recommendation, "Customized text by instructor.")
    assert rec_mod.suggested_content == "Customized text by instructor."

    # Instructor rejects
    rec_rej = engine.reject_recommendation(sample_recommendation, rejection_reason="Not needed for beginners.")
    assert rec_rej.status == RecommendationStatus.REJECTED
    assert "Not needed" in rec_rej.instructor_notes


def test_non_destructive_patch_application(sample_lesson: LessonPlan, sample_recommendation: Recommendation):
    engine = RecommendationEngine()
    engine.accept_recommendation(sample_recommendation)

    original_text = sample_lesson.sections[1].content_markdown
    original_version = sample_lesson.version

    revised_plan, diff = engine.apply_recommendation(sample_lesson, sample_recommendation)

    # 1. Original lesson must be completely untouched
    assert sample_lesson.sections[1].content_markdown == original_text
    assert sample_lesson.version == original_version
    assert id(sample_lesson) != id(revised_plan)

    # 2. Revised lesson has incremented version and patched text
    assert revised_plan.version == original_version + 1
    assert sample_recommendation.suggested_content in revised_plan.sections[1].content_markdown
    assert sample_recommendation.status == RecommendationStatus.APPLIED

    # 3. Diff item recorded
    assert diff.target_section == "sec_http_2_methods"
    assert diff.before_content == original_text
    assert diff.after_content == revised_plan.sections[1].content_markdown


def test_duplicate_application_prevention(sample_lesson: LessonPlan, sample_recommendation: Recommendation):
    engine = RecommendationEngine()
    engine.accept_recommendation(sample_recommendation)

    # First application succeeds
    revised_plan, diff = engine.apply_recommendation(sample_lesson, sample_recommendation)
    assert sample_recommendation.status == RecommendationStatus.APPLIED

    # Second application must be prevented
    with pytest.raises(RecommendationError):
        engine.apply_recommendation(revised_plan, sample_recommendation)


def test_batch_recommendations_application(sample_lesson: LessonPlan):
    engine = RecommendationEngine()

    rec1 = Recommendation(
        id="rec_b1",
        finding_id="f1",
        layer=QCLayer.FACTUAL_ACCURACY,
        severity=QCSeverity.MINOR,
        section_target="sec_http_1_foundations",
        issue_summary="Add note on RFC 9110.",
        suggested_content="RFC 9110 standardizes HTTP semantics.",
        status=RecommendationStatus.ACCEPTED,
    )
    rec2 = Recommendation(
        id="rec_b2",
        finding_id="f2",
        layer=QCLayer.INSTRUCTIONAL_QUALITY,
        severity=QCSeverity.MINOR,
        section_target="sec_http_3_status_codes",
        issue_summary="Clarify 502 vs 503.",
        suggested_content="502 is Bad Gateway, 503 is Service Unavailable.",
        status=RecommendationStatus.ACCEPTED,
    )

    revised_plan, diffs = engine.apply_batch_recommendations(sample_lesson, [rec1, rec2])

    assert len(diffs) == 2
    assert revised_plan.version == sample_lesson.version + 2
    assert "RFC 9110 standardizes" in revised_plan.sections[0].content_markdown
    assert "502 is Bad Gateway" in revised_plan.sections[2].content_markdown


# ---------------------------------------------------------------------------
# Regression Tests for True Content Modification & Verification Defect
# ---------------------------------------------------------------------------
def test_regression_flawed_http_recommendation_and_score_improvement(sample_lesson: LessonPlan):
    from quality_control.instructional_auditor import InstructionalAuditor
    from quality_control.research_auditor import ResearchAuditor

    auditor_qc1 = ResearchAuditor()
    auditor_qc2 = InstructionalAuditor()
    engine = RecommendationEngine()

    # 1. Start with deliberately flawed HTTP lesson containing factual distortion
    flawed_lesson = copy.deepcopy(sample_lesson)
    flawed_statement = "Note: In our web framework, POST is idempotent and safe."
    flawed_lesson.sections[1].content_markdown += f"\n\n{flawed_statement}"

    original_text = flawed_lesson.sections[1].content_markdown
    sec0_orig = flawed_lesson.sections[0].content_markdown
    sec2_orig = flawed_lesson.sections[2].content_markdown

    # 2. Run QC1 and record initial flawed score and finding
    qc1_initial = auditor_qc1.audit(flawed_lesson)
    initial_score = qc1_initial.overall_score
    assert initial_score < 75.0, f"Expected flawed score < 75.0, got {initial_score}"
    assert qc1_initial.status in (QCStatus.NEEDS_REVISION, QCStatus.FAILED)

    post_finding = next(
        f for f in qc1_initial.critical_findings
        if "POST is idempotent" in f.description or "POST is idempotent" in (f.evidence_quote or "")
    )
    assert post_finding is not None

    # 3. Locate and accept the corresponding recommendation
    rec = next(
        r for r in qc1_initial.recommendations
        if r.finding_id == post_finding.id or "POST is idempotent" in r.issue_summary
    )
    assert rec.status == RecommendationStatus.PENDING

    rec_accepted = engine.accept_recommendation(rec, instructor_notes="Approved RFC 9110 correction.")
    assert rec_accepted.status == RecommendationStatus.ACCEPTED

    # 4. Apply recommendation to lesson copy
    revised_lesson, diff = engine.apply_recommendation(flawed_lesson, rec_accepted)

    # 5. Verify the revision:
    # A. Incorrect statement must be GONE from revised lesson
    assert flawed_statement not in revised_lesson.sections[1].content_markdown
    assert "post is idempotent" not in revised_lesson.sections[1].content_markdown.lower()

    # B. Corrected statement must be PRESENT in revised lesson
    assert rec.suggested_content in revised_lesson.sections[1].content_markdown

    # C. Original lesson remains COMPLETELY UNCHANGED
    assert flawed_statement in flawed_lesson.sections[1].content_markdown
    assert flawed_lesson.sections[1].content_markdown == original_text
    assert flawed_lesson.version == 1
    assert id(flawed_lesson) != id(revised_lesson)

    # D. Unrelated sections must remain bitwise identical
    assert revised_lesson.sections[0].content_markdown == sec0_orig
    assert revised_lesson.sections[2].content_markdown == sec2_orig

    # E. Revision diff accurately captures before and after text
    assert flawed_statement in diff.before_content
    assert flawed_statement not in diff.after_content
    assert rec.suggested_content in diff.after_content

    # 6. Re-run QC1 independently on revised lesson:
    # Finding must disappear and score must strictly improve!
    qc1_revised = auditor_qc1.audit(revised_lesson)
    revised_score = qc1_revised.overall_score
    assert revised_score > initial_score, f"Score did not improve: initial={initial_score}, revised={revised_score}"
    assert revised_score >= 90.0
    assert qc1_revised.status == QCStatus.PASSED

    # Confirm the POST contradiction finding is completely gone
    assert not any("POST is idempotent" in f.description for f in qc1_revised.findings)

    # 7. Re-run QC2 independently on revised lesson:
    # Confirms both reports refer to revised lesson version (v2) and have no cross-talk
    qc2_revised = auditor_qc2.audit(revised_lesson)
    assert qc1_revised.version_audited == 2
    assert qc2_revised.version_audited == 2
    assert qc2_revised.layer == QCLayer.INSTRUCTIONAL_QUALITY
    assert qc1_revised.layer == QCLayer.FACTUAL_ACCURACY
    assert qc2_revised.status == QCStatus.PASSED


def test_rejection_leaves_lesson_untouched(sample_lesson: LessonPlan, sample_recommendation: Recommendation):
    engine = RecommendationEngine()
    engine.reject_recommendation(sample_recommendation, rejection_reason="Out of scope for beginner track.")
    assert sample_recommendation.status == RecommendationStatus.REJECTED

    # Lesson remains at version 1
    assert sample_lesson.version == 1
