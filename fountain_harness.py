#!/usr/bin/env python3
"""The fountain harness (P37, 2026-10-05): the head's dag25 agent dropped on a shallow Dungeons level that has a fountain, in
a wizard-mode NLE game on the Mac, at XL 5 with an early kit, run to death, Dlvl --stop or --max-turns turns, logging.
Diagnostics only: never the bench. The wizard-mode pattern (NLE wizard=True, Ctrl-V levelport, Ctrl-W wishes, the #enhance
parse wrapper, make_agent()/reset/act loop) is valley_harness.py's.

  ~/jev-nethack-frontier/.venv/bin/python fountain_harness.py --engine ~/jev-nethack-frontier/wt/p37-fountain/engines/dag25 \\
        --seeds 300 --xl 5 --dlvl 3 --workers 8 --tag ctrl
  ... --cfg '{"FOUNTAIN_QUAFF": true, "TC_ROUTE": true}' --tag quaff

Why: fountain.c drinkfountain summons a water demon 1 drink in 30 and it grants a wish (20 - Dlvl)% of the time (dowaterdemon:
rnd(100) > 80 + level_difficulty()); the head's TC_ROUTE turns a wish into a ring of teleport control (tele_route.route_wish) and
5 of the sizing read's 12 wish games reached 0.79-0.80. The cost side is the hostile demon (80 + Dlvl)% of the time, the nymph,
the moccasins, the curse and the contaminated water (-3..6 Str). The two arms (FOUNTAIN_QUAFF off / on) share seeds and setup.

How:
  1. a wizard-mode NLE (actions = nethack.ACTIONS + WIZLEVELPORT (Ctrl-V) + WIZWISH (Ctrl-W) + WIZMAP (Ctrl-F)), the arena's
     options minus autopickup plus the explicit character options;
  2. the harness drives the setup before the agent sees anything: '#levelchange' to the XL, Ctrl-W wishes for the kit, Ctrl-V to
     --dlvl, Ctrl-F (magic mapping) and a scan of the map for a fountain ('{'); no fountain -> Ctrl-V one level deeper, up to
     --dlvl-max; none at all -> the seed is recorded as 'no fountain' and skipped (wizard mode cannot place a fountain);
  3. hands the observation stream to the head's bot (engines/dag25/bot.py make_agent(): reset(obs), act(obs)), answering 'Die?'
     with y itself so deaths are real, until the game ends, Dlvl --stop is reached, or --max-turns pass after the landing;
     JF_LOG_DIR/JF_EPISODE make the engine write bot_<seed>.log beside the record, and the FOUNTAIN lines in it are the metrics.

Deviations from real games: the level is magic-mapped (both arms), the hero lands at turn ~5 with full HP and a wished kit, a fresh
dungeon per seed (wizard mode re-rolls it: arms compare UNPAIRED), and the dip rule's XL 7 keeps the long sword out of the fountain
at XL 5 (a real game at XL 7+ dips first and drinks only once no dip is wanted).

Output: <out>/fountain-harness-<tag>.jsonl (one record per seed), .summary.json, and logs-<tag>/bot_<seed>.log.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import multiprocessing
import os
import pathlib
import random
import re
import statistics
import sys
import time
import traceback
from collections import Counter

HOME = pathlib.Path.home()
HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_ENGINE = HERE / 'engines' / 'dag25'
DEFAULT_PKG = os.environ.get('NETHACKERS_PKG') or str(HOME / 'jev-nethack-frontier' / 'nhk')
CHAR = 'val-dwa-law-fem'

# the head's typical early kit at XL 5 on Dlvl 3 (the Valkyrie starts with a +1 long sword, a dagger and a +3 small shield): a
# helm and body armour the grind usually has by then, and food so hunger never decides the game
KITS = {
    'early': ['blessed +0 dwarvish iron helm', 'blessed +1 ring mail', '3 blessed food rations'],
    'none': [],
}

ROLE_WORDS = {'val': 'Valkyrie'}
RACE_WORDS = {'dwa': 'dwarf', 'hum': 'human'}
GENDER_WORDS = {'fem': 'female', 'mal': 'male'}
ALIGN_WORDS = {'law': 'lawful', 'neu': 'neutral', 'cha': 'chaotic'}
DUNGEONS = 0


def character_options(character: str) -> list[str]:
    role, race, align, gender = character.split('-')
    return [f'role:{ROLE_WORDS[role]}', f'race:{RACE_WORDS[race]}', f'gender:{GENDER_WORDS[gender]}', f'align:{ALIGN_WORDS[align]}']


def observation_keys():
    try:
        if DEFAULT_PKG not in sys.path:
            sys.path.insert(0, DEFAULT_PKG)
        from nethackers.arena.environment import PUBLIC_OBSERVATION_KEYS  # type: ignore
        return tuple(PUBLIC_OBSERVATION_KEYS)
    except Exception:  # noqa: BLE001
        return ('glyphs', 'chars', 'colors', 'specials', 'blstats', 'message', 'inv_glyphs', 'inv_strs', 'inv_letters',
                'inv_oclasses', 'screen_descriptions', 'tty_chars', 'tty_colors', 'tty_cursor', 'misc')


class WizFountain:
    """One wizard-mode game: the harness's setup keystrokes, then the bot's actions."""

    def __init__(self, seed: int, character: str = CHAR, verbose: bool = False):
        from nle import nethack
        from nle.env.base import NLE
        from nle.nethack.actions import WizardCommand
        self.nh = nethack
        self.actions = tuple(nethack.ACTIONS) + (WizardCommand.WIZLEVELPORT, WizardCommand.WIZWISH, WizardCommand.WIZMAP)
        self.idx = {int(a): i for i, a in enumerate(self.actions)}
        self.LEVELPORT, self.WISH, self.MAP = len(nethack.ACTIONS), len(nethack.ACTIONS) + 1, len(nethack.ACTIONS) + 2
        options = [o for o in nethack.NETHACKOPTIONS if o not in ('autopickup', '!autopickup')] + character_options(character)
        self.env = NLE(actions=self.actions, character=character, allow_all_yn_questions=True, allow_all_modes=True,
                       max_episode_steps=10_000_000, observation_keys=observation_keys(), wizard=True, options=options)
        self.env.seed(core=seed, disp=seed, reseed=False)
        self.obs = self.env.reset()
        if isinstance(self.obs, tuple):
            self.obs = self.obs[0]
        self.done = False
        self.verbose = verbose
        self.setup_steps = 0

    def press(self, index: int):
        if self.done:
            return
        out = self.env.step(index)
        if len(out) == 5:
            self.obs, _r, term, trunc, self.info = out
            self.done = bool(term or trunc)
        else:
            self.obs, _r, self.done, self.info = out
        self.setup_steps += 1

    def key(self, ch: str):
        self.press(self.idx[ord(ch)])

    def flags(self):
        misc = self.obs['misc']
        return bool(misc[0]), bool(misc[1]), bool(misc[2])

    def top(self) -> str:
        return bytes(self.obs['tty_chars'][0]).decode('latin-1').rstrip()

    def message(self) -> str:
        return bytes(self.obs['message']).split(b'\0')[0].decode('latin-1')

    def clear_more(self, n: int = 12):
        for _ in range(n):
            if self.flags()[2] or '--More--' in self.top():
                self.press(self.idx[int(self.nh.MiscAction.MORE)])
            else:
                return

    def type_line(self, text: str):
        for ch in text:
            self.key(ch)
        self.press(self.idx[int(self.nh.MiscAction.MORE)])

    def bl(self):
        b = self.obs['blstats']
        n = self.nh
        return dict(depth=int(b[n.NLE_BL_DEPTH]), dnum=int(b[n.NLE_BL_DNUM]), dlevel=int(b[n.NLE_BL_DLEVEL]), turn=int(b[n.NLE_BL_TIME]),
                    hp=int(b[n.NLE_BL_HP]), hpmax=int(b[n.NLE_BL_HPMAX]), xl=int(b[n.NLE_BL_XP]), ac=int(b[n.NLE_BL_AC]),
                    str_=int(b[n.NLE_BL_STR25]))

    # ---- setup
    def set_xl(self, xl: int):
        if self.bl()['xl'] == xl:
            return
        self.press(self.idx[int(self.nh.Command.EXTCMD)])
        self.type_line('levelchange')
        if self.flags()[1]:
            self.type_line(str(xl))
        self.clear_more()

    def wish(self, text: str) -> str | None:
        self.press(self.WISH)
        if not self.flags()[1]:
            self.clear_more()
            return None
        self.type_line(text)
        msg = self.message() + ' ' + self.top()
        self.clear_more()
        m = re.search(r'\b([a-zA-Z]) - ', msg)
        return m[1] if m else None

    def equip(self, letter: str, text: str):
        if 'ration' in text or 'food' in text:
            return
        weapon = any(w in text for w in ('sword', 'Excalibur', 'axe'))
        cmd = self.nh.Command.WIELD if weapon else self.nh.Command.WEAR
        self.press(self.idx[int(cmd)])
        if self.flags()[1] or 'What do you want to' in self.top():
            self.key(letter)
        self.clear_more()
        for _ in range(8):   # multi-turn armour donning
            if '--More--' in self.top() or self.flags()[2]:
                self.clear_more()
            else:
                break

    def levelport(self, answer: str) -> bool:
        before = self.bl()
        self.press(self.LEVELPORT)
        if not self.flags()[1]:
            self.clear_more()
            return False
        self.type_line(answer)
        self.clear_more()
        after = self.bl()
        return (after['dnum'], after['dlevel']) != (before['dnum'], before['dlevel'])

    def magic_map(self):
        self.press(self.MAP)
        self.clear_more()

    def fountains(self) -> int:
        """'{' squares on the (mapped) map: fountains are the only '{' in NetHack's default symbol set."""
        chars = self.obs['chars']
        return int((chars == ord('{')).sum())

    def answer_die(self) -> bool:
        if self.flags()[0] and 'Die?' in self.top():
            self.key('y')
            self.clear_more()
            return True
        return False


