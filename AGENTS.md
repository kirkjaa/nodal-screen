# NODAL Screen: rules for every agent (Cursor/Grok, Codex and Claude Code)

NODAL Screen is NODAL's prototype for the Future Health Challenge (Abu Dhabi), preventive screening statement. Portable 3D movement screening with NODAL M1: a 5-minute protocol (10 m walk, Timed Up and Go, 5x sit-to-stand, single-leg stance; children also tandem walk and hop), a gait report against age and sex norms, flags a clinician reviews, a suggested pathway (Well-Child Visit developmental review or an adult pathway), annual tracking, and a cohort view for programme managers. The Strain Watch code in `sw/` and `web/report.html` stays working: it becomes the "workplace crossover" tab.

**Deadline:** everything frozen by Thursday 19 November 2026, submitted Friday 20 November.

## Who does what

| Owner | Work |
|---|---|
| Cursor agent (Grok / Composer) | Tasks in `tasks/T*.md`: scaffold, data generators, norms transcription, flag engine, functional screens, i18n strings, server, Docker, Playwright scripts, doc drafts, film composition drafts |
| Claude Code | `docs/CONTRACT.md`, the offline run of NODAL's gait engine (kept outside this public repository), the participant report page's content (C05), every review gate, paid API calls, deployment, the film's spec and final review |
| Codex | Frontend polish (C06), see "Codex lane" below |
| Kirk | Relays tasks, approves spend, submits the form |

### Codex lane (C06 frontend polish, from 13 Nov)

If Codex is out of usage when T04 to T11 have merged, Claude does the next polish pass itself (Kirk, 13 Nov); Codex picks up from whatever is on `main` when it is back.

Polish status (13 Nov, Claude): the shell (wordmark bar, mono tabs, status footer), the participant panel (`#/p/<pid>`) and the overview roster now follow Strain Watch (`web/report.html`). Codex's next pass: bring the review queue, cohort, capture, enrol, history, about and replay pages to the same look (`.blk`, `.big`, `.mono k`, `.find`, `.warn`, `.chip`; `#view.wide` for full-bleed layouts), in EN and AR, 1440 and 390 px. Do not change the participant panel's content.

- Work in your own worktree `D:\nodal-screen-c06` on branch `c06-polish`, created from `main` **after "Merge T01"** (before that, `main` has no app shell). Rebase on `main` each time another task merges. Never commit to `main`, never merge, never push.
- Scope: the look and feel of every screen on `main`: `web/ds/`, `web/app.css`, layout, type, spacing, navigation, charts' styling, right-to-left Arabic, phone width (390 px), keyboard and contrast. Keep `web/report.html` (the workplace tab) working.
- Out of scope: `data/`, `screen/`, `server/`, `docs/CONTRACT.md`, the rules in `scripts/verify.py`, and which numbers, flags or statuses a screen shows (those come from the session files). Do not edit `web/routes/participant.js` until T11 (the report, built from Claude's C05 spec) is merged; then polish its styling only.
- Gait replay viewer: Claude built it (`web/lib/replay.js`, route `#/p/<pid>/replay`) while Codex was out of usage. Codex may restyle it; keep gaps as gaps, the participant's left as left in every view and language, and no computed metric.
- Wording: keep every honesty string as it is (provenance badges, "NODAL screening rule", "Drafted by AI ... A clinician approves ...", "not yet validated"). New visible text goes through `web/i18n/en.json` and `ar.json`, and Claude checks it at the gate.
- Shared files (`web/i18n/*.json`, the route table in `web/app.js`, `scripts/shots.cjs`) are also edited by Cursor's T04 to T07: change only the lines you need, so rebases keep both sides.
- Finish each pass with `python scripts/verify.py` (VERIFY OK), a contact sheet `out/review/C06-sheet.png` (EN and AR, 1440 and 390 px), and `tasks/done/C06.md` (at most 30 lines). Claude gates it like a task.

All data is synthetic. NODAL's gait engine is proprietary and not in this repository: Claude runs it offline and this repository holds only its results. This repository is public, so nothing private goes in it.

## How a task runs

1. Kirk says "Do T0N". Read `tasks/T0N-*.md` and `docs/CONTRACT.md` first. Do only what the card asks.
2. Work on a branch named `t0N-<slug>` from `main`. Never commit to `main`, never merge, never push. Merging and pushing happen only in the "Merge T0N" step of `tasks/REVIEW-PROTOCOL.md`, after Claude's PASS; a pre-push hook blocks everything else.
3. Run `python scripts/verify.py` (after T01 exists). It must end with `VERIFY OK`.
4. Write `tasks/done/T0N.md`, at most 30 lines: what changed (files), the last 10 lines of verify output, screenshot paths, anything not done, questions. Claude reads this note and the diff, so keep it exact.
5. Commit on the branch with a plain message. Stop.

If the card and `docs/CONTRACT.md` disagree, or something in the contract looks wrong, do not edit the contract. Say so in the done note.

## Hard rules

- **Screening, not diagnosis.** The product measures and flags; a clinician reviews and diagnoses. Never write that it diagnoses, detects a disease, is validated, accurate, approved, certified or clinically proven. Allowed: "flags for review", "suggested pathway", "not yet validated", "to be validated in the pilot". `scripts/verify.py` enforces a banned-phrase list.
- **Every screen shows where its data came from** with the provenance badge: `synthetic`, `simulated M1` or `measured`. No real person's data exists in this repo. Never add photos or video of children, ever.
- **No invented numbers.** A norm, cut-off or citation must come from the named source with its table or page. If you cannot read it in the source, put `placeholder` in the status column and say so in the done note.
- **No paid calls.** Never call Vertex, Gemini, Veo, Cloud TTS or any paid API. Use the stored outputs in `data/` and stubs. Claude runs real calls after Kirk approves the cost.
- **No secrets** in files: no keys, tokens, service-account paths or passwords. Config comes from environment variables.
- **Do not open** `F:\pi-camera-project` or `vendor/`: NODAL's proprietary gait engine stays out of this public repository. Claude runs it; you work against `docs/CONTRACT.md`.
- **Keep Strain Watch working:** `python -m pytest` must still pass for `tests/test_ergo.py`, `test_report_data.py`, `test_synth.py`.

## Code style

- Python 3.11, numpy/scipy, pytest. Windows first (PowerShell), paths with `pathlib`.
- Front end: plain HTML, CSS and ES modules, no build step, no framework. Charts are hand-built SVG. Use the NODAL Design System tokens already in `web/report.html` (`--n-*`, accent and type tokens); copy them into `web/ds/tokens.css`, never invent new colors.
- Arabic: every visible string goes through `web/i18n/en.json` and `ar.json`; the page flips with `dir="rtl"`, so use logical CSS properties (`margin-inline-start`, not `margin-left`). Arabic strings carry the note "machine translation, pending native review".
- UI copy: American spelling, short sentences, no em dashes, no hype words ("revolutionary", "seamless", "cutting-edge", "AI-powered").
- New dependencies: only if the card allows; list them in the done note.
