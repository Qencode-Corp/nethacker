# P37 Valley landing fixes: the harness read (2026-10-04)

Branch `p37-valley`, engine `engines/dag25/pf_base`. Five `jf_config.py` switches, all default OFF, nothing changed with
them off (seed 7 replays exactly before/after the patch and under every switch: 213 steps, 83 turns, Dlvl 29).

| switch | where | rule |
|---|---|---|
| `VALLEY_NO_LANDING_LOTTERY` (+`_TURNS` 25) | `valley_walk.py` `lottery_active` / `_lottery_plan` / `_lottery_ok_now` | no unknown-scroll reads or quaffs at all; known tickets only (a known cursed teleport scroll, or a known one while confused); never within 25 turns of the landing or with an awake hostile adjacent; only once the xorn route is spent (no form, no known polymorph wand with control) |
| `VALLEY_RETREAT_STRIKE` | `dive_logic.py` `valley_retreat` (+`_valley_retreat_blocker`, `_valley_retreat_step`) | the step to the '<' strikes the monster on the next square instead of `go_to` panicking on it; a peaceful or VALLEY_NO_MELEE blocker yields to fight2; a monster stepping in mid-move is struck (the `_raven_step_toward` pattern) |
| `VALLEY_DOOR_HP` (+`_FRAC` 0.66, `_MAX_REST` 600) | `castle_logic.py` `_door_step` (`_door_hp_hold`) and `_rest_stop` | below 0.66 HP at the back door / in its doorway: step back out, heal on Elbereth at the door or at SAFE_EAST (CASTLE_EDGE_REST), at most 600 actions |
| `VALLEY_WALK_CAP` (+`_EXPLORE` 300, `_REST` 200) | `dive_logic.py` `valley_step` | `valley: explore` ends after 300 turns; hallucinating it holds (search) instead of exploring; a rest ends after 200 turns and is not retaken for 200. No dig exit exists: the Valley is hardfloor (`valley.py`, `dive_logic.py:3258`), only the xorn form (VALLEY_XORN preempts by itself) and the stairs walk |
| `GEHENNOM_DIG_REST` (+`_FRAC` 0.5) | `dive_logic.py` dig-down rest rule (`GEHENNOM_DIG_REST_BELOW` site) | below the Valley rest under 0.5 of max HP instead of 0.3, and only with nothing in view |

Stack: `JF_CFG='{"VALLEY_NO_LANDING_LOTTERY": true, "VALLEY_RETREAT_STRIKE": true, "VALLEY_DOOR_HP": true, "VALLEY_WALK_CAP": true, "GEHENNOM_DIG_REST": true}'`

## Commands

```
cd ~/jev-nethack-frontier/wt/p37-valley
P=~/jev-nethack-frontier/.venv/bin/python; OUT=$PWD/out
W='--wish "2 uncursed scrolls of enchant armor" --wish "uncursed scroll of light" --wish "uncursed scroll of remove curse" --wish "uncursed scroll of gold detection"'
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag ctrl
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag lot    --cfg '{"VALLEY_NO_LANDING_LOTTERY": true}'
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag strike --cfg '{"VALLEY_RETREAT_STRIKE": true}'
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag door   --cfg '{"VALLEY_DOOR_HP": true}'
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag cap    --cfg '{"VALLEY_WALK_CAP": true}'
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag dig    --cfg '{"GEHENNOM_DIG_REST": true}'
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag all    --cfg '<the stack above>'
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag deep-ctrl --deep 35
$P valley_harness.py --seeds 200 --xl 8 --kit median $W --out $OUT --tag deep-dig  --deep 35 --cfg '{"GEHENNOM_DIG_REST": true}'
$P valley_harness_summary.py out ctrl lot strike door cap dig all deep-ctrl deep-dig
```
(`--out` must be absolute: `load_bot` chdirs into the engine. Seeds 1000-1199 in every arm; wizard mode re-rolls the dungeon,
so arms are unpaired beyond the first divergence -- but a game in which a switch never fires is identical to control.)

