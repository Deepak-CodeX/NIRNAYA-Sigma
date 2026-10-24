# NIRNAYA — System Architecture Specification

## Document Metadata
- **Status:** PROVISIONAL — FOR ARCHITECTURAL REVIEW
- **Phase:** 0 — Engineering Foundation
- **Classification:** Architecture Design Document (ADD)
- **Author:** Principal Software Architect & Systems Engineering Lead

---

## 1. Architectural Principles & System Context

NIRNAYA is architected around four foundational principles:
1. **Separation of Decision Orchestration from Numerical Computation:** Orchestrating workflows, managing state, handling API traffic, and storing audit logs must never block on or be entangled with heavy scientific or mathematical solvers.
2. **Strict Invariant Enforcement via Hexagonal/Clean Architecture:** Core decision domain logic must have zero knowledge of external database drivers, web frameworks, or third-party physics solvers.
3. **Fail-Closed by Design:** Any unresolvable numerical condition, stale telemetry packet, or schema violation must halt the scenario pipeline and raise an explicit `UNKNOWN` state rather than defaulting to an optimistic `FEASIBLE` classification.
4. **Independent Domain Adapters (Anti-Corruption Layer):** All data crossing the boundary from external systems (VAJRA-Ω, AAROHAN-α) is translated into canonical, versioned internal contracts with cryptographic provenance.

### System Context Diagram (C4 Level 1)

```mermaid
C4Context
    title System Context Diagram — NIRNAYA Decision Intelligence Platform

    Person(operator, "Grid Control Operator", "Senior dispatcher managing transmission grid contingencies")
    Person(commander, "Incident Commander", "Emergency director coordinating multi-agency critical infrastructure")
    Person(auditor, "Safety & Regulatory Auditor", "Post-incident investigator examining decision records")

    System(nirnaya, "NIRNAYA Platform", "AI Decision Intelligence Engine orchestrating strategy evaluation, Pareto trade-offs, and auditable human authorizations")

    System_Ext(vajra, "VAJRA-Ω", "Power-System Intelligence providing telemetry snapshots, network topology, and physics model evaluations")
    System_Ext(aarohan, "AAROHAN-α", "Emergency Context providing hazard perimeters, civil incident reports, and critical facility priorities")
    System_Ext(scada, "SCADA / EMS Gateway", "Human-operated operations console receiving exportable dispatch plans")

    Rel(vajra, nirnaya, "Publishes telemetry snapshots & receives physics simulation runs", "JSON / HTTPS / gRPC")
    Rel(aarohan, nirnaya, "Publishes hazard polygons & asset vulnerability feeds", "GeoJSON / HTTPS")
    Rel(operator, nirnaya, "Formulates problems, explores Pareto frontiers, signs authorizations", "Web UI / WSS")
    Rel(commander, nirnaya, "Monitors critical facility risks & provides secondary authorization", "Web UI / WSS")
    Rel(auditor, nirnaya, "Verifies immutable decision records & cryptographic proofs", "REST / Read-only")
    Rel(nirnaya, scada, "Exports signed, human-authorized operational plans", "Signed JSON / C/C++ Gateway")
```

---

## 2. Logical Architecture & Subsystem Responsibilities

NIRNAYA follows a **Modular Monolith** architecture for its control plane and orchestration core, combined with an isolated **Computational Worker Subsystem** for heavy numerical evaluations.

