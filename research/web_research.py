"""
Web research discovery engine.
Searches the open web via DuckDuckGo, captures metadata and snippets,
calculates credibility and relevance, and preserves provenance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
import uuid

from core.exceptions import WebResearchError
from core.schemas import ProvenanceStatus, ResearchSource, SourceType
from research.source_validator import (
    calculate_credibility_score,
    calculate_relevance_score,
    deduplicate_sources,
    normalize_url,
)

logger = logging.getLogger(__name__)


class WebResearcher:
    """Discovers web resources across technical and academic domains."""

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def _execute_search(self, query: str, max_results: int) -> list[dict]:
        """Low-level search invocation with provider fallback."""
        try:
            import ddgs
            ddgs_client = ddgs.DDGS(timeout=self.timeout)
            return list(ddgs_client.text(query, max_results=max_results))
        except ImportError:
            import duckduckgo_search
            ddgs_client = duckduckgo_search.DDGS(timeout=self.timeout)
            return list(ddgs_client.text(query, max_results=max_results))

    def search(
        self,
        query: str,
        max_results: int = 5,
        raise_on_error: bool = False,
    ) -> list[ResearchSource]:
        """
        Execute web search query using DuckDuckGo.
        Returns a list of structured ResearchSource objects with DISCOVERED provenance.
        """
        if not query or not query.strip():
            return []

        cleaned_query = query.strip()
        raw_results: list[dict] = []

        try:
            raw_results = self._execute_search(cleaned_query, max_results=max_results)
        except Exception as err:
            logger.warning(f"Web research search encountered an error: {err}")
            if raise_on_error:
                raise WebResearchError(f"Web discovery failed for query '{query}': {err}") from err
            return []

        sources: list[ResearchSource] = []
        for item in raw_results:
            url = item.get("href") or item.get("link") or item.get("url")
            title = item.get("title", "").strip()
            snippet = item.get("body") or item.get("snippet") or ""

            if not url or not title or not snippet:
                continue

            try:
                norm_url = normalize_url(url)
                domain = urlparse(norm_url).netloc
            except Exception:
                continue

            credibility = calculate_credibility_score(norm_url, SourceType.WEB)
            relevance = calculate_relevance_score(cleaned_query, title, snippet)

            source = ResearchSource(
                id=f"src_web_{uuid.uuid4().hex[:8]}",
                source_type=SourceType.WEB,
                title=title,
                url=norm_url,
                authors_or_channel=domain,
                snippet_or_summary=snippet,
                provenance=ProvenanceStatus.DISCOVERED,
                credibility_score=credibility,
                retrieval_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                metadata={
                    "domain": domain,
                    "relevance_score": relevance,
                    "snippet_only": True,
                    "search_query": cleaned_query,
                },
            )
            sources.append(source)

        return deduplicate_sources(sources)
