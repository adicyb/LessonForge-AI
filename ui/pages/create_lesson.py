"""
Create Lesson view for LessonForge AI.
Handles user inputs, input validation, multi-modal research coordination,
evidence-grounded lesson synthesis, and automatic initial QC auditing.
"""

from __future__ import annotations

import streamlit as st

from config import AppConfig
from core.exceptions import EmptyInputError, ValidationError
from core.schemas import LearnerLevel, LessonInput
from generation.lesson_generator import LessonGenerator
from quality_control.instructional_auditor import InstructionalAuditor
from quality_control.research_auditor import ResearchAuditor
from research.research_engine import ResearchEngine
from ui.session_state import get_repository, notify, set_active_lesson


def render_create_lesson() -> None:
    """Render the lesson synthesis studio."""
    st.markdown("## ➕ Research & Synthesize New Lesson")
    st.markdown(
        "Enter the curriculum parameters below. The multi-modal research engine will scour "
        "web standards, authoritative books, and educational videos before synthesizing a strictly budgeted, 45-minute lesson."
    )

    config = AppConfig()
    api_available = config.is_api_configured()

    if api_available:
        st.success("🟢 Google Gemini API configured. Generation will use live grounded synthesis.")
    else:
        st.info("🔵 Generation Mode: Deterministic Academic Fallback Engine (Offline resilient, zero external API keys required).")

    with st.form("create_lesson_form"):
        col1, col2 = st.columns([3, 2])

        with col1:
            title = st.text_input(
                "Lesson Title *",
                placeholder="e.g. HTTP Requests and Responses, or DNS Resolution and DNS Record Types",
                help="The specific academic or technical topic.",
            )

        with col2:
            learner_level_str = st.selectbox(
                "Target Audience Level *",
                options=["BEGINNER", "INTERMEDIATE", "ADVANCED"],
                index=0,
                help="Calibrates cognitive scaffolding and Bloom's taxonomy depth.",
            )

        objective = st.text_area(
            "Primary Learning Objective *",
            placeholder="e.g. Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
            height=100,
            help="Clear, measurable pedagogical goal (Bloom's taxonomy action verb recommended).",
        )

        col3, col4 = st.columns([2, 3])
        with col3:
            duration = st.slider(
                "Planned Duration (Minutes) *",
                min_value=15,
                max_value=45,
                value=45,
                step=5,
                help="Mandatory Kalvium constraint: total duration must not exceed 45 minutes.",
            )

        with col4:
            prereqs_str = st.text_input(
                "Prerequisites (Optional, comma-separated)",
                placeholder="e.g. Basic networking concepts, IP addresses",
                help="Prior knowledge assumed for this session.",
            )

        submitted = st.form_submit_button("🚀 Start Multi-Modal Research & Synthesis", type="primary", use_container_width=True)

    if submitted:
        # 1. Validation
        title_clean = title.strip()
        obj_clean = objective.strip()

        if len(title_clean) < 3:
            st.error("Validation Error: Lesson Title must be at least 3 characters long.")
            return

        if len(obj_clean) < 10:
            st.error("Validation Error: Learning Objective must be at least 10 characters long with measurable intent.")
            return

        prereqs = [p.strip() for p in prereqs_str.split(",") if p.strip()] if prereqs_str else []
        level = LearnerLevel(learner_level_str)

        try:
            lesson_input = LessonInput(
                title=title_clean,
                learning_objective=obj_clean,
                learner_level=level,
                prerequisites=prereqs,
                target_duration_minutes=duration,
            )
        except ValidationError as e:
            st.error(f"Validation Error: {e.message}")
            return

        # 2. Execution with Real-time Progress Tracking
        repo = get_repository()
        generator = LessonGenerator()

        status_container = st.status("⚡ Orchestrating multi-modal research & lesson generation...", expanded=True)
        with status_container:
            st.write("🔍 Initiating multi-modal research across Web, Google Books, Open Library, and YouTube...")
            research_engine = ResearchEngine()
            research_result = research_engine.research(title_clean)
            st.write(
                f"✅ Research completed: Discovered {len(research_result.web_sources)} web sources, "
                f"{len(research_result.book_sources)} books, and {len(research_result.youtube_sources)} verified videos."
            )

            st.write("📝 Synthesizing evidence-grounded lesson plan and budgeting time allocations...")
            gen_result = generator.generate(lesson_input, research_result)
            lesson_plan = gen_result.lesson_plan
            st.write(f"✅ Synthesis complete. Generation Mode: `{gen_result.generation_mode}`.")

            st.write("💾 Persisting lesson plan, version 1 snapshot, and research bibliography to SQLite...")
            repo.save_lesson(lesson_plan, author="RESEARCH_SYNTHESIZER", change_summary="Initial multi-modal synthesis")

            st.write("🛡️ Executing initial independent Dual Quality Control Audits...")
            auditor_qc1 = ResearchAuditor()
            auditor_qc2 = InstructionalAuditor()
            rep_qc1 = auditor_qc1.audit(lesson_plan)
            rep_qc2 = auditor_qc2.audit(lesson_plan)
            repo.save_qc_report(rep_qc1)
            repo.save_qc_report(rep_qc2)
            st.write(
                f"✅ Audits finished: QC1 (Factual Accuracy) = {rep_qc1.overall_score}/100, "
                f"QC2 (Instructional Quality) = {rep_qc2.overall_score}/100."
            )

            status_container.update(label="🎉 Lesson successfully synthesized and audited!", state="complete", expanded=False)

        # Set active and redirect to workspace
        set_active_lesson(lesson_plan.lesson_id, lesson_plan.version)
        notify(f"Successfully synthesized and saved '{lesson_plan.title}' (Version {lesson_plan.version})!", "success")
        st.session_state.current_page = "Lesson Workspace"
        st.rerun()
