# T10: AI text generator for the featured participants (dry run only)

Branch `t10-ai-texts`, from `main` after T01 is merged. Read `AGENTS.md` and `docs/CONTRACT.md` section 2 (`ai_texts`, `review`) first. **Never make a paid call and never run with `--run`.** Claude runs the real generation (C07) after Kirk approves the cost; the key and project stay in Claude's environment.

## Build

1. **Prompt builder, `screen/ai_prompt.py`.** `facts(session) -> dict`: only what the session holds: group, age band, sex, metrics (id, side, value, unit, status, the norm mean and z, the cut-off and whether it was met), flags (title, evidence, the source names from `data/sources.json`, "NODAL screening rule" for `nodal-rule`), `qc` (status, confidence, notes), `suggested_pathway`, and `review` when present. No name beyond `display_name`, no video, no file paths. `build_prompt(session, kind) -> (system, user)` for `kind` in `family_letter`, `clinician_brief`; the user part is the facts as JSON.
2. **The two texts.**
   - `family_letter`: to a parent or guardian (child) or to the participant (adult). At most 160 words, plain words for a reading age near 12. What was measured, which results a clinician will look at and why in one line each, the suggested next step as a suggestion, that a clinician decides. When `qc.status` is `insufficient`: only that the capture should be repeated and why.
   - `clinician_brief`: at most 140 words. Each flag with its evidence and source, the QC confidence, the suggested pathway, and what was not measured or has no reference.
   - Both say "screening", never "diagnosis"; no reassurance or alarm beyond the facts; no number that is not in the facts.
   - The model returns JSON `{"en": "...", "ar": "..."}` (structured output). The Arabic is labelled on screen as machine translation pending native review, as elsewhere.
3. **Checks, `screen/ai_check.py`.** `check(text, session) -> list[str]` problems: the honesty patterns from `scripts/verify.py` (import them, do not copy), the word limit, and any number in the text that is not in the facts (allow ages, counts of flags, and 10 m / 5 times / 3 m protocol numbers). A text with problems is never stored.
4. **Script, `scripts/ai_texts.py`.**
   - Default `--dry-run`: for each `data/samples/*.json`, print both prompts and an estimate of input and output tokens (characters / 4 is fine) and a cost from `--price-in` and `--price-out` (US$ per million tokens, required numbers, no defaults in the code).
   - `--run`: needs `GOOGLE_CLOUD_PROJECT` and `NODAL_AI_MODEL` in the environment, else it stops before importing any SDK. Uses `google.genai.Client(enterprise=True, project=..., location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))` like `D:\cellpilot\app\argon.py`, temperature 0.2, JSON response. Runs `check` on both languages, and writes `ai_texts.<kind> = {"en", "ar", "model", "generated_at", "status": "stored-sample"}` into the session file only when the check passes; otherwise prints the problems and leaves the file alone. `--only <pid>` and `--max-calls N` (default 20) limit a run.
   - `google-genai` goes in a new `requirements-ai.txt`, not in `requirements.txt` (the app image does not need it).
5. **Tests, `tests/test_ai_texts.py`**, no network: `facts` holds no field outside the list above; the prompt for an `insufficient` session asks only for a recapture letter; `check` catches "diagnosis", "validated", a word count over the limit and an invented number; `--run` without the environment variables exits before importing `google.genai`; a fake client (monkeypatched) returns JSON and the session file gets `ai_texts` with `status: stored-sample`; a fake reply with "diagnose" is not stored.

## Done when

- `python -m pytest -q` passes and `python scripts/verify.py` ends with `VERIFY OK`.
- `python scripts/ai_texts.py --dry-run --price-in 1 --price-out 1` runs on the fixtures; paste its token totals in the done note.
- Done note `tasks/done/T10.md` confirms no paid call and no `--run`.