```mermaid
graph TB
    subgraph "Ingress & Presentation Layer"
        UI["Unified Command Center<br/>(React / TypeScript / MapLibre)"]
        API["API Gateway & Reverse Proxy<br/>(FastAPI / ASGI)"]
        AUTH["AuthN / AuthZ & RBAC<br/>(OIDC / Dual-Control Guard)"]
    end

    subgraph "Core Orchestration Monolith"
        ORCH["Decision Workflow Orchestrator<br/>(State Machine / Case Manager)"]
        RULE["Constraint & Feasibility Evaluator<br/>(Hard/Soft Rule Engine)"]
        PARETO["Multi-Objective & Trade-Off Engine<br/>(Non-dominated Sorting / Regret)"]
        LLM_SVC["Explanation & Synthesis Service<br/>(Constrained LLM Prompting)"]
        AUDIT["Immutable Audit & Provenance Service<br/>(SHA-256 Hash Chain)"]
    end

    subgraph "Anti-Corruption Ingress Adapters"
        ADAPT_V["VAJRA-Ω Ingress Adapter<br/>(CIM / Network State Parser)"]
        ADAPT_A["AAROHAN-α Ingress Adapter<br/>(GeoJSON Hazard Parser)"]
    end

    subgraph "Asynchronous Compute Worker Subsystem"
        QUEUE["Task Broker / Queue<br/>(Redis / In-Memory in Dev)"]
        WORKER_1["Scientific Worker Pool<br/>(NumPy / SciPy / Latin Hypercube)"]
        WORKER_2["Optimization Solver Node<br/>(HiGHS / OR-Tools / Pyomo)"]
    end

    subgraph "Persistence Layer"
        PG["Relational Database<br/>(PostgreSQL 16)"]
        GIS["Spatial Store<br/>(PostGIS Extension)"]
        BLOB["Artifact Store<br/>(S3 / MinIO / Local FS in Dev)"]
    end

    UI <-->|WSS / REST| API
    API --> AUTH
    AUTH --> ORCH

    ADAPT_V -->|Canonical Snapshot| ORCH
    ADAPT_A -->|Canonical Incident| ORCH

    ORCH --> RULE
    ORCH --> PARETO
    ORCH --> LLM_SVC
    ORCH --> AUDIT

    ORCH -->|Enqueue Simulation Job| QUEUE
    QUEUE --> WORKER_1
    QUEUE --> WORKER_2
    WORKER_1 & WORKER_2 -->|Job Artifacts & Metrics| BLOB
    WORKER_1 & WORKER_2 -->|Evaluation Results| QUEUE
    QUEUE -->|Completed Job Event| ORCH

    ORCH --> PG
    ORCH --> GIS
    AUDIT --> PG
```

### Component Responsibility Matrix

| Subsystem | Component | Technology | Primary Responsibility |
| :--- | :--- | :--- | :--- |
| **Edge & Ingress** | API Gateway | FastAPI / Uvicorn | Request validation, rate limiting, OpenAPI contract enforcement, TLS termination. |
| **Security** | Auth & Dual-Control Guard | Custom Python / Pydantic | Validates JWTs, verifies role permissions, enforces Four-Eyes protocol for high-impact decisions. |
| **Orchestration** | Decision Case Manager | Python 3.14 (AsyncIO) | Manages decision case lifecycle, state transitions, task coordination, and persistence transactions. |
| **Domain Logic** | Feasibility Evaluator | Python / NumPy | Evaluates hard inequality and equality constraints ($g_i(x) \le 0, h_j(x) = 0$); filters out infeasible actions. |
| **Domain Logic** | Multi-Objective Engine | Python / SciPy | Executes non-dominated sorting (NSGA-II sorting core), derives Pareto trade-off frontiers, computes regret. |
| **Domain Logic** | Synthesis Service | Python / LiteLLM / Gemini | Synthesizes factor attribution narratives and counterfactual explanations; strictly bounded by output schemas. |
| **Auditing** | Audit & Provenance Service | Python / Cryptography | Generates append-only SHA-256 hash chains of all evaluations, inputs, and operator signatures. |
| **Adapters** | VAJRA-Ω Ingress Adapter | Python / Pydantic | Ingests external power grid telemetry, checks freshness, translates to `SystemStateSnapshot`. |
| **Adapters** | AAROHAN-α Ingress Adapter | Python / Shapely / GeoJSON | Ingests emergency hazard geometries, maps affected critical facilities, translates to `IncidentContext`. |
| **Computation** | Scientific Worker Pool | Python / Celery / RQ | Runs Latin Hypercube sampling, Monte Carlo stochastic simulations, and parameter sensitivity runs. |
| **Computation** | Optimization Solver Node | HiGHS / OR-Tools / Pyomo | Formulates and solves mixed-integer linear and non-linear mathematical programs. |
| **Storage** | Transactional & Spatial Store | PostgreSQL 16 + PostGIS | Stores decision problems, cases, relational entities, geospatial network topologies, and audit trails. |
| **Storage** | Artifact & Blob Store | MinIO / S3 / Local Directory | Stores high-volume telemetry matrices, raw solver output logs, and simulation trace dumps. |

