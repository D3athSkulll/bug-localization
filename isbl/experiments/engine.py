"""Experiment engine: compare IR models, SFL formulas, ISBL filtering and hybrid ranking on cached coverage.

Coverage (the slow part) is collected once per bug by scripts/bugs/prepare_lang_bug.py; everything here is fast
and deterministic. Two result tables:
  file level       how well each IR configuration ranks the buggy FILE (Top@N, MRR, MAP, nDCG, recall@k%)
  statement level  how well each full method (SFL alone / ISBL with an IR configuration / hybrid) ranks the buggy
                   STATEMENTS (TOP@N, MRR, MAP, nDCG, EXAM, wasted effort ...), tie rules worst / average / best
No IR/hybrid parameter is tuned on these bugs: every configuration below is fixed a priori from the literature."""
import json
import math
import os
from collections import OrderedDict

from isbl.baseline import hybrid, ir_models as M, pipeline, ranking, sfl, spectrum
from isbl.baseline.answer_key import answer_key_from_patch
from isbl.evaluation import metrics

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUGS = OrderedDict([(1, "configs/lang1_k50.json"), (2, "configs/bugs/Lang-2.json"), (3, "configs/bugs/Lang-3.json")])

P0 = {"remove_keywords": True, "remove_stopwords": True}                 # the paper's preprocessing
P3 = dict(P0, drop_license=True, split_identifiers=True, stem=True)       # + licence header off, identifier split, stem
BASELINE_IR = "tf_cosine | paper"

IR_CONFIGS = OrderedDict([
    ("tf_cosine | paper", dict(model="tf_cosine", prep=P0)),                       # the ISBL paper (baseline)
    ("tfidf_authors | none", dict(model="tfidf_authors", prep={})),                # authors' repo script
    ("tfidf_smooth | paper", dict(model="tfidf_smooth", prep=P0)),
    ("tfidf_sublinear | paper", dict(model="tfidf_sublinear", prep=P0)),
    ("tfidf_sublinear | split+stem", dict(model="tfidf_sublinear", prep=P3)),
    ("bm25 | paper", dict(model="bm25", prep=P0)),
    ("bm25 | split+stem", dict(model="bm25", prep=P3)),
    ("rvsm | paper", dict(model="rvsm", prep=P0)),
    ("rvsm | split+stem", dict(model="rvsm", prep=P3)),
    ("lm_dirichlet | split+stem", dict(model="lm_dirichlet", prep=P3)),
    ("lsi | split+stem", dict(model="lsi", prep=P3, params={"k": 50})),
    ("jaccard | paper", dict(model="jaccard", prep=P0)),
    ("containment | paper", dict(model="containment", prep=P0)),
    ("bluir_like | split+stem", dict(model="bluir", prep=P3)),
    ("rrf(bm25,tfidf,rvsm) | split+stem", dict(model="rrf", prep=P3, params={"models": [
        {"model": "bm25"}, {"model": "tfidf_sublinear"}, {"model": "rvsm"}]})),
    ("tfidf_sublinear | split+stem +name", dict(model="tfidf_sublinear", prep=P3, name_match_weight=1.0)),
    ("bm25 | split+stem +name", dict(model="bm25", prep=P3, name_match_weight=1.0)),
    # query cleaning: strip pasted stack traces from the bug report (Lang-2 contains 49 foreign stack frames)
    ("tf_cosine | paper +clean", dict(model="tf_cosine", prep=P0, clean_query=True)),
    ("tfidf_sublinear | split+stem +clean", dict(model="tfidf_sublinear", prep=P3, clean_query=True)),
    ("bm25 | split+stem +clean", dict(model="bm25", prep=P3, clean_query=True)),
    ("rvsm | split+stem +clean", dict(model="rvsm", prep=P3, clean_query=True)),
    ("bluir_like | split+stem +clean", dict(model="bluir", prep=P3, clean_query=True)),
    ("lm_dirichlet | split+stem +clean", dict(model="lm_dirichlet", prep=P3, clean_query=True)),
])
SFL_ALONE = ["ochiai", "dstar", "dstar3", "tarantula", "jaccard", "sorensen_dice", "kulczynski2", "op2", "barinel",
             "wong2", "ochiai2"]
