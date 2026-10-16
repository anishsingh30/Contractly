# CONTRACTLY: SYSTEM ARCHITECTURE & IMPLEMENTATION BLUEPRINT
### Intelligent Contract Lifecycle & Legal Operations Platform
**Target Tier:** Enterprise-Ready, Multi-Tenant SaaS Platform  
**Document Version:** 1.0.0-ARCHITECTURE-SPEC  
**Author:** Principal Software Architect & LegalTech Systems Engineering Team  

---

## 1. EXECUTIVE ARCHITECTURE SUMMARY

**Contractly** is an enterprise-grade Legal Operations and Contract Lifecycle Management (CLM) SaaS platform designed for four distinct operating tiers:
1. **Personal / Consumer:** Individuals managing employment agreements, lease/rental contracts, freelance scopes of work, and loan documents.
2. **Business / Enterprise:** Multi-department corporate organizations (Legal, Finance, Procurement, HR, Sales, Executive) executing vendor agreements, MSAs, DPAs, and SOWs with multi-level approval workflows and obligation tracking.
3. **Professional (Lawyers & Law Firms):** Independent practitioners and law firms managing clients, legal matters, redlines, reviews, and client consultations.
4. **Platform Administration:** Contractly internal operators managing tenants, billing, AI quota consumption, model fallbacks, audit compliance, and system health.

### Core Architectural Pillars
- **Strict Multi-Tenant Isolation:** Relational row-level tenant tagging (`organization_id`), tenant-scoped database isolation policies, encrypted object storage paths, and vector collection metadata partitioning.
- **Hybrid AI Execution Matrix:** Strict segregation between **Deterministic Rule Engines** (deadlines, state transitions, financial calculations, permissions) and **Non-Deterministic AI Agents** (clause extraction, semantic risk scoring, redlining diff suggestions, natural language query translation).
- **Legal Non-Adjudicative Safety:** Architectural guarantees ensuring the system never issues binding legal conclusions or assertions of breach, instead utilizing calibrated probability scores, risk flags, and evidentiary trails reserved for human-in-the-loop (HITL) review.
- **Asynchronous Heavy Processing:** Decoupled document ingestion, OCR, chunking, embedding generation, deep risk audits, and notification dispatch using asynchronous background message queues.
- **Zero Data Contamination:** Complete isolation of tenant data from public LLM training surfaces, with ephemeral processing guarantees and tenant-scoped vector search spaces.

---

## 2. PRODUCT ARCHITECTURE & LAYER RESPONSIBILITIES

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       USER SURFACES                                             │
│   ┌─────────────────┐   ┌──────────────────┐   ┌───────────────────┐   ┌────────────────────┐   │
│   │ Personal Client │   │ Business Tenant  │   │ Law Firm / Lawyer │   │   Platform Admin   │   │
│   └────────┬────────┘   └────────┬─────────┘   └─────────┬─────────┘   └─────────┬──────────┘   │
└────────────┼─────────────────────┼───────────────────────┼───────────────────────┼──────────────┘
             ▼                     ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                GATEWAY, AUTHENTICATION & RBAC                                   │
│  - JWT Bearer Authentication / OAuth2 / Session Tokens                                          │
│  - Multi-Tenant Header / Domain Resolution (`X-Tenant-ID` / Subdomain)                          │
│  - Route-Level & Method-Level RBAC Enforcement Guard                                            │
│  - Rate Limiting (Token Bucket per Tenant Tier) & WAF Sanitization                             │
└────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             NEXT.JS FRONTEND APPLICATION LAYER                                  │
│  - Server Components (SSR / RSC) & Client Hydration                                             │
│  - Rich Text & Tracked-Changes Redline Editor (ProseMirror / TipTap)                            │
│  - Side-by-Side Dual-Pane Document & PDF Visualizer (PDF.js / WebViewer)                       │
│  - Real-Time Activity WebSockets / Server-Sent Events (SSE) Client                              │
└────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI BACKEND REST / SSE API LAYER                               │
│  - Request DTO Validation (Pydantic v2)                                                         │
│  - Tenant Context Injection (Dependency Injection: `get_current_tenant`, `get_current_user`)    │
│  - Service Orchestration Layer (Contracts, Redlines, Approvals, Obligations)                     │
│  - Event Publishers (Redis / RabbitMQ Message Broker)                                           │
└──────────────────────┬──────────────────────────────────────────┬───────────────────────────────┘
                       │                                          │
        ┌──────────────┴──────────────┐            ┌──────────────┴──────────────┐
        ▼                             ▼            ▼                             ▼
┌───────────────────────────┐ ┌──────────────┐ ┌───────────────────────────┐ ┌────────────────────┐
│   PERSISTENCE LAYER       │ │DOCUMENT STORE│ │ ASYNC TASK QUEUE (CELERY) │ │   VECTOR STORE     │
│  PostgreSQL (Relational)  │ │ S3-Compatible│ │ - OCR / Extraction Worker │ │  pgvector Extension │
│  - 35+ Normalized Tables  │ │ Encrypted at │ │ - Embeddings Worker       │ │  - Tenant Metadata │
│  - Row-Level Security     │ │ Rest (SSE-S3)│ │ - Deep LLM Audit Worker   │ │    Filtering       │
│  - JSONB Playbook Schemas │ │ Versioned    │ │ - Notification Dispatcher │ │  - HNSW / IVFFlat  │
└───────────────────────────┘ └──────────────┘ └──────────────┬────────────┘ └────────────────────┘
                                                              │
                                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 AI & INTELLIGENCE ENGINE (RAG)                                  │
│  - Hybrid Chunking: Structural (Section/Clause-Aware) + Semantic Splitting                      │
│  - Retrieval Pipeline: Dense Vector Similarity (Cosine) + Sparse Keyword Search (BM25) (Hybrid) │
│  - Re-ranking Layer: Cross-Encoder Contextual Compression                                       │
│  - Agentic Workflow Engine (LangGraph / Multi-Agent State Machine):                             │
│    * Extraction Agent   * Risk Scorer Agent   * Redlining Agent   * Q&A Grounding Agent         │
└─────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               COMPLIANCE & NOTIFICATION ENGINE                                  │
│  - Contract Watch Daemon (Deterministic Cron-based Expiry, Renewal & Obligation Deadlines)      │
│  - Evidence Verification Engine (Audit trail, timestamp validation, user attribution)           │
│  - Notification Dispatcher (In-App SSE, Transactional Email via Resend/SendGrid, Webhooks)       │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Layer Responsibilities
1. **Frontend Presentation Layer (Next.js / TypeScript):** High-fidelity rendering of split-screen contract diffs, legal redline views with additions/deletions/comments, visual approval workflow builders, obligation calendar dashboards, and AI streaming chat interactions.
2. **API & Gateway Layer (FastAPI):** Enforces request schemas, verifies cryptographic JWT tokens, establishes tenant context in request state, checks RBAC permissions before touching service layers, and exposes SSE endpoints for real-time AI responses.
3. **Core Backend Domain Services:** Encapsulates business logic for contract versioning, approval routing state machines, vendor risk profiling, and matter management.
4. **Document Ingestion Pipeline:** Manages multi-part file uploads, calculates cryptographic SHA-256 hashes for tamper verification, validates MIME types, strips malicious macros, and triggers asynchronous ingestion tasks.
5. **Asynchronous Background Processing (Celery / Redis):** Offloads compute-heavy and latency-variable tasks (OCR conversion, text tokenization, vector indexing, multi-clause LLM risk audits, automated scheduled cron monitors).
6. **Persistence & Vector Storage:** 
   - PostgreSQL serves as the single source of truth for transactional state.
   - `pgvector` co-locates relational contract records with clause embeddings inside PostgreSQL, preventing synchronization issues between external vector DBs and transactional databases.
7. **Compliance & Obligation Engine ("Contract Watch"):** Evaluates deadlines against current timestamps, identifies missing evidence, calculates SLA breach probabilities, and flags escalated risk tickets deterministically.
8. **AI / RAG Layer:** Runs structured prompting, few-shot clause classification, fallback parsing, citation verification, and redline replacement synthesis with strict legal guardrails.

---

## 3. ACCOUNT TYPES ARCHITECTURE

Contractly separates system accounts into four distinct conceptual and functional domains:

```text
                               ┌─────────────────────────┐
                               │       User Entity       │
                               └────────────┬────────────┘
                                            │
        ┌───────────────────┬───────────────┴───────────────┬───────────────────┐
        ▼                   ▼                               ▼                   ▼
┌───────────────┐   ┌───────────────┐               ┌───────────────┐   ┌───────────────┐
│   PERSONAL    │   │   BUSINESS    │               │ PROFESSIONAL  │   │ PLATFORM ADMIN│
└───────┬───────┘   └───────┬───────┘               └───────┬───────┘   └───────┬───────┘
        │                   │                               │                   │
  Self-Tenant        Org Membership                  Practice / Firm      System Master
  Individual Vault   Department-scoped               Client / Matter      Cross-Tenant
  Direct Pay-per-doc Quota-based Seats               Hourly / Flat Rate   Observability
```

### 1. Personal Workspace (`ACCOUNT_TYPE = PERSONAL`)
- **Target Audience:** Consumers, freelancers, tenants, individual contractors, employees reviewing job offers.
- **Data Model:** A Personal User owns a personal virtual organization (`is_personal = true`) where they are the sole owner and member.
- **Functionality:** 
  - Simplified, non-intimidating single-column or side-by-side dashboard.
  - Core Focus: "What am I signing?", "What are my risks?", "When do I need to cancel/renew?", "What are my obligations?"
  - Quick contract health check with plain-language risk breakdowns.
  - Direct 1-click consultation booking with verified lawyers in the Professional directory.

### 2. Business Workspace (`ACCOUNT_TYPE = BUSINESS`)
- **Target Audience:** Startups, mid-market companies, multinational enterprises, procurement and in-house legal departments.
- **Data Model:** Multi-user Organization structure with Departments (Legal, Procurement, Finance, HR, Sales, IT).
- **Functionality:**
  - Multi-tiered Approval Workflows with rule-based routing (e.g., contracts > $50,000 require CFO sign-off).
  - Corporate Legal Playbook enforcement (standard fallback clauses, acceptable deviations, prohibited terms).
  - Vendor Risk Management & counterparty vendor profiles.
  - Contract Repository with hierarchical folders, tag taxonomies, and multi-version history.
  - Enterprise Contract Watch: automated milestone tracking, SLA compliance, penalty warnings.

### 3. Professional Workspace (`ACCOUNT_TYPE = PROFESSIONAL`)
- **Target Audience:** Solo practitioners, boutique law firms, corporate legal counsels handling external clients.
- **Data Model:** Firm Entity -> Members (Firm Admin, Partner, Associate, Paralegal) -> Clients -> Matters -> Contracts.
- **Functionality:**
  - Client Management & Matter Isolation: A matter isolates all related contracts, communications, discovery documents, and billing records.
  - Professional Redline Studio with enterprise-grade tracked changes compatible with Microsoft Word (.docx).
  - Public Marketplace / Directory Profile for receiving consultation requests from Personal and Business accounts.
  - Billable hours and consultation appointment logs.

### 4. Platform Admin Workspace (`ACCOUNT_TYPE = PLATFORM_ADMIN`)
- **Target Audience:** Contractly system administrators, DevOps, platform compliance officers, customer support engineers.
- **Data Model:** Internal superuser access with multi-factor authentication (MFA) and immutable action audit logging.
- **Functionality:**
  - Tenant Lifecycle: Provisioning, suspension, tier upgrading, storage usage caps, seat allocations.
  - Global AI Infrastructure Monitoring: Token usage, latency percentiles (p50, p95, p99), error rates, LLM provider fallback routing.
  - Global Security Audits: Review failed login surges, cross-tenant rejection alerts, and export compliance logs.

---

## 4. ROLE-BASED ACCESS CONTROL (RBAC) & PERMISSION MATRIX

Contractly enforces a **Fine-Grained Contextual RBAC (FG-RBAC)** architecture. Permissions are evaluated based on:
`HasPermission(User, Organization, Role, Resource, Action, DepartmentScope)`

