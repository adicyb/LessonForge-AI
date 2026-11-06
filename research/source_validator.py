"""
Source validation, URL normalization, deduplication, and transparent credibility scoring.
Separates domain authority, topic relevance, and content retrieval provenance.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from core.schemas import ProvenanceStatus, ResearchSource, SourceType

# Known tracking query parameters to strip during normalization
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "ref_src",
    "fbclid",
    "gclid",
    "trk",
    "si",
    "feature",
}

# Domain authority tiers for transparent credibility scoring
AUTHORITY_TIERS: list[tuple[list[str], float]] = [
    # Tier 1: Formal RFCs, Internet Standards, Specification Bodies (Score: 1.0)
    (["ietf.org", "rfc-editor.org", "w3.org", "iso.org", "iana.org"], 1.0),
    # Tier 2: Authoritative Tech Documentation & Educational Gateways (Score: 0.95)
    (
        [
            "developer.mozilla.org",
            "docs.python.org",
            "docs.oracle.com",
            "en.cppreference.com",
            "learn.microsoft.com",
            "cloud.google.com",
            "aws.amazon.com",
            "cloudflare.com",
        ],
        0.95,
    ),
    # Tier 3: Universities and Academic Institutions (Score: 0.92)
    ([".edu", ".ac.uk", "mit.edu", "stanford.edu", "berkeley.edu", "cmu.edu", "ox.ac.uk"], 0.92),
    # Tier 4: Major Educational Textbook Publishers & Catalogs (Score: 0.90)
    (
        [
            "openlibrary.org",
            "books.google.com",
            "oreilly.com",
            "pearson.com",
            "mitpress.mit.edu",
            "routledge.com",
            "springer.com",
            "wiley.com",
        ],
        0.90,
    ),
    # Tier 5: Major Verified Encyclopedias & Community Standards (Score: 0.82)
    (["wikipedia.org", "archive.org", "geeksforgeeks.org", "digitalocean.com"], 0.82),
    # Tier 6: High-Quality Educational Media & Video Channels (Score: 0.80)
    (["youtube.com", "youtu.be", "vimeo.com"], 0.80),
]


def normalize_url(raw_url: str) -> str:
    """
    Normalize URL by lowercasing scheme/host, stripping default ports,
    removing tracking query parameters, and normalizing trailing slashes.
    """
    if not raw_url or not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("URL must be a non-empty string.")

    cleaned = raw_url.strip()
    parsed = urlparse(cleaned)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    # Normalize path (remove redundant trailing slash unless it's root '/')
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Strip tracking parameters from query string while preserving genuine query params
    filtered_query = []
    if parsed.query:
        for key, val in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() not in TRACKING_PARAMS:
                filtered_query.append((key, val))

    query_str = urlencode(filtered_query)

    # Reconstruct normalized URL (excluding fragment hashes for identity matching)
    return urlunparse((scheme, netloc, path, parsed.params, query_str, ""))


def calculate_credibility_score(
    url: str,
    source_type: SourceType,
    publisher_or_author: str | None = None,
) -> float:
    """
    Calculate transparent credibility score (0.0 to 1.0) based on domain authority,
    publisher reputation, and source category. Does not require hardcoded domain allowlists.
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
    except Exception:
        return 0.50

    # 1. Match against known authority tiers
    for domain_patterns, score in AUTHORITY_TIERS:
        for pattern in domain_patterns:
            if pattern.startswith(".") and domain.endswith(pattern):
                return score
            elif pattern in domain:
                return score

    # 2. Check source type defaults if no specific domain matched
    if source_type == SourceType.BOOK:
        # Published books have editorial gatekeeping
        return 0.85
    elif source_type == SourceType.WEB:
        # Standard web source without negative indicators
        return 0.65
    elif source_type == SourceType.YOUTUBE:
        return 0.75

    return 0.50


def calculate_relevance_score(query: str, title: str, snippet: str) -> float:
    """
    Calculate topical relevance score (0.0 to 1.0) based on keyword matching
    between user query terms and the source title & snippet.
    """
    if not query:
        return 0.5

    # Extract alphanumeric query keywords (length >= 3, excluding stop words)
    stop_words = {"the", "and", "for", "with", "that", "this", "from", "into", "between"}
    query_tokens = [
        w.lower()
        for w in re.findall(r"\b[a-zA-Z0-9_-]+\b", query)
        if len(w) >= 3 and w.lower() not in stop_words
    ]

    if not query_tokens:
        return 0.5

    title_lower = title.lower()
    snippet_lower = snippet.lower()

    matches = 0
    title_matches = 0

    for token in query_tokens:
        if token in title_lower:
            title_matches += 1
            matches += 1
        elif token in snippet_lower:
            matches += 1

    # Weighted: Title matches count more heavily than snippet matches
    raw_score = (matches + (title_matches * 0.5)) / (len(query_tokens) * 1.5)
    return round(min(1.0, max(0.1, raw_score)), 2)


def deduplicate_sources(sources: list[ResearchSource]) -> list[ResearchSource]:
    """
    Deduplicate a list of ResearchSource objects by normalized URL.
    Preserves highest credibility score and best provenance status.
    """
    seen_urls: dict[str, ResearchSource] = {}

    for source in sources:
        try:
            norm_url = normalize_url(source.url)
        except Exception:
            norm_url = source.url.strip().lower()

        if norm_url not in seen_urls:
            seen_urls[norm_url] = source
        else:
            existing = seen_urls[norm_url]
            # If new source has higher credibility or higher provenance, update
            provenance_order = {
                ProvenanceStatus.DISCOVERED: 1,
                ProvenanceStatus.RETRIEVED: 2,
                ProvenanceStatus.VERIFIED: 3,
            }
            if provenance_order.get(source.provenance, 1) > provenance_order.get(existing.provenance, 1):
                seen_urls[norm_url] = source
            elif source.credibility_score > existing.credibility_score:
                seen_urls[norm_url] = source

    return list(seen_urls.values())
