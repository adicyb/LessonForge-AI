"""
Core Pydantic schemas and domain models for LessonForge AI.
Enforces typed contracts, research provenance, duration invariants, and QC structures.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.exceptions import DurationExceededError, EmptyInputError, ValidationError


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class SourceType(str, Enum):
    """Category of researched external material."""
    WEB = "WEB"
    BOOK = "BOOK"
    YOUTUBE = "YOUTUBE"


class ProvenanceStatus(str, Enum):
    """
    Research verification lifecycle:
    - DISCOVERED: Found via search/index query; snippet captured only.
    - RETRIEVED: Full resource metadata or full text fetched and parsed.
    - VERIFIED: Corroborated by independent authority or verified working URL.
    """
    DISCOVERED = "DISCOVERED"
    RETRIEVED = "RETRIEVED"
    VERIFIED = "VERIFIED"


class LearnerLevel(str, Enum):
    """Target learner audience complexity tier."""
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class QCSeverity(str, Enum):
    """Severity tier for Quality Control audit findings."""
    CRITICAL = "CRITICAL"   # Must fix: Factual distortion, broken URL, severe objective mismatch
    MAJOR = "MAJOR"         # Substantial improvement: Missing prerequisite, weak example
    MINOR = "MINOR"         # Minor polish: Stylistic phrasing, formatting, slight pacing adjustment
    INFO = "INFO"           # Positive observation or optional enhancement


class QCStatus(str, Enum):
    """Audit determination status."""
    PASSED = "PASSED"
    NEEDS_REVISION = "NEEDS_REVISION"
    FAILED = "FAILED"


class QCLayer(str, Enum):
    """Independent Quality Control evaluation layers."""
    FACTUAL_ACCURACY = "FACTUAL_ACCURACY"             # QC Layer 1: Research & Factual Veracity
    INSTRUCTIONAL_QUALITY = "INSTRUCTIONAL_QUALITY"   # QC Layer 2: Pedagogical & Curriculum Efficacy


class RecommendationStatus(str, Enum):
    """Instructor review decision lifecycle for QC recommendations."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


# ---------------------------------------------------------------------------
# Helper Validators
# ---------------------------------------------------------------------------
def validate_web_url(url: str) -> str:
    """Validate that string is a non-empty, syntactically valid HTTP/HTTPS URL."""
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid URL: '{url}'. Must include http/https scheme and domain.")
    return url.strip()


# ---------------------------------------------------------------------------
# Research Schemas
# ---------------------------------------------------------------------------
class ResearchSource(BaseModel):
    """Structured representation of an external research citation."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., description="Unique source identifier, e.g. 'src_1'")
    source_type: SourceType = Field(..., description="Web, Book, or YouTube")
    title: str = Field(..., min_length=2, description="Human-readable title of the resource")
    url: str = Field(..., description="Direct link or catalog reference")
    authors_or_channel: Optional[str] = Field(None, description="Author names or YouTube channel name")
    snippet_or_summary: str = Field(..., min_length=5, description="Retrieved textual excerpt or abstract")
    provenance: ProvenanceStatus = Field(
        default=ProvenanceStatus.DISCOVERED,
        description="Explicit provenance tracking (DISCOVERED, RETRIEVED, or VERIFIED)",
    )
    credibility_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Calculated domain/publisher authority index (0.0 to 1.0)",
    )
    retrieval_date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        description="ISO retrieval timestamp",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context e.g. ISBN, duration")

    @field_validator("url")
    @classmethod
    def check_url(cls, v: str) -> str:
        return validate_web_url(v)


# ---------------------------------------------------------------------------
# Lesson Plan Schemas
# ---------------------------------------------------------------------------
class TimedSection(BaseModel):
    """Atomic lesson component with explicit duration and cognitive focus."""
    model_config = ConfigDict(str_strip_whitespace=True)

    section_id: str = Field(..., description="Identifier e.g. 'sec_intro'")
    title: str = Field(..., min_length=2, description="Section heading")
    duration_minutes: int = Field(..., ge=1, le=45, description="Planned delivery time in minutes")
    cognitive_focus: str = Field(..., min_length=2, description="e.g. 'Conceptual Foundation', 'Worked Example'")
    content_markdown: str = Field(..., min_length=10, description="Rich educational body text")
    citations: List[str] = Field(default_factory=list, description="Referenced source IDs, e.g. ['src_1']")


class KnowledgeCheck(BaseModel):
    """Self-assessment or classroom knowledge-check question."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., description="e.g. 'kc_1'")
    question: str = Field(..., min_length=5, description="Assessment prompt")
    options: List[str] = Field(..., min_length=2, description="List of selectable answer options")
    correct_answer: str = Field(..., min_length=1, description="The correct answer text or option label")
    explanation: str = Field(..., min_length=5, description="Pedagogical rationale explaining why the answer is correct")


class ActivityPlan(BaseModel):
    """Hands-on guided practice or lab exercise."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=2, description="Lab / Activity title")
    duration_minutes: int = Field(..., ge=1, le=45, description="Allocated activity time")
    instructions: str = Field(..., min_length=10, description="Step-by-step student activity guidelines")
    deliverable: str = Field(..., min_length=3, description="Expected student output or artifact")
    evaluation_criteria: List[str] = Field(default_factory=list, description="Assessment rubric points")


class LessonInput(BaseModel):
    """Primary user inputs for initiating research and lesson synthesis."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=3, description="Lesson topic title")
    learning_objective: str = Field(..., min_length=10, description="Explicit pedagogical outcome")
    learner_level: LearnerLevel = Field(default=LearnerLevel.INTERMEDIATE)
    prerequisites: List[str] = Field(default_factory=list)
    target_duration_minutes: int = Field(default=45, ge=10, le=45)

    @field_validator("title", "learning_objective")
    @classmethod
    def check_non_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise EmptyInputError(f"Field '{info.field_name}' must not be empty or whitespace.")
        return v.strip()


