"""Extra diagnostics beyond TOP@N/MRR, to separate IR failure from SFL failure and to show where ties and
spectrum size hurt. All functions are pure and unit-tested."""
import math


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def ir_diagnostics(ranked, bug_files, n_kept):
    """ranked: [(file, cosine)] best first. Metrics about the IR stage only."""
    n = len(ranked)
    scores = [s for _, s in ranked]
    pos = [s for s in scores if s > 0]
    tot = sum(pos)
    entropy = -sum((s / tot) * math.log(s / tot, 2) for s in pos) if tot > 0 else 0.0
    bug_pos = [i + 1 for i, (f, _) in enumerate(ranked) if f in bug_files]
    rank = min(bug_pos) if bug_pos else None
    return {
        "ir_num_files": n,
        "ir_buggy_file_rank": rank,
        "ir_buggy_file_rank_percentile": (rank / float(n)) if rank else None,   # = minimum k that keeps the buggy file
        "ir_buggy_file_cosine": scores[rank - 1] if rank else None,
        "ir_top1_cosine": scores[0] if n else None,
        "ir_score_gap_top1_top2": (scores[0] - scores[1]) if n > 1 else None,
        "ir_score_entropy_bits": entropy,                                       # high = unconfident (adaptive-k signal)
        "ir_files_with_nonzero_cosine": len(pos),
        "ir_buggy_file_recall_at_k": 1.0 if (rank is not None and rank <= n_kept) else 0.0,
        "ir_files_kept": n_kept,
        "ir_files_dropped": n - n_kept,
    }


def spectrum_diagnostics(tests, spec):
    """tests: [(name, passed, {file: set(lines)})]; spec: {(file,line): (ef,ep,nf,np)}."""
    n_t, n_s = len(tests), len(spec)
    nz = sum(len(l) for _, _, c in tests for l in c.values())
    return {
        "sp_num_tests": n_t,
        "sp_num_failed_tests": sum(1 for _, ok, _ in tests if not ok),
        "sp_num_statements": n_s,
        "sp_matrix_cells": n_t * n_s,
        "sp_matrix_density": (nz / float(n_t * n_s)) if n_t and n_s else 0.0,
        "sp_avg_statements_per_test": (nz / float(n_t)) if n_t else 0.0,
        "sp_avg_tests_per_statement": (nz / float(n_s)) if n_s else 0.0,
    }


def reduction_diagnostics(full_tests, red_tests, full_spec, red_spec):
    return {
        "red_statements_removed": len(full_spec) - len(red_spec),
        "red_statements_removed_pct": 100.0 * (len(full_spec) - len(red_spec)) / len(full_spec) if full_spec else 0.0,
        "red_tests_removed": len(full_tests) - len(red_tests),
        "red_tests_removed_pct": 100.0 * (len(full_tests) - len(red_tests)) / len(full_tests) if full_tests else 0.0,
    }


def localization_diagnostics(spec, scores, ranks, bug_stmts):
    """scores/ranks: dicts statement -> value for ONE tie rule. Describes how hard the final ranking is."""
    n = len(spec)
    in_spec = [s for s in bug_stmts if s in spec]
    brank = [ranks[s] for s in in_spec]
    best = min(in_spec, key=lambda s: ranks[s]) if in_spec else None
    top = max(scores.values()) if scores else 0.0
    tie = [s for s in scores if best is not None and scores[s] == scores[best]]
    best_rank = ranks[best] if best else None
    return {
        "loc_num_buggy_statements": len(bug_stmts),
        "loc_num_buggy_in_spectrum": len(in_spec),
        "loc_best_buggy_rank": best_rank,
        "loc_best_buggy_score": scores[best] if best else None,
        "loc_top_score": top,
        "loc_best_buggy_score_over_top": (scores[best] / top) if best and top not in (0, float("inf")) else None,
        "loc_mean_buggy_rank": (sum(brank) / len(brank)) if brank else None,
        "loc_median_buggy_rank": _median(brank),
        "loc_exam_score": (best_rank / float(n)) if best and n else None,      # fraction of statements inspected
        "loc_wasted_effort": (best_rank - 1) if best else None,                 # statements inspected before the bug
        "loc_distinct_scores": len(set(scores.values())),
        "loc_statements_with_score_gt0": sum(1 for v in scores.values() if v > 0),
        "loc_tie_group_size": len(tie) if best else None,                       # statements sharing the buggy line's score
        "loc_buggy_in_tie_group": sum(1 for s in tie if s in bug_stmts) if best else None,
    }
