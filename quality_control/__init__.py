"""
Quality Control package for LessonForge AI.
Coordinates independent factual accuracy audits (QC 1), instructional quality audits (QC 2),
and the instructor recommendation workflow.
"""

from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.qc_schemas import AtomicClaim, ClaimSupportStatus, DetailedQCReport, DiffItem
from quality_control.recommendation_engine import RecommendationEngine
from quality_control.research_auditor import ResearchAuditor

__all__ = [
    "ResearchAuditor",
    "InstructionalAuditor",
    "RecommendationEngine",
    "DetailedQCReport",
    "AtomicClaim",
    "ClaimSupportStatus",
    "DiffItem",
]
