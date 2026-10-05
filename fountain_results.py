#!/usr/bin/env python3
"""The fountain harness read (P37): merge the arm files (ctrl + ctrl2, quaff + quaff2), recover killers from the engine's END
block (the death screen's tty is past the message by the time the harness reads it), and print the per-arm table with Wilson
intervals and the decision arithmetic.

  ~/jev-nethack-frontier/.venv/bin/python fountain_results.py --out out --arms ctrl,ctrl2 quaff,quaff2
"""
import argparse
import json
import math
import pathlib
import re
import statistics
from collections import Counter

_CLOSE = re.compile(r"close=\[([^\]]*)\]")
_KILL = re.compile(r"(killed by [^.|]*|poisoned by [^.|]*|petrified by [^.|]*|died of starvation|drowned[^.|]*|choked on [^.|]*|"
                   r"burned by [^.|]*|dissolved in [^.|]*|turned to slime[^.|]*)")


def killer_from_log(path: pathlib.Path) -> str:
    """The END block (jf instruments): the last 'killed by' message, else the monsters next to us on the last steps."""
    if not path.exists():
        return 'unknown (no log)'
    end = [l for l in path.read_text(errors='replace').splitlines() if ' END msg ' in l]
    text = ' | '.join(end[-30:])
    m = _KILL.findall(text)
    if m:
        return m[-1].strip()
    close = Counter()
    for l in end[-12:]:
        c = _CLOSE.search(l)
        if c and c[1].strip():
            for name in re.findall(r"'([^']*)'", c[1]):
                close[name] += 1
    if close:
        return 'near: ' + ', '.join(n for n, _ in close.most_common(2))
    if any('You faint' in l or 'starv' in l for l in end[-30:]):
        return 'starvation'
    return 'unknown'


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, c - h, c + h)


def fmt(w):
    return f'{100 * w[0]:.1f}% [{100 * w[1]:.1f}, {100 * w[2]:.1f}]'


def load(out: pathlib.Path, tags):
    rows = []
    for tag in tags:
        for line in (out / f'fountain-harness-{tag}.jsonl').read_text().splitlines():
            r = json.loads(line)
            r['_tag'] = tag
            rows.append(r)
    ok = [r for r in rows if 'crash' not in r and 'error' not in r and r.get('max_depth') is not None]
    for r in ok:
        if r.get('died') and not r.get('killer'):
            r['killer'] = killer_from_log(out / f'logs-{r["_tag"]}' / f'bot_{r["seed"]}.log')
    return rows, ok


