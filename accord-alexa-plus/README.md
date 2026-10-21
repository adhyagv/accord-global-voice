# Accord — Alexa+ Household Diplomat Prototype

Accord is a voice-first household planning prototype for families, couples, roommates and other shared homes. It brings conversational help, routines, chores, bills, private check-ins, fair proposals, assignments and simulated monitoring into one simple workspace.

> **Prototype boundary:** integrations, identity and monitoring are simulated. `X-Member-Id` is a local demo identity header, not production authentication. Do not use this prototype for real household disputes or sensitive production data.

## Persistence

The backend now uses a local SQLite database by default. SQLite ships with Python, so no MongoDB server or extra package is required. Data is written to `data/accord.sqlite3` after each API request and restored automatically when the API restarts.

- Override the database file with `ACCORD_DB_PATH`, for example `$env:ACCORD_DB_PATH = "C:\Users\Adhya\accord-data\accord.sqlite3"`.
- Set `ACCORD_PERSISTENCE=memory` to use ephemeral in-memory data instead.
- The demo reset endpoint intentionally replaces the current demo dataset.
- The database stores private interview answers locally. Use only synthetic/demo data for this prototype; local SQLite files are not encrypted by this implementation. Real deployments need authentication, access control, encrypted storage and backups.

## Requirements

- Python 3.11+ (Python 3.13 was used for the included test run)
- Node.js 20+ and npm

## Run on Windows PowerShell

Open PowerShell terminals from the project root. If you extracted the latest refreshed ZIP to `C:\Users\Adhya\accord-refreshed`, the project root is:

`C:\Users\Adhya\accord-refreshed\accord-alexa-plus`

Use that exact folder path in the commands below, or substitute the folder where you extracted the ZIP.

### 1. Install backend dependencies

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Keep using `.\.venv\Scripts\python.exe` from the project root to avoid accidentally running a different Python environment.

### 2. Start the API

```powershell
$env:PYTHONPATH = "$PWD\apps\api\src;$PWD\packages\sim\src"
.\.venv\Scripts\python.exe -m uvicorn accord_api.app:app --app-dir apps/api/src --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/healthz` and open API docs at `http://127.0.0.1:8000/docs`.

### 3. Start the web app

```powershell
cd apps\web
npm ci
npm run dev
```

Open the local URL printed by Vite (usually `http://localhost:5173`). The frontend calls the API at `http://127.0.0.1:8000` by default. Set `VITE_ACCORD_API_URL` before `npm run dev` to override it.

### 4. Initialize the demo

In the app, click **Reset demo scenario** once. This creates deterministic demo data, including the household, three members, sample interviews/constraints, a proposal, assignments and simulated monitoring signals. The current dataset is saved to SQLite. Resetting replaces the current demo dataset.

Then try:

1. **Home:** chat or speak to Accord. Use `Ctrl+K` (or `Cmd+K` on macOS) to open Quick jump and search pages, members, tasks, agreements and expenses.
   - By default, Accord uses a guided, rule-based assistant and does not require an API key.
   - To enable generative replies, copy `.env.example` to `.env`, set `ACCORD_LLM_API_KEY`, and start Uvicorn with `--env-file .env`. `ACCORD_LLM_BASE_URL` and `ACCORD_LLM_MODEL` can point to an OpenAI-compatible provider. Only the current chat message is sent to that provider; private interview records are not included. The assistant suggests workflows but does not mutate records directly.
2. **My Household:** choose Family, Couple, Roommates, Shared home, or Other; add people using the relationship/role that fits.
3. **Plans:** review tasks and existing agreement proposals.
4. **Chores / Bills / Calendar:** create tasks, update statuses, record expenses and view upcoming assignments.
5. **Mediation room:** submit at least two member perspectives only when each member has current consent and separately checks permission to share that statement; review three compromise options, then manually choose whether to draft a counteroffer.
6. **Fair plan & decisions:** use the fairness lab slider to compare Accord's workload-aware heuristic with a round-robin baseline; generate shareable draft clauses for member review.
7. **Bills:** run Optimize settle-up to calculate split-aware reimbursement suggestions from recorded expenses. It does not transfer money.
8. **Household balance:** generate an on-demand seven-day digest and inspect simulated drift signals before deciding whether to renegotiate.


