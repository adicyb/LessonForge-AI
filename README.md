# ⚡ LessonForge AI

> **From research to classroom-ready learning.**  
> *A Research-Driven, Evidence-Grounded AI Pedagogical Studio with Independent Dual-Layer Quality Control.*  
> *Submission deliverable for the Kalvium AI Research Intern Hiring Assignment.*

---

## 📌 Executive Overview

**LessonForge AI** bridges the divide between unstructured external literature and classroom delivery. It automatically searches across **Web Standards**, **Academic Books**, and **Educational Videos**, grounding every synthesized technical claim in verifiable citations. It guarantees that generated lesson plans fit strictly within a **45-minute delivery ceiling**, subjects all content to **two decoupled, independent Quality Control (QC) audits**, and provides a version-controlled workspace for instructor review, recommendation patching, and multi-format publishing.

---

## 🏛️ System Architecture

```
                                    +-----------------------------------------+
                                    |        Streamlit User Workspace         |
                                    | (Dashboard, Editor, QC Hub, Export, UI) |
                                    +-----------------------------------------+
                                                         |
                                                         v
                                    +-----------------------------------------+
                                    |       Orchestrator & Domain Core        |
                                    |   (LessonGenerator, Duration Budget)    |
                                    +-----------------------------------------+
                                      /                  |                  \
                                     /                   |                   \
                                    v                    v                    v
                   +-------------------+   +--------------------+   +-------------------+
                   | Multi-Modal       |   | Dual Independent   |   | Multi-Format      |
                   | Research Engine   |   | Quality Control    |   | Export Engine     |
                   | - DuckDuckGo Web  |   | - QC1 Factual      |   | - ReportLab PDF   |
                   | - Google Books    |   | - QC2 Pedagogy     |   | - GFM Markdown    |
                   | - Open Library    |   | - Patch Engine     |   | - NumberedCanvas  |
                   | - YouTube Video   |   +--------------------+   +-------------------+
                   | - Curated Fallback|             |                        |
                   +-------------------+             |                        |
                                      \              v                       /
                                     +-----------------------------------------+
                                     |        SQLite Persistence Layer         |
                                     | (WAL Mode, FK Cascades, Version Snapshots|
                                     +-----------------------------------------+
```

### Key Architectural Tenets
1. **Duration Invariant**: $\sum \text{section durations} + \text{guided activity} = \text{total\_duration} \le 45 \text{ minutes}$.
2. **Dual Independent QC Layers**:
   - **QC Layer 1 (Research & Factual Accuracy)**: Evaluates claim-to-source traceability, citation authenticity, and standard compliance (e.g. RFC 9110, RFC 1034). Critical contradictions cap scores at $\le 74.0$ (`NEEDS_REVISION`).
   - **QC Layer 2 (Instructional Quality)**: Evaluates Bloom's taxonomy progression, worked examples, hands-on lab rigor, knowledge-check validity, and cognitive load ($\le 20$m/sec). Strictly isolated from QC1.
3. **Non-Destructive Patch Engine**: Applying instructor recommendations performs **true text replacement**, creates an immutable new lesson version ($v \rightarrow v+1$), and preserves the original draft unmutated in database history.
4. **Zero-API Resilience**: Automatically operates with Google Gemini when credentials are provided, or seamlessly switches to deterministic academic synthesis when offline, with complete provenance disclosures.

---

## 📂 Repository Directory Structure