class LessonPlan(BaseModel):
    """Complete, classroom-ready lesson document structure."""
    model_config = ConfigDict(str_strip_whitespace=True)

    lesson_id: str = Field(..., description="Unique UUID or slug")
    title: str = Field(..., min_length=3)
    learning_objective: str = Field(..., min_length=10)
    learner_level: LearnerLevel = Field(default=LearnerLevel.INTERMEDIATE)
    prerequisites: List[str] = Field(default_factory=list)
    total_duration_minutes: int = Field(..., ge=1, le=45, description="Sum of all module durations, must be <= 45")
    introduction: str = Field(..., min_length=10, description="Engaging hook and orientation")
    learning_outcomes: List[str] = Field(..., min_length=1, description="Concrete measurable outcomes")
    sections: List[TimedSection] = Field(..., min_length=1, description="Sequential instructional modules")
    guided_activity: ActivityPlan = Field(..., description="Hands-on lab/activity")
    knowledge_checks: List[KnowledgeCheck] = Field(..., min_length=1, description="Formative assessment questions")
    summary: str = Field(..., min_length=10, description="Key takeaways and recap")
    supplementary_videos: List[ResearchSource] = Field(default_factory=list, description="Curated YouTube links")
    references: List[ResearchSource] = Field(default_factory=list, description="Complete bibliography")
    version: int = Field(default=1, ge=1, description="Document revision counter")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="after")
    def validate_duration_budget(self) -> LessonPlan:
        """
        Validate duration constraints:
        1. total_duration_minutes must be <= 45.
        2. Sum of timed sections + guided activity must equal total_duration_minutes.
        """
        sections_sum = sum(s.duration_minutes for s in self.sections)
        activity_time = self.guided_activity.duration_minutes if self.guided_activity else 0
        computed_total = sections_sum + activity_time

        if self.total_duration_minutes > 45:
            raise DurationExceededError(self.total_duration_minutes, max_allowed=45)

        if computed_total != self.total_duration_minutes:
            raise ValidationError(
                f"Calculated sum of section durations ({sections_sum}m) and activity ({activity_time}m) "
                f"= {computed_total}m, which does not match total_duration_minutes ({self.total_duration_minutes}m)."
            )
        return self


# ---------------------------------------------------------------------------
# Quality Control Schemas
# ---------------------------------------------------------------------------
class QCFinding(BaseModel):
    """An individual audit finding generated by QC Layer 1 or QC Layer 2."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., description="e.g. 'find_fact_1'")
    layer: QCLayer = Field(..., description="Which auditor generated this finding")
    severity: QCSeverity = Field(..., description="CRITICAL, MAJOR, MINOR, INFO")
    criterion: str = Field(..., min_length=3, description="Evaluation rubric category")
    section_target: Optional[str] = Field(None, description="Affected section ID or 'global'")
    description: str = Field(..., min_length=5, description="Clear statement of the flaw or risk")
    evidence_quote: Optional[str] = Field(None, description="Direct quote from lesson or source")
    suggested_fix: str = Field(..., min_length=5, description="Remediation recommendation")


class CriterionEvaluation(BaseModel):
    """Detailed score breakdown for a specific rubric dimension."""
    criterion_name: str = Field(..., min_length=2)
    weight: float = Field(..., ge=0.0, le=1.0)
    score: float = Field(..., ge=0.0, le=100.0)
    assessment: str = Field(..., min_length=5)


class QCReport(BaseModel):
    """Comprehensive Quality Control Audit Report."""
    model_config = ConfigDict(str_strip_whitespace=True)

    report_id: str = Field(..., description="e.g. 'qc_fact_001'")
    lesson_id: str = Field(..., description="Target lesson ID")
    version_audited: int = Field(default=1, ge=1)
    layer: QCLayer = Field(..., description="Layer 1: FACTUAL_ACCURACY or Layer 2: INSTRUCTIONAL_QUALITY")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Calculated 0-100 composite score")
    status: QCStatus = Field(..., description="PASSED, NEEDS_REVISION, or FAILED")
    criterion_scores: List[CriterionEvaluation] = Field(default_factory=list)
    findings: List[QCFinding] = Field(default_factory=list)
    summary: str = Field(..., min_length=10, description="Executive evaluation narrative")
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Recommendation Schemas
# ---------------------------------------------------------------------------
class Recommendation(BaseModel):
    """Instructor-actionable recommendation derived from QC findings."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., description="e.g. 'rec_001'")
    finding_id: str = Field(..., description="Linked QCFinding ID")
    layer: QCLayer = Field(...)
    severity: QCSeverity = Field(...)
    section_target: str = Field(..., description="Section identifier to modify")
    issue_summary: str = Field(..., min_length=5)
    suggested_content: str = Field(..., min_length=5, description="Proposed textual or structural replacement")
    target_text: Optional[str] = Field(None, description="The specific text snippet or proposition targeted for replacement")
    status: RecommendationStatus = Field(default=RecommendationStatus.PENDING)
    instructor_notes: Optional[str] = Field(None, description="Optional override or rationale by instructor")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
