"""Human-readable intermediate output for one bug (--explain): the cosine-similarity table of the IR step and the
test x statement coverage matrix with ef/ep/nf/np and the Ochiai/DStar scores. Also writes full CSVs."""
import csv
import os

from isbl.baseline import ranking, sfl


def _short(f):
    return f.replace("org/apache/commons/lang3/", "")


def explain(cfg, trace, out_dir, tag):
    ranked, susp = trace["ranked"], set(trace["suspicious"])
    bug_files, bug_stmts = set(trace["bug_files"]), trace["bug_stmts"]
    rtests, reduced = trace["reduced_tests"], trace["reduced"]

    # ---------------- 1. IR step: cosine similarity of every file with the bug report -------------
    print("\n" + "=" * 100)
    print("STEP A - IR: cosine similarity between the bug report and each source file (%s)" % cfg.get("ir_mode", "tf"))
    print("  cos(x,y) = sum(x_i*y_i) / ( sqrt(sum x_i^2) * sqrt(sum y_i^2) ),  x = word counts of the file, y = of the report")
    print("  query = %r ..." % trace["query"].replace("\n", " ")[:90])
    print("  %-5s %-52s %-10s %s" % ("rank", "file", "cosine", "kept (top %g%% = %d files)" % (cfg["k"] * 100, len(susp))))
    shown = 0
    for i, (f, sc) in enumerate(ranked, 1):
        is_bug = f in bug_files
        if i <= 10 or is_bug or i == len(susp) or i == len(susp) + 1:
            if shown and i > 11 and not (is_bug or i in (len(susp), len(susp) + 1)):
                pass
            print("  %-5d %-52s %-10.4f %s%s" % (i, _short(f), sc, "KEPT" if f in susp else "dropped",
                                                 "   <== FILE WITH THE BUG" if is_bug else ""))
            shown += 1
        elif i == 11:
            print("  ...")
    print("  (all %d files saved to the CSV below)" % len(ranked))
    ir_csv = os.path.join(out_dir, tag + "_ir_cosine.csv")
    with open(ir_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "file", "cosine", "kept", "has_bug"])
        for i, (f, sc) in enumerate(ranked, 1):
            w.writerow([i, f, "%.6f" % sc, f in susp, f in bug_files])

    # ---------------- 2. spectrum: scores for every statement in the reduced spectrum --------------
    formula = sfl.FORMULAS[cfg["sfl"][0]]
    ranks, scores = ranking.rank_statements(reduced, formula, tie=cfg.get("tie", "worst"))
    dstar_scores = {s: sfl.dstar(*v) for s, v in reduced.items()}
    order = sorted(reduced, key=lambda s: (-scores[s], s))
    spec_csv = os.path.join(out_dir, tag + "_spectrum_scores.csv")
    with open(spec_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank_%s" % cfg.get("tie", "worst"), "file", "line", "ef", "ep", "nf", "np", "ochiai", "dstar", "is_buggy"])
        for s in order:
            ef, ep, nf, np_ = reduced[s]
            w.writerow([ranks[s], s[0], s[1], ef, ep, nf, np_, "%.6f" % sfl.ochiai(ef, ep, nf, np_),
                        "inf" if dstar_scores[s] == float("inf") else "%.6f" % dstar_scores[s], s in bug_stmts])

    # ---------------- 3. the coverage matrix of the reduced spectrum ----------------------------
    cols = order[:8]
    buggy_cols = [s for s in order if s in bug_stmts and s not in cols][:2]
    cols = cols + buggy_cols
    idx = {s: i for i, s in enumerate(cols)}
    rows = []
    for name, ok, cov in rtests:
        v = [1 if (s[0] in cov and s[1] in cov[s[0]]) else 0 for s in cols]
        if any(v):
            rows.append((name, ok, v))
    rows.sort(key=lambda r: (r[1], -sum(r[2]), r[0]))          # failing tests first
    print("\n" + "=" * 100)
    print("STEP B - Spectrum (after IR reduction): %d tests x %d statements; %d failing test(s)." % (
        len(rtests), len(reduced), sum(1 for _, ok, _ in rtests if not ok)))
    print("  Coverage matrix X (1 = test executes the statement). Showing the %d highest-scored statements"
          % len(order[:8]) + (" + %d buggy ones" % len(buggy_cols) if buggy_cols else "") + ".")
    head = "  %-46s %-4s" % ("test", "res") + "".join(" L%-4d" % s[1] for s in cols)
    print("  file of columns: " + ", ".join(sorted({_short(s[0]) for s in cols})))
    print(head)
    nfail_rows = [r for r in rows if not r[1]]
    npass_rows = [r for r in rows if r[1]]
    for name, ok, v in nfail_rows + npass_rows[:7]:
        print("  %-46s %-4s" % (name.split("(")[0][:46], "FAIL" if not ok else "pass") + "".join(" %-5d" % x for x in v))
    if len(npass_rows) > 7:
        print("  ... %d more passing tests that run at least one of these statements ..." % (len(npass_rows) - 7))
    print("  " + "-" * (len(head) - 2))
    for lab, k in (("ef (failing tests that run it)", 0), ("ep (passing tests that run it)", 1),
                   ("nf (failing tests that miss it)", 2), ("np (passing tests that miss it)", 3)):
        print("  %-51s" % lab + "".join(" %-5d" % reduced[s][k] for s in cols))
    print("  %-51s" % "Ochiai = ef/sqrt((ef+nf)(ef+ep))" + "".join(" %-5.2f" % sfl.ochiai(*reduced[s]) for s in cols))
    print("  %-51s" % "DStar  = ef^2/(ep+nf)" + "".join(
        " %-5s" % ("inf" if dstar_scores[s] == float("inf") else "%.2f" % dstar_scores[s]) for s in cols))
    print("  %-51s" % "rank (ties -> %s)" % cfg.get("tie", "worst") + "".join(" %-5s" % ranks[s] for s in cols))
    print("  %-51s" % "is a real buggy line?" + "".join(" %-5s" % ("YES" if s in bug_stmts else "-") for s in cols))

    # full binary matrix as csv (skip if enormous)
    statements = sorted(reduced)
    if len(rtests) * len(statements) <= 3000000:
        mat_csv = os.path.join(out_dir, tag + "_coverage_matrix.csv")
        with open(mat_csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["test", "result"] + ["%s:%d" % (_short(f), l) for f, l in statements])
            for name, ok, cov in rtests:
                w.writerow([name, "pass" if ok else "FAIL"] + [1 if (f in cov and l in cov[f]) else 0 for f, l in statements])
    else:
        mat_csv = "(skipped: matrix too large)"
    print("\nSaved: %s\n       %s\n       %s" % (ir_csv, spec_csv, mat_csv))
