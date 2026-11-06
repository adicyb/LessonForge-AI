"""
Comprehensive unit and integration tests for Phase 3: Grounded Lesson Generation Engine.
Tests HTTP & DNS benchmark generation, duration budgeting, citation validity,
Gemini provider API mocking, rate-limit fallback, and malformed JSON resilience.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest
import requests

from core.exceptions import DurationExceededError, LLMAuthenticationError, LLMGenerationError
from core.llm_provider import GeminiProvider, mask_sensitive_keys
from core.schemas import LearnerLevel, LessonInput, LessonPlan
from generation.lesson_generator import LessonGenerator
from generation.lesson_templates import allocate_time_budget
from research.research_engine import ResearchEngine


# ---------------------------------------------------------------------------
# 1. Benchmark 1: HTTP Requests and Responses
# ---------------------------------------------------------------------------
def test_generate_http_benchmark_lesson():
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        learner_level=LearnerLevel.INTERMEDIATE,
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    result = generator.generate(inp, force_offline=True)

    plan = result.lesson_plan
    assert result.generation_mode == "OFFLINE_DETERMINISTIC"
    assert plan.total_duration_minutes == 45
    assert plan.total_duration_minutes <= 45

    # Duration budgeting invariant
    sections_sum = sum(s.duration_minutes for s in plan.sections)
    activity_time = plan.guided_activity.duration_minutes
    assert sections_sum + activity_time == plan.total_duration_minutes

    # Curriculum coverage
    content_all = " ".join(s.content_markdown for s in plan.sections)
    assert "GET" in content_all
    assert "POST" in content_all
    assert "idempotent" in content_all
    assert "2xx" in content_all or "200" in content_all
    assert "4xx" in content_all or "404" in content_all
    assert "5xx" in content_all or "500" in content_all

    # Learning outcomes
    assert len(plan.learning_outcomes) >= 2

    # Guided activity
    assert plan.guided_activity is not None
    assert "cURL" in plan.guided_activity.title or "cURL" in plan.guided_activity.instructions
    assert len(plan.guided_activity.evaluation_criteria) >= 2

    # Knowledge checks & answer keys
    assert len(plan.knowledge_checks) >= 3
    for kc in plan.knowledge_checks:
        assert kc.correct_answer in kc.options
        assert len(kc.explanation) > 10


# ---------------------------------------------------------------------------
# 2. Benchmark 2: DNS Resolution and DNS Record Types
# ---------------------------------------------------------------------------
def test_generate_dns_benchmark_lesson():
    inp = LessonInput(
        title="DNS Resolution and DNS Record Types",
        learning_objective="Explain how recursive DNS resolution works and distinguish A, AAAA, CNAME, and MX records.",
        learner_level=LearnerLevel.INTERMEDIATE,
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    result = generator.generate(inp, force_offline=True)

    plan = result.lesson_plan
    assert result.generation_mode == "OFFLINE_DETERMINISTIC"
    assert plan.total_duration_minutes == 45

    # Duration budgeting invariant
    sections_sum = sum(s.duration_minutes for s in plan.sections)
    activity_time = plan.guided_activity.duration_minutes
    assert sections_sum + activity_time == plan.total_duration_minutes

    # Curriculum coverage
    content_all = " ".join(s.content_markdown for s in plan.sections)
    assert "Root" in content_all
    assert "TLD" in content_all
    assert "Authoritative" in content_all
    assert "A Record" in content_all
    assert "AAAA Record" in content_all
    assert "CNAME" in content_all
    assert "MX" in content_all

    # Knowledge checks & answer keys
    assert len(plan.knowledge_checks) >= 3
    for kc in plan.knowledge_checks:
        assert kc.correct_answer in kc.options
        assert len(kc.explanation) > 10


# ---------------------------------------------------------------------------
# 3. Duration Planning & Allocation Mechanics
# ---------------------------------------------------------------------------
def test_allocate_time_budget_invariants():
    # 45 minutes
    b45 = allocate_time_budget(45)
    assert b45["sec1"] + b45["sec2"] + b45["sec3"] + b45["activity"] == 45
    assert b45["total"] == 45

    # 30 minutes
    b30 = allocate_time_budget(30)
    assert b30["sec1"] + b30["sec2"] + b30["sec3"] + b30["activity"] == 30
    assert b30["total"] == 30

    # > 45 minutes capped at 45
    b60 = allocate_time_budget(60)
    assert b60["total"] == 45


# ---------------------------------------------------------------------------
# 4. Citation and Evidence Traceability
# ---------------------------------------------------------------------------
def test_citation_traceability():
    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )
    generator = LessonGenerator()
    result = generator.generate(inp, force_offline=True)

    valid_source_ids = {s.id for s in result.lesson_plan.references}

    for section in result.lesson_plan.sections:
        for citation_id in section.citations:
            assert citation_id in valid_source_ids, f"Citation '{citation_id}' in section '{section.title}' not found in references."


# ---------------------------------------------------------------------------
# 5. Gemini Provider Mocking (Success Path)
# ---------------------------------------------------------------------------
@patch("requests.post")
def test_gemini_provider_success_mocked(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "lesson_id": "lesson_gemini_test",
                                "title": "HTTP Protocol Guide",
                                "learning_objective": "Understand HTTP status categories.",
                                "learner_level": "BEGINNER",
                                "prerequisites": ["Web basics"],
                                "total_duration_minutes": 45,
                                "introduction": "An introduction to HTTP.",
                                "learning_outcomes": ["Understand status codes."],
                                "sections": [
                                    {
                                        "section_id": "sec_1",
                                        "title": "HTTP Intro",
                                        "duration_minutes": 35,
                                        "cognitive_focus": "Foundation",
                                        "content_markdown": "HTTP overview content.",
                                        "citations": ["src_1"],
                                    }
                                ],
                                "guided_activity": {
                                    "title": "cURL Lab",
                                    "duration_minutes": 10,
                                    "instructions": "Execute curl.",
                                    "deliverable": "Terminal log.",
                                    "evaluation_criteria": ["Correct execution"],
                                },
                                "knowledge_checks": [
                                    {
                                        "id": "kc_1",
                                        "question": "What is HTTP?",
                                        "options": ["Protocol", "Browser"],
                                        "correct_answer": "Protocol",
                                        "explanation": "HTTP is an application layer protocol.",
                                    }
                                ],
                                "summary": "Lesson summary.",
                            })
                        }
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    provider = GeminiProvider(api_key="test_dummy_key_12345")
    inp = LessonInput(
        title="HTTP Protocol Guide",
        learning_objective="Understand HTTP status categories with sufficient length.",
        target_duration_minutes=45,
    )
    research_res = ResearchEngine().discover("HTTP Protocol Guide", force_offline=True)

    plan, mode = provider.generate_lesson_plan(inp, research_res)
    assert mode == "GEMINI_CLOUD"
    assert plan.total_duration_minutes == 45
    assert len(plan.references) > 0


# ---------------------------------------------------------------------------
# 6. API Error Resilience & Fallback Switching
# ---------------------------------------------------------------------------
@patch("requests.post")
def test_generator_gracefully_falls_back_on_gemini_rate_limit(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Resource has been exhausted (e.g. check quota)."
    mock_post.return_value = mock_resp

    provider = GeminiProvider(api_key="test_dummy_key_12345")
    generator = LessonGenerator(llm_provider=provider)

    inp = LessonInput(
        title="HTTP Requests and Responses",
        learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
        target_duration_minutes=45,
    )

    # Should catch 429 and transparently fall back to OFFLINE_DETERMINISTIC
    result = generator.generate(inp, force_offline=True)
    assert result.generation_mode == "OFFLINE_DETERMINISTIC"
    assert result.is_fallback_generation is True
    assert "OFFLINE_DETERMINISTIC" in result.status_message


@patch("requests.post")
def test_generator_gracefully_falls_back_on_malformed_json(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "{malformed_not_json: true"}]
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    provider = GeminiProvider(api_key="test_dummy_key_12345")
    generator = LessonGenerator(llm_provider=provider)

    inp = LessonInput(
        title="DNS Resolution and DNS Record Types",
        learning_objective="Explain how recursive DNS resolution works and distinguish A, AAAA, CNAME, and MX records.",
        target_duration_minutes=45,
    )

    result = generator.generate(inp, force_offline=True)
    assert result.generation_mode == "OFFLINE_DETERMINISTIC"
    assert result.is_fallback_generation is True


# ---------------------------------------------------------------------------
# 7. Sensitive Key Masking Verification
# ---------------------------------------------------------------------------
def test_mask_sensitive_keys():
    raw_err = "Error calling https://api.example.com?key=AIzaSyD_SECRET_KEY_12345&other=1"
    masked = mask_sensitive_keys(raw_err)
    assert "AIzaSyD_SECRET_KEY_12345" not in masked
    assert "key=***REDACTED***" in masked

    bearer_err = "Authorization: Bearer sk-ant-api03-SECRET_KEY_abc123"
    masked_bearer = mask_sensitive_keys(bearer_err)
    assert "sk-ant-api03-SECRET_KEY_abc123" not in masked_bearer
    assert "Bearer ***REDACTED***" in masked_bearer
