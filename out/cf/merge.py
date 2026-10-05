"""Merge the castle_front_harness shards per arm and print the read (Wilson 95% intervals)."""
import glob
import json
import math
import statistics
import sys
from collections import Counter

HERE = sys.argv[1] if len(sys.argv) > 1 else '.'


def wilson(k, n, z=1.96):
    if n == 0:
        return '0/0'
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f'{k}/{n} = {100 * p:.0f}% [{100 * max(0, c - h):.0f}, {100 * min(1, c + h):.0f}]'


for arm in ('control', 'v1', 'v2'):
    rows = []
    for fn in sorted(glob.glob(f'{HERE}/castle-front-{arm}-s*.jsonl')):
        rows += [json.loads(l) for l in open(fn)]
    ok = [r for r in rows if 'crash' not in r and 'error' not in r and 'turns' in r]
    n = len(ok)
    print(f'\n=== {arm}: {len(rows)} seeds, {n} ok, crashes {sum("crash" in r for r in rows)}, setup errors {sum("error" in r for r in rows)}, '
          f'placed {sum(bool(r.get("placed_on_landing")) for r in ok)}')
    opened = [r for r in ok if r['log']['opened_turn'] is not None]
    print(' opened          ', wilson(len(opened), n), '; plays to open median', statistics.median(r['log']['opened_play'] for r in opened) if opened else '-',
          '; unread plays', sum(r['log']['unread_plays'] for r in ok), '; bad items', sum(r['log']['bad_items'] for r in ok),
          '; passtune give-ups', Counter(str(r['log']['passtune_give_up'])[:40] for r in ok if r['log']['passtune_give_up']).most_common(4))
    print(' died            ', wilson(sum(r['died'] for r in ok), n), '; turns after hand-over median', statistics.median(r['turns'] for r in ok))
    for t in (300, 600, 1500):
        print(f' alive {t:>4} after hand-over', wilson(sum((not r['died']) or r['turns'] >= t for r in ok), n))
    if opened:
        no = len(opened)
        for t in (300, 600, 1500):
            print(f' alive {t:>4} after opening  ', wilson(sum(bool(r.get(f'alive_{t}')) for r in opened), no))
        print(' turns after opening median', statistics.median(r['turns_after_opening'] for r in opened),
              'min', min(r['turns_after_opening'] for r in opened), 'max', max(r['turns_after_opening'] for r in opened))
        kills = [r['log']['crush_killed'] for r in opened]
        print(' crusher: toggles', sum(r['log']['crush_toggles'] for r in opened), 'killed', sum(kills), 'per opened game', round(sum(kills) / no, 2),
              'hist', dict(sorted(Counter(kills).items())), 'why', Counter(str(r['log']['crusher_why'])[:45] for r in opened).most_common(6))
        print(' crusher waits', sum(r['log']['crusher_waits'] for r in opened))
        print(' antechamber     ', wilson(sum(r['marks']['ante'] is not None for r in opened), no),
              '| hallway/throne', wilson(sum(r['marks']['hall'] is not None for r in opened), no),
              '| throne', sum(r['marks']['throne'] is not None for r in opened),
              '| tower', sum(r['marks']['tower'] is not None for r in opened),
              '| chest', sum(r['log']['chest'] or r['log']['treasury_lines'] > 0 for r in opened),
              '| Valley', sum(r['marks']['valley'] is not None for r in opened))
        print(' FRONT milestones', Counter(m for r in opened for m in r['log']['front_miles']).most_common(12))
    print(' Valley (all)    ', wilson(sum(r['marks']['valley'] is not None for r in ok), n), '| antechamber (all)', sum(r['marks']['ante'] is not None for r in ok))
    print(' killers (all)   ', Counter(str(r.get('killer'))[:40] for r in ok if r.get('died')).most_common(12))
    if opened:
        print(' killers (opened)', Counter(str(r.get('killer'))[:40] for r in opened if r.get('died')).most_common(12))
    msgs = [m for r in opened for m in r['log']['crush_kill_msgs']]
    if msgs:
        print(' crush messages (sample)')
        for m in msgs[:4]:
            print('   ', m[:200])
