"""
Research Sources & Provenance Studio for LessonForge AI.
Displays multi-modal citations, calculated credibility indices,
retrieved evidence excerpts, and provenance verification status.
"""

from __future__ import annotations

import streamlit as st

from ui.components import get_provenance_badge, render_metric_card
from ui.session_state import get_active_lesson, get_repository


def render_research_sources() -> None:
    """Render the research bibliography and evidence provenance view."""
    active_lesson = get_active_lesson()
    repo = get_repository()

    if active_lesson is None:
        st.warning("No active lesson selected. Please select a lesson from the Dashboard or create a new one.")
        return

    st.markdown(f"## 🔬 Research Provenance & Citations: {active_lesson.title}")
    st.markdown(
        "Every claim synthesized in LessonForge AI is grounded in multi-modal external evidence. "
        "Research provenance explicitly differentiates discovery from full retrieval and empirical verification."
    )

    # Explanation Callout
    with st.expander("ℹ️ Understanding Research Provenance Semantics", expanded=False):
        st.markdown(
            """
            - **`DISCOVERED`**: Search index or catalogue hit. Query metadata or snippet captured; full text not inspected.
            - **`RETRIEVED`**: Full technical documentation, standard specification, or book metadata fetched and parsed.
            - **`VERIFIED`**: Empirical proposition corroborated by an independent authoritative standard (e.g. IETF RFC, W3C, IEEE).
            *HTTP 200 reachability alone never constitutes factual verification.*
            """
        )

    sources = repo.get_research_sources(active_lesson.lesson_id)
    if not sources and active_lesson.references:
        sources = active_lesson.references

    if not sources:
        st.info("No research sources recorded for this lesson.")
        return

    # Metric Cards
    total_sources = len(sources)
    verified_count = sum(1 for s in sources if s.provenance.value == "VERIFIED")
    retrieved_count = sum(1 for s in sources if s.provenance.value == "RETRIEVED")
    avg_cred = round(sum(s.credibility_score for s in sources) / total_sources * 100, 1)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Total Citations", total_sources, "Multi-Modal")
    with c2:
        render_metric_card("Verified Sources", verified_count, "Authoritative RFC / Peer-Reviewed")
    with c3:
        render_metric_card("Retrieved Sources", retrieved_count, "Full Metadata Fetched")
    with c4:
        render_metric_card("Avg Credibility", f"{avg_cred}%", "Weighted Authority Index")

    st.markdown("---")

    # Filter Controls
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        type_filter = st.multiselect(
            "Filter by Source Type",
            options=["WEB", "BOOK", "YOUTUBE"],
            default=["WEB", "BOOK", "YOUTUBE"],
        )
    with f_col2:
        prov_filter = st.multiselect(
            "Filter by Provenance Status",
            options=["VERIFIED", "RETRIEVED", "DISCOVERED"],
            default=["VERIFIED", "RETRIEVED", "DISCOVERED"],
        )

    filtered_sources = [
        s for s in sources
        if s.source_type.value in type_filter and s.provenance.value in prov_filter
    ]

    st.markdown(f"### 📚 Authoritative Bibliography ({len(filtered_sources)} Sources)")

    for src in filtered_sources:
        with st.container():
            col_info, col_cred = st.columns([5, 2])

            with col_info:
                prov_badge = get_provenance_badge(src.provenance.value)
                st.markdown(
                    f"**{src.title}** &nbsp;`{src.id}` &nbsp; {prov_badge} &nbsp; "
                    f"<span style='font-size:0.8rem; color:#94A3B8;'>[{src.source_type.value}]</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"🔗 [{src.url}]({src.url})")

                if src.authors_or_channel:
                    st.caption(f"Author / Channel: **{src.authors_or_channel}** | Retrieved: **{src.retrieval_date}**")

                # Evidence Text
                if src.snippet_or_summary:
                    st.markdown(
                        f"<div style='background:#111827; border-left:3px solid #0D9488; padding:0.5rem 0.75rem; font-size:0.85rem; color:#E2E8F0; margin:0.5rem 0;'>"
                        f"<b>Retrieved Evidence / Abstract:</b><br/>{src.snippet_or_summary}</div>",
                        unsafe_allow_html=True,
                    )

            with col_cred:
                st.markdown(f"<div style='text-align:right; font-weight:700; color:#38BDF8;'>Authority: {round(src.credibility_score*100)}%</div>", unsafe_allow_html=True)
                st.progress(src.credibility_score)
                relevance = src.metadata.get("relevance_score", 0.8)
                st.caption(f"Relevance Score: {round(float(relevance)*100)}%")
                if "isbn" in src.metadata:
                    st.caption(f"ISBN: `{src.metadata['isbn']}`")
                if "duration" in src.metadata:
                    st.caption(f"Duration: `{src.metadata['duration']}`")

            st.markdown("<hr style='margin: 0.5rem 0; border-color: #1E293B;'/>", unsafe_allow_html=True)
