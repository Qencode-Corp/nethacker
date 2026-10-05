# P37 stack (2026-10-05): the three settled P37 branches merged on jev-instruments

Base: `jev-instruments` at 95006fe ("Jev instrument (logging only): the END block ..."). Worktree
`~/jev-nethack-frontier/wt/p37-stack`, branch `p37-stack`. Nothing pushed. `p37-passtune` and `p37-fountain` are NOT in
this stack (still being edited).

## Branches merged (no-ff, in this order)

| branch | commit | what | merge |
|---|---|---|---|
| p37-msg | efc3904 | P37 track C: sizing instrument (logging only): LEVEL / MSG / KIT lines (`pf_base/agent.py`, `adapter_pf_base.py`) | 3235300 |
| p37-instruments | ccecc20 | P37 track B: KEEP_INSTRUMENT switch (default off) (`jf_config.py`, `opp_items.py`, `global_logic.py`) | 7f9d807 |
| p37-flags | d373ee9 | P37 track A: 25 default-off switches ported from nhbot v12pub (11 files) + `P37_FLAGS.md` | b72fabe |

All three merges auto-resolved (git's ort strategy): the two `jf_config.py` additions land in different blocks
(KEEP_INSTRUMENT next to HORN_KEEP at line ~1165; the nhbot block after ELBERETH_FUTILE at ~1420), and the two
`agent.py` change sets (sizing instrument vs. flag hunks) do not overlap. No hand edits were needed. Combined diff vs
the base: 15 files, +853 / -29 = exactly the sum of the three branches.

## Switches available (all JF_CFG-overridable) and their defaults

In `engines/dag25/pf_base/jf_config.py` unless noted. Every switch is OFF by default except UNSEEN_PET_GUARD (already
the head's behaviour; its experiment is turning it off). With no JF_CFG the engine is the head, byte for byte
(P37_FLAGS.md smoke: identical records and engine logs).

| switch | default | tunables (default) | track |
|---|---|---|---|
| MINES_TOOL_TRIP | False | -- | A (dive_logic.py constant) |
| MEDUSA_HOP | False | MEDUSA_HOP_MAX 6 (dive_logic.py) | A (dive_logic.py constant) |
| DEEP_PRAY_FIRST | False | DEEP_PRAY_FIRST_DEPTH 10 | A |
| LMINION_ELBERETH | False | -- | A |
| MEDUSA_TITAN_MSG | False | -- | A |
| MEDUSA_STRANDED_REROLL | False | MEDUSA_STRANDED_REROLLS 6 | A |
| MEDUSA_NOT_CASTLE | False | -- | A |
| MEDUSA_ZAP_FIRST | False | -- | A |
| MINO_TAME | False | -- | A |
| MINO_DIG_GUARD | False | -- | A |
| MINO_CASTLE_ZAP | False | -- | A |
| DIG_TOOL_MELEE | False | DIG_TOOL_MELEE_MARGIN 1.3 | A |
| HOSTILE_RECHECK | False | -- | A |
| PET_HUNGER_FIX | False | PET_HUNGER_TURNS 250 | A |
| HEAVY_LIFT_GUARD | False | -- | A |
| PANIC_TILE_FIX | False | -- | A |
| DITCH_RETRY | False | dive_logic.DITCH_RETRY_WAIT 400 | A |
| SPORE_TRAP_FIX | False | -- | A |
| RAY_BOUNCE_FIX | False | -- | A |
| SELF_ZAP_FIX | False | SELF_ZAP_PENALTY 300, RAY_CRIT_RUN 0 | A |
| PRAYER_RECORD_FIX | False | -- | A |
| RECORD_MODEL_FIX | False | -- | A |
| ELBERETH_REWRITE_FIX | False | -- | A |
| PYTHON_HOLD | False | -- | A |
| UNSEEN_PET_GUARD | **True** | UNSEEN_PET_TURNS 20 | A (experiment = false) |
| KEEP_INSTRUMENT | False | -- | B |

Track C (the sizing instrument) has no switch: it is logging only (LEVEL / MSG / KIT lines), read by no strategy.

## JF_CFG sets

(a) the kept set so far:

```
{"MEDUSA_HOP": true}
```

(b) the kept set + the leaning switches + nhbot's shipped Valkyrie set (P37_FLAGS.md: the 24 default-off switches, which
is nhbot's "safe" profile plus MEDUSA_HOP; UNSEEN_PET_GUARD left at its default True):

```
{"MEDUSA_HOP": true, "KEEP_INSTRUMENT": true,
 "MINES_TOOL_TRIP": true, "DEEP_PRAY_FIRST": true, "LMINION_ELBERETH": true, "MEDUSA_TITAN_MSG": true,
 "MEDUSA_STRANDED_REROLL": true, "MEDUSA_NOT_CASTLE": true, "MEDUSA_ZAP_FIRST": true, "MINO_CASTLE_ZAP": true,
 "MINO_DIG_GUARD": true, "MINO_TAME": true, "DIG_TOOL_MELEE": true, "HOSTILE_RECHECK": true, "PET_HUNGER_FIX": true,
 "HEAVY_LIFT_GUARD": true, "PANIC_TILE_FIX": true, "DITCH_RETRY": true, "SPORE_TRAP_FIX": true, "RAY_BOUNCE_FIX": true,
 "SELF_ZAP_FIX": true, "PRAYER_RECORD_FIX": true, "RECORD_MODEL_FIX": true, "ELBERETH_REWRITE_FIX": true,
 "PYTHON_HOLD": true}
```

## Verification (2026-10-05, `~/jev-nethack-frontier/.venv/bin/python`, cwd = this worktree)

- `import pf_base.jf_config, pf_base.dive_logic, pf_base.global_logic, pf_base.agent, pf_base.opp_items`: clean (only
  the four pre-existing SyntaxWarnings in character.py / inventory.py, present on the base too).
- Every switch read back at its default listed above; `JF_CFG='{"MEDUSA_HOP": true, "KEEP_INSTRUMENT": true,
  "MINES_TOOL_TRIP": true}'` flips all three (dive_logic constants and jf_config alike).
- `python -m py_compile` on all 14 changed .py files: OK.
- No games run (the Mac was loaded); the bench of set (a)/(b) is the next step, on the pool.
