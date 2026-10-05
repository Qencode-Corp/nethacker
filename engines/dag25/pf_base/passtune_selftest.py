"""Brute-force check of passtune.PasstuneSolver: every one of the 7^5 tunes, the feedback computed by a literal port of
music.c do_play_instrument (3.6.6, lines ~800-830), the solver's guess sequence walked as a decision tree (the solver is
deterministic, so one node per distinct feedback history). Prints the worst and mean number of plays and asserts <= 7.

  python3 -m engines.dag25.pf_base.passtune_selftest      (or run the file from its directory)"""

import itertools
import os
import sys
import time

if __package__:
    from . import passtune
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import passtune


def music_c_feedback(buf, tune):
    """music.c, verbatim in Python: matched[] shared by gears and tumblers, a tumbler never takes a tune position
    that is itself an exact match (buf[y] != tune[y])."""
    tumblers = gears = 0
    matched = [False] * 5
    for x in range(len(buf)):
        if x < 5:
            if buf[x] == tune[x]:
                gears += 1
                matched[x] = True
            else:
                for y in range(5):
                    if not matched[y] and buf[x] == tune[y] and buf[y] != tune[y]:
                        tumblers += 1
                        matched[y] = True
                        break
    return gears, tumblers


def main():
    tunes = [''.join(p) for p in itertools.product(passtune.NOTES, repeat=passtune.LENGTH)]
    assert len(tunes) == 16807
    # the solver's own count equals music.c's on every pair of a sample
    import random
    rng = random.Random(1)
    for _ in range(20000):
        a, b = rng.choice(tunes), rng.choice(tunes)
        assert passtune.feedback(a, b) == music_c_feedback(a, b), (a, b)
    # the vectorised count too
    import numpy as np
    codes, counts = passtune._tables()
    for g in rng.sample(tunes, 30):
        fb = passtune._feedback_all(passtune.to_vec(g), codes, counts)
        for i in rng.sample(range(len(tunes)), 200):
            ge, tu = music_c_feedback(g, tunes[i])
            assert fb[i] == ge * 6 + tu, (g, tunes[i])

    t0 = time.time()
    plays = {}
    worst_examples = []

    def walk(solver, secrets):
        guess = solver.next_guess()
        n = solver.guesses + 1
        groups = {}
        for s in secrets:
            fb = music_c_feedback(guess, s)
            if fb == (5, 0):
                plays[s] = n
            else:
                groups.setdefault(fb, []).append(s)
        for fb, group in groups.items():
            child = solver.clone()
            child.feedback(*fb)
            assert child.candidates == len(group), (guess, fb, child.candidates, len(group))
            walk(child, group)

    sys.setrecursionlimit(10000)
    walk(passtune.PasstuneSolver(), tunes)
    assert len(plays) == len(tunes)
    worst = max(plays.values())
    mean = sum(plays.values()) / len(plays)
    hist = {k: sum(1 for v in plays.values() if v == k) for k in range(1, worst + 1)}
    worst_examples = [s for s, v in plays.items() if v == worst][:5]
    print(f'passtune solver: {len(tunes)} tunes, opener {passtune.OPENER}, max {worst} plays, mean {mean:.3f}, '
          f'histogram {hist}, {time.time() - t0:.1f}s; worst e.g. {worst_examples}')
    assert worst <= 7, worst
    # the message parser
    assert passtune.parse_feedback('You hear 2 tumblers click and 1 gear turn.') == (1, 2)
    assert passtune.parse_feedback('You hear 1 tumbler click.') == (0, 1)
    assert passtune.parse_feedback('You hear 3 gears turn.') == (3, 0)
    assert passtune.parse_feedback('You extract a strange sound from the flute!') is None
    assert passtune.parse_feedback('You hear chains rattling and gears turning.') is None
    assert passtune.is_instrument('a wooden flute') and passtune.is_instrument('an uncursed horn') and \
        passtune.is_instrument('a bugle') and passtune.is_instrument('a magic harp (0:5)') and \
        passtune.is_instrument('a frost horn (0:3)')
    assert not passtune.is_instrument('a unicorn horn') and not passtune.is_instrument('a horn of plenty (0:12)') and \
        not passtune.is_instrument('a leather drum') and not passtune.is_instrument('a tin whistle')
    print('parse_feedback / is_instrument ok')


if __name__ == '__main__':
    main()
