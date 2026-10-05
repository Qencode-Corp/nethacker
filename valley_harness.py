#!/usr/bin/env python3
"""The Valley harness (P37, 2026-10-04): the head's dag25 agent dropped into the Valley of the Dead in a wizard-mode NLE
game on the Mac, with a castle-passage kit, run to death or Dlvl 45, logging. Diagnostics only: never the bench.

  ~/jev-nethack-frontier/.venv/bin/python valley_harness.py --engine ~/jev-nethack-frontier/wt/p37-valley/engines/dag25 \
        --seeds 20 --xl 8 --kit median [--deep 40] [--cfg '{"VALLEY_LOTTERY": false}'] [--tag ctrl] [--setup-only] [--probe 7]

Why (valley_landing_read.csv, the head's 4,000 cloud games): 39 games reach the Valley by the castle passage, 0 reach Dlvl 40,
21 die within 25 turns of landing (15 xorns), 4 lottery-teleport themselves UP to Dlvl 3-18 and die re-digging; the 78
wish-and-teleport games skip the Valley and 39 of them (50%) bank Dlvl 44-50. A bench-4000 sees ~39 Valley landings per
hour of pool time; this harness makes ~1 per minute on the Mac, with the kit and XL of the passage games.

How (tools/dlvl_harness.py did the same for the scaffold engine; the keystrokes are its):
  1. a wizard-mode NLE (nle.env.base.NLE(wizard=True), actions = nethack.ACTIONS + WIZLEVELPORT (Ctrl-V) + WIZWISH (Ctrl-W):
     the bot's action indices into nethack.ACTIONS stay valid, the two wizard keys sit at the end), the arena's options
     (nethack.NETHACKOPTIONS minus autopickup, environment.py disable_autopickup) plus the explicit role/race/gender/align
     options (playmode:debug renames the player 'wizard' and loses the character suffix: oracle_bench.character_options);
  2. the harness drives the setup itself, before the agent sees anything: '#levelchange' to the XL, Ctrl-W wishes for the kit
     (worn/wielded by letter from the wish message), Ctrl-V and 'valley' at 'To what level do you want to teleport?'
     (do.c level_tele: a wizard's lev_by_name sets force_dest; a plain depth past the castle lands in the Valley too through
     find_hell(), so '60' is the fallback) -- and with --deep N a second Ctrl-V from the Valley to Gehennom depth N, the
     dig control arm (the teleport games' landing);
  3. hands the observation stream to the head's bot (engines/dag25/bot.py make_agent(): reset(obs), act(obs) -> index into
     nethack.ACTIONS, the arena's contract in nethackers/arena/sandbox.py), answering 'Die?' with y itself so deaths are real,
     until the game ends, Dlvl --stop is reached, or --max-turns pass after the landing; JF_LOG_DIR/JF_EPISODE make the
     engine write its own bot_<seed>.log beside the harness record (jf_log.py).

Deviations from the passage games (read them off valley_landing_read.csv before trusting a number): the hero lands at turn ~5
with full HP (the passage games land at a median 69% HP, 14/39 under 60%: their landing fight is partly the castle's back-door
fight carried over), unhungry, with a fresh dungeon (wizard mode re-rolls it from frame 0: E13, arms compare UNPAIRED),
without the castle level's Elbereth/prayer history, and with a wished kit (blessed, identified) instead of the mixed one.

Output: <out>/valley-harness-<tag>.jsonl (one record per seed), .summary.json, and the engine's bot_<seed>.log files.
"""
from __future__ import annotations

import argparse
import json
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

