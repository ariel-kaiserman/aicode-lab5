# Lab 5 review

Commit reviewed: 8ef7eb3 on main · Reviewer: Claude Code, Claude Opus 5.5 · Unmerged branches: none

## Highlights

- Fix first: there is no `CLAUDE.md` or `AGENTS.md`, and `pyproject.toml` has no `[tool.ruff]` section, so the checks you ran are written down nowhere and Ruff only runs its default rules.
- Done well: all four checks are clean. 92 tests pass in 2.3 s with 100% coverage, and `ruff check`, `ruff format --check` and `mypy --strict` report nothing.
- Done well: the tests cover the features working together. Undo restores a capture, redo restores a promotion, and undo and redo history survive a save and load (`tests/test_undo_redo.py:43-155`, `tests/test_save_load.py:28`).
- Game state: the position is still the starter's 2-item list `[board, side to move]` (`game.py:13`). Everything the features added lives on `Session` as named fields (`session.py:52-68`).
- Tooling came late: the annotations, Ruff, mypy and redo all arrived in one commit, 7303ebb, and the save/load tests came after it in b6f0af3.

## At a glance

| Check | Result |
| --- | --- |
| Tests | 92 passed, 0 failed, in 2.33 s |
| Coverage | 100% total; lowest: all files 100% |
| `ruff check` | 0 findings |
| `ruff format --check` | 0 files would change |
| `mypy --strict` | 0 errors in 0 files |
| Game state | list or tuple of 2 items (2 in the starter) |
| Game state restructured in the lab | no |
| Instruction file | none |

## The week's practices

1. ✅ **Tests for each feature:** each feature has its own tests: save/load (`tests/test_save_load.py`), undo and redo (`tests/test_undo_redo.py`), captured pieces (`tests/test_captured.py:4`) and promotion (`tests/test_promotion.py`). There is only one captured-pieces test.
2. ✅ **Tests of features together:** `test_undo_save_load_redo` (`tests/test_undo_redo.py:129`), `test_save_load_preserves_a_promotion_in_redo` (`:143`) and `test_computer_redo_survives_save_and_load` (`:255`).
3. ✅ **Assertions that check results:** the tests contain no `print(`. The spot-checked tests compare whole views, for example `assert view == session.view()` in `tests/test_save_load.py:23`.
4. ✅ **Fast and repeatable:** 2.33 s in total. The computer is scripted with `monkeypatch` (`tests/test_undo_redo.py:201`) or given a `random.Random(seed)` (`tests/test_computer.py:47`).
5. ⚠️ **Bugs became tests:** there are no separate fix commits. The merge fixes in 217d548 and the redo work in 7303ebb do touch `tests/`.
6. ✅ **No weakened tests:** `git log -p -- tests/ | grep -E '^-\s*assert'` prints nothing.
7. ✅ **Coverage:** 100% of 840 statements. The total includes the test files themselves.
8. ❌ **Linted beyond the defaults:** `pyproject.toml` has no Ruff configuration. It reports 0 findings and the code has 0 `# noqa`.
9. ✅ **Formatted:** "13 files already formatted".
10. ✅ **Type-checked:** 0 errors, 0 `# type: ignore`, and 9 uses of `Any`. The one that matters is `Position = list[Any]` (`game.py:13`).
11. ❌ **From the start or at the end:** at the end. The tool configuration and every annotation came in one cleanup commit, 7303ebb, after all the merges.
12. ❌ **Checks in the instruction file:** there is no `CLAUDE.md` or `AGENTS.md`. `.claude/` holds only `skills/` and has no `settings.json` hook.

## The game state

The position is a list read by position, `[board, side to move]`, with 2 items now and 2 in the starter (`game.py:13`; `position[1]` at `session.py:96`). It was never restructured: `Session` was already a class in 45f06c1, and the features added named fields to it: `notation`, `history`, `snapshots`, `captured`, `redo_moves` and `opponent`. `copy_position` (`game.py:29`) copies both items. Undo snapshots store the position together with `captured` (`session.py:71`). `save()` writes the board, turn, notation, history, redo and opponent, and `load()` rebuilds snapshots and captured pieces by replaying the history. Nothing is lost on a save and load. The browser keeps no game state of its own.

## Other findings

- `Position = list[Any]` turns off `mypy --strict` for every board and turn access. A two-field dataclass or a `tuple[Board, str]` would let the type checker catch mixed-up indices.
- Save and load are safe. The save is JSON chosen by the player in the browser (`static/app.js:170-179`); the server touches no file path and uses no `pickle`. `load()` checks the save, replays it and keeps the current game if anything fails (`session.py:122-149`).
- Undo (a0070e4) and save/load (f788cf5) were committed without tests, and their tests arrived only in the last two code commits. The checks did not guard the merges while they happened.