def load_bot(engine: pathlib.Path):
    engine = engine.resolve()
    os.chdir(engine)
    if str(engine) not in sys.path:
        sys.path.insert(0, str(engine))
    import importlib
    bot_module = importlib.import_module('bot')
    _patch_wizard_screens()
    return bot_module.make_agent()


# wizard-mode #enhance screens (valley_harness.py's wrapper): 'a -  bare handed combat Unskilled  0(  20)' -> '... [Unskilled]',
# letters stripped (wizard mode letters every skill; the harness hero never advances one)
_SKILL_LINE = re.compile(r'\s+(Unskilled|Basic|Skilled|Expert|Master|Grand Master)\s+-?\d+\(\s*-?\d+\)\s*$')
_SKILL_LETTER = re.compile(r'^\s*[a-zA-Z] - ')


def _patch_wizard_screens():
    from pf_base import character  # type: ignore

    orig = character.Character._parse_enhance_view
    if getattr(orig, '_fountain_harness', False):
        return

    def patched(self):
        lines = []
        for line in self.agent.popup:
            if _SKILL_LINE.search(line):
                line = _SKILL_LETTER.sub('', _SKILL_LINE.sub(r' [\1]', line))
            lines.append(line)
        self.agent.popup = lines
        return orig(self)

    patched._fountain_harness = True
    character.Character._parse_enhance_view = patched


