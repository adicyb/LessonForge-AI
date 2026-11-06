"""
Comprehensive Benchmark Verification Suite for LessonForge AI.
Tests Benchmark 1 (HTTP Requests and Responses) and Benchmark 2 (DNS Resolution and Records)
against all technical requirements, safe/idempotent semantics, DNS hierarchy,
duration budgeting (<=45 min), research provenance, dual QC rigor, and intentional flaw injection.
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
)
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.research_auditor import ResearchAuditor


# ---------------------------------------------------------------------------
# Benchmark 1: HTTP Requests and Responses
# ---------------------------------------------------------------------------
def test_benchmark_1_http_comprehensive_pedagogical_and_technical():
    generator = LessonGenerator()
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between HTTP 2xx, 4xx, and 5xx status codes.",
        learner_level=LearnerLevel.BEGINNER,
        target_duration_minutes=45,
    )
    result = generator.generate(inp, force_offline=True)
    lesson = result.lesson_plan

    # 1. Invariant: Duration Ceiling <= 45 minutes
    assert lesson.total_duration_minutes <= 45
    sec_sum = sum(s.duration_minutes for s in lesson.sections)
    act_dur = lesson.guided_activity.duration_minutes
    assert sec_sum + act_dur == lesson.total_duration_minutes

    # 2. Technical Veracity: GET vs POST Semantics (RFC 9110)
    full_text = "\n".join(s.content_markdown for s in lesson.sections) + "\n" + (lesson.guided_activity.instructions if lesson.guided_activity else "")

    # Safe and Idempotent Semantics
    assert "safe" in full_text.lower()
    assert "idempotent" in full_text.lower()
    assert "GET" in full_text
    assert "POST" in full_text
    # GET must be described as safe/idempotent
    assert any("safe" in s.content_markdown.lower() for s in lesson.sections if "GET" in s.content_markdown)
    # POST must NOT be described as idempotent
    assert "post is idempotent" not in full_text.lower()

    # 3. Status Code Taxonomy (2xx, 4xx, 5xx)
    assert "2xx" in full_text
    assert "4xx" in full_text
    assert "5xx" in full_text
    assert "200" in full_text or "201" in full_text
    assert "400" in full_text or "404" in full_text
    assert "500" in full_text or "503" in full_text

    # 4. Worked Examples & Practical Applications
    assert "curl" in full_text.lower() or "http/1.1" in full_text.lower()

    # 5. Guided Practical Activity
    assert lesson.guided_activity is not None
    assert len(lesson.guided_activity.instructions) > 50
    assert len(lesson.guided_activity.deliverable) > 10
    assert len(lesson.guided_activity.evaluation_criteria) >= 2

    # 6. Valid Knowledge Checks & Answer Key
    assert len(lesson.knowledge_checks) >= 2
    for kc in lesson.knowledge_checks:
        assert len(kc.question) > 10
        assert len(kc.options) >= 3
        assert kc.correct_answer in kc.options or any(kc.correct_answer in opt for opt in kc.options)
        assert len(kc.explanation) > 15

    # 7. Research Citation Traceability
    assert len(lesson.references) >= 3
    ref_ids = {r.id for r in lesson.references}
    cited_ids = {c for s in lesson.sections for c in s.citations}
    # All citations must resolve to actual reference bibliography
    assert cited_ids.issubset(ref_ids)

    # Provenance labels must be valid and transparent
    for ref in lesson.references:
        assert ref.provenance in (ProvenanceStatus.DISCOVERED, ProvenanceStatus.RETRIEVED, ProvenanceStatus.VERIFIED)
        assert ref.credibility_score >= 0.5

    # 8. Dual QC Auditing: Initial Draft must achieve Passing Grade
    auditor_qc1 = ResearchAuditor()
    auditor_qc2 = InstructionalAuditor()

    rep1 = auditor_qc1.audit(lesson)
    rep2 = auditor_qc2.audit(lesson)

    assert rep1.overall_score >= 90.0
    assert rep1.status == QCStatus.PASSED
    assert len(rep1.critical_findings) == 0

    assert rep2.overall_score >= 90.0
    assert rep2.status == QCStatus.PASSED
    assert len(rep2.critical_findings) == 0


# ---------------------------------------------------------------------------
# Benchmark 2: DNS Resolution and DNS Record Types
# ---------------------------------------------------------------------------
def test_benchmark_2_dns_comprehensive_pedagogical_and_technical():
    generator = LessonGenerator()
    inp = LessonInput(
        title="DNS Resolution and DNS Record Types",
        learning_objective="Trace the step-by-step resolution process of a domain name and differentiate between A, AAAA, CNAME, and MX record types.",
        learner_level=LearnerLevel.BEGINNER,
        target_duration_minutes=45,
    )
    result = generator.generate(inp, force_offline=True)
    lesson = result.lesson_plan

    # 1. Invariant: Duration Ceiling <= 45 minutes
    assert lesson.total_duration_minutes <= 45
    sec_sum = sum(s.duration_minutes for s in lesson.sections)
    act_dur = lesson.guided_activity.duration_minutes
    assert sec_sum + act_dur == lesson.total_duration_minutes

    # 2. Technical Veracity: DNS Hierarchy and Resolution
    full_text = "\n".join(s.content_markdown for s in lesson.sections) + "\n" + (lesson.guided_activity.instructions if lesson.guided_activity else "")

    # Hierarchy Components
    assert "root" in full_text.lower()
    assert "tld" in full_text.lower() or "top-level domain" in full_text.lower()
    assert "authoritative" in full_text.lower()

    # Resolution Modes
    assert "recursive" in full_text.lower()
    assert "iterative" in full_text.lower()

    # Record Types
    assert "`A`" in full_text or "**A**" in full_text or "a record" in full_text.lower()
    assert "`AAAA`" in full_text or "**AAAA**" in full_text or "aaaa record" in full_text.lower()
    assert "`CNAME`" in full_text or "**CNAME**" in full_text or "cname record" in full_text.lower()
    assert "`MX`" in full_text or "**MX**" in full_text or "mx record" in full_text.lower()

    # Caching and TTL
    assert "ttl" in full_text.lower() or "time-to-live" in full_text.lower()

    # 3. Practical Worked Examples (dig / nslookup)
    assert "```" in full_text
    assert "dig" in full_text.lower() or "nslookup" in full_text.lower()

    # 4. Guided Hands-On Lab
    assert lesson.guided_activity is not None
    assert len(lesson.guided_activity.instructions) > 50
    assert len(lesson.guided_activity.deliverable) > 10
    assert len(lesson.guided_activity.evaluation_criteria) >= 2

    # 5. Valid Knowledge Checks & Answer Key
    assert len(lesson.knowledge_checks) >= 2
    for kc in lesson.knowledge_checks:
        assert len(kc.question) > 10
        assert len(kc.options) >= 3
        assert len(kc.explanation) > 15

    # 6. Research Citation Traceability
    assert len(lesson.references) >= 3
    ref_ids = {r.id for r in lesson.references}
    cited_ids = {c for s in lesson.sections for c in s.citations}
    assert cited_ids.issubset(ref_ids)

    # 7. Dual QC Auditing: Passing Grade
    auditor_qc1 = ResearchAuditor()
    auditor_qc2 = InstructionalAuditor()

    rep1 = auditor_qc1.audit(lesson)
    rep2 = auditor_qc2.audit(lesson)

    assert rep1.overall_score >= 90.0
    assert rep1.status == QCStatus.PASSED
    assert len(rep1.critical_findings) == 0

    assert rep2.overall_score >= 90.0
    assert rep2.status == QCStatus.PASSED
    assert len(rep2.critical_findings) == 0


# ---------------------------------------------------------------------------
# Intentional Flaw Injection & Dual QC Isolation Verification
# ---------------------------------------------------------------------------
def test_intentional_flaws_detection_and_score_capping():
    generator = LessonGenerator()
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    clean_lesson = generator.generate(inp, force_offline=True).lesson_plan

    auditor_qc1 = ResearchAuditor()
    auditor_qc2 = InstructionalAuditor()

    # Test Flaw A: Factual Contradiction (POST is idempotent)
    flawed_factual = copy.deepcopy(clean_lesson)
    flawed_factual.sections[1].content_markdown += "\n\nNote: In our web framework, POST is idempotent and safe."

    rep_qc1_factual = auditor_qc1.audit(flawed_factual)
    # Must detect critical contradiction and cap score at <= 74.0
    assert rep_qc1_factual.overall_score <= 74.0
    assert rep_qc1_factual.status in (QCStatus.NEEDS_REVISION, QCStatus.FAILED)
    assert any("POST is idempotent" in f.description for f in rep_qc1_factual.critical_findings)

    # QC2 must remain independent: pedagogical structure is intact so QC2 passes
    rep_qc2_factual = auditor_qc2.audit(flawed_factual)
    assert rep_qc2_factual.overall_score >= 90.0
    assert rep_qc2_factual.status == QCStatus.PASSED

    # Test Flaw B: DNS Zone Apex CNAME Contradiction
    dns_inp = LessonInput(
        title="DNS Resolution and DNS Record Types",
        learning_objective="Trace the step-by-step resolution process of a domain name.",
        target_duration_minutes=45,
    )
    dns_lesson = generator.generate(dns_inp, force_offline=True).lesson_plan
    flawed_dns = copy.deepcopy(dns_lesson)
    flawed_dns.sections[1].content_markdown += "\n\nStandard rule: CNAME records can be placed at the zone apex with MX records."

    rep_dns_qc1 = auditor_qc1.audit(flawed_dns)
    assert rep_dns_qc1.overall_score <= 74.0
    assert any("apex" in f.description.lower() for f in rep_dns_qc1.critical_findings)

    # Test Flaw C: Pedagogical Defect (Missing Guided Activity)
    flawed_pedagogy = copy.deepcopy(clean_lesson)
    flawed_pedagogy.guided_activity = None  # type: ignore

    rep_qc2_pedagogy = auditor_qc2.audit(flawed_pedagogy)
    # Must flag instructional defect
    assert rep_qc2_pedagogy.overall_score <= 74.0
    assert any(f.severity == QCSeverity.CRITICAL for f in rep_qc2_pedagogy.findings)

    # QC1 on flawed pedagogy remains factual: QC1 passes because facts weren't altered
    rep_qc1_pedagogy = auditor_qc1.audit(flawed_pedagogy)
    assert rep_qc1_pedagogy.overall_score >= 90.0
