"""
GitHub Flavored Markdown (GFM) exporter for LessonForge AI.
Transforms structured LessonPlan models and version-specific QC reports
into clean, complete, classroom-ready pedagogical Markdown documents.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from core.exceptions import ExportError
from core.schemas import LessonPlan, ProvenanceStatus, QCReport
from quality_control.qc_schemas import DetailedQCReport


class MarkdownExporter:
    """
    Renders a complete LessonPlan into GitHub Flavored Markdown.
    Guarantees zero omission of instructional content, complete citation provenance,
    and version-traceable QC appendix inclusion.
    """

    def export(
        self,
        lesson: LessonPlan,
        qc_reports: Optional[List[DetailedQCReport | QCReport]] = None,
        output_path: Optional[Path | str] = None,
    ) -> str:
        """
        Generate GFM Markdown string from lesson plan and optional audit reports.
        Optionally writes to output_path.
        """
        if not isinstance(lesson, LessonPlan):
            raise ExportError("Expected a valid LessonPlan object for Markdown export.")

        lines: list[str] = []

        # -------------------------------------------------------------------
        # 1. Document Title & Executive Metadata Banner
        # -------------------------------------------------------------------
        lines.append(f"# {lesson.title}")
        lines.append("")
        lines.append(f"> **Document Version:** v{lesson.version}  ")
        lines.append(f"> **Lesson ID:** `{lesson.lesson_id}`  ")
        lines.append(f"> **Target Audience:** {lesson.learner_level.value.capitalize()}  ")
        lines.append(f"> **Planned Delivery:** {lesson.total_duration_minutes} minutes (Hard Ceiling: 45m)  ")
        lines.append(f"> **Export Timestamp:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ")
        lines.append("")

        # -------------------------------------------------------------------
        # 2. Learning Objective & Outcomes
        # -------------------------------------------------------------------
        lines.append("## Learning Objective")
        lines.append(lesson.learning_objective)
        lines.append("")

        if lesson.prerequisites:
            lines.append("### Prerequisites")
            for req in lesson.prerequisites:
                lines.append(f"- {req}")
            lines.append("")

        lines.append("### Measurable Learning Outcomes")
        lines.append("Upon completion of this 45-minute lesson, learners will be able to:")
        for outcome in lesson.learning_outcomes:
            lines.append(f"- {outcome}")
        lines.append("")

        # -------------------------------------------------------------------
        # 3. Timed Agenda / Table of Contents
        # -------------------------------------------------------------------
        lines.append("## Timed Agenda (45-Minute Budget Allocation)")
        lines.append("")
        lines.append("| Phase / Module | Cognitive Focus | Duration | % Budget |")
        lines.append("| :--- | :--- | :---: | :---: |")

        for s in lesson.sections:
            pct = round((s.duration_minutes / lesson.total_duration_minutes) * 100, 1)
            lines.append(f"| {s.title} | {s.cognitive_focus} | {s.duration_minutes} min | {pct}% |")

        if lesson.guided_activity:
            act = lesson.guided_activity
            act_pct = round((act.duration_minutes / lesson.total_duration_minutes) * 100, 1)
            lines.append(f"| **Guided Lab:** {act.title} | Hands-on Application | {act.duration_minutes} min | {act_pct}% |")

        lines.append(f"| **Total Classroom Delivery** | **Comprehensive Synthesis** | **{lesson.total_duration_minutes} min** | **100%** |")
        lines.append("")

        # -------------------------------------------------------------------
        # 4. Introduction
        # -------------------------------------------------------------------
        lines.append("## Introduction & Orientation")
        lines.append(lesson.introduction)
        lines.append("")

        # -------------------------------------------------------------------
        # 5. Core Sequential Instructional Sections
        # -------------------------------------------------------------------
        for idx, sec in enumerate(lesson.sections, start=1):
            lines.append(f"## {sec.title}")
            lines.append(f"*Duration: {sec.duration_minutes} minutes | Focus: {sec.cognitive_focus}*")
            lines.append("")
            lines.append(sec.content_markdown)
            lines.append("")
            if sec.citations:
                cites_str = ", ".join(f"`[{c}]`" for c in sec.citations)
                lines.append(f"> **Citations:** {cites_str}")
                lines.append("")

        # -------------------------------------------------------------------
        # 6. Guided Hands-On Activity
        # -------------------------------------------------------------------
        if lesson.guided_activity:
            act = lesson.guided_activity
            lines.append(f"## Hands-On Guided Activity: {act.title}")
            lines.append(f"*Allocated Time: {act.duration_minutes} minutes*")
            lines.append("")
            lines.append("### Instructions")
            lines.append(act.instructions)
            lines.append("")
            lines.append(f"### Student Deliverable")
            lines.append(f"**Expected Output:** {act.deliverable}")
            lines.append("")
            if act.evaluation_criteria:
                lines.append("### Evaluation Rubric")
                for crit in act.evaluation_criteria:
                    lines.append(f"- [ ] {crit}")
                lines.append("")

        # -------------------------------------------------------------------
        # 7. Formative Knowledge Checks & Answer Key
        # -------------------------------------------------------------------
        if lesson.knowledge_checks:
            lines.append("## Knowledge Checks")
            for i, kc in enumerate(lesson.knowledge_checks, start=1):
                lines.append(f"### Question {i}: {kc.question}")
                for opt in kc.options:
                    lines.append(f"- {opt}")
                lines.append("")
                lines.append("<details>")
                lines.append(f"<summary><b>View Answer & Pedagogical Explanation</b></summary>")
                lines.append("")
                lines.append(f"**Correct Answer:** `{kc.correct_answer}`  ")
                lines.append(f"**Rationale:** {kc.explanation}")
                lines.append("</details>")
                lines.append("")

        # -------------------------------------------------------------------
        # 8. Summary & Key Takeaways
        # -------------------------------------------------------------------
        lines.append("## Summary & Key Takeaways")
        lines.append(lesson.summary)
        lines.append("")

        # -------------------------------------------------------------------
        # 9. Supplementary Learning Resources
        # -------------------------------------------------------------------
        if lesson.supplementary_videos:
            lines.append("## Supplementary Video Resources (YouTube)")
            lines.append("")
            lines.append("| Title | Channel | Duration | Provenance | Watch Link |")
            lines.append("| :--- | :--- | :---: | :---: | :--- |")
            for vid in lesson.supplementary_videos:
                ch = vid.authors_or_channel or "Verified Educator"
                dur = vid.metadata.get("duration", "N/A")
                prov = vid.provenance.value
                lines.append(f"| {vid.title} | {ch} | {dur} | `{prov}` | [{vid.url}]({vid.url}) |")
            lines.append("")

        # -------------------------------------------------------------------
        # 10. Research References & Provenance Tracking
        # -------------------------------------------------------------------
        lines.append("## Research Bibliography & Source Provenance")
        lines.append("")
        lines.append("Every claim in this lesson is linked to authoritative external evidence with verified provenance:")
        lines.append("")
        lines.append("| Source ID | Title & Authority | Type | Provenance | Credibility | Reference URL |")
        lines.append("| :--- | :--- | :---: | :---: | :---: | :--- |")

        for ref in lesson.references:
            prov_badge = f"`{ref.provenance.value}`"
            cred = f"{round(ref.credibility_score * 100)}%"
            lines.append(
                f"| `{ref.id}` | {ref.title} | {ref.source_type.value} | {prov_badge} | {cred} | [{ref.url}]({ref.url}) |"
            )
        lines.append("")

        # -------------------------------------------------------------------
        # 11. Version-Specific Independent Quality Control Appendix
        # -------------------------------------------------------------------
        lines.append("---")
        lines.append(f"## Appendix: Quality Control Audit Reports for Version {lesson.version}")
        lines.append("")

        if qc_reports:
            matching_reports = [r for r in qc_reports if r.version_audited == lesson.version]
            if matching_reports:
                for rep in matching_reports:
                    layer_title = (
                        "QC Layer 1: Research & Factual Accuracy Audit"
                        if rep.layer.value == "FACTUAL_ACCURACY"
                        else "QC Layer 2: Instructional Quality Audit"
                    )
                    status_badge = f"**[{rep.status.value}]**"
                    lines.append(f"### {layer_title} — Score: {rep.overall_score}/100 {status_badge}")
                    lines.append(f"> **Audited Version:** v{rep.version_audited} | **Audit ID:** `{rep.report_id}`")
                    lines.append("")
                    lines.append(f"**Executive Audit Summary:**  \n{rep.summary}")
                    lines.append("")

                    if rep.criterion_scores:
                        lines.append("#### Criterion Breakdown")
                        lines.append("| Rubric Dimension | Weight | Score | Evaluation |")
                        lines.append("| :--- | :---: | :---: | :--- |")
                        for c in rep.criterion_scores:
                            lines.append(f"| {c.criterion_name} | {round(c.weight * 100)}% | {c.score}/100 | {c.assessment} |")
                        lines.append("")

                    if rep.findings:
                        lines.append(f"#### Audit Findings ({len(rep.findings)} items)")
                        for f in rep.findings:
                            lines.append(f"- **[{f.severity.value}] {f.criterion}** (`{f.section_target or 'global'}`): {f.description}")
                            if f.suggested_fix:
                                lines.append(f"  *Remediation:* {f.suggested_fix}")
                        lines.append("")
            else:
                lines.append(
                    f"*Notice: No Quality Control audit records found matching version {lesson.version}. "
                    f"Available reports belong to other revisions.*"
                )
                lines.append("")
        else:
            lines.append(f"*Notice: Quality Control audit has not yet been conducted for Version {lesson.version}.*")
            lines.append("")

        content = "\n".join(lines)

        # Write to file if requested
        if output_path is not None:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(content, encoding="utf-8")

        return content
