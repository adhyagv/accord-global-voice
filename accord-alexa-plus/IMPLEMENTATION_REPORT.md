# Accord implementation report

## Summary

This update continues the existing Accord React/TypeScript + Vite frontend and Python/FastAPI backend. It adds a consent-gated mediation flow, explainable fairness comparison, shareable-summary agreement clause drafts, a split-aware settle-up optimizer, an on-demand weekly digest, and a local Alexa Skills Kit-compatible request adapter. It does not replace the project with a new template.

## Implemented in this build

- Kept the deterministic, workload-aware fairness solver and added a preference-influence weight that can be varied in a read-only what-if simulation.
- Added `POST /api/fairness/compare`, which compares Accord's workload-aware allocation to a round-robin baseline and returns projected minutes, assigned tasks, workload spread, two-sentence member explanations, and heuristic warnings. If an optional JSON-mode LLM provider is configured, it may rewrite the member explanations using only that allocation summary; malformed outputs fall back to deterministic text.
- Added a frontend Fairness Lab with a slider, comparison scores, projected workload bars, assignment lists and explanations. Running a comparison does not save tasks or modify agreements.
- Added `POST /api/mediation/propose`. Each perspective requires current household consent and a separate explicit `consentToShare` confirmation. The endpoint uses the neutral mediator prompt with a JSON-mode optional provider; otherwise it returns three deterministic, need-based compromise options. Output is not stored and every option requires household confirmation. Model outputs that fail the required structure or appear to echo long verbatim statement details are rejected in favor of the guided fallback.
- Added the Mediation Room UI, with per-member statements, sharing consent checkboxes, need-based restatements, shared need, three options and trade-offs. Selecting an option fills a counteroffer draft and navigates to Agreements; it does not submit or apply that change.
- Added `POST /api/agreements/draft-clauses`. It accepts only consented shareable derived summaries, never raw private interview answers, and returns plain-language draft clauses, source preference references and possible conflicts. Clauses remain drafts and do not activate agreements.
- Added optional JSON-mode prompts for mediator, agreement drafter and fairness explainer. All three retain deterministic behavior when no provider is configured or a provider response fails.
- Added `GET /api/expenses/households/{household_id}/settle-up`. It computes an equal split in integer cents and a minimal greedy set of suggested transfers. No payment provider is called and no payment is recorded as completed.
- Added `GET /api/monitoring/weekly-digest/{household_id}` to summarize the past seven days of recorded tasks and expenses, current open tasks, pending agreements and open drift reports. It is on-demand and does not send notifications.
- Added an Alexa Skills Kit-compatible request adapter at `POST /api/alexa/skill-request` for launch/help, weekly-plan and mediation-help intents. Added setup documentation and an example request. This is not a deployed or production-secured Alexa Skill: signature verification, HTTPS deployment and account/household authorization are still required.
- Extended the frontend with the fairness lab, Mediation Room, agreement clause drafter, settle-up panel and weekly digest panel.
- Updated README, demo script and this report with setup and integration boundaries.

## Verification results actually run

- Initial backend verification (historical): **34 passed**; the prior feature pass reached **49 passed**. The current verification below supersedes both counts (**50 passed**).
- Python `compileall`: passed.
- `python -m compileall -q apps/api/src packages/sim/src tests`: completed successfully (`COMPILEALL_OK`).
- FastAPI TestClient route smoke checks: `GET /healthz` (200), demo reset (201), household and member lookup (200), assistant status/chat (200), meal-plan draft (200), privacy dashboard (200), fairness compare (200), eight-week fairness simulation (200 with 8 weeks), mediation session create/get/vote/close (201/200/200/200), settle-up (200; two suggested transfers in the seeded demo), weekly digest (200), workload drift (200), Alexa adapter disabled by default (503), and invalid blank chat rejected (422). All expected status checks passed (`ROUTE_SMOKE_OK`).
- TypeScript/JSX syntax transpilation: `App.tsx`, `api.ts`, `main.tsx`, `voice/DecisionVerdictCard.tsx` and `voice/verdict.ts` each produced zero syntax diagnostics. This is **not** a full TypeScript type-check.
- `npm ci --no-audit --no-fund --fetch-retries=0 --fetch-timeout=15000` was attempted. Package fetches failed with `EAI_AGAIN` against `registry.npmjs.org`, and npm exited with `Exit handler never called!`. `npm run build` then exited 1 because `vite/client` and Node type definitions were unavailable; `npm run lint` exited 127 because ESLint was not installed. Therefore the full frontend production build, type-check and lint are **unverified** here. Re-run `npm ci`, `npm run build`, and `npm run lint` on a network-connected machine before treating the UI as release-ready.