## Reliability fixes in this version

- Agreement clause drafts are deduplicated by normalized source preference plus normalized clause text while preserving deterministic order.
- Demo reset tests check repeated resets keep the same assignment count and do not duplicate chore names; the demo also seeds four realistic expenses, including one allocated to a two-member subset.
- Constraint repository indexes tolerate replayed duplicate records without showing duplicate derived preferences.
- The Home greeting uses the local time of day.

## Added mediation, fairness and decision features

- **Saved mediation sessions:** the Mediation Room stores the topic, neutral restatements, options, vote map and status only. Raw statements are not part of the session schema. Members with current household consent can change their vote until the session closes. Once all currently consenting members have voted, the server chooses the most-voted option; ties choose the earliest displayed option and flag the tie. Closing creates a **draft** agreement which still needs the ordinary member-review and approval workflow.
- **Fairness Lab:** a single-allocation solver-vs-round-robin preview and an 8-week seeded simulation. It does not save tasks. Task loads are synthetic; only permitted shareable derived constraints may affect the solver. Results are heuristic and are not a guarantee of fairness.
- **Decision verdict cards:** captions are always available; “Hear the verdict” uses browser Web Speech API locally and makes no audio server call. The global Voice on/off toggle gates speech. Unsupported browsers keep the captions. Drafts are labeled as needing household confirmation.
- **Expenses:** expense creation supports all-member equal splits, subset splits and custom integer ratios. Minor-unit allocation uses deterministic largest-remainder handling, and settle-up computes net-zero reimbursement suggestions only; no payment is sent or marked complete.
- **Meal plan:** a seven-day rota is a draft based on consenting members and shareable availability/preferences only. It is not saved as calendar events or assignments.
- **Workload drift:** the Monitoring page can check completed work in the last 21 days. The default threshold is 40% (`ACCORD_WORKLOAD_DRIFT_THRESHOLD`); the signal is shown on demand and in the weekly digest, and sends no notification.
- **Privacy dashboard:** `Privacy` reads the backend's actual provider configuration and describes the data boundaries. When an LLM provider is configured, only endpoint-specific sanitized payloads should cross the provider boundary; raw private interviews and private-classified constraints are excluded from mediation/fairness/drafting provider inputs.
- **Confirm-before-act chat:** a supported reassignment suggestion appears as an Approve/Reject card. Approval explicitly calls the reassign endpoint under the currently selected demo member; Reject makes no backend change. The action outcome appears in Chat History for the current browser session.
- **Alexa request adapter:** disabled by default. For a controlled local test only, set `ACCORD_ALEXA_ENABLED=true` and `ACCORD_ALEXA_SHARED_SECRET`, then send `X-Accord-Alexa-Secret`. That is a temporary shared-secret guard, not Amazon signature verification. Do not expose it publicly.
- **Assistant rate limit:** `ACCORD_ASSISTANT_RATE_LIMIT_PER_MIN` sets the small process-local assistant chat limit (default 60 requests per minute per client IP). This is prototype protection, not a distributed gateway rate limiter.

## Environment settings

Copy `.env.example` to `.env` when needed. Keep secrets out of Git. Optional settings include `ACCORD_LLM_API_KEY`, `ACCORD_LLM_BASE_URL`, `ACCORD_LLM_MODEL`, `ACCORD_ALEXA_ENABLED`, `ACCORD_ALEXA_SHARED_SECRET`, `ACCORD_ASSISTANT_RATE_LIMIT_PER_MIN`, `ACCORD_WORKLOAD_DRIFT_THRESHOLD`, `ACCORD_PERSISTENCE`, and `ACCORD_DB_PATH`. A configured model receives only the sanitized endpoint payload, not the raw private interview answers. The selected `X-Member-Id` remains a demo identity header; the app has no production-grade authentication.

## Tests and build

From the repository root:

```powershell
$env:PYTHONPATH = "$PWD\apps\api\src;$PWD\packages\sim\src"
.\.venv\Scripts\python.exe -m pytest -q
cd apps\web
npm ci
npm run build
npm run lint
```

## Privacy and implementation notes