### Comprehensive Permission Matrix

| Feature / Resource Action | Org Owner | Business Admin | Legal Manager | Legal Reviewer | Finance | Procurement | HR | Sales | Dept Manager | Employee / Requester | Law Firm Admin | Lawyer | Legal Assistant | Personal User | Platform Admin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **View Contracts (All Org)** | ✅ | ✅ | ✅ | ✅ | ⚠️ (Finance) | ⚠️ (Proc) | ⚠️ (HR) | ⚠️ (Sales) | ⚠️ (Dept) | ❌ (Own only) | ✅ (Firm) | ⚠️ (Assigned) | ⚠️ (Assigned) | ✅ (Own) | 🔍 (Audit only) |
| **Upload Contract / Draft** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (Request) | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Execute AI Risk Analysis** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ (Restricted) | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Generate AI Redlines** | ✅ | ✅ | ✅ | ✅ | ❌ | ⚠️ (Draft) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ⚠️ (Draft) | ✅ | ❌ |
| **Accept/Reject Redlines** | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| **Approve Stage (Workflow)** | ✅ | ⚠️ (Admin) | ✅ | ✅ | ⚠️ (Fin $ threshold) | ⚠️ (Proc terms) | ⚠️ (HR) | ❌ | ⚠️ (Dept cap) | ❌ | ❌ | ❌ | ❌ | N/A | ❌ |
| **Configure Workflows** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Configure Legal Playbook**| ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ⚠️ (Firm draft) | ❌ | ❌ | ❌ |
| **View Financial Terms/Values**| ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ⚠️ (HR comp) | ⚠️ (Deal val) | ⚠️ (Dept budg)| ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| **Manage Vendors** | ✅ | ✅ | ✅ | ❌ | ⚠️ (View) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Manage Obligations / Watch**| ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ (Sales obl) | ✅ | ⚠️ (Own tasks) | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Upload Obligation Evidence**| ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (Assigned) | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Manage Users & Roles** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ (All Orgs) |
| **Manage Billing & Seats** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ (Global) |
| **Client / Matter Isolation** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | ✅ | ✅ | ⚠️ (Assigned) | N/A | 🔍 (Global view) |
| **Book Legal Consultation** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **View Immutable Audit Logs**| ✅ | ✅ | ✅ | ❌ | ⚠️ (Finance) | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ (Own) | ✅ (Global) |

*Legend: ✅ Full Access | ⚠️ Conditional / Scoped Access | ❌ Forbidden | 🔍 Blind Audit / Support Access (Requires break-glass protocol)*

---

## 5. FEATURE ARCHITECTURE (MODULES & DEPENDENCY GRAPH)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                  CORE INFRASTRUCTURE                                   │
│  [Auth & Identity] ──► [Organization & Multi-Tenancy] ──► [RBAC & Permissions]         │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              DOCUMENT REPOSITORY SYSTEM                                │
│  [Document Ingestion & S3 Store] ──► [Extraction Pipeline] ──► [Contract Repository]   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
         ┌──────────────────────────────────┴──────────────────────────────────┐
         ▼                                                                     ▼
┌──────────────────────────────────┐                 ┌───────────────────────────────────┐
│     AI REASONING ENGINE (RAG)    │                 │      LIFECYCLE WORKFLOW ENGINE    │
│  - [Clause Extraction & Classify]│                 │  - [Contract Request Pipeline]    │
│  - [Risk Analysis & Scoring]     │                 │  - [Multi-Tier Approval Engine]   │
│  - [Contract Q&A Agent]          │                 │  - [Vendor Management Module]     │
│  - [AI Redlining & Diff Engine]  │                 │  - [Legal Playbook Rule Engine]   │
│  - [Contract Comparison Engine]  │                 │  - [Templates & Clause Library]   │
└────────────────┬─────────────────┘                 └─────────────────┬─────────────────┘
                 │                                                     │
                 └──────────────────────────┬──────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     POST-EXECUTION COMPLIANCE & MONITORING                             │
│  [Contract Watch Daemon] ◄──► [Obligation Engine] ◄──► [Evidence & Audit Trail]        │
│          │                                                                             │
│          ▼                                                                             │
│  [Alert & Escalation Subsystem] ──► [Renewal Pipeline] ──► [Analytics & Reporting]     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             SPECIALIZED ECOSYSTEM EXTENSIONS                           │
│  [Professional Matter Management] ◄──► [Consultation & Directory] ◄──► [Billing/Stripe]│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Module Breakdown & Technical Dependencies
1. **Authentication & Identity Service:** Implements Argon2id password hashing, OAuth2 (Google, Microsoft Azure AD), JWT issuance, refresh token rotation, and MFA (TOTP). *Dep: None.*
2. **Organization & Multi-Tenancy Service:** Handles tenant registration, workspace settings, domain verification, and member invitations. *Dep: Auth.*
3. **Document Ingestion & Storage Service:** Direct upload via presigned S3 URLs, antivirus scanning (ClamAV container), MIME validation, SHA-256 integrity checks. *Dep: Auth, Org.*
4. **Contract Repository & Versioning:** Tracks parent-child document lineage, version numbers (`v1.0`, `v1.1`, `v2.0`), execution state, and metadata. *Dep: Storage, Org.*
5. **Clause Extraction & Classification:** Structural parsing of legal text into discrete clause entities (Indemnity, Termination, Liability, Governing Law, IP). *Dep: Repository, Celery.*
6. **Risk Analysis & Scoring Engine:** Maps detected clauses against risk taxonomies, identifies missing clauses, and computes composite risk ratings (1-100). *Dep: Clause Extraction, Playbook.*
7. **Legal Playbook Engine:** Maintains an organization's standard, fallback, and unacceptable clause language with fallback guidance for negotiators. *Dep: Org.*
8. **AI Redlining & Tracked Changes:** Generates line-by-line strike-through/insert redline diffs based on company playbooks, producing standard docx/JSON delta formats. *Dep: Risk Analysis, Playbook.*
9. **Approval Workflow Engine:** Configurable directed acyclic graph (DAG) routing requests across departments based on contract value, department, and risk level. *Dep: Repository, RBAC.*
10. **Obligation Extraction & Contract Watch:** Identifies explicit party duties, recurring deliverables, notice windows, and penalty clauses; monitors status against real-world dates. *Dep: Repository, Risk Analysis.*
11. **Evidence & Audit Trail:** Immutable, append-only log capturing user actions, IP addresses, document checksums, and compliance evidence uploads. *Dep: All modules.*
12. **Professional Matter & Consultation Service:** Connects personal/business users with legal professionals, manages isolated matter workspaces, and tracks advisory notes. *Dep: Repository, Auth.*

---

## 6. END-TO-END USER JOURNEYS

### Journey 1: Personal User (Lease / Employment Review Flow)
```text
[Sign Up / Login]
      │
      ▼
[Select "Personal" Account Mode]
      │
      ▼
[Personal Clean Dashboard]
      │
      ▼
[Upload Contract (e.g., Employment Agreement .pdf)]
      │
      ▼ (Background Queue: OCR + Text Parsing + AI Risk Audit)
[Live SSE Progress: "Extracting Clauses..." -> "Scanning Non-Compete..." -> "Evaluating IP Assignment..."]
      │
      ▼
[Review Interactive Risk Report]
  - Plain-Language Summary: "What you need to know"
  - High-Risk Alert: "3-Year Worldwide Non-Compete Clause Detected"
  - Missing Clause: "No Clear Severance Provision Found"
      │
      ▼
[Trigger AI Redline Suggestion]
  - Suggests reasonable 6-month non-compete restricted to direct competitors.
  - Generates downloadable negotiation letter draft.
      │
      ▼
[Activate "Contract Watch"]
  - Automatically schedules 90-day probation review deadline and annual notice dates.
      │
      ▼ (Optional Escalation)
[Click "Consult a Verified Lawyer"]
  - Selects verified employment lawyer from directory -> Shares matter bundle -> Books consultation.
```

### Journey 2: Business User (Enterprise SaaS Procurement Flow)
```text
[Org Owner Creates Org "Acme Corp" & Invites Legal, Finance, Procurement]
      │
      ▼
[Procurement Specialist Initiates Contract Request: Vendor "CloudStack", $120,000/yr]
      │
      ▼
[System Matches Approval Rule: Value > $50,000 => Multi-Stage DAG: Procurement -> Legal -> Finance -> VP]
      │
      ▼
[Vendor MSA Uploaded (.docx)]
      │
      ▼ (Asynchronous AI Ingestion & Playbook Matching)
[AI Flags Playbook Conflicts:
  - Vendor Liability: Uncapped (Playbook: Capped at 12 Months Fees)
  - Governing Law: Delaware (Playbook: New York Standard)
  - Payment Terms: Net 15 (Playbook: Net 45 Minimum)]
      │
      ▼
[Legal Reviewer Launches Redline Studio]
  - Auto-applies Playbook Fallback Clause for Liability Cap.
  - Adds comments explaining company standard.
  - Exports tracked changes DOCX for vendor negotiation.
      │
      ▼
[Vendor Agrees; Final Clean Version Uploaded (v2.0 Executed)]
      │
      ▼
[Approval Sequence Triggered -> Legal Signs Off -> Finance Signs Off -> VP Approves]
      │
      ▼
[Contract Marked "Executed" -> Status set to "Active"]
      │
      ▼
[Contract Watch Auto-Extracts Obligations:
  - Acme duty: SOC2 Type II report submission by Oct 31
  - Vendor duty: 99.9% uptime SLA report monthly
  - Renewal notice window: 60 days prior to expiry (Aug 15)]
      │
      ▼
[Compliance Monitor tracks deadlines; notifies responsible owners before renewal lock-in]
```

### Journey 3: Professional / Legal Practitioner (Matter Defense Flow)
```text
[Law Firm Signs Up as Professional Workspace "Sterling & Partners"]
      │
      ▼
[Lawyer Configures Public Profile & Verification Credentials (Bar Council / State Bar ID)]
      │
      ▼
[Incoming Client Request from Business User OR Direct Matter Creation: "Fintech Regulatory Compliance"]
      │
      ▼
[Matter Workspace Created: Complete Data Isolation from other Firm Clients]
      │
      ▼
[Upload 5 Interconnected Project Documents (SaaS Agreement, DPA, SLA, Security Schedule)]
      │
      ▼
[Matter-Scoped Multi-Document AI Querying:
  "Does the SLA remedy clause conflict with the limitation of liability in the main agreement?"]
      │
      ▼
[AI Cites Exact Cross-Contract Provisions with Side-by-Side Snippets]
      │
      ▼
[Lawyer Annotates, Redlines, and Prepares Formal Legal Memorandum]
      │
      ▼
[Exports Client-Ready Redline Package & Completed Matter Documentation]
```

---

## 7. CONTRACT LIFECYCLE STATE MACHINE & TRANSITIONS

A contract moves through a deterministic finite state machine (FSM). Unauthorized state jumps are blocked by transition validation hooks in the database and API.

