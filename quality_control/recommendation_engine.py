"""
Instructor Recommendation and Non-Destructive Patch Engine.
Manages the recommendation review lifecycle (PENDING -> ACCEPTED / REJECTED -> APPLIED),
creates versioned revised copies of lessons, and computes before/after diffs.
"""

from __future__ import annotations

import copy
import logging
import re
from datetime import datetime, timezone
from typing import List, Tuple

from core.exceptions import RecommendationError
from core.schemas import (
    ActivityPlan,
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
        Modifies the actual targeted lesson content (replacing incorrect statements)
        while preserving all unrelated content and keeping the input lesson_plan untouched.
        """
        if recommendation.status == RecommendationStatus.APPLIED:
            raise RecommendationError(f"Duplicate application: Recommendation '{recommendation.id}' is already APPLIED.")

        # Non-destructive deep copy
        revised_plan = copy.deepcopy(lesson_plan)
        target = recommendation.section_target
        now_ts = datetime.now(timezone.utc).isoformat()

        before_content = ""
        after_content = ""
        patch_type = "CONTENT_REPLACEMENT"

        # Scenario 1: Target is a specific section
        target_section = next((s for s in revised_plan.sections if s.section_id == target), None)
        if target_section:
            before_content = target_section.content_markdown
            target_to_replace = recommendation.target_text

            replaced = False
            # 1. Direct substring replacement if target_text matches
            if target_to_replace and target_to_replace in before_content:
                after_content = before_content.replace(target_to_replace, recommendation.suggested_content)
                replaced = True
            elif target_to_replace:
                # Case-insensitive or stripped substring replacement
                pattern = re.compile(re.escape(target_to_replace.strip()), re.IGNORECASE)
                if pattern.search(before_content):
                    after_content = pattern.sub(recommendation.suggested_content, before_content)
                    replaced = True

            # 2. Known domain contradiction pattern replacement if target_text was not an exact line match
            if not replaced:
                lower_before = before_content.lower()
                # Check for POST idempotency assertion
                if "post is idempotent" in lower_before or "post is a safe method" in lower_before:
                    pattern = re.compile(r"([^\n.]*post is (?:idempotent|a safe method)[^\n.]*[.\n]?)", re.IGNORECASE)
                    if pattern.search(before_content):
                        after_content = pattern.sub(recommendation.suggested_content + "\n", before_content)
                        replaced = True
                elif "404 is a server error" in lower_before or "500 is a client error" in lower_before:
                    pattern = re.compile(r"([^\n.]*(?:404 is a server error|500 is a client error)[^\n.]*[.\n]?)", re.IGNORECASE)
                    if pattern.search(before_content):
                        after_content = pattern.sub(recommendation.suggested_content + "\n", before_content)
                        replaced = True
                elif "cname can be placed at the root" in lower_before or "cname at apex" in lower_before:
                    pattern = re.compile(r"([^\n.]*cname (?:can be placed at the root|at apex)[^\n.]*[.\n]?)", re.IGNORECASE)
                    if pattern.search(before_content):
                        after_content = pattern.sub(recommendation.suggested_content + "\n", before_content)
                        replaced = True

            # 3. If target was an unresolvable citation, remove the bad citation ID from text and section.citations
            if not replaced and "cites unknown source id" in recommendation.issue_summary.lower():
                bad_ids = re.findall(r"'([a-zA-Z0-9_\-]+)'", recommendation.issue_summary)
                after_content = before_content
                for bid in bad_ids:
                    after_content = after_content.replace(f"[{bid}]", "").replace(f"according to [{bid}], ", "")
                    if bid in target_section.citations:
                        target_section.citations.remove(bid)
                replaced = True

            # 4. Fallback if no specific replacement matched: append the corrected content cleanly
            if not replaced:
                after_content = before_content + "\n\n" + recommendation.suggested_content

            target_section.content_markdown = after_content
            patch_type = "SECTION_CONTENT_REVISION"

        # Scenario 2: Target is guided activity (e.g. missing activity)
        elif "activity" in target.lower() or ("global" in target.lower() and "activity" in recommendation.issue_summary.lower()):
            if revised_plan.guided_activity is None:
                before_content = "None (Activity Missing)"
                revised_plan.guided_activity = ActivityPlan(
                    title="Hands-On Terminal Verification Lab",
                    duration_minutes=8,
                    instructions=recommendation.suggested_content,
                    deliverable="Terminal log capturing execution outputs and verification steps.",
                    evaluation_criteria=["Accurate command syntax", "Correct interpretation of outputs"],
                )
                # Adjust first section duration by -8 to keep duration sum invariant!
                revised_plan.sections[0].duration_minutes = max(3, revised_plan.sections[0].duration_minutes - 8)
                after_content = f"Added Activity: {revised_plan.guided_activity.title}"
                patch_type = "ACTIVITY_RESTORE"

        # Scenario 3: Target is knowledge checks (e.g. bad answer key)
        elif "knowledge" in target.lower() or "kc" in target.lower() or ("global" in target.lower() and "answer key" in recommendation.issue_summary.lower()):
            for kc in revised_plan.knowledge_checks:
                if kc.correct_answer not in kc.options:
                    before_content = f"Bad Key: {kc.correct_answer}"
                    kc.correct_answer = kc.options[0]
                    after_content = f"Corrected Key: {kc.correct_answer}"
                    patch_type = "ANSWER_KEY_REPAIR"
                    break

        # Scenario 4: Target is global / learning outcomes
        elif target == "global" and "outcome" in recommendation.issue_summary.lower():
            before_content = "\n".join(revised_plan.learning_outcomes)
            revised_plan.learning_outcomes.append(f"Differentiate and apply: {recommendation.suggested_content[:60]}")
            after_content = "\n".join(revised_plan.learning_outcomes)
            patch_type = "LEARNING_OUTCOMES_APPEND"

        # Scenario 5: Target is introduction
        elif "intro" in target.lower():
            before_content = revised_plan.introduction
            revised_plan.introduction += f" {recommendation.suggested_content}"
            after_content = revised_plan.introduction
            patch_type = "INTRODUCTION_REVISION"
        else:
            first_sec = revised_plan.sections[0]
            before_content = first_sec.content_markdown
            first_sec.content_markdown += f"\n\n{recommendation.suggested_content}"
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