def killer_from_tty(game: WizFountain) -> str | None:
    text = '\n'.join(bytes(r).decode('latin-1') for r in game.obs['tty_chars'])
    m = re.search(r'(killed by [^\n.]*|poisoned by [^\n.]*|petrified by [^\n.]*|died of starvation|drowned[^\n.]*|'
                  r'choked on [^\n.]*|burned by [^\n.]*|dissolved in [^\n.]*|turned to slime[^\n.]*|zapped [^\n.]*)', text)
    return m[1].strip() if m else None


# fountain.c messages, one per event (dips and drinks alike; 'You unleash' counts the wish-granting demon too)
GAME_EVENTS = (
    ('You unleash', 'demon'), ('presence of evil', 'demon'), ('grants you a wish', 'wish'),
    ('You attract', 'nymph'), ('seductive voice', 'nymph'),
    ('pours forth', 'moccasin'), ('hissing', 'moccasin'),
    ("water's no good", 'curse'), ('contaminated', 'poison'), ('water is foul', 'foul'),
    ('fountain dries up', 'dry'), ('gushes forth', 'gush'), ('stole', 'stolen'), ('steals', 'stolen'),
    ('From the murky depths', 'excalibur'),
)

_Q = re.compile(r'FOUNTAIN quaff n=(\d+) dlvl=(\d+)')
_E = re.compile(r'FOUNTAIN event=(\w+)')
_TASK = re.compile(r"DIVE task (walk to a fountain \(quaff\)|drink from the fountain)")