ISBL_FORMULAS = ["ochiai", "dstar"]
ISBL_KS = [0.1, 0.25, 0.5]
HYBRID_IR = ["tf_cosine | paper", "tfidf_sublinear | split+stem", "bm25 | split+stem", "rvsm | split+stem",
             "bluir_like | split+stem", "rrf(bm25,tfidf,rvsm) | split+stem",
             "tfidf_sublinear | split+stem +clean", "bm25 | split+stem +clean"]
HYBRID_MODES = [("tie_file", {}), ("tie_text", {}), ("tie_file_text", {}), ("linear a=0.3", {"mode": "linear", "a": 0.3}),
                ("linear a=0.3 b=0.3", {"mode": "linear", "a": 0.3, "b": 0.3}), ("mult a=0.5", {"mode": "mult", "a": 0.5})]
HYBRID_KS = [0.5, 1.0]
TIES = ("worst", "average", "best")


def load_bug(n):
    cfg = json.load(open(os.path.join(ROOT, BUGS[n])))
    P = lambda p: os.path.join(ROOT, p)
    files = pipeline.load_sources(os.path.join(P(cfg["repo"]), cfg["src_dir"]))
    qpath = P(cfg["bug_report"])
    cov = P(cfg["coverage_file"].replace(".tsv", "_relevant.tsv"))
    tests = spectrum.parse_coverage(cov)
    tests, _ = spectrum.keep_trigger_failures(tests, spectrum.parse_trigger_tests(P(cfg["trigger_tests_file"])))
    key = answer_key_from_patch(open(P(cfg["answer_key_patch"]), encoding="utf-8").read())
    return {"n": n, "name": "Lang-%d" % n, "files": files, "query": pipeline.load_bug_report(qpath),
            "fields": pipeline.load_bug_report_fields(qpath), "tests": tests, "full": spectrum.build_spectrum(tests),
            "key": key, "bug_files": sorted({f for f, _ in key})}


def ir_rank(bug, name, cache):
    ck = (bug["n"], name)
    if ck not in cache:
        c = dict(IR_CONFIGS[name])
        cache[ck] = M.rank(c.pop("model"), bug["query"], bug["files"], query_fields=bug["fields"],
                           **dict(c, **c.pop("params", {})))
    return cache[ck]


def file_level(bug, name, ranked):
    n_files = len(ranked)
    pos = sorted(i + 1 for i, (f, _) in enumerate(ranked) if f in bug["bug_files"])
    rel = len(bug["bug_files"])
    first = pos[0] if pos else None
    row = {"bug": bug["name"], "ir_config": name, "num_files": n_files, "num_buggy_files": rel,
           "buggy_file_rank": first, "rank_percentile": (first / float(n_files)) if first else None,
           "Top@1": int(bool(first and first <= 1)), "Top@5": int(bool(first and first <= 5)),
           "Top@10": int(bool(first and first <= 10)), "RR": (1.0 / first) if first else 0.0,
           "AP": metrics.ap_over_all_relevant(pos, rel), "nDCG@10": metrics.ndcg_at_k(pos, 10, rel)}
    for pct in (10, 25, 50):
        kk = max(1, int(math.ceil(pct / 100.0 * n_files)))
        row["recall@%d%%files" % pct] = metrics.recall_at_k(pos, kk, rel)
    return row