```
LessonForge-AI/
├── app.py                         # Streamlit application entrypoint & workspace router
├── config.py                      # Application configuration, environment & path resolution
├── requirements.txt               # Locked production dependencies
├── .env.example                   # Environment configuration template
│
├── core/                          # Domain schemas, exceptions & LLM providers
│   ├── exceptions.py              # Typed domain exception hierarchy
│   ├── schemas.py                 # Pydantic v2 models (LessonPlan, ResearchSource, QCReport)
│   └── llm_provider.py            # LLM abstraction (Gemini REST API & Offline Deterministic)
│
├── research/                      # Multi-modal research engine
│   ├── research_engine.py         # Multi-modal coordinator (Web, Books, YouTube)
│   ├── web_research.py            # DuckDuckGo standard web researcher
│   ├── book_research.py           # Google Books & Open Library failover integration
│   ├── youtube_research.py        # Validated YouTube video discovery & duration parsing
│   ├── source_validator.py        # URL normalization, deduplication & authority scoring
│   └── fallback_engine.py         # Curated peer-reviewed fallback datasets (HTTP & DNS)
│
├── generation/                    # Grounded pedagogical synthesis
│   ├── lesson_generator.py        # Synthesis orchestrator enforcing 45-min duration invariants
│   ├── lesson_templates.py        # Benchmark synthesis engines (HTTP Requests & DNS Resolution)
│   └── prompts.py                 # Grounded synthesis prompts with citation constraints
│
├── quality_control/               # Independent dual-layer audit engines
│   ├── qc_schemas.py              # AtomicClaim, ClaimSupportStatus, DetailedQCReport, DiffItem
│   ├── research_auditor.py        # QC Layer 1: Research & factual veracity auditor
│   ├── instructional_auditor.py   # QC Layer 2: Pedagogical & curriculum efficacy auditor
│   └── recommendation_engine.py   # Instructor recommendation review & non-destructive patcher
│
├── storage/                       # SQLite relational persistence layer
│   ├── database.py                # DatabaseManager (WAL mode, FK pragmas, atomic transactions)
│   └── lesson_repository.py       # Entity repository (Lessons, Versions, Sources, QC, Decisions)
│
├── export/                        # Multi-format publication engine
│   ├── export_service.py          # Unified service coordinating exports & version traceability
│   ├── markdown_exporter.py       # GitHub Flavored Markdown exporter with GFM tables
│   └── pdf_exporter.py            # ReportLab vector PDF engine with two-pass NumberedCanvas
│
├── ui/                            # Streamlit user interface
│   ├── components.py              # Executive dark styling, metric cards, badges, diff viewers
│   ├── session_state.py           # Cached repository access, active lesson state, toasts
│   └── pages/                     # Dedicated workspace views
│       ├── dashboard.py           # Overview, quick benchmark loaders, repository metrics
│       ├── create_lesson.py       # Interactive research and synthesis studio
│       ├── lesson_workspace.py    # Document viewer, section editor, version history, exports
│       ├── research_sources.py    # Multi-modal bibliography, provenance tags, credibility bars
│       ├── quality_control.py     # Dual QC hub, claim verification tables, patch review
│       └── settings.py            # LLM status, SQLite diagnostics, Kalvium compliance matrix
│
├── docs/                          # Architectural documentation
│   ├── REQUIREMENTS.md            # Traceability checklist against Kalvium assignment
│   ├── ARCHITECTURE.md            # Deep system architecture & Mermaid diagrams
│   ├── DESIGN_DECISIONS.md        # Architecture Decision Records (ADRs)
│   ├── TESTING.md                 # Verification plan & test scenarios
│   └── KALVIUM_COMPLIANCE.md      # Full compliance matrix with test evidence
│
├── scripts/                       # Standalone offline verification scripts
│   ├── demo_storage.py            # End-to-end SQLite persistence & immutability demonstration
│   └── demo_export.py             # Multi-benchmark Markdown & ReportLab PDF export verification
│
└── tests/                         # Automated test suite (90 tests passing)
    ├── test_schemas.py            # Invariants, validation, duration boundary tests
    ├── test_research.py           # Web, books, YouTube, normalization, fallback tests
    ├── test_generation.py         # Grounded synthesis, Gemini mocking, duration budgeting
    ├── test_research_qc.py        # QC1 claims, RFC checks, contradiction penalties
    ├── test_instructional_qc.py   # QC2 Bloom's outcomes, pacing, cognitive load, isolation
    ├── test_recommendations.py    # Instructor review, true text replacement, diff verification
    ├── test_storage.py            # CRUD, WAL mode, foreign keys, rollbacks, restart tests
    ├── test_export.py             # Markdown, ReportLab PDF, pypdf selectable text, tables
    ├── test_benchmarks.py         # HTTP & DNS technical depth, safe/idempotent semantics
    └── test_ui_integration.py     # End-to-end lifecycle, persistence, QC, and exports
```

---

## ⚡ Quick Start & Installation

### 1. Prerequisites
- **Python**: Version `3.11` or `3.12` recommended (compatible with Python `3.11` through `3.14`).
- **Operating System**: Linux, macOS, or Windows (WSL recommended on Windows).

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/adicyb/LessonForge-AI.git
cd LessonForge-AI

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install locked production dependencies
pip install -r requirements.txt
```

### 3. Environment Variables (Optional)
```bash
# Copy example configuration template
cp .env.example .env
```
*Note: Adding a `GEMINI_API_KEY` is completely optional. If left blank, LessonForge AI automatically runs in 100% offline resilient deterministic mode.*

### 4. Launch the Streamlit Application
```bash
streamlit run app.py
```
*Access the workspace in your browser at: **`http://localhost:8501`***.

---

## 🧪 Automated Testing & Verification

Run the complete test suite across all 10 architectural modules:

```bash
# Run all 90 automated tests
pytest -v
```

### Standalone Demonstration Scripts
Verify persistence and export generation directly from the command line:

```bash
# Verify SQLite persistence, version snapshots & restart survivability
python3 scripts/demo_storage.py

# Verify Multi-Benchmark Markdown and ReportLab PDF document exports
python3 scripts/demo_export.py
```
---

## ⚖️ Standards Compliance & Citations

- **IETF RFC 9110**: *HTTP Semantics* (GET safe/idempotent properties, POST non-idempotent semantics, status code classes).
- **IETF RFC 1034 & RFC 1035**: *Domain Names — Concepts and Facilities* (DNS hierarchy, resolution flow, zone apex CNAME coexistence rules).
- **ReportLab 5.1.0**: Two-pass vector document generation with selectable Type 1 typography.
- **SQLite 3**: Acid durability, Write-Ahead Logging (WAL) concurrency, and cascading foreign key enforcement.

---

## 📄 License & Attribution

Developed by **Aditya Kumar** for the **Kalvium AI Research Intern Hiring Assignment**.  
All rights reserved. Delivered under academic fair use for candidate technical evaluation.
