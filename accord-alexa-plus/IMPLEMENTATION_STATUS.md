# Accord implementation status

This file is a short pointer to the current, authoritative implementation report. Earlier reports showing 29 or 34 tests are historical; use the latest count below.

See [`IMPLEMENTATION_REPORT.md`](IMPLEMENTATION_REPORT.md) for current features, actual verification results, Windows setup steps, and known limitations.

## Current verification summary

- Backend tests: **50 passed** in the latest local run (includes the original backend suite plus regression/integration tests).
- Python compilation: passed after adding regression checks for constraint index idempotency and duplicate task names on repeated demo reset.
- TypeScript/JSX source syntax transpilation: 5 source files checked, zero syntax diagnostics (not a full type-check).
- FastAPI OpenAPI specification regenerated and contains the new fairness, mediation, clause-drafting, settle-up, weekly-digest, and Alexa adapter routes.
- Full frontend Vite build and ESLint remain unverified because the package registry returned `EAI_AGAIN` during `npm ci`; consequently build lacked `vite/client` and Node types and ESLint was not installed. Run `npm ci`, `npm run build`, and `npm run lint` on a network-connected machine before treating the frontend as release-ready.

## Newly implemented capability summary

- Fairness comparison, preference-influence what-if control, and seeded eight-week simulation chart.
- Explicitly consented mediation with saved safe sessions, changeable member votes, deterministic tie handling and draft-only agreement creation.
- Agreement clause drafts built only from shareable derived constraints.
- Equal-split settle-up recommendations with no payment action.
- On-demand seven-day household digest.
- Local Alexa Skills Kit request-envelope adapter; not deployed or production-secured.
- Corresponding frontend panels, regression tests, documentation and regenerated OpenAPI.

- Confirm-before-act chat cards, meal-plan drafts, subset/custom expense split UI, browser-only decision verdict cards and the live-config privacy dashboard.
- A CI workflow runs backend pytest/compileall and frontend npm ci/build/lint. The current local network could not reach the npm registry; GitHub Actions can verify the frontend on its runner.