def _stmt_row(bug, method_id, family, ir_name, k, formula, mode, spec, n_tests, key_by_tie):
    key = bug["key"]
    row = {"bug": bug["name"], "method": method_id, "family": family, "ir_config": ir_name, "k": k,
           "sfl": formula, "hybrid": mode, "num_statements": len(spec), "num_tests": n_tests}
    in_spec = [s for s in key if s in spec]
    row["buggy_in_spectrum"] = len(in_spec)
    rel = len(key)
    for tie in TIES:
        ranks = key_by_tie[tie]
        rr = metrics.all_ranks(ranks, key)
        best = rr[0] if rr else None
        t = {"worst": "w", "average": "a", "best": "b"}[tie]
        row["rank_" + t] = best
        row["MRR_" + t] = (1.0 / best) if best else 0.0
        if tie != "best":
            for n in (1, 3, 5):
                row["TOP@%d_%s" % (n, t)] = int(bool(best and best <= n))
        if tie == "average":
            row["MAP_a"] = metrics.ap_over_all_relevant(rr, rel)
            row["nDCG@10_a"] = metrics.ndcg_at_k(rr, 10, rel)
            row["recall@10_a"] = metrics.recall_at_k(rr, 10, rel)
            row["EXAM_a"] = metrics.exam_score(best, len(bug["full"]))   # same denominator for every method
            row["wasted_a"] = (best - 1) if best else None
    return row


def _ranks_all_ties(keys):
    return {tie: ranking.rank_keys(keys, tie=tie) for tie in TIES}


def statement_level(bug, cache):
    rows = []
    full, tests = bug["full"], bug["tests"]
    # E1: SFL formulas alone (no IR)
    for f in SFL_ALONE:
        scores = {s: sfl.FORMULAS[f](*v) for s, v in full.items()}
        keys = hybrid.finite(scores)
        rows.append(_stmt_row(bug, "SFL:" + f, "SFL", None, None, f, "sfl", full, len(tests), _ranks_all_ties(keys)))
    # E2: ISBL (IR filter then SFL) for every IR configuration
    reduced_cache = {}
    for name in IR_CONFIGS:
        ranked = ir_rank(bug, name, cache)
        for k in ISBL_KS:
            susp = pipeline.ir.select_top_k(ranked, k)
            rt = spectrum.reduce_tests(tests, susp)
            red = spectrum.build_spectrum(rt)
            reduced_cache[(name, k)] = (rt, red)
            for f in ISBL_FORMULAS:
                scores = {s: sfl.FORMULAS[f](*v) for s, v in red.items()}
                rows.append(_stmt_row(bug, "ISBL[%s,k=%g]+%s" % (name, k, f), "ISBL", name, k, f, "sfl", red,
                                      len(rt), _ranks_all_ties(hybrid.finite(scores))))
    # E3: hybrid ranking (bug-report information used to break SFL ties / blend scores)
    text_cache = {}
    for name in HYBRID_IR:
        ranked = ir_rank(bug, name, cache)
        fscore = hybrid.file_score_map(ranked)
        for k in HYBRID_KS:
            if (name, k) in reduced_cache:
                rt, red = reduced_cache[(name, k)]
            else:
                susp = pipeline.ir.select_top_k(ranked, k)
                rt = spectrum.reduce_tests(tests, susp)
                red = spectrum.build_spectrum(rt)
            if "stmt" not in text_cache:
                text_cache["stmt"] = hybrid.statement_text_scores(list(full.keys()), bug["files"], bug["query"], P3)
            text = {s: text_cache["stmt"][s] for s in red}
            for f in ISBL_FORMULAS:
                scores = {s: sfl.FORMULAS[f](*v) for s, v in red.items()}
                for label, kw in HYBRID_MODES:
                    mode = kw.get("mode", label)
                    keys = hybrid.keys_for(mode, scores, fscore, text, a=kw.get("a", 0.3), b=kw.get("b", 0.0))
                    rows.append(_stmt_row(bug, "HYBRID[%s,k=%g,%s]+%s" % (name, k, label, f), "HYBRID", name, k, f,
                                          label, red, len(rt), _ranks_all_ties(keys)))
    return rows


