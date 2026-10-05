#!/usr/bin/env python3
"""The castle-front harness (P37 v2, 2026-10-05): the head's dag25 agent dropped on the castle's west courtyard in a
wizard-mode NLE game on the Mac, with a castle-arrival kit and a wooden flute, run to death or --max-turns turns,
logging. Diagnostics only: never the bench.

  ~/jev-nethack-frontier/.venv/bin/python castle_front_harness.py --arm v2 --seeds 100 [--shard 0/3] [--probe 7]
  arms: control (no passtune: the head gives the castle up), v1 (CASTLE_PASSTUNE: open and walk in),
        v2 (CASTLE_PASSTUNE + CASTLE_PASSTUNE_CRUSH: the crusher, then the walk-in)

Why (f2.4.0-passtune on the pool, 1,660 castle arrivals): 52 games played the tune, 18 opened the bridge, all 18 died at
the front within 10-130 turns of the opening (soldiers, trolls, a dragon, a lich). The pool scores the castle depth
whether we die inside or outside; what this harness sizes is the garrison fight itself, and whether the bridge can do
the killing (dbridge.c close_drawbridge crushes what stands on the span or under the portcullis).

How (valley_harness.py's pattern; the keystrokes are its):
  1. a wizard-mode NLE (actions = nethack.ACTIONS + WIZLEVELPORT Ctrl-V + WIZWISH Ctrl-W; the arena's observation keys
     and options plus the explicit role/race/gender/align options);
  2. the setup, before the agent sees anything: '#levelchange' to the XL (8 or 9 by seed parity: the arrivals' 7-9),
     Ctrl-W wishes for the kit (worn by letter), Ctrl-V 'castle' (do.c level_tele: a wizard's lev_by_name), then Ctrl-T
     to level (8,11) = castle map (0,8), the courtyard's west column on the drawbridge row. (teleport.c tele_jump_ok
     with the castle's TELEPORT_REGION exclusion box, level x 9..18: from outside it no teleport lands inside, so
     (8,11) is the nearest square the agent can be put on; it walks the last 3-4 squares to the shore itself, as the
     real arrivals do after their dig through the west maze.) Seeds re-roll the castle's garrison, towers and eels.
  3. hands the observation stream to the head's bot (engines/dag25/bot.py make_agent(): reset(obs), act(obs)),
     JF_SCENARIO castle_known (castle_logic.note_level marks the castle without the failed dig), JF_CFG per arm,
     answering 'Die?' with y itself so deaths are real, until the game ends or --max-turns pass after the hand-over;
     JF_LOG_DIR/JF_EPISODE make the engine write bot_<seed>.log beside the harness record.

Deviations from the pool's arrivals: full HP at the hand-over, no west-maze walk (its minotaurs), a wished (blessed)
kit with the flute identified only by appearance, no pet beyond the starting kitten/dog (it follows the levelport
when adjacent), the wizard-mode skill screens stripped (the hero never #enhances), fresh dungeon per seed (arms compare
UNPAIRED: the garrison is re-rolled per seed, but the same seed gives the same castle in every arm).

Metrics (per game, from the harness loop and the engine log): opened (turn), crusher toggles and kills ('PASSTUNE crush
n='), alive 300/600/1500 turns after the opening, reached the antechamber (map x 7..14, y 5..11), the hallway/throne
room (x >= 15, row 8 or the throne room box), a tower interior, a trap door/the Valley (Gehennom), a tower chest
(castle_treasury's 'CASTLE TREASURY' lines / FRONT M:chest), the killer.

Output: <out>/castle-front-<arm>[-s<i>of<n>].jsonl (one record per seed), .summary.json, logs-<arm>/bot_<seed>.log.
"""
from __future__ import annotations

import argparse
import json
import math
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

# the kit: the pool's castle arrivals (f2.4.0-passtune PASSTUNE start lines, castle_head.csv): long sword (Excalibur in
# ~1/3), +3 small shield, dwarvish iron helm, iron shoes, dwarvish mithril coat / banded mail, dwarvish cloak, a pick-axe
# or mattock, XL 7-9, max HP median ~84. Wishes as objnam.c readobjnam parses them; a flute reads 'a flute' until used.
# (the Valkyrie starts with the +1 long sword, the +3 small shield and a dagger: not wished for)
KIT = ['blessed +2 pick-axe', 'blessed +0 dwarvish iron helm', 'blessed +0 dwarvish mithril coat',
       'blessed +0 pair of iron shoes', 'blessed +0 dwarvish cloak', 'blessed wooden flute', 'blessed food ration']
