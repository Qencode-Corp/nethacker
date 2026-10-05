#!/usr/bin/env python3
"""Summarise valley_harness.py arms (P37): per arm n, Dlvl 40, left the Valley, alive 25, median turns, killers (from
the engine log's END block: the last 'close' monsters and the hit verbs, since the tombstone is not on the tty), and the
switch-firing counts from the engine logs. Wilson 95% intervals. Usage: python valley_harness_summary.py out ctrl lot ..."""
import glob
import json
import math
import os
import re
import statistics
import sys
from collections import Counter

HIT = re.compile(r"(?:The |[A-Z][a-z]*'s )([a-z][a-z' -]*?)(?: ghost)? (?:hits|bites|touches you|stings|kicks|butts|"
                 r"claws|engulfs you|misses|just misses|swings wildly)")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(k, n):
    lo, hi = wilson(k, n)
    return f'{k}/{n} = {100 * k / n:.0f}% [{100 * lo:.0f}, {100 * hi:.0f}]' if n else '-'


def games(out, tag):
    """The arm's engine log split per game: jf_log keeps one file handle per process, so every game of an arm appends
    to logs-<tag>/bot_<first seed>.log; the adapter's TRAJ line at reset starts each game (in seed order)."""
    text = ''
    for fn in sorted(glob.glob(os.path.join(out, f'logs-{tag}', 'bot_*.log'))):
        text += open(fn, errors='replace').read()
    parts = re.split(r'(?m)^(?=\[s0 t0 d0 0:0 xl0 hp0/0\] TRAJ fp=)', text)
    return [p for p in parts if 'TRAJ fp=' in p]


def killer(game):
    """The monster named by the last melee message in the END block, else the last 'close' list."""
    lines = [l for l in game.splitlines() if ' END msg ' in l]
    if not lines:
        return 'no END block'
    names = Counter()
    close = None
    for l in lines[-8:]:
        m = re.search(r"close=\[(.*?)\]", l)
        if m and m.group(1):
            close = [s.strip("' ") for s in m.group(1).split(',')]
        msg = l.split('|', 1)[-1]
        for h in HIT.finditer(msg):
            names[h.group(1).strip()] += 1
    if names:
        return names.most_common(1)[0][0]
    return close[0] if close else 'unknown'


def main(out, tags):
    print('| arm | n | Dlvl 40 | left the Valley | alive 25 | median turns | top killers |')
    print('|---|---|---|---|---|---|---|')
    fires = {}
    for tag in tags:
        fn = os.path.join(out, f'valley-harness-{tag}.jsonl')
        rows = [json.loads(l) for l in open(fn)]
        ok = [r for r in rows if 'crash' not in r and 'error' not in r and r.get('max_depth') is not None]
        n = len(ok)
        t = [r['turns_after_landing'] for r in ok]
        base = 'deep_arrival' if ok and ok[0].get('deep_arrival') else 'valley_arrival'
        left = sum(r['max_depth'] > r[base]['depth'] for r in ok)
        r40 = sum(r['max_depth'] >= 40 for r in ok)
        a25 = sum(x > 25 for x in t)
        ks = Counter()
        logs = games(out, tag)
        for i, r in enumerate(rows):
            if r in ok and r.get('died'):
                ks[killer(logs[i]) if i < len(logs) else 'no log'] += 1
        top = ', '.join(f'{k} {v}' for k, v in ks.most_common(5))
        print(f"| {tag} | {n} ({len(rows) - n} bad) | {pct(r40, n)} | {pct(left, n)} | {pct(a25, n)} | "
              f"{statistics.median(t) if t else '-'} | {top} |")
        c = Counter()
        for s in logs:
            c['lottery reads'] += s.count('LOTTERY read ->')
            c['games with a lottery read'] += 'LOTTERY read ->' in s
            c['retreat strikes'] += s.count('VALLEY retreat: striking') + s.count('VALLEY retreat: hitting')
            c['next-tile panics'] += s.count('Monster on a next tile')
            c['explore caps'] += s.count('VALLEY explore capped')
            c['rest caps'] += s.count('VALLEY rest capped')
            c['hallu holds'] += s.count('task valley: wait out hallucination')
            c['rest before digging'] += s.count('task rest before digging')
            c['door HP holds'] += s.count('door HP hold at')
            c['climbs to the castle'] += s.count(' up to the castle at hp')
            c['returns by the trap door'] += s.count('fell through a trap door')
            c['games with progress toward the >'] += 'VALLEY progress' in s
            c['secret doors broken'] += s.count('break through a secret door')
            c['games down the Valley stairs'] += 'VALLEY down the stairs' in s
            c['DRIVER restarts'] += s.count('DRIVER restart')
        fires[tag] = c
    print('\nswitch firings per arm (engine logs):')
    for tag, c in fires.items():
        print(f'- {tag}: ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
