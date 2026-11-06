"""
Instructor Recommendation and Non-Destructive Patch Engine.
Manages the recommendation review lifecycle (PENDING -> ACCEPTED / REJECTED -> APPLIED),
creates versioned revised copies of lessons, and computes before/after diffs.
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime, timezone
from typing import List, Tuple

from core.exceptions import RecommendationError
from core.schemas import (
    LessonPlan,
    Recommendation,
    RecommendationStatus,
)
from quality_control.qc_schemas import DiffItem

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Manages instructor decisions and executes non-destructive lesson revisions."""

    @staticmethod
    def accept_recommendation(
        recommendation: Recommendation,
        instructor_notes: str | None = None,
    ) -> Recommendation:
        """Mark a recommendation as accepted for inclusion in the revised lesson draft."""
        if recommendation.status == RecommendationStatus.APPLIED:
            raise RecommendationError(f"Recommendation '{recommendation.id}' has already been applied.")
        recommendation.status = RecommendationStatus.ACCEPTED
        if instructor_notes:
            recommendation.instructor_notes = instructor_notes
        return recommendation

    @staticmethod
    def reject_recommendation(
        recommendation: Recommendation,
        rejection_reason: str | None = None,
    ) -> Recommendation:
        """Mark a recommendation as rejected by the instructor with an optional rationale."""
        if recommendation.status == RecommendationStatus.APPLIED:
            raise RecommendationError(f"Recommendation '{recommendation.id}' has already been applied.")
        recommendation.status = RecommendationStatus.REJECTED
        if rejection_reason:
            recommendation.instructor_notes = f"Rejected: {rejection_reason}"
        return recommendation

    @staticmethod
    def modify_recommendation(
        recommendation: Recommendation,
        modified_content: str,
    ) -> Recommendation:
        """Allow instructor to customize the suggested content before application."""
        if recommendation.status == RecommendationStatus.APPLIED:
            raise RecommendationError(f"Recommendation '{recommendation.id}' has already been applied.")
        recommendation.suggested_content = modified_content.strip()
        return recommendation

    @classmethod
    def apply_recommendation(
        cls,
        lesson_plan: LessonPlan,
        recommendation: Recommendation,
    ) -> Tuple[LessonPlan, DiffItem]:
        """
        Apply a single recommendation to a DEEP COPY of the lesson plan.
        Guarantees that the input lesson_plan instance is completely untouched.
        """
        if recommendation.status == RecommendationStatus.APPLIED:
            raise RecommendationError(f"Duplicate application: Recommendation '{recommendation.id}' is already APPLIED.")

        # Non-destructive deep copy
        revised_plan = copy.deepcopy(lesson_plan)
        target = recommendation.section_target
        now_ts = datetime.now(timezone.utc).isoformat()

        before_content = ""
        after_content = ""

        # Scenario 1: Target is a specific section
        target_section = next((s for s in revised_plan.sections if s.section_id == target), None)
        if target_section:
            before_content = target_section.content_markdown
            # Append or patch suggested content
            patch_note = f"\n\n> **[QC Revision - {recommendation.layer.value}]:** {recommendation.suggested_content}"
            target_section.content_markdown = before_content + patch_note
            after_content = target_section.content_markdown
            patch_type = "SECTION_REVISION"

        # Scenario 2: Target is global / learning outcomes
        elif target == "global" and "outcome" in recommendation.issue_summary.lower():
            before_content = "\n".join(revised_plan.learning_outcomes)
            revised_plan.learning_outcomes.append(f"Synthesize and apply best practices: {recommendation.suggested_content[:60]}")
            after_content = "\n".join(revised_plan.learning_outcomes)
            patch_type = "LEARNING_OUTCOMES_APPEND"

        # Scenario 3: Target is introduction or summary
        elif "intro" in target.lower():
            before_content = revised_plan.introduction
            revised_plan.introduction += f" {recommendation.suggested_content}"
            after_content = revised_plan.introduction
            patch_type = "INTRODUCTION_REVISION"
        else:
            # Fallback: patch onto first section
            first_sec = revised_plan.sections[0]
            before_content = first_sec.content_markdown
            first_sec.content_markdown += f"\n\n> **[QC Revision]:** {recommendation.suggested_content}"
            after_content = first_sec.content_markdown
            patch_type = "GENERAL_SECTION_REVISION"

        # Update metadata and version on revised copy
        revised_plan.version += 1
        revised_plan.updated_at = now_ts

        # Mark recommendation state
        recommendation.status = RecommendationStatus.APPLIED

        diff = DiffItem(
            recommendation_id=recommendation.id,
            target_section=target,
            patch_type=patch_type,
            before_content=before_content,
            after_content=after_content,
            timestamp=now_ts,
        )

        return revised_plan, diff

    @classmethod
    def apply_batch_recommendations(
        cls,
        lesson_plan: LessonPlan,
        recommendations: List[Recommendation],
    ) -> Tuple[LessonPlan, List[DiffItem]]:
        """Apply all accepted recommendations sequentially to a deep copy of the lesson plan."""
        current_plan = copy.deepcopy(lesson_plan)
        diffs: list[DiffItem] = []

        for rec in recommendations:
            if rec.status == RecommendationStatus.ACCEPTED:
                current_plan, diff = cls.apply_recommendation(current_plan, rec)
                diffs.append(diff)

        return current_plan, diffs