```
                  ┌──────────────┐
                  │    DRAFT     │◄──────────────────────────────────┐
                  └──────┬───────┘                                   │
                         │ (Submit for Review)                       │
                         ▼                                           │
                  ┌──────────────┐                                   │
                  │ UNDER_REVIEW │                                   │
                  └──────┬───────┘                                   │
                         │ (Launch Redlines / Negotiations)          │
                         ▼                                           │
                  ┌──────────────┐                                   │
                  │ NEGOTIATION  │                                   │
                  └──────┬───────┘                                   │
                         │ (Agreement Reached -> Submit Approval)    │
                         ▼                                           │
               ┌───────────────────┐                                 │
               │ PENDING_APPROVAL  │─────────────────────────────────┤  Rework Needed)
               └─────────┬─────────┘                                 │
                         │ (All Approvers Sign Off)                  │
                         ▼                                           │
                  ┌──────────────┐                                   │
                  │   APPROVED   │                                   │
                  └──────┬───────┘                                   │
                         │ (Sent to Signature)                       │
                         ▼                                           │
               ┌───────────────────┐                                 │
               │ PENDING_SIGNATURE │                                 │
               └─────────┬─────────┘                                 │
                         │ (All Parties Sign & Upload Executed)      │
                         ▼                                           │
                  ┌──────────────┐                                   │
                  │   EXECUTED   │                                   │
                  └──────┬───────┘                                   │
                         │ (Effective Date Reached -> Contract Watch)│
                         ▼                                           │
                  ┌──────────────┐                                   │
                  │    ACTIVE    │                                   │
                  └──┬───┬───┬───┘                                   │
                     │   │   │                                       │
        ┌────────────┘   │   └────────────┐                          │
        ▼                ▼                ▼                          │
┌──────────────┐ ┌──────────────┐ ┌───────────────┐                  │
│   AT_RISK    │ │POTENTIAL_    │ │IN_RENEWAL_    │                  │
│(Overdue Obl.)│ │NON_COMPLIANCE│ │WINDOW         │                  │
└───────┬──────┘ └───────┬──────┘ └───────┬───────┘                  │
        │                │                │                          │
        └────────────┐   │   ┌────────────┘                          │
                     ▼   ▼   ▼                                       │
                  ┌──────────────┐                                   │
                  │   RENEWED    │───────────────────────────────────┘
                  └──────────────┘ (Spawns New Contract Version / Cycle)
                         │
                         ▼
             ┌────────────────────────┐
             │ EXPIRED  /  TERMINATED │
             └────────────────────────┘
```

### State Transition Authority Matrix

| Origin State | Target State | Authorized Trigger Roles | Validation Condition |
|---|---|---|---|
| `DRAFT` | `UNDER_REVIEW` | Document Creator, Legal Reviewer | File parsed, metadata validated, at least 1 clause detected |
| `UNDER_REVIEW` | `NEGOTIATION` | Legal Manager, Legal Reviewer | Initial risk analysis completed |
| `NEGOTIATION` | `PENDING_APPROVAL`| Legal Manager, Org Owner | Redlines resolved or marked pending sign-off |
| `PENDING_APPROVAL`| `APPROVED` | Defined Approvers in DAG Sequence | 100% required approval steps marked `APPROVED` |
| `PENDING_APPROVAL`| `DRAFT` | Any Assigned Approver | Rejection reason logged in audit trail |
| `APPROVED` | `PENDING_SIGNATURE`| Legal Reviewer, Org Owner | Clean executable document generated |
| `PENDING_SIGNATURE`| `EXECUTED` | Legal Manager, Org Owner, Personal| Signed document uploaded; cryptographic hash recorded |
| `EXECUTED` | `ACTIVE` | System (Contract Watch Daemon) | Current Date >= Contract `effective_date` |
| `ACTIVE` | `AT_RISK` | System (Contract Watch Daemon) | Critical obligation overdue by > 24 hours |
| `ACTIVE` | `POTENTIAL_NON_COMPLIANCE`| Compliance Officer, System | Evidence rejected or breach notice logged |
| `ACTIVE` | `IN_RENEWAL_WINDOW`| System (Contract Watch Daemon) | Current Date >= (`expiry_date` - `renewal_notice_period_days`) |
| `IN_RENEWAL_WINDOW`| `RENEWED` | Org Owner, Legal Manager | Renewal agreement attached; new term dates defined |
| `ACTIVE` | `EXPIRED` | System (Contract Watch Daemon) | Current Date > `expiry_date` without renewal trigger |
| `ANY_ACTIVE` | `TERMINATED` | Org Owner, Legal Manager | Early termination notice and legal justification logged |

---

## 8. NORMALIZED RELATIONAL DATABASE ARCHITECTURE (POSTGRESQL + PGVECTOR)

The data model utilizes PostgreSQL 16+ with the `pgvector` extension. Every tenant-scoped table strictly enforces foreign keys back to `organizations.id`.

### Textual Entity-Relationship Diagram (ERD)

```text
organizations 1 ────< users
organizations 1 ────< departments
organizations 1 ────< vendors
organizations 1 ────< playbooks 1 ────< playbook_clauses
organizations 1 ────< approval_workflows 1 ────< approval_workflow_steps
organizations 1 ────< contract_templates
organizations 1 ────< contracts 1 ────< contract_versions 1 ────< contract_clauses
                                  1 ────< contract_parties
                                  1 ────< contract_risks
                                  1 ────< contract_comments
                                  1 ────< contract_approvals 1 ────< approval_decisions
                                  1 ────< obligations 1 ────< obligation_evidence
                                  1 ────< compliance_events
                                  1 ────< contract_renewals
                                  1 ────< ai_analyses
                                  1 ────< ai_conversations 1 ────< ai_messages

law_firms 1 ────< lawyers
law_firms 1 ────< clients 1 ────< matters 1 ────< contracts
users 1 ────< consultations >──── 1 lawyers
organizations 1 ────< audit_logs
```

### Table Definitions & Core Schemas