def read_bot_log(path: pathlib.Path) -> dict:
    """The FOUNTAIN lines (dive_logic.fountain_quaff) and the wish lines (agent.update / power.py) of one game's log."""
    r = dict(quaffs=0, fountains_quaffed=0, events=Counter(), wishes=0, wish_texts=[], tc_ring_learned=0, refused=0)
    if not path.exists():
        return r
    fountains = set()
    for line in path.read_text(errors='replace').splitlines():
        if 'FOUNTAIN result' in line and 'refused' in line:
            r['refused'] += 1
            r['quaffs'] -= 1     # the matching 'FOUNTAIN quaff' line was no drink
            continue
        if 'FOUNTAIN quaff' in line:
            r['quaffs'] += 1
            m = re.search(r'\[s\d+ t\d+ d(\d+) (\d+):(\d+) ', line)
            q = _Q.search(line)
            if m and q and q[1] == '1':
                fountains.add((m[2], m[3], r['quaffs']))
        m = _E.search(line)
        if m:
            r['events'][m[1]] += 1
        if 'POWER wishing for' in line:
            r['wishes'] += 1
            m = re.search(r"POWER wishing for '([^']*)'", line)
            r['wish_texts'].append(m[1] if m else '?')
        if 'POWER wished teleport control' in line:
            r['tc_ring_learned'] += 1
    r['fountains_quaffed'] = len(fountains)
    r['events'] = dict(r['events'])
    return r


