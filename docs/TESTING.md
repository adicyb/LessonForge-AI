# LessonForge AI — Testing Strategy & Verification Plan

> **Scope**: Unit, Integration, Quality Control Audits, and Benchmark End-to-End Tests  
> **Framework**: Pytest with automated coverage and mocked external services  
> **Status**: Specification Complete  

---

## 1. Test Suite Structure

```
tests/
├── conftest.py                   # Pytest fixtures, mock research data, mock LLM responses
├── test_schemas.py               # Pydantic validation, 45-min duration invariants
├── test_research.py              # Web (DDGS), Book (Google Books/OpenLibrary), YouTube engines
├── test_generation.py            # Lesson generator, prompt composition, structure verification
├── test_research_qc.py           # QC Layer 1: Factual accuracy, source support, claim verification
├── test_instructional_qc.py      # QC Layer 2: Pedagogical quality, objective alignment, pacing
├── test_recommendations.py       # Recommendation acceptance/rejection/patch workflow
├── test_storage.py               # SQLite schema, versioning, CRUD, state preservation
├── test_export.py                # PDF and Markdown export verification
├── test_benchmark_http.py        # Benchmark 1: HTTP Requests and Responses
└── test_benchmark_dns.py         # Benchmark 2: DNS Resolution and Record Types
```

---

## 2. Test Execution Commands

```bash
# Run complete test suite with verbose output
pytest -v

# Run only QC layer tests
pytest -v tests/test_research_qc.py tests/test_instructional_qc.py

# Run benchmark verification tests
pytest -v tests/test_benchmark_http.py tests/test_benchmark_dns.py

# Run with coverage report
pytest --cov=. --cov-report=term-missing
```

---

## 3. Mandatory Benchmark Test Scenarios

### Benchmark 1: HTTP Requests and Responses
- **Title**: HTTP Requests and Responses
- **Objective**: Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.
- **Verification Gates**:
  1. *Generation*: Covers GET (idempotent, query parameters) and POST (body payload, non-idempotent); distinguishes 2xx (Success, e.g. 200 OK, 201 Created), 4xx (Client errors, e.g. 400 Bad Request, 404 Not Found), and 5xx (Server errors, e.g. 500 Internal Server Error, 503 Service Unavailable).
  2. *Research*: Discovers MDN Web Docs, RFC 9110 / RFC 7231, Computer Networking textbooks, and verified YouTube explainers.
  3. *QC Layer 1*: Verifies factual fidelity against RFC 9110; checks that GET vs POST idempotency is accurately stated; verifies status code explanations; confirms zero hallucinated claims.
  4. *QC Layer 2*: Assesses alignment to the objective, verifies cognitive scaffolding (from protocol basics to headers to methods to status codes to hands-on cURL/fetch activity), and validates that total duration is exactly 45 minutes.

### Benchmark 2: DNS Resolution and DNS Record Types
- **Title**: DNS Resolution and DNS Record Types
- **Objective**: Explain how recursive DNS resolution works and distinguish A, AAAA, CNAME, and MX records.
- **Verification Gates**:
  1. *Generation*: Explains recursive vs iterative resolution (Root, TLD, Authoritative servers); details A (IPv4), AAAA (IPv6), CNAME (canonical alias), and MX (mail exchange priority).
  2. *Research*: Discovers IETF RFC 1034/1035, Cloudflare/IANA technical documentation, Networking textbooks, and visual YouTube walk-throughs.
  3. *QC Layer 1*: Assesses technical accuracy of DNS hierarchy and record definitions; checks TTL concepts and resolution tree.
  4. *QC Layer 2*: Evaluates instructional clarity, step-by-step resolution diagram/analogy, hands-on `dig` or `nslookup` activity, and 45-minute timing feasibility.

---

## 4. Verification Checkpoints & Invariants

| Component | Invariant / Acceptance Criteria | Failure Condition |
| :--- | :--- | :--- |
| **Duration Budget** | $\sum \text{section.duration\_minutes} == 45$ | AssertionError if $\neq 45$ |
| **Citation Integrity** | All claims reference actual discovered source IDs | Flagged by QC Layer 1 as "UNSUPPORTED" |
| **QC Independence** | QC 1 and QC 2 run in isolated execution scopes | Shared state or cross-talk prohibited |
| **Persistence** | Updating a lesson creates a new version without deleting previous | Original version missing from DB |
| **Export Validity** | PDF exporter produces valid, uncorrupted PDF bytes with > 0 pages | Empty bytes or syntax error |
| **API Fallback** | Application executes end-to-end without any API keys | Crash or unhandled exception when keys absent |
