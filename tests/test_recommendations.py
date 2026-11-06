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
