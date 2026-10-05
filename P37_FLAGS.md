# P37: feature flags ported from zarutskiysy/nethack `nhbot` (2026-10-04)

Source: github.com/zarutskiysy/nethack, engine `nhbot/` (forked from daglar's `pf_s25p` = our dag25 base, with eL1fe's
fixes ported). The local shallow clone at `forks/zarutskiysy` is branch `main` (40698e4, "project state at freeze"),
whose CHANGES.md has none of these flags; they live on the pushed release branches. This port reads branch **v12pub
(96ef326, 2026-10-03)**, the newest, whose `nhbot/` is identical to branch `dev` (bb7def3) and whose CHANGES.md lists
the A/B readings below (nhbot's own dev held-out seeds, all roles, Mac arm64 + VM x86 pooled).

Target: `engines/dag25/pf_base`. Every flag defaults **OFF** here (nhbot ships them ON unless noted), so with no JF_CFG
the engine's behaviour is unchanged. `MINES_TOOL_TRIP` and `MEDUSA_HOP` are module constants in `dive_logic.py`
(JF_CFG-overridable through `_apply_dev_overrides`); everything else is in `jf_config.py`.

## Ported

| flag | default here | nhbot default | nhbot reading (CHANGES.md / jf_config comments) | files touched | hunks |
|---|---|---|---|---|---|
| MINES_TOOL_TRIP | False | True | +0.0178 +- 0.0065 per game over 272 paired held-out games (23 human/elf/orc identities x 12 seeds), 30 wins / 16 losses: a tool-less planned dive takes the Mines route for any race and takes a dwarf's pick-axe | dive_logic.py (constant, `use_mines`) | 2 |
| DEEP_PRAY_FIRST (+ DEEP_PRAY_FIRST_DEPTH 10) | False | True | part of v4's deep-game set: +0.0021 +- 0.0012 over 512 deterministic held-out pairs vs v3; 39 deaths within 3 turns of a heal with a safe prayer unused | agent.py (`_deep_pray_first`, `_deep_pray_after_heal`, `emergency_strategy`) | 4 |
| LMINION_ELBERETH | False | True | +0.0004 (STATE.md: 'close', z 1.5-2.5); 29 of 1150 games killed by a lawful minion | dive_logic.py (`_melee_ignores_elbereth`, `_lawful_minion`, `elbereth_rest`) | 2 |
| MEDUSA_TITAN_MSG | False | True | v4 deep-game set (above); 31 of ~135 Medusa-2 arrivals never recognised, 13 died there | dive_logic.py (`_TITAN_MSG`, `update`, `_titan_named`) | 3 |
| MEDUSA_STRANDED_REROLL (+ MEDUSA_STRANDED_REROLLS 6) | False | True | v4 set; 6 of 152 Medusa-3 arrivals stranded, 5 died | dive_logic.py (`__init__`, `update`, `_medusa_reroll_stairs`) | 4 |
| MEDUSA_NOT_CASTLE | False | True | v4 set; CASTLE_SCARE / CASTLE_POLY fired on 73 of 205 deep Medusa arrivals, 47 died | dive_logic.py (`gehennom_scare` gate), castle_power.py (`deep_poly_escape_strategy`) | 2 |
| MEDUSA_ZAP_FIRST | False | True | v4 set; 5 logged games played a DEEP_ITEMS gamble before the kept wand of digging | dive_logic.py (`_deep_items_plan`, `_medusa_zap_ready`) | 2 |
| MINO_TAME | False | True | v4 set ("minotaur guard fixes"); 5 minotaur deaths held a known scroll of taming | mino_guard.py (`_minotaurs`, action list) | 2 |
| MINO_DIG_GUARD | False | True | v4 set; dig-out plans under an adjacent dig-stopper | mino_guard.py (`_dig_interrupter`, 2 dig plans) | 3 |
| MINO_CASTLE_ZAP | False | True | v4 set; 3 logged castle-pit zaps | mino_guard.py (`_castle_evidence`, zapdown, `_dig_action`) | 3 |
| DIG_TOOL_MELEE (+ DIG_TOOL_MELEE_MARGIN 1.3) | False | True | "small fixes found by log analysis" (no A/B number); 42% of Archeologist dive deaths swapped to the bullwhip | agent.py (`_keep_digging_tool_wielded`, melee wield) | 2 |
| HOSTILE_RECHECK | False | True | v4 set ("a pet turned hostile is fought"); 1 logged death | monster_tracker.py | 4 |
| PET_HUNGER_FIX (+ PET_HUNGER_TURNS 250) | False | True | v4 set ("a starving pet gets the corpses"); all 5 'killed by a kitten' Wizard deaths | agent.py (`_note_pet_hunger`, `eat_corpses_from_ground`, `update`) | 3 |
| HEAVY_LIFT_GUARD | False | True | v3 set (no separate number); 4 shallow deaths in 1023 games | item/inventory.py (`pickup`), item/item_manager.py (lycanthrope corpse weight) | 2 |
| PANIC_TILE_FIX | False | True | log analysis; one grind sat 38k turns | agent.py (`_note_repeated_panic`) | 1 |
| DITCH_RETRY (+ dive_logic.DITCH_RETRY_WAIT 400) | False | True | log analysis (Knight pony) | dive_logic.py (`_ditch_pet_check`) | 3 |
| SPORE_TRAP_FIX | False | True | log analysis (HP test was a ratio, true at any HP) | combat/fight_heur.py | 1 |
| RAY_BOUNCE_FIX | False | True | 7 logged deaths from the bot's own bounced cold/fire ray | known_items.py | 1 |
| SELF_ZAP_FIX (+ SELF_ZAP_PENALTY 300, RAY_CRIT_RUN 0) | False | True (RAY_CRIT_RUN 0) | v3 set; 20 deaths in 1023 games right after our own ray hit us (two of them Valkyries' lightning) | combat/fight_heur.py (`get_potential_wand_usages`), known_items.py (RAY_CRIT_RUN) | 3 |
| PRAYER_RECORD_FIX | False | True | v3 set; 13 of 17 lost prayer records were lycanthropy cures | agent.py (`pray` -> `_after_prayer`) | 2 |
| RECORD_MODEL_FIX | False | True | v3 set | nhmodel/prayer.py (`on_prayer`) | 1 |
| ELBERETH_REWRITE_FIX | False | True | v3 set | dive_logic.py (`_elbereth_before_digging_escape`, `dig_with_tool`) | 4 |
| PYTHON_HOLD | False | True | v4 set; 3 of 59 Medusa-4 deaths drowned by a python | dive_logic.py (`_PYTHON_GRAB`, eel-hold check) | 2 |
| UNSEEN_PET_GUARD (+ UNSEEN_PET_TURNS 20) | **True** | True | v10b: Rangers WITHOUT it +0.022 +- 0.012 (420 pairs); eL1fe v6->v7 private seeds -0.024 Ranger / -0.026 Monk / +0.025 Priest per identity group | combat/fight_heur.py (`unseen_pet_may_be_at`) | 2 |
| MEDUSA_HOP (+ MEDUSA_HOP_MAX 6) | False | False (daglar's OVERRIDES: on for arc/cav/mon/pri/wiz, off for val) | "off pending A/B"; Barbarian MEDUSA_ISLE_HOP +0.002 ('close') | dive_logic.py (constants, `__init__`, `try_dig_down`, `_medusa_terrain`, `_medusa_hop_plan`, `_medusa_hop`) | 4 |

Total: 25 switches, 11 files, 60 hunks (one jf_config block counts as 1).

## Adaptations (where nhbot's hunk differed from a clean guard)

- **UNSEEN_PET_GUARD defaults True**: the guard is already the head's behaviour (eL1fe 76b511c is in both trees);
  nhbot's switch exists to turn it OFF. Default-OFF would have changed the engine. The experiment is
  `{"UNSEEN_PET_GUARD": false}`.
- **LMINION_ELBERETH**: nhbot *replaced* the head's Barbarian-only `S_ANGEL` ignorer rule with the flag. Here the
  Barbarian line is kept and the flag's check is added after it, so off = unchanged.
- **PRAYER_RECORD_FIX**: nhbot wraps `step(PRAY)` in try/except unconditionally (the `except` body is flag-gated).
  Here the whole try/except is under the flag; the body of the old `pray()` tail became `_after_prayer()` in both
  branches (pure refactor, same statements in the same order).
- **RECORD_MODEL_FIX**: nhbot's `except Exception: record_fix = True` fallback is `False` here (the import of
  jf_config never fails in-package; this keeps the off-path identical even if it did).
- **DIG_TOOL_MELEE**: nhbot's castle_cross `_swap_for_fight` hunk is gated by `CASTLE_PICK_MELEE` (off, "pending a
  lift-suite A/B"), not by DIG_TOOL_MELEE -- not ported; DIG_TOOL_MELEE here touches agent.py only, as in nhbot.
- **MEDUSA_TITAN_MSG** also narrows the existing titan-*glyph* rule (skips a level where 'You hear a door open.' was
  heard) -- that narrowing is under the flag too, as in nhbot. Uses the head's existing `_door_heard` map.
- **MEDUSA_STRANDED_REROLL**: `_medusa_reroll_stairs` was re-ordered so the stranded bookkeeping runs before the
  `_medusa_reroll_blocked_until` early return; with the flag off the two returns are equivalent (same condition, no
  side effects in between).
- Comments were shortened and nhbot's game ids kept only where they identify the evidence; "nhbot" is named where a
  number is theirs.

## Skipped (not ported)

| what | why |
|---|---|
| FORCE_BOLT, FB_FOCUS, FB_SANITY, FB_RESERVE, FB_SHOP_KNOWN, FB_OVER_RAYS, `_CAST_REFUSED`, '(gone)' spells (character.py) | Wizard spellcasting; our character is a Valkyrie. (Our head keeps its own unflagged force-bolt code.) |
| RING_MODULE (+ item/ring_amulet_*.py, scroll_identify.py, the `install(Inventory)` hook and 6 strategy insertions) | Wizard-only ring module, explicitly not wanted |
| ARC_DIG_DIVE_XL 3 -> 5 | Archeologist-only; also an unguarded constant change |
| ROLE_GRIND_LEVELS, global_logic `by_role` | role table for Rogue/Knight/Tourist/Priest; our head hardcodes `{'Rogue': {}}` |
| CASTLE_PICK_MELEE (castle_cross `_swap_for_fight`) | off in nhbot "pending a lift-suite A/B", unmeasured |
| AT_THREAT_AVOID (+ 8 tunables, ~130 lines) | nhbot REJECTED it: -0.004 +- 0.003 over 235 pairs |
| MEDUSA_HOLE_CYCLE (+ `_dug_holes`, cycle/plunge/rest machinery, ~150 lines) | nhbot REJECTED it: -0.0147 +- 0.0050 per Medusa game |
| STALKER_ZAP_FIX, SHOP_SAFETY, ALIGN_PRAYER, LONE_WEAK_THREAT, FEYE_GUARD, DURABLE_ELBERETH | off in nhbot "pending an A/B", not in the requested list |
| ALTAR_NO_ENGRAVE | on in nhbot (v4 "no Elbereth on altars") but not in the requested list; small (agent.can_engrave) -- easy follow-up if wanted |
| ENHANCE_PAGES (character.py two-page `#enhance` assert -> if) | DT6A's fix, on and *unguarded* in nhbot; cannot be flag-gated without changing the assert path; Valkyries rarely hit a two-page menu. Not ported |
| import renames (`pf_base` -> `nhbot`), removal of our Jev instrument (`_jf_ring`), our Wizard shop-mask and Knight floating-eye hypotheses | ours to keep |

## JF_CFG

Each flag alone, e.g. `JF_CFG='{"MINES_TOOL_TRIP": true}'`; the UNSEEN_PET_GUARD experiment is `{"UNSEEN_PET_GUARD": false}`.

All 24 default-off switches on (UNSEEN_PET_GUARD left at its default True):

```
{"MINES_TOOL_TRIP": true, "DEEP_PRAY_FIRST": true, "LMINION_ELBERETH": true, "MEDUSA_TITAN_MSG": true,
 "MEDUSA_STRANDED_REROLL": true, "MEDUSA_NOT_CASTLE": true, "MEDUSA_ZAP_FIRST": true, "MINO_CASTLE_ZAP": true,
 "MINO_DIG_GUARD": true, "MINO_TAME": true, "DIG_TOOL_MELEE": true, "HOSTILE_RECHECK": true, "PET_HUNGER_FIX": true,
 "HEAVY_LIFT_GUARD": true, "PANIC_TILE_FIX": true, "DITCH_RETRY": true, "SPORE_TRAP_FIX": true, "RAY_BOUNCE_FIX": true,
 "SELF_ZAP_FIX": true, "PRAYER_RECORD_FIX": true, "RECORD_MODEL_FIX": true, "ELBERETH_REWRITE_FIX": true,
 "PYTHON_HOLD": true, "MEDUSA_HOP": true}
```

nhbot's own shipped set (what v10c/v12pub run for a Valkyrie, per roles.py's "safe" profile) is the above without
MEDUSA_HOP and with UNSEEN_PET_GUARD true.

## Verification

- `python -c "import pf_base.jf_config, pf_base.dive_logic"` (and the other nine touched modules) imports clean;
  JF_CFG overrides of `MINES_TOOL_TRIP` / `MEDUSA_HOP` (dive_logic) and `DEEP_PRAY_FIRST` (jf_config) take effect.
- pyflakes on the 11 changed files: no new findings vs the base (one pre-existing SyntaxWarning moved 14 lines).
- Smoke games (jev-nethack `tools/frontier_bench.py`, ids 2 / 1898 / 3012, frozen clock, val-dwa-law-fem), tags
  `smoke-p37-flags-off` and `smoke-p37-flags-mtt` in `bench/frontier/`: all 6 games completed, error None.
  - flags off: id 2 Dlvl 25 / 12,354 turns / 0.466 (lynx); id 1898 Dlvl 3 / 10,429 / 0.051 (dwarf, Xp 7); id 3012 Dlvl
    25 / 20,073 / 0.466 (raven). **Identical, field for field, to the pre-port `smoke-p37-head-val-3` record** (same
    Mac, same frozen clock), and the per-game engine logs are byte-identical past the TRAJ header (pid/start): the
    engine is unchanged with every flag at its default.
  - `{"MINES_TOOL_TRIP": true}`: the same three outcomes and byte-identical engine logs. Expected: our character is a
    **dwarf** (val-dwa-law-fem), for whom `use_mines` is already true (MINES_ROUTE: dwarves and gnomes); the flag only
    adds humans, elves and orcs. It cannot move this line unless the identity changes -- nhbot's +0.018 is a
    human/elf/orc number. (Game 3012's tool-less dive took the Mines branch and camped there in both runs.)
  - cloud series (cloud-el1fe-bd8cb7c-val-4000) on the same ids, for orientation only: id 2 Dlvl 24 / 12,481 (drowned),
    id 1898 Dlvl 29 / 35,524 (master mind flayer), id 3012 Dlvl 3 / 23,524 (giant spider) -- the Mac and cloud series
    diverge, as known.
