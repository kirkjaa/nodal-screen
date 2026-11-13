# T01: app shell, routes, i18n, fixtures, verify script

Branch `t01-app-shell`. Read `AGENTS.md` and `docs/CONTRACT.md` first.

## Build

1. **Server stub** `server/main.py` (FastAPI + uvicorn): serves `web/` at `/` and `data/` at `/data`, plus `GET /api/health` returning `{"ok": true}`. Run with `python -m uvicorn server.main:app --port 8080`. Add `fastapi`, `uvicorn`, `jsonschema` to `requirements.txt`.
2. **Tokens** `web/ds/tokens.css`: copy the NODAL Design System custom properties from `web/report.html` unchanged. `web/app.css` uses only those tokens.
3. **App shell** `web/index.html` + `web/app.js` (ES modules, hash router). Header: product name "NODAL Screen", nav, EN/AR toggle. Routes, each its own module in `web/routes/`:
   - `#/` overview: one line on what it does, the six steps from consent to annual tracking as a row of cards, links to the screens.
   - `#/enrol`, `#/capture`, `#/review`, `#/cohort`, `#/about`: a heading and a "built in T04 to T06" placeholder.
   - `#/p/<pid>`: participant report placeholder. Load `data/samples/<pid>.json` and render a plain, unstyled table: every metric (label, value, unit, reference, status), every flag, the suggested pathway, the QC block. Claude replaces this view later; keep the data-loading function separate (`web/lib/data.js`) so it can be reused.
   - `#/p/<pid>/history`: placeholder.
   - `#/crossover`: a short intro ("The same kit can screen workplace movement risk") and a link that opens the existing `report.html` (Strain Watch). Do not change `report.html`.
4. **Provenance badge** `web/lib/badge.js`: renders the badge from `provenance` per CONTRACT section 1, visible near the top of every route that shows data.
5. **i18n**: `web/i18n/en.json` and `ar.json`, every visible string keyed; the toggle sets `<html lang dir>` and remembers the choice in `localStorage` (wrapped in try/catch). Arabic strings: translate them yourself and add the footer note "Arabic: machine translation, pending native review".
6. **Fixtures**: `data/samples/SYN-C-0007.json` (child, 7, toe-walking flag, `WCV_DEV_REVIEW`) and `data/samples/SYN-A-0102.json` (adult, 70, `qc.status` insufficient, `RECAPTURE`), both following CONTRACT section 2 exactly, `provenance_note` ending "Hand-written fixture; replaced by pipeline output." Plus `data/samples/index.json` listing pids. Plausible values only; these are placeholders.
7. **Schema** `docs/session.schema.json`: JSON Schema for the session file, from CONTRACT section 2.
8. **`scripts/verify.py`** runs, in order, and exits non-zero on any failure:
   - `python -m pytest -q`;
   - validation of every `data/samples/*.json` against the schema;
   - the honesty scan over `web/`, `data/` and `docs/` (skip `docs/CONTRACT.md`): case-insensitive regexes `diagnos(e|es|is|ing|tic)`, `\bvalidated\b`, `clinically proven`, `\bcertified\b`, `\bFDA\b`, `CE[- ]mark`, `AI[- ]powered`, `revolutionary`, `seamless`, `cutting[- ]edge`, and the em dash character. Allowlist exact phrases: "does not diagnose", "clinician reviews and diagnoses", "clinicians review and diagnose", "not a diagnosis", "not yet validated", "to be validated". Print file:line for every hit;
   - screenshots, if `node` is on PATH: start the server on port 8099, run `scripts/shots.cjs`, stop the server;
   - print `VERIFY OK`.
9. **`scripts/shots.cjs`**: Playwright with Chrome (`chromium.launch({channel: 'chrome'})`), loaded from `NODE_PATH=C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules` (verify.py sets it). Screenshot every route in EN and AR at 1440x900 and at 390x844 into `out/shots/<route>-<lang>-<w>.png`. Fail on any console error.

## Done when

- `python scripts/verify.py` ends with `VERIFY OK`, and the three Strain Watch test files still pass.
- No horizontal scroll at 390 px wide on any route.
- Done note `tasks/done/T01.md` lists the screenshot paths.

No new dependencies beyond fastapi, uvicorn and jsonschema.
