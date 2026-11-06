"""
Specialized Quality Control schemas, claim classifications, and audit report models.
Defines atomic claim models, criterion score breakdowns, and patch comparison structures.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from core.schemas import (
    CriterionEvaluation,
    QCFinding,
    QCLayer,
    QCReport,
    QCSeverity,
    QCStatus,
    Recommendation,
    RecommendationStatus,
)


class ClaimSupportStatus(str, Enum):
    """Factual claim verification status against retrieved research evidence."""
    SUPPORTED = "SUPPORTED"                       # Corroborated by explicit text in cited sources
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"   # Source mentions topic but lacks full corroboration
    UNSUPPORTED = "UNSUPPORTED"                   # No cited source, or cited source does not state this
    CONTRADICTED = "CONTRADICTED"                 # Contradicted by authoritative standards or cited source
    UNVERIFIABLE = "UNVERIFIABLE"                 # Source is metadata-only or content is inaccessible


class AtomicClaim(BaseModel):
    """An individual factual or technical proposition extracted from a lesson."""
    model_config = ConfigDict(str_strip_whitespace=True)

    claim_id: str = Field(..., description="e.g. 'clm_sec1_1'")
    section_id: str = Field(..., description="Target lesson section ID")
    claim_text: str = Field(..., min_length=5, description="The specific factual statement")
    cited_source_ids: List[str] = Field(default_factory=list, description="Source IDs cited by this claim")
    support_status: ClaimSupportStatus = Field(default=ClaimSupportStatus.UNSUPPORTED)
    evidence_excerpt: Optional[str] = Field(None, description="Direct quote from research verifying or refuting claim")
    explanation: str = Field(..., min_length=5, description="Auditor reasoning for the support status")


class DiffItem(BaseModel):
    """Represents a discrete textual change produced by applying a recommendation."""
    model_config = ConfigDict(str_strip_whitespace=True)

    recommendation_id: str
    target_section: str
    patch_type: str = "REPLACE_SECTION"  # REPLACE_SECTION, APPEND_OUTCOME, UPDATE_TITLE, etc.
    before_content: str
    after_content: str
    timestamp: str


class DetailedQCReport(QCReport):
    """Enhanced audit report with categorized findings, atomic claims, and evaluator metadata."""
    evaluator_mode: str = Field(default="DETERMINISTIC_AUDITOR", description="LLM_AUDITOR or DETERMINISTIC_AUDITOR")
    critical_findings: List[QCFinding] = Field(default_factory=list)
    major_findings: List[QCFinding] = Field(default_factory=list)
    minor_findings: List[QCFinding] = Field(default_factory=list)
    atomic_claims: List[AtomicClaim] = Field(default_factory=list, description="Evaluated claims for Layer 1")
    recommendations: List[Recommendation] = Field(default_factory=list)

    @classmethod
    def from_report_components(
        cls,
        report_id: str,
        lesson_id: str,
        version_audited: int,
        layer: QCLayer,
        overall_score: float,
        status: QCStatus,
        criterion_scores: List[CriterionEvaluation],
        findings: List[QCFinding],
        summary: str,
        evaluator_mode: str = "DETERMINISTIC_AUDITOR",
        atomic_claims: List[AtomicClaim] | None = None,
        recommendations: List[Recommendation] | None = None,
    ) -> DetailedQCReport:
        crit = [f for f in findings if f.severity == QCSeverity.CRITICAL]
        maj = [f for f in findings if f.severity == QCSeverity.MAJOR]
        minr = [f for f in findings if f.severity in (QCSeverity.MINOR, QCSeverity.INFO)]

        return cls(
            report_id=report_id,
            lesson_id=lesson_id,
            version_audited=version_audited,
            layer=layer,
            overall_score=round(max(0.0, min(100.0, overall_score)), 1),
            status=status,
            criterion_scores=criterion_scores,
            findings=findings,
            critical_findings=crit,
            major_findings=maj,
            minor_findings=minr,
            atomic_claims=atomic_claims or [],
            recommendations=recommendations or [],
            summary=summary,
            evaluator_mode=evaluator_mode,
        )
