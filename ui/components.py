"""
Reusable UI components, executive styling, and custom CSS for LessonForge AI.
Provides dark navy/charcoal styling, status badges, metric cards, and diff viewers.
"""

from __future__ import annotations

import difflib
import html
import streamlit as st
from typing import Any, Optional


def inject_custom_css() -> None:
    """Inject premium dark executive styling with cyan/violet accents."""
    custom_css = """
    <style>
    /* Global Background and Typography */
    .stApp {
        background-color: #0B132B;
        color: #E2E8F0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0A0F1D;
        border-right: 1px solid #1E293B;
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #F8FAFC !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }

    /* Custom Header Banner */
    .app-header-container {
        padding: 1.5rem 1.75rem;
        background: linear-gradient(135deg, #0F172A 0%, #1E1B4B 100%);
        border: 1px solid #312E81;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.4);
    }

    .app-header-title {
        font-size: 1.85rem;
        font-weight: 800;
        color: #F8FAFC;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .app-header-tagline {
        color: #38BDF8;
        font-size: 0.95rem;
        font-weight: 500;
        margin-top: 0.35rem;
    }

    /* Cards and Containers */
    .forge-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }

    .forge-card-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #38BDF8;
        margin-bottom: 0.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Metrics Card */
    .forge-metric-box {
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
    }

    .forge-metric-value {
        font-size: 1.75rem;
        font-weight: 800;
        color: #38BDF8;
        line-height: 1.2;
    }

    .forge-metric-label {
        font-size: 0.8rem;
        color: #94A3B8;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.05em;
        margin-top: 0.25rem;
    }

    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.75rem;
        font-weight: 700;
        border-radius: 9999px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .badge-passed {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid #059669;
    }

    .badge-revision {
        background-color: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid #D97706;
    }

    .badge-failed {
        background-color: rgba(239, 68, 68, 0.15);
        color: #F87171;
        border: 1px solid #DC2626;
    }

    .badge-discovered {
        background-color: rgba(59, 130, 246, 0.15);
        color: #93C5FD;
        border: 1px solid #2563EB;
    }

    .badge-retrieved {
        background-color: rgba(139, 92, 246, 0.15);
        color: #C4B5FD;
        border: 1px solid #7C3AED;
    }

    .badge-verified {
        background-color: rgba(20, 184, 166, 0.15);
        color: #5EEAD4;
        border: 1px solid #0D9488;
    }

    /* Code Diff Styling */
    .diff-container {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.82rem;
        background-color: #0A0F1D;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 0.75rem;
        overflow-x: auto;
    }

    .diff-del {
        background-color: rgba(239, 68, 68, 0.2);
        color: #FCA5A5;
        display: block;
        padding: 0.1rem 0.4rem;
        border-left: 3px solid #EF4444;
    }

    .diff-add {
        background-color: rgba(16, 185, 129, 0.2);
        color: #6EE7B7;
        display: block;
        padding: 0.1rem 0.4rem;
        border-left: 3px solid #10B981;
    }

    .diff-neutral {
        color: #94A3B8;
        display: block;
        padding: 0.1rem 0.4rem;
    }

    /* Streamlit Input Overrides */
    div[data-baseweb="input"], div[data-baseweb="textarea"] {
        background-color: #0F172A !important;
        border-color: #334155 !important;
        color: #F8FAFC !important;
    }

    /* Button Styling */
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton>button:hover {
        border-color: #38BDF8 !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.2);
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def render_app_header() -> None:
    """Render application branding banner."""
    html_code = """
    <div class="app-header-container">
        <div class="app-header-title">
            <span>⚡ LessonForge AI</span>
        </div>
        <div class="app-header-tagline">
            From research to classroom-ready learning &nbsp;&bull;&nbsp; Dual-Layer Research & Instructional QC Workspace
        </div>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


def render_metric_card(label: str, value: Any, subtext: Optional[str] = None) -> None:
    """Render a styled numerical metric card."""
    sub_html = f"<div style='font-size: 0.75rem; color: #64748B; margin-top: 2px;'>{subtext}</div>" if subtext else ""
    html_code = f"""
    <div class="forge-metric-box">
        <div class="forge-metric-value">{value}</div>
        <div class="forge-metric-label">{label}</div>
        {sub_html}
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


def get_status_badge(status: str) -> str:
    """Return HTML badge for audit determinations."""
    status_upper = str(status).upper()
    if status_upper in ("PASSED", "PASS"):
        return '<span class="badge badge-passed">PASSED</span>'
    elif status_upper in ("NEEDS_REVISION", "WARN", "WARNING"):
        return '<span class="badge badge-revision">NEEDS REVISION</span>'
    elif status_upper in ("FAILED", "FAIL", "CRITICAL"):
        return '<span class="badge badge-failed">FAILED</span>'
    else:
        return f'<span class="badge">{status}</span>'


def get_provenance_badge(status: str) -> str:
    """Return HTML badge for research provenance status."""
    st_upper = str(status).upper()
    if "VERIFIED" in st_upper:
        return '<span class="badge badge-verified">VERIFIED</span>'
    elif "RETRIEVED" in st_upper:
        return '<span class="badge badge-retrieved">RETRIEVED</span>'
    elif "DISCOVERED" in st_upper:
        return '<span class="badge badge-discovered">DISCOVERED</span>'
    else:
        return f'<span class="badge">{status}</span>'


def render_diff_viewer(before: str, after: str) -> None:
    """Render a visual side-by-side or unified colored diff."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = list(difflib.ndiff(before_lines, after_lines))

    html_lines = ["<div class='diff-container'>"]
    for line in diff:
        escaped = html.escape(line.rstrip("\n"))
        if line.startswith("- "):
            html_lines.append(f"<span class='diff-del'>{escaped}</span>")
        elif line.startswith("+ "):
            html_lines.append(f"<span class='diff-add'>{escaped}</span>")
        elif line.startswith("? "):
            continue
        else:
            html_lines.append(f"<span class='diff-neutral'>{escaped}</span>")
    html_lines.append("</div>")

    st.markdown("\n".join(html_lines), unsafe_allow_html=True)
