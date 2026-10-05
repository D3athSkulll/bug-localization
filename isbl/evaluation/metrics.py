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
