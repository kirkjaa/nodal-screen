# T07: session API, stored AI texts, Docker, deploy script

Branch `t07-server-docker`. Read `AGENTS.md` and `docs/CONTRACT.md` section 2 (`ai_texts` and `review`) first. Extend `server/main.py` from T01. Do not call a paid API. Do not run the deploy script.

## Build

1. **Read API.** `GET /api/session/{pid}` returns `data/samples/{pid}.json` or 404. `GET /api/health` stays `{"ok": true}`. Static `/` and `/data` stay as they are.
2. **Stored texts.** `GET /api/ai/{pid}` returns that session's `ai_texts` (an empty object when none are stored) and `live: false`.
3. **Live flag, capped, stubbed.** `POST /api/ai/{pid}` reads `NODAL_LIVE_AI` and `NODAL_DAILY_LIVE_RUNS` from the environment. Default the cap to 10 when the variable is unset. When `NODAL_LIVE_AI` is not `1`, respond 200 with the stored texts and `live: false`. When it is `1` and the in-memory count for this process is still under the cap, respond 503 with a short body that live AI is not configured, and count that call. Over the cap, respond 429 and do not increment past the cap. No outbound HTTP, no SDK, no key, no project id, and no credential path in the code or in tests.
4. **Tests** `tests/test_api.py`, using FastAPI's `TestClient`. Cover health, a known pid, an unknown pid, the flag off, the flag on (503 and no network), and the 429 cap. If `TestClient` needs `httpx`, add it to `requirements-dev.txt` only and name it in the done note.
5. **Report block.** Under the QC block in `web/routes/participant.js`, if `ai_texts` has a `family_letter` or a `clinician_brief`, show the English or Arabic string for the active language and the exact sentence: "Drafted by AI from the measurements. A clinician approves before anything is sent." A button asks the API and shows the response. When nothing is stored, say none are stored. Strings in both i18n files. The two current fixtures have empty `ai_texts`; do not invent letters.
6. **Docker.** `Dockerfile` based on `python:3.12-slim`. Copy `requirements.txt`, `server/`, `web/`, and `data/samples/` only. Run as a non-root user. Listen on `$PORT` with `uvicorn server.main:app --host 0.0.0.0`. Do not add packages the app does not import. `.dockerignore` excludes `.git`, `.venv`, `out`, and `data/raw`.
7. **`deploy.ps1`** follows the CellPilot shape and holds no secrets. `-Project` defaults to `$env:GOOGLE_CLOUD_PROJECT` and the script throws if it is empty. Region `asia-southeast1`, service name `nodal-screen`, `--allow-unauthenticated`, `--max-instances 1`, `--min-instances` default 0. Pass `NODAL_LIVE_AI=0` and the daily cap as env vars. Do not embed a project id, bucket, key, or account email. This task does not execute the script.

## Done when

- `python -m pytest -q` passes and `python scripts/verify.py` ends with `VERIFY OK`.
- `docker build` is not required for the done note. Say if Docker was not run.
- Done note `tasks/done/T07.md` lists the new routes and confirms no live call was made.

No paid API. No deploy.