def run_one(seed: int, a) -> dict:
    t0 = time.time()
    random.seed(seed)
    out = dict(seed=seed, tag=a.tag, kit=a.kit, xl=a.xl)
    game = WizFountain(seed, verbose=a.verbose)
    try:
        game.set_xl(a.xl)
        letters = []
        for text in KITS[a.kit] + list(a.wish):
            letter = game.wish(text)
            letters.append((text, letter))
            if letter:
                game.equip(letter, text)
        out['wishes_setup'] = letters
        # a level with a fountain: Ctrl-V to --dlvl, map it, look for '{'; else one deeper, up to --dlvl-max
        found = 0
        for d in range(a.dlvl, a.dlvl_max + 1):
            if game.bl()['depth'] != d and not game.levelport(str(d)):
                out['error'] = f'level teleport to {d} refused: {game.top()!r}'
                return out
            game.magic_map()
            found = game.fountains()
            if found:
                break
        if not found:
            out['error'] = f'no fountain on Dlvl {a.dlvl}-{a.dlvl_max}'
            out['no_fountain'] = True
            return out
        out['fountains_on_level'] = found
        out['landing'] = game.bl()
        out['setup_steps'] = game.setup_steps
        if a.setup_only:
            out['tty'] = [bytes(r).decode('latin-1').rstrip() for r in game.obs['tty_chars']][:24]
            return out
        # ---- hand over to the head's agent
        os.environ['JF_EPISODE'] = str(seed)
        bot = load_bot(pathlib.Path(a.engine))
        bot.reset(game.obs)
        landing_turn = game.bl()['turn']
        max_depth = game.bl()['depth']
        steps = 0
        last_bl = game.bl()
        tc_known = None
        game_events = Counter()   # the game's own messages (engine-independent): fountain.c's event texts
        last_msg = ''
        try:
            while not game.done and steps < a.max_steps:
                if game.answer_die():
                    continue
                action = bot.act(game.obs)
                game.press(int(action))
                steps += 1
                msg = game.message()
                if msg and msg != last_msg:
                    for frag, name in GAME_EVENTS:
                        if frag in msg:
                            game_events[name] += 1
                last_msg = msg
                if game.done:
                    break
                last_bl = b = game.bl()
                max_depth = max(max_depth, b['depth'])
                if b['depth'] >= a.stop or b['turn'] - landing_turn > a.max_turns:
                    break
        finally:
            try:
                agent = getattr(getattr(bot, '_driver', None), '_agent', None)
                if agent is not None:
                    from pf_base import power_route  # type: ignore
                    tc_known = bool(power_route.tc_known(agent))
            except Exception:  # noqa: BLE001
                tc_known = None
            bot.close()
            out.update(steps=steps, turns=last_bl['turn'] - landing_turn, max_depth=max_depth, final=last_bl, died=game.done,
                       killer=killer_from_tty(game) if game.done else None, reached_stop=max_depth >= a.stop, tc_known=tc_known,
                       game_events=dict(game_events))
            out.update(read_bot_log(pathlib.Path(os.environ['JF_LOG_DIR']) / f'bot_{seed}.log'))
    except Exception as e:  # noqa: BLE001
        out['crash'] = f'{type(e).__name__}: {str(e)[:300]}'
        out['traceback'] = traceback.format_exc(limit=8)[-2000:]
    finally:
        out['wall_s'] = round(time.time() - t0, 1)
        try:
            game.env.close()
        except Exception:  # noqa: BLE001
            pass
    return out


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(p, 4), round(c - h, 4), round(c + h, 4))


def summarize(rows: list[dict], a) -> dict:
    ok = [r for r in rows if 'crash' not in r and 'error' not in r and r.get('max_depth') is not None]
    n = len(ok)
    s = dict(tag=a.tag, kit=a.kit, xl=a.xl, dlvl=a.dlvl, seeds=len(rows), crashes=sum('crash' in r for r in rows),
             no_fountain=sum(bool(r.get('no_fountain')) for r in rows), setup_errors=sum('error' in r for r in rows), n=n)
    if not n:
        return s
    ev = Counter()
    for r in ok:
        ev.update(r.get('events', {}))
    quaffs = sum(r.get('quaffs', 0) for r in ok)
    died = [r for r in ok if r.get('died')]
    demon_deaths = [r for r in died if 'water demon' in str(r.get('killer'))]
    wished = [r for r in ok if r.get('wishes', 0) > 0]
    wished_tc = [r for r in wished if r.get('tc_known') or r.get('tc_ring_learned')]
    s.update(
        quaffs=quaffs, quaffs_per_game=round(quaffs / n, 3),
        fountains_quaffed=sum(r.get('fountains_quaffed', 0) for r in ok),
        games_quaffing=sum(r.get('quaffs', 0) > 0 for r in ok),
        events=dict(ev),
        wishes=sum(r.get('wishes', 0) for r in ok), wish_games=len(wished), wish_games_wilson=wilson(len(wished), n),
        wish_texts=dict(Counter(t for r in ok for t in r.get('wish_texts', []))),
        wish_then_tc_known=len(wished_tc), wish_then_tc_frac=wilson(len(wished_tc), len(wished)) if wished else None,
        hostile_demons=ev.get('demon', 0) - ev.get('wish', 0), demon_deaths=len(demon_deaths),
        nymphs=ev.get('nymph', 0), curses=ev.get('curse', 0), poison=ev.get('poison', 0), moccasins=ev.get('moccasin', 0),
        deaths=len(died), death_rate_wilson=wilson(len(died), n),
        killers=Counter(str(r.get('killer'))[:40] for r in died).most_common(15),
        reached_stop=sum(bool(r.get('reached_stop')) for r in ok), reached_stop_wilson=wilson(sum(bool(r.get('reached_stop')) for r in ok), n),
        turns_median=statistics.median(r['turns'] for r in ok), turns_mean=round(statistics.mean(r['turns'] for r in ok), 1),
        max_depth_mean=round(statistics.mean(r['max_depth'] for r in ok), 2),
        str_final_mean=round(statistics.mean(r['final']['str_'] for r in ok), 2),
        wall_s_mean=round(statistics.mean(r['wall_s'] for r in ok), 1),
    )
    return s


