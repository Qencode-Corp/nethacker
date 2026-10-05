"""CASTLE_PASSTUNE: the castle drawbridge's passtune found by Mastermind with any musical instrument.

NetHack 3.6.6 music.c do_play_instrument (lines ~700-830): applying an instrument that plays notes asks 'Improvise?'
('n'), then getlin 'What tune are you playing? [5 notes, A-G]'. On the castle level (Is_stronghold) with the drawbridge
span or its portcullis wall among the 8 squares around us, a wrong tune is answered like Mastermind unless we are Deaf:
gears = notes right and in place, tumblers = right notes out of place (each tune position matched at most once, exact
matches excluded first -- the standard Mastermind count, see `feedback`). 'You hear N tumbler(s) click and M gear(s)
turn.' / 'You hear N tumbler(s) click.' / 'You hear N gear(s) turn.'; nothing at all for 0/0. The right tune
(dbridge.c open_drawbridge: 'You see a drawbridge coming down!') opens the bridge -- or closes it when it is down.
Instruments that play notes: wooden/magic flute, tooled/frost/fire horn, bugle, wooden/magic harp (unidentified
'flute', 'horn', 'harp'; a bugle has no description). Drums, whistles, a horn of plenty (apply.c) and a unicorn horn
do not. 7 notes, 5 positions, repeats allowed: 7^5 = 16,807 tunes.

The solver keeps the consistent candidates and, after a fixed opener, plays the guess with the smallest expected
remaining class (sum of squared class sizes) over a pool of every candidate plus EXTRA_POOL non-candidates drawn by a
seeded RNG (a candidate wins ties: it can be the tune). passtune_selftest.py plays every tune against a literal port
of the music.c count: max 7 plays, mean 5.16 (2026-10-04; candidates-only minimax needed 8 for 3 tunes)."""

import re

import numpy as np

NOTES = 'ABCDEFG'
LENGTH = 5
OPENER = 'ABCAB'
EXTRA_POOL = 100   # non-candidate guesses scored beside the candidates at each node

_codes = None     # (16807, 5) note indices
_counts = None    # (16807, 7) per-note counts


def _tables():
    global _codes, _counts
    if _codes is None:
        n = len(NOTES)
        idx = np.arange(n ** LENGTH)
        cols = [(idx // n ** (LENGTH - 1 - i)) % n for i in range(LENGTH)]
        _codes = np.stack(cols, axis=1).astype(np.int8)
        _counts = np.stack([(_codes == c).sum(axis=1) for c in range(n)], axis=1).astype(np.int8)
    return _codes, _counts


def to_vec(tune):
    return np.array([NOTES.index(c) for c in tune.upper()], dtype=np.int8)


def to_tune(vec):
    return ''.join(NOTES[int(c)] for c in vec)


def feedback(guess, tune):
    """(gears, tumblers) of one guess against one tune, both 5-letter strings: the Mastermind count music.c makes."""
    g, t = guess.upper(), tune.upper()
    gears = sum(1 for a, b in zip(g, t) if a == b)
    common = sum(min(g.count(c), t.count(c)) for c in NOTES)
    return gears, common - gears


def _feedback_all(gvec, cands, ccounts):
    """Feedback class id (gears * 6 + tumblers) of guess gvec against every candidate row."""
    gears = (cands == gvec).sum(axis=1)
    gcount = np.bincount(gvec, minlength=len(NOTES)).astype(np.int8)
    common = np.minimum(ccounts, gcount).sum(axis=1)
    return gears * 6 + (common - gears)


class PasstuneSolver:
    """solver = PasstuneSolver(); guess = solver.next_guess(); solver.feedback(gears, tumblers); ..."""

    def __init__(self):
        codes, counts = _tables()
        self._cands = codes
        self._counts = counts
        self._last = None
        self.guesses = 0
        self.history = []

    @property
    def candidates(self):
        return len(self._cands)

    def clone(self):
        other = PasstuneSolver.__new__(PasstuneSolver)
        other._cands, other._counts, other._last = self._cands, self._counts, self._last
        other.guesses, other.history = self.guesses, list(self.history)
        return other

    def next_guess(self):
        if self._last is not None:
            return to_tune(self._last)
        if self.guesses == 0:
            best = to_vec(OPENER)
        elif len(self._cands) <= 2:
            best = self._cands[0]
        else:
            codes, _ = _tables()
            rng = np.random.RandomState(self.guesses * 7919 + len(self._cands))   # deterministic per node
            pool = [(row, 1) for row in self._cands] + \
                [(codes[i], 0) for i in rng.choice(len(codes), EXTRA_POOL, replace=False)]
            best = None
            best_key = None
            for row, is_cand in pool:
                classes = np.bincount(_feedback_all(row, self._cands, self._counts), minlength=36)
                key = (float((classes * classes).sum()) - is_cand, int(classes.max()))
                if best_key is None or key < best_key:
                    best_key = key
                    best = row
        self._last = np.array(best, dtype=np.int8)
        return to_tune(self._last)

    def feedback(self, gears, tumblers):
        """Narrow the candidates by the game's answer to the last guess."""
        if self._last is None:
            raise ValueError('feedback before a guess')
        fb = _feedback_all(self._last, self._cands, self._counts)
        keep = fb == gears * 6 + tumblers
        self._cands = self._cands[keep]
        self._counts = self._counts[keep]
        self.history.append((to_tune(self._last), int(gears), int(tumblers)))
        self.guesses += 1
        self._last = None

    def solved(self):
        return len(self._cands) == 1

    def exhausted(self):
        return len(self._cands) == 0


_TUMBLERS = re.compile(r'(\d+) tumblers? click')
_GEARS = re.compile(r'(\d+) gears? turn\b')


def parse_feedback(message):
    """(gears, tumblers) from the game's Mastermind line(s), or None when the message holds none."""
    if not message:
        return None
    t = _TUMBLERS.search(message)
    g = _GEARS.search(message)
    if t is None and g is None:
        return None
    return (int(g.group(1)) if g else 0), (int(t.group(1)) if t else 0)


_INSTRUMENT = re.compile(r'\b(flute|harp|bugle|horn)\b')
_NOT_INSTRUMENT = ('unicorn horn', 'horn of plenty', 'horned')


def is_instrument(item_text):
    """An inventory line naming something that plays notes (identified or by appearance)."""
    s = (item_text or '').lower()
    if any(w in s for w in _NOT_INSTRUMENT):
        return False
    return _INSTRUMENT.search(s) is not None
