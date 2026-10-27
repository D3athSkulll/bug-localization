"""Hybrid ranking: combine the spectrum (SFL) score of a statement with information from the bug report.

Why: the spectrum alone cannot separate statements that have identical (ef, ep, nf, np) - on Lang-1 six lines tie
and no SFL formula can split them. The bug report is independent information that can:
  * file score  F(s): IR score of the statement's file (min-max normalised over all files);
  * text score  T(s): idf-weighted overlap between the statement's own tokens and the bug-report tokens.
Modes (key = what is sorted, larger is more suspicious; equal keys tie):
  sfl            S                               plain SFL (or ISBL, if the spectrum was reduced)
  tie_file       (S, F)                          F only breaks exact ties of S
  tie_text       (S, T)                          T only breaks exact ties of S
  tie_file_text  (S, F, T)
  linear         (1-a-b)*S~ + a*F~ + b*T~        S~, F~, T~ min-max normalised inside the ranked spectrum
  mult           S~ * (1 + a*F~)
Nothing here uses the answer key, the fixed version or tests that are not in the spectrum. This is OUR exploratory
extension, not part of the ISBL paper; its parameters are fixed in advance, not tuned on the evaluation bugs."""
import math
from collections import Counter

from isbl.baseline import ir


def finite(scores):
    """Replace +inf (DStar with zero denominator) by one more than the largest finite score."""
    fin = [v for v in scores.values() if v != float("inf")]
    top = (max(fin) if fin else 0.0) + 1.0
    return {s: (top if v == float("inf") else v) for s, v in scores.items()}


def minmax(scores):
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    return {s: (0.0 if hi == lo else (v - lo) / (hi - lo)) for s, v in scores.items()}


def file_score_map(ranked):
    """[(file, score)] -> {file: score min-max normalised over all files}."""
    if not ranked:
        return {}
    sc = [v for _, v in ranked]
    lo, hi = min(sc), max(sc)
    return {f: (0.0 if hi == lo else (v - lo) / (hi - lo)) for f, v in ranked}


def statement_text_scores(statements, files, query_text, prep):
    """T(s) = sum of idf(t) over the distinct tokens t shared by the statement's source line and the bug report.
    idf is computed over the project's files with the same preprocessing."""
    opts = {k: v for k, v in (prep or {}).items() if k in ("split_identifiers", "remove_keywords", "remove_stopwords",
                                                           "stem", "drop_license")}
    docs = {f: set(ir.preprocess_source_file(t, **opts)) for f, t in files.items()}
    n = len(docs)
    df = Counter()
    for d in docs.values():
        df.update(d)
    idf = {t: math.log(1.0 + n / float(c)) for t, c in df.items()}
    q = set(ir.preprocess_bug_report(query_text, **opts))
    lines = {f: t.splitlines() for f, t in files.items()}
    out = {}
    for f, ln in statements:
        src = lines.get(f, [])
        text = src[ln - 1] if 0 < ln <= len(src) else ""
        toks = set(ir.preprocess_source_file(text, **opts))
        out[(f, ln)] = sum(idf.get(t, 0.0) for t in toks & q)
    return out


def keys_for(mode, sfl_scores, file_scores_by_file, text_scores, a=0.3, b=0.0):
    """Sort keys for the chosen mode. sfl_scores may contain +inf (handled)."""
    S = finite(sfl_scores)
    F = {s: file_scores_by_file.get(s[0], 0.0) for s in S}
    T = text_scores or {s: 0.0 for s in S}
    if mode == "sfl":
        return dict(S)
    if mode == "tie_file":
        return {s: (S[s], F[s]) for s in S}
    if mode == "tie_text":
        return {s: (S[s], T[s]) for s in S}
    if mode == "tie_file_text":
        return {s: (S[s], F[s], T[s]) for s in S}
    Sn, Fn, Tn = minmax(S), minmax(F), minmax(T)
    if mode == "linear":
        return {s: (1 - a - b) * Sn[s] + a * Fn[s] + b * Tn[s] for s in S}
    if mode == "mult":
        return {s: Sn[s] * (1.0 + a * Fn[s]) for s in S}
    raise ValueError("unknown hybrid mode: %s" % mode)
