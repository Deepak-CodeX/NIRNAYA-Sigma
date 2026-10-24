# NIRNAYA — Architecture Decision Log

## Document Metadata
- **Status:** PROVISIONAL — FOR ARCHITECTURAL REVIEW
- **Phase:** 0 — Engineering Foundation
- **Classification:** Architecture Decision Records (ADR)
- **Author:** Principal Software Architect & Systems Engineering Lead

---

## Architecture Decision Record Index

| ADR ID | Title | Status | Date Proposed |
| :--- | :--- | :---: | :---: |
| **ADR-001** | Modular Monolith Core with Isolated Scientific Compute Workers | **PROPOSED** | 2026-10-24 |
| **ADR-002** | Formal 7-Tuple Mathematical Problem Formulation $\mathcal{D} = (S, A, C, O, M, U, E)$ | **PROPOSED** | 2026-10-24 |
| **ADR-003** | Rejection of Universal Single-Scalar Scoring in Favor of Pareto Trade-Off Frontiers | **PROPOSED** | 2026-10-24 |
| **ADR-004** | Strict Separation of Recommendation Engine from Operational Command Actuation | **PROPOSED** | 2026-10-24 |
| **ADR-005** | Mandatory Dual-Control (Four-Eyes Principle) for Emergency Decision Authorization | **PROPOSED** | 2026-10-24 |
| **ADR-006** | Anti-Corruption Layer (ACL) Adapters for VAJRA-Ω and AAROHAN-α Ingress | **PROPOSED** | 2026-10-24 |
| **ADR-007** | Polyglot Technology Selection (Python Scientific Core + TypeScript WebGL Client) | **PROPOSED** | 2026-10-24 |
| **ADR-008** | Sequestered Role of Large Language Models to Structured Natural-Language Explanation | **PROPOSED** | 2026-10-24 |
| **ADR-009** | Immutable SHA-256 Hash Chaining for Decision Record Provenance | **PROPOSED** | 2026-10-24 |
| **ADR-010** | Deterministic Tri-State Feasibility (`FEASIBLE`, `INFEASIBLE`, `UNKNOWN`) and Freshness Envelopes | **PROPOSED** | 2026-10-24 |

---

## Detailed Architecture Decision Records

### ADR-001: Modular Monolith Core with Isolated Scientific Compute Workers
- **Decision Identifier:** `ADR-001`
- **Status:** `PROPOSED`
- **Context:** NIRNAYA requires transactional state management, relational persistence, real-time WebSocket communication, and heavy scientific power flow simulations. We must decide between a microservices architecture, a distributed service mesh, or a modular monolith.
- **Decision:** Implement NIRNAYA's control plane as a **Modular Monolith** in Python, paired with an isolated **Asynchronous Worker Subsystem** (Celery/Redis) for long-running numerical simulations.
- **Alternatives Considered:**
  1. *Full Microservices Mesh (Docker/K8s from Day 1):* High deployment complexity, distributed data consistency overhead, and premature network latency across domain boundaries.
  2. *Single In-Process Monolith (No Workers):* Long-running simulation runs would block the event loop or crash the web server on OOM events.
- **Rationale:** A modular monolith provides clean domain separation with zero network serialization overhead during initial development, while background worker processes safely isolate computationally intensive and potentially non-deterministic solvers.
- **Consequences:** Low operational complexity in early phases; requires disciplined module boundaries so workers can be scaled horizontally without refactoring domain logic.
- **Validation Needed:** Load testing API responsiveness under concurrent 50-scenario simulation batches.
- **Conditions Triggering Reconsideration:** If background worker scheduling latency exceeds 200 ms under high-concurrency multi-user loads, evaluate migration to dedicated Ray or Argo clusters.

---

### ADR-002: Formal 7-Tuple Mathematical Problem Formulation $\mathcal{D} = (S, A, C, O, M, U, E)$
- **Decision Identifier:** `ADR-002`
- **Status:** `PROPOSED`
- **Context:** Ad-hoc decision-support tools often mix data ingestion, heuristics, and optimization rules into tangled logic, making formal verification and regulatory auditing impossible.
- **Decision:** Standardize every decision case in NIRNAYA as a formal mathematical 7-tuple: $\mathcal{D} = (S, A, C, O, M, U, E)$, binding System State ($S$), Action Space ($A$), Constraints ($C$), Objectives ($O$), Domain Models ($M$), Uncertainty ($U$), and Evidence ($E$).
- **Alternatives Considered:**
  1. *Rule-Based Expert System (Heuristic If-Then Rules):* Lacks mathematical optimality guarantees and fails on novel $N-k$ multi-contingency topologies.
  2. *End-to-End Reinforcement Learning (RL):* Black-box policy networks cannot guarantee hard physical constraint satisfaction and fail safety certification standards.
