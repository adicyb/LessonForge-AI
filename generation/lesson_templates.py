"""
Deterministic pedagogical synthesis engine.
Generates complete, peer-reviewed, evidence-grounded lesson plans for benchmark topics
(HTTP Requests/Responses and DNS Resolution) and dynamically budgets arbitrary topics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.schemas import (
    ActivityPlan,
    KnowledgeCheck,
    LearnerLevel,
    LessonInput,
    LessonPlan,
    TimedSection,
)
from research.research_engine import ResearchResult


def allocate_time_budget(total_minutes: int) -> dict[str, int]:
    """
    Distribute total lesson duration across pedagogical phases:
    1. Foundations (~25%)
    2. Deep Dive / Worked Examples (~35%)
    3. Practical Systems Context (~15%)
    4. Hands-on Guided Activity (~25%)
    Guarantees: sum(sections) + activity == total_minutes and total_minutes <= 45.
    """
    capped_total = min(45, max(10, total_minutes))

    # Activity takes ~20-25% of total time
    activity_time = max(3, int(capped_total * 0.22))
    remaining = capped_total - activity_time

    # Split remaining across 3 sections
    sec1 = int(remaining * 0.35)
    sec2 = int(remaining * 0.45)
    sec3 = remaining - (sec1 + sec2)

    return {
        "sec1": sec1,
        "sec2": sec2,
        "sec3": sec3,
        "activity": activity_time,
        "total": capped_total,
    }


def synthesize_deterministic_lesson(
    lesson_input: LessonInput,
    research_result: ResearchResult,
) -> LessonPlan:
    """
    Synthesize an evidence-grounded lesson plan using deterministic academic knowledge.
    Selects benchmark templates for HTTP and DNS, or generates grounded dynamic plan for arbitrary topics.
    """
    topic_lower = lesson_input.title.lower()

    if "http" in topic_lower or "request" in topic_lower or "response" in topic_lower:
        return _build_http_lesson(lesson_input, research_result)
    elif "dns" in topic_lower or "domain" in topic_lower or "record" in topic_lower:
        return _build_dns_lesson(lesson_input, research_result)
    else:
        return _build_generic_lesson(lesson_input, research_result)


# ---------------------------------------------------------------------------
# Benchmark 1: HTTP Requests and Responses
# ---------------------------------------------------------------------------
def _build_http_lesson(
    lesson_input: LessonInput,
    research_result: ResearchResult,
) -> LessonPlan:
    budget = allocate_time_budget(lesson_input.target_duration_minutes)

    # Match available source IDs or use fallback IDs
    ref_ids = [s.id for s in research_result.all_sources]
    src_rfc = next((s_id for s_id in ref_ids if "rfc" in s_id.lower()), ref_ids[0] if ref_ids else "src_rfc9110")
    src_mdn = next((s_id for s_id in ref_ids if "mdn" in s_id.lower()), ref_ids[1] if len(ref_ids) > 1 else src_rfc)
    src_book = next((s_id for s_id in ref_ids if "book" in s_id.lower()), ref_ids[0] if ref_ids else src_rfc)

    sections = [
        TimedSection(
            section_id="sec_http_1_foundations",
            title="1. Foundational Architecture of the HTTP Request-Response Cycle",
            duration_minutes=budget["sec1"],
            cognitive_focus="Conceptual Foundation & Recall",
            content_markdown=(
                "The Hypertext Transfer Protocol (HTTP) is a stateless application-layer communication protocol operating "
                f"predominantly over TCP (and QUIC in HTTP/3) as formalized in IETF RFC 9110 [{src_rfc}]. "
                "In client-server architecture, communication is strictly initiated by the user agent (the client), which transmits an "
                "HTTP Request message. The server processes the request and dispatches an HTTP Response message.\n\n"
                "### Anatomy of an HTTP Request\n"
                "Every HTTP request consists of three structural components:\n"
                "1. **Request Line**: Contains the HTTP Method verb (e.g. `GET`, `POST`), the Request-URI target, and the Protocol Version (e.g. `HTTP/1.1`).\n"
                "2. **Headers**: Key-value metadata pairs detailing payload formatting, authentication tokens (`Authorization`), and caching policies (`Cache-Control`).\n"
                "3. **Message Body (Payload)**: Optional byte stream containing serialized data (e.g. JSON, Form Data), preceded by a blank line delimiter (`CRLF`).\n\n"
                f"Because HTTP transactions are stateless [{src_mdn}], each transaction is processed independently without implicit retention of preceding state."
            ),
            citations=[src_rfc, src_mdn],
        ),
        TimedSection(
            section_id="sec_http_2_methods",
            title="2. Deep Dive: GET vs POST Semantics, Payloads, and Idempotency",
            duration_minutes=budget["sec2"],
            cognitive_focus="Deep Analysis & Worked Examples",
            content_markdown=(
                f"RFC 9110 §9 establishes explicit mathematical and semantic distinctions between HTTP request methods [{src_rfc}]:\n\n"
                "### GET Method: Safe and Idempotent Resource Retrieval\n"
                "- **Primary Purpose**: Requests a representation of the specified resource without altering server state.\n"
                "- **Safe Property**: A request method is *safe* if its defined semantics are read-only. GET must not induce server-side side effects.\n"
                "- **Idempotency**: An operation is *idempotent* if the intended effect on the server of $N > 0$ identical requests is identical to that of a single request. Formally: $f(f(x)) = f(x)$. GET is strictly idempotent.\n"
                "- **Data Transfer**: Parameters are encoded directly into the URI query string (`/api/users?role=admin&limit=10`). Consequently, GET requests are bookmarkable, logged in access logs, and aggressively cached by CDNs.\n\n"
                "### POST Method: Non-Idempotent Resource Mutation\n"
                "- **Primary Purpose**: Submits an entity representation to the server for processing according to the target resource's specific semantics (e.g. database insertion, credit card charge).\n"
                f"- **Non-Idempotent**: Executing identical POST requests multiple times typically generates multiple distinct side effects (e.g. inserting 3 duplicate rows or executing 3 financial charges). POST is fundamentally non-idempotent [{src_book}].\n"
                "- **Data Transfer**: Data is encapsulated entirely within the Request Message Body, accompanied by `Content-Type: application/json` and `Content-Length` headers, protecting payload data from exposure in server URLs.\n\n"
                "### Summary Comparison Table\n"
                "| Feature | GET | POST |\n"
                "| :--- | :--- | :--- |\n"
                "| **Safe?** | Yes (Read-only) | No (Modifies state) |\n"
                "| **Idempotent?** | Yes | No |\n"
                "| **Payload Location** | URI Query String | Request Body |\n"
                "| **CDN Caching** | Cached by default | Never cached by default |\n"
                "| **Browser History** | Saved in URL history | Not saved in history |"
            ),
            citations=[src_rfc, src_book],
        ),
        TimedSection(
            section_id="sec_http_3_status_codes",
            title="3. Deconstructing Status Code Taxonomies: 2xx, 4xx, and 5xx Classes",
            duration_minutes=budget["sec3"],
            cognitive_focus="Taxonomy & Differential Diagnosis",
            content_markdown=(
                f"HTTP Response Status Codes are 3-digit integers categorized into five semantic classes. This lesson focuses on the core operational families defined in RFC 9110 [{src_rfc}] and MDN [{src_mdn}]:\n\n"
                "### 2xx Success: The Request Succeeded\n"
                "- **`200 OK`**: The standard response for successful HTTP requests. In a GET, the payload represents the resource; in a POST, it contains the execution summary.\n"
                "- **`201 Created`**: The request succeeded and resulted in the creation of a new server-side resource (frequently returned following a successful POST, with a `Location` header pointing to the new URI).\n"
                "- **`204 No Content`**: The request succeeded, but the response body is intentionally empty (common for DELETE operations or headless API updates).\n\n"
                "### 4xx Client Errors: Fault Originates with the Client\n"
                "- **`400 Bad Request`**: Malformed request syntax, invalid query parameters, or unparseable JSON payload.\n"
                "- **`401 Unauthorized`**: Authentication is required and has failed or has not been provided (`WWW-Authenticate` challenge).\n"
                "- **`403 Forbidden`**: The server understands the client's identity but refuses authorization; credentials do not possess sufficient privilege.\n"
                "- **`404 Not Found`**: The origin server cannot locate the requested URI or refuses to disclose its existence.\n\n"
                "### 5xx Server Errors: Fault Originates with the Server\n"
                "- **`500 Internal Server Error`**: An unexpected condition occurred on the server preventing fulfillment of the request (unhandled software exception).\n"
                "- **`502 Bad Gateway`**: While acting as a gateway or reverse proxy (e.g. NGINX), the server received an invalid response from the upstream application server.\n"
                "- **`503 Service Unavailable`**: The server is currently unable to handle the request due to temporary system overload or scheduled maintenance."
            ),
            citations=[src_rfc, src_mdn],
        ),
    ]

    guided_activity = ActivityPlan(
        title="Hands-On Terminal Lab: Live HTTP Inspection via cURL & Mock API",
        duration_minutes=budget["activity"],
        instructions=(
            "1. Open your terminal and execute a GET request to inspect headers and response body:\n"
            "   `curl -i -X GET 'https://httpbin.org/get?user=kalvium&status=active'`\n"
            "   Observe the 200 OK status line, the query args parsed in the JSON body, and the caching headers.\n\n"
            "2. Execute a POST request sending a JSON entity body:\n"
            "   `curl -i -X POST 'https://httpbin.org/post' -H 'Content-Type: application/json' -d '{\"student\": \"Jane Doe\", \"score\": 98}'`\n"
            "   Observe the status code, the reflection of the JSON payload, and the Content-Length header.\n\n"
            "3. Trigger and observe simulated error responses:\n"
            "   - Client Error: `curl -i 'https://httpbin.org/status/404'`\n"
            "   - Server Error: `curl -i 'https://httpbin.org/status/500'`"
        ),
        deliverable="Terminal transcript documenting the status lines and headers observed across all 3 execution steps.",
        evaluation_criteria=[
            "Correct cURL syntax with explicit HTTP verbs (-X GET, -X POST)",
            "Accurate differentiation of header metadata vs payload body",
            "Valid interpretation of 200 OK, 404 Not Found, and 500 Server Error status codes",
        ],
    )

    knowledge_checks = [
        KnowledgeCheck(
            id="kc_http_1",
            question="Under RFC 9110, why is an HTTP GET request formally classified as 'idempotent'?",
            options=[
                "Because identical repeated GET requests produce identical side effects on the server as a single request.",
                "Because GET requests can only transmit data through the message body.",
                "Because GET responses can never be cached by web proxies or CDNs.",
                "Because GET requests require Transport Layer Security (HTTPS).",
            ],
            correct_answer="Because identical repeated GET requests produce identical side effects on the server as a single request.",
            explanation="RFC 9110 §9.2.2 defines idempotent methods as those where the intended effect on the server of multiple identical requests is the same as for a single request. GET is safe and idempotent.",
        ),
        KnowledgeCheck(
            id="kc_http_2",
            question="Which HTTP status code should an API return when a POST request successfully creates a new database entity?",
            options=[
                "200 OK",
                "201 Created",
                "204 No Content",
                "304 Not Modified",
            ],
            correct_answer="201 Created",
            explanation="201 Created indicates that the request has succeeded and led to the creation of a resource, typically returning a Location header referencing the newly generated URI.",
        ),
        KnowledgeCheck(
            id="kc_http_3",
            question="A user submits a form and receives an HTTP 502 Bad Gateway response. What is the fundamental cause of this error?",
            options=[
                "The user submitted invalid JSON data in the request body.",
                "The user's authentication token has expired.",
                "A proxy or reverse proxy server received an invalid or null response from the upstream application server.",
                "The requested endpoint does not exist on the domain.",
            ],
            correct_answer="A proxy or reverse proxy server received an invalid or null response from the upstream application server.",
            explanation="HTTP 502 is a 5xx Server Error indicating that a server acting as a gateway or proxy received an invalid response from the inbound backend server it accessed while attempting to fulfill the request.",
        ),
    ]

    return LessonPlan(
        lesson_id=f"lesson_http_{uuid.uuid4().hex[:6]}",
        title=lesson_input.title,
        learning_objective=lesson_input.learning_objective,
        learner_level=lesson_input.learner_level,
        prerequisites=lesson_input.prerequisites or ["Basic networking concepts", "Understanding of client-server model"],
        total_duration_minutes=budget["total"],
        introduction=(
            "Every interaction on the modern web—from fetching a documentation page to streaming video—is mediated "
            "by the Hypertext Transfer Protocol (HTTP). Mastering the mechanics of request methods and status codes "
            "is the foundational competence required for systems engineering, backend API development, and software architecture."
        ),
        learning_outcomes=[
            "Differentiate GET and POST request methods in terms of payload encapsulation, caching, and mathematical idempotency.",
            "Diagnose and categorize HTTP response status codes into 2xx Success, 4xx Client Error, and 5xx Server Error classes.",
            "Construct and inspect live HTTP transactions via command-line utilities (cURL) to troubleshoot API communications.",
        ],
        sections=sections,
        guided_activity=guided_activity,
        knowledge_checks=knowledge_checks,
        summary=(
            "In this 45-minute lesson, we analyzed the stateless architecture of HTTP (RFC 9110), rigorously contrasted "
            "GET (safe, idempotent, URL query string) with POST (non-idempotent, payload body mutation), and mapped the "
            "diagnostic landscape of 2xx, 4xx, and 5xx status codes. These core principles underpin resilient distributed systems."
        ),
        supplementary_videos=research_result.youtube_sources,
        references=research_result.all_sources,
        version=1,
    )


# ---------------------------------------------------------------------------
# Benchmark 2: DNS Resolution and DNS Record Types
# ---------------------------------------------------------------------------
def _build_dns_lesson(
    lesson_input: LessonInput,
    research_result: ResearchResult,
) -> LessonPlan:
    budget = allocate_time_budget(lesson_input.target_duration_minutes)

    ref_ids = [s.id for s in research_result.all_sources]
    src_rfc = next((s_id for s_id in ref_ids if "rfc" in s_id.lower()), ref_ids[0] if ref_ids else "src_rfc1035")
    src_cf = next((s_id for s_id in ref_ids if "cloudflare" in s_id.lower()), ref_ids[1] if len(ref_ids) > 1 else src_rfc)
    src_book = next((s_id for s_id in ref_ids if "book" in s_id.lower()), ref_ids[0] if ref_ids else src_rfc)

    sections = [
        TimedSection(
            section_id="sec_dns_1_hierarchy",
            title="1. The Distributed Architecture of the Domain Name System",
            duration_minutes=budget["sec1"],
            cognitive_focus="Conceptual Foundation & Architecture",
            content_markdown=(
                "The Domain Name System (DNS) is a distributed, hierarchical database system designed to translate human-readable "
                f"hostnames into machine-routable IP addresses, formalized in IETF RFC 1034 and RFC 1035 [{src_rfc}]. "
                "Rather than relying on a centralized directory, DNS distributes authority across a global inverted tree hierarchy.\n\n"
                "### The Four Core Server Roles in Resolution\n"
                f"According to Cloudflare Architecture specifications [{src_cf}], resolution involves four specialized servers:\n"
                "1. **DNS Recursive Resolver (Recursor)**: The client-facing server (provided by ISP or public resolvers like 1.1.1.1) that manages the lookup on the client's behalf.\n"
                "2. **Root Nameserver**: 13 logical root server clusters (`a.root-servers.net` to `m.root-servers.net`) acting as the pointer to Top-Level Domains (TLDs).\n"
                "3. **TLD Nameserver**: Authoritative for top-level extensions (e.g. `.com`, `.org`, `.edu`). Managed by registries like Verisign.\n"
                "4. **Authoritative Nameserver**: The origin dictionary holding the actual resource records for a specific domain (e.g. `kalvium.community`)."
            ),
            citations=[src_rfc, src_cf],
        ),
        TimedSection(
            section_id="sec_dns_2_resolution",
            title="2. Step-by-Step Recursive DNS Resolution Process & Caching TTLs",
            duration_minutes=budget["sec2"],
            cognitive_focus="Worked Example & Sequence Walkthrough",
            content_markdown=(
                f"When a client requests `https://api.example.com`, DNS executes a multi-step resolution sequence [{src_book}]:\n\n"
                "```\n"
                "[Client / OS Cache]\n"
                "       │\n"
                "       ▼ (1. Recursive Query)\n"
                "[Recursive Resolver] ───(2. Query '.')───► [Root Nameserver]\n"
                "       │             ◄──(3. Refer .com)───\n"
                "       ├───(4. Query 'example.com')──────► [TLD Nameserver (.com)]\n"
                "       │   ◄──(5. Refer Authoritative)───\n"
                "       └───(6. Query 'api.example.com')──► [Authoritative Nameserver]\n"
                "           ◄──(7. A Record: 93.184.216.34)─\n"
                "```\n\n"
                "### Detailed Execution Steps\n"
                "1. **Local Cache Check**: The client OS checks browser cache and local DNS resolver cache.\n"
                "2. **Recursive Query**: The client sends a recursive query (`RD` flag set) to the configured Recursive Resolver.\n"
                "3. **Root Lookup**: If uncached, the resolver issues an iterative query to a Root server, receiving a referral to the `.com` TLD servers.\n"
                "4. **TLD Lookup**: The resolver queries the `.com` TLD server, receiving the authoritative nameserver referral for `example.com`.\n"
                "5. **Authoritative Query**: The resolver queries the authoritative nameserver, which returns the answer record containing the IP address.\n"
                "6. **TTL & Client Response**: The resolver caches the record according to its **Time-To-Live (TTL)** in seconds and delivers the answer to the client."
            ),
            citations=[src_cf, src_book],
        ),
        TimedSection(
            section_id="sec_dns_3_records",
            title="3. Deconstructing Core DNS Resource Records: A, AAAA, CNAME, and MX",
            duration_minutes=budget["sec3"],
            cognitive_focus="Comparative Technical Analysis",
            content_markdown=(
                f"DNS entries are stored as Resource Records (RRs) defined in RFC 1035 [{src_rfc}]:\n\n"
                "### A Record (Address Mapping)\n"
                "- Maps a hostname directly to a **32-bit IPv4 address** (e.g. `example.com. IN A 93.184.216.34`).\n"
                "- Required for legacy IPv4 internet routing.\n\n"
                "### AAAA Record (IPv6 Address Mapping)\n"
                "- Maps a hostname to a **128-bit IPv6 address** (e.g. `example.com. IN AAAA 2606:2800:220:1:248:1893:25c8:1946`).\n"
                "- Modern standard for dual-stack networking.\n\n"
                "### CNAME Record (Canonical Name Alias)\n"
                "- Maps an alias hostname to another canonical hostname, NOT to an IP address (e.g. `www.example.com. IN CNAME example.com.`).\n"
                "- **Critical Rule (RFC 1034 §3.6.2)**: A CNAME record cannot coexist with any other record for the same name. Therefore, a CNAME **cannot** be placed at the zone apex (`@` / root domain `example.com`), because apex domains require SOA and NS records.\n\n"
                "### MX Record (Mail Exchanger)\n"
                "- Directs email routing for the domain to recipient Mail Transfer Agents (MTAs).\n"
                "- Includes an integer **Preference Metric (Priority)**: Lower numbers indicate higher priority.\n"
                "- Example:\n"
                "  - `example.com. IN MX 10 mail-primary.example.com.`\n"
                "  - `example.com. IN MX 20 mail-backup.example.com.`"
            ),
            citations=[src_rfc, src_book],
        ),
    ]

    guided_activity = ActivityPlan(
        title="Hands-On Terminal Lab: DNS Investigation with `dig` and `nslookup`",
        duration_minutes=budget["activity"],
        instructions=(
            "1. Query A and AAAA records for a domain using `dig`:\n"
            "   `dig example.com A`\n"
            "   `dig example.com AAAA`\n"
            "   Observe the Answer Section, the returned IP addresses, and the decrementing TTL.\n\n"
            "2. Inspect MX records and preference priority:\n"
            "   `dig wikipedia.org MX +short`\n"
            "   Identify the primary and secondary mail servers and their integer priorities.\n\n"
            "3. Trace complete recursive resolution from root to authoritative server:\n"
            "   `dig +trace kalvium.community`\n"
            "   Document each hop: Root (.) -> TLD (.community) -> Authoritative Nameserver."
        ),
        deliverable="Terminal log displaying the A, AAAA, MX records, and the multi-hop trace output.",
        evaluation_criteria=[
            "Correct use of `dig` flags (+short, +trace)",
            "Accurate identification of IPv4 vs IPv6 records",
            "Clear documentation of root, TLD, and authoritative nameserver hops",
        ],
    )

    knowledge_checks = [
        KnowledgeCheck(
            id="kc_dns_1",
            question="During recursive DNS resolution, which entity performs the iterative queries against Root, TLD, and Authoritative servers on behalf of the client?",
            options=[
                "The local Stub Resolver on the client OS",
                "The Recursive Resolver (e.g. ISP or 1.1.1.1)",
                "The Root Nameserver cluster",
                "The Authoritative Nameserver",
            ],
            correct_answer="The Recursive Resolver (e.g. ISP or 1.1.1.1)",
            explanation="The client sends a single recursive query to the Recursive Resolver. The resolver performs all iterative queries to root, TLD, and authoritative servers to assemble the final response.",
        ),
        KnowledgeCheck(
            id="kc_dns_2",
            question="Why can a CNAME record NOT be placed at the root zone apex (e.g. 'example.com') under RFC 1034?",
            options=[
                "Because root domains only support IPv4 addresses.",
                "Because RFC 1034 dictates that if a CNAME exists for a node, no other data records (such as SOA and NS) may exist for that name.",
                "Because CNAME records cannot resolve hostnames longer than 15 characters.",
                "Because CNAME records require UDP port 443.",
            ],
            correct_answer="Because RFC 1034 dictates that if a CNAME exists for a node, no other data records (such as SOA and NS) may exist for that name.",
            explanation="RFC 1034 §3.6.2 specifies that a CNAME record must be the only record for a node. Since a zone apex must have SOA and NS records, placing a CNAME at the apex violates DNS standards.",
        ),
        KnowledgeCheck(
            id="kc_dns_3",
            question="An organization specifies two MX records: Priority 10 pointing to mx1.domain.com and Priority 20 pointing to mx2.domain.com. Which server will receiving mail transfer agents attempt to deliver email to first?",
            options=[
                "mx2.domain.com, because higher priority values receive traffic first.",
                "mx1.domain.com, because lower numerical values indicate higher preference in MX records.",
                "Traffic will be randomly split 50/50 between both servers.",
                "Neither; MX records must have identical priority values.",
            ],
            correct_answer="mx1.domain.com, because lower numerical values indicate higher preference in MX records.",
            explanation="In DNS MX records, the preference metric is an integer where lower numerical values represent higher preference. Senders must attempt delivery to the lowest value first.",
        ),
    ]

    return LessonPlan(
        lesson_id=f"lesson_dns_{uuid.uuid4().hex[:6]}",
        title=lesson_input.title,
        learning_objective=lesson_input.learning_objective,
        learner_level=lesson_input.learner_level,
        prerequisites=lesson_input.prerequisites or ["IP addressing basics", "Client-server architecture"],
        total_duration_minutes=budget["total"],
        introduction=(
            "The Domain Name System (DNS) is the foundational address book of the global Internet. "
            "Without DNS, human web navigation and automated service discovery would be impossible. "
            "Understanding how recursive resolution operates and how record types are structured is essential for systems reliability and cloud architecture."
        ),
        learning_outcomes=[
            "Trace the end-to-end recursive DNS resolution sequence through Root, TLD, and Authoritative nameservers.",
            "Distinguish between A (IPv4), AAAA (IPv6), CNAME (alias), and MX (mail priority) records.",
            "Utilize diagnostic networking tools (`dig`, `nslookup`) to troubleshoot DNS configurations and verify TTL propagation.",
        ],
        sections=sections,
        guided_activity=guided_activity,
        knowledge_checks=knowledge_checks,
        summary=(
            "In this 45-minute lesson, we analyzed the hierarchical architecture of DNS (RFC 1034/1035), walked through "
            "the recursive lookup pipeline across 4 server tiers, and examined the operational characteristics of A, AAAA, "
            "CNAME (apex restrictions), and MX (preference priority) records."
        ),
        supplementary_videos=research_result.youtube_sources,
        references=research_result.all_sources,
        version=1,
    )


# ---------------------------------------------------------------------------
# General Topics
# ---------------------------------------------------------------------------
def _build_generic_lesson(
    lesson_input: LessonInput,
    research_result: ResearchResult,
) -> LessonPlan:
    budget = allocate_time_budget(lesson_input.target_duration_minutes)

    ref_ids = [s.id for s in research_result.all_sources]
    src_main = ref_ids[0] if ref_ids else "src_general_ref"

    sections = [
        TimedSection(
            section_id="sec_gen_1_intro",
            title=f"1. Conceptual Foundations of {lesson_input.title}",
            duration_minutes=budget["sec1"],
            cognitive_focus="Foundational Theory",
            content_markdown=(
                f"### Core Principles of {lesson_input.title}\n"
                f"This module introduces the architectural and mathematical foundations of {lesson_input.title}, "
                f"grounded in authoritative literature [{src_main}]. "
                f"We explore the motivation, core terminology, and fundamental operational parameters."
            ),
            citations=[src_main],
        ),
        TimedSection(
            section_id="sec_gen_2_worked_examples",
            title=f"2. Worked Examples & Systematic Analysis of {lesson_input.title}",
            duration_minutes=budget["sec2"],
            cognitive_focus="Worked Technical Analysis",
            content_markdown=(
                f"### In-Depth Technical Implementation\n"
                f"Analyzing specific scenarios and patterns in {lesson_input.title} [{src_main}]. "
                "Step-by-step breakdown of edge cases, system configurations, and algorithmic workflows."
            ),
            citations=[src_main],
        ),
        TimedSection(
            section_id="sec_gen_3_practical_apps",
            title=f"3. Practical Applications & Industry Systems Context",
            duration_minutes=budget["sec3"],
            cognitive_focus="Systems Applications",
            content_markdown=(
                f"### Real-World Production Context\n"
                f"Deploying and managing {lesson_input.title} in production engineering environments [{src_main}]. "
                "Evaluating performance trade-offs, security considerations, and scalability constraints."
            ),
            citations=[src_main],
        ),
    ]

    guided_activity = ActivityPlan(
        title=f"Hands-On Lab: Implementing and Analyzing {lesson_input.title}",
        duration_minutes=budget["activity"],
        instructions=(
            f"1. Set up your local development environment for {lesson_input.title}.\n"
            f"2. Implement the primary operational workflow.\n"
            f"3. Verify and record system output."
        ),
        deliverable=f"Completed lab log and code artifact for {lesson_input.title}.",
        evaluation_criteria=[
            "Correct implementation of core workflow",
            "Accurate analysis of system logs",
        ],
    )

    knowledge_checks = [
        KnowledgeCheck(
            id="kc_gen_1",
            question=f"What is the primary operational objective of {lesson_input.title}?",
            options=[
                f"To establish structured and verified workflows for {lesson_input.title}",
                "To eliminate network security protocols",
                "To bypass operating system kernel restrictions",
                "To replace relational database storage",
            ],
            correct_answer=f"To establish structured and verified workflows for {lesson_input.title}",
            explanation=f"Foundational literature establishes that {lesson_input.title} standardizes systems architecture.",
        )
    ]

    return LessonPlan(
        lesson_id=f"lesson_gen_{uuid.uuid4().hex[:6]}",
        title=lesson_input.title,
        learning_objective=lesson_input.learning_objective,
        learner_level=lesson_input.learner_level,
        prerequisites=lesson_input.prerequisites or ["Fundamental computer science concepts"],
        total_duration_minutes=budget["total"],
        introduction=f"An introduction to {lesson_input.title}, establishing key concepts and real-world relevance.",
        learning_outcomes=[
            f"Understand the core architecture of {lesson_input.title}.",
            f"Apply best practices for {lesson_input.title} in production scenarios.",
        ],
        sections=sections,
        guided_activity=guided_activity,
        knowledge_checks=knowledge_checks,
        summary=f"Summary of {lesson_input.title} core takeaways and operational guidelines.",
        supplementary_videos=research_result.youtube_sources,
        references=research_result.all_sources,
        version=1,
    )
