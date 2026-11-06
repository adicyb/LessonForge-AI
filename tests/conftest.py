"""
Pytest configuration and shared test fixtures for LessonForge AI.
"""

from __future__ import annotations

import pytest

from core.schemas import (
    ActivityPlan,
    CriterionEvaluation,
    KnowledgeCheck,
    LearnerLevel,
    LessonInput,
    LessonPlan,
    ProvenanceStatus,
    QCFinding,
    QCLayer,
    QCReport,
    QCSeverity,
    QCStatus,
    Recommendation,
    RecommendationStatus,
    ResearchSource,
    SourceType,
    TimedSection,
)


@pytest.fixture
def sample_web_source() -> ResearchSource:
    return ResearchSource(
        id="src_mdn_1",
        source_type=SourceType.WEB,
        title="HTTP request methods - MDN Web Docs",
        url="https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods",
        authors_or_channel="Mozilla Contributors",
        snippet_or_summary="HTTP defines a set of request methods to indicate the desired action to be performed for a given resource.",
        provenance=ProvenanceStatus.VERIFIED,
        credibility_score=0.98,
        retrieval_date="2026-11-06",
        metadata={"domain": "developer.mozilla.org"},
    )


@pytest.fixture
def sample_youtube_source() -> ResearchSource:
    return ResearchSource(
        id="src_yt_1",
        source_type=SourceType.YOUTUBE,
        title="HTTP Crash Course & Status Codes Explained",
        url="https://www.youtube.com/watch?v=iYM2zFP3Zn0",
        authors_or_channel="Traversy Media",
        snippet_or_summary="Comprehensive video explanation of HTTP request methods, headers, and status code categories.",
        provenance=ProvenanceStatus.VERIFIED,
        credibility_score=0.85,
        retrieval_date="2026-11-06",
        metadata={"duration_seconds": 960, "video_id": "iYM2zFP3Zn0"},
    )


@pytest.fixture
def valid_lesson_plan_data(sample_web_source, sample_youtube_source) -> dict:
    """Dictionary representing a fully valid 45-minute lesson plan."""
    return {
        "lesson_id": "lesson_http_001",
        "title": "HTTP Requests and Responses",
        "learning_objective": "Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        "learner_level": LearnerLevel.INTERMEDIATE,
        "prerequisites": ["Basic web browser usage", "Basic client-server concept"],
        "total_duration_minutes": 45,
        "introduction": "The Hypertext Transfer Protocol (HTTP) serves as the foundational communication layer of the World Wide Web.",
        "learning_outcomes": [
            "Contrast GET and POST methods in terms of payload, caching, and idempotency.",
            "Categorize HTTP response status codes into 2xx Success, 4xx Client Error, and 5xx Server Error.",
        ],
        "sections": [
            TimedSection(
                section_id="sec_1_proto_basics",
                title="Foundations of HTTP Client-Server Architecture",
                duration_minutes=10,
                cognitive_focus="Conceptual Foundation",
                content_markdown="HTTP is a stateless, application-layer request-response protocol running over TCP or QUIC.",
                citations=["src_mdn_1"],
            ),
            TimedSection(
                section_id="sec_2_methods",
                title="Deep Dive: GET vs POST Semantics",
                duration_minutes=15,
                cognitive_focus="Worked Example & Analysis",
                content_markdown="GET retrieves resources and must be idempotent. POST submits data to modify server state.",
                citations=["src_mdn_1"],
            ),
            TimedSection(
                section_id="sec_3_status_codes",
                title="Deconstructing HTTP Status Code Families (2xx, 4xx, 5xx)",
                duration_minutes=10,
                cognitive_focus="Classification & Diagnosis",
                content_markdown="2xx represents successful transactions; 4xx denotes client fault; 5xx signifies server failure.",
                citations=["src_mdn_1"],
            ),
        ],
        "guided_activity": ActivityPlan(
            title="Hands-on HTTP cURL Lab",
            duration_minutes=10,
            instructions="Execute cURL commands against httpbin.org to observe GET query strings vs POST JSON bodies.",
            deliverable="Terminal log showing response headers and status codes 200, 404, and 500.",
            evaluation_criteria=["Correct cURL syntax", "Accurate interpretation of status code"],
        ),
        "knowledge_checks": [
            KnowledgeCheck(
                id="kc_1",
                question="Why is an HTTP GET request considered idempotent?",
                options=[
                    "Because repeating the request multiple times produces the same intended server state without side effects.",
                    "Because it carries data only in the message body.",
                    "Because it can never be cached by intermediaries.",
                    "Because it requires an SSL certificate.",
                ],
                correct_answer="Because repeating the request multiple times produces the same intended server state without side effects.",
                explanation="RFC 9110 defines idempotent methods as those where the intended effect on the server of multiple identical requests is the same as for a single request.",
            )
        ],
        "summary": "We have explored HTTP client-server communication, detailed GET and POST semantics, and classified response status codes.",
        "supplementary_videos": [sample_youtube_source],
        "references": [sample_web_source],
        "version": 1,
    }


@pytest.fixture
def sample_lesson_plan(valid_lesson_plan_data) -> LessonPlan:
    return LessonPlan(**valid_lesson_plan_data)
