# Accord — Fairer Household Decisions, With Voice

Accord is a prototype for helping a household make everyday decisions more fairly and transparently. It combines explainable task allocation, consent-aware assistance, mediation workflows, and a browser-based voice experience.

> **Project status:** Prototype / hackathon project. Alexa integration and production deployment are not complete. Do not treat the current build as a production-ready service.

## Why Accord?

Household responsibilities can become a source of friction when work is distributed unevenly or the reasons behind a decision are unclear. Accord aims to make those decisions easier to discuss by providing:

- **Fairness-aware planning** to help distribute household tasks.
- **Explainable decisions** so people can understand the rationale behind a proposed plan.
- **Mediation support** for discussing disagreements.
- **Human approval gates** before proposed changes are applied.
- **Consent-aware AI assistance** designed to share only the derived context needed for a response.
- **Browser voice controls** using the Web Speech API, with visible captions and controls.

Accord is a decision-support prototype, not a substitute for household members' judgement or consent.

## Key features

- Household demo initialization and sample data.
- Fairness and task-assignment workflows.
- Structured assistant responses with deterministic fallback behavior.
- Interview/consent flow and privacy-oriented context handling.
- Mediation and settle-up-related product flows.
- Voice provider and controls for supported browsers.
- Backend API tests and frontend voice tests.
- CI workflow for automated project checks.

Feature availability may depend on the selected demo flow and current implementation.

## Architecture at a glance

```text
Browser UI (React + TypeScript + Vite)
        |
        | HTTP API
        v
Python API (FastAPI)
        |
        +-- Household, assignments, fairness and mediation workflows
        +-- Structured assistance and privacy/context handling
        +-- Persistence/repository interfaces
        |
        v
Simulation / domain interfaces

Browser voice layer:
Web Speech API -> captions / spoken responses
(no voice-server call is required by the browser voice layer)
```

### Main folders

| Path | Purpose |
| --- | --- |
| `accord-alexa-plus/apps/web/` | React + TypeScript web application |
| `accord-alexa-plus/apps/api/` | Python API and application services |
| `accord-alexa-plus/packages/sim/` | Simulation/domain support package |
| `accord-alexa-plus/tests/` | Backend test suite |
| `accord-alexa-plus/docs/` | Specification, architecture, UX, Alexa intent notes and demo script |
| `accord-alexa-plus/.github/workflows/ci.yml` | GitHub Actions CI workflow |

## Requirements

- Git
- Python 3.11+ recommended for the backend environment
- Node.js 20+ recommended for the web application
- A modern browser; voice support depends on browser and operating-system Web Speech API support

The original validation report was run in a Linux environment with Node 22 and Python 3.13. Windows commands may differ slightly.

## Run locally

Open a terminal at the repository root.

### 1. Start the backend

Create and activate a virtual environment:

**Windows PowerShell**
```powershell
cd accord-alexa-plus
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS / Linux**
```bash
cd accord-alexa-plus
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start the API with the source directories on `PYTHONPATH`:

**Windows PowerShell**
```powershell
$env:PYTHONPATH = "apps/api/src;packages/sim/src"
python -m uvicorn accord_api.app:app --reload
```

**macOS / Linux**
```bash
PYTHONPATH=apps/api/src:packages/sim/src python -m uvicorn accord_api.app:app --reload
```

If `uvicorn` is not installed by the requirements file, install the backend's declared dependencies and check `apps/api/README.md` for the project's current launch instructions.

### 2. Start the web application

In a second terminal, from the repository root:

```bash
cd accord-alexa-plus/apps/web
npm ci
npm run dev
```

Vite prints the local URL in the terminal (commonly `http://localhost:5173`). Keep the backend running in its own terminal. If the frontend cannot reach the API, check the API base URL and CORS settings in the project configuration.

## Run checks

From `accord-alexa-plus/`:

### Backend tests
```bash
python -m pytest
```

### Frontend checks
```bash
cd apps/web
npm ci
npm run build
npm run lint
npm run test:voice
```

The project has previously been validated with 50 backend tests and 4 voice tests passing, and with the frontend build and lint checks passing after fixes. Re-run these commands on your machine and check the latest **Actions** run before relying on that result.

## Demo walkthrough

For a short presentation, use this sequence:

1. Start the backend and frontend.
2. Open the local web app.
3. Initialize the demo household.
4. Walk through the consent/interview flow.
5. Generate and review a fair task plan.
6. Explain the rationale shown for the plan.
7. Demonstrate the mediation flow.
8. Show the voice controls and captions in a supported browser.
9. Finish by explaining what is implemented, what is simulated, and what remains future work.

See [`accord-alexa-plus/docs/DEMO_SCRIPT.md`](accord-alexa-plus/docs/DEMO_SCRIPT.md) for the current demo script and [`accord-alexa-plus/docs/ARCHITECTURE.md`](accord-alexa-plus/docs/ARCHITECTURE.md) for more implementation detail.

## Voice and Alexa status

The current browser voice layer uses the browser's Web Speech API. Browser support and voice availability vary by browser and operating system.

**Alexa is not yet a production-ready integration.** The Alexa endpoint and intent documentation are part of the prototype, but request-signature/timestamp verification, a complete deployable skill interaction model, a hosted HTTPS endpoint, and end-to-end Alexa validation remain work to complete. Do not describe the project as a live Alexa skill until those items have been implemented and tested.

## Privacy, security and known limitations

- The prototype is designed around consent-aware context and derived information, but this is not a formal privacy or security certification.
- The current member identity mechanism is prototype-level and is not production authentication.
- SQLite persistence is not encrypted in the current prototype.
- The Alexa endpoint must not be exposed publicly until request verification and production security controls are implemented.
- No live deployment is claimed.
- Browser end-to-end coverage and demo media should be added before final submission.
- Do not commit `.env` files, API keys, tokens, credentials, or real household/private data. Use `.env.example` as a template where applicable.

## Screenshots and demo video

Screenshots and a demo video have not yet been added to this repository. Add them here when ready, for example:

```text
docs/
  media/
    dashboard.png
    fair-plan.png
    mediation.png
    voice-controls.png
    accord-demo.mp4
```

Then link them from this section so reviewers can quickly see the product without setting it up locally.

## Roadmap

- [ ] Complete Alexa request signature and timestamp verification.
- [ ] Add and validate the Alexa interaction model, including appropriate spoken responses.
- [ ] Deploy the API behind HTTPS and validate a real Alexa skill flow.
- [ ] Add browser end-to-end tests to CI for the main user journey.
- [ ] Improve first-run demo experience and offline readiness.
- [ ] Add screenshots and a short demo video.
- [ ] Strengthen authentication, persistence security and accessibility testing.

## Project documentation

- [Specification](accord-alexa-plus/docs/SPEC.md)
- [Architecture](accord-alexa-plus/docs/ARCHITECTURE.md)
- [UX notes](accord-alexa-plus/docs/UX.md)
- [Voice-first UX](accord-alexa-plus/docs/VOICE_FIRST_UX.md)
- [Alexa intent notes](accord-alexa-plus/docs/ALEXA_INTENT.md)
- [Demo script](accord-alexa-plus/docs/DEMO_SCRIPT.md)

## Contributing

For changes, create a branch, make the change, run the relevant tests and checks, then open a pull request with a clear description of what changed and how it was tested.

## License

No license has been specified yet. Unless a license is added to the repository, all rights remain with the copyright holder and reuse is not automatically granted.