## Run on Windows

### Backend terminal (from the extracted repository root)

```powershell
cd C:\Users\Adhya\accord-refreshed\accord-alexa-plus
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\apps\api\src;$PWD\packages\sim\src"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn accord_api.app:app --app-dir apps/api/src --reload --host 127.0.0.1 --port 8000
```

Keep this terminal open. API docs: `http://127.0.0.1:8000/docs`; health: `http://127.0.0.1:8000/healthz`.

### Frontend terminal

Open a second terminal:

```powershell
cd C:\Users\Adhya\accord-refreshed\accord-alexa-plus\apps\web
npm ci
npm run build
npm run lint
npm run dev
```

Use the local URL printed by Vite, normally `http://localhost:5173/`. Keep both terminals open.

## Optional LLM

Without a provider key the app uses guided outputs. For an OpenAI-compatible provider, copy `.env.example` to `.env`, set `ACCORD_LLM_API_KEY`, and optionally configure `ACCORD_LLM_BASE_URL` and `ACCORD_LLM_MODEL`. Start Uvicorn using `--env-file .env`. Do not commit or share `.env`.

## Important limitations

- This is a local prototype, not production-secure multi-user software. `X-Member-Id` is a demo identity header, not authentication. Do not use real sensitive household data.
- SQLite is not encrypted at rest.
- The fairness engine is a deterministic heuristic, not a guarantee of objective fairness.
- Mediation and clause drafting use an optional LLM provider only if configured; otherwise the guided fallback is used.
- The weekly digest is on-demand, not a scheduled email or push notification.
- Settle-up produces suggestions only; it does not move money.
- The Alexa adapter is an un-deployed Skills Kit request handler, not live Alexa+ connectivity. Implement signature/timestamp verification, replay protection, account linking/authorization, HTTPS hosting and Amazon Console configuration before connecting a live skill.


## Latest task implementation (2026-10-18)

This section records the additional features added after the initial 34-test report above. The earlier 34-test count and intermediate 49-test run are historical; the current local suite contains **50 tests**.

### Files changed or added in the latest pass

- `apps/api/src/accord_api/api/routes/alexa.py` — disables the adapter by default and requires a temporary shared-secret header when locally enabled.
- `apps/api/src/accord_api/api/routes/assistant.py` — process-local chat rate limiter and deterministic shareable-data-only meal-plan draft endpoint.
- `apps/api/src/accord_api/api/routes/assignments.py` and `apps/api/src/accord_api/repositories/in_memory.py` — explicit confirmed task-reassignment route, idempotent assignment links, and duplicate-safe constraint indexes.
- `apps/api/src/accord_api/api/routes/fairness.py` — deterministic eight-week seeded solver-vs-round-robin simulation.
- `apps/api/src/accord_api/api/routes/mediation.py`, `apps/api/src/accord_api/services/use_cases.py`, `apps/api/src/accord_api/persistence.py`, and related models/schemas — saved safe mediation sessions, votes, deterministic tie rule, draft agreement creation, subset/custom expense split allocations, and workload drift reporting.
- `apps/web/src/App.tsx`, `apps/web/src/App.css`, `apps/web/src/voice/verdict.ts`, `apps/web/src/voice/DecisionVerdictCard.tsx` — time-aware greeting, mediation votes/session restoration, fairness charts, subset/custom split inputs, chat confirmation cards, meal-plan draft, privacy dashboard, workload-drift view and browser-only spoken verdict cards.
- `tests/test_extended_features.py` — reset idempotence, clause deduplication, expense split rounding, mediation voting/ties/privacy, SQLite session persistence, meal draft, rate limit, reassignment, drift and integrated interview/fairness/mediation/settle-up workflow.
- `tests/test_product_features.py` — Alexa adapter disabled-by-default and shared-secret checks.
- `.github/workflows/ci.yml`, `.env.example`, `README.md`, `docs/DEMO_SCRIPT.md`, `docs/ALEXA_INTENT.md` and `apps/web/openapi.json` — CI, environment/security docs, demo guide and API spec updates.

