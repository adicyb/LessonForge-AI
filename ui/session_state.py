"""
Session state management and repository accessor for LessonForge AI.
Handles state persistence across Streamlit reruns, active lesson tracking,
version selection, and error message dispatching.
"""

from __future__ import annotations

import streamlit as st
from typing import Optional, List, Dict, Any

from core.schemas import LessonPlan
from storage.database import DatabaseManager
from storage.lesson_repository import LessonRepository


@st.cache_resource
def get_database_manager() -> DatabaseManager:
    """Singleton DatabaseManager instance cached across Streamlit reruns."""
    return DatabaseManager()


@st.cache_resource
def get_repository() -> LessonRepository:
    """Singleton LessonRepository instance cached across Streamlit reruns."""
    db = get_database_manager()
    return LessonRepository(db=db)


def init_session_state() -> None:
    """Initialize default session state keys if not present."""
    if "active_lesson_id" not in st.session_state:
        st.session_state.active_lesson_id = None

    if "active_version" not in st.session_state:
        st.session_state.active_version = None

    if "current_page" not in st.session_state:
        st.session_state.current_page = "Dashboard"

    if "feedback_message" not in st.session_state:
        st.session_state.feedback_message = None

    if "feedback_type" not in st.session_state:
        st.session_state.feedback_type = "info"


def set_active_lesson(lesson_id: str, version: Optional[int] = None) -> None:
    """Set the active lesson ID and optionally an explicit version."""
    st.session_state.active_lesson_id = lesson_id
    st.session_state.active_version = version


def get_active_lesson() -> Optional[LessonPlan]:
    """
    Retrieve the active LessonPlan instance from storage.
    If active_version is specified, retrieves that specific historical snapshot;
    otherwise retrieves the current latest version.
    """
    lesson_id = st.session_state.get("active_lesson_id")
    if not lesson_id:
        return None

    repo = get_repository()
    version = st.session_state.get("active_version")

    if version is not None:
        lesson = repo.get_lesson_version(lesson_id, version_number=version)
        if lesson is not None:
            return lesson

    # Default to current active version
    return repo.get_lesson(lesson_id)


def notify(message: str, type_: str = "info") -> None:
    """Set a user feedback message to display on the next render."""
    st.session_state.feedback_message = message
    st.session_state.feedback_type = type_


def display_feedback() -> None:
    """Display and clear any pending user notification."""
    msg = st.session_state.get("feedback_message")
    type_ = st.session_state.get("feedback_type", "info")
    if msg:
        if type_ == "success":
            st.success(msg)
        elif type_ == "error":
            st.error(msg)
        elif type_ == "warning":
            st.warning(msg)
        else:
            st.info(msg)
        st.session_state.feedback_message = None
