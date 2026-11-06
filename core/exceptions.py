"""
Domain exception hierarchy for LessonForge AI.
Provides typed, meaningful exceptions across research, generation, QC, storage, and export.
"""

from __future__ import annotations


class LessonForgeError(Exception):
    """Base exception for all LessonForge AI errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error": self.__class__.__name__, "message": self.message, "details": self.details}


# ---------------------------------------------------------------------------
# Validation Exceptions
# ---------------------------------------------------------------------------
class ValidationError(LessonForgeError):
    """Raised when input validation fails (e.g. empty fields, bad schema)."""


class DurationExceededError(ValidationError):
    """Raised when total lesson duration exceeds the mandatory 45-minute limit."""

    def __init__(self, duration: int, max_allowed: int = 45) -> None:
        super().__init__(
            f"Lesson duration {duration} minutes exceeds maximum allowed duration of {max_allowed} minutes.",
            {"duration": duration, "max_allowed": max_allowed},
        )
        self.duration = duration
        self.max_allowed = max_allowed


class EmptyInputError(ValidationError):
    """Raised when mandatory fields like Lesson Title or Objective are empty."""


# ---------------------------------------------------------------------------
# Research Exceptions
# ---------------------------------------------------------------------------
class ResearchError(LessonForgeError):
    """Base exception for research discovery failures."""


class WebResearchError(ResearchError):
    """Raised when web search discovery fails."""


class BookResearchError(ResearchError):
    """Raised when book search (Google Books / Open Library) fails."""


class YouTubeResearchError(ResearchError):
    """Raised when YouTube discovery or validation fails."""


class SourceVerificationError(ResearchError):
    """Raised when a research source fails authenticity or schema verification."""


# ---------------------------------------------------------------------------
# LLM Generation Exceptions
# ---------------------------------------------------------------------------
class LLMGenerationError(LessonForgeError):
    """Raised when an LLM provider fails to generate or returns invalid output."""


class LLMAuthenticationError(LLMGenerationError):
    """Raised when API credentials for an LLM provider are missing or rejected."""


class LLMRateLimitError(LLMGenerationError):
    """Raised when LLM provider rate limits are exceeded."""


# ---------------------------------------------------------------------------
# Quality Control Exceptions
# ---------------------------------------------------------------------------
class QualityControlError(LessonForgeError):
    """Base exception for Quality Control audit failures."""


class FactualAuditError(QualityControlError):
    """Raised when QC Layer 1 (Research & Factual Accuracy) audit encounters a fatal error."""


class InstructionalAuditError(QualityControlError):
    """Raised when QC Layer 2 (Instructional Quality) audit encounters a fatal error."""


class RecommendationError(LessonForgeError):
    """Raised when recommendation review or patch application fails."""


# ---------------------------------------------------------------------------
# Storage and Export Exceptions
# ---------------------------------------------------------------------------
class StorageError(LessonForgeError):
    """Raised when SQLite database operations fail."""


class ExportError(LessonForgeError):
    """Raised when PDF or Markdown document export fails."""
