"""
Lesson generation module for LessonForge AI.
Coordinates grounded technical curriculum synthesis, duration budgeting, and prompt engineering.
"""

from generation.lesson_generator import LessonGenerationResult, LessonGenerator
from generation.lesson_templates import allocate_time_budget, synthesize_deterministic_lesson
from generation.prompts import build_grounded_lesson_prompt

__all__ = [
    "LessonGenerator",
    "LessonGenerationResult",
    "build_grounded_lesson_prompt",
    "allocate_time_budget",
    "synthesize_deterministic_lesson",
]
