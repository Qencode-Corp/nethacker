# P37 fountain-quaffing wish policy: harness read (2026-10-05)

Branch `p37-fountain` (worktree `~/jev-nethack-frontier/wt/p37-fountain`, off `jev-instruments`), engine `engines/dag25/pf_base`.
Switch `FOUNTAIN_QUAFF` (default OFF) in `jf_config.py`; policy in `dive_logic.py` (`_dip_wanted`, `_fountain_quaff_target`,
`fountain_quaff`, `fountain_quaff_strategy`); hooks: the dive step beside `prep_fountain_dip`, and a lowest-priority global preempt
in `global_logic.global_strategy` for the tour (`.condition(lambda: jf_config.FOUNTAIN_QUAFF and not self.dive.diving)`).
Logging: `FOUNTAIN quaff n= dlvl=` (before the drink), `FOUNTAIN result n= msg=` and `FOUNTAIN event=<...>` (after it, in a
`finally`: a demon/nymph/snake in view fires fight2 on the drink's own step and unwinds the body), `FOUNTAIN stop reason=`.

**Verdict: REJECTED.** Net about -11 points on the 4,000 bench by the agreed arithmetic (bar: >= +0.5). Not a bench candidate.

## 1. The game rule (NetHack 3.6.6 src/fountain.c, read exactly)

`drinkfountain()`: `fate = rnd(30)`. A magic fountain (`blessedftn`) with Luck >= 0 and fate >= 10 restores/gains an attribute and
returns before `dryup` (then `blessedftn = 0`, so it is an ordinary fountain afterwards). Otherwise:

| fate | effect |
|---|---|
| 1-9 | "The cool draught refreshes you." (+rnd(10) nutrition) |
| 10-18 | "This tepid water is tasteless." |
| 19 | enlightenment |
| 20 | foul water: vomit, -rn1(20,11) nutrition |
| 21 | contaminated: `losestr(rn1(4,3))` = -3..6 Str, d10 HP (no poison resistance on a Valkyrie) |
| 22 | `dowatersnakes`: rn1(5,2) = 2-6 water moccasins |
| 23 | `dowaterdemon`: a water demon; **wish if `rnd(100) > 80 + level_difficulty()`**, i.e. (20 - Dlvl)%; else hostile (& L8 AC-4 sp12, 3x1d3, summons demons in melee 1 in 13) |
| 24 | "This water's no good!": each carried item cursed 1 in 5, -11..30 nutrition |
| 25 | see invisible |
| 26 | monster detection |
| 27 | a gem (falls through to the nymph once the fountain is looted) |
| 28 | `dowaternymph`: a water nymph (steals, teleports) |
| 29 | scare: every monster flees |
| 30 | `dogushforth`: pools in the room |

Then `dryup(u.ux, u.uy, TRUE)` after **every** drink (fate < 10 included): the fountain dries 1 time in 3 (`!rn2(3)`; a warned
town fountain dries at once). In wizard mode `dryup` asks "Dry up fountain?" -- the engine's generic yn handler answers y, so
the harness fountain dries like a real one (seen as `Dry up fountain? [yn] (n) The fountain dries up!` in the logs).

Per-fountain arithmetic. The policy stops at a demon, snakes or a nymph (3/30 of drinks); the fountain dries 1/3 per drink:
P(another drink) = (27/30)(2/3) = 0.600, so **E[drinks per fountain] = 1/(1-0.6) = 2.5**. Per drink at Dlvl d:
wish = (1/30)(20-d)/100, hostile demon = (1/30)(80+d)/100, curse = nymph = contaminated = snakes = 1/30.

| Dlvl | wishes / fountain | hostile demons / fountain | curses | nymphs | contaminated | snakes |
|---|---|---|---|---|---|---|
| 3 | 2.5 x 0.17/30 = **0.0142** | 2.5 x 0.83/30 = 0.0692 | 0.083 | 0.083 | 0.083 | 0.083 |
| 5 | 0.0125 | 0.0708 | 0.083 | 0.083 | 0.083 | 0.083 |
| 8 | 0.0100 | 0.0733 | 0.083 | 0.083 | 0.083 | 0.083 |
| 12 | 0.0067 | 0.0767 | 0.083 | 0.083 | 0.083 | 0.083 |

Per game at the sizing read's 3.77 fountains (a ceiling: all of them drunk at Dlvl 3): 0.053 wishes, 0.26 hostile demons,
0.31 curses, 0.31 nymphs, 0.31 Str losses, 0.31 snake packs. Gain ceiling = 0.053 x 0.35 x 100 = **+1.87 points**; the
break-even extra death rate at 0.40 progression per death is (1.87 - 0.5) / 40 = **3.4 percentage points** per game.

## 2. Harness

`fountain_harness.py` (the wizard-mode pattern from `wt/p37-valley/valley_harness.py`: NLE `wizard=True`, Ctrl-V levelport, Ctrl-W
wishes, the #enhance parse wrapper, `make_agent()`/`reset`/`act`, 'Die?' answered y). Setup per seed: `#levelchange` to XL 5, wishes
`blessed +0 dwarvish iron helm`, `blessed +1 ring mail`, `3 blessed food rations` (worn; the Valkyrie's own +1 long sword, dagger,
+3 small shield), Ctrl-V to Dlvl 3, Ctrl-F (magic mapping) and a scan for `{`; seeds without a Dlvl-3 fountain are skipped
(49%; wizard mode cannot place one; Dlvl 3 is where GRIND_LEVELS {5: 3} keeps an XL-5 hero, a deeper landing is walked away
from -- probe s1000 landed on the Oracle's four fountains and left them). Run until death, Dlvl 12 or 3,000 turns. Two
measurements per game: the engine's FOUNTAIN lines and the game's own messages counted by the harness each step
(`game_events`: You unleash / grants you a wish / You attract / pours forth / water's no good / contaminated / dries up).
Killers come from the engine's END block (`fountain_results.py`: the death tty is past the message).

Commands (Mac, ~9 s a game, 5 workers an arm, the two arms concurrently; ~20 min):

```
cd ~/jev-nethack-frontier/wt/p37-fountain
~/jev-nethack-frontier/.venv/bin/python fountain_harness.py --engine $PWD/engines/dag25 --seeds 600 --seed-base 1000 \
    --dlvl-max 3 --workers 5 --out $PWD/out --tag ctrl-v2
~/jev-nethack-frontier/.venv/bin/python fountain_harness.py --engine $PWD/engines/dag25 --seeds 600 --seed-base 1000 \
    --dlvl-max 3 --workers 5 --out $PWD/out --tag quaff-v2 --cfg '{"FOUNTAIN_QUAFF": true, "TC_ROUTE": true}'
~/jev-nethack-frontier/.venv/bin/python fountain_results.py --out out --arms ctrl-v2 quaff-v2
```

Switch-off check: seed 1003 with `FOUNTAIN_QUAFF` off on this engine vs the pristine `nethacker-head/engines/dag25`: 4,183 steps
both, bot logs identical but for pid and traceback paths. (A first pass, tags `ctrl`/`quaff`, 256 games an arm, missed the
demon/nymph/snake FOUNTAIN lines -- the body unwound before logging -- and gave the same deaths: 11 vs 42 of 256.)

## 3. Results (seeds 1000-1599, 306 games an arm with a Dlvl-3 fountain; Wilson 95%)

| metric | control (off) | FOUNTAIN_QUAFF on |
|---|---|---|
| games | 306 | 306 |
| drinks / fountains drunk / games drinking | 0 / 0 / 0 | 1,168 / 444 / 292 |
| drinks per fountain (source 2.5) | - | 2.63 |
| fountains dried (game msgs) | 13 (dips) | 368 |
| water demons (game msgs) / engine | 1 (a dip at XL 7) | 35 / 34 |
| wishes (all 'blessed ring of teleport control') | 0 | **6** = 2.0% of games [0.9, 4.2]; 17% of demons (source 17%) |
| wish -> TC ring known (route step 1) | - | 6/6 = 100% [61, 100] |
| hostile demons / demon deaths | 1 / 1 (Yeenoghu summoned) | 29 / **19** (66% of hostile demons kill) |
| nymphs / theft messages | 1 / 51 | 39 / 129 |
| water moccasin events / moccasin deaths | 2 / 0 | 40 / 12 |
| curse events ('This water's no good!') | 0 | 31 |
| contaminated (-3..6 Str) | 0 | 36 (final Str 17.33 vs 17.75) |
| Excalibur made (tour dips at XL 7) | 6 | 2 |
| **deaths** | **13 = 4.2% [2.5, 7.1]** | **52 = 17.0% [13.2, 21.6]** |
| reached Dlvl 12 | 9 = 2.9% [1.6, 5.5] | 3 = 1.0% [0.3, 2.8] |
| turns mean / max depth mean / final XL | 2,941 / 3.81 / 6.02 | 2,687 / 3.61 / 5.86 |

Killers, quaff arm: water demon 13 (near the death: incubus and Yeenoghu-type summons included), water moccasin 12,
floating eye 5, the rest ordinary. Control: hill orcs, wererat, floating eye, gnome king, one demon from an Excalibur dip.

The harness rates match the source: 1,168 drinks gave 35 demons (1 in 33; source 1 in 30), 39 nymphs, 40 snake events, 31
curses, 36 contaminations (each 1 in 30 = 39 expected), 6 wishes of 35 demons (17%, source 17% at Dlvl 3).

## 4. Decision arithmetic

- Gain: wishes per fountain drunk 6/444 = 0.0135 (source 0.0142). At 3.77 fountains a game: 0.051 wishes x 0.35 x 100 =
  **+1.78 points** (source rate: +1.87). Every wish did buy the TC ring (6/6).
- Cost: death rate +12.75 pp per 1.45 fountains drunk (the harness drinks only Dlvl 3's); at 0.40 progression a death
  and scaled to 3.77 fountains: 12.75 x 0.40 x 3.77/1.45 = **-13.3 points**. Unscaled (1.45 fountains) it is -5.1 points.
- Net **-11.5 points** (unscaled -3.3); bar >= +0.5. Even the Wilson lower bound of the death difference (13.2 - 7.1 = +6.1 pp)
  costs -2.4 points unscaled, more than the whole gain ceiling.
- Why: at XL 5 the hostile demon kills 2 in 3 times the vigil notwithstanding (AC -4, speed 12, summons; `water_demon_vigil`
  engraves but the demon's summons and the hero's own fight2 break it), and the moccasins (2-6 of them, poisonous) kill 1
  in 3 times. The per-fountain death chance is ~(0.069 x 0.66 + 0.083 x 0.30) = 7% vs 1.4% of a wish worth 0.35.
  Break-even would need the hostile-demon-plus-snake death rate under ~1.9% per fountain, i.e. a hero that survives them
  ~85% of the time -- a castle-kit Valkyrie, not the XL 5-8 one that passes these fountains.

Not tried, left open: quaffing only at XL >= 10 or with Excalibur in hand (fewer fountains would be reached; the Dlvl
window stays 1-12), and a flee-upstairs rule on 'You unleash'. Neither changes the gain side (+1.9 ceiling), so a variant
would have to bring the extra death rate under 3.4 pp per game to pass.

Files: `fountain_harness.py`, `fountain_results.py`, `out/fountain-harness-{ctrl-v2,quaff-v2}.jsonl` + `.summary.json`,
`out/logs-{ctrl-v2,quaff-v2}/bot_<seed>.log`, `out/run-*.txt`. Nothing committed.
