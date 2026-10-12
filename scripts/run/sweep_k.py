"""k sweep (10%..90%) for the configured bug: ISBL vs the unfiltered SFL baseline, all three tie rules.
Usage: python scripts/run/sweep_k.py configs/lang1_k50.json"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from isbl.baseline import pipeline  # noqa: E402

cfg = json.load(open(sys.argv[1]))
cfg["_root"] = ROOT
rows = []
print("%-4s %-12s %-5s %5s %6s %-17s %s" % ("k", "method", "inTopK", "files", "stmts", "rank worst/avg/best", "MRR(worst)"))
for k in [i / 10 for i in range(1, 10)]:
    cfg["k"] = k
    for r in pipeline.run(cfg):
        if r["method"] == r["sfl_formula"] and k != 0.1:
            continue  # the unfiltered baseline does not depend on k; print it once
        rows.append(r)
        print("%-4.1f %-12s %-6s %5s %6d %-19s %.4f" % (
            k, r["method"], r["buggy_file_in_top_k"], r["num_suspicious_files"], r["num_statements"],
            "%s/%s/%s" % (r["rank_worst"], r["rank_average"], r["rank_best"]), r["MRR"]))
tag = "%s-%s_%s_%s_sweep_k.csv" % (cfg["project"], cfg["bug_id"], cfg.get("ir_mode", "tf"), cfg.get("test_scope", "relevant"))
out = os.path.join(ROOT, "results", "raw", tag)
cols = ["project", "bug_id", "method", "k", "test_scope", "num_suspicious_files", "buggy_file_in_top_k", "num_tests",
        "num_statements", "rank_worst", "rank_average", "rank_best", "TOP@1", "TOP@3", "TOP@5", "MRR"]
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
print("wrote", out)
