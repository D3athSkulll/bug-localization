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
