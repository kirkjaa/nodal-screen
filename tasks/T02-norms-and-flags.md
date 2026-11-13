# T02: reference values, cut-offs and the flag engine

Branch `t02-norms-flags`. Read `AGENTS.md` and `docs/CONTRACT.md` sections 3 to 5 and 7 first. This card is about getting numbers right: a missing value is fine, an invented one is not.

## 1. Sources and values

Create `data/sources.json`, `data/norms.csv` and `data/cutoffs.csv`.

`data/cutoffs.csv` columns: `source_id, metric, group, op, threshold, unit, meaning, table_ref, status`.

For each source: find the paper or guideline, record citation and DOI or URL, and transcribe the values **from the source itself**, with the table or page in `table_ref`. If you cannot open the source text, write the row with `status=placeholder`, leave a note in the done note, and move on. Do not fill numbers from memory.

| source_id | What to take |
|---|---|
| `bohannon2011` | Bohannon & Andrews 2011, Physiotherapy 97(3):182-189, normal walking speed meta-analysis: comfortable gait speed mean (and SD if given) by age decade and sex, 20 to 99 |
| `lythgo2009` | Lythgo, Wilson & Galea 2009, Gait & Posture 30(4):502-506, primary school-aged children: by age year 5 to 12 (and the adult group), free-speed walking speed, cadence, stride length, step time, double support, normalized values if given |
| `bohannon2006tug` | Bohannon 2006, J Geriatr Phys Ther 29(2):64-68, TUG reference values by age group |
| `bohannon2006sts` | Bohannon 2006, Percept Mot Skills 103(1):215-222, five-repetition sit-to-stand reference values by age group |
| `springer2007` | Springer et al. 2007, J Geriatr Phys Ther 30(1):8-15, single-leg stance, eyes open, by age group and sex |
| `steadi` | CDC STEADI Timed Up and Go assessment: the time at or above which an older adult is at risk of falling |
| `ewgsop2` | Cruz-Jentoft et al. 2019, Age Ageing 48(1):16-31: chair-stand cut-off (five rises) and the gait-speed cut-off for severity |
| `awgs2019` | Chen et al. 2020, JAMDA 21(3):300-307: 6-m gait speed and five-time chair-stand cut-offs |
| `perera2006` | Perera et al. 2006, J Am Geriatr Soc 54(5):743-749: small and substantial meaningful change in gait speed |
| `nodal-rule` | Citation "NODAL screening rule (CONTRACT section 4), not a published cut-off" |

## 2. `screen/norms.py`

`load()` reads the CSVs; `norm_for(metric, sex, age_y, group)` returns mean, sd, source_id, status or `None`; `cutoffs_for(metric, group, cutoff_set)` returns the active cut-offs. Pick the row whose age range contains the age; children use the age-year row.

## 3. `screen/flags.py`

`apply(session: dict, cutoff_set="ewgsop2") -> dict` takes a session with metric values filled (refs and statuses empty) and returns it with every metric's `ref` and `status`, the `flags` list, and `suggested_pathway`, exactly per CONTRACT sections 3 to 5. Pure function, no I/O except through `norms`. `symmetry_index(l, r)` as in section 4.

## 4. Tests `tests/test_flags.py`

At least: each rule just inside and just outside every threshold; z exactly 1.5 and 2.0; direction (`cadence` flags both ways, `gait_speed` only low); toe-walking only for children aged 3+; `insufficient` clears flags and sets `RECAPTURE`; pathway order (first match wins); `awgs2019` vs `ewgsop2` switching; SI formula; a norm with `placeholder` status still computes but stays `placeholder` in `ref`.

## Done when

`python -m pytest -q` passes (T01's verify script may not exist yet on this branch; that is fine). The done note has a table: source_id, opened the source (yes/no), rows written, rows left as placeholder.
