"""
Grounded Lesson Generation Engine for LessonForge AI.
Coordinates multi-modal research inputs, LLM synthesis, duration validation,
and evidence-traceability enforcement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Tuple

from core.exceptions import DurationExceededError, LLMGenerationError, ValidationError
from core.llm_provider import (
    BaseLLMProvider,
    OfflineDeterministicProvider,
    get_llm_provider,
)
from core.schemas import LessonInput, LessonPlan
from research.research_engine import ResearchEngine, ResearchResult

logger = logging.getLogger(__name__)


@dataclass
class LessonGenerationResult:
    """Consolidated generation output package."""

    lesson_plan: LessonPlan
    generation_mode: str  # "GEMINI_CLOUD" or "OFFLINE_DETERMINISTIC"
    research_result: ResearchResult
    is_fallback_generation: bool = False
    status_message: str = ""


class LessonGenerator:
    """Orchestrates research-grounded pedagogical synthesis."""

    def __init__(
        self,
        llm_provider: BaseLLMProvider | None = None,
        research_engine: ResearchEngine | None = None,
    ) -> None:
        self.provider = llm_provider
        self.research = research_engine or ResearchEngine()

    def generate(
        self,
        lesson_input: LessonInput,
        research_result: ResearchResult | None = None,
        force_offline: bool = False,
    ) -> LessonGenerationResult:
        """
        Generate a classroom-ready 45-minute lesson plan.
        1. Verifies input constraints (duration <= 45).
        2. Retrieves research if not supplied.
        3. Invokes LLM provider with fallback handling.
        4. Validates Pydantic schema and duration budgeting.
        """
        # 1. Enforce duration ceiling
        if lesson_input.target_duration_minutes > 45:
            raise DurationExceededError(lesson_input.target_duration_minutes, max_allowed=45)

        # 2. Discover research evidence if not provided
        if research_result is None:
            research_result = self.research.discover(
                topic=lesson_input.title,
                learning_objective=lesson_input.learning_objective,
                force_offline=force_offline,
            )

        # 3. Determine active provider
        if self.provider is not None and not force_offline:
            active_provider = self.provider
            active_mode = "CUSTOM_PROVIDER"
        else:
            active_provider, active_mode = get_llm_provider(force_offline=force_offline)

        # 4. Attempt generation with resilient fallback
        try:
            lesson_plan, generation_mode = active_provider.generate_lesson_plan(
                lesson_input, research_result
            )
            status_msg = f"Lesson successfully synthesized via {generation_mode}."
            is_fallback = (generation_mode == "OFFLINE_DETERMINISTIC")

        except Exception as err:
            logger.warning(
                f"Primary provider generation encountered an error: {err}. "
                "Engaging OFFLINE_DETERMINISTIC synthesis."
            )
            fallback_provider = OfflineDeterministicProvider()
            lesson_plan, generation_mode = fallback_provider.generate_lesson_plan(
                lesson_input, research_result
            )
            status_msg = f"Synthesized via OFFLINE_DETERMINISTIC fallback after provider error ({err})."
            is_fallback = True

        # 5. Verify duration budget invariants
        sections_sum = sum(s.duration_minutes for s in lesson_plan.sections)
        activity_time = lesson_plan.guided_activity.duration_minutes if lesson_plan.guided_activity else 0
        total_sum = sections_sum + activity_time

        if total_sum != lesson_plan.total_duration_minutes:
            raise ValidationError(
                f"Generated lesson sections ({sections_sum}m) and activity ({activity_time}m) "
                f"total {total_sum}m, which does not match declared total_duration_minutes ({lesson_plan.total_duration_minutes}m)."
            )

        return LessonGenerationResult(
            lesson_plan=lesson_plan,
            generation_mode=generation_mode,
            research_result=research_result,
            is_fallback_generation=is_fallback,
            status_message=status_msg,
        )