- **Rationale:** An explicit mathematical tuple ensures every evaluated strategy is transparently verifiable, reproducible, and mathematically bound to physical conservation laws.
- **Consequences:** All inputs must be strictly structured into canonical schemas before analysis can begin.
- **Validation Needed:** Formal proof and test verification that standard grid contingency problems map completely into the 7-tuple without data loss.
- **Conditions Triggering Reconsideration:** Inability to express dynamic market or civil coordination constraints within the 7-tuple.

---

### ADR-003: Rejection of Universal Single-Scalar Scoring in Favor of Pareto Trade-Off Frontiers
- **Decision Identifier:** `ADR-003`
- **Status:** `PROPOSED`
- **Context:** Users often request a single composite "Strategy Score" (e.g., 0 to 100) to easily pick the "best" operational option.
- **Decision:** **Strictly reject** any single scalar composite score. Present candidate strategies across their natural physical units via Pareto non-dominated frontiers $\mathcal{P}^*$.
- **Alternatives Considered:**
  1. *Weighted Linear Sum Scoring ($Score = \sum w_i f_i$):* Conceals severe localized physical violations (e.g., $100 saved in fuel trading off a 1-hour outage at a hospital). Cannot identify solutions on non-convex Pareto frontiers.
  2. *Analytic Hierarchy Process (AHP):* Relies on subjective pairwise human weighting matrices that vary significantly between operators.
- **Rationale:** High-consequence decisions in critical infrastructure require explicit trade-off awareness. Preserving physical units ensures legal accountability and prevents catastrophic masking of life-safety impacts.
- **Consequences:** Command Center UI must provide intuitive multi-dimensional visualization tools (scatter plots, spider charts, side-by-side diffs) to help operators navigate trade-offs.
- **Validation Needed:** Control room human-factors testing to ensure operators can interpret 3-objective Pareto surfaces within 30 seconds.
- **Conditions Triggering Reconsideration:** Regulatory mandates requiring a single composite compliance index for reporting purposes.

---

### ADR-004: Strict Separation of Recommendation Engine from Operational Command Actuation
- **Decision Identifier:** `ADR-004`
- **Status:** `PROPOSED`
- **Context:** Automated grid control is technically possible via SCADA interfaces, raising the question of whether NIRNAYA should automatically dispatch switching orders.
- **Decision:** Enforce **strict architectural separation** between recommendation generation and operational command execution. NIRNAYA will not possess SCADA write access in Phase 0 through Phase 4. All outputs are exportable action plans requiring manual execution by certified operators.
- **Alternatives Considered:**
  1. *Autonomous Closed-Loop Control:* Direct breaker actuation via DNP3/IEC 61850. Rejected due to extreme liability risks, software bug hazards, and regulatory prohibitions.
  2. *Supervised Auto-Execution:* One-click automated dispatch after operator confirmation. Deferred to post-Phase 5 pending extensive field trials.
- **Rationale:** Safety, liability, and regulatory standards (NERC CIP) mandate certified human agency for power system reconfigurations.
- **Consequences:** Operational execution latency includes human typing/entry time into EMS consoles.
- **Validation Needed:** Verify that exportable plan formats match utility dispatch console formats to prevent operator transcription errors.
- **Conditions Triggering Reconsideration:** Dedicated microgrid environments where autonomous islanding within milliseconds is technically required to prevent equipment destruction.

---

