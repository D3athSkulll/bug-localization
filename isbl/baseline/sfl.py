"""Spectrum-based fault localisation formulas. A spectrum entry is (ef, ep, nf, np):
ef/ep = failing/passing tests that execute the statement, nf/np = failing/passing tests that do not."""
import math


def ochiai(ef, ep, nf, np_=0):
    denom = math.sqrt((ef + nf) * (ef + ep))
    return ef / denom if denom > 0 else 0.0


def dstar(ef, ep, nf, np_=0, star=2):
    denom = ep + nf
    if denom == 0:
        return float("inf") if ef > 0 else 0.0
    return (ef ** star) / denom


FORMULAS = {"ochiai": ochiai, "dstar": dstar}


# ---- additional spectrum formulas (families surveyed by Wong et al., arXiv 1607.04347; Zou et al., arXiv 1803.09939)
def _div(a, b):
    return a / b if b else 0.0


def tarantula(ef, ep, nf, np_=0):
    f, p = _div(ef, ef + nf), _div(ep, ep + np_)
    return _div(f, f + p)


def jaccard(ef, ep, nf, np_=0):
    return _div(ef, ef + nf + ep)


def sorensen_dice(ef, ep, nf, np_=0):
    return _div(2.0 * ef, 2.0 * ef + nf + ep)


def kulczynski2(ef, ep, nf, np_=0):
    return 0.5 * (_div(ef, ef + nf) + _div(ef, ef + ep))


def op2(ef, ep, nf, np_=0):
    return ef - ep / (ep + np_ + 1.0)


def barinel(ef, ep, nf, np_=0):
    return 1.0 - _div(ep, ep + ef) if (ep + ef) else 0.0


def wong2(ef, ep, nf, np_=0):
    return float(ef - ep)


def dstar3(ef, ep, nf, np_=0):
    return dstar(ef, ep, nf, np_, star=3)


def ochiai2(ef, ep, nf, np_=0):
    return _div(ef * np_, math.sqrt((ef + ep) * (nf + np_) * (ef + nf) * (ep + np_)) or 0.0)


FORMULAS.update({"tarantula": tarantula, "jaccard": jaccard, "sorensen_dice": sorensen_dice,
                 "kulczynski2": kulczynski2, "op2": op2, "barinel": barinel, "wong2": wong2, "dstar3": dstar3,
                 "ochiai2": ochiai2})
