"""
Unit and integration tests for QC Layer 1: Research and Factual Accuracy Auditor.
Tests claim extraction, source corroboration, hallucination detection,
technical contradiction identification, and weighted criterion scoring.
"""

from __future__ import annotations

import copy
import pytest

from core.schemas import (
    LearnerLevel,
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
from generation.lesson_generator import LessonGenerator
from quality_control.qc_schemas import ClaimSupportStatus
from quality_control.research_auditor import ResearchAuditor


@pytest.fixture
def clean_http_lesson() -> LessonPlan:
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    return generator.generate(inp, force_offline=True).lesson_plan


def test_research_auditor_on_valid_http_lesson(clean_http_lesson: LessonPlan):
    auditor = ResearchAuditor()
    report = auditor.audit(clean_http_lesson)

    assert report.layer == QCLayer.FACTUAL_ACCURACY
    assert report.overall_score >= 80.0
    assert report.status == QCStatus.PASSED
    assert len(report.atomic_claims) > 0
    assert len(report.criterion_scores) == 4

    # Weights sum to 1.0 (100%)
    total_weight = sum(c.weight for c in report.criterion_scores)
    assert pytest.approx(total_weight, 0.001) == 1.0


def test_research_auditor_detects_post_idempotency_contradiction(clean_http_lesson: LessonPlan):
    # Introduce deliberate factual contradiction into Section 2
    flawed_lesson = copy.deepcopy(clean_http_lesson)
    flawed_lesson.sections[1].content_markdown += "\n\nNote: In our web framework, POST is idempotent and safe."

    auditor = ResearchAuditor()
    report = auditor.audit(flawed_lesson)

    # Must flag critical contradiction
    crit_findings = [f for f in report.critical_findings if "POST is idempotent" in f.description]
    assert len(crit_findings) >= 1
    assert report.status in (QCStatus.NEEDS_REVISION, QCStatus.FAILED)
    assert report.overall_score < 80.0


def test_research_auditor_detects_unresolvable_citations(clean_http_lesson: LessonPlan):
    # Introduce hallucinated citation ID not present in references
    flawed_lesson = copy.deepcopy(clean_http_lesson)
    flawed_lesson.sections[0].citations.append("src_hallucinated_ghost_id_999")
    flawed_lesson.sections[0].content_markdown += " According to [src_hallucinated_ghost_id_999], HTTP is magic."

    auditor = ResearchAuditor()
    report = auditor.audit(flawed_lesson)

    # Must flag unresolvable citation
    bad_cite_findings = [f for f in report.findings if "src_hallucinated_ghost_id_999" in f.description]
    assert len(bad_cite_findings) >= 1
    assert any(f.severity == QCSeverity.CRITICAL for f in bad_cite_findings)


def test_research_auditor_detects_empty_references(clean_http_lesson: LessonPlan):
    flawed_lesson = copy.deepcopy(clean_http_lesson)
    flawed_lesson.references = []

    auditor = ResearchAuditor()
    report = auditor.audit(flawed_lesson)

    assert any(f.criterion == "Citation Authenticity & Source Reliability" for f in report.findings)
    assert report.overall_score < 75.0


def test_research_auditor_handles_metadata_only_book(clean_http_lesson: LessonPlan):
    # Add a metadata-only book citation
    lesson = copy.deepcopy(clean_http_lesson)
    book_src = ResearchSource(
        id="src_test_book_meta",
        source_type=SourceType.BOOK,
        title="Advanced Networking Systems",
        url="https://books.google.com/test",
        snippet_or_summary="Catalog index entry for advanced networking systems.",
        provenance=ProvenanceStatus.RETRIEVED,
        metadata={"metadata_only": True, "full_text_read": False},
    )
    lesson.references.append(book_src)
    lesson.sections[0].citations = ["src_test_book_meta"]
    lesson.sections[0].content_markdown = "Detailed protocol mechanics are described in [src_test_book_meta]."

    auditor = ResearchAuditor()
    report = auditor.audit(lesson)

    # Claim should be classified as PARTIALLY_SUPPORTED due to metadata-only restriction
    meta_claims = [c for c in report.atomic_claims if "src_test_book_meta" in c.cited_source_ids]
    if meta_claims:
        assert meta_claims[0].support_status in (ClaimSupportStatus.PARTIALLY_SUPPORTED, ClaimSupportStatus.UNSUPPORTED)


def test_research_auditor_detects_dns_apex_contradiction():
    inp = LessonInput(
        title="DNS Resolution and DNS Record Types",
        learning_objective="Explain how recursive DNS resolution works and distinguish A, AAAA, CNAME, and MX records.",
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    dns_lesson = generator.generate(inp, force_offline=True).lesson_plan

    # Flaw: claim CNAME can be at apex
    flawed_dns = copy.deepcopy(dns_lesson)
    flawed_dns.sections[2].content_markdown += "\n\nCNAME can be placed at the root zone apex without restrictions."

    auditor = ResearchAuditor()
    report = auditor.audit(flawed_dns)

    assert any("CNAME" in f.description and f.severity == QCSeverity.CRITICAL for f in report.findings)