---

## 3. End-to-End Decision Execution Flow

The sequence diagram below details the path from initial contingency detection to authorized decision record generation.

```mermaid
sequenceDiagram
    autonumber
    actor Dispatcher as Senior Grid Controller
    participant UI as Unified Command Center
    participant API as Decision API Gateway
    participant Orch as Decision Case Manager
    participant VAdapter as VAJRA-Ω Adapter
    participant Queue as Task Broker
    participant Worker as Compute Worker
    participant Audit as Audit Service
    actor Commander as Incident Commander (Secondary)

    Note over Dispatcher,UI: Contingency Detected (Line Trip + Storm Front)
    Dispatcher->>UI: Create Decision Case (Problem Definition)
    UI->>API: POST /api/v1/decision-problems
    API->>Orch: Initialize Decision Case
    Orch->>VAdapter: Pull Fresh Grid Snapshot
    VAdapter-->>Orch: Return SystemStateSnapshot (VALIDATED, Freshness: 1.8s)
    Orch->>Orch: Evaluate Hard Constraints (Screen Candidate Actions)
    Orch->>Queue: Enqueue Scenario Evaluations [Batch of N=20 Scenarios]

    loop Asynchronous Simulation Batch
        Queue->>Worker: Dispatch ScenarioDefinition
        Worker->>Worker: Run Power Flow Simulation & Constraint Check
        Worker-->>Queue: Return ModelEvaluation (FEASIBLE / INFEASIBLE / UNKNOWN)
    end

    Queue-->>Orch: All Scenario Evaluations Completed
    Orch->>Orch: Compute Non-Dominated Pareto Frontier & Trade-Off Matrix
    Orch->>Orch: Synthesize Evidence Narrative & Factor Attributions
    Orch-->>API: Decision Case READY_FOR_REVIEW
    API-->>UI: Push State Update via WebSocket

    Dispatcher->>UI: Inspect Pareto Curve & Select Non-Dominated Strategy
    Dispatcher->>UI: Provide Primary Digital Signature & Rationale
    UI->>API: POST /api/v1/decision-cases/{id}/authorize (Primary)
    API->>Orch: Record Primary Sign-Off

    Note over Orch,Commander: Dual-Control Check Triggered (Curtailment > 10 MW)
    Orch-->>Commander: Alert: Secondary Sign-Off Required
    Commander->>UI: Inspect Critical Infrastructure Outage Impact (0.0 hrs)
    Commander->>UI: Provide Secondary Digital Signature
    UI->>API: POST /api/v1/decision-cases/{id}/authorize (Secondary)

    API->>Audit: Commit DecisionRecord to Append-Only Audit Chain
    Audit-->>Orch: Audit Hash Generated & Verified
    Orch-->>UI: Decision Case AUTHORIZED (Exportable Plan Ready)
```

---

## 4. Decision Execution Lifecycle & State Machine

Every decision case in NIRNAYA transitions through a strictly validated, deterministic state machine.