## Harness deviations found while running (read before trusting a number)

- The median kit carries no scrolls, so the lottery (14 of 39 real landing deaths read scrolls) could not fire: four
  unknown scroll types are wished in (the real castle kits carry 6-8 unknown types). NOT teleportation: wizard mode
  bypasses `noteleport` and a read scroll of teleportation teleports the hero across the Valley to a chosen square and
  identifies the stack (the first run did that in every control game; archived in `out/old-telekit/`). So the harness reads
  cost turns and harmless effects, never the 72%-up level roll of the real cursed/confused reads.
- `VALLEY_DOOR_HP` cannot fire: the harness lands in the Valley by Ctrl-V at full HP, never through the castle's trap door
  (the real landing median is 69% HP). No wizard-mode way to set HP to 0.69 of max without a potion was found; skipped.
  It is checked only for syntax and for leaving the off-path unchanged (door arm = control).
- `--deep 35` lands at Dlvl 35 (Gehennom 7) at turn 4: a 5-level dig to Dlvl 40. The teleport-route games of the read
  landed at Dlvl 44-50 directly (their "89% to Dlvl 40" is the landing itself), so this arm is the dig-dive control below
  the Valley, not a replica of that route.
- `jf_log` keeps one file handle per process: each arm's games append to one `logs-<tag>/bot_1000.log`; the summariser
  splits it at the adapter's TRAJ line. Killers come from the END block (last melee message), not the tombstone.
