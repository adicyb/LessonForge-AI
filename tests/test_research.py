"""
Comprehensive unit and integration tests for Phase 2: Multi-Modal Research Engine.
Tests URL normalization, deduplication, credibility scoring, web discovery,
Google Books / Open Library APIs, YouTube discovery, provenance transitions,
and offline fallback handling with complete offline mock coverage.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
import requests

from core.exceptions import BookResearchError, WebResearchError, YouTubeResearchError
from core.schemas import ProvenanceStatus, ResearchSource, SourceType
from research.book_research import BookResearcher
from research.fallback_engine import FallbackKnowledgeEngine
from research.research_engine import ResearchEngine
from research.source_validator import (
    calculate_credibility_score,
    calculate_relevance_score,
    deduplicate_sources,
    normalize_url,
)
from research.web_research import WebResearcher
from research.youtube_research import (
    YouTubeResearcher,
    extract_youtube_video_id,
    parse_duration_to_seconds,
)


# ---------------------------------------------------------------------------
# 1. URL Normalization Tests
# ---------------------------------------------------------------------------
def test_normalize_url_strips_tracking_parameters():
    raw = "https://example.com/guide/?utm_source=twitter&utm_medium=social&ref=tech_daily&id=42"
    normalized = normalize_url(raw)
    assert "utm_source" not in normalized
    assert "ref" not in normalized
    assert "id=42" in normalized
    assert normalized == "https://example.com/guide?id=42"


def test_normalize_url_strips_default_ports_and_trailing_slashes():
    raw_http = "http://EXAMPLE.COM:80/tutorials/http/"
    raw_https = "https://EXAMPLE.COM:443/tutorials/http/"
    assert normalize_url(raw_http) == "http://example.com/tutorials/http"
    assert normalize_url(raw_https) == "https://example.com/tutorials/http"


def test_normalize_url_empty_or_invalid_raises():
    with pytest.raises(ValueError):
        normalize_url("")
    with pytest.raises(ValueError):
        normalize_url("   ")


# ---------------------------------------------------------------------------
# 2. Credibility & Relevance Scoring Tests
# ---------------------------------------------------------------------------
def test_credibility_score_tiers():
    # Tier 1: Standards / RFCs -> 1.0
    assert calculate_credibility_score("https://www.rfc-editor.org/rfc/rfc9110", SourceType.WEB) == 1.0
    assert calculate_credibility_score("https://www.ietf.org/rfc/rfc1035.txt", SourceType.WEB) == 1.0

    # Tier 2: Official Tech Documentation -> 0.95
    assert calculate_credibility_score("https://developer.mozilla.org/en-US/docs/Web/HTTP", SourceType.WEB) == 0.95
    assert calculate_credibility_score("https://docs.python.org/3/library/urllib.request.html", SourceType.WEB) == 0.95

    # Tier 3: Universities (.edu) -> 0.92
    assert calculate_credibility_score("https://cs.stanford.edu/people/networking", SourceType.WEB) == 0.92

    # Tier 4: Major Educational Textbook Catalog -> 0.90
    assert calculate_credibility_score("https://openlibrary.org/works/OL12345W", SourceType.BOOK) == 0.90

    # Default Tech Blog -> 0.65
    assert calculate_credibility_score("https://mytechblog.io/http-status-codes", SourceType.WEB) == 0.65


def test_relevance_score_computation():
    query = "HTTP GET and POST methods"
    high_match_title = "Complete Guide to HTTP GET and POST Methods in Web Protocols"
    high_match_snippet = "Explaining HTTP GET vs POST request methods and payloads."
    low_match_title = "Introduction to Database SQL Queries"
    low_match_snippet = "Learn how to select from tables and update rows."

    high_score = calculate_relevance_score(query, high_match_title, high_match_snippet)
    low_score = calculate_relevance_score(query, low_match_title, low_match_snippet)

    assert high_score > 0.70
    assert low_score < 0.30


# ---------------------------------------------------------------------------
# 3. Deduplication Tests
# ---------------------------------------------------------------------------
def test_deduplicate_sources_by_normalized_url():
    src1 = ResearchSource(
        id="src_1",
        source_type=SourceType.WEB,
        title="MDN HTTP Methods",
        url="https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods?utm_source=google",
        snippet_or_summary="HTTP methods guide snippet one.",
        provenance=ProvenanceStatus.DISCOVERED,
        credibility_score=0.95,
    )
    src2 = ResearchSource(
        id="src_2",
        source_type=SourceType.WEB,
        title="MDN HTTP Methods Clean",
        url="https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods",
        snippet_or_summary="HTTP methods guide snippet two retrieved.",
        provenance=ProvenanceStatus.RETRIEVED,
        credibility_score=0.95,
    )
    src3 = ResearchSource(
        id="src_3",
        source_type=SourceType.WEB,
        title="RFC 9110",
        url="https://www.rfc-editor.org/rfc/rfc9110",
        snippet_or_summary="RFC 9110 snippet.",
        provenance=ProvenanceStatus.RETRIEVED,
        credibility_score=1.0,
    )

    deduped = deduplicate_sources([src1, src2, src3])
    assert len(deduped) == 2
    # Verify the RETRIEVED provenance was favored over DISCOVERED for MDN
    mdn_source = next(s for s in deduped if "developer.mozilla.org" in s.url)
    assert mdn_source.provenance == ProvenanceStatus.RETRIEVED


# ---------------------------------------------------------------------------
# 4. Web Research Discovery (Mocked)
# ---------------------------------------------------------------------------
@patch("research.web_research.WebResearcher.search")
def test_web_research_success_mocked(mock_search):
    mock_search.return_value = [
        ResearchSource(
            id="src_web_1",
            source_type=SourceType.WEB,
            title="RFC 9110 - HTTP Semantics",
            url="https://www.rfc-editor.org/rfc/rfc9110",
            snippet_or_summary="The standard HTTP specification.",
            provenance=ProvenanceStatus.DISCOVERED,
            credibility_score=1.0,
        )
    ]
    researcher = WebResearcher()
    results = researcher.search("HTTP Requests")
    assert len(results) == 1
    assert results[0].source_type == SourceType.WEB
    assert results[0].provenance == ProvenanceStatus.DISCOVERED


def test_web_research_empty_query():
    researcher = WebResearcher()
    assert researcher.search("") == []
    assert researcher.search("   ") == []


@patch("research.web_research.WebResearcher._execute_search")
def test_web_research_handles_network_failure(mock_exec):
    mock_exec.side_effect = requests.ConnectionError("Network connection reset")
    researcher = WebResearcher()

    # Graceful return when raise_on_error is False
    res = researcher.search("HTTP Requests", raise_on_error=False)
    assert res == []

    # Raises WebResearchError when raise_on_error is True
    with pytest.raises(WebResearchError):
        researcher.search("HTTP Requests", raise_on_error=True)


# ---------------------------------------------------------------------------
# 5. Book Research Discovery & Metadata Parsing (Mocked)
# ---------------------------------------------------------------------------
@patch("requests.get")
def test_google_books_metadata_parsing(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "volumeInfo": {
                    "title": "Computer Networking: A Top-Down Approach",
                    "authors": ["James F. Kurose", "Keith W. Ross"],
                    "publisher": "Pearson",
                    "publishedDate": "2020",
                    "description": "Comprehensive textbook covering computer networking from application to physical layers.",
                    "previewLink": "https://books.google.com/books?id=12345",
                    "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9780136681557"}],
                }
            }
        ]
    }
    mock_get.return_value = mock_response

    researcher = BookResearcher()
    results = researcher.search("Computer Networking")

    assert len(results) == 1
    book = results[0]
    assert book.source_type == SourceType.BOOK
    assert "Kurose" in book.authors_or_channel
    assert book.provenance == ProvenanceStatus.RETRIEVED
    assert book.metadata.get("metadata_only") is True
    assert book.metadata.get("full_text_read") is False
    assert book.metadata.get("isbn") == "9780136681557"


@patch("requests.get")
def test_book_research_fallback_to_open_library_on_429(mock_get):
    # First call (Google Books) returns 429 quota exceeded
    google_resp = MagicMock()
    google_resp.status_code = 429

    # Second call (Open Library) returns 200 with docs
    openlib_resp = MagicMock()
    openlib_resp.status_code = 200
    openlib_resp.json.return_value = {
        "docs": [
            {
                "title": "Computer Networks",
                "author_name": ["Andrew S. Tanenbaum"],
                "publisher": ["Prentice Hall"],
                "first_publish_year": 2011,
                "key": "/works/OL25841W",
                "isbn": ["9780132126953"],
            }
        ]
    }

    mock_get.side_effect = [google_resp, openlib_resp]

    researcher = BookResearcher()
    results = researcher.search("Computer Networks")

    assert len(results) == 1
    assert "Tanenbaum" in results[0].authors_or_channel
    assert "openlibrary.org" in results[0].url
    assert results[0].metadata.get("provider") == "open_library"


# ---------------------------------------------------------------------------
# 6. YouTube Discovery & ID / Duration Validation
# ---------------------------------------------------------------------------
def test_extract_youtube_video_id():
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=iYM2zFP3Zn0") == "iYM2zFP3Zn0"
    assert extract_youtube_video_id("https://youtu.be/iYM2zFP3Zn0") == "iYM2zFP3Zn0"
    assert extract_youtube_video_id("https://www.youtube.com/embed/iYM2zFP3Zn0") == "iYM2zFP3Zn0"
    assert extract_youtube_video_id("https://example.com/video") is None


def test_parse_duration_to_seconds():
    assert parse_duration_to_seconds("02:30") == 150
    assert parse_duration_to_seconds("16:00") == 960
    assert parse_duration_to_seconds("01:27:55") == 5275
    assert parse_duration_to_seconds("invalid") is None
    assert parse_duration_to_seconds(None) is None


@patch("research.youtube_research.YouTubeResearcher._execute_search")
def test_youtube_researcher_validates_metadata(mock_videos):
    mock_videos.return_value = [
        {
            "content": "https://www.youtube.com/watch?v=iYM2zFP3Zn0",
            "title": "HTTP Crash Course & Status Codes",
            "publisher": "Traversy Media",
            "duration": "16:00",
            "description": "Explaining HTTP methods and status codes.",
        },
        {
            # Invalid item without genuine YouTube video ID
            "content": "https://vimeo.com/999999",
            "title": "Invalid video",
            "publisher": "Unknown",
            "duration": "10:00",
            "description": "Non-youtube link.",
        },
    ]

    researcher = YouTubeResearcher()
    results = researcher.search("HTTP Crash Course")

    assert len(results) == 1
    yt = results[0]
    assert yt.source_type == SourceType.YOUTUBE
    assert yt.metadata.get("video_id") == "iYM2zFP3Zn0"
    assert yt.metadata.get("duration_seconds") == 960
    assert yt.provenance == ProvenanceStatus.RETRIEVED


# ---------------------------------------------------------------------------
# 7. Curated Offline Fallback Engine Tests
# ---------------------------------------------------------------------------
def test_fallback_engine_http_sources():
    sources = FallbackKnowledgeEngine.get_fallback_sources("HTTP Requests and Responses")
    assert len(sources) >= 5

    # Check that Web, Books, and YouTube are all present
    types = {s.source_type for s in sources}
    assert SourceType.WEB in types
    assert SourceType.BOOK in types
    assert SourceType.YOUTUBE in types

    # Verify all fallback items are explicitly labeled
    for s in sources:
        assert s.metadata.get("is_offline_fallback") is True
        assert s.provenance == ProvenanceStatus.RETRIEVED


def test_fallback_engine_dns_sources():
    sources = FallbackKnowledgeEngine.get_fallback_sources("DNS Resolution and Record Types")
    assert len(sources) >= 5

    types = {s.source_type for s in sources}
    assert SourceType.WEB in types
    assert SourceType.BOOK in types
    assert SourceType.YOUTUBE in types

    for s in sources:
        assert s.metadata.get("is_offline_fallback") is True


# ---------------------------------------------------------------------------
# 8. Unified Research Coordinator Tests
# ---------------------------------------------------------------------------
def test_research_engine_forced_offline():
    engine = ResearchEngine()
    result = engine.discover("HTTP Requests and Responses", force_offline=True)

    assert result.is_fallback is True
    assert len(result.all_sources) > 0
    assert len(result.web_sources) > 0
    assert len(result.book_sources) > 0
    assert len(result.youtube_sources) > 0
    assert result.provenance_counts[ProvenanceStatus.RETRIEVED.value] > 0


def test_research_engine_partial_provider_failure():
    mock_web = MagicMock()
    mock_web.search.return_value = [
        ResearchSource(
            id="src_w1",
            source_type=SourceType.WEB,
            title="MDN HTTP",
            url="https://developer.mozilla.org/en-US/docs/Web/HTTP",
            snippet_or_summary="MDN HTTP overview.",
            provenance=ProvenanceStatus.DISCOVERED,
        )
    ]

    mock_books = MagicMock()
    mock_books.search.side_effect = BookResearchError("Google Books & Open Library unreachable")

    mock_youtube = MagicMock()
    mock_youtube.search.return_value = [
        ResearchSource(
            id="src_yt1",
            source_type=SourceType.YOUTUBE,
            title="HTTP Video",
            url="https://www.youtube.com/watch?v=iYM2zFP3Zn0",
            snippet_or_summary="HTTP video tutorial.",
            provenance=ProvenanceStatus.RETRIEVED,
        )
    ]

    engine = ResearchEngine(
        web_researcher=mock_web,
        book_researcher=mock_books,
        youtube_researcher=mock_youtube,
    )
    result = engine.discover("HTTP Methods")

    assert result.is_fallback is False
    assert len(result.all_sources) == 2
    assert "OK" in result.provider_status["web"]
    assert "FAILED" in result.provider_status["books"]
    assert "OK" in result.provider_status["youtube"]


def test_research_engine_complete_failure_engages_fallback():
    mock_web = MagicMock()
    mock_web.search.return_value = []
    mock_books = MagicMock()
    mock_books.search.return_value = []
    mock_youtube = MagicMock()
    mock_youtube.search.return_value = []

    engine = ResearchEngine(
        web_researcher=mock_web,
        book_researcher=mock_books,
        youtube_researcher=mock_youtube,
    )
    result = engine.discover("HTTP Requests and Responses")

    # When all 3 return 0 items, fallback is engaged
    assert result.is_fallback is True
    assert len(result.all_sources) > 0
    assert result.all_sources[0].metadata.get("is_offline_fallback") is True
