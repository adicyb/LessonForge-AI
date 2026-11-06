"""
Unified Multi-Modal Research Coordinator.
Coordinates discovery across Web, Books, and YouTube, handles partial provider downtimes,
and seamlessly engages transparent offline fallbacks when external networks are unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

from core.schemas import ProvenanceStatus, ResearchSource, SourceType
from research.book_research import BookResearcher
from research.fallback_engine import FallbackKnowledgeEngine
from research.source_validator import deduplicate_sources
from research.web_research import WebResearcher
from research.youtube_research import YouTubeResearcher

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    """Consolidated multi-modal research payload."""

    web_sources: List[ResearchSource] = field(default_factory=list)
    book_sources: List[ResearchSource] = field(default_factory=list)
    youtube_sources: List[ResearchSource] = field(default_factory=list)
    all_sources: List[ResearchSource] = field(default_factory=list)
    is_fallback: bool = False
    provider_status: dict[str, str] = field(default_factory=dict)
    query_used: str = ""

    @property
    def provenance_counts(self) -> dict[str, int]:
        counts = {
            ProvenanceStatus.DISCOVERED.value: 0,
            ProvenanceStatus.RETRIEVED.value: 0,
            ProvenanceStatus.VERIFIED.value: 0,
        }
        for s in self.all_sources:
            counts[s.provenance.value] = counts.get(s.provenance.value, 0) + 1
        return counts


class ResearchEngine:
    """Coordinates multi-modal research discovery across external and offline sources."""

    def __init__(
        self,
        web_researcher: WebResearcher | None = None,
        book_researcher: BookResearcher | None = None,
        youtube_researcher: YouTubeResearcher | None = None,
    ) -> None:
        self.web = web_researcher or WebResearcher()
        self.books = book_researcher or BookResearcher()
        self.youtube = youtube_researcher or YouTubeResearcher()

    def discover(
        self,
        topic: str,
        learning_objective: str = "",
        force_offline: bool = False,
        max_web: int = 4,
        max_books: int = 3,
        max_youtube: int = 3,
    ) -> ResearchResult:
        """
        Execute comprehensive multi-modal research across Web, Books, and YouTube.
        If force_offline is True or all live providers fail, returns clearly labeled fallback knowledge.
        """
        query = f"{topic} {learning_objective}".strip() if learning_objective else topic.strip()
        provider_status: dict[str, str] = {}

        if force_offline:
            logger.info("Executing research in forced offline mode.")
            return self._build_fallback_result(topic, provider_status={"mode": "forced_offline"})

        # 1. Discover Web Sources
        web_sources: list[ResearchSource] = []
        try:
            web_sources = self.web.search(topic, max_results=max_web)
            provider_status["web"] = f"OK ({len(web_sources)} found)"
        except Exception as err:
            logger.warning(f"Web discovery failed: {err}")
            provider_status["web"] = f"FAILED ({err})"

        # 2. Discover Book Sources
        book_sources: list[ResearchSource] = []
        try:
            book_sources = self.books.search(topic, max_results=max_books)
            provider_status["books"] = f"OK ({len(book_sources)} found)"
        except Exception as err:
            logger.warning(f"Book discovery failed: {err}")
            provider_status["books"] = f"FAILED ({err})"

        # 3. Discover YouTube Sources
        youtube_sources: list[ResearchSource] = []
        try:
            youtube_sources = self.youtube.search(topic, max_results=max_youtube)
            provider_status["youtube"] = f"OK ({len(youtube_sources)} found)"
        except Exception as err:
            logger.warning(f"YouTube discovery failed: {err}")
            provider_status["youtube"] = f"FAILED ({err})"

        # If all three providers returned zero results, activate the labeled offline fallback
        total_live_found = len(web_sources) + len(book_sources) + len(youtube_sources)
        if total_live_found == 0:
            logger.info(f"Zero live sources discovered for query '{topic}'. Engaging fallback knowledge base.")
            provider_status["fallback_engaged"] = "True (Network/API unavailable or 0 results)"
            return self._build_fallback_result(topic, provider_status=provider_status)

        # Consolidate and deduplicate all discovered sources
        all_sources = deduplicate_sources(web_sources + book_sources + youtube_sources)

        return ResearchResult(
            web_sources=web_sources,
            book_sources=book_sources,
            youtube_sources=youtube_sources,
            all_sources=all_sources,
            is_fallback=False,
            provider_status=provider_status,
            query_used=query,
        )

    def _build_fallback_result(self, topic: str, provider_status: dict[str, str]) -> ResearchResult:
        """Construct a structured ResearchResult from the curated offline knowledge base."""
        fallback_sources = FallbackKnowledgeEngine.get_fallback_sources(topic)

        web = [s for s in fallback_sources if s.source_type == SourceType.WEB]
        books = [s for s in fallback_sources if s.source_type == SourceType.BOOK]
        youtube = [s for s in fallback_sources if s.source_type == SourceType.YOUTUBE]

        return ResearchResult(
            web_sources=web,
            book_sources=books,
            youtube_sources=youtube,
            all_sources=fallback_sources,
            is_fallback=True,
            provider_status=provider_status,
            query_used=topic,
        )
