"""
Lesson Workspace & Editor view for LessonForge AI.
Provides complete interactive lesson viewing, section-level instructor editing,
version history navigation, diff comparison, and multi-format exports.
"""

from __future__ import annotations

import copy
import streamlit as st

from core.exceptions import DurationExceededError, ValidationError
from core.schemas import LessonPlan, TimedSection
from export.export_service import ExportService
from ui.components import get_status_badge, render_diff_viewer
from ui.session_state import get_active_lesson, get_repository, notify, set_active_lesson


def render_lesson_workspace() -> None:
    """Render the comprehensive lesson workspace."""
    repo = get_repository()
    active_lesson = get_active_lesson()

    if active_lesson is None:
        st.warning("No active lesson selected. Please select a lesson from the Dashboard or create a new one.")
        if st.button("⬅️ Return to Dashboard"):
            st.session_state.current_page = "Dashboard"
            st.rerun()
        return

    lesson_id = active_lesson.lesson_id

    # Top Control Bar: Version Selector & Switcher
    versions = repo.get_lesson_versions(lesson_id)
    available_ver_numbers = [v["version_number"] for v in versions]
    current_ver = active_lesson.version

    top_c1, top_c2, top_c3 = st.columns([6, 3, 3])
    with top_c1:
        st.markdown(f"## 📖 {active_lesson.title}")
    with top_c2:
        selected_ver = st.selectbox(
            "Selected Revision Snapshot",
            options=available_ver_numbers,
            index=available_ver_numbers.index(current_ver) if current_ver in available_ver_numbers else len(available_ver_numbers) - 1,
            format_func=lambda v: f"Version {v} {'(Latest Active)' if v == max(available_ver_numbers) else '(Historical)'}",
        )
        if selected_ver != current_ver:
            set_active_lesson(lesson_id, selected_ver)
            st.rerun()

    with top_c3:
        st.markdown(
            f"<div style='text-align:right; margin-top:1.5rem;'>"
            f"<span style='color:#38BDF8; font-weight:700;'>⏱️ {active_lesson.total_duration_minutes} min / 45m</span> &bull; "
            f"<span style='color:#94A3B8;'>{active_lesson.learner_level.value.capitalize()}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.caption(f"**Learning Objective:** {active_lesson.learning_objective}")
    st.markdown("---")

    # Main Workspace Tabs
    tab_view, tab_edit, tab_history, tab_export = st.tabs([
        "📄 Interactive Document",
        "✏️ Content Editor",
        "🕒 Version History & Diffs",
        "📥 Multi-Format Export",
    ])

    # -----------------------------------------------------------------------
    # TAB 1: Interactive Document Viewer
    # -----------------------------------------------------------------------
    with tab_view:
        st.markdown("### 🎯 Measurable Learning Outcomes")
        for outcome in active_lesson.learning_outcomes:
            st.markdown(f"- **{outcome}**")

        st.markdown("---")

        # 45-Minute Timed Agenda
        st.markdown("### ⏱️ Timed Agenda (45-Minute Budget Allocation)")
        agenda_rows = []
        for s in active_lesson.sections:
            pct = round((s.duration_minutes / active_lesson.total_duration_minutes) * 100, 1)
            agenda_rows.append({
                "Module / Phase": s.title,
                "Cognitive Focus": s.cognitive_focus,
                "Duration": f"{s.duration_minutes} mins",
                "% Class": f"{pct}%",
            })
        if active_lesson.guided_activity:
            act = active_lesson.guided_activity
            act_pct = round((act.duration_minutes / active_lesson.total_duration_minutes) * 100, 1)
            agenda_rows.append({
                "Module / Phase": f"Guided Lab: {act.title}",
                "Cognitive Focus": "Hands-On Practice",
                "Duration": f"{act.duration_minutes} mins",
                "% Class": f"{act_pct}%",
            })
        st.table(agenda_rows)

        st.markdown("---")

        # Introduction
        st.markdown("### 💡 Conceptual Orientation")
        st.markdown(active_lesson.introduction)
        st.markdown("---")

        # Sequential Modules
        for idx, sec in enumerate(active_lesson.sections, start=1):
            st.markdown(f"### {sec.title}")
            st.caption(f"Planned Duration: **{sec.duration_minutes} minutes** | Focus: **{sec.cognitive_focus}**")
            st.markdown(sec.content_markdown)
            if sec.citations:
                cites = ", ".join(f"`[{c}]`" for c in sec.citations)
                st.info(f"**Authoritative Citations:** {cites}")
            st.markdown("<br/>", unsafe_allow_html=True)

        # Guided Hands-On Lab
        if active_lesson.guided_activity:
            st.markdown("---")
            act = active_lesson.guided_activity
            st.markdown(f"### 🧪 Guided Hands-On Lab: {act.title} ({act.duration_minutes} min)")
            st.markdown(f"**Instructions:**\n{act.instructions}")
            st.success(f"**Expected Deliverable:** {act.deliverable}")
            if act.evaluation_criteria:
                st.markdown("**Assessment Rubric:**")
                for crit in act.evaluation_criteria:
                    st.checkbox(crit, value=False, key=f"rubric_{crit[:15]}")

        # Formative Knowledge Checks
        if active_lesson.knowledge_checks:
            st.markdown("---")
            st.markdown("### ❓ Formative Knowledge Checks")
            for i, kc in enumerate(active_lesson.knowledge_checks, start=1):
                st.markdown(f"**Question {i}: {kc.question}**")
                for opt in kc.options:
                    st.markdown(f"- {opt}")
                with st.expander(f"Reveal Answer & Pedagogical Explanation for Q{i}"):
                    st.markdown(f"**Correct Answer:** `{kc.correct_answer}`")
                    st.markdown(f"**Explanation:** {kc.explanation}")

        # Summary
        st.markdown("---")
        st.markdown("### 📌 Summary & Key Takeaways")
        st.markdown(active_lesson.summary)

    # -----------------------------------------------------------------------
    # TAB 2: Instructor Content Editor
    # -----------------------------------------------------------------------
    with tab_edit:
        st.markdown("### ✏️ Pedagogical Content Editor")
        st.markdown(
            "Instructors have full authority to modify lesson text, add specialized examples, or refine explanations. "
            "Saving changes **creates a new immutable version snapshot**, preserving the original."
        )

        # Section Selector
        section_titles = [f"Section {i+1}: {s.title}" for i, s in enumerate(active_lesson.sections)]
        sec_idx = st.selectbox("Select Section to Edit", options=range(len(section_titles)), format_func=lambda i: section_titles[i])

        target_sec = active_lesson.sections[sec_idx]

        with st.form("editor_form"):
            col_ed1, col_ed2 = st.columns([3, 1])
            with col_ed1:
                new_sec_title = st.text_input("Section Title", value=target_sec.title)
            with col_ed2:
                new_sec_dur = st.number_input("Duration (Mins)", min_value=1, max_value=30, value=target_sec.duration_minutes)

            new_content = st.text_area("Markdown Content", value=target_sec.content_markdown, height=350)

            col_meta1, col_meta2 = st.columns(2)
            with col_meta1:
                author_name = st.text_input("Instructor / Author Name", value="INSTRUCTOR_REVIEWER")
            with col_meta2:
                change_summary = st.text_input("Summary of Changes", value=f"Refined {target_sec.title}")

            save_submitted = st.form_submit_button("💾 Save as New Version", type="primary", use_container_width=True)

        if save_submitted:
            # Create deep copy
            revised_lesson = copy.deepcopy(active_lesson)
            # Update target section
            revised_lesson.sections[sec_idx].title = new_sec_title.strip()
            revised_lesson.sections[sec_idx].duration_minutes = int(new_sec_dur)
            revised_lesson.sections[sec_idx].content_markdown = new_content.strip()

            # Recalculate duration
            sec_sum = sum(s.duration_minutes for s in revised_lesson.sections)
            act_dur = revised_lesson.guided_activity.duration_minutes if revised_lesson.guided_activity else 0
            revised_lesson.total_duration_minutes = sec_sum + act_dur

            if revised_lesson.total_duration_minutes > 45:
                st.error(f"Cannot save: Total duration ({revised_lesson.total_duration_minutes}m) exceeds the mandatory 45-minute ceiling.")
                return

            # Save as new version in SQLite
            new_v = repo.save_lesson_version(revised_lesson, author=author_name.strip(), change_summary=change_summary.strip())
            set_active_lesson(lesson_id, new_v)
            notify(f"Created and saved Version {new_v} successfully!", "success")
            st.rerun()

    # -----------------------------------------------------------------------
    # TAB 3: Version History & Diffs
    # -----------------------------------------------------------------------
    with tab_history:
        st.markdown("### 🕒 Immutable Version History & Snapshots")
        st.markdown("Every revision is archived as a permanent, retrievable snapshot in SQLite.")

        for v in versions:
            v_num = v["version_number"]
            v_auth = v["author"]
            v_sum = v["change_summary"]
            v_date = v["created_at"][:16].replace("T", " ")
            is_active = v_num == active_lesson.version

            card_border = "#0D9488" if is_active else "#334155"
            with st.container():
                st.markdown(
                    f"<div style='border:1px solid {card_border}; border-radius:6px; padding:0.75rem 1rem; margin-bottom:0.75rem; background:#1E293B;'>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"<div><b>Version {v_num}</b> &nbsp;<span style='color:#38BDF8;'>{v_sum}</span></div>"
                    f"<div style='font-size:0.8rem; color:#94A3B8;'>By: <b>{v_auth}</b> &bull; {v_date}</div>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )

        if len(versions) >= 2:
            st.markdown("---")
            st.markdown("#### 🔍 Compare Revisions Side-by-Side")
            c_diff1, c_diff2 = st.columns(2)
            with c_diff1:
                v_from = st.selectbox("Base Version", options=available_ver_numbers, index=0)
            with c_diff2:
                v_to = st.selectbox("Compare With Version", options=available_ver_numbers, index=len(available_ver_numbers)-1)

            if v_from != v_to:
                l_from = repo.get_lesson_version(lesson_id, v_from)
                l_to = repo.get_lesson_version(lesson_id, v_to)
                if l_from and l_to:
                    # Diff section 2 as typical target or full text
                    st.markdown(f"**Diff between Version {v_from} and Version {v_to} (Section 2):**")
                    text_from = l_from.sections[1].content_markdown if len(l_from.sections) > 1 else l_from.sections[0].content_markdown
                    text_to = l_to.sections[1].content_markdown if len(l_to.sections) > 1 else l_to.sections[0].content_markdown
                    render_diff_viewer(text_from, text_to)

    # -----------------------------------------------------------------------
    # TAB 4: Multi-Format Export
    # -----------------------------------------------------------------------
    with tab_export:
        st.markdown(f"### 📥 Export Version {active_lesson.version}")
        st.markdown("Generate and download publication-ready educational artifacts.")

        export_service = ExportService(repo=repo)
        matching_qc = repo.get_qc_reports(lesson_id, version_number=active_lesson.version)

        # QC Traceability Status Banner
        if matching_qc:
            qc1 = next((r for r in matching_qc if r.layer.value == "FACTUAL_ACCURACY"), None)
            qc2 = next((r for r in matching_qc if r.layer.value == "INSTRUCTIONAL_QUALITY"), None)
            qc1_str = f"{qc1.overall_score}/100 ({qc1.status.value})" if qc1 else "Not Audited"
            qc2_str = f"{qc2.overall_score}/100 ({qc2.status.value})" if qc2 else "Not Audited"
            st.success(f"✅ Audit Traceability: Export will attach verified audit reports for Version {active_lesson.version} (QC1: {qc1_str} | QC2: {qc2_str}).")
        else:
            st.info(f"ℹ️ Audit Traceability: Version {active_lesson.version} has not been audited yet. Export will clearly denote that audit records are pending.")

        st.markdown("<br/>", unsafe_allow_html=True)
        col_md, col_pdf = st.columns(2)

        with col_md:
            st.markdown("#### 📝 GitHub Flavored Markdown (`.md`)")
            st.caption("Clean, complete academic markdown with GFM tables, collapsible answer keys, and citation provenance.")
            if st.button("Generate Markdown Artifact", key="gen_md_btn", use_container_width=True):
                with st.spinner("Rendering Markdown artifact..."):
                    md_path = export_service.export_markdown(lesson_id, version=active_lesson.version)
                    md_bytes = md_path.read_bytes()
                    st.download_button(
                        label="⬇️ Download Markdown (.md)",
                        data=md_bytes,
                        file_name=md_path.name,
                        mime="text/markdown",
                        use_container_width=True,
                    )

        with col_pdf:
            st.markdown("#### 📑 Publication-Grade PDF (`.pdf`)")
            st.caption("ReportLab vector document featuring executive styling, timed agenda grid, selectable text, and dynamic pagination.")
            if st.button("Generate PDF Teaching Guide", key="gen_pdf_btn", type="primary", use_container_width=True):
                with st.spinner("Compiling vector PDF document with ReportLab..."):
                    pdf_path = export_service.export_pdf(lesson_id, version=active_lesson.version)
                    pdf_bytes = pdf_path.read_bytes()
                    st.download_button(
                        label="⬇️ Download PDF Guide (.pdf)",
                        data=pdf_bytes,
                        file_name=pdf_path.name,
                        mime="application/pdf",
                        use_container_width=True,
                    )
