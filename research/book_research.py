"""
Book research discovery engine.
Integrates with Google Books API v1 and Open Library REST APIs.
Captures genuine publication metadata and enforces the metadata-only provenance boundary.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
import uuid
import requests

from core.exceptions import BookResearchError
from core.schemas import ProvenanceStatus, ResearchSource, SourceType
from research.source_validator import (
    calculate_credibility_score,
    calculate_relevance_score,
    deduplicate_sources,
    normalize_url,
)

logger = logging.getLogger(__name__)


class BookResearcher:
    """Discovers published educational books and textbooks via public APIs."""

    def __init__(self, timeout: int = 8) -> None:
        self.timeout = timeout
        self.google_books_url = "https://www.googleapis.com/books/v1/volumes"
        self.open_library_url = "https://openlibrary.org/search.json"

    def search(
        self,
        query: str,
        max_results: int = 4,
        raise_on_error: bool = False,
    ) -> list[ResearchSource]:
        """
        Search for relevant academic and technical books.
        Attempts Google Books first; if rate-limited (HTTP 429) or failing,
        falls back to Open Library.
        """
        if not query or not query.strip():
            return []

        cleaned_query = query.strip()
        sources: list[ResearchSource] = []

        # 1. Attempt Google Books API
        try:
            google_sources = self._search_google_books(cleaned_query, max_results)
            sources.extend(google_sources)
        except Exception as err:
            logger.info(f"Google Books API unavailable or rate-limited ({err}). Falling back to Open Library.")

        # 2. If insufficient results, query Open Library
        if len(sources) < max_results:
            try:
                openlib_sources = self._search_open_library(cleaned_query, max_results - len(sources))
                sources.extend(openlib_sources)
            except Exception as err:
                logger.warning(f"Open Library search failed: {err}")
                if not sources and raise_on_error:
                    raise BookResearchError(f"Book search failed for query '{query}': {err}") from err

        return deduplicate_sources(sources)

    def _search_google_books(self, query: str, limit: int) -> list[ResearchSource]:
        """Query Google Books REST API and parse volume metadata."""
        params = {"q": query, "maxResults": min(limit, 10), "printType": "books", "langRestrict": "en"}
        resp = requests.get(self.google_books_url, params=params, timeout=self.timeout)

        if resp.status_code == 429:
            raise requests.HTTPError("Google Books API quota exceeded (HTTP 429).")
        resp.raise_for_status()

        data = resp.json()
        items = data.get("items", [])
        sources: list[ResearchSource] = []

        for item in items:
            vol_info = item.get("volumeInfo", {})
            title = vol_info.get("title", "").strip()
            authors = ", ".join(vol_info.get("authors", [])) or "Unknown Author"
            publisher = vol_info.get("publisher", "Standard Academic Press")
            pub_date = vol_info.get("publishedDate", "")
            description = vol_info.get("description", "")
            preview_url = vol_info.get("previewLink") or vol_info.get("infoLink")

            if not title or not preview_url:
                continue

            # Extract ISBN if present
            isbn = None
            for identifier in vol_info.get("industryIdentifiers", []):
                if identifier.get("type") in ("ISBN_13", "ISBN_10"):
                    isbn = identifier.get("identifier")
                    break

            snippet = description if len(description) >= 20 else f"{title} by {authors}. Published by {publisher} ({pub_date})."

            try:
                norm_url = normalize_url(preview_url)
            except Exception:
                continue

            credibility = calculate_credibility_score(norm_url, SourceType.BOOK, publisher)
            relevance = calculate_relevance_score(query, title, snippet)

            sources.append(
                ResearchSource(
                    id=f"src_book_{uuid.uuid4().hex[:8]}",
                    source_type=SourceType.BOOK,
                    title=f"{title} (Book)",
                    url=norm_url,
                    authors_or_channel=authors,
                    snippet_or_summary=snippet,
                    provenance=ProvenanceStatus.RETRIEVED,  # Metadata retrieved
                    credibility_score=credibility,
                    retrieval_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    metadata={
                        "publisher": publisher,
                        "published_date": pub_date,
                        "isbn": isbn,
                        "relevance_score": relevance,
                        "metadata_only": True,
                        "full_text_read": False,
                        "provider": "google_books",
                    },
                )
            )

        return sources

    def _search_open_library(self, query: str, limit: int) -> list[ResearchSource]:
        """Query Open Library Search API and parse volume metadata."""
        params = {"q": query, "limit": min(limit, 10)}
        resp = requests.get(self.open_library_url, params=params, timeout=self.timeout)
        resp.raise_for_status()

        data = resp.json()
        docs = data.get("docs", [])
        sources: list[ResearchSource] = []

        for doc in docs:
            title = doc.get("title", "").strip()
            authors_list = doc.get("author_name", [])
            authors = ", ".join(authors_list[:3]) if authors_list else "Unknown Author"
            publishers = doc.get("publisher", [])
            publisher = publishers[0] if publishers else "Academic Publisher"
            first_pub_year = str(doc.get("first_publish_year", ""))
            key = doc.get("key", "")  # e.g. /works/OL12345W

            if not title or not key:
                continue

            book_url = f"https://openlibrary.org{key}"
            isbn_list = doc.get("isbn", [])
            isbn = isbn_list[0] if isbn_list else None

            snippet = f"{title} by {authors}. Published by {publisher} ({first_pub_year}). Indexed in Open Library."

            try:
                norm_url = normalize_url(book_url)
            except Exception:
                continue

            credibility = calculate_credibility_score(norm_url, SourceType.BOOK, publisher)
            relevance = calculate_relevance_score(query, title, snippet)

            sources.append(
                ResearchSource(
                    id=f"src_book_{uuid.uuid4().hex[:8]}",
                    source_type=SourceType.BOOK,
                    title=f"{title} (Book)",
                    url=norm_url,
                    authors_or_channel=authors,
                    snippet_or_summary=snippet,
                    provenance=ProvenanceStatus.RETRIEVED,  # Metadata retrieved
                    credibility_score=credibility,
                    retrieval_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    metadata={
                        "publisher": publisher,
                        "published_date": first_pub_year,
                        "isbn": isbn,
                        "relevance_score": relevance,
                        "metadata_only": True,
                        "full_text_read": False,
                        "provider": "open_library",
                    },
                )
            )

        return sources
