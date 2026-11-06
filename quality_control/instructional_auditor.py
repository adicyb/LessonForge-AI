"""
Quality Control Layer 2: Instructional Quality Auditor.
Independently evaluates curriculum progression, objective alignment, active learning,
knowledge-check rigor, and cognitive load with strict isolation from QC Layer 1.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Tuple

from core.schemas import (
    CriterionEvaluation,
    LearnerLevel,
    LessonPlan,
    QCFinding,
    QCLayer,
    QCSeverity,
    QCStatus,
    Recommendation,
    RecommendationStatus,
)
from quality_control.qc_schemas import DetailedQCReport

logger = logging.getLogger(__name__)

# Bloom's revised taxonomy action verbs for measurable learning outcomes
BLOOM_ACTION_VERBS = {
    # Remember & Understand
    "explain", "describe", "identify", "recognize", "summarize", "classify", "outline",
    # Apply & Analyze
    "differentiate", "contrast", "compare", "apply", "execute", "construct", "analyze",
    "diagnose", "investigate", "demonstrate", "solve", "trace", "inspect", "implement",
    # Evaluate & Create
    "evaluate", "critique", "design", "formulate", "synthesize", "architect",
}


class InstructionalAuditor:
    """
    Independent Curriculum and Instructional Quality Auditor.
    Zero factual checking: Focuses purely on pedagogical efficacy, scaffolding,
    active learning engagement, and Bloom's taxonomy progression.
    """

    CRITERIA_WEIGHTS = {
        "Learning Objective & Outcomes Alignment": 0.25,
        "Pedagogical Progression & Scaffolding": 0.20,
        "Worked Examples & Practical Applications": 0.20,
        "Guided Activity & Lab Engagement": 0.20,
        "Assessment Rigor & Cognitive Pacing": 0.15,
    }

    def audit(
        self,
        lesson_plan: LessonPlan,
        evaluator_mode: str = "DETERMINISTIC_AUDITOR",
    ) -> DetailedQCReport:
        """
        Execute independent instructional quality audit.
        Input is strictly isolated to lesson content, objective, learner level, and duration.
        """
        report_id = f"qc_inst_{uuid.uuid4().hex[:8]}"
        all_findings: list[QCFinding] = []

        # 1. Audit Objective Alignment & Outcome Measurability
        obj_findings = self._audit_objectives_and_outcomes(lesson_plan)
        all_findings.extend(obj_findings)

        # 2. Audit Scaffolding & Conceptual Sequencing
        seq_findings = self._audit_sequencing_and_scaffolding(lesson_plan)
        all_findings.extend(seq_findings)

        # 3. Audit Worked Examples & Systems Context
        ex_findings = self._audit_examples_and_practice(lesson_plan)
        all_findings.extend(ex_findings)

        # 4. Audit Guided Activity & Active Learning
        act_findings = self._audit_guided_activity(lesson_plan)
        all_findings.extend(act_findings)

        # 5. Audit Knowledge Checks, Answer Keys & Pacing
        assess_findings = self._audit_assessments_and_pacing(lesson_plan)
        all_findings.extend(assess_findings)

        # 6. Compute weighted criterion scores
        criterion_scores, overall_score = self._compute_scores(all_findings)

        # 7. Determine audit status
        has_critical = any(f.severity == QCSeverity.CRITICAL for f in all_findings)
        if has_critical:
            status = QCStatus.FAILED if overall_score < 60 else QCStatus.NEEDS_REVISION
        elif overall_score >= 80.0:
            status = QCStatus.PASSED
        elif overall_score >= 60.0:
            status = QCStatus.NEEDS_REVISION
        else:
            status = QCStatus.FAILED

        # 8. Generate recommendations
        recommendations = self._generate_recommendations(all_findings)

        crit_count = sum(1 for f in all_findings if f.severity == QCSeverity.CRITICAL)
        maj_count = sum(1 for f in all_findings if f.severity == QCSeverity.MAJOR)
        summary = (
            f"QC Layer 2 Audit Complete. Overall Score: {overall_score:.1f}/100 ({status.value}). "
            f"Assessed pedagogical efficacy for '{lesson_plan.title}' targeted at {lesson_plan.learner_level.value} level. "
            f"Identified {crit_count} Critical, {maj_count} Major, and "
            f"{len(all_findings) - crit_count - maj_count} Minor pedagogical recommendations."
        )

        return DetailedQCReport.from_report_components(
            report_id=report_id,
            lesson_id=lesson_plan.lesson_id,
            version_audited=lesson_plan.version,
            layer=QCLayer.INSTRUCTIONAL_QUALITY,
            overall_score=overall_score,
            status=status,
            criterion_scores=criterion_scores,
            findings=all_findings,
            summary=summary,
            evaluator_mode=evaluator_mode,
            recommendations=recommendations,
        )

    def _audit_objectives_and_outcomes(self, lesson_plan: LessonPlan) -> List[QCFinding]:
        findings: list[QCFinding] = []
        obj_lower = lesson_plan.learning_objective.lower()

        # Check outcomes count
        if not lesson_plan.learning_outcomes:
            findings.append(
                QCFinding(
                    id=f"find_inst_no_outcomes_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Learning Objective & Outcomes Alignment",
                    section_target="global",
                    description="Lesson lacks explicit, measurable learning outcomes.",
                    suggested_fix="Define at least 2 measurable learning outcomes utilizing Bloom's taxonomy action verbs.",
                )
            )
        else:
            # Check Bloom's action verb measurability
            for idx, outcome in enumerate(lesson_plan.learning_outcomes):
                first_word = outcome.strip().split()[0].lower().rstrip("s")
                if first_word not in BLOOM_ACTION_VERBS:
                    findings.append(
                        QCFinding(
                            id=f"find_inst_outcome_verb_{idx}",
                            layer=QCLayer.INSTRUCTIONAL_QUALITY,
                            severity=QCSeverity.MINOR,
                            criterion="Learning Objective & Outcomes Alignment",
                            section_target="global",
                            description=f"Outcome {idx+1} ('{outcome[:50]}...') does not begin with a standard measurable action verb.",
                            suggested_fix=f"Rephrase outcome using measurable verbs: 'Differentiate', 'Explain', 'Construct', or 'Analyze'.",
                        )
                    )

        # Check objective alignment with section contents
        combined_content = " ".join(s.content_markdown for s in lesson_plan.sections).lower()
        if "get" in obj_lower and "get" not in combined_content:
            findings.append(
                QCFinding(
                    id=f"find_inst_missing_obj_get_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Learning Objective & Outcomes Alignment",
                    section_target="sec_1",
                    description="Stated learning objective demands explaining GET method, but GET is not adequately covered in lesson content.",
                    suggested_fix="Add a dedicated instructional section thoroughly analyzing GET request semantics.",
                )
            )

        if "dns" in obj_lower and "recursive" in obj_lower and "recursive" not in combined_content:
            findings.append(
                QCFinding(
                    id=f"find_inst_missing_obj_dns_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Learning Objective & Outcomes Alignment",
                    section_target="sec_1",
                    description="Objective requires recursive DNS resolution, but step-by-step resolution sequence is absent.",
                    suggested_fix="Incorporate a step-by-step recursive query walkthrough through Root, TLD, and Authoritative servers.",
                )
            )

        return findings

    def _audit_sequencing_and_scaffolding(self, lesson_plan: LessonPlan) -> List[QCFinding]:
        findings: list[QCFinding] = []

        if len(lesson_plan.sections) < 2:
            findings.append(
                QCFinding(
                    id=f"find_inst_scaffolding_sections_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.MAJOR,
                    criterion="Pedagogical Progression & Scaffolding",
                    section_target="global",
                    description="Lesson contains fewer than 2 sections, failing to scaffold learning from concepts to applications.",
                    suggested_fix="Structure lesson into at least 3 progressive modules: Foundations, Worked Examples, and Systems Applications.",
                )
            )

        if not lesson_plan.introduction or len(lesson_plan.introduction) < 30:
            findings.append(
                QCFinding(
                    id=f"find_inst_weak_intro_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.MINOR,
                    criterion="Pedagogical Progression & Scaffolding",
                    section_target="global",
                    description="Lesson introduction is brief or lacks an engaging pedagogical hook.",
                    suggested_fix="Expand introduction to contextualize the real-world significance and motivational hook.",
                )
            )

        return findings

    def _audit_examples_and_practice(self, lesson_plan: LessonPlan) -> List[QCFinding]:
        findings: list[QCFinding] = []
        combined_text = " ".join(s.content_markdown for s in lesson_plan.sections)

        # Check for presence of code blocks, tables, or terminal snippets
        has_code_or_table = ("```" in combined_text) or ("|" in combined_text) or ("`curl" in combined_text) or ("`dig" in combined_text)

        if not has_code_or_table:
            findings.append(
                QCFinding(
                    id=f"find_inst_no_examples_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.MAJOR,
                    criterion="Worked Examples & Practical Applications",
                    section_target="sec_2",
                    description="Lesson content lacks worked technical examples, comparison tables, or code demonstrations.",
                    suggested_fix="Embed concrete worked examples, syntax breakdowns, and structured comparative markdown tables.",
                )
            )

        return findings

    def _audit_guided_activity(self, lesson_plan: LessonPlan) -> List[QCFinding]:
        findings: list[QCFinding] = []
        activity = lesson_plan.guided_activity

        if not activity:
            findings.append(
                QCFinding(
                    id=f"find_inst_no_activity_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Guided Activity & Lab Engagement",
                    section_target="global",
                    description="Lesson is missing a hands-on guided activity, preventing active student participation.",
                    suggested_fix="Incorporate a dedicated 8-10 minute hands-on terminal or coding lab exercise.",
                )
            )
            return findings

        if len(activity.instructions) < 30:
            findings.append(
                QCFinding(
                    id=f"find_inst_weak_activity_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.MAJOR,
                    criterion="Guided Activity & Lab Engagement",
                    section_target="global",
                    description="Guided activity instructions are underspecified or lack actionable step-by-step guidelines.",
                    suggested_fix="Provide clear, numbered step-by-step instructions for student execution.",
                )
            )

        if not activity.deliverable or len(activity.deliverable) < 5:
            findings.append(
                QCFinding(
                    id=f"find_inst_no_deliverable_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.MINOR,
                    criterion="Guided Activity & Lab Engagement",
                    section_target="global",
                    description="Activity does not specify a tangible expected student deliverable.",
                    suggested_fix="State the expected output artifact (e.g. terminal log, script output, or architecture diagram).",
                )
            )

        return findings

    def _audit_assessments_and_pacing(self, lesson_plan: LessonPlan) -> List[QCFinding]:
        findings: list[QCFinding] = []

        # 1. Knowledge check checks
        if not lesson_plan.knowledge_checks or len(lesson_plan.knowledge_checks) < 2:
            findings.append(
                QCFinding(
                    id=f"find_inst_few_checks_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.MAJOR,
                    criterion="Assessment Rigor & Cognitive Pacing",
                    section_target="global",
                    description=f"Lesson has only {len(lesson_plan.knowledge_checks)} knowledge check(s); minimum 2 required for formative assessment.",
                    suggested_fix="Add at least 3 rigorous multiple-choice questions testing core concepts.",
                )
            )

        for idx, kc in enumerate(lesson_plan.knowledge_checks):
            if kc.correct_answer not in kc.options:
                findings.append(
                    QCFinding(
                        id=f"find_inst_bad_key_{idx}",
                        layer=QCLayer.INSTRUCTIONAL_QUALITY,
                        severity=QCSeverity.CRITICAL,
                        criterion="Assessment Rigor & Cognitive Pacing",
                        section_target="global",
                        description=f"Knowledge Check #{idx+1} answer key '{kc.correct_answer}' is missing from options.",
                        suggested_fix="Ensure correct_answer exactly matches one of the selectable options.",
                    )
                )

            if len(kc.explanation) < 15:
                findings.append(
                    QCFinding(
                        id=f"find_inst_weak_explanation_{idx}",
                        layer=QCLayer.INSTRUCTIONAL_QUALITY,
                        severity=QCSeverity.MINOR,
                        criterion="Assessment Rigor & Cognitive Pacing",
                        section_target="global",
                        description=f"Knowledge Check #{idx+1} lacks an in-depth pedagogical explanation.",
                        suggested_fix="Explain why the correct answer is valid and why alternative distractors are incorrect.",
                    )
                )

        # 2. Timing and cognitive load
        for section in lesson_plan.sections:
            if section.duration_minutes > 20:
                findings.append(
                    QCFinding(
                        id=f"find_inst_section_too_long_{section.section_id}",
                        layer=QCLayer.INSTRUCTIONAL_QUALITY,
                        severity=QCSeverity.MAJOR,
                        criterion="Assessment Rigor & Cognitive Pacing",
                        section_target=section.section_id,
                        description=f"Section '{section.title}' duration is {section.duration_minutes}m (> 20m), exceeding optimal cognitive attention span.",
                        suggested_fix="Split this module into two shorter focused modules to reduce cognitive load.",
                    )
                )

        if lesson_plan.total_duration_minutes > 45:
            findings.append(
                QCFinding(
                    id=f"find_inst_over_45_{uuid.uuid4().hex[:6]}",
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=QCSeverity.CRITICAL,
                    criterion="Assessment Rigor & Cognitive Pacing",
                    section_target="global",
                    description=f"Total duration {lesson_plan.total_duration_minutes}m exceeds mandatory 45-minute lesson delivery ceiling.",
                    suggested_fix="Trim section times so the total duration sum is strictly <= 45 minutes.",
                )
            )

        return findings

    def _compute_scores(
        self,
        findings: List[QCFinding],
    ) -> Tuple[List[CriterionEvaluation], float]:
        criterion_evals: list[CriterionEvaluation] = []
        overall_composite = 0.0

        for crit_name, weight in self.CRITERIA_WEIGHTS.items():
            base_score = 100.0
            crit_findings = [f for f in findings if f.criterion == crit_name]

            for f in crit_findings:
                if f.severity == QCSeverity.CRITICAL:
                    base_score -= 30.0
                elif f.severity == QCSeverity.MAJOR:
                    base_score -= 15.0
                elif f.severity == QCSeverity.MINOR:
                    base_score -= 5.0

            final_crit_score = max(0.0, min(100.0, base_score))
            overall_composite += final_crit_score * weight

            assessment = (
                f"Curriculum design meets high pedagogical standards ({final_crit_score:.0f}/100)."
                if final_crit_score >= 85
                else f"Pedagogical improvements recommended ({len(crit_findings)} issues identified) ({final_crit_score:.0f}/100)."
            )

            criterion_evals.append(
                CriterionEvaluation(
                    criterion_name=crit_name,
                    weight=weight,
                    score=round(final_crit_score, 1),
                    assessment=assessment,
                )
            )

        # Enforce rule: A lesson with critical issues must not receive a passing grade
        crit_count = sum(1 for f in findings if f.severity == QCSeverity.CRITICAL)
        if crit_count > 0:
            overall_composite = min(74.0, overall_composite - (crit_count * 5.0))

        return criterion_evals, round(max(0.0, overall_composite), 1)

    def _generate_recommendations(self, findings: List[QCFinding]) -> List[Recommendation]:
        recommendations: list[Recommendation] = []
        for f in findings:
            recommendations.append(
                Recommendation(
                    id=f"rec_{f.id}",
                    finding_id=f.id,
                    layer=QCLayer.INSTRUCTIONAL_QUALITY,
                    severity=f.severity,
                    section_target=f.section_target or "sec_1",
                    issue_summary=f.description,
                    suggested_content=f.suggested_fix,
                    status=RecommendationStatus.PENDING,
                )
            )
        return recommendations
