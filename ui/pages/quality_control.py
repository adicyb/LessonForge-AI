"""
Dual Quality Control & Recommendation Review Hub for LessonForge AI.
Features strictly isolated QC1 (Factual Accuracy) and QC2 (Instructional Quality) panels,
atomic claim traceability, severity-tiered findings, and instructor recommendation patching.
"""

from __future__ import annotations

import streamlit as st

from core.schemas import QCLayer, QCSeverity, QCStatus, RecommendationStatus
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.recommendation_engine import RecommendationEngine
from quality_control.research_auditor import ResearchAuditor
from ui.components import get_status_badge, render_diff_viewer, render_metric_card
from ui.session_state import get_active_lesson, get_repository, notify, set_active_lesson


def render_quality_control() -> None:
    """Render the dual-layer QC and recommendation review workspace."""
    active_lesson = get_active_lesson()
    repo = get_repository()

    if active_lesson is None:
        st.warning("No active lesson selected. Please select a lesson from the Dashboard or create a new one.")
        return

    lesson_id = active_lesson.lesson_id
    version_audited = active_lesson.version

    st.markdown(f"## 🛡️ Dual Quality Control & Recommendation Hub: {active_lesson.title}")
    st.markdown(
        f"**Active Revision:** Version {version_audited} &nbsp;|&nbsp; "
        "LessonForge AI evaluates instructional materials through two strictly decoupled, independent quality layers."
    )

    # Top Audit Trigger Controls
    act_col1, act_col2, act_col3 = st.columns([1, 1, 1])

    with act_col1:
        if st.button("🔬 Run QC Layer 1 (Factual Only)", use_container_width=True):
            with st.spinner("Extracting atomic claims and verifying evidence citations..."):
                rep1 = ResearchAuditor().audit(active_lesson)
                repo.save_qc_report(rep1)
                # Also save any new recommendations generated
                for r in rep1.recommendations:
                    repo.save_recommendation(r, lesson_id, version_audited)
                notify(f"QC Layer 1 completed. Score: {rep1.overall_score}/100 ({rep1.status.value})", "success" if rep1.status == QCStatus.PASSED else "warning")
                st.rerun()

    with act_col2:
        if st.button("📐 Run QC Layer 2 (Instructional Only)", use_container_width=True):
            with st.spinner("Auditing Bloom's taxonomy progression and cognitive load..."):
                rep2 = InstructionalAuditor().audit(active_lesson)
                repo.save_qc_report(rep2)
                for r in rep2.recommendations:
                    repo.save_recommendation(r, lesson_id, version_audited)
                notify(f"QC Layer 2 completed. Score: {rep2.overall_score}/100 ({rep2.status.value})", "success" if rep2.status == QCStatus.PASSED else "warning")
                st.rerun()

    with act_col3:
        if st.button("🛡️ Run Both QC Audits Independently", type="primary", use_container_width=True):
            with st.spinner("Executing independent dual quality control audits..."):
                rep1 = ResearchAuditor().audit(active_lesson)
                rep2 = InstructionalAuditor().audit(active_lesson)
                repo.save_qc_report(rep1)
                repo.save_qc_report(rep2)
                for r in rep1.recommendations + rep2.recommendations:
                    repo.save_recommendation(r, lesson_id, version_audited)
                notify(f"Dual audits completed: QC1 = {rep1.overall_score}/100, QC2 = {rep2.overall_score}/100", "success")
                st.rerun()

    st.markdown("---")

    # Fetch existing reports for this exact version
    reports = repo.get_qc_reports(lesson_id, version_number=version_audited)
    qc1_report = next((r for r in reports if r.layer.value == "FACTUAL_ACCURACY"), None)
    qc2_report = next((r for r in reports if r.layer.value == "INSTRUCTIONAL_QUALITY"), None)

    # Main QC Tabs
    qc_tab1, qc_tab2, qc_tab3 = st.tabs([
        "🔬 QC Layer 1: Research & Factual Accuracy",
        "📐 QC Layer 2: Instructional Quality",
        "💡 Instructor Recommendation Review",
    ])

    # -----------------------------------------------------------------------
    # TAB 1: QC Layer 1 (Research & Factual Accuracy)
    # -----------------------------------------------------------------------
    with qc_tab1:
        st.markdown("### QC Layer 1: Research & Factual Veracity Audit")
        st.caption("Inspects atomic claims, citation authenticity, and RFC/standard compliance. Penalizes ungrounded assertions.")

        if qc1_report is None:
            st.info("QC Layer 1 has not yet been executed for this version. Click 'Run QC Layer 1' above.")
        else:
            # Score Metrics
            m1, m2, m3 = st.columns(3)
            with m1:
                render_metric_card("Factual Score", f"{qc1_report.overall_score}/100", f"Status: {qc1_report.status.value}")
            with m2:
                status_html = get_status_badge(qc1_report.status.value)
                st.markdown(f"<div style='margin-top:1.5rem; text-align:center;'>Determination:<br/>{status_html}</div>", unsafe_allow_html=True)
            with m3:
                crit_count = len(qc1_report.critical_findings)
                render_metric_card("Critical Findings", crit_count, "Score capped at ≤ 74 if > 0")

            if qc1_report.critical_findings:
                st.error("⚠️ CRITICAL FACTUAL FLAW DETECTED: Score capped at ≤ 74.0. Mandatory remediation required before classroom delivery.")

            st.markdown(f"**Executive Narrative:**\n{qc1_report.summary}")
            st.markdown("---")

            # Rubric Breakdown Table
            st.markdown("#### Weighted Criterion Evaluation (100% Total)")
            crit_rows = [
                {
                    "Rubric Dimension": c.criterion_name,
                    "Weight": f"{round(c.weight * 100)}%",
                    "Score": f"{c.score}/100",
                    "Evaluation Assessment": c.assessment,
                }
                for c in qc1_report.criterion_scores
            ]
            st.table(crit_rows)

            # Atomic Claims Table
            if qc1_report.atomic_claims:
                st.markdown(f"#### Atomic Claim Verification ({len(qc1_report.atomic_claims)} Extracted Claims)")
                claims_data = [
                    {
                        "Claim ID": clm.claim_id,
                        "Section": clm.section_id,
                        "Factual Proposition": clm.claim_text,
                        "Citations": ", ".join(clm.cited_source_ids) or "None",
                        "Support Status": clm.support_status.value,
                        "Auditor Evidence": clm.evidence_excerpt or clm.explanation,
                    }
                    for clm in qc1_report.atomic_claims
                ]
                st.dataframe(claims_data, use_container_width=True)

            # Findings List
            if qc1_report.findings:
                st.markdown("#### Audit Findings & Remediation Advice")
                for f in qc1_report.findings:
                    with st.expander(f"[{f.severity.value}] {f.criterion} — {f.description[:90]}..."):
                        st.markdown(f"**Section Target:** `{f.section_target or 'global'}`")
                        st.markdown(f"**Flaw Description:** {f.description}")
                        if f.evidence_quote:
                            st.caption(f"Evidence Excerpt: *\"{f.evidence_quote}\"*")
                        st.success(f"**Remediation Fix:** {f.suggested_fix}")

    # -----------------------------------------------------------------------
    # TAB 2: QC Layer 2 (Instructional Quality)
    # -----------------------------------------------------------------------
    with qc_tab2:
        st.markdown("### QC Layer 2: Pedagogical & Curriculum Efficacy Audit")
        st.caption("Evaluates Bloom's taxonomy progression, worked examples, hands-on lab rigor, and cognitive load.")

        if qc2_report is None:
            st.info("QC Layer 2 has not yet been executed for this version. Click 'Run QC Layer 2' above.")
        else:
            m1, m2, m3 = st.columns(3)
            with m1:
                render_metric_card("Instructional Score", f"{qc2_report.overall_score}/100", f"Status: {qc2_report.status.value}")
            with m2:
                status_html = get_status_badge(qc2_report.status.value)
                st.markdown(f"<div style='margin-top:1.5rem; text-align:center;'>Determination:<br/>{status_html}</div>", unsafe_allow_html=True)
            with m3:
                crit_count = len(qc2_report.critical_findings)
                render_metric_card("Instructional Defects", crit_count, "Missing activity or bad rubric")

            st.markdown(f"**Executive Narrative:**\n{qc2_report.summary}")
            st.markdown("---")

            # Rubric Breakdown Table
            st.markdown("#### Pedagogical Dimension Evaluation")
            crit_rows = [
                {
                    "Dimension": c.criterion_name,
                    "Weight": f"{round(c.weight * 100)}%",
                    "Score": f"{c.score}/100",
                    "Assessment": c.assessment,
                }
                for c in qc2_report.criterion_scores
            ]
            st.table(crit_rows)

            # Findings List
            if qc2_report.findings:
                st.markdown("#### Pedagogical Improvement Recommendations")
                for f in qc2_report.findings:
                    with st.expander(f"[{f.severity.value}] {f.criterion} — {f.description[:90]}..."):
                        st.markdown(f"**Section Target:** `{f.section_target or 'global'}`")
                        st.markdown(f"**Pedagogical Flaw:** {f.description}")
                        st.info(f"**Instructional Remediation:** {f.suggested_fix}")

    # -----------------------------------------------------------------------
    # TAB 3: Recommendation Review & Non-Destructive Patching
    # -----------------------------------------------------------------------
    with qc_tab3:
        st.markdown("### 💡 Instructor Recommendation Review & Patching")
        st.markdown(
            "Review AI-generated Quality Control recommendations. Instructors can **Accept**, **Reject**, or **Annotate** "
            "recommendations. Applying accepted recommendations performs **true in-place text replacement**, updates the version, "
            "and preserves the original draft snapshot."
        )

        all_recs = repo.get_recommendations(lesson_id, version_number=version_audited)
        if not all_recs:
            # Fallback check from current reports if none explicitly saved in recommendations table
            extracted = []
            if qc1_report and qc1_report.recommendations:
                extracted.extend(qc1_report.recommendations)
            if qc2_report and qc2_report.recommendations:
                extracted.extend(qc2_report.recommendations)
            for r in extracted:
                repo.save_recommendation(r, lesson_id, version_audited)
            all_recs = repo.get_recommendations(lesson_id, version_number=version_audited)

        if not all_recs:
            st.success("🎉 No outstanding recommendations for this lesson version! The material meets all quality thresholds.")
            return

        # Status Filter
        status_filter = st.radio(
            "Filter Recommendations by Status",
            options=["ALL", "PENDING", "ACCEPTED", "APPLIED", "REJECTED"],
            horizontal=True,
            index=0,
        )

        filtered_recs = (
            all_recs if status_filter == "ALL"
            else [r for r in all_recs if r.status.value == status_filter]
        )

        st.caption(f"Displaying {len(filtered_recs)} recommendations:")

        engine = RecommendationEngine()

        for idx, rec in enumerate(filtered_recs):
            rec_id = rec.id
            is_pending = rec.status == RecommendationStatus.PENDING
            is_accepted = rec.status == RecommendationStatus.ACCEPTED
            is_applied = rec.status == RecommendationStatus.APPLIED
            is_rejected = rec.status == RecommendationStatus.REJECTED

            with st.container():
                st.markdown(
                    f"<div class='forge-card'>"
                    f"<div class='forge-card-header'>"
                    f"<span>[{rec.severity.value}] {rec.issue_summary}</span>"
                    f"<span>Status: <b>{rec.status.value}</b> &bull; Target: <code>{rec.section_target}</code></span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                st.markdown(f"**Proposed Textual Replacement:**\n> *\"{rec.suggested_content}\"*")
                if rec.instructor_notes:
                    st.caption(f"Instructor Annotation: *\"{rec.instructor_notes}\"*")

                col_b1, col_b2, col_b3 = st.columns([2, 2, 4])

                # Accept Button
                if is_pending or is_rejected:
                    with col_b1:
                        if st.button("✅ Accept", key=f"acc_{rec_id}_{idx}", use_container_width=True):
                            rec_acc = engine.accept_recommendation(rec, instructor_notes="Accepted via QC Hub")
                            repo.save_recommendation(rec_acc, lesson_id, version_audited)
                            repo.save_recommendation_decision(rec_id, RecommendationStatus.ACCEPTED, notes="Accepted via QC Hub")
                            notify(f"Accepted recommendation '{rec.issue_summary}'. Ready to apply.", "success")
                            st.rerun()

                # Reject Button
                if is_pending or is_accepted:
                    with col_b2:
                        if st.button("❌ Reject", key=f"rej_{rec_id}_{idx}", use_container_width=True):
                            rec_rej = engine.reject_recommendation(rec, rejection_reason="Rejected by instructor")
                            repo.save_recommendation(rec_rej, lesson_id, version_audited)
                            repo.save_recommendation_decision(rec_id, RecommendationStatus.REJECTED, notes="Rejected by instructor")
                            notify(f"Rejected recommendation '{rec.issue_summary}'.", "warning")
                            st.rerun()

                # Apply Button (Active when Accepted)
                if is_accepted:
                    with col_b3:
                        if st.button("⚡ Apply Replacement to New Version", key=f"app_{rec_id}_{idx}", type="primary", use_container_width=True):
                            with st.spinner("Applying non-destructive replacement and incrementing lesson version..."):
                                revised_lesson, diff = engine.apply_recommendation(active_lesson, rec)
                                # Persist revised lesson in SQLite as new version
                                new_ver = repo.save_lesson_version(
                                    revised_lesson,
                                    author="INSTRUCTOR_QC_PATCH",
                                    change_summary=f"Remediated: {rec.issue_summary}",
                                )
                                # Update recommendation status to APPLIED
                                repo.save_recommendation_decision(rec_id, RecommendationStatus.APPLIED, notes=f"Applied in Version {new_ver}")
                                
                                # Automatically re-audit the revised lesson independently!
                                rep1_new = ResearchAuditor().audit(revised_lesson)
                                rep2_new = InstructionalAuditor().audit(revised_lesson)
                                repo.save_qc_report(rep1_new)
                                repo.save_qc_report(rep2_new)

                                # Set active lesson to new version
                                set_active_lesson(lesson_id, new_ver)
                                notify(
                                    f"Successfully applied recommendation! Created Version {new_ver}. "
                                    f"Re-audited QC1 score improved to {rep1_new.overall_score}/100 ({rep1_new.status.value})!",
                                    "success",
                                )
                                st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)
