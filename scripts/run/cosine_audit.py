"""Cosine-similarity audit for the IR step.
(1) Correctness: our cosine vs scikit-learn and SciPy on the real Lang bugs (max absolute difference).
(2) Mathematical properties: bounds, symmetry, self-similarity, scale invariance, zero vector.
(3) Diagnosis: which terms produce the score of the buggy file and of the top-ranked file (raw term frequency vs idf).
Usage: python scripts/run/cosine_audit.py   (writes results/experiments/cosine_audit_*.csv)"""
import csv
import json
import math
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402
from scipy.spatial.distance import cosine as scipy_cosine  # noqa: E402
from sklearn.feature_extraction.text import CountVectorizer  # noqa: E402
from sklearn.metrics.pairwise import cosine_similarity  # noqa: E402

from isbl.baseline import ir, ir_models as M, pipeline  # noqa: E402
from isbl.baseline.answer_key import answer_key_from_patch  # noqa: E402

OUT = os.path.join(ROOT, "results", "experiments")
os.makedirs(OUT, exist_ok=True)
CFGS = {1: "configs/lang1_k50.json", 2: "configs/bugs/Lang-2.json", 3: "configs/bugs/Lang-3.json"}


def load(n):
    cfg = json.load(open(os.path.join(ROOT, CFGS[n])))
    files = pipeline.load_sources(os.path.join(ROOT, cfg["repo"], cfg["src_dir"]))
    q = pipeline.load_bug_report(os.path.join(ROOT, cfg["bug_report"]))
    key = answer_key_from_patch(open(os.path.join(ROOT, cfg["answer_key_patch"]), encoding="utf-8").read())
    return files, q, sorted({f for f, _ in key})


def contributions(qv, dv):
    """Per-term share of the cosine: (x_t * y_t) / (|x||y|)."""
    nq = math.sqrt(sum(v * v for v in qv.values()))
    nd = math.sqrt(sum(v * v for v in dv.values()))
    return {t: qv[t] * dv[t] / (nq * nd) for t in qv if t in dv} if nq and nd else {}


def main():
    prep = M.PAPER_PREP
    corr_rows, prop_rows, why_rows = [], [], []
    for n in (1, 2, 3):
        files, qtext, bug_files = load(n)
        ids = sorted(files)
        dt = [ir.preprocess_source_file(files[i], **prep) for i in ids]
        qt = ir.preprocess_bug_report(qtext, **prep)
        ours = np.array(M.tf_cosine(qt, dt))
        # ---- (1) reference implementations
        cv = CountVectorizer(analyzer=lambda toks: toks)
        X = cv.fit_transform(dt + [qt])
        sk = cosine_similarity(X[-1], X[:-1]).ravel()
        sp = np.array([1.0 - scipy_cosine(X[-1].toarray().ravel(), X[k].toarray().ravel()) if X[k].nnz else 0.0
                       for k in range(len(dt))])
        corr_rows.append({"bug": "Lang-%d" % n, "files": len(ids), "max_abs_diff_vs_sklearn": float(np.abs(ours - sk).max()),
                          "max_abs_diff_vs_scipy": float(np.abs(ours - sp).max()),
                          "ranking_identical_to_sklearn": bool(
                              [ids[k] for k in np.lexsort((np.array(ids), -np.round(sk, 12)))]
                              == [f for f, _ in sorted(zip(ids, ours), key=lambda x: (-round(x[1], 12), x[0]))])})
        # ---- (2) properties on the real vectors
        vecs = [dict(Counter(d)) for d in dt]
        qv = dict(Counter(qt))
        sym = max(abs(ir.cosine_similarity(v, qv) - ir.cosine_similarity(qv, v)) for v in vecs)
        scale = max(abs(ir.cosine_similarity(v, qv) - ir.cosine_similarity(v, {t: 7 * c for t, c in qv.items()}))
                    for v in vecs)
        prop_rows.append({"bug": "Lang-%d" % n, "min_cosine": float(ours.min()), "max_cosine": float(ours.max()),
                          "within_0_1": bool(ours.min() >= 0 and ours.max() <= 1 + 1e-12),
                          "self_similarity": ir.cosine_similarity(qv, qv), "max_asymmetry": sym,
                          "max_scale_change_x7_query": scale, "zero_vector_cosine": ir.cosine_similarity({}, qv)})
        # ---- (3) why: top contributing terms for the buggy file and the top-ranked file (tf vs tf-idf)
        order = sorted(range(len(ids)), key=lambda k: (-ours[k], ids[k]))
        top1 = order[0]
        buggy = [k for k in order if ids[k] in bug_files][0]
        df = Counter()
        for d in dt:
            df.update(set(d))
        N = len(dt)
        for role, k in (("top-1 file", top1), ("buggy file", buggy)):
            c = contributions(qv, vecs[k])
            tot = sum(c.values())
            top = sorted(c.items(), key=lambda x: -x[1])[:5]
            common = sum(v for t, v in c.items() if df[t] / float(N) > 0.5)
            why_rows.append({"bug": "Lang-%d" % n, "role": role, "file": ids[k], "ir_rank": order.index(k) + 1,
                             "cosine": round(float(ours[k]), 4), "doc_tokens": len(dt[k]),
                             "query_terms_matched": len(c), "query_terms_total": len(qv),
                             "share_from_terms_in_>50%_of_files": round(common / tot, 3) if tot else 0,
                             "top_terms (share of cosine)": "; ".join("%s=%.0f%%" % (t, 100 * v / tot) for t, v in top)})
    for name, rows in (("correctness", corr_rows), ("properties", prop_rows), ("why", why_rows)):
        path = os.path.join(OUT, "cosine_audit_%s.csv" % name)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print("== (1) our cosine vs scikit-learn / SciPy (raw term-frequency vectors, paper preprocessing)")
    for r in corr_rows:
        print("  %s: files=%d  max|diff| sklearn=%.2e scipy=%.2e  same ranking=%s" % (
            r["bug"], r["files"], r["max_abs_diff_vs_sklearn"], r["max_abs_diff_vs_scipy"], r["ranking_identical_to_sklearn"]))
    print("== (2) properties")
    for r in prop_rows:
        print("  %s: cosine in [%.4f, %.4f] within[0,1]=%s self=%.1f asym=%.1e scale-x7 change=%.1e zero-vector=%.1f" % (
            r["bug"], r["min_cosine"], r["max_cosine"], r["within_0_1"], r["self_similarity"], r["max_asymmetry"],
            r["max_scale_change_x7_query"], r["zero_vector_cosine"]))
    print("== (3) why the files score as they do (raw term frequency)")
    for r in why_rows:
        print("  %s %-10s rank %-3d %-45s cos=%.4f tokens=%-6d matched %d/%d terms, %.0f%% of score from terms found in >50%% of files"
              % (r["bug"], r["role"], r["ir_rank"], r["file"].split("/")[-1], r["cosine"], r["doc_tokens"],
                 r["query_terms_matched"], r["query_terms_total"], 100 * r["share_from_terms_in_>50%_of_files"]))
        print("        top terms: " + r["top_terms (share of cosine)"])


if __name__ == "__main__":
    main()
