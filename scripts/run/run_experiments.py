"""Run the IR-model / SFL / ISBL / hybrid comparison on Lang-1, Lang-2, Lang-3 (cached coverage).
Usage: python scripts/run/run_experiments.py      -> results/experiments/*.csv and printed tables"""
import csv
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from isbl.experiments import engine  # noqa: E402

OUT = os.path.join(ROOT, "results", "experiments")


def write(name, rows):
    os.makedirs(OUT, exist_ok=True)
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    path = os.path.join(OUT, name)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    return path


def f(x, d=3):
    return "-" if x is None else ("%.*f" % (d, x) if isinstance(x, float) else str(x))


def main():
    t0 = time.time()
    frows, srows = engine.run()
    fsum = engine.summarize_files(frows)
    ssum = engine.summarize_statements(srows)
    paths = [write("file_level_per_bug.csv", frows), write("file_level_summary.csv", fsum),
             write("statement_level_per_bug.csv", srows), write("statement_level_summary.csv", ssum)]
    print("ran %d file-level + %d statement-level rows in %.1fs\n" % (len(frows), len(srows), time.time() - t0))

    # ---- false exclusion: how often does the top-k filter throw the buggy file away?
    n_full = {r["bug"]: r["num_statements"] for r in srows if r["method"] == "SFL:ochiai"}
    excl = []
    for name in engine.IR_CONFIGS:
        for k in engine.ISBL_KS:
            rs = [r for r in srows if r["family"] == "ISBL" and r["ir_config"] == name and r["k"] == k and r["sfl"] == "ochiai"]
            lost = [r["bug"] for r in rs if r["buggy_in_spectrum"] == 0]
            cut = [1.0 - r["num_statements"] / float(n_full[r["bug"]]) for r in rs]
            excl.append({"ir_config": name, "k": k, "bugs": len(rs), "buggy_file_excluded": len(lost),
                         "which_bugs": ",".join(lost), "mean_statements_removed": sum(cut) / len(cut)})
    paths.append(write("false_exclusion.csv", excl))
    print("=" * 118)
    print("FALSE EXCLUSION - top-k filter vs the buggy file (bugs whose buggy file is thrown away, of 3) and how much of the spectrum is cut")
    print("%-38s %s" % ("IR configuration", "   ".join("k=%-4g lost  cut " % k for k in engine.ISBL_KS)))
    for name in engine.IR_CONFIGS:
        cells = []
        for k in engine.ISBL_KS:
            e = [x for x in excl if x["ir_config"] == name and x["k"] == k][0]
            cells.append("   %d/3  %4.0f%%     " % (e["buggy_file_excluded"], 100 * e["mean_statements_removed"]))
        print("%-38s %s" % (name, "".join(cells)))
    print()
    print("=" * 118)
    print("FILE LEVEL - how well each IR configuration ranks the buggy FILE (Lang-1, Lang-2, Lang-3; 108 files each)")
    print("%-38s %-9s %5s %5s %5s %6s %6s %7s  %s" % ("IR configuration", "ranks", "Top1", "Top5", "Top10", "MRR", "MAP",
                                                      "nDCG10", "recall@10/25/50% files"))
    for r in sorted(fsum, key=lambda r: (-r["MRR"], r["ir_config"])):
        print("%-38s %-9s %5d %5d %5d %6.3f %6.3f %7.3f  %.2f / %.2f / %.2f" % (
            r["ir_config"], r["ranks_per_bug"], r["Top@1"], r["Top@5"], r["Top@10"], r["MRR"], r["MAP"], r["nDCG@10"],
            r["recall@10%files"], r["recall@25%files"], r["recall@50%files"]))

    def show(title, rows, n=12):
        print("\n" + "=" * 118)
        print(title)
        print("%-62s %-10s %9s %9s %6s %6s %6s %7s  %s" % ("method", "rank(avg)", "TOP1/3/5w", "TOP1/3/5a", "MRRw",
                                                          "MRRa", "MAPa", "EXAMa", "vs SFL:ochiai W/D/L"))
        for r in rows[:n]:
            print("%-62s %-10s %9s %9s %6.3f %6.3f %6.3f %7.4f  %d/%d/%d" % (
                r["method"][:62], r["ranks_avg_per_bug"], "%d/%d/%d" % (r["TOP@1_worst"], r["TOP@3_worst"], r["TOP@5_worst"]),
                "%d/%d/%d" % (r["TOP@1_avg"], r["TOP@3_avg"], r["TOP@5_avg"]), r["MRR_worst"], r["MRR_avg"],
                r["MAP_avg"], r["EXAM_avg"], r["vs_SFL:ochiai_win"], r["vs_SFL:ochiai_draw"], r["vs_SFL:ochiai_lose"]))

    key = lambda r: (-r["MRR_avg"], -r["MAP_avg"], r["method"])
    show("STATEMENT LEVEL - SFL formulas alone (no IR filter), best first",
         sorted([r for r in ssum if r["family"] == "SFL"], key=key), 11)
    show("STATEMENT LEVEL - ISBL (IR filter k then SFL), top 12 by expected MRR",
         sorted([r for r in ssum if r["family"] == "ISBL"], key=key), 12)
    show("STATEMENT LEVEL - HYBRID (SFL + bug-report tie-breaking/blending), top 12 by expected MRR",
         sorted([r for r in ssum if r["family"] == "HYBRID"], key=key), 12)
    print("\nrank(avg) = best buggy-statement rank per bug (Lang-1/2/3) with tied statements averaged; "
          "w = worst-case ties, a = average ties.")
    print("Saved:\n  " + "\n  ".join(paths))


if __name__ == "__main__":
    main()
