# P37 read: why the Castle-passage games die in the Valley (2026-10-04)

Data: the head's 4,000 cloud games (cloud-el1fe-bd8cb7c), logs paired to ids by tools/frontier_logs.py (3,980 resolved).
Per-game table: `valley_landing_read.csv` (117 rows: 39 passage Valleys + the 78 teleport-route ids). These logs predate the
END instrument, so "last 30 steps" is the `last30` column (the last 30 logged lines) plus `top_tasks`.

## The two routes

| | passage (39) | teleport route (78) |
|---|---|---|
| reached Gehennom | 39 | 44 (34 die before the castle) |
| landing HP fraction, median | 0.69 (14 under 0.6, 5 under 0.33) | 1.0 |
| landing XL, median | 8 (33 at XL 7-9) | 5-7 |
| digging tool at landing | 38 (pick-axe 33, mattock 6; wand 9) | 4 |
| turns survived in Gehennom, median | 23 | 39 (banked deep) |
| died within 25 turns of landing | 21 | 20 |
| left the Valley | 3 (to Dlvl 33, 33, 36) | 40 (second controlled teleport) |
| **reached Dlvl 40** | **0 / 39 = 0%** | **39 / 78 = 50%** (89% of the 44 in Gehennom) |

Killers of the 39: xorn 15 (11 of the 21 landing deaths), vampire lord/bat form 4, ettin zombie 2.

## Failure classes (passage, 39) and the first fix for each

| class | n | the log | first fix |
|---|---|---|---|
| killed at the landing (<= 25 turns) | 21 | 14 read unknown scrolls on the landing square (VALLEY_LOTTERY) as the crowd closed; 17 end in `valley: retreat to the up stairs`; 14 show `AgentPanic: Monster on a next tile` from the retreat's `go_to` | (a) `valley_walk.py:524 _lottery_ok_now` (`VALLEY_LOTTERY_DESPERATE = 1.0` reads with hostiles adjacent): no awake hostile within 2, HP >= 0.6, never in the first 20 turns; (b) `dive_logic.py:6578 valley_retreat` -> `go_to(*up, max_steps=1)` panics on a monster in the way: strike it (as `valley_sneak` does, 6395-6401) or `yield False` for fight2; (c) `castle_logic.py:1702 _door_step` steps onto the trap door at any HP: require HP >= REST_BELOW (0.66) at DOOR -- the castle has Elbereth and prayer, the Valley neither |
| died walking the Valley (> 25 turns) | 8 | 3748: `valley: explore` 1,485 task lines over 892 turns (hallucinating; `exploration().until(_valley_route_open)` never ends); 1304 / 3967: `valley: rest` loops of 1,100 / 450 turns, then a xorn; 3156, 510: ettin zombies at the doors | the walk is 0/61 in every harness arm and 0/39 here: cap `valley_step`'s explore/rest (`dive_logic.py:6300`) at ~150 turns; the exit is the xorn form or a known cursed teleport scroll |
| lottery teleported UP | 4 | 430 -> Dlvl 3, 1109 -> 4 (re-dug to 25), 2028 -> 18 (re-dug to 27, `trap door did not trigger` x15), 597 -> 4; all dead | the roll is 72% up (teleport.c); 1 of 5 went deeper (3624). `valley_walk.py:447 lottery_active`: only after the xorn route failed, known cursed teleport scrolls only |
| retreated up to the castle | 3 | 610 (landed 1/16 HP, no tool), 924 (23/89), 2587 | fix (c) |
| exited the Valley, died below | 3 | 60, 3906: xorn form (VALLEY_XORN) phased to the '>' and dug to Dlvl 33; 3624: lucky roll, pick-axe 26 -> 36 in 57 turns, owlbear at 41/99 right after a `GEHENNOM escape` zap | `dive_logic.py:582 GEHENNOM_DIG_REST_BELOW = 0.3`: 3624 dug ten levels at 35-41/99; 0.5 below the Valley, rest only with nothing in view |

Reading: the Valley is lost at the landing. The passage drops a median XL-8, 69%-HP dwarf on a square every resident knows
(set_apparxy); a xorn comes through the wall in 11 of 21 landing deaths; the engine reads scrolls, then panics walking to the
'<'. The exits were two xorn forms and one roll; below the Valley the dig-dive works (3624: ten levels in 57 turns). Skipping
the Valley is worth 50% of 78 games at Dlvl 44-50.

## The harness (`valley_harness.py`, runnable, probed; details in its docstring)

Wizard-mode NLE with Ctrl-V / Ctrl-W appended to `nethack.ACTIONS`; the harness does the setup itself (`#levelchange`,
wishes for a kit sized from the table, armour worn by letter, Ctrl-V `valley`, optional `--deep N` second teleport = the dig
control arm), then hands the observations to `engines/dag25/bot.py make_agent()` (reset/act, the arena's contract), answers
`Die?`, and runs to death, Dlvl 45 or `--max-turns`, with the engine's own `bot_<seed>.log` via `JF_LOG_DIR`.

Status: probe seed 7 ran end to end -- Valley at Dlvl 29, turn 4, XL 8, HP 92, AC -6; the agent took over at turn 5, killed a
ghost, a ghoul and a vrock, went XL 8 -> 10 and died at turn 259 to a vampire lord and bats (the END block names them; the
harness's `killer` field is empty since the tombstone is not on the tty). Two wizard-mode `#enhance` screen differences are
wrapped harness-side (no engine edit; `character.py:473/523` assert on them), so the harness hero never advances a skill.
Not reproduced: the landing HP deficit (wizard mode lands at full HP), the castle's Elbereth/prayer history, the mixed
unidentified kit; seeds re-roll the dungeon (unpaired arms).

## Numbers asked for

- Passage games reaching Dlvl 40: **0 / 39 (0%)**; Dlvl 30+: 14/39, 3 by leaving the Valley.
- Teleport-route games reaching Dlvl 40: **39 / 78 (50%)**; 89% of the 44 that reached Gehennom.