# --- the kit (valley_landing_read.csv, 39 passage arrivals): pick-axe 25, mattock 5, wand of digging 9 (8 with a pick);
# helm 29, shield 27, long sword 20 (Excalibur 13), cloak 15, mithril 11; AC median -3 (range -9..10); XL median 8 (7-9 for 33
# of 39); max HP median 84. Wishes are typed as NetHack parses them (objnam.c readobjnam); artifacts may be refused
# (rn2(nartifact_exist()+... ) -- Excalibur is wished for last so a refusal costs nothing else.
KITS = {
    'median': ['blessed +2 pick-axe', 'blessed +0 dwarvish iron helm', 'blessed +3 small shield', 'blessed +1 long sword',
               'blessed +2 dwarvish mithril coat'],
    'rich': ['blessed +2 pick-axe', 'blessed wand of digging', 'blessed +0 dwarvish iron helm', 'blessed +3 small shield',
             'blessed +2 dwarvish mithril coat', 'blessed +1 elven cloak', 'blessed +3 Excalibur'],
    'mattock': ['blessed +2 dwarvish mattock', 'blessed +0 dwarvish iron helm', 'blessed +2 dwarvish mithril coat'],
    'none': [],
}

ROLE_WORDS = {'val': 'Valkyrie'}
RACE_WORDS = {'dwa': 'dwarf', 'hum': 'human'}
GENDER_WORDS = {'fem': 'female', 'mal': 'male'}
ALIGN_WORDS = {'law': 'lawful', 'neu': 'neutral', 'cha': 'chaotic'}
GEHENNOM = 1


def character_options(character: str) -> list[str]:
    role, race, align, gender = character.split('-')
    return [f'role:{ROLE_WORDS[role]}', f'race:{RACE_WORDS[race]}', f'gender:{GENDER_WORDS[gender]}', f'align:{ALIGN_WORDS[align]}']


def observation_keys():
    """The arena's observation keys (what the bot was written against); the NLE default set is the fallback."""
    try:
        if DEFAULT_PKG not in sys.path:
            sys.path.insert(0, DEFAULT_PKG)
        from nethackers.arena.environment import PUBLIC_OBSERVATION_KEYS  # type: ignore
        return tuple(PUBLIC_OBSERVATION_KEYS)
    except Exception:  # noqa: BLE001
        return ('glyphs', 'chars', 'colors', 'specials', 'blstats', 'message', 'inv_glyphs', 'inv_strs', 'inv_letters',
                'inv_oclasses', 'screen_descriptions', 'tty_chars', 'tty_colors', 'tty_cursor', 'misc')


class WizValley:
    """One wizard-mode game: the harness's setup keystrokes, then the bot's actions."""

    def __init__(self, seed: int, character: str = CHAR, verbose: bool = False):
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
        if isinstance(self.obs, tuple):   # gymnasium-style (obs, info)
            self.obs = self.obs[0]
        self.done = False
        self.verbose = verbose
        self.setup_steps = 0

    # ---- raw keystrokes (setup only)
    def press(self, index: int):
        if self.done:
            return   # the game is over: NLE raises on any further step ('Called step on finished NetHack')
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
        return bool(misc[0]), bool(misc[1]), bool(misc[2])   # in_yn, in_getlin, waiting for --More--

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
        self.press(self.idx[int(self.nh.MiscAction.MORE)])   # Enter

    def bl(self):
        b = self.obs['blstats']
        n = self.nh
        return dict(depth=int(b[n.NLE_BL_DEPTH]), dnum=int(b[n.NLE_BL_DNUM]), dlevel=int(b[n.NLE_BL_DLEVEL]), turn=int(b[n.NLE_BL_TIME]),
                    hp=int(b[n.NLE_BL_HP]), hpmax=int(b[n.NLE_BL_HPMAX]), xl=int(b[n.NLE_BL_XP]), ac=int(b[n.NLE_BL_AC]))

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
        """Ctrl-W, the text; returns the inventory letter the item landed on ('a - a blessed +2 pick-axe.')."""
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
        """Wear armour / wield a weapon by letter (the agent's own wear logic never runs inside the dig-dive)."""
        weapon = any(w in text for w in ('pick-axe', 'mattock', 'sword', 'Excalibur', 'axe'))
        cmd = self.nh.Command.WIELD if weapon else self.nh.Command.WEAR
        if 'pick-axe' in text or 'mattock' in text:
            return   # the agent applies the pick itself (dig_with_tool wields it); a wielded pick would block Excalibur
        self.press(self.idx[int(cmd)])
        if self.flags()[1] or 'What do you want to' in self.top():
            self.key(letter)
        self.clear_more()
        for _ in range(6):   # multi-turn armour donning
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

    def to_valley(self) -> bool:
        if self.levelport('valley') and self.bl()['dnum'] == GEHENNOM:
            return True
        return self.levelport('60') and self.bl()['dnum'] == GEHENNOM

    def answer_die(self) -> bool:
        """Wizard mode asks 'Die? [yn] (n)': yes, so the death is real (and the bot never sees the prompt)."""
        if self.flags()[0] and 'Die?' in self.top():
            self.key('y')
            self.clear_more()
            return True
        return False