- Consent is required before starting/submitting/completing interviews and deriving constraints.
- Raw interview answers are never returned by the shared interview serializer.
- Derived constraints are classified separately from private context.
- The fairness solver is a deterministic, explainable workload-balancing heuristic. The fairness lab compares it with a simple round-robin baseline and lets you preview how permitted preference influence changes a proposed allocation; previews do not save assignments. Scores are not objective guarantees of fairness.
- The mediation endpoint accepts only statements with explicit per-statement sharing consent from members whose household consent is currently granted. Requests are not stored; a guided fallback is available without an LLM key.
- Agreement clauses are drafted only from permitted shareable derived summaries, not raw private interview answers. Generated clauses remain drafts until the household reviews and agrees.
- The settle-up optimizer respects each expense participant subset and optional custom integer split ratios, uses deterministic cent rounding, and produces a minimal greedy transfer plan. No payment is initiated.
- The weekly digest is generated on demand from recorded prototype data; it does not send scheduled notifications.
- The assistant uses a local guided fallback by default and supports an optional OpenAI-compatible chat provider. Provider replies are generated from the submitted message only; no household database or private interview records are added to the provider request.
- Demo reset and monitoring signals are prototype/simulated features; `X-Member-Id` is local demo identity rather than production authentication.
- Local SQLite persistence is enabled by default. `ACCORD_PERSISTENCE=memory` switches to ephemeral in-memory mode. This is not production authentication or authorization.


## Voice-first UX and integration boundary

- The Home screen provides voice/text chat, quick actions and household status cards.
- Voice input uses browser speech recognition where available (Chrome/Edge and microphone permission are typical requirements). Speech replies use the browser/device speech synthesizer and selected system voice.
- The household type selector is stored as a local browser preference; it does not update the backend household metadata.
- The assistant has a safe guided fallback when no LLM key is configured. An optional OpenAI-compatible provider can be enabled with `ACCORD_LLM_API_KEY`, `ACCORD_LLM_BASE_URL`, and `ACCORD_LLM_MODEL`; only the user's current chat message is sent to the provider, not household records or private interview answers. Chat replies suggest UI workflows; consequential writes still require user confirmation in the applicable workflow.
- Quick jump is available using Ctrl+K / Cmd+K and searches navigation plus loaded demo members, tasks, agreements and expenses.
- The browser provides local speech input and speech synthesis; that is separate from Alexa. A Skills Kit-compatible request adapter and custom intent handlers are included at `/api/alexa/skill-request`, but this is not yet a deployed Alexa Skill or live Alexa+ integration. Read `docs/ALEXA_INTENT.md`; do not expose the adapter publicly until Alexa signature verification, account/household authorization and HTTPS deployment are implemented.

## Back up or move the local database

The SQLite file is `data/accord.sqlite3` under the repository root. To move the app to another computer, stop the backend first, copy this file along with the source project, then restart the API. To keep the database somewhere else, set `ACCORD_DB_PATH` before starting Uvicorn. Do not commit or share the database file: it can contain private interview answers.

For deployment, use a managed PostgreSQL database and proper authentication/authorization rather than exposing this local SQLite snapshot adapter to multiple users.
## Global browser voice layer

The single voice controller is mounted in `apps/web/src/main.tsx` via `VoiceProvider`. Its implementation lives in `apps/web/src/voice/`: `speech.ts` formats captions for browser speech and splits long messages; `voiceContext.ts` defines `useVoice`; `VoiceProvider.tsx` owns the only speech-synthesis queue and voice-enabled setting; `VoiceControls.tsx` exposes the shared toggle; and `DecisionVerdictCard.tsx` offers captions plus a manual “Hear it” action. This layer uses only the browser Web Speech API and does not send speech text to a server.

Only curated, public-safe summaries should be assigned to `data-speak`. Place `data-voice-skip` on raw private interview/mediation inputs, navigation, loaders, and decorative UI. Never put raw interview answers, private constraints, or unrestricted private rationales in `data-speak` or a verdict card. Fairness verdicts must retain the caveat “This is a heuristic, not a guarantee of fairness.” Browser speech support varies; captions remain visible when speech is unavailable.

To test the speech helpers when npm registry access is available, run `npm run test:voice`; the script fetches pinned Vitest 4.0.14 through `npx`. `npm ci`, `npm run build`, and `npm run lint` still need to be run on a machine with access to `registry.npmjs.org`.
