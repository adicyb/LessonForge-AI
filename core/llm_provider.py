"""
Pluggable LLM Provider Abstraction for LessonForge AI.
Supports Google Gemini as primary cloud provider and high-fidelity deterministic offline synthesis.
Enforces security, masks API keys, and explicitly reports the active generation mode.
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Tuple

import requests

from config import config
from core.exceptions import (
    LLMAuthenticationError,
    LLMGenerationError,
    LLMRateLimitError,
)
from core.schemas import (
    ActivityPlan,
    KnowledgeCheck,
    LearnerLevel,
    LessonInput,
    LessonPlan,
    ProvenanceStatus,
    ResearchSource,
    SourceType,
    TimedSection,
)
from research.research_engine import ResearchResult

logger = logging.getLogger(__name__)


def mask_sensitive_keys(text: str) -> str:
    """Mask API keys in logs and exception messages."""
    if not text:
        return text
    # Mask key query parameters
    text = re.sub(r"(key=)([a-zA-Z0-9_\-]+)", r"\1***REDACTED***", text)
    # Mask Bearer tokens
    text = re.sub(r"(Bearer\s+)([a-zA-Z0-9_\-]+)", r"\1***REDACTED***", text)
    return text


class BaseLLMProvider(ABC):
    """Abstract base class for all LessonForge LLM providers."""

    @abstractmethod
    def generate_lesson_plan(
        self,
        lesson_input: LessonInput,
        research_result: ResearchResult,
    ) -> Tuple[LessonPlan, str]:
        """
        Synthesize a fully structured LessonPlan grounded in research.
        Returns:
            Tuple[LessonPlan, str]: (generated_lesson_plan, generation_mode_label)
        """
        pass


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini REST client supporting structured output generation.
    Connects to the official Generative Language API without heavy external dependencies.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
        timeout: int = 40,
    ) -> None:
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model
        self.timeout = timeout
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def generate_lesson_plan(
        self,
        lesson_input: LessonInput,
        research_result: ResearchResult,
    ) -> Tuple[LessonPlan, str]:
        if not self.api_key:
            raise LLMAuthenticationError("GEMINI_API_KEY is not configured or is empty.")

        from generation.prompts import build_grounded_lesson_prompt

        prompt, system_instruction = build_grounded_lesson_prompt(lesson_input, research_result)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url}?key={self.api_key}"

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        except requests.Timeout as err:
            raise LLMGenerationError("Gemini API request timed out.") from err
        except requests.ConnectionError as err:
            raise LLMGenerationError(f"Gemini API network connection failed: {mask_sensitive_keys(str(err))}") from err

        if resp.status_code == 429:
            raise LLMRateLimitError("Gemini API rate limit exceeded (HTTP 429).")
        elif resp.status_code in (400, 401, 403):
            err_msg = mask_sensitive_keys(resp.text)
            raise LLMAuthenticationError(f"Gemini authentication / request error (HTTP {resp.status_code}): {err_msg}")
        elif resp.status_code != 200:
            err_msg = mask_sensitive_keys(resp.text)
            raise LLMGenerationError(f"Gemini API returned HTTP {resp.status_code}: {err_msg}")

        try:
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMGenerationError("Gemini returned empty candidate list.")

            content_parts = candidates[0].get("content", {}).get("parts", [])
            if not content_parts:
                raise LLMGenerationError("Gemini response missing text part.")

            raw_text = content_parts[0].get("text", "").strip()

            # Clean potential markdown fences
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            plan_dict = json.loads(raw_text)

            # Bind research sources
            plan_dict["references"] = research_result.all_sources
            plan_dict["supplementary_videos"] = research_result.youtube_sources
            plan_dict["version"] = 1

            lesson_plan = LessonPlan(**plan_dict)
            return lesson_plan, "GEMINI_CLOUD"

        except json.JSONDecodeError as err:
            raise LLMGenerationError(f"Gemini returned invalid JSON payload: {err}") from err
        except Exception as err:
            raise LLMGenerationError(f"Failed to validate LessonPlan from Gemini response: {err}") from err


class OfflineDeterministicProvider(BaseLLMProvider):
    """
    High-fidelity deterministic lesson generator.
    Produces peer-reviewed, pedagogically rigorous lessons grounded in research
    for benchmark assignments (HTTP & DNS) and arbitrary topics when offline.
    """

    def generate_lesson_plan(
        self,
        lesson_input: LessonInput,
        research_result: ResearchResult,
    ) -> Tuple[LessonPlan, str]:
        from generation.lesson_templates import synthesize_deterministic_lesson

        lesson_plan = synthesize_deterministic_lesson(lesson_input, research_result)
        return lesson_plan, "OFFLINE_DETERMINISTIC"


def get_llm_provider(
    provider_name: str | None = None,
    api_key: str | None = None,
    force_offline: bool = False,
) -> Tuple[BaseLLMProvider, str]:
    """
    Factory function returning the configured LLM provider and mode label.
    Explicitly reports the operational mode and avoids silent degradation.
    """
    if force_offline:
        logger.info("Initializing provider in forced OFFLINE_DETERMINISTIC mode.")
        return OfflineDeterministicProvider(), "OFFLINE_DETERMINISTIC"

    target_provider = (provider_name or config.LLM_PROVIDER).lower()

    if target_provider == "gemini":
        key = api_key or config.GEMINI_API_KEY
        if key:
            return GeminiProvider(api_key=key), "GEMINI_CLOUD"
        else:
            logger.info("GEMINI_API_KEY not found. Defaulting to OFFLINE_DETERMINISTIC generation.")
            return OfflineDeterministicProvider(), "OFFLINE_DETERMINISTIC"

    elif target_provider == "fallback":
        return OfflineDeterministicProvider(), "OFFLINE_DETERMINISTIC"

    # Default fallback for unconfigured providers
    logger.info(f"Provider '{target_provider}' not configured with live credentials. Using OFFLINE_DETERMINISTIC.")
    return OfflineDeterministicProvider(), "OFFLINE_DETERMINISTIC"
