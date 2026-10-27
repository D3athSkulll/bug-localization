"""End-to-end ISBL baseline for one Defects4J bug:
bug report -> IR ranking -> top-k files -> spectrum -> reduced spectrum -> Ochiai/DStar -> statement ranks -> metrics.
Every stage is timed; extra IR / spectrum / localisation diagnostics are logged next to TOP@N and MRR.
Usage: python -m isbl.baseline.pipeline configs/lang1_k50.json [--recollect] [--explain]"""
import csv
import json
import os
import platform
import re
import subprocess
import sys

from isbl.baseline import ir, ir_models, spectrum, sfl, ranking
from isbl.baseline.answer_key import answer_key_from_patch
from isbl.baseline.timing import StageTimer
from isbl.evaluation import metrics, diagnostics


def load_sources(src_root):
    files = {}
    for root, _, names in os.walk(src_root):
        for n in names:
            if n.endswith(".java"):
                p = os.path.join(root, n)
                rel = os.path.relpath(p, src_root).replace(os.sep, "/")
                with open(p, encoding="utf-8", errors="replace") as f:
                    files[rel] = f.read()
    return files


def load_bug_report(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)["fields"]
    return (d.get("summary") or "") + "\n" + (d.get("description") or "")


def load_bug_report_fields(path):
    """{'summary': ..., 'description': ...} of the bug report (used by structured retrieval)."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)["fields"]
    return {"summary": d.get("summary") or "", "description": d.get("description") or ""}


def buggy_statements(repo, buggy, fixed, src_prefix):
    """Buggy statements = lines of the buggy version changed by the fix (from `git diff -U0 buggy fixed`).
    Removed lines are buggy. For a pure insertion after old line a, the next old line (a+1) is used.
    Used ONLY for evaluation, never by the localisation."""
    out = subprocess.check_output(["git", "-C", repo, "diff", "-U0", buggy, fixed, "--", src_prefix],
                                  universal_newlines=True, encoding="utf-8", errors="replace")
    stmts, cur = set(), None
    for line in out.splitlines():
        if line.startswith("--- "):
            cur = None
        elif line.startswith("+++ b/"):
            cur = line[6:][len(src_prefix.rstrip("/")) + 1:]
        elif line.startswith("@@") and cur:
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+", line)
            a, b = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
            lines = range(a, a + b) if b > 0 else [a + 1]
            stmts.update((cur, l) for l in lines)
    return stmts


def discover_test_classes(test_classes_dir):
    """All top-level JUnit test classes (*Test.class) compiled in test_classes_dir."""
    out = []
    for root, _, names in os.walk(test_classes_dir):
        for n in names:
            if n.endswith("Test.class") and "$" not in n:
                rel = os.path.relpath(os.path.join(root, n), test_classes_dir)
                out.append(rel[:-len(".class")].replace(os.sep, "."))
    return sorted(out)


def _result_row(cfg, method, formula, tests_used, spec, suspicious, files, ranked, bug_stmts, bug_files, timer, extra):
    fn = sfl.FORMULAS[formula]
    tie_cfg = cfg.get("tie", "worst")
    ranks_by_tie, scores, ranks_cfg = {}, None, None
    with timer("sfl_score_and_rank:" + method):
        for tie in ("worst", "average", "best"):
            rk, sc = ranking.rank_statements(spec, fn, tie=tie)
            ranks_by_tie[tie] = metrics.bug_rank(rk, bug_stmts)
            if tie == tie_cfg:
                scores, ranks_cfg = sc, rk
    with timer("metrics_and_diagnostics:" + method):
        r = ranks_by_tie[tie_cfg]
        rs = [r]
        row = {
            "project": cfg["project"], "bug_id": cfg["bug_id"], "defects4j_version": cfg["defects4j_version"],
            "source_commit": cfg["buggy_commit"], "method": method,
            "ir_implementation": ("none" if suspicious is None else (cfg.get("ir_model") or "vsm-%s-cosine" % cfg.get("ir_mode", "tf"))),
            "ir_parameters": cfg.get("ir_options", {}), "test_scope": cfg.get("test_scope", "relevant"),
            "k": None if suspicious is None else cfg["k"], "sfl_formula": formula,
            "sfl_parameters": {"star": 2} if formula == "dstar" else {}, "tie_handling": tie_cfg,
            "num_files": len(files), "num_suspicious_files": None if suspicious is None else len(suspicious),
            "num_statements": len(spec), "num_tests": len(tests_used),
            "num_failed_tests": sum(1 for _, ok, _ in tests_used if not ok),
            "buggy_files": bug_files,
            "buggy_statements_in_spectrum": sorted("%s:%d" % s for s in bug_stmts if s in spec),
            "buggy_file_ir_rank": next((i + 1 for i, (f, _) in enumerate(ranked) if f in bug_files), None),
            "buggy_file_in_top_k": None if suspicious is None else bool(set(bug_files) & set(suspicious)),
            "predicted_rank": r, "rank_worst": ranks_by_tie["worst"], "rank_average": ranks_by_tie["average"],
            "rank_best": ranks_by_tie["best"],
            "TOP@1": metrics.top_n(rs, 1), "TOP@3": metrics.top_n(rs, 3), "TOP@5": metrics.top_n(rs, 5),
            "TOP@10": metrics.top_n(rs, 10), "MRR": metrics.mrr(rs),
            "env": {"python": platform.python_version(), "os": platform.platform()},
        }
        n_kept = len(suspicious) if suspicious is not None else len(ranked)
        row.update(diagnostics.ir_diagnostics(ranked, bug_files, n_kept))
        row.update(diagnostics.spectrum_diagnostics(tests_used, spec))
        row.update(diagnostics.localization_diagnostics(spec, scores, ranks_cfg, bug_stmts))
        row.update(extra)
    return row


def run(cfg, recollect=False, trace=None, timer=None):
    """Returns result rows: for every SFL formula, the plain SFL baseline (no IR filter) and ISBL.
    Every stage is timed in `timer` (a StageTimer; one is created if not given)."""
    timer = timer or StageTimer()
    root = cfg["_root"]
    P = lambda p: os.path.normpath(os.path.join(root, p))
    repo = P(cfg["repo"])
    src_root = os.path.join(repo, cfg["src_dir"])
    with timer("01 load_source_files"):
        files = load_sources(src_root)
    with timer("02 load_bug_report"):
        query = load_bug_report(P(cfg["bug_report"]))

    # Step A: IR file ranking + top-k
    with timer("03 ir_rank_files (tokenise+cosine)"):
        if cfg.get("ir_model"):       # any model of isbl/baseline/ir_models.py (bm25, rvsm, tfidf_sublinear, ...)
            ranked = ir_models.rank(cfg["ir_model"], query, files, prep=cfg.get("ir_options", {}),
                                    query_fields=load_bug_report_fields(P(cfg["bug_report"])),
                                    name_match_weight=cfg.get("ir_name_match_weight", 0.0), **cfg.get("ir_params", {}))
        else:
            ranked = ir.rank_files(query, files, mode=cfg.get("ir_mode", "tf"), **cfg.get("ir_options", {}))
    with timer("04 ir_select_top_k"):
        suspicious = ir.select_top_k(ranked, cfg["k"])

    # Step B: coverage of the chosen test scope
    scope = cfg.get("test_scope", "relevant")
    test_classes = cfg["test_classes"] if scope == "relevant" else discover_test_classes(
        os.path.join(repo, cfg["test_classes_dir"]))
    cov_file = P(cfg["coverage_file"].replace(".tsv", "_%s.tsv" % scope))
    from_cache = not (recollect or not os.path.exists(cov_file))
    with timer("05 coverage_collect (JVM+JaCoCo)"):
        if not from_cache:
            os.makedirs(os.path.dirname(cov_file), exist_ok=True)
            classpath = open(P(cfg["classpath_file"])).read().strip().split(";")
            spectrum.collect_coverage(os.path.join(P(cfg["java_home"]), "bin", "java"),
                                      os.path.join(repo, cfg["classes_dir"]),
                                      [os.path.join(repo, cfg["test_classes_dir"])] + classpath,
                                      test_classes, cov_file, P("tools/jacoco"), P("tools/runner"))
    with timer("06 coverage_parse"):
        tests = spectrum.parse_coverage(cov_file)
    runner_stats = spectrum.parse_runner_stats(cov_file)
    removed = []
    with timer("07 trigger_test_filter"):
        if cfg.get("trigger_tests_file"):
            trig = spectrum.parse_trigger_tests(P(cfg["trigger_tests_file"]))
            tests, removed = spectrum.keep_trigger_failures(tests, trig)
    with timer("08 build_spectrum_full"):
        full = spectrum.build_spectrum(tests)
    with timer("09 reduce_tests (paper II-B)"):
        reduced_tests = spectrum.reduce_tests(tests, suspicious)
    with timer("10 build_spectrum_reduced"):
        reduced = spectrum.build_spectrum(reduced_tests)

    # evaluation answer key (never used by the localisation)
    with timer("11 answer_key"):
        if cfg.get("answer_key_patch"):      # Defects4J src patch (fixed -> buggy): '+' lines are buggy
            with open(P(cfg["answer_key_patch"]), encoding="utf-8", errors="replace") as fh:
                bug_stmts = answer_key_from_patch(fh.read())
        else:
            bug_stmts = buggy_statements(repo, cfg["buggy_commit"], cfg["fixed_commit"], cfg["src_dir"])
        bug_files = sorted({f for f, _ in bug_stmts})

    if trace is not None:
        trace.update(ranked=ranked, suspicious=suspicious, tests=tests, reduced_tests=reduced_tests,
                     full=full, reduced=reduced, bug_stmts=bug_stmts, bug_files=bug_files, query=query,
                     timer=timer, runner_stats=runner_stats, from_cache=from_cache)
    results = []
    red = diagnostics.reduction_diagnostics(tests, reduced_tests, full, reduced)
    for name in cfg["sfl"]:
        results.append(_result_row(cfg, name, name, tests, full, None, files, ranked, bug_stmts, bug_files, timer, {}))
        results.append(_result_row(cfg, "ISBL-" + name, name, reduced_tests, reduced, suspicious, files, ranked,
                                   bug_stmts, bug_files, timer, red))
    for r in results:
        r["removed_non_trigger_failures"] = len(removed)
        r["coverage_from_cache"] = from_cache
        r["coverage_runner_ms"] = runner_stats
        r["timings_sec"] = timer.as_dict()
        r["runtime_sec"] = round(timer.total(), 3)
    return results


CSV_COLS = ["project", "bug_id", "method", "k", "test_scope", "num_files", "num_suspicious_files", "num_tests",
            "num_failed_tests", "num_statements", "buggy_file_ir_rank", "buggy_file_in_top_k", "predicted_rank",
            "rank_worst", "rank_average", "rank_best", "TOP@1", "TOP@3", "TOP@5", "TOP@10", "MRR",
            "ir_buggy_file_rank_percentile", "ir_buggy_file_cosine", "ir_top1_cosine", "ir_score_gap_top1_top2",
            "ir_score_entropy_bits", "ir_files_with_nonzero_cosine", "ir_buggy_file_recall_at_k",
            "sp_matrix_cells", "sp_matrix_density", "sp_avg_statements_per_test", "sp_avg_tests_per_statement",
            "red_statements_removed_pct", "red_tests_removed_pct",
            "loc_num_buggy_statements", "loc_num_buggy_in_spectrum", "loc_best_buggy_score", "loc_top_score",
            "loc_best_buggy_score_over_top", "loc_mean_buggy_rank", "loc_median_buggy_rank", "loc_exam_score",
            "loc_wasted_effort", "loc_distinct_scores", "loc_statements_with_score_gt0", "loc_tie_group_size",
            "loc_buggy_in_tie_group", "runtime_sec"]


def _fmt(v):
    return "-" if v is None else ("%.4g" % v if isinstance(v, float) else str(v))


def print_metrics(res):
    """Compact metric tables from the result rows."""
    r0 = res[0]
    print("\nIR stage : buggy file rank %s/%d (percentile %s = smallest k that keeps it), cosine %s vs top-1 %s, "
          "gap(top1-top2) %s, entropy %s bits, %d files with cosine>0" % (
              _fmt(r0["ir_buggy_file_rank"]), r0["num_files"], _fmt(r0["ir_buggy_file_rank_percentile"]),
              _fmt(r0["ir_buggy_file_cosine"]), _fmt(r0["ir_top1_cosine"]), _fmt(r0["ir_score_gap_top1_top2"]),
              _fmt(r0["ir_score_entropy_bits"]), r0["ir_files_with_nonzero_cosine"]))
    hdr = "%-12s %6s %6s %8s | %5s %5s %5s | %9s %7s %8s | %6s %6s | %-9s"
    print("\n" + hdr % ("method", "tests", "stmts", "density", "worst", "avg", "best", "exam", "wasted", "distinct",
                        "tieGrp", "bugInT", "stmts cut"))
    for r in res:
        print(hdr % (r["method"], r["num_tests"], r["num_statements"], _fmt(r["sp_matrix_density"]),
                     r["rank_worst"], r["rank_average"], r["rank_best"], _fmt(r["loc_exam_score"]),
                     _fmt(r["loc_wasted_effort"]), r["loc_distinct_scores"], _fmt(r["loc_tie_group_size"]),
                     _fmt(r["loc_buggy_in_tie_group"]),
                     ("-%.1f%%" % r["red_statements_removed_pct"]) if "red_statements_removed_pct" in r else "-"))
    print("  exam = buggy rank / #statements (share of the list read); wasted = statements read before the bug;\n"
          "  distinct = number of different scores; tieGrp = statements sharing the buggy line's score; "
          "bugInT = how many of those are buggy.")


def print_timing(timer, runner_stats, from_cache):
    print("\nTIMING (wall clock per pipeline stage, this run)")
    print(timer.table())
    if runner_stats:
        tot = float(runner_stats["jvm_total_ms"]) or 1.0
        print("\n  JVM coverage run (%s): %d tests, %.2fs total" % (
            "recorded when the coverage file was created; this run read the cache" if from_cache else "measured now",
            runner_stats["tests"], tot / 1000))
        for k, label in (("test_exec_ms", "running the project's tests"),
                         ("jacoco_dump_ms", "JaCoCo dump of exec data"),
                         ("jacoco_analyze_ms", "JaCoCo class analysis (repeated for every test)")):
            print("    %-50s %8.2fs %5.1f%%" % (label, runner_stats[k] / 1000.0, 100.0 * runner_stats[k] / tot))
        other = tot - runner_stats["test_exec_ms"] - runner_stats["jacoco_dump_ms"] - runner_stats["jacoco_analyze_ms"]
        print("    %-50s %8.2fs %5.1f%%" % ("JVM startup, class loading, other", other / 1000.0, 100.0 * other / tot))
        print("    throughput: %.1f tests/s end-to-end" % (runner_stats["tests"] / (tot / 1000.0)))


def main(argv):
    cfg_path = argv[1]
    with open(cfg_path) as f:
        cfg = json.load(f)
    cfg["_root"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    trace = {}
    timer = StageTimer()
    res = run(cfg, recollect="--recollect" in argv, trace=trace, timer=timer)
    out_dir = os.path.join(cfg["_root"], "results", "raw")
    os.makedirs(out_dir, exist_ok=True)
    ir_name = cfg.get("ir_model") or cfg.get("ir_mode", "tf")
    tag = "%s-%s_%s_%s_k%g" % (cfg["project"], cfg["bug_id"], ir_name, cfg.get("test_scope", "relevant"), cfg["k"])
    with open(os.path.join(out_dir, tag + ".json"), "w") as f:
        json.dump(res, f, indent=2)
    with open(os.path.join(out_dir, tag + ".csv"), "w", newline="") as f:
        w = csv.DictWriter(f, CSV_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(res)
    tot = timer.total() or 1e-12
    with open(os.path.join(out_dir, tag + "_timing.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["stage", "seconds", "share_pct"])
        for k, v in timer.stages.items():
            w.writerow([k, "%.6f" % v, "%.2f" % (100.0 * v / tot)])
        rs = trace.get("runner_stats")
        if rs:
            for k in ("test_exec_ms", "jacoco_dump_ms", "jacoco_analyze_ms", "jvm_total_ms"):
                w.writerow(["jvm:" + k, "%.3f" % (rs[k] / 1000.0), ""])
    print("non-trigger failing tests removed from spectrum: %d" % res[0]["removed_non_trigger_failures"])
    print("IR=%s scope=%s k=%g tie=%s  buggy file IR rank=%s/%d" % (
        ir_name, cfg.get("test_scope", "relevant"), cfg["k"], cfg.get("tie", "worst"),
        res[0]["buggy_file_ir_rank"], res[0]["num_files"]))
    print("%-12s %7s %6s %9s  %-18s %s" % ("method", "tests", "stmts", "rank", "worst/avg/best", "TOP@1/3/5  MRR"))
    for r in res:
        print("%-12s %7d %6d %9s  %-18s %d/%d/%d      %.4f" % (
            r["method"], r["num_tests"], r["num_statements"], r["predicted_rank"],
            "%s/%s/%s" % (r["rank_worst"], r["rank_average"], r["rank_best"]),
            r["TOP@1"], r["TOP@3"], r["TOP@5"], r["MRR"]))
    print_metrics(res)
    print_timing(timer, trace.get("runner_stats"), trace.get("from_cache"))
    print("\nSaved: %s{.json,.csv,_timing.csv}" % os.path.join(out_dir, tag))
    if "--explain" in argv:
        from isbl.baseline import report
        report.explain(cfg, trace, out_dir, tag)


if __name__ == "__main__":
    main(sys.argv)
