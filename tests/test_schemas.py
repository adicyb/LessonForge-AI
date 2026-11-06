"""
Unit tests for core Pydantic schemas, validation invariants, provenance, and QC models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from core.exceptions import DurationExceededError, EmptyInputError, ValidationError
from core.schemas import (
    ActivityPlan,
    CriterionEvaluation,
    KnowledgeCheck,
    LearnerLevel,
    LessonInput,
    LessonPlan,
    ProvenanceStatus,
    QCFinding,
    QCLayer,
    QCReport,
    QCSeverity,
    QCStatus,
    Recommendation,
    RecommendationStatus,
    ResearchSource,
    SourceType,
    TimedSection,
)


# ---------------------------------------------------------------------------
# LessonInput Tests
# ---------------------------------------------------------------------------
def test_valid_lesson_input():
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        learner_level=LearnerLevel.BEGINNER,
        target_duration_minutes=45,
    )
    assert inp.title == "HTTP Requests and Responses"
    assert inp.target_duration_minutes == 45


def test_empty_title_input_fails():
    with pytest.raises((EmptyInputError, PydanticValidationError)):
        LessonInput(
            title="   ",
            learning_objective="Valid learning objective with sufficient length.",
        )


def test_empty_learning_objective_fails():
    with pytest.raises((EmptyInputError, PydanticValidationError)):
        LessonInput(
            title="Valid Lesson Title",
            learning_objective="",
        )


def test_lesson_input_duration_bounds():
    # Less than 10 mins should fail
    with pytest.raises(PydanticValidationError):
        LessonInput(
            title="Valid Lesson Title",
            learning_objective="Valid learning objective with sufficient length.",
            target_duration_minutes=5,
        )

    # Greater than 45 mins should fail
    with pytest.raises(PydanticValidationError):
        LessonInput(
            title="Valid Lesson Title",
            learning_objective="Valid learning objective with sufficient length.",
            target_duration_minutes=50,
        )


# ---------------------------------------------------------------------------
# LessonPlan & Duration Invariant Tests
# ---------------------------------------------------------------------------
def test_valid_lesson_plan_instantiation(sample_lesson_plan: LessonPlan):
    assert sample_lesson_plan.total_duration_minutes == 45
    assert len(sample_lesson_plan.sections) == 3
    assert sample_lesson_plan.guided_activity.duration_minutes == 10
    total = sum(s.duration_minutes for s in sample_lesson_plan.sections) + sample_lesson_plan.guided_activity.duration_minutes
    assert total == sample_lesson_plan.total_duration_minutes


def test_lesson_duration_exceeding_45_fails(valid_lesson_plan_data):
    data = dict(valid_lesson_plan_data)
    data["total_duration_minutes"] = 55
    data["sections"][0] = TimedSection(
        section_id="sec_1_proto_basics",
        title="Foundations of HTTP",
        duration_minutes=20,
        cognitive_focus="Conceptual Foundation",
        content_markdown="HTTP is a stateless protocol.",
    )
    # Sum is 20 + 15 + 10 + 10 = 55 > 45
    with pytest.raises((DurationExceededError, PydanticValidationError)):
        LessonPlan(**data)


def test_lesson_duration_sum_mismatch_fails(valid_lesson_plan_data):
    data = dict(valid_lesson_plan_data)
    data["total_duration_minutes"] = 40  # But sections sum to 45
    with pytest.raises((ValidationError, PydanticValidationError)):
        LessonPlan(**data)


def test_empty_sections_fails(valid_lesson_plan_data):
    data = dict(valid_lesson_plan_data)
    data["sections"] = []
    with pytest.raises(PydanticValidationError):
        LessonPlan(**data)


def test_missing_required_fields_fails():
    with pytest.raises(PydanticValidationError):
        LessonPlan(
            lesson_id="test_missing",
            title="Incomplete Lesson",
            # missing learning_objective, sections, etc.
        )


def test_shorter_valid_duration_lesson(valid_lesson_plan_data):
    """Refinement test: Lessons with duration <= 45 (e.g. 30 mins) are valid."""
    data = dict(valid_lesson_plan_data)
    data["total_duration_minutes"] = 30
    data["sections"] = [
        TimedSection(
            section_id="sec_1",
            title="Fast Introduction",
            duration_minutes=10,
            cognitive_focus="Concept",
            content_markdown="Quick intro to HTTP concepts.",
        ),
        TimedSection(
            section_id="sec_2",
            title="Status Codes Overview",
            duration_minutes=10,
            cognitive_focus="Worked Example",
            content_markdown="Quick look at 2xx, 4xx, 5xx status codes.",
        ),
    ]
    data["guided_activity"] = ActivityPlan(
        title="Quick 10-minute check",
        duration_minutes=10,
        instructions="Perform quick checks.",
        deliverable="Output log.",
    )
    plan = LessonPlan(**data)
    assert plan.total_duration_minutes == 30
    assert plan.total_duration_minutes <= 45


# ---------------------------------------------------------------------------
# ResearchSource & Provenance Tests
# ---------------------------------------------------------------------------
def test_valid_research_source(sample_web_source: ResearchSource):
    assert sample_web_source.source_type == SourceType.WEB
    assert sample_web_source.provenance == ProvenanceStatus.VERIFIED
    assert sample_web_source.credibility_score == 0.98


def test_invalid_source_url_fails():
    with pytest.raises(PydanticValidationError):
        ResearchSource(
            id="src_bad_url",
            source_type=SourceType.WEB,
            title="Bad URL Resource",
            url="not_a_valid_url_string",
            snippet_or_summary="Some snippet text that is long enough.",
        )


def test_source_url_without_scheme_fails():
    with pytest.raises(PydanticValidationError):
        ResearchSource(
            id="src_no_scheme",
            source_type=SourceType.WEB,
            title="No Scheme Resource",
            url="www.google.com/search",
            snippet_or_summary="Some snippet text that is long enough.",
        )


def test_invalid_provenance_value_fails():
    with pytest.raises(PydanticValidationError):
        ResearchSource(
            id="src_bad_provenance",
            source_type=SourceType.WEB,
            title="Bad Provenance Resource",
            url="https://example.com/test",
            snippet_or_summary="Some snippet text that is long enough.",
            provenance="GUESSED_BY_AI",  # Not a valid ProvenanceStatus enum
        )


def test_provenance_lifecycle_distinction():
    s_discovered = ResearchSource(
        id="src_disc",
        source_type=SourceType.WEB,
        title="Discovered Spec",
        url="https://www.rfc-editor.org/rfc/rfc9110",
        snippet_or_summary="Search query snippet preview only.",
        provenance=ProvenanceStatus.DISCOVERED,
    )
    s_retrieved = ResearchSource(
        id="src_ret",
        source_type=SourceType.WEB,
        title="Retrieved Spec",
        url="https://www.rfc-editor.org/rfc/rfc9110",
        snippet_or_summary="Full text downloaded and body extracted.",
        provenance=ProvenanceStatus.RETRIEVED,
    )
    s_verified = ResearchSource(
        id="src_ver",
        source_type=SourceType.WEB,
        title="Verified Spec",
        url="https://www.rfc-editor.org/rfc/rfc9110",
        snippet_or_summary="Cross-checked against IETF authoritative index.",
        provenance=ProvenanceStatus.VERIFIED,
    )
    assert s_discovered.provenance == "DISCOVERED"
    assert s_retrieved.provenance == "RETRIEVED"
    assert s_verified.provenance == "VERIFIED"


# ---------------------------------------------------------------------------
# Quality Control & Findings Tests
# ---------------------------------------------------------------------------
def test_valid_qc_finding():
    finding = QCFinding(
        id="find_1",
        layer=QCLayer.FACTUAL_ACCURACY,
        severity=QCSeverity.CRITICAL,
        criterion="RFC 9110 Method Idempotency",
        section_target="sec_2_methods",
        description="The text claims POST is idempotent, contradicting RFC 9110 §9.2.2.",
        evidence_quote="POST requests can be repeated indefinitely without side-effects.",
        suggested_fix="Correct the text: POST is inherently non-idempotent; contrast it with PUT and GET.",
    )
    assert finding.severity == QCSeverity.CRITICAL
    assert finding.layer == QCLayer.FACTUAL_ACCURACY


def test_qc_finding_invalid_severity_fails():
    with pytest.raises(PydanticValidationError):
        QCFinding(
            id="find_bad",
            layer=QCLayer.FACTUAL_ACCURACY,
            severity="CATASTROPHIC",  # Not in QCSeverity
            criterion="Validity",
            description="Bad severity test.",
            suggested_fix="Fix it.",
        )


def test_qc_report_structure(sample_lesson_plan: LessonPlan):
    report = QCReport(
        report_id="qc_rep_001",
        lesson_id=sample_lesson_plan.lesson_id,
        version_audited=1,
        layer=QCLayer.INSTRUCTIONAL_QUALITY,
        overall_score=92.5,
        status=QCStatus.PASSED,
        criterion_scores=[
            CriterionEvaluation(
                criterion_name="Learning Objective Alignment",
                weight=0.30,
                score=95.0,
                assessment="All stated objectives (GET/POST and status codes) are rigorously covered.",
            ),
            CriterionEvaluation(
                criterion_name="Pacing and Cognitive Scaffolding",
                weight=0.30,
                score=90.0,
                assessment="Structured 45-minute progression matches university level standards.",
            ),
        ],
        findings=[],
        summary="Excellent instructional pacing and objective alignment throughout the lesson.",
    )
    assert report.overall_score == 92.5
    assert report.status == QCStatus.PASSED
    assert len(report.criterion_scores) == 2


# ---------------------------------------------------------------------------
# Recommendation Tests
# ---------------------------------------------------------------------------
def test_recommendation_lifecycle():
    rec = Recommendation(
        id="rec_001",
        finding_id="find_1",
        layer=QCLayer.FACTUAL_ACCURACY,
        severity=QCSeverity.CRITICAL,
        section_target="sec_2_methods",
        issue_summary="Clarify GET vs POST idempotency according to RFC 9110.",
        suggested_content="GET is idempotent because multiple identical requests have the same effect as a single request.",
        status=RecommendationStatus.PENDING,
    )
    assert rec.status == RecommendationStatus.PENDING

    # Instructor accepts recommendation
    rec.status = RecommendationStatus.ACCEPTED
    assert rec.status == RecommendationStatus.ACCEPTED

    # System applies recommendation
    rec.status = RecommendationStatus.APPLIED
    assert rec.status == RecommendationStatus.APPLIED
