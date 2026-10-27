"""Figures for docs/REPORT.md, drawn from results/experiments/*.csv (matplotlib; run with a Python that has it,
e.g. the Anaconda base:  C:\\Users\\Prasun\\anaconda3\\python.exe scripts\\run\\make_report_figures.py)."""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXP = os.path.join(ROOT, "results", "experiments")
OUT = os.path.join(ROOT, "docs", "images")
C1, C2, RED, GREY = "#2F6DB5", "#E07B00", "#C00000", "#7F7F7F"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})


def rows(name):
    return list(csv.DictReader(open(os.path.join(EXP, name))))


def fig_file_rank():
    F = {(r["bug"], r["ir_config"]): int(r["buggy_file_rank"]) for r in rows("file_level_per_bug.csv")}
    cfgs = ["tf_cosine | paper", "tf_cosine | paper +clean", "jaccard | paper", "containment | paper",
            "bm25 | paper", "bm25 | split+stem", "bm25 | split+stem +clean", "lm_dirichlet | split+stem",
            "lm_dirichlet | split+stem +clean", "bluir_like | split+stem", "bluir_like | split+stem +clean",
            "lsi | split+stem", "tfidf_sublinear | split+stem", "tfidf_authors | none", "tfidf_sublinear | paper",
            "tfidf_sublinear | split+stem +clean", "rvsm | paper", "rvsm | split+stem +clean"]
    order = sorted(cfgs, key=lambda c: (-(F[("Lang-2", c)] + F[("Lang-1", c)]), c))
    fig, ax = plt.subplots(figsize=(9.5, 7))
    h = 0.38
    for i, c in enumerate(order):
        y = i
        for off, bug, col in ((-h / 2, "Lang-1", C1), (h / 2, "Lang-2", C2)):
            v = F[(bug, c)]
            ax.barh(y + off, v, height=h, color=col, label=bug if i == 0 else None)
            ax.text(v + 0.4, y + off, str(v), va="center", fontsize=8)
    ax.set_yticks(range(len(order)))
    labels = [c.replace(" | ", "  /  ") for c in order]
    ax.set_yticklabels(labels)
    for lab, c in zip(ax.get_yticklabels(), order):
        if c == "tf_cosine | paper":
            lab.set_color(RED)
            lab.set_fontweight("bold")
    ax.set_xlabel("rank of the buggy file among 108 files   (1 = best, lower is better)")
    ax.set_title("Which IR model finds the buggy file?\n(red label = the ISBL paper's raw term-frequency cosine)")
    ax.axvline(1, color=GREY, lw=0.8, ls=":")
    ax.set_xlim(0, 40)
    ax.legend(loc="center right")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_file_rank.png"), dpi=150)
    plt.close(fig)


def fig_spectrum_cut():
    S = {(r["bug"], r["method"]): r for r in rows("statement_level_per_bug.csv")}
    cfgs = [("tf_cosine | paper", "raw-TF cosine (paper)", RED), ("rvsm | paper", "rVSM", "#548235"),
            ("tfidf_sublinear | split+stem +clean", "TF-IDF + clean", C1), ("bm25 | split+stem", "BM25 split+stem", "#7030A0")]
    ks = [0.1, 0.25, 0.5]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, bug in zip(axes, ("Lang-1", "Lang-2")):
        full = int(S[(bug, "SFL:ochiai")]["num_statements"])
        w = 0.19
        for j, (cfg, lab, col) in enumerate(cfgs):
            for i, k in enumerate(ks):
                r = S[(bug, "ISBL[%s,k=%g]+ochiai" % (cfg, k))]
                pct = 100.0 * int(r["num_statements"]) / full
                lost = r["buggy_in_spectrum"] == "0"
                x = i + (j - 1.5) * w
                ax.bar(x, pct, width=w * 0.92, color=("white" if lost else col), edgecolor=(RED if lost else col),
                       hatch=("///" if lost else None), linewidth=1.4, label=lab if i == 0 else None)
                if lost:
                    ax.text(x, pct + 1.5, "LOST", ha="center", fontsize=7, color=RED, rotation=90, va="bottom")
        ax.set_xticks(range(len(ks)))
        ax.set_xticklabels(["k = %d%%" % int(k * 100) for k in ks])
        ax.set_title("%s   (full spectrum = %d statements)" % (bug, full))
        ax.set_ylim(0, 128)
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("statements left after the file filter (% of full spectrum)")
    axes[0].legend(loc="upper left", fontsize=8, ncol=2)
    fig.suptitle("How much of the spectrum the filter cuts - and when it throws the buggy file away (hatched red = buggy file lost)", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_spectrum_cut.png"), dpi=150)
    plt.close(fig)


def fig_ties():
    S = {(r["bug"], r["method"]): r for r in rows("statement_level_per_bug.csv")}
    items = [("Lang-1", "SFL:ochiai", "plain Ochiai"),
             ("Lang-1", "HYBRID[tfidf_sublinear | split+stem +clean,k=0.5,tie_text]+ochiai", "hybrid tie-break"),
             ("Lang-2", "SFL:ochiai", "plain Ochiai"),
             ("Lang-2", "HYBRID[tfidf_sublinear | split+stem +clean,k=0.5,tie_text]+ochiai", "hybrid tie-break")]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ys = [3.3, 2.7, 1.3, 0.7]
    for (bug, m, lab), y in zip(items, ys):
        r = S[(bug, m)]
        b, a, wst = float(r["rank_b"]), float(r["rank_a"]), float(r["rank_w"])
        col = RED if lab == "plain Ochiai" else "#548235"
        ax.plot([b, wst], [y, y], color=col, lw=7, solid_capstyle="round", alpha=0.45)
        ax.plot([a], [y], marker="D", color=col, ms=9, zorder=3)
        ax.text(wst + 0.18, y, "best %g / average %g / worst %g" % (b, a, wst), va="center", fontsize=8.5)
    ax.set_yticks(ys)
    ax.set_yticklabels(["Lang-1  plain Ochiai", "Lang-1  hybrid", "Lang-2  plain Ochiai", "Lang-2  hybrid"])
    ax.set_xlim(0.5, 11)
    ax.set_xlabel("rank of the best buggy statement   (bar = the range the tie allows, diamond = average)")
    ax.set_title("Breaking exact ties with the bug-report words narrows where the buggy line can be")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_ties.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_file_rank()
    fig_spectrum_cut()
    fig_ties()
    print("wrote figures to", OUT)
