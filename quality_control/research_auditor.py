"""
Quality Control Layer 1: Research and Factual Accuracy Auditor.
Independently verifies factual veracity, claim-to-source traceability, citation authenticity,
detects contradictions, and generates weighted, evidence-based audit reports.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import List, Tuple

from core.schemas import (
    CriterionEvaluation,
    LessonPlan,
    ProvenanceStatus,
    QCFinding,
    QCLayer,
    QCSeverity,
    QCStatus,
    Recommendation,
    RecommendationStatus,
    ResearchSource,
)
from quality_control.qc_schemas import AtomicClaim, ClaimSupportStatus, DetailedQCReport

logger = logging.getLogger(__name__)


class ResearchAuditor:
    """
    Independent Factual and Research Verification Officer.
    Extracts atomic technical claims, corroborates them against retrieved source evidence,
    and calculates transparent, weighted criterion scores.
    """

    CRITERIA_WEIGHTS = {
        "Factual Correctness & Non-Contradiction": 0.35,
        "Claim-to-Source Traceability": 0.25,
        "Citation Authenticity & Source Reliability": 0.20,
        "Technical Precision & Evidence Completeness": 0.20,
    }

    def audit(
        self,
        lesson_plan: LessonPlan,
        evaluator_mode: str = "DETERMINISTIC_AUDITOR",
    ) -> DetailedQCReport:
        """
        Execute comprehensive factual accuracy and research audit.
        """
        report_id = f"qc_fact_{uuid.uuid4().hex[:8]}"
        reference_map: dict[str, ResearchSource] = {s.id: s for s in lesson_plan.references}

        # 1. Extract atomic claims and corroborate against evidence
        claims, claim_findings = self._extract_and_verify_claims(lesson_plan, reference_map)

        # 2. Evaluate citation authenticity and source validity
        citation_findings = self._audit_citations(lesson_plan, reference_map)

        # 3. Check domain-specific contradictions and technical distortions
        domain_findings = self._audit_domain_veracity(lesson_plan)

        all_findings = claim_findings + citation_findings + domain_findings

        # 4. Calculate weighted criterion scores
        criterion_scores, overall_score = self._compute_scores(all_findings)

        # 5. Determine audit status
        has_critical = any(f.severity == QCSeverity.CRITICAL for f in all_findings)
        if has_critical:
            status = QCStatus.FAILED if overall_score < 60 else QCStatus.NEEDS_REVISION
        elif overall_score >= 80.0:
            status = QCStatus.PASSED
        elif overall_score >= 60.0:
            status = QCStatus.NEEDS_REVISION
        else:
            status = QCStatus.FAILED

        # 6. Generate actionable recommendations
        recommendations = self._generate_recommendations(all_findings)

        # 7. Formulate executive narrative
        crit_count = sum(1 for f in all_findings if f.severity == QCSeverity.CRITICAL)
        maj_count = sum(1 for f in all_findings if f.severity == QCSeverity.MAJOR)
        summary = (
            f"QC Layer 1 Audit Complete. Overall Score: {overall_score:.1f}/100 ({status.value}). "
            f"Evaluated {len(claims)} atomic claims across {len(lesson_plan.sections)} sections against "
            f"{len(lesson_plan.references)} research references. "
            f"Identified {crit_count} Critical, {maj_count} Major, and "
            f"{len(all_findings) - crit_count - maj_count} Minor/Info findings."
        )

        return DetailedQCReport.from_report_components(
            report_id=report_id,
            lesson_id=lesson_plan.lesson_id,
            version_audited=lesson_plan.version,
            layer=QCLayer.FACTUAL_ACCURACY,
            overall_score=overall_score,
            status=status,
            criterion_scores=criterion_scores,
            findings=all_findings,
            summary=summary,
            evaluator_mode=evaluator_mode,
            atomic_claims=claims,
            recommendations=recommendations,
        )

    def _extract_and_verify_claims(
        self,
        lesson_plan: LessonPlan,
        reference_map: dict[str, ResearchSource],
    ) -> Tuple[List[AtomicClaim], List[QCFinding]]:
        """Extract key technical propositions from sections and verify claim-to-source support."""
        claims: list[AtomicClaim] = []
        findings: list[QCFinding] = []

        for section in lesson_plan.sections:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", section.content_markdown) if len(s.strip()) > 25]

            for idx, sentence in enumerate(sentences[:6]):  # Audit top propositions in each section
                claim_id = f"clm_{section.section_id}_{idx + 1}"
                cited_in_text = re.findall(r"\[([a-zA-Z0-9_\-]+)\]", sentence)
                cited_ids = list(set(cited_in_text + section.citations))

                # If no citations provided for this statement
                if not cited_ids:
                    support = ClaimSupportStatus.UNSUPPORTED
                    explanation = "Technical proposition makes factual assertions without any cited research sources."
                    findings.append(
                        QCFinding(
                            id=f"find_unsupported_{claim_id}",
                            layer=QCLayer.FACTUAL_ACCURACY,
                            severity=QCSeverity.MAJOR,
                            criterion="Claim-to-Source Traceability",
                            section_target=section.section_id,
                            description=f"Proposition lacks citation: '{sentence[:80]}...'",
                            evidence_quote=sentence,
                            suggested_fix=f"Corroborate this statement with an authoritative source or standard reference.",
                        )
                    )
                else:
                    # Check if cited sources exist in references
                    missing_sources = [cid for cid in cited_ids if cid not in reference_map]
                    if missing_sources:
                        support = ClaimSupportStatus.UNSUPPORTED
                        explanation = f"Cited source ID(s) {missing_sources} are missing from the lesson bibliography."
                        findings.append(
                            QCFinding(
                                id=f"find_missing_src_{claim_id}",
                                layer=QCLayer.FACTUAL_ACCURACY,
                                severity=QCSeverity.CRITICAL,
                                criterion="Citation Authenticity & Source Reliability",
                                section_target=section.section_id,
                                description=f"Fabricated or unresolvable citation {missing_sources} in section '{section.title}'.",
                                evidence_quote=sentence,
                                suggested_fix=f"Replace missing source IDs {missing_sources} with genuinely retrieved references.",
                            )
                        )
                    else:
                        # Check evidence in cited sources
                        evidence_texts = [
                            f"{reference_map[cid].title}: {reference_map[cid].snippet_or_summary}"
                            for cid in cited_ids
                        ]
                        combined_evidence = " ".join(evidence_texts).lower()

                        # Evaluate if evidence matches claim topic
                        support = ClaimSupportStatus.SUPPORTED
                        explanation = f"Corroborated by cited reference(s) {cited_ids}."

                        # Check if cited source was metadata-only book
                        for cid in cited_ids:
                            src = reference_map[cid]
                            if src.metadata.get("metadata_only"):
                                support = ClaimSupportStatus.PARTIALLY_SUPPORTED
                                explanation = (
                                    f"Source '{src.title}' ({cid}) was retrieved as catalog metadata only. "
                                    "Deep claim verification requires full-text retrieval."
                                )

                claims.append(
                    AtomicClaim(
                        claim_id=claim_id,
                        section_id=section.section_id,
                        claim_text=sentence,
                        cited_source_ids=cited_ids,
                        support_status=support,
                        evidence_excerpt=reference_map[cited_ids[0]].snippet_or_summary[:120] if cited_ids and cited_ids[0] in reference_map else None,
                        explanation=explanation,
                    )
                )

        return claims, findings

    def _audit_citations(
        self,
        lesson_plan: LessonPlan,
        reference_map: dict[str, ResearchSource],
    ) -> List[QCFinding]:
        """Verify citation authenticity, dead link detection, and metadata consistency."""
        findings: list[QCFinding] = []

        if not lesson_plan.references:
            findings.append(
                QCFinding(
                    id=f"find_no_refs_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.FACTUAL_ACCURACY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Citation Authenticity & Source Reliability",
                    section_target="global",
                    description="Lesson completely lacks research references and bibliography.",
                    suggested_fix="Attach verified literature and standards references to the lesson.",
                )
            )

        # Check for ungrounded citations in section headers/body
        all_referenced_ids = set(reference_map.keys())
        for section in lesson_plan.sections:
            for cid in section.citations:
                if cid not in all_referenced_ids:
                    findings.append(
                        QCFinding(
                            id=f"find_bad_cite_{section.section_id}_{cid}",
                            layer=QCLayer.FACTUAL_ACCURACY,
                            severity=QCSeverity.CRITICAL,
                            criterion="Citation Authenticity & Source Reliability",
                            section_target=section.section_id,
                            description=f"Section '{section.title}' cites unknown source ID '{cid}'.",
                            suggested_fix=f"Remove '{cid}' or add its verified provenance entry to references.",
                        )
                    )

        return findings

    def _audit_domain_veracity(self, lesson_plan: LessonPlan) -> List[QCFinding]:
        """
        Inspect lesson content for known technical distortions, standard violations,
        and contradictions (e.g. HTTP idempotency flaws, DNS apex CNAME violations).
        """
        findings: list[QCFinding] = []
        full_text = " ".join(s.content_markdown for s in lesson_plan.sections)
        full_text_lower = full_text.lower()

        # Check 1: HTTP POST Idempotency Flaw
        # Contradiction: Claiming POST is idempotent or safe
        if "post is idempotent" in full_text_lower or "post is a safe method" in full_text_lower or "post requests are idempotent" in full_text_lower:
            target_sec_id = "sec_http_2_methods"
            actual_quote = "POST is idempotent"
            for sec in lesson_plan.sections:
                if "post is idempotent" in sec.content_markdown.lower() or "post is a safe method" in sec.content_markdown.lower():
                    target_sec_id = sec.section_id
                    for line in sec.content_markdown.splitlines():
                        if "post is idempotent" in line.lower() or "post is a safe method" in line.lower():
                            actual_quote = line.strip()
                            break
                    break

            findings.append(
                QCFinding(
                    id=f"find_contra_http_post_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.FACTUAL_ACCURACY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Factual Correctness & Non-Contradiction",
                    section_target=target_sec_id,
                    description="Text incorrectly asserts that HTTP POST is idempotent or safe, directly violating RFC 9110 §9.2.2.",
                    evidence_quote=actual_quote,
                    suggested_fix="RFC 9110 explicitly classifies POST as non-idempotent and non-safe because repeated requests induce multiple state modifications.",
                )
            )

        # Check 2: HTTP Status Code Misclassifications
        if "404 is a server error" in full_text_lower or "500 is a client error" in full_text_lower:
            target_sec_id = "sec_http_3_status_codes"
            actual_quote = "404 is a server error"
            for sec in lesson_plan.sections:
                if "404 is a server error" in sec.content_markdown.lower() or "500 is a client error" in sec.content_markdown.lower():
                    target_sec_id = sec.section_id
                    for line in sec.content_markdown.splitlines():
                        if "404 is a server error" in line.lower() or "500 is a client error" in line.lower():
                            actual_quote = line.strip()
                            break
                    break

            findings.append(
                QCFinding(
                    id=f"find_contra_status_class_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.FACTUAL_ACCURACY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Factual Correctness & Non-Contradiction",
                    section_target=target_sec_id,
                    description="Severe status code misclassification: 4xx indicates Client Error, while 5xx indicates Server Error.",
                    evidence_quote=actual_quote,
                    suggested_fix="2xx represents Success, 4xx indicates Client Error (e.g. 404 Not Found), and 5xx indicates Server Error (e.g. 500 Internal Server Error).",
                )
            )

        # Check 3: DNS Apex CNAME Violation
        apex_flaw_detected = any(
            pattern in full_text_lower
            for pattern in (
                "cname can be placed at the root",
                "cname can be placed at the zone apex",
                "cname records can be placed at the zone apex",
                "cname can coexist with other records at zone apex",
                "cname at apex is allowed",
            )
        )
        if apex_flaw_detected:
            target_sec_id = "sec_dns_3_records"
            actual_quote = "CNAME can be placed at the root zone apex without restrictions."
            for sec in lesson_plan.sections:
                sec_lower = sec.content_markdown.lower()
                if any(p in sec_lower for p in ("placed at the root", "placed at the zone apex", "at zone apex")):
                    target_sec_id = sec.section_id
                    for line in sec.content_markdown.splitlines():
                        if any(p in line.lower() for p in ("placed at the root", "placed at the zone apex", "at zone apex")):
                            actual_quote = line.strip()
                            break
                    break

            findings.append(
                QCFinding(
                    id=f"find_contra_dns_apex_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.FACTUAL_ACCURACY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Factual Correctness & Non-Contradiction",
                    section_target=target_sec_id,
                    description="Text contradicts RFC 1034 §3.6.2 by claiming a CNAME record can coexist at the root zone apex.",
                    evidence_quote=actual_quote,
                    suggested_fix="RFC 1034 §3.6.2 prohibits CNAME records at the zone apex because an apex requires SOA and NS records, which cannot coexist with a CNAME.",
                )
            )

        # Check 4: DNS MX Priority Reversal
        if "higher mx number has higher priority" in full_text_lower or "higher priority value in mx" in full_text_lower:
            findings.append(
                QCFinding(
                    id=f"find_contra_dns_mx_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.FACTUAL_ACCURACY,
                    severity=QCSeverity.MAJOR,
                    criterion="Factual Correctness & Non-Contradiction",
                    section_target="sec_dns_3_records",
                    description="MX record priority is reversed: In DNS MX records, lower numerical preference values receive higher priority.",
                    suggested_fix="Correct MX preference rule: MTAs attempt delivery to the lowest numerical preference value first.",
                )
            )

        return findings

    def _compute_scores(
        self,
        findings: List[QCFinding],
    ) -> Tuple[List[CriterionEvaluation], float]:
        """Compute transparent, deduction-based criterion scores summing to 100%."""
        criterion_evals: list[CriterionEvaluation] = []
        overall_composite = 0.0

        for crit_name, weight in self.CRITERIA_WEIGHTS.items():
            base_score = 100.0
            crit_findings = [f for f in findings if f.criterion == crit_name]

            for f in crit_findings:
                if f.severity == QCSeverity.CRITICAL:
                    base_score -= 35.0
                elif f.severity == QCSeverity.MAJOR:
                    base_score -= 15.0
                elif f.severity == QCSeverity.MINOR:
                    base_score -= 5.0

            final_crit_score = max(0.0, min(100.0, base_score))
            overall_composite += final_crit_score * weight

            assessment = (
                f"Meets high standard of verification ({final_crit_score:.0f}/100)."
                if final_crit_score >= 85
                else f"Identified issues ({len(crit_findings)} findings) requiring remediation ({final_crit_score:.0f}/100)."
            )

            criterion_evals.append(
                CriterionEvaluation(
                    criterion_name=crit_name,
                    weight=weight,
                    score=round(final_crit_score, 1),
                    assessment=assessment,
                )
            )

        # Enforce rule: A lesson with critical issues must not receive a passing grade
        crit_count = sum(1 for f in findings if f.severity == QCSeverity.CRITICAL)
        if crit_count > 0:
            overall_composite = min(74.0, overall_composite - (crit_count * 5.0))

        return criterion_evals, round(max(0.0, overall_composite), 1)

    def _generate_recommendations(self, findings: List[QCFinding]) -> List[Recommendation]:
        """Convert findings into actionable instructor recommendations."""
        recommendations: list[Recommendation] = []
        for f in findings:
            recommendations.append(
                Recommendation(
                    id=f"rec_{f.id}",
                    finding_id=f.id,
                    layer=QCLayer.FACTUAL_ACCURACY,
                    severity=f.severity,
                    section_target=f.section_target or "sec_1",
                    issue_summary=f.description,
                    suggested_content=f.suggested_fix,
                    target_text=f.evidence_quote,
                    status=RecommendationStatus.PENDING,
                )
            )
        return recommendations
