"""
Dashboard view for LessonForge AI.
Displays aggregate repository metrics, recently modified lessons,
latest QC audit determinations, and quick actions to create or load lessons.
"""

from __future__ import annotations

import streamlit as st
from datetime import datetime

from core.schemas import LessonInput, LearnerLevel
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.research_auditor import ResearchAuditor
from ui.components import get_status_badge, render_metric_card
from ui.session_state import get_repository, notify, set_active_lesson


def render_dashboard() -> None:
    """Render the executive research dashboard."""
    repo = get_repository()
    lessons = repo.list_lessons()

    st.markdown("## 📊 Research & Instructional Workspace Dashboard")
    st.markdown("Overview of synthesized curriculum, active revisions, and dual-layer quality determinations.")

    # Top Metric Cards
    total_lessons = len(lessons)
    total_audited = 0
    avg_qc_score = 0.0
    all_scores = []

    for l in lessons:
        reports = repo.get_qc_reports(l["lesson_id"], version_number=l["current_version"])
        if reports:
            total_audited += 1
            all_scores.extend([r.overall_score for r in reports])

    if all_scores:
        avg_qc_score = round(sum(all_scores) / len(all_scores), 1)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Total Lessons", total_lessons, "Saved in SQLite")
    with c2:
        render_metric_card("Audited Lessons", total_audited, "Dual QC Complete")
    with c3:
        render_metric_card("Avg QC Score", f"{avg_qc_score}/100" if all_scores else "N/A", "Layer 1 & Layer 2")
    with c4:
        render_metric_card("Duration Ceiling", "45 min", "Mandatory Invariant")

    st.markdown("---")

    # Quick Benchmark Pre-loaders
    st.markdown("### ⚡ Quick Benchmark Synthesis")
    st.caption("Instantly synthesize and persist peer-reviewed benchmark lessons for evaluation:")

    b_col1, b_col2, b_col3 = st.columns([1, 1, 2])
    with b_col1:
        if st.button("🚀 Load HTTP Benchmark", use_container_width=True):
            with st.spinner("Synthesizing and auditing HTTP Requests & Responses benchmark..."):
                gen = LessonGenerator()
                inp = LessonInput(
                    title="HTTP Requests and Responses",
                    learning_objective="Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
                    target_duration_minutes=45,
                    learner_level=LearnerLevel.BEGINNER,
                )
                res = gen.generate(inp, force_offline=True)
                repo.save_lesson(res.lesson_plan, author="BENCHMARK_PRELOADER", change_summary="HTTP Benchmark preloaded")
                
                # Run dual QC
                q1 = ResearchAuditor().audit(res.lesson_plan)
                q2 = InstructionalAuditor().audit(res.lesson_plan)
                repo.save_qc_report(q1)
                repo.save_qc_report(q2)

                set_active_lesson(res.lesson_plan.lesson_id, res.lesson_plan.version)
                notify("Successfully loaded and audited HTTP benchmark lesson!", "success")
                st.session_state.current_page = "Lesson Workspace"
                st.rerun()

    with b_col2:
        if st.button("🌐 Load DNS Benchmark", use_container_width=True):
            with st.spinner("Synthesizing and auditing DNS Resolution benchmark..."):
                gen = LessonGenerator()
                inp = LessonInput(
                    title="DNS Resolution and DNS Record Types",
                    learning_objective="Trace the step-by-step resolution process of a domain name and differentiate between A, AAAA, CNAME, and MX record types.",
                    target_duration_minutes=45,
                    learner_level=LearnerLevel.BEGINNER,
                )
                res = gen.generate(inp, force_offline=True)
                repo.save_lesson(res.lesson_plan, author="BENCHMARK_PRELOADER", change_summary="DNS Benchmark preloaded")
                
                # Run dual QC
                q1 = ResearchAuditor().audit(res.lesson_plan)
                q2 = InstructionalAuditor().audit(res.lesson_plan)
                repo.save_qc_report(q1)
                repo.save_qc_report(q2)

                set_active_lesson(res.lesson_plan.lesson_id, res.lesson_plan.version)
                notify("Successfully loaded and audited DNS benchmark lesson!", "success")
                st.session_state.current_page = "Lesson Workspace"
                st.rerun()

    with b_col3:
        if st.button("➕ Create Custom Lesson from Scratch", type="primary", use_container_width=True):
            st.session_state.current_page = "Create Lesson"
            st.rerun()

    st.markdown("---")

    # Stored Lessons Table & Card List
    st.markdown("### 📚 Stored Instructional Materials")

    if not lessons:
        st.info("No lessons in storage yet. Use the benchmark loaders above or click 'Create Custom Lesson' to begin.")
        return

    for l in lessons:
        lesson_id = l["lesson_id"]
        title = l["title"]
        version = l["current_version"]
        duration = l["duration_minutes"]
        level = l["learner_level"].capitalize()
        updated_at = l["updated_at"][:16].replace("T", " ")

        # Fetch QC status for current version
        qc_reports = repo.get_qc_reports(lesson_id, version_number=version)
        qc1_rep = next((r for r in qc_reports if r.layer.value == "FACTUAL_ACCURACY"), None)
        qc2_rep = next((r for r in qc_reports if r.layer.value == "INSTRUCTIONAL_QUALITY"), None)

        with st.container():
            col_main, col_qc, col_act = st.columns([5, 3, 2])

            with col_main:
                st.markdown(f"**{title}** &nbsp;`<font color='#38BDF8'>v{version}</font>`", unsafe_allow_html=True)
                st.caption(
                    f"Objective: {l['learning_objective'][:100]}... | "
                    f"Audience: {level} | Duration: {duration}m | ID: `{lesson_id[:12]}`"
                )

            with col_qc:
                qc1_badge = get_status_badge(qc1_rep.status.value) if qc1_rep else "<span style='color:#64748B;'>Not Audited</span>"
                qc2_badge = get_status_badge(qc2_rep.status.value) if qc2_rep else "<span style='color:#64748B;'>Not Audited</span>"
                st.markdown(f"<div style='font-size:0.8rem; margin-top:0.25rem;'>QC1 (Factual): {qc1_badge}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:0.8rem; margin-top:0.25rem;'>QC2 (Instructional): {qc2_badge}</div>", unsafe_allow_html=True)

            with col_act:
                btn_open, btn_del = st.columns(2)
                with btn_open:
                    if st.button("Open", key=f"open_{lesson_id}", use_container_width=True):
                        set_active_lesson(lesson_id, version)
                        st.session_state.current_page = "Lesson Workspace"
                        st.rerun()
                with btn_del:
                    if st.button("🗑️", key=f"del_{lesson_id}", help="Delete Lesson", use_container_width=True):
                        repo.delete_lesson(lesson_id)
                        notify(f"Deleted lesson '{title}'.", "warning")
                        st.rerun()

            st.markdown("<hr style='margin: 0.5rem 0; border-color: #1E293B;'/>", unsafe_allow_html=True)
