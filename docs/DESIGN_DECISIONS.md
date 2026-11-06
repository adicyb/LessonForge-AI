# LessonForge AI — Key Engineering Decisions & Trade-Offs

> **Document**: Architectural Decision Records (ADRs)  
> **Status**: Approved  
> **Audience**: AI Research Engineers, Technical Evaluators, System Architects  

---

## Decision 1: Dual-Auditor Quality Control Architecture

### Context
Educational AI systems frequently suffer from hallucinations, vague explanations, and misalignment with stated learning objectives. A single evaluation prompt that tries to check both factual accuracy and pedagogical quality suffers from prompt dilution and confirmation bias (evaluating its own generated work leniently).

### Decision
We decoupled the audit phase into two **completely independent evaluators**:
1. **Research & Factual Accuracy Auditor**: Role-specialized as a strict fact-checker. It extracts atomic technical claims from the lesson and verifies each claim against the retrieved research corpus (Web snippets, Book metadata, RFCs/Standards). It flags unsupported claims, missing citations, and factual discrepancies.
2. **Instructional Quality Auditor**: Role-specialized as a university curriculum designer. It is prohibited from checking factual claims; instead, it evaluates the lesson solely against pedagogical standards: Bloom's taxonomy alignment, cognitive scaffolding, clarity of explanations, worked example quality, hands-on lab viability, and time allocation.

### Trade-offs & Mitigations
- *Trade-off*: Requires two evaluation passes instead of one, slightly increasing compute time.
- *Mitigation*: The audits are decoupled and can execute concurrently or independently, and either can be re-run in isolation when an instructor edits specific sections.

---

## Decision 2: Pluggable Multi-Provider LLM Engine with Zero-API-Key Fallback

### Context
The platform must support enterprise LLMs (Gemini, OpenAI, Anthropic, Groq, Ollama) while guaranteeing that an evaluator running the system locally without any paid API credentials can experience the full workflow without crashes or mock placeholders.

### Decision
We implemented a provider abstraction (`core/llm_provider.py`) with a factory pattern:
- Detects available API keys in environment or Streamlit UI settings (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`).
- When no API key is present, the system defaults to the **Deterministic High-Fidelity Research & Generation Engine**.
- The fallback engine performs **real live external search** (DuckDuckGo, Google Books, Open Library, YouTube), extracts real sources, and performs rigorous grounded synthesis and auditing for the target topics (including the mandatory HTTP Requests and DNS Resolution benchmarks).
- The UI transparently indicates whether an active cloud LLM provider or the local high-fidelity engine is active.

### Trade-offs & Mitigations
- *Trade-off*: Need to maintain both provider interfaces and structured fallback generators.
- *Mitigation*: Both paths return identical Pydantic `LessonPlan` and `QCReport` models, ensuring downstream components (UI, Editor, Exporter, Database) behave identically.

---

## Decision 3: Research Discovery Without Restricted API Keys

### Context
Obtaining official YouTube Data API v3 keys or paid search engine keys (Google Custom Search, Bing) creates high onboarding friction for evaluators and requires payment credentials.

### Decision
1. **Web Search**: Implemented via `duckduckgo-search` (`ddgs`), delivering real-time web results, snippets, and URLs with domain filtering (prioritizing MDN, RFCs, official specifications).
2. **Book Search**: Implemented via the public Google Books REST API (`https://www.googleapis.com/books/v1/volumes`) and Open Library API (`https://openlibrary.org/search.json`), which are freely accessible without authentication.
3. **YouTube Search**: Implemented via DuckDuckGo video discovery and verified YouTube search scrapers, extracting valid video IDs, titles, channels, and verified watch links (`https://www.youtube.com/watch?v=...`).

### Integrity Rule
We strictly enforce provenance: Sources are categorized as `DISCOVERED`, `RETRIEVED`, or `VERIFIED`. The system never fabricates book chapters, fake citations, or dead YouTube URLs.

---

## Decision 4: Strict 45-Minute Lesson Duration Budgeting

### Context
The assignment mandate states: *"The complete lesson should be designed to be consumed within 45 minutes, either through self-learning or instructor-led teaching."*

### Decision
We designed a time-budgeting schema in Pydantic:
- Every lesson has a `timed_agenda` array where each module (Hook, Foundations, Worked Examples, Application, Guided Lab, Knowledge Checks, Summary) has an explicit `duration_minutes` integer.
- A model validator asserts:
  $$\sum \text{duration\_minutes} = 45$$
- The generator prompt is explicitly instructed to allocate time according to cognitive load theory (e.g., maximum 12 minutes on dense conceptual theory before transitioning into active worked examples).

---

## Decision 5: Non-Destructive Instructor Editing and Recommendation Patching

### Context
Instructors must have complete authority over lesson content. Applying AI recommendations must never overwrite instructor revisions or cause unrecoverable loss of work.

### Decision
- **SQLite Database with Versioning**: Each lesson maintains an immutable history of revisions (`v1` AI draft, `v2` patched, `v3` instructor edited).
- **Atomic Recommendation Lifecycle**: Every recommendation has a state machine: `PENDING` $\rightarrow$ `ACCEPTED` / `REJECTED` $\rightarrow$ `APPLIED`.
- **Side-by-Side Diffing**: Before and after states are clearly displayed, highlighting additions and deletions.
- **Isolated Re-Audit**: After modifications, the instructor can re-run either QC Layer 1 or QC Layer 2 individually to observe score changes.

---

## Decision 6: ReportLab for PDF Export over Web Headless Browsers

### Context
Exporting PDFs via WeasyPrint or headless Chrome/Puppeteer requires heavy system dependencies (`libcairo`, `libpango`, Chromium binaries) that often fail in minimal Python environments or Docker containers.

### Decision
We selected **ReportLab**, a pure-Python library with zero binary dependencies:
- Enables precise coordinate control, custom flowables, running headers/footers with dynamic page numbering ("Page X of Y"), and clean typography.
- Renders tables for the 45-minute timed agenda, callout boxes for hands-on activities, and distinct appendices for QC 1 and QC 2 audit certificates.
