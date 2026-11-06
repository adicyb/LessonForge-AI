# LessonForge AI — Requirements Traceability & Verification Matrix

> **Project**: LessonForge AI — Research-Driven Lesson Creation Platform  
> **Assignment**: Kalvium AI Research Intern Hiring Assignment  
> **Status**: Baseline Approved / Implementation Ready  
> **Version**: 1.0.0  

---

## 1. Executive Summary & Purpose

LessonForge AI is an enterprise-grade, research-grounded educational engineering platform designed to automate and elevate the authoring of university-level and vocational technical lessons. Given an input **Lesson Title** and **Learning Objective**, LessonForge AI coordinates automated literature and media research across three distinct external modalities (Web, Books, YouTube), synthesizes structured 45-minute classroom-ready learning experiences, and enforces rigorous quality standards through **two independent Quality Control (QC) auditing layers**.

---

## 2. Requirements Traceability Matrix

| Req ID | Category | Requirement Description | Assignment Source | Planned Implementation Module | Verification Method | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **REQ-INP-01** | Inputs | Accept Lesson Title and Learning Objective as primary user inputs | Assignment Section 1 | `core/schemas.py`, `ui/pages/create.py` | UI validation & Unit test | PENDING |
| **REQ-INP-02** | Inputs | Accept Learner Level (Beginner, Intermediate, Advanced) and optional prerequisites | Prompt Section 6 | `core/schemas.py`, `ui/pages/create.py` | Schema validation test | PENDING |
| **REQ-INP-03** | Constraints | Total lesson content must strictly fit within a 45-minute delivery window | Assignment Section 1 | `core/schemas.py`, `generation/lesson_generator.py` | Duration summation test (sum == 45) | PENDING |
| **REQ-INP-04** | Validation | Empty inputs or malformed inputs must be rejected with helpful error feedback | Assignment Section 4 | `core/schemas.py`, `ui/components.py` | Edge case validation tests | PENDING |
| **REQ-RES-01** | Research | Multi-source discovery across Websites (DDGS), Books (Google Books / Open Library), and YouTube | Assignment Section 1, Prompt Section 5 | `research/research_engine.py`, `research/*` | Live & Mocked integration tests | PENDING |
| **REQ-RES-02** | Research | Web discovery capturing Title, URL, Snippet, Credibility Score, Retrieval Timestamp without duplicates | Prompt Section 5.A | `research/web_research.py` | Unit tests on deduplication & schemas | PENDING |
| **REQ-RES-03** | Research | Book discovery capturing Title, Authors, Publisher, Year, ISBN/URL; strictly no fabricated chapter contents | Prompt Section 5.B | `research/book_research.py` | Unit test with Google Books / Open Library | PENDING |
| **REQ-RES-04** | Research | YouTube discovery capturing Title, Channel, Video URL, Duration; strictly verified URLs | Prompt Section 5.C | `research/youtube_research.py` | Unit test verifying valid video links | PENDING |
| **REQ-RES-05** | Research | Transparent provenance: explicit differentiation between discovered, retrieved, and verified sources | Prompt Section 5 | `research/source_validator.py` | Audit metadata verification test | PENDING |
| **REQ-RES-06** | Research | Graceful fallbacks: resilience against network dropouts, rate limits, and provider downtimes | Prompt Section 5, 11 | `research/research_engine.py` | Network error simulation tests | PENDING |
| **REQ-GEN-01** | Generation | Structured lesson output: Intro, Outcomes, Prerequisites, Timed Agenda, Concepts, Worked Examples, Practical Applications, Guided Activity, Knowledge Checks + Answers, Summary | Assignment Section 1, Prompt Section 6 | `generation/lesson_generator.py`, `core/schemas.py` | Pydantic validation & structure test | PENDING |
| **REQ-GEN-02** | Generation | Timed agenda: explicit duration per section whose sum equals the requested lesson duration (<= 45 mins) | Assignment Section 1, Prompt Section 6 | `generation/lesson_generator.py` | Assertion tests on agenda total | PENDING |
| **REQ-GEN-03** | Generation | Strict factual grounding: factual claims bound to retrieved research without hallucinated citations | Prompt Section 6, 14 | `generation/lesson_generator.py`, `prompts.py` | Citation grounding test | PENDING |
| **REQ-GEN-04** | Generation | Integration of relevant YouTube resources and formatted academic/technical reference bibliography | Assignment Section 1 | `generation/lesson_generator.py` | Content presence check | PENDING |
| **REQ-QC1-01** | QC Layer 1 | Independent Research & Factual Accuracy Audit (isolated evaluator & criteria) | Assignment Section 2, Prompt Section 7 | `quality_control/research_auditor.py` | Layer isolation test | PENDING |
| **REQ-QC1-02** | QC Layer 1 | Evaluate claim-to-source support, factual correctness, source credibility, misleading statements, contradictions, research gaps | Prompt Section 7 | `quality_control/research_auditor.py` | Audit evaluation test | PENDING |
| **REQ-QC1-03** | QC Layer 1 | Generate structured report: Score (0-100), Critical/Major/Minor issues, evidence quotes, remediation suggestions, source reliability ratings | Assignment Section 2, Prompt Section 7 | `quality_control/qc_schemas.py` | Schema & score bounds test | PENDING |
| **REQ-QC1-04** | QC Layer 1 | Unverified claim reporting: if evidence is absent, explicitly flag as "unverified" rather than assuming truth | Prompt Section 7 | `quality_control/research_auditor.py` | Negative test with ungrounded claim | PENDING |
| **REQ-QC2-01** | QC Layer 2 | Independent Instructional Quality Audit (separate evaluator, zero overlap with factual QC) | Assignment Section 2, Prompt Section 8 | `quality_control/instructional_auditor.py` | Evaluator independence test | PENDING |
| **REQ-QC2-02** | QC Layer 2 | Evaluate objective alignment, cognitive load/pacing, clarity, pedagogical progression, example quality, activity effectiveness, knowledge-check rigor | Prompt Section 8 | `quality_control/instructional_auditor.py` | Pedagogical evaluation test | PENDING |
| **REQ-QC2-03** | QC Layer 2 | Generate structured report: Score (0-100), criterion-level rubric marks, missing components, actionable improvement recommendations | Assignment Section 2, Prompt Section 8 | `quality_control/qc_schemas.py` | Schema & score bounds test | PENDING |
| **REQ-REC-01** | Recommendations | Granular recommendation review: list individual findings from both QC layers with severity badges | Assignment Section 3, Prompt Section 9 | `quality_control/recommendation_engine.py`, `ui/pages/` | UI interaction & unit test | PENDING |
| **REQ-REC-02** | Recommendations | Instructor decision control: Accept, Reject, or Modify recommendations individually or in batches | Assignment Section 3, Prompt Section 9 | `quality_control/recommendation_engine.py` | State transition test | PENDING |
| **REQ-REC-03** | Recommendations | Automated & semi-automated application of accepted recommendations to create revised lesson drafts | Assignment Section 3, Prompt Section 9 | `quality_control/recommendation_engine.py` | Patch application test | PENDING |
| **REQ-REC-04** | Recommendations | Non-destructive revision: preserve original draft, support side-by-side diff comparison, allow re-running QC | Prompt Section 9 | `storage/lesson_repository.py`, `ui/components.py` | Version preservation test | PENDING |
| **REQ-EDT-01** | Editing | Full instructor editing suite for all lesson sections with rich Markdown editor | Assignment Section 3, Prompt Section 10 | `ui/pages/editor.py` | State persistence test | PENDING |
| **REQ-EDT-02** | Editing | Final lesson preview with interactive tabbed navigation and classroom presentation mode | Assignment Section 3, Prompt Section 10 | `ui/pages/preview.py` | UI rendering test | PENDING |
| **REQ-EXP-01** | Export | Professional PDF export with custom typography, headers, footers, metadata, and lesson structure | Assignment Section 3, Prompt Section 12 | `export/pdf_exporter.py` | PDF generation test | PENDING |
| **REQ-EXP-02** | Export | Clean GitHub-flavored Markdown export of complete lesson and research bibliography | Assignment Section 3, Prompt Section 12 | `export/markdown_exporter.py` | Markdown generation test | PENDING |
| **REQ-EXP-03** | Export | Independent exportable audit reports for QC Layer 1 (Factual) and QC Layer 2 (Instructional) in PDF & MD | Assignment Section 3, Prompt Section 12 | `export/pdf_exporter.py`, `export/markdown_exporter.py` | QC export validation test | PENDING |
| **REQ-STO-01** | Persistence | SQLite database storage capturing inputs, lessons, references, QC audits, edits, and timestamps | Prompt Section 11 | `storage/database.py`, `storage/lesson_repository.py` | Database CRUD tests | PENDING |
| **REQ-STO-02** | Persistence | Auto-save and state preservation: instructor edits never lost across page reloads or failed operations | Assignment Section 4, Prompt Section 11 | `storage/lesson_repository.py`, `app.py` | Session restoration test | PENDING |
| **REQ-ERR-01** | Reliability | Robust error boundaries: catch network, API, rate limit, and format errors with actionable UI alerts | Assignment Section 4, Prompt Section 11 | `core/exceptions.py`, `ui/components.py` | Error injection tests | PENDING |
| **REQ-ERR-02** | Reliability | Retry mechanics: allow retrying failed research, generation, or QC steps without restarting from scratch | Assignment Section 4, Prompt Section 11 | `core/orchestrator.py`, `ui/components.py` | Step retry test | PENDING |
| **REQ-LLM-01** | Architecture | Interchangeable LLM Provider abstraction supporting OpenAI, Anthropic, Gemini, Groq, Ollama, and Fallback Mock | Prompt Section 3, 14 | `core/llm_provider.py` | Multi-provider unit tests | PENDING |
| **REQ-LLM-02** | Architecture | Deterministic, high-fidelity offline fallback mode enabling complete end-to-end operation without API keys | Prompt Section 3 | `core/llm_provider.py`, `research/fallback_engine.py` | Zero-API-key end-to-end test | PENDING |
| **REQ-TST-01** | Verification | Mandatory Test Case 1: "HTTP Requests and Responses" (GET/POST, 2xx, 4xx, 5xx status codes) | Assignment "Sample Inputs", Prompt Section 13 | `tests/test_benchmark_http.py` | E2E integration test | PENDING |
| **REQ-TST-02** | Verification | Mandatory Test Case 2: "DNS Resolution and DNS Record Types" (Recursive resolution, A, AAAA, CNAME, MX) | Prompt Section 13 | `tests/test_benchmark_dns.py` | E2E integration test | PENDING |

---

## 3. Evaluation Criteria Cross-Reference

1. **Workflow Functionality & Technical Implementation**: Modular, decoupled components, typed contracts, multi-threaded or resilient async research, atomic database persistence.
2. **Research Quality & Factual Accuracy**: Multi-modal discovery (Web + Books + YouTube), verified URLs, publisher information, zero hallucinated citations.
3. **Effectiveness of Both QC Layers**: Distinct agents/evaluators with independent prompt engineering and separate scoring rubrics (Research Verification vs Pedagogical Efficacy).
4. **Instructional Quality & Learning Objective Alignment**: Bloom's taxonomy pacing, cognitive load management, active learning integration, exact 45-minute agenda fit.
5. **Problem-Solving Approach & Technical Decisions**: Documented in `docs/ARCHITECTURE.md` and `docs/DESIGN_DECISIONS.md`.
