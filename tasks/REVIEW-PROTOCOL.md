# Review protocol (saves Claude's limited usage)

Claude's usage is scarce; Cursor's is not. So Cursor does the first review, the git work and the drafting, and Claude reads one short file per task.

## 1. First review, by a fresh Cursor chat (not the one that built the task)

Kirk pastes: **"First review T0N. Follow tasks/REVIEW-PROTOCOL.md."** The reviewer:

1. Works in the task's worktree folder; changes nothing except the review file.
2. Runs `python -m pytest -q` and, once it exists, `python scripts/verify.py`.
3. Checks every line of the card's "Done when" and every rule in `AGENTS.md`, and compares the data with `docs/CONTRACT.md`.
4. For T02: opens each source it can and re-checks five numbers in `data/norms.csv` and `data/cutoffs.csv` against the source table.
5. Makes one contact sheet of the screenshots (`out/review/T0N-sheet.png`, at most 12 tiles, 1600 px wide) if the task has screens.
6. Writes `tasks/review/T0N.md`, at most 25 lines:
   - `VERDICT: PASS` or `VERDICT: FIX`;
   - test and verify result (last 5 lines);
   - each problem as `file:line, what is wrong, what the rule or contract says`;
   - **"Claude should look at:"** at most 3 `file:line` ranges where judgment matters (numbers, flag logic, honesty wording);
   - the contact sheet path.

## 2. Claude's gate

Kirk opens a **new** Claude Code session (or `/clear`), sets `/model sonnet` unless the task is the report, the polish pass or the film spec, and says **"Gate T0N"**. Claude reads only `tasks/review/T0N.md`, the listed ranges and the contact sheet, then writes `PASS` or a fix list into `tasks/T0N.fix.md`.

## 3. Merge, by Cursor

After Claude's PASS, Kirk pastes into Cursor: **"Merge T0N."** Cursor, in `D:\nodal-screen` on `main`:

```
git rebase --onto main 06e5b4a t0N-<slug>      # T01 to T03 only: they started from an older main
git checkout main && git merge --ff-only t0N-<slug>
python -m pytest -q
git push origin main
```

Never force-push `main`. If the rebase conflicts, stop and say so.

## 4. Next cards, drafted by Cursor

Kirk pastes: **"Draft cards T04 to T07."** Cursor writes `tasks/T0N-*.md` in the same shape as T01 to T03 (branch, Build, Done when), from the row in `tasks/README.md` and `docs/CONTRACT.md`, as drafts on branch `cards-draft`. Claude approves or edits them at its next gate.

The public repository rule holds for everything: nothing private, nothing from NODAL's proprietary gait engine.
