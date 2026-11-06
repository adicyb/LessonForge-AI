"""
LessonForge AI — Primary Streamlit Application Entrypoint.
Tagline: From research to classroom-ready learning.
Orchestrates multi-modal research, evidence-grounded generation, dual QC audits,
immutable version persistence, and multi-format document exports.
"""

from __future__ import annotations

import streamlit as st

from ui.components import inject_custom_css, render_app_header
from ui.pages.create_lesson import render_create_lesson
from ui.pages.dashboard import render_dashboard
from ui.pages.lesson_workspace import render_lesson_workspace
from ui.pages.quality_control import render_quality_control
from ui.pages.research_sources import render_research_sources
from ui.pages.settings import render_settings
from ui.session_state import (
    display_feedback,
    get_active_lesson,
    get_repository,
    init_session_state,
    set_active_lesson,
)

# ---------------------------------------------------------------------------
# Streamlit Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="LessonForge AI — Research to Classroom",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    """Main application orchestrator and view router."""
    # Initialize UI and State
    inject_custom_css()
    init_session_state()

    # Sidebar Navigation and Active Lesson Status
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 0.5rem 0 1rem 0; border-bottom: 1px solid #1E293B; margin-bottom: 1rem;">
                <h2 style="color: #38BDF8 !important; margin: 0; font-size: 1.4rem;">⚡ LessonForge AI</h2>
                <div style="font-size: 0.78rem; color: #94A3B8; margin-top: 0.2rem;">From research to classroom-ready learning</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Active Lesson Indicator
        active_lesson = get_active_lesson()
        repo = get_repository()

        if active_lesson:
            st.markdown(
                f"""
                <div style="background: #111827; border: 1px solid #0D9488; border-radius: 6px; padding: 0.75rem; margin-bottom: 1rem;">
                    <div style="font-size: 0.7rem; color: #5EEAD4; font-weight: 700; text-transform: uppercase;">Active Lesson</div>
                    <div style="font-size: 0.88rem; font-weight: 700; color: #F8FAFC; margin-top: 0.2rem;">{active_lesson.title}</div>
                    <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 0.2rem;">
                        Version: <b>v{active_lesson.version}</b> &bull; Duration: <b>{active_lesson.total_duration_minutes}m</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Main Navigation Selector
        nav_options = [
            "Dashboard",
            "Create Lesson",
            "Lesson Workspace",
            "Research Sources",
            "Dual Quality Control",
            "Settings & System Status",
        ]

        # Sync selection with session state
        default_index = nav_options.index(st.session_state.current_page) if st.session_state.current_page in nav_options else 0
        selected_page = st.radio("Navigation Workspace", options=nav_options, index=default_index)

        if selected_page != st.session_state.current_page:
            st.session_state.current_page = selected_page
            st.rerun()

        # Switch Active Lesson Dropdown if lessons exist
        all_lessons = repo.list_lessons()
        if all_lessons:
            st.markdown("---")
            st.markdown("<div style='font-size:0.75rem; font-weight:700; color:#94A3B8;'>QUICK SWITCH LESSON:</div>", unsafe_allow_html=True)
            lesson_choices = {l["lesson_id"]: f"{l['title']} (v{l['current_version']})" for l in all_lessons}
            current_id = active_lesson.lesson_id if active_lesson else all_lessons[0]["lesson_id"]

            selected_id = st.selectbox(
                "Select Lesson",
                options=list(lesson_choices.keys()),
                index=list(lesson_choices.keys()).index(current_id) if current_id in lesson_choices else 0,
                format_func=lambda x: lesson_choices[x],
                label_visibility="collapsed",
            )
            if not active_lesson or selected_id != active_lesson.lesson_id:
                set_active_lesson(selected_id)
                st.rerun()

        # Sidebar Footer
        st.markdown(
            """
            <div style="position: fixed; bottom: 1rem; width: 15rem; font-size: 0.7rem; color: #64748B; border-top: 1px solid #1E293B; padding-top: 0.5rem;">
                LessonForge AI v1.0.0<br/>
                Kalvium AI Research Intern Submission
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Main Canvas Branding Banner
    render_app_header()

    # Toast / Feedback notification
    display_feedback()

    # Router to Selected Workspace View
    current = st.session_state.current_page
    if current == "Dashboard":
        render_dashboard()
    elif current == "Create Lesson":
        render_create_lesson()
    elif current == "Lesson Workspace":
        render_lesson_workspace()
    elif current == "Research Sources":
        render_research_sources()
    elif current == "Dual Quality Control":
        render_quality_control()
    elif current == "Settings & System Status":
        render_settings()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
