"""Evaluation metrics. A bug's rank is the rank of its best-ranked buggy statement; None if no buggy
statement is in the ranking (e.g. the buggy file was excluded by top-k)."""


def bug_rank(ranks, buggy_statements):
    found = [ranks[s] for s in buggy_statements if s in ranks]
    return min(found) if found else None


def top_n(bug_ranks, n):
    """Number of bugs whose rank is <= n."""
    return sum(1 for r in bug_ranks if r is not None and r <= n)


def mrr(bug_ranks):
    if not bug_ranks:
        return 0.0
    return sum(1.0 / r for r in bug_ranks if r is not None) / len(bug_ranks)


def file_recall_at_k(suspicious_files, buggy_files):
    return 1.0 if set(buggy_files) & set(suspicious_files) else 0.0


# ---- additional metrics (MAP, nDCG, recall/precision@k, EXAM, wasted effort, bootstrap CI, win/draw/lose).
# Definitions follow the IR-based bug-localisation and SBFL literature (see docs/literature.md).
import math as _math


def all_ranks(ranks, buggy_statements):
    """Sorted ranks of EVERY buggy statement that appears in the ranking (None-free)."""
    return sorted(ranks[s] for s in buggy_statements if s in ranks)


def average_precision(rel_ranks):
    """AP over the relevant items' ranks (1-based): mean of (i / rank_i). 0 if nothing is ranked."""
    r = sorted(rel_ranks)
    return sum((i + 1) / float(x) for i, x in enumerate(r)) / len(r) if r else 0.0


def ap_over_all_relevant(rel_ranks, n_relevant):
    """AP where unranked relevant items count as 0 (n_relevant = size of the answer key)."""
    r = sorted(rel_ranks)
    return sum((i + 1) / float(x) for i, x in enumerate(r)) / n_relevant if n_relevant else 0.0


def ndcg_at_k(rel_ranks, k, n_relevant):
    dcg = sum(1.0 / _math.log(x + 1, 2) for x in rel_ranks if x <= k)
    ideal = sum(1.0 / _math.log(i + 2, 2) for i in range(min(n_relevant, k)))
    return dcg / ideal if ideal else 0.0


def recall_at_k(rel_ranks, k, n_relevant):
    return sum(1 for x in rel_ranks if x <= k) / float(n_relevant) if n_relevant else 0.0


def precision_at_k(rel_ranks, k):
    return sum(1 for x in rel_ranks if x <= k) / float(k) if k else 0.0


def exam_score(rank, n_items):
    """Share of the ranked list a developer reads before the first buggy item (lower is better)."""
    return (rank / float(n_items)) if (rank is not None and n_items) else None


def win_draw_lose(ranks_a, ranks_b):
    """Per-bug comparison of method A against B by rank (lower is better; None = not found = worst)."""
    inf = float("inf")
    w = d = l = 0
    for a, b in zip(ranks_a, ranks_b):
        a, b = (inf if a is None else a), (inf if b is None else b)
        if a < b:
            w += 1
        elif a == b:
            d += 1
        else:
            l += 1
    return w, d, l


def bootstrap_ci(values, n_boot=2000, seed=0, alpha=0.05):
    """Percentile bootstrap CI of the mean. With very few bugs the interval is wide and not informative."""
    import random
    vals = [v for v in values if v is not None]
    if not vals:
        return None, None
    rnd = random.Random(seed)
    means = sorted(sum(rnd.choice(vals) for _ in vals) / float(len(vals)) for _ in range(n_boot))
    return means[int(n_boot * alpha / 2)], means[int(n_boot * (1 - alpha / 2)) - 1]


def wilcoxon_p(a, b):
    """Two-sided Wilcoxon signed-rank p-value of paired values, or None (scipy missing / all differences zero)."""
    try:
        from scipy.stats import wilcoxon
        if all(x == y for x, y in zip(a, b)):
            return None
        return float(wilcoxon(a, b).pvalue)
    except Exception:                                    # noqa: BLE001
        return None