def load_bot(engine: pathlib.Path):
    """engines/dag25/bot.py make_agent(): the arena chdir()s into the solution and imports `bot` (sandbox._load_agent)."""
    engine = engine.resolve()
    os.chdir(engine)
    if str(engine) not in sys.path:
        sys.path.insert(0, str(engine))
    import importlib
    bot_module = importlib.import_module('bot')
    _patch_wizard_screens()
    return bot_module.make_agent()


# wizard-mode screen differences the engine's parsers were never written against (harness-side wrappers, no engine edit):
#   #enhance (weapon.c skill_advance menu): in wizard mode each line reads 'a -  bare handed combat Unskilled  0(  20)'
#   -- no brackets round the level, practice counters after it -- and pf_base/character.py:_parse_enhance_view asserts on it
#   (the first probe, seed 7: 25 DRIVER restarts at t4, the agent never acted). Rewritten here to 'bare handed combat [Unskilled]'.
#   Second difference (probe 2): wizard mode gives EVERY skill a menu letter over several pages (letters repeat), where a
#   normal game letters only the advanceable ones -- character.py:523 asserts on the repeat, and had it not, the agent would
#   have enhanced every skill (wizard mode allows it). The letters are stripped: the harness hero never advances a skill
#   (a deviation: the passage games' Valkyries are XL 7-9 with their skills already spent; Valley runs are a few hundred turns).
_SKILL_LINE = re.compile(r'\s+(Unskilled|Basic|Skilled|Expert|Master|Grand Master)\s+-?\d+\(\s*-?\d+\)\s*$')
_SKILL_LETTER = re.compile(r'^\s*[a-zA-Z] - ')


def _patch_wizard_screens():
    from pf_base import character  # type: ignore

    orig = character.Character._parse_enhance_view
    if getattr(orig, '_valley_harness', False):
        return

    def patched(self):
        lines = []
        for line in self.agent.popup:
            if _SKILL_LINE.search(line):
                line = _SKILL_LETTER.sub('', _SKILL_LINE.sub(r' [\1]', line))
            lines.append(line)
        self.agent.popup = lines
        return orig(self)

    patched._valley_harness = True
    character.Character._parse_enhance_view = patched


def killer_from_tty(game: WizValley) -> str | None:
    text = '\n'.join(bytes(r).decode('latin-1') for r in game.obs['tty_chars'])
    m = re.search(r'(killed by [^\n.]*|poisoned by [^\n.]*|petrified by [^\n.]*|died of starvation|drowned[^\n.]*)', text)
    return m[1].strip() if m else None


def run_one(seed: int, a) -> dict:
    t0 = time.time()
    random.seed(seed)
    out = dict(seed=seed, tag=a.tag, kit=a.kit, xl=a.xl, deep=a.deep)
    game = WizValley(seed, verbose=a.verbose)
    try:
        game.set_xl(a.xl)
        letters = []
        for text in KITS[a.kit] + list(a.wish):
            letter = game.wish(text)
            letters.append((text, letter))
            if letter:
                game.equip(letter, text)
        out['wishes'] = letters
        if not game.to_valley():
            out['error'] = f'level teleport did not reach Gehennom: {game.bl()} top={game.top()!r}'
            return out
        out['valley_arrival'] = game.bl()
        if a.deep:
            if not game.levelport(str(a.deep)):
                out['error'] = f'deep teleport to {a.deep} refused: {game.top()!r}'
                return out
            out['deep_arrival'] = game.bl()
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
        try:
            while not game.done and steps < a.max_steps:
                if game.answer_die():
                    continue
                action = bot.act(game.obs)
                game.press(int(action))
                steps += 1
                if game.done:
                    break   # the death observation: blstats are the last live ones
                last_bl = b = game.bl()
                max_depth = max(max_depth, b['depth'])
                if b['depth'] >= a.stop or b['turn'] - landing_turn > a.max_turns:
                    break
        finally:
            bot.close()
            out.update(steps=steps, turns_after_landing=last_bl['turn'] - landing_turn, max_depth=max_depth, final=last_bl,
                       died=game.done, killer=killer_from_tty(game) if game.done else None, reached_stop=max_depth >= a.stop)
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


