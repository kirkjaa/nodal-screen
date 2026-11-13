# T06: enrolment, capture protocol, history, About

Branch `t06-enrol-history`. Read `AGENTS.md` and `docs/CONTRACT.md` sections 1, 2, and 6 first. Replace four T01 placeholders. Do not rebuild the participant report; Claude owns that page.

## Build

1. **Enrol** replaces `web/routes/enrol.js` at `#/enrol`. Show two consent texts at once, English and Arabic: one for an adult, and one for a guardian plus the child's assent. Mark both as demo wording, not legal text. Include an opt-out control. Choosing opt-out ends on a sentence that nothing was stored. Submitting the demo keeps the answers in `localStorage` only (try/catch, key starting `nodal-screen-`) and says they are not stored on a server. No name that is not already a synthetic display name, no photo input, no upload.
2. **Capture** stays at `#/capture` for an adult and adds `#/capture/child` in `web/app.js`. Adult steps, in order: 10 m walk, Timed Up and Go, 5 times sit-to-stand, single-leg stance. The child page adds tandem walk and hop. Say this page is not connected to a camera. No device calls.
3. **History** replaces `web/routes/history.js` at `#/p/<pid>/history`. Load the session with `loadSession`. Show each `history` visit (date, visit id, metrics) and the current visit's gait speed. If a flag has `rule` `change`, show that flag's title and evidence. If `history` is empty, show an empty state. Do not apply the 0.05 or 0.10 m/s rule in JavaScript. Badge from the session. `SYN-A-0102` is the empty case. `SYN-C-0007` has one earlier visit.
4. **About** replaces `web/routes/about.js` at `#/about`. Short method, assumptions, and limitations. Load `/data/sources.json` and list each `citation` and `used_for`. Do not call a source verified. Say reference values marked placeholder are pending verification. Say the product measures and flags, and that it is not yet validated. Say complementary suppression is not applied. Say review decisions stay in the browser, and that a letter drafted from the measurements is not sent until a clinician approves it. Say every person in this prototype is synthetic. Leave one marked slot, i18n key `about.method.engine`, with the text "Method details: written by Claude."; Claude fills it. Do not describe code that is outside this repository.
5. New strings in `web/i18n/en.json` and `ar.json`. Keep the existing Arabic footer note. Tokens only, logical CSS, no horizontal scroll at 390 px.
6. `scripts/shots.cjs` already opens `#/enrol`, `#/capture`, `#/about`, and both history hashes. Add `#/capture/child`. `python scripts/verify.py` must end with `VERIFY OK`.

## Done when

- `python scripts/verify.py` ends with `VERIFY OK`.
- Done note `tasks/done/T06.md` lists the screenshot paths, including `capture-child` in EN and AR at both widths.

No new dependencies.
