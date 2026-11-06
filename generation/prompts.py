"""
Prompt engineering and evidence-grounding templates for LessonForge AI.
Constructs strict instructional prompts binding technical claims directly to retrieved sources.
"""

from __future__ import annotations

import json
from core.schemas import LessonInput, ProvenanceStatus, ResearchSource
from research.research_engine import ResearchResult


SYSTEM_INSTRUCTION = """You are LessonForge AI, a Master Educational Architect and AI Curriculum Specialist.
Your mission is to synthesize rigorous, evidence-grounded, 45-minute technical lesson plans based on peer-reviewed research.

STRICT PEDAGOGICAL & GROUNDING CONSTRAINTS:
1. EVIDENCE GROUNDING: Every core technical statement and factual explanation MUST reference an available research source using its exact ID, e.g. [src_1].
2. ZERO HALLUCINATION: Never fabricate citations, URLs, author names, or standards. If evidence on a specific detail is absent, state explicitly that it requires further empirical verification.
3. BOOK INTEGRITY: If a book source is marked as metadata-only, do not simulate or pretend to cite unretrieved internal chapters.
4. YOUTUBE CITATION: Treat YouTube resources solely as supplementary visual media; do not claim to have watched unretrieved video contents.
5. TIME BUDGET INVARIANT: The total lesson delivery time MUST NOT exceed 45 minutes. The sum of all section durations plus the guided activity duration MUST EXACTLY equal the requested total duration.
6. BLOOM'S TAXONOMY PROGRESSION: Sequence instruction logically:
   - Recall & Orientation (Hook, 5 min)
   - Core Theoretical Foundations (10-15 min)
   - In-Depth Worked Technical Examples (10 min)
   - Practical Applications & Systems Context (5 min)
   - Active Hands-on Guided Activity / Lab (8-10 min)
   - Knowledge Checks & Formative Assessment (5 min)
   - Synthesis & Summary (5 min)
7. OUTPUT FORMAT: Output valid, parseable JSON conforming strictly to the requested schema.
"""


def build_grounded_lesson_prompt(
    lesson_input: LessonInput,
    research_result: ResearchResult,
) -> tuple[str, str]:
    """
    Construct user prompt containing research evidence, constraints, and JSON schema.
    Returns:
        tuple[str, str]: (user_prompt, system_instruction)
    """
    # Format research sources with provenance notes
    sources_text_lines = []
    for s in research_result.all_sources:
        meta_note = ""
        if s.metadata.get("metadata_only"):
            meta_note = " [Note: Metadata only retrieved; do not claim internal chapter access]"
        elif s.metadata.get("snippet_only"):
            meta_note = " [Note: Search snippet only; verify before deep citation]"

        sources_text_lines.append(
            f"- [{s.id}] ({s.source_type.value} | Provenance: {s.provenance.value}{meta_note})\n"
            f"  Title: {s.title}\n"
            f"  URL: {s.url}\n"
            f"  Author/Publisher: {s.authors_or_channel or 'N/A'}\n"
            f"  Excerpt: {s.snippet_or_summary.strip()}"
        )

    sources_block = "\n".join(sources_text_lines) if sources_text_lines else "No live research sources available."

    target_duration = lesson_input.target_duration_minutes

    prompt = f"""Synthesize a complete, structured, classroom-ready technical lesson plan based on the following specifications:

LESSON PARAMETERS:
- Title: {lesson_input.title}
- Learning Objective: {lesson_input.learning_objective}
- Learner Level: {lesson_input.learner_level.value}
- Prerequisites: {', '.join(lesson_input.prerequisites) if lesson_input.prerequisites else 'None specified'}
- Target Total Duration: {target_duration} minutes (STRICT: sum of sections + guided activity must equal {target_duration})

RETRIEVED RESEARCH EVIDENCE CORPUS:
{sources_block}

JSON SCHEMA REQUIREMENT:
Respond with a single JSON object matching this exact structure:
{{
  "lesson_id": "lesson_{lesson_input.title.lower().replace(' ', '_')[:20]}",
  "title": "{lesson_input.title}",
  "learning_objective": "{lesson_input.learning_objective}",
  "learner_level": "{lesson_input.learner_level.value}",
  "prerequisites": ["..."],
  "total_duration_minutes": {target_duration},
  "introduction": "Engaging hook introducing the relevance of the topic...",
  "learning_outcomes": [
    "Outcome 1 using action verb (e.g. Differentiate, Analyze)",
    "Outcome 2 using action verb"
  ],
  "sections": [
    {{
      "section_id": "sec_1",
      "title": "Section Title",
      "duration_minutes": 10,
      "cognitive_focus": "Conceptual Foundation",
      "content_markdown": "In-depth explanation citing research [source_id]...",
      "citations": ["source_id"]
    }}
  ],
  "guided_activity": {{
    "title": "Hands-on Lab Title",
    "duration_minutes": 10,
    "instructions": "Step-by-step terminal or coding instructions...",
    "deliverable": "Specific tangible artifact expected from student...",
    "evaluation_criteria": ["Criterion 1", "Criterion 2"]
  }},
  "knowledge_checks": [
    {{
      "id": "kc_1",
      "question": "Rigorous multiple-choice question testing understanding...",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A text",
      "explanation": "Detailed pedagogical explanation referencing RFC/standard..."
    }}
  ],
  "summary": "Key takeaways summarizing GET/POST or topic foundations..."
}}
"""
    return prompt, SYSTEM_INSTRUCTION
