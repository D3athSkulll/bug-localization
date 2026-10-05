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