### Latest verification actually run

- Backend tests: **50 passed in 2.67s** (`PYTHONPATH=apps/api/src:packages/sim/src ACCORD_PERSISTENCE=memory python -m pytest -q`). This includes the HTTP integration journey for reset, private interview consent/derivation, fairness comparison and 8-week simulation, mediation votes/close, and settle-up, plus regressions for clause deduplication by normalized preference/text, reset task-name uniqueness and idempotency, duplicate constraint-index entries, workload drift completion timestamps, subset expense splits and ties.
- Python compilation: `python -m compileall -q apps/api/src packages/sim/src tests` completed successfully.
- Route smoke checks: `GET /healthz` (200), demo reset (201), household lookup (200), list members (200), assistant status/chat (200), meal plan draft (200), privacy dashboard (200), fairness compare and 8-week simulation (200), mediation create/vote/close (201/200/200), settle-up (200; the subset-split/net-zero invariant is also asserted by the backend tests), weekly digest (200), workload drift (200), and Alexa adapter disabled by default (503).
- OpenAPI spec regenerated from the current FastAPI application. All 9 new/important routes checked are present in the 49-path specification.
- TypeScript/JSX syntax transpilation: `App.tsx`, `api.ts`, `main.tsx`, `voice/DecisionVerdictCard.tsx`, and `voice/verdict.ts` all passed syntax transpilation with zero syntax diagnostics. This is not a full TypeScript type-check.
- Frontend `npm ci` was attempted but could not complete because this environment cannot resolve `registry.npmjs.org` (`EAI_AGAIN`). `npm run build` then failed because incomplete `node_modules` lacked `vite/client` and Node type definitions; `npm run lint` failed because ESLint wasn't installed. Therefore the full Vite build and lint are **unverified**, not passed. Re-run the npm checks on a network-connected machine.
- Equivalent API integration E2E: `test_end_to_end_demo_to_mediation_vote_and_settle_up` exercises the reset → interview consent/derived shareable constraints → fairness comparison → mediation voting/draft → settle-up journey through FastAPI HTTP endpoints. No browser-driven Playwright test was run in this environment.


### Final verification and small reliability regressions (2026-10-18)

- Made constraint repository indexing idempotent when a batch is replayed, so the same derived constraint cannot appear multiple times in member/household indexes.
- Strengthened demo reset regression assertions to catch duplicate chore names as well as duplicate assignment IDs and to compare counts across two consecutive resets. The reset test also verifies four seeded expenses and one subset-split expense shared by two members.
- Regenerated/checked the checked-in OpenAPI file: **49 paths**; the mediation sessions, eight-week fairness simulation, privacy dashboard and split-aware settle-up paths are present.
- The API end-to-end test is an HTTP-level FastAPI `TestClient` integration test, not a browser-driven Playwright run.

### Security and functionality boundaries

