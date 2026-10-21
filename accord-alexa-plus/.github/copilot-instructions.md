# Copilot Instructions for Accord

## Repository intent
This repository is for a **simulated** household-negotiation prototype. Build iteratively from docs/specs before adding broad implementation scope.

## Hard privacy rule
Never place one member’s raw private interview text/messages into another member’s prompt or visible context. Use only sanitized/derived representations for shared flows.

## Simulated integrations only
When implementing voice, notifications, calendar, or household signals, keep them explicitly marked and implemented as simulations unless requirements explicitly change.

## Scope discipline
- Prefer smallest viable change per task.
- Keep scope achievable for one developer.
- Do not add dependencies or production infrastructure without explicit task requirements.

## Documentation-first expectation
For new workflows/architecture decisions:
1. Update relevant docs in `docs/` first or in the same change.
2. Keep SPEC, ARCHITECTURE, UX, and DEMO_SCRIPT internally consistent.