def _worker(args):
    seed, a = args
    return run_one(seed, a)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--engine', default=str(DEFAULT_ENGINE))
    p.add_argument('--seeds', type=int, default=20)
    p.add_argument('--seed-base', type=int, default=1_000)
    p.add_argument('--probe', type=int, help='one seed, verbose, record printed')
    p.add_argument('--xl', type=int, default=5)
    p.add_argument('--dlvl', type=int, default=3, help='the first level tried for a fountain')
    p.add_argument('--dlvl-max', type=int, default=6, help='the deepest level tried for a fountain')
    p.add_argument('--kit', choices=sorted(KITS), default='early')
    p.add_argument('--wish', action='append', default=[], help='extra wish text (repeatable)')
    p.add_argument('--stop', type=int, default=12, help='stop once this Dlvl is reached')
    p.add_argument('--max-turns', type=int, default=3000, help='game turns after the landing')
    p.add_argument('--max-steps', type=int, default=60_000)
    p.add_argument('--workers', type=int, default=1, help='games in parallel (one fresh process per game)')
    p.add_argument('--cfg', help='JF_CFG json for the engine (dev switch overrides, jf_config.py)')
    p.add_argument('--tag', default='')
    p.add_argument('--out', default=str(HERE / 'out'))
    p.add_argument('--setup-only', action='store_true')
    p.add_argument('--verbose', action='store_true')
    a = p.parse_args()
    a.tag = a.tag or f'{a.kit}-xl{a.xl}-d{a.dlvl}'
    out_dir = pathlib.Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    os.environ['JF_LOG_DIR'] = str(out_dir / f'logs-{a.tag}')
    if a.cfg:
        os.environ['JF_CFG'] = a.cfg
    if a.probe is not None:
        a.verbose = True
        r = run_one(a.probe, a)
        print(json.dumps(r, indent=1, default=str))
        return 0
    fn = out_dir / f'fountain-harness-{a.tag}.jsonl'
    rows = []
    seeds = [a.seed_base + i for i in range(a.seeds)]
    with open(fn, 'w') as fh:
        def record(r):
            rows.append(r); fh.write(json.dumps(r, default=str) + '\n'); fh.flush()
            status = r.get('error') or r.get('crash') or \
                f"depth {r.get('max_depth')} turns {r.get('turns')} quaffs {r.get('quaffs')} events {r.get('events')} killer {r.get('killer')}"
            print(f"seed {r['seed']}: {status}", flush=True)
        if a.workers > 1:
            ctx = multiprocessing.get_context('spawn')
            with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers, mp_context=ctx, max_tasks_per_child=1) as ex:
                for r in ex.map(_worker, [(s, a) for s in seeds]):
                    record(r)
        else:
            for s in seeds:
                record(run_one(s, a))   # one process per game would be cleaner (engine module state); --workers does that
    s = summarize(rows, a)
    (out_dir / f'fountain-harness-{a.tag}.summary.json').write_text(json.dumps(s, indent=1, default=str))
    print(json.dumps(s, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
