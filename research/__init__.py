"""
Research module for LessonForge AI.
Coordinates multi-modal discovery across Web, Books, and YouTube with provenance tracking.
"""

from research.book_research import BookResearcher
from research.fallback_engine import FallbackKnowledgeEngine
from research.research_engine import ResearchEngine, ResearchResult
from research.source_validator import (
    calculate_credibility_score,
    calculate_relevance_score,
    deduplicate_sources,
    normalize_url,
)
from research.web_research import WebResearcher
from research.youtube_research import YouTubeResearcher

__all__ = [
    "ResearchEngine",
    "ResearchResult",
    "WebResearcher",
    "BookResearcher",
    "YouTubeResearcher",
    "FallbackKnowledgeEngine",
    "normalize_url",
    "calculate_credibility_score",
    "calculate_relevance_score",
    "deduplicate_sources",
]
