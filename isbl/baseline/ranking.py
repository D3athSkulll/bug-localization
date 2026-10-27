"""Statement ranking from suspiciousness scores."""
import bisect


def rank_statements(spectrum, formula, tie="worst"):
    """Returns ({statement: rank}, {statement: score}).
    tie='worst'   : rank = number of statements with score >= s    (pessimistic; default)
    tie='best'    : rank = 1 + number of statements with score > s (optimistic)
    tie='average' : mean of best and worst.
    The paper does not specify tie handling; this is a documented assumption."""
    scores = {s: formula(*v) for s, v in spectrum.items()}
    neg = sorted(-v for v in scores.values())
    ranks = {}
    for s, sc in scores.items():
        best = bisect.bisect_left(neg, -sc) + 1
        worst = bisect.bisect_right(neg, -sc)
        ranks[s] = {"worst": worst, "best": best, "average": (best + worst) / 2.0}[tie]
    return ranks, scores


def rank_keys(keys, tie="worst"):
    """Generic version for arbitrary comparable keys (float or tuple, larger = more suspicious); equal keys tie.
    Used for lexicographic tie-breaking, e.g. key = (sfl_score, ir_file_score, statement_text_score)."""
    vals = sorted(keys.values())
    n = len(vals)
    ranks = {}
    for s, k in keys.items():
        greater = n - bisect.bisect_right(vals, k)
        at_least = n - bisect.bisect_left(vals, k)
        best, worst = greater + 1, at_least
        ranks[s] = {"worst": worst, "best": best, "average": (best + worst) / 2.0}[tie]
    return ranks
