# Task queue

Loop per task (details in `REVIEW-PROTOCOL.md`): Cursor builds ("Do T0N"), a fresh Cursor chat does the first review ("First review T0N"), Claude gates in a new session ("Gate T0N"), Cursor merges ("Merge T0N"). Fixes come back as `tasks/T0N.fix.md` ("Do T0N.fix").

Cards marked *(card later)* are written by Claude after the cards before them are reviewed.

| ID | Owner | What | Depends on | Status |
|---|---|---|---|---|
| T01 | Cursor | App shell, routes, tokens, i18n EN/AR, fixtures, server stub, `scripts/verify.py`, screenshots | none | ready |
| T02 | Cursor | Sources, norms and cut-offs transcribed with table refs; `screen/norms.py`, `screen/flags.py` and tests | none (parallel with T01) | ready |
| T03 | Cursor | `screen/gaitsynth.py`: synthetic 3D walk, TUG, sit-to-stand, single-leg stance, with tests | none (parallel) | ready |
| C02 | Claude | Offline run of NODAL's gait engine (adapter kept in the private NODAL repo); featured participants written to `data/samples/` | T02, T03 | |
| T04 | Cursor | Cohort generator and programme dashboard with the small-cell rule | T02 | draft |
| T05 | Cursor | Clinician review queue, pathway choice, FHIR R4 preview | T01 | draft |
| T06 | Cursor | Enrolment and consent, capture protocol, history view, About page draft | T01 | draft |
| T11 | Cursor | Participant report from Claude's spec (C05), fixtures retired | C02, T05, T06, T07 | ready after those merge |
| C05 | Claude | Report spec (T11 card) and gate | T11 | |
| T07 | Cursor | Server API (stored AI texts, capped live AI behind a flag), Dockerfile, `deploy.ps1` modeled on CellPilot (C08's build half) | T01 | ready |
| C06 | Claude | Frontend polish pass over every screen, EN and AR, desktop and phone | T04 to T06 | |
| T10 | Cursor | AI text generator: prompts, checks, dry run with cost estimate, fake-client tests; never a paid call | T01 | ready |
| C07 | Claude | Run T10 for real on the featured sessions (paid, Kirk approves the quoted cost) | C02, T10 | |
| C08 | Claude | Deploy to Cloud Run with T07's `deploy.ps1` (paid, Kirk approves) | T07, C06 | |
| T08 | Cursor | Playwright recording script for the film, full screenshot set | C08 | *(card later)* |
| T09 | Cursor | README and `docs/TECHNICAL.md` drafts from Claude's outline | C02 | *(card later)* |
| V1 | Cursor | Film: copy `D:\strain-watch-out\hf` structure, three storylines | T01 | *(card later)* |
| V2 | Cursor | Film compositions from Claude's SPEC | V1, C09a | *(card later)* |
| C09 | Claude | Film: SPEC (C09a), paid Veo and voice, check and snapshot review, render, loudness | V1, V2 | |
| C10 | Claude | Form answers, final technical doc, check of the form text against the code | all | |