#### 1. Core Identity & Multi-Tenancy
- **`organizations`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `name`: `VARCHAR(255) NOT NULL`
  - `slug`: `VARCHAR(100) UNIQUE NOT NULL`
  - `account_type`: `VARCHAR(30) NOT NULL CHECK (account_type IN ('PERSONAL', 'BUSINESS', 'PROFESSIONAL', 'PLATFORM_ADMIN'))`
  - `subscription_tier`: `VARCHAR(50) DEFAULT 'FREE'`
  - `storage_quota_bytes`: `BIGINT DEFAULT 10737418240` (10 GB default)
  - `settings`: `JSONB DEFAULT '{}'`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`
  - `updated_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`departments`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
  - `name`: `VARCHAR(100) NOT NULL` (e.g., 'Legal', 'Procurement', 'Finance', 'HR')
  - `budget_currency`: `VARCHAR(3) DEFAULT 'USD'`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`users`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `email`: `VARCHAR(255) UNIQUE NOT NULL`
  - `password_hash`: `VARCHAR(255)` (Null if purely SSO)
  - `full_name`: `VARCHAR(255) NOT NULL`
  - `avatar_url`: `TEXT`
  - `is_verified`: `BOOLEAN DEFAULT FALSE`
  - `is_super_admin`: `BOOLEAN DEFAULT FALSE`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`organization_members`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
  - `user_id`: `UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
  - `department_id`: `UUID REFERENCES departments(id) ON DELETE SET NULL`
  - `role`: `VARCHAR(50) NOT NULL` (e.g., 'OWNER', 'ADMIN', 'LEGAL_REVIEWER', 'EMPLOYEE')
  - `status`: `VARCHAR(30) DEFAULT 'ACTIVE'`
  - `UNIQUE(organization_id, user_id)`

#### 2. Contracts, Versions & Storage
- **`contracts`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
  - `matter_id`: `UUID REFERENCES matters(id) ON DELETE SET NULL`
  - `vendor_id`: `UUID REFERENCES vendors(id) ON DELETE SET NULL`
  - `department_id`: `UUID REFERENCES departments(id) ON DELETE SET NULL`
  - `title`: `VARCHAR(500) NOT NULL`
  - `contract_type`: `VARCHAR(100) NOT NULL` (e.g., 'NDA', 'MSA', 'SLA', 'DPA', 'EMPLOYMENT', 'LEASE')
  - `status`: `VARCHAR(50) NOT NULL DEFAULT 'DRAFT'`
  - `current_version_id`: `UUID` -- Forward reference updated upon version creation
  - `contract_value`: `NUMERIC(15, 2)`
  - `currency`: `VARCHAR(3) DEFAULT 'USD'`
  - `effective_date`: `DATE`
  - `expiry_date`: `DATE`
  - `auto_renew`: `BOOLEAN DEFAULT FALSE`
  - `renewal_notice_period_days`: `INT DEFAULT 30`
  - `governing_law`: `VARCHAR(100)`
  - `composite_risk_score`: `INT` (0 - 100)
  - `created_by_user_id`: `UUID REFERENCES users(id)`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`
  - `updated_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`contract_versions`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `contract_id`: `UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE`
  - `version_number`: `VARCHAR(20) NOT NULL` (e.g., 'v1.0', 'v1.1', 'v2.0')
  - `file_storage_path`: `TEXT NOT NULL` (S3 Key)
  - `file_mime_type`: `VARCHAR(100) NOT NULL`
  - `file_byte_size`: `BIGINT NOT NULL`
  - `sha256_checksum`: `VARCHAR(64) NOT NULL`
  - `raw_text`: `TEXT`
  - `structured_prosemirror_json`: `JSONB`
  - `change_summary`: `TEXT`
  - `created_by_user_id`: `UUID REFERENCES users(id)`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`contract_parties`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `contract_id`: `UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE`
  - `party_name`: `VARCHAR(255) NOT NULL`
  - `party_role`: `VARCHAR(50) NOT NULL` (e.g., 'DISCLOSING_PARTY', 'SERVICE_PROVIDER', 'EMPLOYER', 'TENANT')
  - `signatory_name`: `VARCHAR(255)`
  - `signatory_email`: `VARCHAR(255)`
  - `signed_at`: `TIMESTAMPTZ`

#### 3. AI Clause Extraction, Risk & Vector Embeddings
- **`contract_clauses`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `contract_version_id`: `UUID NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE`
  - `clause_type`: `VARCHAR(100) NOT NULL` (e.g., 'LIMITATION_OF_LIABILITY', 'INDEMNIFICATION', 'TERMINATION_FOR_CONVENIENCE')
  - `section_number`: `VARCHAR(50)`
  - `clause_text`: `TEXT NOT NULL`
  - `start_char_idx`: `INT NOT NULL`
  - `end_char_idx`: `INT NOT NULL`
  - `risk_level`: `VARCHAR(20) NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))`
  - `risk_reasoning`: `TEXT`
  - `playbook_deviation`: `BOOLEAN DEFAULT FALSE`
  - `embedding`: `vector(1536)` (Optimized with HNSW indexing)
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`contract_risks`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `contract_id`: `UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE`
  - `contract_version_id`: `UUID NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE`
  - `clause_id`: `UUID REFERENCES contract_clauses(id) ON DELETE SET NULL`
  - `severity`: `VARCHAR(20) NOT NULL CHECK (severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'))`
  - `risk_title`: `VARCHAR(255) NOT NULL`
  - `potential_impact`: `TEXT NOT NULL`
  - `remedy_recommendation`: `TEXT NOT NULL`
  - `status`: `VARCHAR(30) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'MITIGATED', 'ACCEPTED'))`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

#### 4. Approval Workflows & Requests
- **`approval_workflows`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
  - `name`: `VARCHAR(255) NOT NULL`
  - `trigger_rules`: `JSONB NOT NULL` (e.g., `{"min_value": 50000, "contract_type": "PROCUREMENT"}`)
  - `is_active`: `BOOLEAN DEFAULT TRUE`

- **`approval_workflow_steps`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `workflow_id`: `UUID NOT NULL REFERENCES approval_workflows(id) ON DELETE CASCADE`
  - `step_order`: `INT NOT NULL`
  - `approver_role`: `VARCHAR(50)`
  - `approver_user_id`: `UUID REFERENCES users(id)`
  - `approver_department_id`: `UUID REFERENCES departments(id)`
  - `required_approvals_count`: `INT DEFAULT 1`

- **`contract_approvals`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `contract_id`: `UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE`
  - `workflow_id`: `UUID REFERENCES approval_workflows(id)`
  - `overall_status`: `VARCHAR(30) DEFAULT 'IN_PROGRESS'`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`approval_decisions`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `approval_id`: `UUID NOT NULL REFERENCES contract_approvals(id) ON DELETE CASCADE`
  - `step_order`: `INT NOT NULL`
  - `assigned_user_id`: `UUID NOT NULL REFERENCES users(id)`
  - `decision`: `VARCHAR(30) DEFAULT 'PENDING' CHECK (decision IN ('PENDING', 'APPROVED', 'REJECTED'))`
  - `comments`: `TEXT`
  - `decided_at`: `TIMESTAMPTZ`

#### 5. Contract Watch & Compliance Engine
- **`obligations`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `contract_id`: `UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE`
  - `clause_id`: `UUID REFERENCES contract_clauses(id)`
  - `obligor_party`: `VARCHAR(255) NOT NULL` (Who must perform)
  - `obligee_party`: `VARCHAR(255) NOT NULL` (To whom)
  - `title`: `VARCHAR(255) NOT NULL`
  - `description`: `TEXT NOT NULL`
  - `due_date`: `DATE`
  - `frequency`: `VARCHAR(30) DEFAULT 'ONE_TIME'` (ONE_TIME, MONTHLY, QUARTERLY, ANNUALLY)
  - `financial_penalty_amount`: `NUMERIC(15, 2)`
  - `responsible_user_id`: `UUID REFERENCES users(id)`
  - `status`: `VARCHAR(30) DEFAULT 'UPCOMING' CHECK (status IN ('UPCOMING', 'DUE_SOON', 'FULFILLED', 'OVERDUE', 'POTENTIAL_BREACH'))`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`obligation_evidence`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `obligation_id`: `UUID NOT NULL REFERENCES obligations(id) ON DELETE CASCADE`
  - `file_storage_path`: `TEXT NOT NULL`
  - `file_name`: `VARCHAR(255) NOT NULL`
  - `uploaded_by_user_id`: `UUID NOT NULL REFERENCES users(id)`
  - `verification_notes`: `TEXT`
  - `verified_by_user_id`: `UUID REFERENCES users(id)`
  - `verified_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`compliance_events`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `contract_id`: `UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE`
  - `obligation_id`: `UUID REFERENCES obligations(id) ON DELETE SET NULL`
  - `event_type`: `VARCHAR(50) NOT NULL` (e.g., 'DEADLINE_MISSED', 'EVIDENCE_REJECTED', 'CRITICAL_RISK_FLAGGED')
  - `event_severity`: `VARCHAR(20) NOT NULL` (LOW, MEDIUM, HIGH, CRITICAL)
  - `status_label`: `VARCHAR(100) NOT NULL` (Always non-adjudicative: "Potential Contractual Non-Compliance Detected")
  - `human_resolved`: `BOOLEAN DEFAULT FALSE`
  - `resolution_notes`: `TEXT`
  - `resolved_by_user_id`: `UUID REFERENCES users(id)`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

#### 6. Enterprise Legal Playbooks & Vendors
- **`playbooks`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
  - `title`: `VARCHAR(255) NOT NULL`
  - `contract_type`: `VARCHAR(100) NOT NULL`
  - `is_default`: `BOOLEAN DEFAULT FALSE`

- **`playbook_clauses`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `playbook_id`: `UUID NOT NULL REFERENCES playbooks(id) ON DELETE CASCADE`
  - `clause_category`: `VARCHAR(100) NOT NULL`
  - `standard_preferred_text`: `TEXT NOT NULL`
  - `fallback_acceptable_text`: `TEXT NOT NULL`
  - `prohibited_terms`: `TEXT[]` (List of trigger tokens or terms)
  - `negotiation_guidance`: `TEXT`

- **`vendors`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
  - `name`: `VARCHAR(255) NOT NULL`
  - `contact_email`: `VARCHAR(255)`
  - `website`: `VARCHAR(255)`
  - `overall_vendor_risk_rating`: `VARCHAR(20) DEFAULT 'MEDIUM'`
  - `soc2_certified`: `BOOLEAN DEFAULT FALSE`
  - `gdpr_compliant`: `BOOLEAN DEFAULT FALSE`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

#### 7. Legal Professionals, Law Firms & Consultations
- **`law_firms`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
  - `firm_name`: `VARCHAR(255) NOT NULL`
  - `bar_registration_number`: `VARCHAR(100)`
  - `verified`: `BOOLEAN DEFAULT FALSE`

- **`lawyers`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `user_id`: `UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
  - `law_firm_id`: `UUID REFERENCES law_firms(id) ON DELETE SET NULL`
  - `jurisdiction`: `VARCHAR(100) NOT NULL`
  - `practice_areas`: `TEXT[]` (e.g., 'Employment', 'Corporate Tech', 'Real Estate')
  - `years_of_experience`: `INT`
  - `hourly_rate`: `NUMERIC(10, 2)`
  - `bio`: `TEXT`
  - `is_available_for_consultation`: `BOOLEAN DEFAULT TRUE`

- **`matters`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE`
  - `client_id`: `UUID NOT NULL REFERENCES users(id)`
  - `lead_lawyer_id`: `UUID NOT NULL REFERENCES lawyers(id)`
  - `matter_name`: `VARCHAR(255) NOT NULL`
  - `matter_status`: `VARCHAR(50) DEFAULT 'OPEN'`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

- **`consultations`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `requester_user_id`: `UUID NOT NULL REFERENCES users(id)`
  - `lawyer_id`: `UUID NOT NULL REFERENCES lawyers(id)`
  - `contract_id`: `UUID REFERENCES contracts(id) ON DELETE SET NULL`
  - `scheduled_time`: `TIMESTAMPTZ NOT NULL`
  - `duration_minutes`: `INT DEFAULT 30`
  - `status`: `VARCHAR(30) DEFAULT 'REQUESTED' CHECK (status IN ('REQUESTED', 'CONFIRMED', 'COMPLETED', 'CANCELLED'))`
  - `meeting_link`: `TEXT`
  - `client_notes`: `TEXT`
  - `lawyer_summary`: `TEXT`

#### 8. Audit Logs & System Telemetry
- **`audit_logs`**
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `organization_id`: `UUID REFERENCES organizations(id) ON DELETE SET NULL`
  - `user_id`: `UUID REFERENCES users(id) ON DELETE SET NULL`
  - `action`: `VARCHAR(100) NOT NULL` (e.g., 'CONTRACT_VIEWED', 'REDLINE_ACCEPTED', 'ROLE_CHANGED')
  - `resource_type`: `VARCHAR(50) NOT NULL`
  - `resource_id`: `UUID NOT NULL`
  - `ip_address`: `INET`
  - `user_agent`: `TEXT`
  - `change_payload`: `JSONB`
  - `created_at`: `TIMESTAMPTZ DEFAULT NOW()`

---

## 9. MULTI-TENANCY & TENANT DATA ISOLATION STRATEGY

Contractly utilizes a **Logical Multi-Tenancy with Tenant Discriminator Column & PostgreSQL Row-Level Security (RLS)** architecture.

```text
┌────────────────────────────────────────────────────────┐
│ Incoming Request: Authorization: Bearer <JWT>          │
│ Header: X-Tenant-ID: 7a82b9e1-....                     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ FastAPI Dependency: verify_tenant_membership()         │
│ - Confirms User belongs to Organization                │
│ - Extracts User Role & Permissions for that Tenant     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ PostgreSQL Connection Session Context Setting:         │
│ SET LOCAL app.current_tenant_id = '7a82b9e1-....';     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ PostgreSQL Row-Level Security (RLS) Policy Activated:  │
│ CREATE POLICY tenant_isolation_policy ON contracts     │
│   USING (organization_id =                             │
│     current_setting('app.current_tenant_id')::UUID);   │
└────────────────────────────────────────────────────────┘
```

### Defense-in-Depth Tenant Protection
1. **Application-Layer Scoping:** Every SQL query generated via the ORM/query builder automatically appends `WHERE organization_id = :tenant_id`.
2. **Database-Layer Enforcement (PostgreSQL RLS):** Even if an application developer forgets a `WHERE` clause, PostgreSQL enforces the policy at the database engine level, rejecting access if the tenant variable does not match.
3. **Object Storage Boundary (S3 Key Namespacing):** Document storage paths are partitioned:
   `s3://contractly-vault/{organization_id}/contracts/{contract_id}/{version_id}/{hash}.pdf`
   No file is ever requested via public URLs; all access requires short-lived presigned URLs (expires in 15 minutes) validated against the user's tenant session.
4. **Vector Retrieval Partitioning:** The vector database query always contains metadata filter clauses:
   ```sql
   SELECT clause_text, 1 - (embedding <=> :query_vec) AS similarity
   FROM contract_clauses cc
   JOIN contract_versions cv ON cc.contract_version_id = cv.id
   JOIN contracts c ON cv.contract_id = c.id
   WHERE c.organization_id = :current_tenant_id
   ORDER BY embedding <=> :query_vec LIMIT 5;
   ```
   Cross-tenant vector bleeding is impossible because non-matching rows are excluded from the index scan.

---

## 10. DOCUMENT PIPELINE ARCHITECTURE

The document processing pipeline converts unstructured legal documents into standardized tokens, structured JSON, vector embeddings, and tracked-changes diffs.

```text
┌──────────────┐
│ PDF/DOCX/TXT │
└──────┬───────┘
       │ 1. Direct Presigned Upload (SHA-256 Checksum Computed by Client & Server)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│ S3-Compatible Encrypted Object Store (SSE-KMS Encryption)       │
└──────┬──────────────────────────────────────────────────────────┘
       │ 2. Celery Event Trigger: `process_document_pipeline.delay(version_id)`
       ▼
┌─────────────────────────────────────────────────────────────────┐
│ File Validation & Antivirus Sandbox (ClamAV Docker Container)   │
└──────┬──────────────────────────────────────────────────────────┘
       │ 3. Text Extraction Router
       ├─────────────────────────────────┬────────────────────────┐
       ▼ (Digital PDF)                   ▼ (Scanned / Image PDF)  ▼ (Word DOCX)
┌──────────────────────┐        ┌───────────────────────┐ ┌──────────────────────┐
│ PyMuPDF (fitz)       │        │ OCR Pipeline:         │ │ python-docx          │
│ Fast direct text     │        │ Tesseract / PaddleOCR │ │ Native XML parsing   │
│ & layout extraction  │        │ Table detection       │ │ Paragraph & style map│
└──────┬───────────────┘        └──────┬────────────────┘ └──────┬───────────────┘
       └─────────────────────────────────┼────────────────────────┘
                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Document Normalization Engine: Markdown / ProseMirror Schema    │
│ - Standardizes headers, numbered clauses (1.1, 1.2), bolding    │
│ - Eliminates page breaks, headers/footers, and watermarks       │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Structural Legal Clause Chunking Engine                         │
│ - Boundary detection: splits on recognized legal section breaks  │
│ - Preserves cross-clause references and definition clauses      │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ├─────────────────────────────────┬────────────────────────┐
       ▼                                 ▼                        ▼
┌──────────────────────┐        ┌───────────────────────┐ ┌──────────────────────┐
│ Metadata Extraction  │        │ Dense Vector Embed    │ │ Keyword Index        │
│ Parties, Dates, Value│        │ text-embedding-3-small│ │ PostgreSQL Full-Text │
│ Governing Law        │        │ 1536 Dimensions       │ │ (tsvector - English) │
└──────────────────────┘        └──────┬────────────────┘ └──────┬───────────────┘
                                       ▼                         ▼
                                ┌────────────────────────────────────────┐
                                │ Hybrid Vector + BM25 Storage (pgvector)│
                                └────────────────────────────────────────┘
```

---

## 11. AI / RAG ARCHITECTURE & AGENT CLASSIFICATION

Contractly does not rely on monolithic, uncontrolled LLM prompts. Instead, it uses a multi-agent orchestrated pipeline separating non-deterministic LLM analysis from deterministic rules.

```
                           ┌────────────────────────────┐
                           │      Contract Context      │
                           └─────────────┬────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │ NON-DETERMINISTIC AGENTS  │                   │    DETERMINISTIC ENGINES  │
   └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                 │                                               │
   ┌─────────────┴─────────────┐                   ┌─────────────┴─────────────┐
   │ 1. Clause Extractor Agent │                   │ 1. Mathematical Value Calc│
   │ 2. Risk Scorer Agent      │                   │ 2. FSM State Transition   │
   │ 3. Redline Drafting Agent │                   │ 3. Deadline / Cron Watch  │
   │ 4. Grounded Q&A Agent     │                   │ 4. RBAC Permission Checks │
   │ 5. Negotiation Assistant  │                   │ 5. Playbook Strict Regex  │
   └───────────────────────────┘                   └───────────────────────────┘
```

### Feature Implementation Matrix

| Platform Feature | Primary Engine Category | Technology / Pattern | Technical Justification |
|---|---|---|---|
| **Clause Boundary Detection** | Hybrid: Rule Engine + LLM Fallback | Regex heuristic + Few-Shot LLM | Section numbering (1.1, 2.0) is predictable; LLM only needed for unstructured narrative contracts. |
| **Clause Categorization** | LLM API | Fine-tuned or Zero-Shot Prompting with JSON schema | Categorizing subtle indemnities or IP grants requires deep semantic context over token structure. |
| **Contract Risk Score (0-100)**| Deterministic Formula over AI Flags | Weighted scoring formula | Aggregating severity into a score must be reproducible and explainable to legal teams. |
| **Contract Q&A** | RAG (Hybrid Retrieval + Grounded LLM)| Vector + BM25 + Citation Prompts | Prevents hallucination; model is strictly constrained to cite exact clause IDs and line numbers. |
| **Playbook Compliance** | Hybrid: Rule Engine + RAG | Exact token search + Semantic cosine similarity | Detects prohibited terms via fast regex, and conceptual mismatches via embeddings against standard playbook terms. |
| **Redline Generation** | LLM API (Structured Output) | Pydantic JSON Output (`original_text`, `suggested_text`, `reasoning`) | Synthesizing legally sound, polished contract language with track-changes semantics. |
| **Contract Comparison** | Deterministic Backend Logic | Levenshtein / Myers Diff Algorithm + Semantic Grouping | Word-level diffing must be 100% mathematically precise; LLM is only used to summarize the impact of the diff. |
| **Obligation Deadline Tracking**| Deterministic Backend Logic | Cron Job + PostgreSQL Timestamps | Date math (e.g., "30 days after effective date") must never be delegated to non-deterministic LLM execution. |
| **Non-Compliance Warnings** | Deterministic Rule Engine | Boolean conditional triggers | Determining if an upload is past a recorded date is a deterministic check, not a statistical prediction. |

---

## 12. DATASET STRATEGY & SYNTHETIC DATA GENERATION

To ensure zero risk of customer document leakage and zero data contamination, Contractly establishes a strict data firewall:

```text
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│     EXTERNAL PUBLIC DATASETS    │       │     SYNTHETIC BENCHMARK DATA    │
│  CUAD (Atticus Project - 510)   │       │  10 Distinct Contract Archetypes│
│  ContractNLI (3-way NLI checks) │       │  Programmatically Parameterized │
│  MAUD (M&A Deal Provisions)     │       │  Injectable Risk Anomalies      │
└────────────────┬────────────────┘       └────────────────┬────────────────┘
                 │                                         │
                 ▼                                         ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                     OFFLINE EVALUATION & PROMPT BENCHMARK                 │
│  - Never touches production customer data                                 │
│  - Used to benchmark Clause Extraction Precision/Recall & Redline Quality │
└───────────────────────────────────────────────────────────────────────────┘
```

### 1. Public Legal Datasets Usage
- **CUAD (Contract Understanding Atticus Dataset):** 510 contracts labeled with 41 clause types. Used exclusively to build evaluation benchmarks for our Clause Classification Agent.
- **ContractNLI:** Used to benchmark natural language inference ("Does this contract clause entail, contradict, or remain neutral toward Playbook Policy X?").
- **MAUD:** Used for complex transactional and termination clause edge-case testing.

### 2. Synthetic Dataset Generation Plan
We design a programmatic generator script producing 1,000 synthetic, jurisdiction-varied contracts spanning 10 key categories:
1. **SaaS Master Services Agreements (MSAs)** (US-DE, US-CA, UK, India)
2. **Mutual Non-Disclosure Agreements (NDAs)** (Injecting unfair 5-year trade-secret survival terms)
3. **Executive & Standard Employment Contracts** (Injecting non-compete clauses)
4. **Data Processing Agreements (DPAs)** (Evaluating GDPR Article 28 compliance)
5. **Vendor Procurement & Hardware Supply Agreements** (Liquidated damages, delayed delivery penalties)
6. **Commercial Real Estate Leases** (Maintenance, repair, and security deposit terms)
7. **Independent Contractor / Freelance Agreements** (IP assignment terms)
8. **Intellectual Property License Agreements** (Royalty and auditing clauses)
9. **Service Level Agreements (SLAs)** (Uptime tiers, service credit formulas)
10. **Consulting Framework Agreements** (Scope of work definitions)

### 3. Synthetic Anomaly Injection
Each synthetic document is generated with deliberate, ground-truth-labeled anomalies:
- *Anomaly Type A:* Uncapped liability in vendor agreements.
- *Anomaly Type B:* Auto-renewal with impossible notice windows (e.g., 180 days advance notice).
- *Anomaly Type C:* Unilateral indemnity holding only the customer liable.
- *Anomaly Type D:* Silent IP transfer transferring customer pre-existing IP to the vendor.

*Privacy Guarantee:* Customer documents uploaded to production are never added to prompt evaluation benchmarks, are never retained in shared training pools, and are stored with tenant-specific encryption keys.

---

## 13. REDLINING ARCHITECTURE & TRACKED-CHANGES ENGINE

The redline engine generates legal redlines compatible with corporate legal workflows.

```text
┌───────────────────────────────┐
│ Original Contract Clause Text │
└───────────────┬───────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Playbook Matcher: Compares against Organization's Playbook Clause       │
│ Identifies: Deviations, Risk Magnitude, Required Corporate Fallback     │
└───────────────┬─────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ AI Redlining Agent (Structured Output Prompt)                           │
│ Input: Original Clause, Playbook Rule, Negotiation Stance (Strict/Mild) │
│ Output JSON:                                                            │
│ {                                                                       │
│   "target_span": "Vendor liability shall be unlimited...",              │
│   "replacement_text": "Vendor liability shall be capped at 12 mo...",   │
│   "rationale": "Capping exposure pursuant to Acme Playbook Rule 4.2"    │
│ }                                                                       │
└───────────────┬─────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Deterministic Myers Diff / ProseMirror Delta Transformation Engine       │
│ Computes character-level and word-level diff spans                      │
└───────────────┬─────────────────────────────────────────────────────────┘
                │
                ├─────────────────────────────────┬───────────────────────┐
                ▼                                 ▼                       ▼
┌───────────────────────────────┐ ┌─────────────────────────────┐ ┌─────────────────────────────┐
│ In-App Interactive Redline    │ │ Word (.docx) Generator      │ │ PDF Audit Diff View         │
│ TipTap/ProseMirror DOM Nodes: │ │ `python-docx` XML Injection:│ │ Dual-column split view with │
│ `<span class="ins">...</span>`│ │ `<w:ins>`, `<w:del>`,       │ │ color-coded additions /     │
│ `<span class="del">...</span>`│ │ `<w:comment>` tracked markup│ │ deletions                   │
└───────────────────────────────┘ └─────────────────────────────┘ └─────────────────────────────┘
```

### Technical Workflow for .docx Tracked Changes
To ensure compatibility with Microsoft Word and enterprise legal teams:
1. The backend parses Word documents using `python-docx`.
2. Redlines are injected not as raw replaced text, but as native Word OpenXML tracked change tags:
   - `<w:del w:id="1" w:author="Contractly AI" w:date="2026-10-07T14:00:00Z"><w:r><w:t>original uncapped liability</w:t></w:r></w:del>`
   - `<w:ins w:id="2" w:author="Contractly AI" w:date="2026-10-07T14:00:00Z"><w:r><w:t>liability capped at fees paid in prior 12 months</w:t></w:r></w:ins>`
3. When the outside counterparty opens the exported `.docx` in Microsoft Word, native Track Changes mode is active, showing Contractly's proposed edits for review.

---

## 14. COMPLIANCE ENGINE & "CONTRACT WATCH"

Contract Watch serves as the continuous post-execution monitoring system.

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Executed Contract Activated                                               │
└─────────────────────┬─────────────────────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Obligation Extraction Agent: Parses structured duties                     │
│ Generates: { "due_date": "2026-12-01", "obligor": "Vendor", ... }         │
└─────────────────────┬─────────────────────────────────────────────────────┘
                      │
                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Contract Watch Daemon (Celery Beat Cron running hourly)                   │
│ Evaluates: `WHERE status = 'UPCOMING' AND due_date <= NOW() + INTERVAL`  │
└─────────────────────┬─────────────────────────────────────────────────────┘
                      │
                      ├──────────────────────┬──────────────────────────────┐
                      ▼                      ▼                              ▼
             [T-30 Days Notice]     [T-7 Days Notice]              [T-0 Day Due]
             Email & In-App Alert   High-Priority Alert            Action Required
                      │
                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Obligation Evidence Submission Portal                                     │
│ User uploads proof document (e.g., SOC2 Report, Insurance Certificate)     │
└─────────────────────┬─────────────────────────────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
[Evidence Submitted]      [No Evidence Submitted & Deadline Passed]
         │                         │
         ▼                         ▼
[Assigned Reviewer Verifies] ┌──────────────────────────────────────────────┐
         │                   │ Deterministic Flag Raised:                   │
         ▼                   │ "Potential Contractual Non-Compliance Detected"
[Status: FULFILLED]          └──────────────────────┬───────────────────────┘
                                                    │
                                                    ▼
                                     ┌──────────────────────────────┐
                                     │ Auto-Escalation Protocol:    │
                                     │ - Notify Legal Manager       │
                                     │ - Raise Vendor Risk Score    │
                                     │ - Create Audit Issue Ticket  │
                                     └──────────────────────────────┘
```

---

## 15. LEGAL SAFETY PRINCIPLES & GUARDRAILS

To protect users and maintain compliance with legal regulatory requirements, Contractly operates under strict **Non-Adjudicative Safety Constraints**.

### Explicit UI & Language Rules
1. **Forbidden Language (Strict Linter Rule):**
   - ❌ *"The counterparty has breached Section 12."*
   - ❌ *"This contract is illegal under state law."*
   - ❌ *"You are legally released from all duties."*
   - ❌ *"Contractly's legal determination is..."*
2. **Mandatory Safe Lexicon:**
   - ✅ *"Potential contractual non-compliance detected for Section 12."*
   - ✅ *"Provision appears inconsistent with standard statutory limits in [Jurisdiction]."*
   - ✅ *"Potential risk condition identified: Missing reciprocal indemnity."*
   - ✅ *"Review recommended by a qualified legal professional."*
3. **Ubiquitous System Disclaimer:**
   > *"Contractly is an intelligent legal operations and contract analysis tool, not a law firm, and does not provide legal advice. Analyses, risk ratings, and redlines are automated suggestions for review by qualified human operators."*
4. **Architectural Guardrail Enforcement:**
   Every LLM completion pipeline passes through an output validation guard:
   ```python
   def sanitize_legal_output(text: str) -> str:
       FORBIDDEN_ASSERTIONS = [
           (r"\bhas breached\b", "may be in potential non-compliance with"),
           (r"\bis a legal violation\b", "may present potential regulatory inconsistency"),
           (r"\byou are guaranteed\b", "terms indicate an intention to provide")
       ]
       for pattern, replacement in FORBIDDEN_ASSERTIONS:
           text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
       return text
   ```

---

## 16. NOTIFICATION & ESCALATION ARCHITECTURE

```text
┌────────────────────────────────────────────────────────┐
│ Trigger Source:                                        │
│ - Approval Requested / Step Complete                   │
│ - Contract Watch: Approaching Deadline / Overdue       │
│ - Redline Suggested / Comment Left                     │
│ - Consultation Booked                                  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Notification Dispatcher Service                        │
│ - Deduplication Buffer (Prevents alert fatigue)       │
│ - User Preference Matrix Lookup (Email vs In-App)      │
└──────────────────────────┬─────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌───────────────┐ ┌───────────────┐
│ In-App SSE / WS │ │ Transactional │ │ Organization  │
│ Real-time Bell  │ │ Email (Resend)│ │ Webhooks      │
│ Center & Toast  │ │ HTML Summary  │ │ (Slack/Teams) │
└─────────────────┘ └───────────────┘ └───────────────┘
```

### Escalation Matrix
- **Level 1 (T-30 Days):** Standard notification to assigned contract owner.
- **Level 2 (T-14 Days):** Reminder notification with daily digest inclusion.
- **Level 3 (T-3 Days):** Urgent priority alert to contract owner and department manager.
- **Level 4 (Deadline Breached):** Immediate escalation to Legal Manager and Organization Owner; contract status updated to `AT_RISK`.

---

## 17. SEARCH ARCHITECTURE (HYBRID RELATIONAL, VECTOR & NL-TO-SQL)

```text
                              ┌────────────────────────┐
                              │  Unified Search Bar    │
                              └───────────┬────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     [Structured / Natural Query]                     [Semantic Clause Query]
  "Show vendor contracts > $50k expiring"           "Find liability terms limiting
                  │                                  consequential damages"
                  ▼                                               │
┌───────────────────────────────────┐                             ▼
│ Safe NL-to-SQL Query Generator    │               ┌───────────────────────────┐
│ - LLM maps prompt to bounded JSON │               │ Dense Vector Embeddings   │
│   filter schema (NO raw SQL)      │               │ Cosine Similarity Search  │
│ - Pydantic parses validated JSON  │               │ pgvector: HNSW Index      │
│ - Query Builder executes query    │               └─────────────┬─────────────┘
└─────────────────┬─────────────────┘                             │
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────┐
                         │ Merged & Ranked Search Results  │
                         │ Multi-Tenant Filter Enforced    │
                         └─────────────────────────────────┘
```

### Safe NL-to-Structured Query Mapping
To prevent SQL injection or unvetted table access, user natural-language questions never convert directly into raw SQL strings. They convert into a strictly validated filter schema:

```json
{
  "contract_type": "VENDOR",
  "min_value": 50000,
  "expiry_date_within_days": 90,
  "sort_by": "expiry_date",
  "order": "ASC"
}
```
The FastAPI backend parses this structure using a Pydantic DTO and binds it to safe SQLAlchemy queries.

---

## 18. ANALYTICS & TELEMETRY ENGINE

### Analytics Dimensions by Workspace Tier

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PERSONAL DASHBOARD METRICS                                                             │
│ • Total Contracts Vaulted: [ 6 ]              • Healthy: [ 5 ]   • At Risk: [ 1 ]      │
│ • Upcoming Critical Dates: Lease Renewal in 42 Days (Notice required in 12 days)       │
│ • Identified Risk Flags: 1 Overly Broad Non-Compete                                    │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ BUSINESS / ENTERPRISE DASHBOARD METRICS                                                │
│ • Total Active Contract Value: $4.2M across 142 Active Agreements                      │
│ • Cycle Time to Signature: 12.4 Days avg (Down 3.2 days from last quarter)             │
│ • Risk Exposure Distribution: 68% Low, 24% Medium, 8% High                             │
│ • Approval Bottleneck Analytics: Legal Review averages 48h; Finance averages 6h        │
│ • Upcoming Renewal Pipeline: $840k expiring within 90-day window                       │
│ • Obligation Compliance Rate: 96.2% on-time evidentiary fulfillment                    │
│ • High-Risk Vendor Concentration: Top 3 vendors hold 42% of total risk points          │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PLATFORM ADMIN METRICS                                                                 │
│ • Global Tenants: 1,240 Organizations | Active Users: 8,420                            │
│ • AI Ingestion Throughput: 4,800 docs/day | Avg Parse Latency: 4.2s                    │
│ • LLM Token Burn & Cost per Tenant: Average $0.18 per contract analysis                │
│ • Storage Footprint: 1.8 TB on S3 | Database Size: 42 GB (including vectors)           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 19. SECURITY, CRYPTOGRAPHY & COMPLIANCE ARCHITECTURE

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ IN-TRANSIT SECURITY                                                                    │
│ TLS 1.3 Strict HTTPS | HSTS Headers | PFS Ciphers | CORS Restricted to App Domains     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ AT-REST ENCRYPTION                                                                     │
│ Database: AWS RDS AES-256 Storage Encryption                                          │
│ Object Storage: S3 Server-Side Encryption (SSE-KMS) with Customer-Managed Keys (CMK)   │
│ Sensitive Fields (e.g. Integrations tokens): App-level AES-GCM-256 field encryption    │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ IDENTITY & SESSION MANAGEMENT                                                          │
│ Short-lived Access Tokens (15 min) | Refresh Tokens in HttpOnly, Secure, SameSite=Lax  │
│ Argon2id Password Hashing (Memory: 64MB, Iterations: 3, Parallelism: 4)                │
│ Enterprise SSO: SAML 2.0 / OpenID Connect with Azure AD & Okta                         │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ DATA INTEGRITY & AUDIT TRAIL                                                           │
│ Cryptographic SHA-256 Checksum computed upon file upload and logged to immutable trail  │
│ Write-Once-Read-Many (WORM) compliant audit log design: DELETE/UPDATE revoked on audit  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 20. RECOMMENDED TECHNOLOGY STACK

To ensure low development overhead, maximum developer velocity, robust typing, and strong production performance:

| Component | Technology | Version | Justification |
|---|---|---|---|
| **Frontend Framework** | Next.js (App Router) | 14.x / 15.x | Server Components for instant initial paint, React Server Actions, optimal SEO for landing pages. |
| **Language** | TypeScript | 5.x | Strict end-to-end type safety shared between schemas. |
| **Styling & UI Components**| Vanilla CSS / Tailored CSS Modules / Radix UI | Latest | Custom, sleek dark-mode glassmorphic aesthetics without generic UI defaults. |
| **Document Editor** | ProseMirror / TipTap | Latest | The industry standard for structured document node editing and inline tracked changes. |
| **Backend Framework** | FastAPI (Python) | 0.111+ | Python ecosystem is required for legal AI/NLP pipelines; FastAPI provides automatic OpenAPI documentation and high async throughput. |
| **Data Validation** | Pydantic v2 | 2.x | High-speed C-extension validation for complex legal DTOs. |
| **Relational Database** | PostgreSQL | 16+ | ACID compliance, JSONB support for playbook rules, Row-Level Security. |
| **Vector Search Extension** | `pgvector` | 0.7+ | Co-locates vector embeddings inside PostgreSQL, avoiding separate vector DB costs and sync overhead. |
| **Task Queue & Scheduler**| Celery + Redis | 5.x | Proven distributed async processing for PDF parsing, embeddings, and hourly Contract Watch crons. |
| **Object Storage** | MinIO (Dev) / AWS S3 or Cloudflare R2 (Prod) | S3 API | Low egress costs (Cloudflare R2 has $0 egress fees), high reliability, presigned URL support. |
| **LLM Provider Gateway** | Anthropic Claude 3.5 Sonnet / OpenAI GPT-4o-mini | API | Claude 3.5 Sonnet excels at legal reasoning, nuanced redlining, and complex clause extraction; GPT-4o-mini handles fast classification. |
| **Authentication** | NextAuth.js / Custom FastAPI JWT | v5 | Flexible multi-tenant session management with OAuth2 and email magic links. |
| **PDF Extraction & OCR** | PyMuPDF (fitz) + Tesseract | Latest | PyMuPDF is 10x faster than PyPDF; Tesseract handles scanned document OCR fallback. |

---

## 21. API ARCHITECTURE & ENDPOINT SPECIFICATIONS

All endpoints enforce tenant resolution, JWT authentication, and RBAC permission checks.

```
/api/v1
  ├── /auth
  │     POST   /register
  │     POST   /login
  │     POST   /refresh
  │     POST   /logout
  │     GET    /me
  │
  ├── /organizations
  │     POST   /
  │     GET    /current
  │     PATCH  /current
  │     GET    /members
  │     POST   /members/invite
  │     PATCH  /members/{id}/role
  │
  ├── /contracts
  │     GET    /                      # Paginated, filtered by department, status, risk
  │     POST   /                      # Initialize contract record
  │     GET    /{id}                  # Contract details & current version
  │     PATCH  /{id}                  # Update metadata (title, dates, value)
  │     DELETE /{id}                  # Soft delete (Archived)
  │     POST   /{id}/upload-url       # Request presigned S3 upload URL for new version
  │     POST   /{id}/finalize-upload  # Trigger Celery ingestion pipeline
  │
  ├── /contracts/{id}/versions
  │     GET    /                      # List version history (v1.0, v1.1, etc.)
  │     GET    /{version_id}          # Full details, raw text, structured JSON
  │     GET    /{version_id}/diff/{other_version_id} # Compute diff
  │
  ├── /contracts/{id}/analysis
  │     POST   /trigger               # Run deep AI risk audit
  │     GET    /status                # Ingestion / analysis progress SSE endpoint
  │     GET    /clauses               # Extracted structured clauses
  │     GET    /risks                 # Detected risk flags and mitigation advice
  │
  ├── /contracts/{id}/redline
  │     POST   /generate              # Generate AI redlines against organization playbook
  │     GET    /proposals             # Get proposed edits
  │     POST   /proposals/{pid}/accept# Accept edit (merges into new working version)
  │     POST   /proposals/{pid}/reject# Reject edit
  │     GET    /export/docx           # Download .docx with native Word tracked changes
  │
  ├── /contracts/{id}/qa
  │     POST   /query                 # Ask questions (Returns answer with clause citations)
  │     GET    /history               # Prior Q&A thread
  │
  ├── /contracts/{id}/obligations
  │     GET    /                      # List extracted obligations
  │     POST   /                      # Manually add obligation
  │     PATCH  /{oid}                 # Update obligation status / owner
  │     POST   /{oid}/evidence        # Upload compliance proof
  │
  ├── /approvals
  │     GET    /pending-my-action     # User's actionable approval inbox
  │     POST   /contracts/{id}/submit # Trigger approval workflow
  │     POST   /{approval_id}/decide  # Approve or Reject with comments
  │
  ├── /playbooks
  │     GET    /                      # List organization playbooks
  │     POST   /                      # Create playbook
  │     POST   /{id}/clauses          # Add standard clause & fallbacks
  │
  ├── /vendors
  │     GET    /                      # Vendor directory & aggregate risk scores
  │     POST   /                      # Add vendor profile
  │     GET    /{id}/contracts        # Vendor contract history
  │
  ├── /lawyers
  │     GET    /directory             # Public verified lawyer search
  │     GET    /{id}/profile          # Experience, jurisdiction, rates
  │     POST   /{id}/consultations    # Book consultation session
  │
  ├── /matters (Professional Workspace)
  │     GET    /                      # Active client matters
  │     POST   /                      # Create matter
  │     GET    /{id}/contracts        # Matter-specific document repository
  │
  ├── /analytics
  │     GET    /dashboard             # KPI cards (Value, Volume, Cycle time)
  │     GET    /risk-distribution     # Breakdown by risk tier
  │     GET    /renewal-pipeline      # 30/60/90-day expiry forecast
  │
  └── /audit
        GET    /logs                  # Immutable audit trail with date/user filters
```

---

## 22. BACKGROUND TASK PROCESSING ENGINE (CELERY + REDIS)

The HTTP request-response cycle is kept under 200ms by delegating long-running compute jobs to Celery workers:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ CELERY WORKER POOLS                                                    │
├────────────────────────────────┬───────────────────────────────────────┤
│ Queue: `ingestion_high`        │ Queue: `ai_reasoning`                 │
│ - ClamAV Antivirus Check       │ - Dense Vector Embedding Batching     │
│ - PyMuPDF / Tesseract OCR      │ - LLM Clause Extraction & Scoring     │
│ - Layout Markdown Normalizer   │ - AI Redline Generation               │
├────────────────────────────────┼───────────────────────────────────────┤
│ Queue: `cron_watch`            │ Queue: `notifications`                │
│ - Hourly Contract Watch Check  │ - Resend Transactional Emails         │
│ - Daily Expiry & Renewal Scan  │ - Webhook Event Delivery              │
│ - Obligation Overdue Flagging  │ - In-App SSE Push Delivery            │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 23. FRONTEND ROUTE ARCHITECTURE (NEXT.JS APP ROUTER)

```
app/
  ├── (public)
  │     ├── page.tsx                           # Landing page with interactive demo preview
  │     ├── platform/page.tsx                  # Architecture & enterprise security overview
  │     ├── solutions/
  │     │     ├── personal/page.tsx            # Consumer & freelancer features
  │     │     └── professional/page.tsx        # Law firm matter management
  │     ├── pricing/page.tsx                   # Transparent tier breakdown
  │     └── lawyers/page.tsx                   # Public verified lawyer marketplace
  │
  ├── (auth)
  │     ├── login/page.tsx
  │     ├── register/page.tsx
  │     ├── forgot-password/page.tsx
  │     └── onboarding/page.tsx                # Account Type selection & Org profile setup
  │
  ├── app/
  │     ├── personal/                          # PERSONAL WORKSPACE
  │     │     ├── layout.tsx                   # Simplified personal navigation
  │     │     ├── page.tsx                     # Personal Dashboard (Health, Deadlines)
  │     │     ├── contracts/
  │     │     │     ├── page.tsx               # Personal Contract Vault
  │     │     │     └── [id]/
  │     │     │           ├── page.tsx         # Document Reader & Plain-Language Summary
  │     │     │           └── redline/page.tsx # Consumer Negotiation & Letter Generator
  │     │     ├── calendar/page.tsx            # Personal Obligation & Renewal Calendar
  │     │     └── consultations/page.tsx       # Bookings with Legal Professionals
  │     │
  │     ├── business/                          # BUSINESS WORKSPACE
  │     │     ├── layout.tsx                   # Multi-tenant corporate layout with team switcher
  │     │     ├── page.tsx                     # Executive Overview (Value, Risk, Bottlenecks)
  │     │     ├── contracts/
  │     │     │     ├── page.tsx               # Repository (Search, Filters, Folders)
  │     │     │     ├── new/page.tsx           # Contract Intake / Request Form
  │     │     │     └── [id]/
  │     │     │           ├── page.tsx         # Main Contract View (Metadata, Versions)
  │     │     │           ├── analysis/page.tsx# Clause Breakdown & Risk Scoring
  │     │     │           ├── editor/page.tsx  # Redline Studio (Tracked changes editor)
  │     │     │           ├── compare/page.tsx # Side-by-Side Version Comparison
  │     │     │           └── watch/page.tsx   # Obligation & Compliance Tracker
  │     │     ├── approvals/page.tsx           # My Pending Approvals & DAG visualizer
  │     │     ├── vendors/page.tsx             # Counterparty Directory & Risk Profiles
  │     │     ├── playbook/page.tsx            # Corporate Clause Playbook Configurator
  │     │     ├── analytics/page.tsx           # Deep Contract Intelligence Charts
  │     │     └── settings/
  │     │           ├── team/page.tsx          # Member invitations & RBAC matrix
  │     │           └── audit/page.tsx         # Immutable Security Audit Log
  │     │
  │     ├── professional/                      # LAWYER / LAW FIRM WORKSPACE
  │     │     ├── layout.tsx                   # Practice navigation (Client / Matter scope)
  │     │     ├── page.tsx                     # Practice Dashboard (Billable, Matters, Tasks)
  │     │     ├── clients/page.tsx             # Client Database
  │     │     ├── matters/
  │     │     │     ├── page.tsx               # Matters List
  │     │     │     └── [id]/page.tsx          # Isolated Matter Workspace (Contracts, Notes)
  │     │     ├── reviews/page.tsx             # Contract Review Queue
  │     │     └── consultations/page.tsx       # Client Appointment Schedule
  │     │
  │     └── admin/                             # PLATFORM SUPER-ADMIN
  │           ├── layout.tsx                   # Platform Admin Shell
  │           ├── page.tsx                     # Global Health (Tenants, Revenue, AI burn)
  │           ├── organizations/page.tsx       # Tenant Management & Quota Overrides
  │           ├── ai-telemetry/page.tsx        # LLM Latency, Error Rates, Provider Failover
  │           └── audit/page.tsx               # Global Security Logs
```

---

## 24. DEVELOPMENT PHASES & ROADMAP

```text
PHASE 0: Foundations & Design System
   │
PHASE 1: Auth, Multi-Tenancy & Account Types
   │
PHASE 2: Document Pipeline & Ingestion Repository
   │
PHASE 3: AI Clause Extraction & Risk Analysis
   │
PHASE 4: Redline Studio & Word Tracked Changes
   │
PHASE 5: Contract Requests & Approval DAG Engine
   │
PHASE 6: Obligation Engine & "Contract Watch"
   │
PHASE 7: Compliance, Escalation & Notifications
   │
PHASE 8: Enterprise Playbooks & Vendor Intelligence
   │
PHASE 9: Professional Law Firm Workspace & Consultations
   │
PHASE 10: Production Hardening, Billing & Observability
```

### Detailed Phase Specifications

#### Phase 0: Foundations & Design System
- **Objective:** Establish repo architecture, linting, shared types, and rich UI design system.
- **Deliverables:** Modern theme tokens (dark mode, glassmorphism, accessible contrast), typography, shared UI components (buttons, modals, tables, badges, split panes).
- **Definition of Done:** Next.js application boots with responsive component library storybook/catalog and baseline test runners pass.

#### Phase 1: Authentication, Multi-Tenancy & Account Types
- **Objective:** Deliver secure login, registration, workspace provisioning, and RBAC guards.
- **Database:** `organizations`, `users`, `organization_members`, `departments`.
- **APIs:** `/auth/*`, `/organizations/*`.
- **Definition of Done:** Users can sign up, select Personal/Business/Professional, invite members, and have RBAC enforced via JWT.

#### Phase 2: Document Repository & Ingestion Pipeline
- **Objective:** Enable secure PDF/DOCX uploads to S3 and text extraction.
- **Database:** `contracts`, `contract_versions`, `contract_parties`.
- **APIs:** `/contracts/*`, `/contracts/{id}/upload-url`.
- **Background Worker:** Celery ingestion worker with PyMuPDF parsing and ClamAV scanning.
- **Definition of Done:** User uploads contract; file is securely saved in S3; parsed markdown text is stored in PostgreSQL and rendered in the viewer.

#### Phase 3: AI Clause Extraction & Risk Analysis (RAG)
- **Objective:** Extract clauses, identify risk levels, and enable conversational Q&A.
- **Database:** `contract_clauses`, `contract_risks`, `pgvector` index.
- **APIs:** `/contracts/{id}/analysis/*`, `/contracts/{id}/qa/*`.
- **Definition of Done:** Ingestion triggers automated clause segmentation, generates embeddings, calculates risk scores (0-100), and answers contract questions with exact clause citations.

#### Phase 4: Redlining & Comparison Engine
- **Objective:** Build the side-by-side redline editor and DOCX tracked changes export.
- **Database:** ProseMirror delta storage in `contract_versions`.
- **APIs:** `/contracts/{id}/redline/*`.
- **Frontend:** Dual-pane comparison viewer with interactive accept/reject diff cards.
- **Definition of Done:** User accepts AI-suggested redline; clean version and Word `.docx` with native `<w:ins>`/`<w:del>` tracked changes are successfully generated.

#### Phase 5: Contract Requests & Approval Workflows
- **Objective:** Implement the multi-stage approval DAG for business contracts.
- **Database:** `approval_workflows`, `approval_workflow_steps`, `contract_approvals`.
- **APIs:** `/approvals/*`.
- **Definition of Done:** Contracts exceeding threshold values automatically route to assigned managers; dashboard updates approval state upon review.

#### Phase 6: Obligation Tracking & "Contract Watch"
- **Objective:** Automated extraction of contract duties and background deadline monitoring.
- **Database:** `obligations`, `obligation_evidence`.
- **APIs:** `/contracts/{id}/obligations/*`.
- **Background Worker:** Celery Beat daemon scanning due dates every hour.
- **Definition of Done:** Active contracts automatically generate calendar obligations with reminder notifications dispatched on schedule.

#### Phase 7: Compliance, Escalation & Notifications
- **Objective:** Implement non-compliance alerts, evidence verification, and in-app/email dispatch.
- **Database:** `compliance_events`, `notifications`.
- **APIs:** `/notifications/*`, `/compliance/*`.
- **Definition of Done:** Missed deadlines raise non-adjudicative compliance events, trigger email alerts via Resend, and notify administrators.

#### Phase 8: Enterprise Playbooks & Vendor Intelligence
- **Objective:** Support corporate negotiation playbooks and vendor risk profiling.
- **Database:** `playbooks`, `playbook_clauses`, `vendors`.
- **APIs:** `/playbooks/*`, `/vendors/*`.
- **Definition of Done:** AI redlining evaluates drafts directly against the organization's saved playbook rules and flags prohibited clauses.

#### Phase 9: Professional Law Firm Workspace & Lawyer Directory
- **Objective:** Build matter isolation for legal practitioners and public consultation booking.
- **Database:** `law_firms`, `lawyers`, `matters`, `consultations`.
- **APIs:** `/lawyers/*`, `/matters/*`, `/consultations/*`.
- **Definition of Done:** Personal and Business users can find verified lawyers and book consultations; lawyers can manage isolated client matters.

#### Phase 10: Production Hardening, Billing & Platform Admin
- **Objective:** Stripe billing, platform telemetry, rate limiting, and production deployment.
- **Database:** Billing subscriptions, global audit logs.
- **APIs:** `/admin/*`, Stripe webhook handlers.
- **Definition of Done:** Automated subscription enforcement, platform admin usage metrics live, and end-to-end security penetration testing verified.

---

## 25. MVP SCOPE VS. V2 ROADMAP

```text
┌────────────────────────────────────────────────────────────────────────┐
│                          MVP SCOPE (LAUNCH-READY)                      │
├────────────────────────────────────────────────────────────────────────┤
│ • Complete Authentication & 3 Account Types (Personal, Business, Pro)  │
│ • Secure PDF / DOCX Document Upload & S3 Ingestion                     │
│ • PyMuPDF Fast Parsing & Markdown Normalization                        │
│ • AI Clause Extraction & Risk Analysis (1-100 Score)                   │
│ • Grounded Contract Q&A with Clause Citations                          │
│ • Interactive Redlining Studio with In-App Diff & DOCX Export          │
│ • Core Contract Watch (Basic Obligation Extraction & Due Date Alerts)   │
│ • Multi-Stage Approval Workflow (Sequential Business Approvals)        │
│ • Professional Lawyer Directory & Direct Consultation Booking          │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           V2 FUTURE HORIZONS                           │
├────────────────────────────────────────────────────────────────────────┤
│ • Native E-Signature Integration (DocuSign, HelloSign, Native PKI)     │
│ • Multi-Party Real-Time Collaborative Editing (Yjs / WebSockets)       │
│ • Direct Outlook & Gmail Add-ins (Review contracts directly in inbox)  │
│ • Salesforce & HubSpot CRM Two-Way Contract Sync                       │
│ • Slack & Microsoft Teams Interactive Approval Action Bots             │
│ • Multi-Lingual Contract Translation & Cross-Border Jurisdiction Rules │
│ • Mobile Native Apps (iOS & Android for On-The-Go Approvals)           │
│ • Advanced OCR for Complex Scanned Tables & Handwriting                │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 26. COMPREHENSIVE TESTING STRATEGY

```text
┌────────────────────────────────────────────────────────────────────────┐
│ TEST PYRAMID                                                           │
│                                                                        │
│                    ▲                                                   │
│                   / \         E2E Tests (Playwright)                   │
│                  /   \        - Full User Journeys                     │
│                 /─────\       - Cross-Browser Split Screen             │
│                /       \                                               │
│               /  AI &   \     AI Evaluation Harness                    │
│              / RAG Evals \    - Clause Precision / Recall (CUAD)       │
│             /─────────────\   - Grounding & Faithfulness (Ragas)       │
│            /               \                                           │
│           /   Integration   \ Integration Tests (Pytest + Testcontainers│
│          /      Tests        \- Real PostgreSQL RLS & S3 API Mock      │
│         /─────────────────────\                                        │
│        /      Unit Tests       \ Unit Tests (Pytest + Vitest)          │
│       /─────────────────────────\- FSM, Math, Playbook Regex, DTOs     │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. AI & RAG Evaluation Metrics (Automated CI Pipeline)
- **Extraction Precision & Recall:** Benchmarked against a 100-document labeled synthetic test set. Minimum acceptable precision: **95%**; recall: **92%**.
- **Faithfulness (Ragas Metric):** Ensures answers generated by the Contract Q&A agent are strictly grounded in retrieved clause text. Hallucination rate must be **< 1%**.
- **Redline Semantic Stability:** Verifies that suggested redlines adhere to the legal playbook guidance without introducing grammar errors or unintended liability shifts.

### 2. Multi-Tenant Security & RBAC Penetration Tests
- **Cross-Tenant Data Leak Test:** Automated test where Tenant B attempts to read `/api/v1/contracts/{id}` belonging to Tenant A. System must return `404 Not Found` or `403 Forbidden`.
- **Direct S3 Key Tamper Test:** User attempts to access a presigned URL with an altered organization ID path. AWS S3 policy must reject the request.
- **SQL RLS Injection Test:** API query parameter attempts to reset `app.current_tenant_id`. Connection handler must prevent session-level overrides.

---

## 27. DEPLOYMENT STRATEGY & PRODUCTION INFRASTRUCTURE

Contractly is designed to scale affordably on standard cloud infrastructure:

```text
                                  ┌───────────────────────────┐
                                  │      Cloudflare Edge      │
                                  │   (DNS, WAF, CDN, DDoS)   │
                                  └─────────────┬─────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
  ┌─────────────────────────────┐                               ┌─────────────────────────────┐
  │ Frontend: Vercel / Node VM  │                               │ Backend API: Docker Cluster │
  │ Next.js App Router (SSR)    │                               │ FastAPI on AWS ECS / Hetzner│
  └──────────────┬──────────────┘                               └──────────────┬──────────────┘
                 │                                                             │
                 └──────────────────────────────┬──────────────────────────────┘
                                                │
                                                ▼
  ┌───────────────────────────────────────────────────────────────────────────────────────────┐
  │ Managed PostgreSQL 16 + pgvector (AWS RDS / Supabase / Neon)                              │
  └─────────────────────────────────────────────┬─────────────────────────────────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
  ┌─────────────────────────────┐                               ┌─────────────────────────────┐
  │ Celery Async Workers & Redis│                               │ Object Storage: S3 / R2     │
  │ Redis (ElastiCache / Upstash│                               │ Cloudflare R2 ($0 Egress)   │
  └─────────────────────────────┘                               └─────────────────────────────┘
```

### Production Environment Configuration
```ini
# Application Core
ENVIRONMENT=production
LOG_LEVEL=info
SECRET_KEY=generate_with_openssl_rand_hex_64
ALLOWED_ORIGINS=https://contractly.io,https://app.contractly.io

# Database & Vector Store
DATABASE_URL=postgresql+asyncpg://contractly_app:secure_pwd@db.contractly.internal:5432/contractly_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Redis & Celery Message Broker
REDIS_URL=rediss://:redis_secure_pwd@redis.contractly.internal:6379/0
CELERY_CONCURRENCY=8

# Storage (Cloudflare R2 or S3)
STORAGE_PROVIDER=s3
AWS_ACCESS_KEY_ID=prod_s3_key
AWS_SECRET_ACCESS_KEY=prod_s3_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=contractly-enterprise-vault
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com

# LLM Providers & Inference Gateways
ANTHROPIC_API_KEY=sk-ant-prod-...
OPENAI_API_KEY=sk-prod-...
PRIMARY_LLM_MODEL=claude-3-5-sonnet-20241022
FAST_LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Transactional Communications
RESEND_API_KEY=re_prod_...
EMAIL_FROM_ADDRESS=notifications@contractly.io
```

---

## 28. COST OPTIMIZATION & BUDGET-CONSCIOUS AI ARCHITECTURE

To support sustainable unit economics from initial launch to enterprise scale:

1. **Deterministic Pre-Filtering:** Never send whole contracts to expensive LLMs. Use regex and keyword pre-filters to isolate clauses first.
2. **Two-Tier LLM Architecture:**
   - **Tier 1 (Fast & Inexpensive - GPT-4o-mini / Claude 3.5 Haiku):** Clause classification, simple date extraction, search term extraction (~$0.15 / 1M tokens).
   - **Tier 2 (High Reasoning - Claude 3.5 Sonnet):** Complex risk analysis, redline generation, nuanced negotiation guidance (~$3.00 / 1M tokens).
3. **Embedding Caching:** Compute clause embeddings once and store them in `contract_clauses.embedding`. Subsequent searches and similarity checks run on indexed PostgreSQL vectors with zero additional LLM costs.
4. **Zero Egress Storage:** Use **Cloudflare R2** for contract document storage. R2 provides full S3 API compatibility with **$0 data egress charges**, eliminating bandwidth costs when streaming large PDFs to browser viewers.
5. **Prompt Compression:** Strip boilerplates, repeated headers/footers, and page numbers before sending prompts to the LLM context window.

---

## 29. RISKS, EDGE CASES & TECHNICAL CHALLENGES

| Risk / Technical Challenge | Severity | Impact | Mitigation Strategy |
|---|---|---|---|
| **Poor-Quality Scanned PDFs** | High | Inaccurate clause extraction due to corrupted OCR | Image pre-processing pipeline (deskewing, contrast adjustment using OpenCV) before OCR; flag low-confidence OCR pages for human review. |
| **Cross-Tenant Vector Bleed** | Critical | Severe privacy violation & legal liability | Hardcoded tenant filtering in all vector queries via SQL joins against `c.organization_id = :tenant_id`; automated CI penetration tests. |
| **Word (.docx) Formatting Corruption** | High | Redlines break document styles and fonts | Native Word OpenXML editing via `python-docx` using tracked-change tags (`<w:ins>`, `<w:del>`), preserving document styles. |
| **Unauthorized Legal Practice Claims** | High | Regulatory challenges | Strict non-adjudicative safe language linter in AI output pipeline; clear disclaimers; position tool as human-in-the-loop assistance. |
| **AI Hallucinations in Q&A** | High | Users rely on inaccurate terms | Strict RAG pipeline requiring direct clause citations; temperature set to 0.0; direct link to highlighted source text in viewer. |
| **Complex Approval Deadlocks** | Medium | Contracts stall if an approver leaves | Configurable escalation rules, delegation settings, and Admin override protocols with complete audit logging. |

---

## 30. RECOMMENDED IMPLEMENTATION ORDER

```text
Step 1: Project Scaffold & Database Foundation
        Setup repository, Docker Compose (PostgreSQL 16 + pgvector, Redis, MinIO),
        Alembic migration pipeline, and Core Organization/User models.

Step 2: Authentication & RBAC Guard
        Implement JWT issuance, password hashing, Multi-Tenant context middleware,
        and FastAPI permission dependency injectors.

Step 3: Document Ingestion & Storage Pipeline
        S3 presigned upload endpoints, PyMuPDF text parsing worker,
        document normalization into markdown, and contract metadata storage.

Step 4: AI & Vector Infrastructure (pgvector)
        Structural clause chunking, OpenAI text-embedding-3-small integration,
        vector indexing, and semantic similarity search queries.

Step 5: Contract Risk Analysis & Grounded Q&A
        Few-shot clause classification, risk assessment prompts,
        composite score formula, and streaming citation-grounded Q&A API.

Step 6: Frontend Shell & Document Visualizer (Next.js)
        App Router layout, design tokens, contract repository table,
        and dual-pane split document viewer (Markdown / PDF).

Step 7: Redline Studio & Word Tracked Changes
        ProseMirror-based diff editor, AI playbook revision generator,
        and python-docx OpenXML tracked-change exporter.

Step 8: Contract Watch & Obligation Engine
        Post-execution obligation extractor, Celery Beat hourly deadline monitor,
        and evidence upload portal.

Step 9: Business Approval Workflow Engine
        DAG approval builder, review decision endpoints, and status state machine.

Step 10: Professional Workspace & Marketplace
         Lawyer directory, client-matter isolation, and consultation scheduling.
```

---

# READY FOR IMPLEMENTATION

### Milestone 1: Core Foundation, Multi-Tenant Auth & Document Ingestion Pipeline

When approved, development will begin with **Milestone 1**:

#### 1. Directory Structure to Initialize
```text
/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                  # Database & Tenant Context Dependencies
│   │   │   └── v1/
│   │   │       ├── api.py               # Router Aggregator
│   │   │       ├── auth.py              # Login, Register, Session Endpoints
│   │   │       ├── organizations.py     # Tenant Provisioning
│   │   │       └── contracts.py         # Upload & Repository Endpoints
│   │   ├── core/
│   │   │   ├── config.py                # Pydantic v2 BaseSettings
│   │   │   ├── database.py              # Async SQLAlchemy Engine & SessionMaker
│   │   │   └── security.py              # Argon2id & JWT Cryptography
│   │   ├── models/                      # SQLAlchemy Declarative Models
│   │   │   ├── organization.py
│   │   │   ├── user.py
│   │   │   ├── contract.py
│   │   │   └── audit.py
│   │   ├── schemas/                     # Pydantic DTOs
│   │   │   ├── auth.py
│   │   │   ├── organization.py
│   │   │   └── contract.py
│   │   ├── services/
│   │   │   ├── storage.py               # S3 / MinIO Presigned URL Provider
│   │   │   └── document_parser.py       # PyMuPDF Text Extractor
│   │   ├── workers/
│   │   │   ├── celery_app.py            # Celery Configuration
│   │   │   └── tasks.py                 # Async Ingestion Worker
│   │   └── main.py                      # FastAPI Application Factory
│   ├── alembic/                         # Database Migration Scripts
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── app/                         # Next.js App Router Structure
│   │   │   ├── (auth)/
│   │   │   ├── (dashboard)/
│   │   │   │   ├── personal/
│   │   │   │   └── business/
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── ui/                      # Design System Primitives
│   │   │   └── contracts/               # Document Viewer & Uploaders
│   │   ├── lib/
│   │   │   ├── api.ts                   # Fetch Client with JWT Handling
│   │   │   └── tokens.ts
│   │   └── styles/
│   │       └── globals.css              # Custom Styling & Glassmorphic Design Tokens
│   ├── package.json
│   └── tsconfig.json
│
└── docker-compose.yml                   # PostgreSQL 16 with pgvector, Redis, MinIO
```

#### 2. First Database Entities (SQLAlchemy 2.0 Async)
- `Organization` (with `account_type` support)
- `User` (Argon2id, verified flags)
- `OrganizationMember` (Tenant membership + Role)
- `Contract` (Status state machine, metadata)
- `ContractVersion` (S3 key, SHA-256 hash, raw text)
- `AuditLog` (Immutable tenant audit tracking)

#### 3. First API Endpoints
- `POST /api/v1/auth/register` (Creates user and personal/business organization)
- `POST /api/v1/auth/login` (Returns access token and sets secure refresh cookie)
- `GET  /api/v1/organizations/current` (Fetches active workspace context)
- `POST /api/v1/contracts/upload-request` (Issues validated presigned S3 upload URL)
- `POST /api/v1/contracts/confirm-upload` (Queues background extraction task)
- `GET  /api/v1/contracts/` (Lists tenant contracts with status and metadata)

#### 4. First Frontend Routes
- `/(auth)/login` & `/(auth)/register` (Clean authentication interface)
- `/onboarding` (Account type selection: Personal vs. Business vs. Professional)
- `/app/business/contracts` (Contract repository table)
- `/app/business/contracts/[id]` (Split-pane document view with parsed text)

#### 5. Core Dependencies
- **Backend:** `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `python-jose`, `passlib[argon2]`, `boto3`, `celery`, `redis`, `pymupdf`
- **Frontend:** `next`, `react`, `react-dom`, `typescript`, `@types/react`, `lucide-react`, `pdfjs-dist`