```mermaid
stateDiagram-v2
    [*] --> DRAFT : Operator initiates problem

    DRAFT --> INGESTING : Trigger state snapshot fetch
    INGESTING --> INGESTION_FAILED : Telemetry stale / signature invalid / timeout
    INGESTION_FAILED --> DRAFT : Retry with fresh snapshot

    INGESTING --> FEASIBILITY_CHECK : Snapshot validated & fresh
    FEASIBILITY_CHECK --> INFEASIBLE_SET : All candidate actions violate hard constraints
    INFEASIBLE_SET --> DRAFT : Adjust candidate parameters or constraints

    FEASIBILITY_CHECK --> EVALUATING : Feasible candidate subspace identified
    EVALUATING --> UNKNOWN_STATE : Solver timeout / physics envelope breach
    UNKNOWN_STATE --> READY_FOR_REVIEW : Flagged with Fail-Closed warnings

    EVALUATING --> OPTIMIZING : Simulations complete
    OPTIMIZING --> UNCERTAINTY_ANALYSIS : Pareto frontier sorted
    UNCERTAINTY_ANALYSIS --> SYNTHESIS : Monte Carlo & sensitivity computed
    SYNTHESIS --> READY_FOR_REVIEW : Evidence explanations generated

    READY_FOR_REVIEW --> UNDER_REVIEW : Operator begins inspection
    UNDER_REVIEW --> AUTHORIZED : Single sign-off (low impact) OR Dual sign-off (high impact)
    UNDER_REVIEW --> REJECTED : Operator rejects all candidates with rationale
    UNDER_REVIEW --> DRAFT : Re-formulate with modified objectives

    AUTHORIZED --> SUPERSEDED : New grid event invalidates authorized plan
    REJECTED --> [*]
    SUPERSEDED --> [*]
    AUTHORIZED --> [*]
```

### State Definitions & Safety Invariants

1. **`DRAFT`:** Problem definition is being configured (objectives selected, candidate actions populated).
2. **`INGESTING`:** System is querying external adapters for fresh `SystemStateSnapshot` and `IncidentContext`.
3. **`INGESTION_FAILED`:** Ingress data exceeded freshness thresholds ($>30$s) or failed cryptographic hash check.
4. **`FEASIBILITY_CHECK`:** Mathematical screening of candidate actions against hard constraints ($g_i(x) \le 0$).
5. **`EVALUATING`:** Background workers are executing numerical solvers across defined scenarios.
6. **`UNKNOWN_STATE`:** Solver returned numerical divergence or execution timed out. **Safety Invariant:** Scenarios in `UNKNOWN_STATE` are quarantined and can never be selected for operational authorization.
7. **`OPTIMIZING`:** Calculation of Pareto non-dominated sets and hypervolume metrics.
8. **`UNCERTAINTY_ANALYSIS`:** Sampling over aleatory distributions and calculating max regret over bounded uncertainty sets.
9. **`SYNTHESIS`:** Fact-checked textual justification generated from numerical evaluation artifacts.
10. **`READY_FOR_REVIEW` / `UNDER_REVIEW`:** Case presented in the Command Center for human inspection.
11. **`AUTHORIZED`:** Cryptographically signed by required authorities. Plan exported for manual operator dispatch.

---

## 5. Domain Adapter Boundaries (Anti-Corruption Layer)

NIRNAYA enforces an **Anti-Corruption Layer (ACL)** between internal decision models and external systems.

```mermaid
classDiagram
    class ExternalVAJRASnapshot {
        +String cim_xml_payload
        +Long scada_epoch_ms
        +String substation_flags
    }

    class VAJRAIngressAdapter {
        +validate_freshness(epoch) bool
        +verify_payload_signature(sig) bool
        +translate_to_canonical(raw) SystemStateSnapshot
    }

    class SystemStateSnapshot {
        +UUID snapshot_id
        +String schema_version
        +Float grid_frequency_hz
        +List substations
        +List transmission_lines
        +List generation_units
        +List load_buses
        +String payload_hash
    }

    ExternalVAJRASnapshot --> VAJRAIngressAdapter : Ingests proprietary wire format
    VAJRAIngressAdapter --> SystemStateSnapshot : Emits validated canonical contract
```

### Adapter Safety Rules
- **Schema Validation Gate:** Ingress adapters run Pydantic/JSON Schema validation before any domain processing occurs. Malformed payloads are rejected at the edge.
- **Freshness Envelopes:** Snapshots older than 30 seconds trigger `DEGRADED` warnings; snapshots older than 120 seconds cause the adapter to refuse problem initialization (`FAIL_CLOSED`).
- **Cryptographic Provenance:** Ingress adapters record a SHA-256 hash of the exact raw bytes received to ensure external domain data can be audited forensically.

