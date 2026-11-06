"""
Unit and integration tests for QC Layer 2: Instructional Quality Auditor.
Tests curriculum progression, objective alignment, Bloom's measurability,
activity quality, knowledge-check rigor, cognitive pacing, and QC layer isolation.
"""

from __future__ import annotations

import copy
import inspect
import pytest

from core.schemas import (
    ActivityPlan,
    KnowledgeCheck,
    LearnerLevel,
    LessonInput,
    LessonPlan,
    QCLayer,
    QCSeverity,
    QCStatus,
)
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor


@pytest.fixture
def clean_dns_lesson() -> LessonPlan:
    inp = LessonInput(
        title="DNS Resolution and DNS Record Types",
        learning_objective="Explain how recursive DNS resolution works and distinguish A, AAAA, CNAME, and MX records.",
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    return generator.generate(inp, force_offline=True).lesson_plan


def test_instructional_auditor_on_valid_dns_lesson(clean_dns_lesson: LessonPlan):
    auditor = InstructionalAuditor()
    report = auditor.audit(clean_dns_lesson)

    assert report.layer == QCLayer.INSTRUCTIONAL_QUALITY
    assert report.overall_score >= 80.0
    assert report.status == QCStatus.PASSED
    assert len(report.criterion_scores) == 5

    # Weights must sum to 1.0
    total_weight = sum(c.weight for c in report.criterion_scores)
    assert pytest.approx(total_weight, 0.001) == 1.0


def test_instructional_auditor_detects_missing_activity(clean_dns_lesson: LessonPlan):
    flawed_lesson = copy.deepcopy(clean_dns_lesson)
    # Simulate missing activity
    flawed_lesson.guided_activity = None  # type: ignore

    auditor = InstructionalAuditor()
    report = auditor.audit(flawed_lesson)

    assert any("missing a hands-on guided activity" in f.description for f in report.findings)
    assert any(f.severity == QCSeverity.CRITICAL for f in report.findings)
    assert report.status in (QCStatus.NEEDS_REVISION, QCStatus.FAILED)


def test_instructional_auditor_detects_bad_answer_key(clean_dns_lesson: LessonPlan):
    flawed_lesson = copy.deepcopy(clean_dns_lesson)
    # Correct answer not in options
    flawed_lesson.knowledge_checks[0].correct_answer = "Option That Does Not Exist In Options List"

    auditor = InstructionalAuditor()
    report = auditor.audit(flawed_lesson)

    bad_key_findings = [f for f in report.findings if "missing from options" in f.description]
    assert len(bad_key_findings) >= 1
    assert any(f.severity == QCSeverity.CRITICAL for f in bad_key_findings)


def test_instructional_auditor_detects_excessive_section_duration(clean_dns_lesson: LessonPlan):
    flawed_lesson = copy.deepcopy(clean_dns_lesson)
    # Section 1 takes 28 mins (> 20 mins cognitive attention threshold)
    flawed_lesson.sections[0].duration_minutes = 28
    flawed_lesson.sections[1].duration_minutes = 5
    flawed_lesson.sections[2].duration_minutes = 3
    flawed_lesson.guided_activity.duration_minutes = 9
    flawed_lesson.total_duration_minutes = 45

    auditor = InstructionalAuditor()
    report = auditor.audit(flawed_lesson)

    pacing_findings = [f for f in report.findings if "exceeding optimal cognitive attention span" in f.description]
    assert len(pacing_findings) >= 1


def test_qc_layer_isolation_rule():
    """
    Mandatory refinement test: QC Layer 2 must receive only lesson content, objective,
    learner level, and duration. It must NOT receive QC Layer 1 findings or scores.
    """
    auditor = InstructionalAuditor()
    sig = inspect.signature(auditor.audit)
    params = list(sig.parameters.keys())

    # Verify signature only accepts lesson_plan (which holds content, objective, level, duration)
    # and evaluator_mode
    assert "lesson_plan" in params
    assert "qc1_report" not in params
    assert "factual_report" not in params
    assert "qc_layer_1" not in params