- The hero never advances skills (wizard #enhance screens), is unhungry, has no castle Elbereth/prayer history.

## Results

200 games per arm, seeds 1000-1199, XL 8, median kit + four unknown non-teleport scrolls (`plain` = the median kit alone),
`--stop 45`, `--max-turns 3000`. Wilson 95% intervals. "alive 25" = survived more than 25 turns after the landing.

| arm | n | Dlvl 40 | left the Valley | alive 25 | median turns | top killers |
|---|---|---|---|---|---|---|
| ctrl | 200 (0 bad) | 0/200 = 0% [0, 2] | 0/200 = 0% [0, 2] | 154/200 = 77% [71, 82] | 57.5 | vampire bat 61, xorn 21, vampire lord 15, ghost 14, minotaur 11 |
| plain | 200 (0 bad) | 0/200 = 0% [0, 2] | 0/200 = 0% [0, 2] | 143/200 = 72% [65, 77] | 49.0 | vampire bat 60, ghost 14, xorn 13, minotaur 12, vampire 12 |
| lot | 200 (0 bad) | 0/200 = 0% [0, 2] | 0/200 = 0% [0, 2] | 133/200 = 66% [60, 73] | 40.5 | vampire bat 66, xorn 16, vampire lord 15, ettin mummy 9, unknown 9 |
| strike | 200 (0 bad) | 0/200 = 0% [0, 2] | 0/200 = 0% [0, 2] | 150/200 = 75% [69, 80] | 54.5 | vampire bat 57, vampire 16, ghost 16, vampire lord 14, xorn 14 |
| door | 200 (0 bad) | 0/200 = 0% [0, 2] | 0/200 = 0% [0, 2] | 154/200 = 77% [71, 82] | 57.5 | vampire bat 61, xorn 21, vampire lord 15, ghost 15, minotaur 11 |
| cap | 200 (0 bad) | 0/200 = 0% [0, 2] | 0/200 = 0% [0, 2] | 154/200 = 77% [71, 82] | 57.5 | vampire bat 61, xorn 21, vampire lord 15, ghost 14, minotaur 11 |
| dig | 200 (0 bad) | 0/200 = 0% [0, 2] | 0/200 = 0% [0, 2] | 154/200 = 77% [71, 82] | 57.5 | vampire bat 61, xorn 21, vampire lord 15, ghost 14, minotaur 11 |
| all | 200 (0 bad) | 0/200 = 0% [0, 2] | 0/200 = 0% [0, 2] | 127/200 = 64% [57, 70] | 38.0 | vampire bat 65, vampire lord 15, xorn 13, ettin mummy 10, vampire 10 |
| deep-ctrl | 200 (0 bad) | 51/200 = 26% [20, 32] | 159/200 = 80% [73, 85] | 128/200 = 64% [57, 70] | 37.0 | minotaur 28, unknown 16, xorn 13, baluchitherium 5, fire vortex 5 |
| deep-dig | 200 (0 bad) | 52/200 = 26% [20, 32] | 158/200 = 79% [73, 84] | 128/200 = 64% [57, 70] | 37.5 | minotaur 29, unknown 18, xorn 14, umber hulk 6, master lich 5 |

switch firings per arm (engine logs):
- ctrl: DRIVER restarts 0, climbs to the castle 77, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 200, games with progress toward the > 200, hallu holds 0, lottery reads 801, next-tile panics 651, rest before digging 0, rest caps 0, retreat strikes 0, returns by the trap door 28, secret doors broken 0
- plain: DRIVER restarts 0, climbs to the castle 71, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 1, games with progress toward the > 200, hallu holds 0, lottery reads 1, next-tile panics 645, rest before digging 0, rest caps 0, retreat strikes 0, returns by the trap door 23, secret doors broken 0
- lot: DRIVER restarts 0, climbs to the castle 68, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 0, games with progress toward the > 200, hallu holds 0, lottery reads 0, next-tile panics 507, rest before digging 0, rest caps 0, retreat strikes 0, returns by the trap door 21, secret doors broken 0
- strike: DRIVER restarts 0, climbs to the castle 70, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 200, games with progress toward the > 200, hallu holds 0, lottery reads 801, next-tile panics 105, rest before digging 0, rest caps 0, retreat strikes 229, returns by the trap door 19, secret doors broken 0
- door: DRIVER restarts 0, climbs to the castle 79, door HP holds 1, explore caps 0, games down the Valley stairs 0, games with a lottery read 200, games with progress toward the > 200, hallu holds 0, lottery reads 801, next-tile panics 678, rest before digging 0, rest caps 0, retreat strikes 0, returns by the trap door 31, secret doors broken 0
- cap: DRIVER restarts 0, climbs to the castle 75, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 200, games with progress toward the > 200, hallu holds 0, lottery reads 801, next-tile panics 654, rest before digging 0, rest caps 4, retreat strikes 0, returns by the trap door 29, secret doors broken 0
- dig: DRIVER restarts 0, climbs to the castle 77, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 200, games with progress toward the > 200, hallu holds 0, lottery reads 801, next-tile panics 651, rest before digging 0, rest caps 0, retreat strikes 0, returns by the trap door 28, secret doors broken 0
- all: DRIVER restarts 0, climbs to the castle 57, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 0, games with progress toward the > 200, hallu holds 0, lottery reads 0, next-tile panics 78, rest before digging 0, rest caps 4, retreat strikes 169, returns by the trap door 18, secret doors broken 0
- deep-ctrl: DRIVER restarts 0, climbs to the castle 0, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 0, games with progress toward the > 0, hallu holds 0, lottery reads 0, next-tile panics 9, rest before digging 31, rest caps 0, retreat strikes 0, returns by the trap door 569, secret doors broken 0
- deep-dig: DRIVER restarts 0, climbs to the castle 0, door HP holds 0, explore caps 0, games down the Valley stairs 0, games with a lottery read 0, games with progress toward the > 0, hallu holds 0, lottery reads 0, next-tile panics 9, rest before digging 76, rest caps 0, retreat strikes 0, returns by the trap door 566, secret doors broken 0

Landing deaths (<= 25 turns) / games that ended on the castle level after a climb: ctrl 46 / 47, plain 57 / -, lot 67 / 46,
strike 50 / 50, door 46 / 46, cap 46 / 46, dig 46 / 47, all 73 / 39; deep-ctrl 71 / -, deep-dig 71 / -.
75th-percentile turns: ctrl 266, lot 101, strike 164, all 88; the longest games 2,100-2,500 turns (castle round trips).

## Reading

- **Nothing moves the number that matters.** Every Valley arm is 0/200 past the Valley's '>' and 0/200 at Dlvl 40
  (upper bound 2%); no game broke the first secret door (the walk's first obstacle, `secret doors broken 0` everywhere).
  The read's "walk is 0/39" is 0/1,400 here. The whole arm population dies in the landing zone or on castle round trips:
  vampire bats 30% of killers, then xorns, vampire lords, ghosts, minotaurs (which follow up the '<').
- **VALLEY_NO_LANDING_LOTTERY** fires in every game (801 reads removed) and reads *worse* on survival: alive-25 66% [60, 73]
  vs 77% [71, 82]. The plain kit (no scrolls at all) is 72% [65, 77]: most of the gap is what the harness's harmless wished
  scrolls give the control when read (two enchant armours = AC -4 -> -6, a lit field), not a cost of the switch; the rest is
  inside the intervals. The real kits' reads are not harmless (fire, amnesia, create monster, the 72%-up level roll of a
  cursed/confused teleport: 4 of 39 real games), which the harness cannot reproduce (wizard mode bypasses `noteleport`),
  so this switch's real value is only readable on the bench.
- **VALLEY_RETREAT_STRIKE** does what it says -- 'Monster on a next tile' panics 651 -> 105, 229 strikes -- and changes no
  outcome: alive-25 75% [69, 80] vs 77%, median turns 54.5 vs 57.5. The panic was a symptom; the retreat itself (77 climbs,
  28 returns in control; 47 of 200 games end on the castle level) does not save the games.
- **VALLEY_WALK_CAP**: 4 rest caps, 0 explore caps, 0 hallucination holds in 200 games; identical to control otherwise. The
  explore/rest loops of the read (3748, 1304, 3967) are rare events the harness population does not reach (it dies first).
- **VALLEY_DOOR_HP**: fired once (after a climb, at the castle's back door below 0.66); the harness lands at full HP so the
  switch's target (the 14 of 39 real landings under 60% HP) is not in the sample. Door arm = control.
- **GEHENNOM_DIG_REST** (deep arms, Dlvl 35 landing): rests 31 -> 76, Dlvl 40 reached 26% [20, 32] in both arms, median
  37 turns, 71 of 200 dead within 25 turns, minotaurs the first killer (28/29). The dig-dive below the Valley at this kit is
  a 26% proposition from Dlvl 35, and the rest threshold is not what decides it.
- **The stack** (all five on): alive-25 64% [57, 70], median 38 turns, 0/200 out -- the lottery arm's kit effect plus noise;
  no interaction worth the name.

## Remaining failure classes (harness population, median kit, XL 8, full HP)

1. The landing crowd: vampire bats (fast, 44% vampires in bat form), ghosts and mummies within 3 turns of the fall; 46-73
   of 200 die in the first 25 turns, nothing in the stack touches it. The landing itself is the lever (a scroll of scare
   monster held on the '<' -- VALLEY_FORT/GEHENNOM_SCARE are built but off; or not landing at all: the teleport route).
2. Castle round trips: ~75 climbs per 200 games, ~25% of games end on the castle level (minotaurs, xorns through the walls).
3. The walk: no game reaches the first secret door. VALLEY_WALK is off; the walk the stack caps is never the binding loop here.
4. Below the Valley: minotaurs within the first 25 turns on Gehennom mazes (28/200 deep games), 26% to Dlvl 40 from Dlvl 35.

Verdict for the bench: the harness cannot read switches 1 and 3 (kit and HP deviations) and finds switches 2, 4, 5 to be
outcome-neutral here (2 verifiably removes its panic). None of the five is a Valley exit; the exit remains skipping the
Valley (the teleport route, 50% of 78 at Dlvl 44-50) or a wall-walking form.