---

## 6. Persistence & Storage Responsibilities

NIRNAYA implements a hybrid storage architecture:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NIRNAYA PERSISTENCE ARCHITECTURE                │
├────────────────────────────────┬───────────────────────────────────────┤
│ PostgreSQL 16 (Relational DB)  │ - Decision problem specifications     │
│                                │ - Scenario metadata and statuses      │
│                                │ - Evaluated objective values          │
│                                │ - User identity, roles, and sessions  │
│                                │ - Append-only DecisionRecord hashes   │
├────────────────────────────────┼───────────────────────────────────────┤
│ PostGIS (Spatial Extension)    │ - Transmission line geometries (WKT)  │
│                                │ - Substation coordinates (Point)      │
│                                │ - Hazard impact perimeters (Polygon)  │
│                                │ - Critical asset geo-containment      │
├────────────────────────────────┼───────────────────────────────────────┤
│ Object Store (MinIO / S3)      │ - Raw external CIM/SCADA snapshots    │
│ (Local FS in Phase 0-1)        │ - Full solver log traces & matrices   │
│                                │ - Monte Carlo sample distributions    │
│                                │ - Signed exportable PDF/JSON dossiers │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 7. Long-Running Worker Recovery & Idempotency

Scientific simulations and Monte Carlo optimizations can take from seconds to minutes. NIRNAYA enforces robust worker handling:

1. **Job Leases with Heartbeats:** Workers acquire an execution lease on a scenario job. If a worker fails to send a heartbeat for $>15$ seconds, the job is reclaimed and requeued up to a maximum of 3 attempts.
2. **Deterministic Seed Tracking:** Every `ScenarioDefinition` contains a 64-bit integer seed (`simulation_seed`). Re-executing a scenario produces identical pseudo-random sequences for wind gusts, load fluctuations, and generator trips.
3. **Idempotent Job Completion:** If two workers complete the same scenario evaluation concurrently (due to network partitioning), the orchestrator deduplicates based on `(scenario_id, simulation_seed, solver_version)` and keeps the first verified artifact.

---

## 8. Observability, Error Handling, and Resilience

NIRNAYA adopts the **OpenTelemetry** standard for system observability:
- **Distributed Tracing:** Every decision case assigns a `TraceID` that propagates through API gateway, orchestration state machine, background task broker, and worker nodes.
- **Structured JSON Logging:** All log entries output structured JSON containing `case_id`, `problem_id`, `operator_id`, and `execution_state`.
- **Circuit Breakers on External Adapters:** Calls to external systems (e.g., querying VAJRA-Ω or AAROHAN-α) are wrapped in circuit breakers (failure threshold: 5 consecutive failures, reset timeout: 30 seconds).

---

## 9. Deployment Evolution Strategy

```mermaid
graph LR
    subgraph "Phase 1 - 2 (Development & Core Validation)"
        P1["Modular Monolith<br/>FastAPI + SQLite/Postgres<br/>In-Process Async Workers"]
    end

    subgraph "Phase 3 - 4 (Command Center & Integrations)"
        P2["Containerized Services<br/>FastAPI Orchestrator<br/>Redis + Celery Worker Pool<br/>Postgres + PostGIS"]
    end

    subgraph "Phase 5 (High-Resilience Production)"
        P3["High-Availability Cluster<br/>Multi-Node Worker Group<br/>Clustered Postgres<br/>Air-Gapped / Control-Room Ready"]
    end

    P1 --> P2 --> P3
```

- **Phase 0 (Current):** Engineering foundation and verified documentation; no application deployment.
- **Phase 1-2:** Modular monolith running in a single container or development environment with asynchronous worker threads or local Redis queues.
- **Phase 3-4:** Decoupled container stack via Docker Compose / Helm charts separating API orchestrator, frontend client, and auto-scaling Celery compute worker nodes.
- **Phase 5:** Hardened, redundant control-room deployment supporting air-gapped on-premise infrastructure with hardware-security-module (HSM) signing.
