# Accord API (TASK 003)

Backend core service for Accord's simulated household-negotiation prototype.

## Run locally
From repository root:

```bash
pip install fastapi uvicorn
PYTHONPATH=/home/runner/work/accord-alexa-plus/accord-alexa-plus/apps/api/src python -m uvicorn accord_api.app:app --reload
```

API base path: `/api`

## Notes
- All integrations are simulated.
- Privacy enforcement is server-side (authorization + private/shared serializers).
- The fairness solver is a deterministic placeholder (non-LLM) behind a replaceable interface.


## SQLite persistence

By default, Accord stores its complete domain snapshot in `data/accord.sqlite3` at the repository root. The API restores the snapshot on startup and saves after every request. This requires no external service or extra Python package.

Set `ACCORD_DB_PATH` to choose another database file or `ACCORD_PERSISTENCE=memory` to disable persistence. The SQLite adapter is intended for local development/hackathon demos only; interview answers are stored as ordinary local database content and are not encrypted at rest.