def run(bug_ids=None):
    cache, frows, srows = {}, [], []
    for n in (bug_ids or list(BUGS)):
        bug = load_bug(n)
        for name in IR_CONFIGS:
            frows.append(file_level(bug, name, ir_rank(bug, name, cache)))
        srows.extend(statement_level(bug, cache))
    return frows, srows


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def summarize_files(frows):
    out = OrderedDict()
    for r in frows:
        out.setdefault(r["ir_config"], []).append(r)
    res = []
    for name, rs in out.items():
        res.append({"ir_config": name, "bugs": len(rs), "Top@1": sum(r["Top@1"] for r in rs),
                    "Top@5": sum(r["Top@5"] for r in rs), "Top@10": sum(r["Top@10"] for r in rs),
                    "MRR": _mean([r["RR"] for r in rs]), "MAP": _mean([r["AP"] for r in rs]),
                    "nDCG@10": _mean([r["nDCG@10"] for r in rs]),
                    "mean_buggy_file_rank": _mean([r["buggy_file_rank"] for r in rs]),
                    "ranks_per_bug": "/".join(str(r["buggy_file_rank"]) for r in rs),
                    "recall@10%files": _mean([r["recall@10%files"] for r in rs]),
                    "recall@25%files": _mean([r["recall@25%files"] for r in rs]),
                    "recall@50%files": _mean([r["recall@50%files"] for r in rs])})
    return res


def summarize_statements(srows, baseline="SFL:ochiai"):
    by = OrderedDict()
    for r in srows:
        by.setdefault(r["method"], []).append(r)
    base_ranks = [r["rank_a"] for r in by[baseline]]
    res = []
    for m, rs in by.items():
        ra = [r["rank_a"] for r in rs]
        w, d, l = metrics.win_draw_lose(ra, base_ranks)
        mrr_a = [r["MRR_a"] for r in rs]
        lo, hi = metrics.bootstrap_ci(mrr_a)
        res.append({"method": m, "family": rs[0]["family"], "ir_config": rs[0]["ir_config"], "k": rs[0]["k"],
                    "sfl": rs[0]["sfl"], "hybrid": rs[0]["hybrid"], "bugs": len(rs),
                    "TOP@1_worst": sum(r["TOP@1_w"] for r in rs), "TOP@3_worst": sum(r["TOP@3_w"] for r in rs),
                    "TOP@5_worst": sum(r["TOP@5_w"] for r in rs),
                    "TOP@1_avg": sum(r["TOP@1_a"] for r in rs), "TOP@3_avg": sum(r["TOP@3_a"] for r in rs),
                    "TOP@5_avg": sum(r["TOP@5_a"] for r in rs),
                    "MRR_worst": _mean([r["MRR_w"] for r in rs]), "MRR_avg": _mean(mrr_a),
                    "MRR_best": _mean([r["MRR_b"] for r in rs]), "MRR_avg_CI95_lo": lo, "MRR_avg_CI95_hi": hi,
                    "MAP_avg": _mean([r["MAP_a"] for r in rs]), "nDCG@10_avg": _mean([r["nDCG@10_a"] for r in rs]),
                    "recall@10_avg": _mean([r["recall@10_a"] for r in rs]), "EXAM_avg": _mean([r["EXAM_a"] for r in rs]),
                    "mean_rank_avg": _mean(ra), "mean_wasted_effort": _mean([r["wasted_a"] for r in rs]),
                    "ranks_avg_per_bug": "/".join(("%g" % x) if x is not None else "-" for x in ra),
                    "vs_%s_win" % baseline: w, "vs_%s_draw" % baseline: d, "vs_%s_lose" % baseline: l,
                    "wilcoxon_p_vs_%s" % baseline: metrics.wilcoxon_p([x if x is not None else 1e9 for x in ra],
                                                                       [x if x is not None else 1e9 for x in base_ranks])})
    return res