- AI voice playback uses the browser Speech Synthesis API only; it does not send audio to a server. Captions are always rendered.
- `X-Member-Id` is a local demo identity, not authentication.
- Alexa adapter shared-secret protection is a temporary local guard, not Alexa signature/timestamp verification.
- Assistant rate limiting is process-local, not a production API gateway.
- Workload drift and digest are on demand; no notification is sent. Monitoring can include simulated signals.
- A mediation vote creates a draft agreement. The normal explicit submit/approval/activation flow remains required.
- Settle-up computes suggested transfers only; it never records or executes a payment.
- LLM support is optional. With no key, deterministic/guided fallbacks work. Raw private interview answers and private-classified constraints must not be passed to LLMs, fairness solver, digest, or spoken verdicts.

## Global voice layer integration (2026-10-20)

### Files changed or added

- `apps/web/src/main.tsx` — wraps the app in `VoiceProvider`.
- `apps/web/src/voice/speech.ts` — browser-only speech cleanup, rupee/paise and minute normalization, text chunking, and support detection.
- `apps/web/src/voice/voiceContext.ts` — shared `useVoice` API and `useSpeakOnChange` hook.
- `apps/web/src/voice/VoiceProvider.tsx` — single speech-synthesis owner, shared voice state stored in local storage, `data-speak` observer, queueing, and stop/cancel support.
- `apps/web/src/voice/VoiceControls.tsx` — shared top-bar, chat, and settings toggle.
- `apps/web/src/voice/DecisionVerdictCard.tsx` — shared `useVoice().speak`, persistent captions, browser support fallback, and manual “Hear it” action.
- `apps/web/src/voice/speech.test.ts` — Vitest tests for `cleanForSpeech` and `chunkText`.
- `apps/web/src/App.tsx` and `apps/web/src/App.css` — shared voice integration, curated auto-speech summaries on the requested results, voice skip attributes for sensitive inputs and navigation, chat speech stop behavior, and navy/violet voice-control styles.
- `apps/web/package.json`, `apps/web/tsconfig.app.json`, `apps/web/README.md` — helper test command, test-file exclusion from production app compilation, and voice documentation.

### Privacy and behavior notes

The voice layer uses only the browser Web Speech API and makes no speech-server calls. Automatic speech is limited to curated `data-speak` values; it does not scrape arbitrary page text. Raw private interview and mediation form fields are marked `data-voice-skip`; the sidebar, decorative assistant orb, and loading indicators are excluded. Error banners are spoken as generic safe summaries while the visible banner retains diagnostic details. Agreement verdict speech uses status/counts rather than a free-text rationale. `DecisionVerdictCard` captions remain on screen if speech synthesis is unsupported; explicit “Hear it” actions use the shared provider and can interrupt current speech. Money is normalized to rupees/paise and durations to minutes. Fairness verdicts retain the heuristic disclaimer.

### Checks actually run for this voice change

- Node-based assertions against `cleanForSpeech` / `chunkText`: passed (`VOICE_HELPER_CHECKS_OK`), including INR formatting, markdown link cleanup, code-block omission and chunk ordering/length. This is a direct helper check; the Vitest runner itself was not run because npm registry access is unavailable.
- Standalone global TypeScript compiler check for `src/voice/speech.ts`: passed (`SPEECH_TSC_OK`) with an empty type root to avoid incomplete local package metadata.
- TypeScript/TSX syntax transpilation: passed for all 10 source files (`TS_TSX_SYNTAX_OK (10 files)`). This checks syntax only and is not a full React/Vite type-check or build.
- Backend tests rerun: **50 passed in 3.33s**. Python compilation: `COMPILEALL_OK`. These backend results are unchanged by the frontend voice integration.
- `npm ci --no-audit --no-fund --fetch-retries=0 --fetch-timeout=12000`: failed with npm exit code 1; npm log reports `EAI_AGAIN` for `registry.npmjs.org` and `Exit handler never called!`.
- `npm run build`: failed because dependency installation was incomplete (`vite/client` and Node type definitions not found).
- `npm run lint`: failed because ESLint was not installed (`eslint: not found`, exit code 127).
- Accordingly, the full frontend type-check/build/lint and Vitest runner remain **unverified** until dependencies can be installed on a network-connected machine.