### ADR-005: Mandatory Dual-Control (Four-Eyes Principle) for Emergency Decision Authorization
- **Decision Identifier:** `ADR-005`
- **Status:** `PROPOSED`
- **Context:** Under high cognitive stress, a single operator can experience tunnel vision or make catastrophic operational errors (e.g., shedding the wrong transmission corridor).
- **Decision:** Mandate **Dual-Control (Four-Eyes Principle)** authorization for any operational plan involving emergency load shedding ($>10 \text{ MW}$), bus sectionalizing, or operating within emergency voltage bands. Two distinct authorized users (e.g., Senior Grid Controller + Incident Commander) must provide digital signatures.
- **Alternatives Considered:**
  1. *Single Senior Operator Sign-Off:* Fast, but vulnerable to individual fatigue and operational error during major crises.
  2. *Post-Facto Review:* Single operator executes immediately; supervisors review hours later. Leaves safety-critical actions vulnerable to unvetted mistakes.
- **Rationale:** Redundant human verification is standard in high-reliability organizations (nuclear, aviation, defense) to prevent catastrophic human failure modes.
- **Consequences:** Requires both operations and emergency management personnel to have active sessions during severe events.
- **Validation Needed:** Usability drills measuring the end-to-end latency of obtaining secondary digital signatures under simulated emergency conditions.
- **Conditions Triggering Reconsideration:** Complete loss of communication infrastructure leaving an isolated dispatcher unable to contact secondary authorizers.

---

### ADR-006: Anti-Corruption Layer (ACL) Adapters for VAJRA-Ω and AAROHAN-α Ingress
- **Decision Identifier:** `ADR-006`
- **Status:** `PROPOSED`
- **Context:** NIRNAYA must ingest data from independent external platforms (VAJRA-Ω and AAROHAN-α) whose schemas, lifecycles, and internal structures will evolve autonomously.
- **Decision:** Implement dedicated **Anti-Corruption Layer (ACL) Ingress Adapters** that normalize external payloads into immutable canonical internal contracts (`SystemStateSnapshot`, `IncidentContext`) with cryptographic provenance checks.
- **Alternatives Considered:**
  1. *Direct Shared Schema Libraries:* Coupling all repositories to a common data model package. Rejected because it binds release lifecycles and causes cross-repository dependency lock.
  2. *Direct Database Reads:* Querying VAJRA-Ω or AAROHAN-α databases directly. Rejected as a violation of system invariants and security boundaries.
- **Rationale:** ACL isolators insulate NIRNAYA’s mathematical core from external schema churn and provide a clear location to enforce freshness and data quality validation.
- **Consequences:** Requires maintaining translation and validation code for each external integration point.
- **Validation Needed:** Mock integration tests simulating breaking changes in external payloads to confirm adapter containment.
- **Conditions Triggering Reconsideration:** If an international standard (e.g., IEC 61970 CIM) is universally adopted by all ecosystem systems without dialect variations.

---

### ADR-007: Polyglot Technology Selection (Python Scientific Core + TypeScript WebGL Client)
- **Decision Identifier:** `ADR-007`
- **Status:** `PROPOSED`
- **Context:** Selecting a programming language and ecosystem for the decision engine and presentation layer.
- **Decision:** Adopt a **Polyglot Stack**: Python 3.12+/3.14+ (FastAPI, Pydantic v2, NumPy, SciPy, HiGHS) for orchestration and scientific computation; TypeScript 5.x (React 18/19, Vite, MapLibre GL JS) for the presentation layer.
- **Alternatives Considered:**
  1. *TypeScript Full-Stack (Node.js backend):* Rejected due to weak, non-performant scientific optimization and linear algebra tooling.
  2. *Python Full-Stack (Streamlit / Dash / PyWebStation):* Rejected because server-rendered UI cannot achieve the 60 FPS WebGL rendering required for interactive 100,000-element power grid maps.
  3. *Rust / C++ Full-Stack:* High development latency; lacks the mature algebraic modeling libraries (e.g., Pyomo) available in Python.
- **Rationale:** Best-of-breed selection: Python dominates scientific computing and AI; TypeScript/WebGL dominates high-density, interactive browser interfaces.
- **Consequences:** Requires cross-language contract synchronization (achieved via automated TypeScript type generation from JSON Schemas).
- **Validation Needed:** Automated CI verification that generated TypeScript types match Python Pydantic models.
- **Conditions Triggering Reconsideration:** Emergence of a mature, battle-tested scientific computing and mathematical optimization ecosystem in WebAssembly or Rust.

---

