# T04: cohort generator and program dashboard

Branch `t04-cohort`. Read `AGENTS.md` and `docs/CONTRACT.md` sections 1 and 6 first. The screen reads a cohort file. It does not compute flags.

## Build

1. **Generator** `screen/cohort.py`. A fixed seed writes `data/cohort.json` with `schema` `nodal-screen/cohort@1`, `provenance` `synthetic`, and `generated` set to the day the file is written. Sites are the three in CONTRACT section 6: `PHC-1`, `SCH-1`, `MAJ-1`. Each person is synthetic: `pid` starts with `SYN-`, `group` is `child` or `adult`, `sex` is `F` or `M`, `nationality_group` is `UAE national` or `Non-national`, `site` is one of the three, plus `invited`, `screened`, `flags`, `pathway`, `flag_date`, and `attended_date`. `flags` are metric ids from CONTRACT section 3. `pathway` is one of the codes in section 5. Display age bands, not norms: child `3-4`, `5-6`, `7-8`, `9-12`; adult `18-39`, `40-59`, `60-69`, `70-79`, `80-99`. Do not overwrite `data/samples/`. About 600 people. `pathway` must follow CONTRACT section 5 from the person's group and flags: import the pathway logic from `screen/flags.py`, do not copy it. `attended_date` is empty for some flagged people and 3 to 90 days after `flag_date` for the rest.
2. **Small-cell rule**, a pure function with tests in `tests/test_cohort.py`. A count or a rate whose cell has fewer than 10 people is shown as `<10` and is not plotted. A cell with 10 or more shows the number or the rate and may be plotted. Totals always show the true count, including when every part of the total is suppressed. Do not add complementary suppression.
3. The committed `data/cohort.json` uses that seed. It must contain at least one site-by-nationality cell under 10 and one at 10 or more, and the same for site by age band, so both sides of the rule are visible.
4. **Dashboard** replaces the placeholder in `web/routes/cohort.js`. Keep the hash `#/cohort`. Show the provenance badge from `web/lib/badge.js`. Show reach (invited and screened), flag counts, pathway counts, and pathway completion (the share of flagged people who attended within 30 and within 60 days, and the median days from flag to visit, the deck's success measures), each split by site and by nationality group, and by site and age band. Hand-built SVG only, using the tokens in `web/ds/tokens.css`. A suppressed cell is the text `<10` and has no bar. One line says complementary suppression is not applied. Every new English string goes in `web/i18n/en.json` and `web/i18n/ar.json`. The visible English title stays the existing key `overview.step.program` ("Program view"). Arabic strings stay under the existing footer note. No horizontal scroll at 390 px. Logical CSS only.
5. `scripts/shots.cjs` already visits `#/cohort`. Do not drop that route. `python scripts/verify.py` must still end with `VERIFY OK`.

## Done when

- `python -m pytest -q` passes, including the small-cell tests, and `python scripts/verify.py` ends with `VERIFY OK`.
- Done note `tasks/done/T04.md` names the seed, the cell that is under 10, the cell that is 10 or more, and the screenshot paths.

No new runtime dependencies.
