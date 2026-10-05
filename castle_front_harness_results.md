# Castle-front harness: passtune v2 (the crusher) vs v1 vs control (2026-10-05)

Branch p37-passtune (engine engines/dag25/pf_base), uncommitted. Wizard-mode NLE on the Mac, the head's dag25 agent
dropped on the castle's west courtyard (level (8,11) = map (0,8)) at XL 8/9 with a castle-arrival kit (pick-axe, dwarvish
iron helm, mithril coat, iron shoes, dwarvish cloak, the Valkyrie's long sword and shield) plus a wooden flute, run to
death or 1,500 turns. Seeds 1000-1099, the same castle per seed in every arm (unpaired otherwise). ~3-8 s per game.

## Commands

    cd ~/jev-nethack-frontier/wt/p37-passtune
    for arm in control v1 v2; do for i in 0 1; do
      nohup ~/jev-nethack-frontier/.venv/bin/python castle_front_harness.py --arm $arm --seeds 100 --seed-base 1000 \
          --shard $i/2 --out out/cf > out/cf/run-$arm-$i.txt 2>&1 &
    done; done
    ~/jev-nethack-frontier/.venv/bin/python out/cf/merge.py out/cf        # the read below
    # one game, every bot step printed from step 150: --probe 1002 --trace 150

Arms: control = defaults (CASTLE_PASSTUNE off: the head gives the castle up, 'nothing that crosses water');
v1 = {"CASTLE_PASSTUNE": true}; v2 = {"CASTLE_PASSTUNE": true, "CASTLE_PASSTUNE_CRUSH": true}.
Records: out/cf/castle-front-<arm>-s<i>of2.jsonl, engine logs out/cf/logs-<arm>/bot_<seed>.log.

## Read (100 games per arm, Wilson 95%)

| | control | v1 | v2 |
|---|---|---|---|
| opened the bridge | 0 | 49% [39, 59], median 5 plays | 49% [39, 59], median 5 plays |
| unread plays / bad items | - | 0 / 0 | 0 / 0 |
| died within 1,500 turns | 85% [77, 91] | 100% [96, 100] | 100% [96, 100] |
| alive 300 turns after hand-over | 28% [20, 37] | 6% [3, 12] | 9% [5, 16] |
| alive 300 / 600 / 1500 after opening | - | 4% [1, 14] / 2% / 0% [0, 7] | 8% [3, 19] / 6% [2, 17] / 0% [0, 7] |
| median turns alive after opening | - | 15 | 48 |
| garrison killed by the bridge (sum / per opened game) | - | 0 | 254 / 5.2 (24 of 49 openings: 6-14 each) |
| crusher end | - | - | 30-toggle cap 21, died mid-crusher 21, bridge destroyed by a soldier's wand 5, 600 turns 2 |
| antechamber / hallway / throne / tower / chest / Valley | 0 | 0 | 0 |
| killers, all games (top) | minotaur 34, shark 14, eel 7 | minotaur 22, soldier 19, lieutenant 11 | minotaur 26, eel 7, xorn 5, soldier 5, lightning 4 |
| killers, opened games | - | soldier 15, lieutenant 11 | minotaur 4, eel 4, lightning 4, xorn 3, rust monster 3 |

The crusher does what dbridge.c says: 'The soldier is crushed by the falling portcullis!', 'The soldier falls into the
moat.' (24 games with 6-14 kills each, 21 of them stopped only by the 30-toggle cap with soldiers still coming), and the
walk-in's killers (soldier, lieutenant: 26 of 49 in v1) drop to 5 of 49. The hero still dies: median 48 turns after the
opening instead of 15, 8% vs 4% alive at 300 turns (intervals overlap). What kills the v2 hero after the garrison: the
throne room's court (xorns through the walls, nagas, a black dragon's disintegration, liches' 'head aches', a storm
giant's lightning, soldiers' wands: 'The soldier zaps a wand of striking', 'death ray'), the west-maze minotaur reaching
the courtyard (26 of 100 v2 games, 34 of 100 control), and the drawbridge eels at the shore square (4 drownings of 49
openings even on Elbereth: the bite-and-wrap needs no melee turn). 25 of the 49 v2 openings died before any toggle
(median 21 turns after opening), to the same court and minotaur.

No arm reached the antechamber in 100 games (the walk-in's hold at (3,8) never ends: 'inside' 6 of 49, all killed in the
first squares). No on-foot path to a tower chest exists without the throne room (castle.des: the towers open onto the
row-3/row-13 hallways whose other door is the locked throne-room door), so the walk-in's realistic goal is XP from the
garrison at the span or the trap-door hall, not the chest; the control arm's 15% alive at 1,500 turns is the head
waiting on the west side.

Deviations from the pool's arrivals: full HP and a blessed kit at the hand-over; no west-maze walk (the agent is put on
the courtyard's west column; teleport.c tele_jump_ok refuses any teleport from outside into level x 9..18, the castle's
exclusion box); the starting pet follows the levelport; no #enhance (wizard-mode skill screens stripped).