def summarize(rows: list[dict], a) -> dict:
    ok = [r for r in rows if 'crash' not in r and 'error' not in r and r.get('max_depth') is not None]
    s = dict(tag=a.tag, kit=a.kit, xl=a.xl, deep=a.deep, seeds=len(rows), crashes=sum('crash' in r for r in rows),
             setup_errors=sum('error' in r for r in rows), n=len(ok))
    if ok:
        t = [r['turns_after_landing'] for r in ok]
        s.update(median_turns_after_landing=statistics.median(t), alive_25=sum(x > 25 for x in t), alive_200=sum(x > 200 for x in t),
                 left_valley=sum(1 for r in ok if r['max_depth'] > r['valley_arrival']['depth']),
                 reached_30=sum(r['max_depth'] >= 30 for r in ok), reached_40=sum(r['max_depth'] >= 40 for r in ok),
                 reached_stop=sum(r.get('reached_stop', False) for r in ok),
                 killers=Counter(str(r.get('killer'))[:30] for r in ok if r.get('died')).most_common(10))
    return s


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--engine', default=str(DEFAULT_ENGINE))
    p.add_argument('--seeds', type=int, default=20)
    p.add_argument('--seed-base', type=int, default=1_000)
    p.add_argument('--probe', type=int, help='one seed, verbose, record printed')
    p.add_argument('--xl', type=int, default=8)
    p.add_argument('--kit', choices=sorted(KITS), default='median')
    p.add_argument('--wish', action='append', default=[], help='extra wish text (repeatable)')
    p.add_argument('--deep', type=int, default=0, help='dig control arm: a second Ctrl-V from the Valley to this Gehennom depth')
    p.add_argument('--stop', type=int, default=45, help='stop once this Dlvl is reached')
    p.add_argument('--max-turns', type=int, default=3000, help='game turns after the landing')
    p.add_argument('--max-steps', type=int, default=60_000)
    p.add_argument('--cfg', help='JF_CFG json for the engine (dev switch overrides, jf_config.py)')
    p.add_argument('--tag', default='')
    p.add_argument('--out', default=str(HERE / 'out'))
    p.add_argument('--setup-only', action='store_true', help='stop after the landing; print the screen (the keystroke check)')
    p.add_argument('--verbose', action='store_true')
    a = p.parse_args()
    a.tag = a.tag or f"{a.kit}-xl{a.xl}{'-deep' + str(a.deep) if a.deep else ''}"
    out_dir = pathlib.Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    os.environ['JF_LOG_DIR'] = str(out_dir / f'logs-{a.tag}')
    if a.cfg:
        os.environ['JF_CFG'] = a.cfg
    if a.probe is not None:
        a.verbose = True
        r = run_one(a.probe, a)
        print(json.dumps(r, indent=1, default=str))
        return 0
    fn = out_dir / f'valley-harness-{a.tag}.jsonl'
    rows = []
    with open(fn, 'w') as fh:
        for i in range(a.seeds):
            r = run_one(a.seed_base + i, a)   # one process: the engine's module state (numba cache, pf_base globals) is per process;
            rows.append(r); fh.write(json.dumps(r, default=str) + '\n'); fh.flush()   # a ProcessPoolExecutor is the next step
            status = r.get('error') or r.get('crash') or \
                f"depth {r.get('max_depth')} turns {r.get('turns_after_landing')} killer {r.get('killer')}"
            print(f"seed {r['seed']}: {status}", flush=True)
    s = summarize(rows, a)
    (out_dir / f'valley-harness-{a.tag}.summary.json').write_text(json.dumps(s, indent=1, default=str))
    print(json.dumps(s, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