ARMS = {
    'control': {},
    'v1': {'CASTLE_PASSTUNE': True},
    'v2': {'CASTLE_PASSTUNE': True, 'CASTLE_PASSTUNE_CRUSH': True},
}
COL0, ROW0 = 8, 3            # castle map (mx, my) = level (mx + COL0, my + ROW0) (castle_logic.to_map)
LANDING = (8, 11)            # level coordinates of map (0,8)
ANTE = frozenset((x, y) for x in range(7, 15) for y in range(5, 12))
THRONE = frozenset((x, y) for x in range(27, 38) for y in range(5, 12))
TOWERS = frozenset((x, y) for x in list(range(2, 7)) + list(range(56, 61)) for y in (2, 3, 13, 14))
GEHENNOM = 1

ROLE_WORDS = {'val': 'Valkyrie'}
RACE_WORDS = {'dwa': 'dwarf', 'hum': 'human'}
GENDER_WORDS = {'fem': 'female', 'mal': 'male'}
ALIGN_WORDS = {'law': 'lawful', 'neu': 'neutral', 'cha': 'chaotic'}


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


class WizCastle:
    """One wizard-mode game: the harness's setup keystrokes, then the bot's actions."""

    def __init__(self, seed: int, character: str = CHAR):
        from nle import nethack
        from nle.env.base import NLE
        from nle.nethack.actions import WizardCommand
        self.nh = nethack
        self.actions = tuple(nethack.ACTIONS) + (WizardCommand.WIZLEVELPORT, WizardCommand.WIZWISH)
        self.idx = {int(a): i for i, a in enumerate(self.actions)}
        self.LEVELPORT, self.WISH = len(nethack.ACTIONS), len(nethack.ACTIONS) + 1
        options = [o for o in nethack.NETHACKOPTIONS if o not in ('autopickup', '!autopickup')] + character_options(character)
        self.env = NLE(actions=self.actions, character=character, allow_all_yn_questions=True, allow_all_modes=True,
                       max_episode_steps=10_000_000, observation_keys=observation_keys(), wizard=True, options=options)
        self.env.seed(core=seed, disp=seed, reseed=False)
        self.obs = self.env.reset()
        if isinstance(self.obs, tuple):
            self.obs = self.obs[0]
        self.done = False
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
        return dict(x=int(b[0]), y=int(b[1]), depth=int(b[n.NLE_BL_DEPTH]), dnum=int(b[n.NLE_BL_DNUM]),
                    dlevel=int(b[n.NLE_BL_DLEVEL]), turn=int(b[n.NLE_BL_TIME]), hp=int(b[n.NLE_BL_HP]),
                    hpmax=int(b[n.NLE_BL_HPMAX]), xl=int(b[n.NLE_BL_XP]), ac=int(b[n.NLE_BL_AC]))

    def pos_map(self):
        b = self.bl()
        return (b['x'] - COL0, b['y'] - ROW0)

    def chars(self):
        return [bytes(r).decode('latin-1') for r in self.obs['chars']]

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
        weapon = any(w in text for w in ('pick-axe', 'mattock', 'sword', 'Excalibur', 'axe'))
        if 'pick-axe' in text or 'mattock' in text or 'flute' in text or 'ration' in text:
            return
        cmd = self.nh.Command.WIELD if weapon else self.nh.Command.WEAR
        self.press(self.idx[int(cmd)])
        if self.flags()[1] or 'What do you want to' in self.top():
            self.key(letter)
        self.clear_more()
        for _ in range(8):
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

    def castle_here(self):
        """The castle map's moat: '}' along map row 0 x 0..8 and the west moat column x 5 rows 5..11 (chars)."""
        ch = self.chars()
        pts = [(5, y) for y in range(5, 8)] + [(5, y) for y in range(9, 12)]   # seen from the courtyard
        hit = 0
        for mx, my in pts:
            x, y = mx + COL0, my + ROW0
            if 0 <= y < len(ch) and 0 <= x < len(ch[y]) and ch[y][x] == '}':
                hit += 1
        return hit, len(pts)

    def teleport_to(self, tx: int, ty: int) -> bool:
        """Wizard Ctrl-T: getpos moves (hjkl, HJKL by 8), '.' picks; 'Sorry...' = refused (a random jump follows)."""
        b = self.bl()
        dx, dy = tx - b['x'], ty - b['y']
        self.press(self.idx[20])   # Ctrl-T
        if 'Where do you want to be teleported' not in (self.message() + self.top()):
            self.clear_more()
            return False
        seq = ('L' * (abs(dx) // 8) + 'l' * (abs(dx) % 8)) if dx > 0 else ('H' * (abs(dx) // 8) + 'h' * (abs(dx) % 8))
        seq += ('J' * (abs(dy) // 8) + 'j' * (abs(dy) % 8)) if dy > 0 else ('K' * (abs(dy) // 8) + 'k' * (abs(dy) % 8))
        for ch in seq:
            self.key(ch)
        self.key('.')
        self.clear_more()
        b = self.bl()
        return (b['x'], b['y']) == (tx, ty)

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


# wizard-mode #enhance screens (valley_harness.py): every skill lettered over several pages, practice counters after the
# level -- character._parse_enhance_view asserts on both; letters stripped, '[Level]' restored
_SKILL_LINE = re.compile(r'\s+(Unskilled|Basic|Skilled|Expert|Master|Grand Master)\s+-?\d+\(\s*-?\d+\)\s*$')
_SKILL_LETTER = re.compile(r'^\s*[a-zA-Z] - ')


def _patch_wizard_screens():
    from pf_base import character  # type: ignore

    orig = character.Character._parse_enhance_view
    if getattr(orig, '_castle_harness', False):
        return

    def patched(self):
        lines = []
        for line in self.agent.popup:
            if _SKILL_LINE.search(line):
                line = _SKILL_LETTER.sub('', _SKILL_LINE.sub(r' [\1]', line))
            lines.append(line)
        self.agent.popup = lines
        return orig(self)

    patched._castle_harness = True
    character.Character._parse_enhance_view = patched


def killer_from_tty(game: WizCastle) -> str | None:
    text = '\n'.join(bytes(r).decode('latin-1') for r in game.obs['tty_chars'])
    m = re.search(r'(killed by [^\n.]*|poisoned by [^\n.]*|petrified by [^\n.]*|died of starvation|drowned[^\n.]*|'
                  r'crushed to death[^\n.]*|burned by [^\n.]*|dissolved in [^\n.]*|choked on [^\n.]*)', text)
    return m[1].strip() if m else None


_TURN = re.compile(r'\bt(\d+) ')


def read_engine_log(path: pathlib.Path) -> dict:
    """PASSTUNE / FRONT M: / CASTLE TREASURY lines of the engine's bot_<seed>.log."""
    out = dict(opened_turn=None, opened_play=None, tune_plays=0, crush_toggles=0, crush_killed=0, crush_done_turn=None,
               crush_kill_msgs=[], front_miles={}, treasury_lines=0, chest=False, unread_plays=0, bad_items=0,
               crusher_why=None, passtune_give_up=None, end_close=[], end_msg='', end_hp=None, crusher_waits=0)
    if not path.exists():
        return out
    for line in path.read_text(errors='replace').splitlines():
        mt = _TURN.search(line)
        turn = int(mt[1]) if mt else None
        if 'PASSTUNE ' in line:
            if 'PASSTUNE opened play=' in line:
                out['opened_turn'] = turn
                out['opened_play'] = int(re.search(r'play=(\d+)', line)[1])
            elif re.search(r'PASSTUNE play=\d+ tune=\w+ gears=', line):
                out['tune_plays'] += 1
            elif 'unread:' in line:
                out['unread_plays'] += 1
            elif 'gave no tune prompt' in line:
                out['bad_items'] += 1
            elif 'PASSTUNE crusher done' in line:
                out['crush_done_turn'] = turn
                m = re.search(r'toggles=(\d+) killed=(\d+)', line)
                out['crush_toggles'], out['crush_killed'] = int(m[1]), int(m[2])
                m = re.search(r'\((.*)\)\s*$', line)
                out['crusher_why'] = m[1] if m else None
            elif 'crusher: waiting' in line:
                out['crusher_waits'] += 1
            elif 'PASSTUNE crusher play=' in line:
                m = re.search(r'kills=(\d+) msg=(.*)$', line)
                if m and int(m[1]) > 0:
                    out['crush_kill_msgs'].append(m[2][:200])
            elif 'PASSTUNE giving up' in line:
                out['passtune_give_up'] = line.split('giving up:', 1)[1].strip()[:80]
        elif 'END msg ' in line:
            m = re.search(r"hp(\d+) close=\[(.*?)\] \| (.*)$", line)
            if m:
                out['end_hp'] = int(m[1])
                out['end_close'] = [c.strip(" '") for c in m[2].split(',') if c.strip(" '")]
                if m[3].strip():
                    out['end_msg'] = m[3].strip()[:200]
        elif 'FRONT M:' in line:
            name = re.search(r'FRONT M:(\w+)', line)[1]
            out['front_miles'].setdefault(name, turn)
            if name == 'chest':
                out['chest'] = True
        elif 'CASTLE TREASURY' in line:
            out['treasury_lines'] += 1
    return out


def run_one(seed: int, a) -> dict:
    t0 = time.time()
    random.seed(seed)
    xl = a.xl or (8 + seed % 2)
    out = dict(seed=seed, arm=a.arm, xl=xl)
    game = WizCastle(seed)
    try:
        game.set_xl(xl)
        letters = []
        for text in KIT + list(a.wish):
            letter = game.wish(text)
            letters.append((text, letter))
            if letter:
                game.equip(letter, text)
        out['wishes'] = letters
        if not game.levelport('castle'):
            out['error'] = f'level teleport to the castle refused: {game.bl()} top={game.top()!r}'
            return out
        placed = False
        for _ in range(4):
            if game.teleport_to(*LANDING):
                placed = True
                break
        out['placed_on_landing'] = placed
        hit, tot = game.castle_here()
        out['moat_seen'] = (hit, tot)
        if placed and hit < 4:
            out['error'] = f'not the castle after the levelport: moat {hit}/{tot} {game.bl()}'
            return out
        out['arrival'] = game.bl()
        out['arrival_pos_map'] = game.pos_map()
        out['setup_steps'] = game.setup_steps
        if a.setup_only:
            out['tty'] = [bytes(r).decode('latin-1').rstrip() for r in game.obs['tty_chars']][:24]
            return out
        castle_depth = game.bl()['depth']
        # ---- hand over
        os.environ['JF_EPISODE'] = str(seed)
        bot = load_bot(pathlib.Path(a.engine))
        try:   # jf_log opens bot_<JF_EPISODE>.log once per process: reopened per game, or every game lands in the first file
            from pf_base import jf_log  # type: ignore
            if jf_log._fh is not None:
                jf_log._fh.close()
            jf_log._fh = None
        except Exception:  # noqa: BLE001
            pass
        bot.reset(game.obs)
        start_turn = game.bl()['turn']
        steps = 0
        last_bl = game.bl()
        marks = dict(ante=None, hall=None, throne=None, tower=None, valley=None, east=None)
        max_x = -99
        min_hp = last_bl['hp']
        last_msgs = []
        try:
            while not game.done and steps < a.max_steps:
                if game.answer_die():
                    continue
                action = bot.act(game.obs)
                game.press(int(action))
                steps += 1
                m_ = game.message().strip()
                if m_ and (not last_msgs or last_msgs[-1] != m_):
                    last_msgs.append(m_[:160])
                    del last_msgs[:-8]
                if a.trace and steps >= a.trace:
                    print(f'  step {steps} act {game.actions[int(action)]!r} flags {game.flags()} msg {game.message()[:120]!r} '
                          f'top {game.top()[:100]!r} bl {game.bl()}', flush=True)
                if game.done:
                    break
                last_bl = b = game.bl()
                min_hp = min(min_hp, b['hp'])
                if b['dnum'] == GEHENNOM or b['depth'] > castle_depth:
                    marks['valley'] = marks['valley'] or b['turn']
                    break   # the Valley: banked (castle_landing is the valley harness's business)
                if b['depth'] == castle_depth and b['dnum'] == 0:
                    p = game.pos_map()
                    max_x = max(max_x, p[0])
                    if p in ANTE and marks['ante'] is None:
                        marks['ante'] = b['turn']
                    if p[0] >= 15 and 5 <= p[1] <= 11 and marks['hall'] is None:
                        marks['hall'] = b['turn']
                    if p in THRONE and marks['throne'] is None:
                        marks['throne'] = b['turn']
                    if p in TOWERS and marks['tower'] is None:
                        marks['tower'] = b['turn']
                    if p[0] >= 57 and marks['east'] is None:
                        marks['east'] = b['turn']
                if b['turn'] - start_turn > a.max_turns:
                    break
        finally:
            bot.close()
            died = game.done
            out['last_msgs'] = last_msgs
            out.update(steps=steps, start_turn=start_turn, end_turn=last_bl['turn'], turns=last_bl['turn'] - start_turn,
                       final=last_bl, died=died, killer=killer_from_tty(game) if died else None, marks=marks,
                       max_x=max_x, min_hp=min_hp)
    except Exception as e:  # noqa: BLE001
        out['crash'] = f'{type(e).__name__}: {str(e)[:300]}'
        out['traceback'] = traceback.format_exc(limit=8)[-2000:]
    finally:
        out['wall_s'] = round(time.time() - t0, 1)
        try:
            game.env.close()
        except Exception:  # noqa: BLE001
            pass
    log = read_engine_log(pathlib.Path(os.environ['JF_LOG_DIR']) / f'bot_{seed}.log')
    out['log'] = log
    if out.get('died') and not out.get('killer'):
        text = ' '.join(out.get('last_msgs', [])[-4:]) + ' ' + log['end_msg']
        hits = re.findall(r'The ([a-z][a-z \-]*?) (?:hits|bites|butts|kicks|stings|touches|engulfs|swings|thrusts|breathes|zaps|casts|'
                          r'hits you|drowns you|explodes)', text)
        if 'drown' in text:
            hits.append('drowned (eel)')
        out['killer'] = ('end: ' + (hits[-1] if hits else ', '.join(log['end_close'][:3]) or '?'))[:60]
    if log['opened_turn'] is not None and 'end_turn' in out:
        after = out['end_turn'] - log['opened_turn']
        out['turns_after_opening'] = after
        out['alive_300'] = (not out['died']) or after >= 300
        out['alive_600'] = (not out['died']) or after >= 600
        out['alive_1500'] = (not out['died']) or after >= 1500
    return out


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(p, 3), round(max(0.0, c - h), 3), round(min(1.0, c + h), 3))


def summarize(rows: list[dict], a) -> dict:
    ok = [r for r in rows if 'crash' not in r and 'error' not in r and 'turns' in r]
    n = len(ok)
    s = dict(arm=a.arm, seeds=len(rows), crashes=sum('crash' in r for r in rows), setup_errors=sum('error' in r for r in rows),
             n=n, placed_on_landing=sum(bool(r.get('placed_on_landing')) for r in ok))
    if not n:
        return s
    opened = [r for r in ok if r['log']['opened_turn'] is not None]
    s['opened'] = wilson(len(opened), n) + (len(opened), n)
    s['died'] = wilson(sum(r['died'] for r in ok), n)
    s['median_turns'] = statistics.median(r['turns'] for r in ok)
    s['alive_300_after_arrival'] = sum(r['turns'] >= 300 or not r['died'] for r in ok)
    s['alive_600_after_arrival'] = sum(r['turns'] >= 600 or not r['died'] for r in ok)
    s['alive_1500_after_arrival'] = sum(r['turns'] >= 1500 or not r['died'] for r in ok)
    s['tune_plays_median'] = statistics.median(r['log']['opened_play'] for r in opened) if opened else None
    s['unread_plays'] = sum(r['log']['unread_plays'] for r in ok)
    s['bad_items'] = sum(r['log']['bad_items'] for r in ok)
    if opened:
        no = len(opened)
        s['opened_n'] = no
        for key in ('alive_300', 'alive_600', 'alive_1500'):
            s[key + '_after_opening'] = wilson(sum(bool(r.get(key)) for r in opened), no) + (sum(bool(r.get(key)) for r in opened), no)
        s['crush_toggles_total'] = sum(r['log']['crush_toggles'] for r in opened)
        s['crush_killed_total'] = sum(r['log']['crush_killed'] for r in opened)
        s['crush_killed_per_opened_game'] = round(s['crush_killed_total'] / no, 2)
        s['crush_killed_hist'] = dict(Counter(r['log']['crush_killed'] for r in opened))
        s['crusher_why'] = dict(Counter(str(r['log']['crusher_why']) for r in opened))
        s['ante'] = wilson(sum(r['marks']['ante'] is not None for r in opened), no) + (sum(r['marks']['ante'] is not None for r in opened), no)
        s['hall'] = wilson(sum(r['marks']['hall'] is not None for r in opened), no) + (sum(r['marks']['hall'] is not None for r in opened), no)
        s['throne'] = sum(r['marks']['throne'] is not None for r in opened)
        s['tower'] = sum(r['marks']['tower'] is not None for r in opened)
        s['chest'] = sum(r['log']['chest'] or r['log']['treasury_lines'] > 0 for r in opened)
        s['valley_after_opening'] = sum(r['marks']['valley'] is not None for r in opened)
    s['valley'] = wilson(sum(r['marks']['valley'] is not None for r in ok), n) + (sum(r['marks']['valley'] is not None for r in ok), n)
    s['ante_any'] = sum(r['marks']['ante'] is not None for r in ok)
    s['killers'] = Counter(str(r.get('killer'))[:40] for r in ok if r.get('died')).most_common(15)
    return s


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--engine', default=str(DEFAULT_ENGINE))
    p.add_argument('--arm', choices=sorted(ARMS), default='v2')
    p.add_argument('--seeds', type=int, default=100)
    p.add_argument('--seed-base', type=int, default=1_000)
    p.add_argument('--shard', default='', help='i/n: run the seeds with (seed - base) %% n == i')
    p.add_argument('--probe', type=int, help='one seed, record printed')
    p.add_argument('--xl', type=int, default=0, help='0: 8 or 9 by seed parity')
    p.add_argument('--wish', action='append', default=[], help='extra wish text (repeatable)')
    p.add_argument('--max-turns', type=int, default=1500, help='game turns after the hand-over')
    p.add_argument('--max-steps', type=int, default=30_000)
    p.add_argument('--cfg', help='extra JF_CFG json merged over the arm\'s')
    p.add_argument('--tag', default='')
    p.add_argument('--out', default=str(HERE / 'out'))
    p.add_argument('--setup-only', action='store_true')
    p.add_argument('--trace', type=int, default=0, help='print every bot step from this step on (probe debugging)')
    a = p.parse_args()
    cfg = dict(ARMS[a.arm])
    if a.cfg:
        cfg.update(json.loads(a.cfg))
    tag = a.tag or a.arm
    out_dir = pathlib.Path(a.out).resolve(); out_dir.mkdir(parents=True, exist_ok=True)   # absolute: load_bot chdir()s
    os.environ['JF_LOG_DIR'] = str(out_dir / f'logs-{tag}')
    os.environ['JF_CFG'] = json.dumps(cfg)
    os.environ['JF_SCENARIO'] = json.dumps({'castle_known': True})
    if a.probe is not None:
        r = run_one(a.probe, a)
        print(json.dumps(r, indent=1, default=str))
        return 0
    seeds = [a.seed_base + i for i in range(a.seeds)]
    suffix = ''
    if a.shard:
        i, n = (int(v) for v in a.shard.split('/'))
        seeds = [sd for sd in seeds if (sd - a.seed_base) % n == i]
        suffix = f'-s{i}of{n}'
    fn = out_dir / f'castle-front-{tag}{suffix}.jsonl'
    rows = []
    with open(fn, 'w') as fh:
        for sd in seeds:
            r = run_one(sd, a)
            rows.append(r); fh.write(json.dumps(r, default=str) + '\n'); fh.flush()
            lg = r.get('log', {})
            status = r.get('error') or r.get('crash') or \
                f"turns {r.get('turns')} opened {lg.get('opened_turn')} crush k={lg.get('crush_killed')} " \
                f"ante {r.get('marks', {}).get('ante')} valley {r.get('marks', {}).get('valley')} killer {r.get('killer')} " \
                f"({r['wall_s']}s)"
            print(f"seed {sd}: {status}", flush=True)
    s = summarize(rows, a)
    (out_dir / f'castle-front-{tag}{suffix}.summary.json').write_text(json.dumps(s, indent=1, default=str))
    print(json.dumps(s, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
