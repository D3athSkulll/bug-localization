"""Per-stage wall-clock timing of the pipeline (insertion-ordered)."""
import time
from collections import OrderedDict


class StageTimer(object):
    def __init__(self):
        self.stages = OrderedDict()
        self._t0 = time.perf_counter()

    def __call__(self, name):
        return _Stage(self, name)

    def add(self, name, seconds):
        self.stages[name] = self.stages.get(name, 0.0) + seconds

    def total(self):
        return sum(self.stages.values())

    def wall(self):
        return time.perf_counter() - self._t0

    def as_dict(self, digits=4):
        return OrderedDict((k, round(v, digits)) for k, v in self.stages.items())

    def table(self, notes=None):
        """Printable table: stage, seconds, share of the total, bar."""
        notes = notes or {}
        tot = self.total() or 1e-12
        lines = ["  %-34s %9s %7s  %s" % ("stage", "seconds", "share", "")]
        for k, v in self.stages.items():
            share = 100.0 * v / tot
            lines.append("  %-34s %9.4f %6.1f%%  %s%s" % (k, v, share, "#" * int(round(share / 2.5)),
                                                         ("  <- " + notes[k]) if k in notes else ""))
        lines.append("  %-34s %9.4f" % ("TOTAL (sum of stages)", tot))
        return "\n".join(lines)


class _Stage(object):
    def __init__(self, timer, name):
        self.timer, self.name = timer, name

    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.timer.add(self.name, time.perf_counter() - self.t)
        return False
