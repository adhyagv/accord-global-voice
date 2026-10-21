# Accord Specification (TASK 001 Foundation)

## Product framing
Accord is a **simulated** Alexa+ household diplomat prototype for shared-home conflict resolution.

Primary scenario: three roommates (A, B, C) negotiate recurring household chores (dishes, trash, bathroom cleaning, shared supplies) after repeated friction about fairness and reliability.

## End-to-end workflow
1. **Private interviews (per roommate, isolated):** each roommate submits goals, constraints, preferences, boundaries, and availability.
2. **Constraint extraction:** backend/AI layer converts each private interview into structured signals.
3. **Privacy-preserving aggregation:** only safe derived representations (weights, windows, do-not-assign tags, confidence, anonymized rationale summaries) are merged.
4. **Deterministic fairness optimization:** solver computes candidate allocations and schedule balance.
5. **Agreement creation:** members review, edit member-controlled settings, and confirm an agreement artifact.
6. **Long-term monitoring:** simulated activity and check-in signals track adherence and satisfaction.
7. **14-day drift detection:** system flags persistent imbalance, repeated misses, or sentiment decline and proposes a renegotiation session.

## Privacy rule (hard requirement)
One member’s raw private messages must never enter another member’s prompt.

### Data-flow boundary
- **Private zone:** raw transcripts/messages, member-specific notes, direct quotes.
- **Shared computation zone:** only derived/aggregated outputs needed for optimization and explanation.
- **Presentation zone:** each member sees only agreement-level outcomes and safe summaries.

### Allowed shared representations
- Numeric preference weights
- Availability windows (normalized)
- Capability/exemption flags
- Chore burden scores
- Aggregated tension indicators
- Non-identifying rationale summaries

### Disallowed shared representations
- Raw chat text
- Direct quoted grievances from another roommate
- Identifiable private anecdotes not explicitly consented for sharing

## Deterministic fairness solver
### Responsibilities
- Produce reproducible chore assignments and cadence for the next planning horizon.
- Enforce hard constraints and optimize fairness objective.
- Output explainable scoring artifacts.

### Inputs
- Chore catalog and estimated effort values
- Roommate availability/capability constraints
- Preference weights and burden history
- Existing agreement state and horizon length

### Outputs
- Assignment plan by day/week
- Fairness score breakdown by roommate
- Constraint satisfaction report
- Tie-break trace for reproducibility

### Constraints
- Hard constraints must never be violated (availability, exemptions, max-load caps).
- Soft constraints optimize balance and preference fit.

### Tie-breaking and reproducibility
- Stable sort order and documented deterministic tie-break keys.
- Seedless deterministic behavior from identical inputs.
- Versioned solver config recorded with each run.

### Human/member-controlled areas
- Final acceptance/rejection of proposed agreement
- Manual swaps with explicit consent
- Weight tuning presets and renegotiation triggers

## Scope boundaries for one developer
### In scope for early stages
- Simulated data pipeline
- Deterministic local solver implementation
- Basic agreement lifecycle and drift alerts

### Non-goals (TASK 001 and near-term)
- Production-grade real Alexa+ integration
- Real third-party notification/calendar APIs
- Enterprise auth/compliance infrastructure
- Multi-household scale optimization

## Simulated integrations (explicit)
All external touchpoints are simulated in this prototype:
- **Simulated Alexa+ voice interactions**
- **Simulated notifications**
- **Simulated calendar events**
- **Simulated household activity signals**

## TASK 002 implementation boundary (data/contracts only)
- Data model entities and state transitions are defined without UI implementation.
- API contracts cover household/member/interview/constraint/agreement/monitoring/drift/renegotiation lifecycle actions.
- Deterministic fairness solver is represented only as a typed interface consuming structured derived constraints and producing structured assignment proposals.
- External integrations remain simulated-only at the interface level.
