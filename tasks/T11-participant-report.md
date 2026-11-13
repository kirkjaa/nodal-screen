# T11: participant report (C05 content, built by Cursor from Claude's spec)

Branch `t11-report`, from `main` **after C02, T05, T06 and T07 are merged** (it needs the nine measured sessions and `web/lib/aitexts.js`). Read `AGENTS.md` and `docs/CONTRACT.md` sections 2 to 5 first. You may edit `web/routes/participant.js` (this card replaces the C05 hold). Use the existing tokens and classes; Codex does the visual polish afterwards, so build clean structure, not styling. The front end never computes a flag or a status: it shows what the session file holds.

## Sections, in this order (`#/p/<pid>`)

1. **Header.** Display name, then one line: group, age band, sex, site, visit date, kit. The provenance badge as today.
2. **Summary** (a box at the top).
   - `qc.status` ok: the suggested pathway label, then "{n_flags} flags and {n_watches} watches for a clinician to review." (use "No flags or watches." when both are 0), then always: "A clinician reviews every flag and chooses the pathway."
   - `qc.status` insufficient: "This capture did not give enough data to report. Repeat the capture." then each `qc.notes` line.
3. **Flags.** One row per flag: a chip "Flag" or "Watch" (from `severity`), the title, the evidence, the source, the confidence. Source text: the short citation from `data/sources.json` for each `source_ids` entry, and "NODAL screening rule" for `nodal-rule` (never call it a guideline). Each flag links to its metric's row (`#m-<task>-<metric id>-<side>`).
4. **Results, one table per task** that is present (gait, TUG, sit-to-stand, single-leg stance, tandem, hop; a task that is absent is not shown). Columns: Measure (label plus side), Value (value and unit, never wrapped), Reference, Cut-off, Status.
   - Reference: "mean {mean} {unit}" plus ", SD {sd}, z {z}" when present; "reference value pending verification" when the norm's `status` is `placeholder`; a dash when `ref` is null.
   - Cut-off: "{op} {threshold} {unit}, {source}" plus "met" or "not met"; for `nodal-rule` the source is "NODAL screening rule". A dash when `cutoff` is null.
   - Status labels: `in_range` "Within reference", `borderline` "Near the edge", `out_of_range` "Outside reference", `no_reference` "No reference loaded", `insufficient` "Not reported".
5. **Joint angles** (only when `tasks.gait.curves` has data). One inline SVG chart per curve (`knee_flexion`, `hip_flexion`): x 0 to 100 % of the gait cycle, y in degrees with gridlines every 10 or 20, left solid and right dashed, a legend, axis labels, `<title>` and `<desc>` for screen readers. No chart library. Draw a band only if `norm_mean` and `norm_sd` hold 101 values; today they are empty, so under the charts: "Mean of the measured strides. No reference band is loaded for joint-angle curves."
6. **Change over time** (only when `history` is not empty): a small table of visit, date and gait speed, the current visit last, and the change flag's evidence if there is one. Link "See the full history" to the T06 history route.
7. **Capture check.** Status, confidence, strides left and right, keypoint confidence, notes. When `calib_residual_px` is null: "Calibration residual: not applicable (synthetic take, no camera)."
8. **Drafted texts.** `await renderAiTexts(session, lang)` from `web/lib/aitexts.js`, unchanged.
9. **Footer**, always: "Screening, not diagnosis. NODAL Screen flags results for review; a clinician reviews and diagnoses." and the provenance note from the session.

All strings go through `web/i18n/en.json` and `ar.json` with the English above exactly; Arabic keeps the machine-translation note. Arabic is right to left; numbers and units stay left to right inside it.

## Retire the two T01 fixtures

Move `SYN-C-0007.json` and `SYN-A-0102.json` from `data/samples/` to `tests/fixtures/`; point `scripts/make_fixtures.py`, `tests/test_samples.py` (check both folders) and every route in `scripts/shots.cjs` that names them (participant, history, review) at the measured pids instead. Nothing in `web/` may name a pid.

## Done when

- `python -m pytest -q` passes and `python scripts/verify.py` ends with `VERIFY OK`.
- Shots of `#/p/<pid>` for `SYN-C-0102`, `SYN-C-0104`, `SYN-A-0203`, `SYN-A-0204` and `SYN-A-0205`, EN at 1440 and AR at 390, plus a contact sheet `out/review/T11-sheet.png` (at most 12 tiles).
- `tasks/done/T11.md` (at most 30 lines) lists the files changed and any string you could not place.
