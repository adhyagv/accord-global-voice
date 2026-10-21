# Architecture Foundation (Specification-Level)

## System shape
- `apps/web`: frontend experience for interviews, agreement review, and monitoring.
- `apps/api`: backend service exposing interview, planning, agreement, and monitoring endpoints.
- `packages/sim`: simulation utilities for Alexa+ voice, notifications, calendar, and activity events.

## Frontend architecture (spec)
- Single web client with three main flows:
  1. Private interview capture
  2. Agreement review/edit/accept
  3. Monitoring and drift status
- State model separates:
  - private local draft state
  - shared agreement state
  - simulated signal timeline

## Backend architecture (spec)
- API modules:
  - Interview intake
  - Constraint extraction orchestration
  - Fairness solver orchestration
  - Agreement persistence/versioning
  - Drift detection (14-day window)
- Privacy guard sits between extraction outputs and any shared prompt/context construction.

## AI architecture (spec)
- AI used for:
  - extracting structured constraints from private interviews
  - generating safe, non-identifying explanation summaries
- AI not used for final allocation authority; deterministic solver owns final plan computation.
- Prompt construction policy enforces no cross-member raw transcript leakage.

## Database architecture (spec)
Logical entities:
- Member
- InterviewSession (private)
- DerivedConstraint (sanitized)
- ChoreDefinition
- AgreementVersion
- Assignment
- MonitoringSignal (simulated)
- DriftReport

Storage boundary:
- Raw private interview content stored and accessed only in member-scoped paths.
- Solver/monitoring read from sanitized derived tables/views.

## 14-day drift detection model (spec)
- Sliding 14-day window over assignment completion and sentiment/check-in indicators.
- Trigger conditions (example baseline):
  - repeated missed chores above threshold
  - burden delta imbalance above threshold
  - sustained negative check-in trend
- Output: DriftReport with reason codes and renegotiation recommendation.

## Staged implementation boundaries
- Stage 1: schema + simulation + deterministic solver core.
- Stage 2: end-to-end API + web workflow with local persistence.
- Stage 3: UI polish + richer monitoring visualizations.
- Stage 4: optional hardening and broader testing.

## TASK 002 contract-layer decisions
- Canonical API contract is defined in `/apps/api/contracts/openapi.yaml`.
- Python dataclass models in `/apps/api/src/accord_api/models.py` represent the initial backend schema/lifecycle rules.
- Contract request/response types are defined in `/apps/api/src/accord_api/contracts.py`.
- Fairness planning uses `/apps/api/src/accord_api/solver_interface.py` protocol only; no LLM or algorithm implementation is included in this stage.
- Simulation interfaces live in `/packages/sim/src/accord_sim/interfaces.py` with deterministic synthetic provider in `/packages/sim/src/accord_sim/generator.py`.

### Privacy boundary in contract responses
- Shared interview responses must use the safe session summary shape (no raw transcript data or transcript reference leakage).
- Derived constraints are the only shareable interview outputs entering agreement generation and solver inputs.

## TASK 003 backend core service decisions
- FastAPI service implementation lives under `/apps/api/src/accord_api` with separation between routes, services/use-cases, repositories, privacy guards, serializers, and config.
- In-memory repository implementations are used for all entities and intentionally abstracted so persistent storage (for example PostgreSQL) can replace them later without changing route handlers.
- Deterministic placeholder fairness solver is implemented behind the `DeterministicFairnessSolver` interface boundary. It consumes structured constraints/task-effort data and is replaceable without API rewrites.
- Deterministic drift detection service computes deviations from expected vs observed contributions and emits actionable severity/evidence.

### Enforced privacy boundary in application code
- Authorization checks execute before serialization for member-scoped resources.
- Unauthorized requests return generic not-found errors to avoid confirming hidden private data exists.
- Private interview payloads are available only through member-authorized private endpoints.
- Shared endpoints never include raw private transcript content or transcript references.
- Agreement generation only consumes constraints explicitly marked `shareable_derived`.

## Local persistence

The current local prototype uses `SQLiteSnapshotStore` in `apps/api/src/accord_api/persistence.py`. Domain services continue to use the repository implementations and their interfaces; after each mutating API request, the API serializes a typed snapshot to SQLite in a transaction. The context restores this snapshot on first startup. The default database file is `data/accord.sqlite3` at the repository root, overridable with `ACCORD_DB_PATH`. `ACCORD_PERSISTENCE=memory` disables persistence for test/dev use. This single-snapshot adapter is suitable for a local demo, not concurrent production workloads; interview content is not encrypted at rest.