### ADR-008: Sequestered Role of Large Language Models to Structured Natural-Language Explanation
- **Decision Identifier:** `ADR-008`
- **Status:** `PROPOSED`
- **Context:** Determining how generative AI / LLMs should be integrated into NIRNAYA's decision pipeline.
- **Decision:** **Sequester LLMs strictly to natural-language query translation and evidence explanation formatting.** LLMs are strictly forbidden from performing mathematical calculations, checking constraint compliance, or ranking strategies.
- **Alternatives Considered:**
  1. *End-to-End LLM Decision Agent (ReAct / Function Calling):* Allowing the LLM to autonomously formulate strategies and select actions. Rejected due to hallucination risks, non-determinism, and zero safety guarantees.
  2. *Zero LLM Usage (Pure Deterministic Strings):* Clunky, inflexible explanations that cannot answer nuanced operator queries or contextualize multi-factor trade-offs.
- **Rationale:** Restricting the LLM to translating verified numerical outputs into structured prose ensures deterministic safety while providing the cognitive benefits of natural-language interaction.
- **Consequences:** All LLM outputs must pass automated post-generation regex assertion against verified numerical JSON metrics before display.
- **Validation Needed:** Adversarial evaluation with prompt injection datasets attempting to force the LLM to endorse an infeasible strategy.
- **Conditions Triggering Reconsideration:** If formal mathematical proofs demonstrate that neuro-symbolic foundation models can guarantee 100% adherence to complex physical inequality constraints.

---

### ADR-009: Immutable SHA-256 Hash Chaining for Decision Record Provenance
- **Decision Identifier:** `ADR-009`
- **Status:** `PROPOSED`
- **Context:** High-consequence power grid decisions are subject to post-incident forensic audits and legal regulatory reviews (e.g., FERC/NERC inquiries). Records must be provably tamper-evident.
- **Decision:** Serialize every `DecisionRecord` into an **append-only SHA-256 hash chain**, where each record contains the cryptographic digest of the preceding record and the digital signatures of the authorizers.
- **Alternatives Considered:**
  1. *Standard Database Audit Table (`updated_at`, `user_id`):* Vulnerable to direct database tampering, accidental row modification, or database administrator credential misuse.
  2. *Public Distributed Blockchain (Ethereum / Hyperledger):* Unnecessary operational complexity, latency, and confidentiality exposure for sensitive grid infrastructure data.
- **Rationale:** A localized cryptographic hash chain provides absolute mathematical tamper-evidence without external blockchain overhead or operational dependencies.
- **Consequences:** Historical records cannot be altered or deleted; database migrations must preserve cryptographic chain integrity.
- **Validation Needed:** Automated tests verifying that manual modification of a single historical record triggers an immediate audit verification failure.
- **Conditions Triggering Reconsideration:** Legal mandate requiring submission of audit proofs directly to a federally operated external ledger.

---

### ADR-010: Deterministic Tri-State Feasibility (`FEASIBLE`, `INFEASIBLE`, `UNKNOWN`) and Freshness Envelopes
- **Decision Identifier:** `ADR-010`
- **Status:** `PROPOSED`
- **Context:** Power grid contingency evaluation frequently encounters solver divergence, numerical conditioning issues, or missing telemetry. How should ambiguous outcomes be handled?
- **Decision:** Enforce **Deterministic Tri-State Feasibility** (`FEASIBLE`, `INFEASIBLE`, `UNKNOWN`) and strict telemetry freshness envelopes ($30$s warning, $120$s lockout). `UNKNOWN` states must fail-closed and cannot be treated as `FEASIBLE`.
- **Alternatives Considered:**
  1. *Binary Feasibility (`True` / `False`):* Obscures the difference between a proven violation and a solver timeout, encouraging dangerous optimistic assumptions.
  2. *Heuristic Feasibility Imputation:* Guessing missing state values using historical averages. Rejected as dangerously unsafe during unprecedented severe weather contingencies.
- **Rationale:** In life-critical infrastructure, an unprovable state is as dangerous as a violation. Fail-closed handling prevents unverified strategies from being recommended to operators.
- **Consequences:** System will refuse to evaluate actions if telemetry is $>120$ seconds old, requiring operators to rely on local SCADA meters until communication is restored.
- **Validation Needed:** Hardware-in-the-loop tests verifying that simulated telemetry dropouts cleanly trigger the fail-closed lockout state within 120 seconds.
- **Conditions Triggering Reconsideration:** Operational scenarios where human dispatchers are legally authorized to operate blind under emergency executive orders.