def arm_stats(rows, ok):
    n = len(ok)
    ev = Counter()
    ge = Counter()
    for r in ok:
        ev.update(r.get('events', {}))
        ge.update(r.get('game_events', {}))
    died = [r for r in ok if r.get('died')]
    wished = [r for r in ok if r.get('wishes', 0) > 0]
    wished_tc = [r for r in wished if r.get('tc_known') or r.get('tc_ring_learned')]
    quaffs = sum(r.get('quaffs', 0) for r in ok)
    s = dict(
        seeds=len(rows), no_fountain=sum(bool(r.get('no_fountain')) for r in rows), crashes=sum('crash' in r for r in rows), n=n,
        quaffs=quaffs, quaffs_per_game=quaffs / n if n else 0, fountains_quaffed=sum(r.get('fountains_quaffed', 0) for r in ok),
        games_quaffing=sum(r.get('quaffs', 0) > 0 for r in ok),
        wishes=sum(r.get('wishes', 0) for r in ok), wish_games=len(wished), wish_games_w=wilson(len(wished), n),
        wish_texts=Counter(t for r in ok for t in r.get('wish_texts', [])),
        wish_then_tc=len(wished_tc), wish_then_tc_w=wilson(len(wished_tc), len(wished)) if wished else None,
        demons=ev.get('demon', 0), hostile_demons=ev.get('demon', 0) - ev.get('wish', 0),
        demon_deaths=sum('water demon' in str(r.get('killer')) for r in died),
        nymphs=ev.get('nymph', 0), curses=ev.get('curse', 0), poison=ev.get('poison', 0), moccasins=ev.get('moccasin', 0),
        dry=ev.get('dry', 0), gush=ev.get('gush', 0), foul=ev.get('foul', 0), events=dict(ev), game_events=dict(ge),
        deaths=len(died), death_w=wilson(len(died), n),
        killers=Counter(str(r.get('killer'))[:40] for r in died).most_common(12),
        reached_stop=sum(bool(r.get('reached_stop')) for r in ok), reached_stop_w=wilson(sum(bool(r.get('reached_stop')) for r in ok), n),
        turns_mean=statistics.mean(r['turns'] for r in ok) if ok else 0,
        max_depth_mean=statistics.mean(r['max_depth'] for r in ok) if ok else 0,
        str_final_mean=statistics.mean(r['final']['str_'] for r in ok) if ok else 0,
        xl_final_mean=statistics.mean(r['final']['xl'] for r in ok) if ok else 0,
    )
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='out')
    p.add_argument('--arms', nargs='+', default=['ctrl,ctrl2', 'quaff,quaff2'])
    p.add_argument('--wish-value', type=float, default=0.35, help='progression a converted wish is worth')
    p.add_argument('--death-cost', type=float, default=0.40, help='progression lost by a death at this depth')
    p.add_argument('--fountains-per-game', type=float, default=3.77)
    a = p.parse_args()
    out = pathlib.Path(a.out)
    stats = {}
    for arm in a.arms:
        tags = arm.split(',')
        rows, ok = load(out, tags)
        stats[tags[0]] = arm_stats(rows, ok)
    keys = list(stats)
    print(f'{"metric":34s}' + ''.join(f'{k:>34s}' for k in keys))
    for name, f in [
        ('seeds run', lambda s: str(s['seeds'])), ('no fountain on Dlvl 3 (skipped)', lambda s: str(s['no_fountain'])),
        ('games (n)', lambda s: str(s['n'])), ('crashes', lambda s: str(s['crashes'])),
        ('quaffs', lambda s: str(s['quaffs'])), ('quaffs per game', lambda s: f"{s['quaffs_per_game']:.2f}"),
        ('fountains quaffed', lambda s: str(s['fountains_quaffed'])), ('games that quaffed', lambda s: str(s['games_quaffing'])),
        ('quaffs per fountain quaffed', lambda s: f"{s['quaffs'] / s['fountains_quaffed']:.2f}" if s['fountains_quaffed'] else '-'),
        ('fountains dried', lambda s: str(s['dry'])),
        ('wishes', lambda s: str(s['wishes'])), ('wish games (Wilson)', lambda s: f"{s['wish_games']} = {fmt(s['wish_games_w'])}"),
        ('wish texts', lambda s: ', '.join(f'{k}:{v}' for k, v in s['wish_texts'].items()) or '-'),
        ('wish -> TC ring known', lambda s: f"{s['wish_then_tc']}/{s['wish_games']}" + (f" = {fmt(s['wish_then_tc_w'])}" if s['wish_then_tc_w'] else '')),
        ('water demons (engine log)', lambda s: str(s['demons'])), ('hostile demons (engine log)', lambda s: str(s['hostile_demons'])),
        ('game msgs: demons / wishes', lambda s: f"{s['game_events'].get('demon', 0)} / {s['game_events'].get('wish', 0)}"),
        ('game msgs: nymphs / stolen', lambda s: f"{s['game_events'].get('nymph', 0)} / {s['game_events'].get('stolen', 0)}"),
        ('game msgs: moccasins / curses', lambda s: f"{s['game_events'].get('moccasin', 0)} / {s['game_events'].get('curse', 0)}"),
        ('game msgs: contaminated / dried', lambda s: f"{s['game_events'].get('poison', 0)} / {s['game_events'].get('dry', 0)}"),
        ('game msgs: Excalibur made', lambda s: str(s['game_events'].get('excalibur', 0))),
        ('demon deaths', lambda s: str(s['demon_deaths'])),
        ('nymphs', lambda s: str(s['nymphs'])), ('moccasin events', lambda s: str(s['moccasins'])),
        ('curse events', lambda s: str(s['curses'])), ('contaminated (Str loss)', lambda s: str(s['poison'])),
        ('foul water', lambda s: str(s['foul'])), ('gushes', lambda s: str(s['gush'])),
        ('deaths (Wilson)', lambda s: f"{s['deaths']} = {fmt(s['death_w'])}"),
        ('reached Dlvl 12 (Wilson)', lambda s: f"{s['reached_stop']} = {fmt(s['reached_stop_w'])}"),
        ('turns mean', lambda s: f"{s['turns_mean']:.0f}"), ('max depth mean', lambda s: f"{s['max_depth_mean']:.2f}"),
        ('final XL mean', lambda s: f"{s['xl_final_mean']:.2f}"), ('final Str mean', lambda s: f"{s['str_final_mean']:.2f}"),
    ]:
        print(f'{name:34s}' + ''.join(f'{f(stats[k]):>34s}' for k in keys))
    for k in keys:
        print(f'\nkillers {k}: {stats[k]["killers"]}')
        print(f'events {k}: {stats[k]["events"]}')
        print(f'game events {k}: {stats[k]["game_events"]}')
    if len(keys) == 2:
        c, q = stats[keys[0]], stats[keys[1]]
        print('\n--- decision arithmetic (points = progression x 100 on the 4,000-seed bench) ---')
        wpg_harness = q['wishes'] / q['n'] if q['n'] else 0
        fpg_harness = q['fountains_quaffed'] / q['n'] if q['n'] else 0
        wpf = q['wishes'] / q['fountains_quaffed'] if q['fountains_quaffed'] else 0
        print(f'harness: wishes per game {wpg_harness:.4f}, fountains quaffed per game {fpg_harness:.3f}, wishes per fountain quaffed {wpf:.4f}')
        print(f'source:  wishes per fountain at Dlvl 3 = 2.5 x (1/30) x 0.17 = {2.5 / 30 * 0.17:.4f}')
        for label, wpf_used in (('harness rate', wpf), ('source rate (Dlvl 3)', 2.5 / 30 * 0.17), ('source rate (Dlvl 5)', 2.5 / 30 * 0.15)):
            gain = a.fountains_per_game * wpf_used * a.wish_value * 100
            dd = q['death_w'][0] - c['death_w'][0]
            cost = dd * a.death_cost * 100 * (a.fountains_per_game / max(fpg_harness, 1e-9)) if fpg_harness else float('nan')
            print(f'{label:22s}: gain = {a.fountains_per_game} fountains x {wpf_used:.4f} x {a.wish_value} x 100 = {gain:+.2f} pts; '
                  f'death rate diff {100 * dd:+.2f} pp per {fpg_harness:.2f} fountains -> x {a.death_cost} x 100 scaled to {a.fountains_per_game} fountains = {-cost:+.2f} pts; '
                  f'net {gain - cost:+.2f} pts (bar +0.5)')
        print(f'death-rate difference Wilson (quaff - ctrl): {100 * (q["death_w"][0] - c["death_w"][0]):+.2f} pp; '
              f'ctrl {fmt(c["death_w"])}, quaff {fmt(q["death_w"])}')


if __name__ == '__main__':
    main()
