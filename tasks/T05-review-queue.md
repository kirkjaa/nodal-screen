# T05: clinician review queue, pathway choice, FHIR preview

Branch `t05-review-queue`. Read `AGENTS.md` and `docs/CONTRACT.md` sections 1, 2, and 5 first. The browser displays flags. It does not calculate them.

## Build

1. **Queue** replaces the placeholder in `web/routes/review.js`. Keep `#/review`. Add `#/review/<pid>` in `web/app.js` `routeOf`. Build the list from `web/lib/data.js` (`loadIndex`, then `loadSession`). A session is in the queue when `flags` is not empty or `qc.status` is `insufficient`. Show pid, display name, group, age, the first flag title or the QC note, and the suggested pathway label. With the current fixtures, `SYN-C-0007` and `SYN-A-0102` both appear. Provenance badge on the list and on the detail.
2. **Decision**, on `#/review/<pid>`. Buttons for `confirm`, `dismiss`, and `recapture`. A pathway control lists the seven codes in CONTRACT section 5, with the session's `suggested_pathway.code` selected first. The clinician can change it. Optional note. Saving writes the `review` object from section 2 into `localStorage` under a `nodal-screen-` key, wrapped in try/catch, and does not write the JSON file. The screen says the decision is kept in this browser only. Reopening the same pid shows the saved decision.
3. **FHIR R4 preview** on the same detail page, after a decision is saved. A `ServiceRequest` with `status` `draft` and `intent` `order`. `subject.identifier.value` is the synthetic pid. The reason text is the flag titles, or `qc.notes` when there are no flags. Show the JSON in a block and a one-line reading of status, subject, and reason. The page says this preview is not sent and is not connected to Malaffi. No `fetch` except the local session files.
4. Strings through `web/i18n/en.json` and `ar.json`. Reuse pathway keys already added in T01 where they exist. Logical CSS, tokens in `web/ds/tokens.css` only, no horizontal scroll at 390 px.
5. Add `#/review/SYN-C-0007` to `scripts/shots.cjs` (the queue route is already there). For that detail shot, the script may click `confirm` and wait until the FHIR block is visible, in EN and AR at both widths. Fail on any console error. `python scripts/verify.py` must end with `VERIFY OK`.

## Done when

- `python scripts/verify.py` ends with `VERIFY OK`.
- A reload of `#/review/SYN-C-0007` still shows the decision, and the sample JSON files are unchanged.
- Done note `tasks/done/T05.md` lists the new screenshot paths and the localStorage key.

No new dependencies. No network call.
