# Literature scan: metrics and methods for IR-based + spectrum-based bug localisation

Collected on 2026-10-25 by web search (WebSearch, abstracts and search snippets only; **the full papers were not read**).
Each row says what the source reports and what, if anything, was added to this code base. Formula definitions that
the search results did not show (Barinel, Op2, Kulczynski2, Ochiai2, Sørensen-Dice) are the standard ones from the
SBFL literature and are covered by unit tests, but are not verified against the cited surveys here.

## 1. Evaluation metrics

| Source | What it reports | Added here |
|---|---|---|
| [When Deep Learning Meets IR-based Bug Localization: A Survey, arXiv 2505.00144](https://arxiv.org/pdf/2505.00144) | Of 61 primary studies, 59 use **MAP**; MAP, **MRR** and **Top-k** are the usual metrics; AUC/precision/recall/F-measure appear only occasionally | `average_precision`, `ap_over_all_relevant` (MAP), `ndcg_at_k`, `recall_at_k`, `precision_at_k` in `isbl/evaluation/metrics.py`; MAP, MRR, Top@1/5/10, nDCG@10, recall@k% at **file level** in the experiment tables |
| [FlexFL, arXiv 2411.10714](https://arxiv.org/pdf/2411.10714) and related snippets | Top-N with N = 1, 3, 5 is close to what developers expect; **EXAM** = share of statements examined before the first buggy one | `exam_score` (one fixed denominator for every method, the full-spectrum statement count), `wasted effort = rank - 1`, TOP@1/3/5 kept as in the ISBL paper |
| [Literature review of bug-localisation approaches, arXiv 2212.11774](https://arxiv.org/pdf/2212.11774) | Survey of empirically evaluated approaches | background only |
| ISBL paper (Li et al., SMC 2023), section IV-A | **WIN / DRAW / LOSE** per bug against Ochiai/DStar | `win_draw_lose` (by best buggy-statement rank), plus `bootstrap_ci` and `wilcoxon_p`. With only 3 bugs these are reported for completeness, not as evidence |

## 2. Information-retrieval models for ranking files

| Source | What it reports | Added here (`isbl/baseline/ir_models.py`) |
|---|---|---|
| [Zhou, Zhang, Lo, *Where should the bugs be fixed?* (BugLocator), ICSE 2012](https://ink.library.smu.edu.sg/sis_research/1531), DOI 10.1109/ICSE.2012.6227210 | **rVSM**: a tf-idf variant with a size-based correction that favours larger files; BugLocator also uses similar previously fixed bugs | `rvsm` (log-tf x log-idf cosine times a logistic file-length bonus). The similar-bug history part is **not** implemented (no report history available) |
| [Saha et al., *BLUiR*, ASE 2013](https://ischool.utexas.edu/ml/papers/saha-ase13.pdf) | Structured IR: class, method and variable names and comments of each file are separate fields; two fields of the bug report | `bluir`: BM25 between {summary, description} and {class name, method names, identifiers, comments}, summed. Field extraction is a regex heuristic, not a Java parser |
| A feature-location study (snippet only; [PDF](https://static.aminer.org/pdf/20170130/pdfs/sigsoft/enipyx1fcu9xh8dzrtcz50jbq4mgskj7.pdf), authors/venue not visible in the snippet) | On four open-source projects BM25 and BM25F were consistently better than VSM, a unigram model and LDA | `bm25` (Okapi, k1 = 1.2, b = 0.75), `lm_dirichlet` (unigram query likelihood, mu = 2000), `lsi` (truncated SVD) |
| [Purdue, SCAM 2012: effect of stemming on keyword-based source-code retrieval](https://engineering.purdue.edu/RVL/Publications/SCAM12.pdf) | The benefit of stemming depends on other factors such as whether tf-idf already filters common terms | `stem` option (Snowball English stemmer). Evaluated both with and without it, not assumed to help |
| Search snippets on tf-idf / cosine bug localisation | Plain VSM with tf-idf and cosine plus Porter stemming is the common baseline | `tfidf_authors` (the repo's `vsm.py`), `tfidf_smooth`, `tfidf_sublinear` (scikit-learn semantics, unit-tested against `TfidfVectorizer`) |
| General IR practice | Jaccard / term containment as simple set baselines; reciprocal-rank fusion for combining rankings | `jaccard`, `containment`, `rrf` |

## 3. Combining bug reports with program spectra

| Source | What it reports | Added here |
|---|---|---|
| [Le, Oentaryo, Lo, *Information Retrieval and Spectrum Based Bug Localization: Better Together*, FSE 2015](https://cs.unibg.it/esecfse_proceedings/fse15/p579-le.pdf), DOI 10.1145/2786805.2786880 | A multi-modal method using both bug reports and spectra. On 157 real bugs from four systems it beat the baselines by at least 47.62% / 31.48% / 27.78% / 28.80% on Top 1 / Top 5 / Top 10 / MAP (abstract) | Motivates `hybrid.py`. Our combination is much simpler (lexicographic tie-breaking and blends); it is **not** a reimplementation of their method |
| [Dao, Zhang, Meng, *How does execution information help with IR-based bug localization?*, 2017](https://experts.illinois.edu/en/publications/how-does-execution-information-help-with-information-retrieval-ba/) | Studies how execution information helps IR-based localisation (same 157-bug data set) | background |
| ISBL paper (Li et al., SMC 2023) | IR filters files, then the spectrum is reduced | the baseline in `pipeline.py` |

## 4. Ties in spectrum-based fault localisation

| Source | What it reports | Added here |
|---|---|---|
| [Sarhan, Vancsics, Beszédes, *Method calls frequency-based tie-breaking*, arXiv 2108.11031](https://arxiv.org/pdf/2108.11031) | About 54-56% of buggy methods in Defects4J share their suspiciousness with at least one other method (average tie group roughly six); their call-frequency tie-breaker removed ties completely in 72-73% of cases | Matches what we see on Lang-1 (a tie group of six). We break ties with bug-report text instead (`tie_text`); their call-frequency idea is **not** implemented |
| [Sarhan, Beszédes, a ranking formula that breaks ties only](https://www.inf.u-szeged.hu/~beszedes/research/SaB22c.html) | Raised the number of cases where the faulty element is ranked first by 13-23% on six Defects4J programs | background for the lexicographic design (a secondary key may only reorder exact ties) |

## 5. SFL formula families

| Source | What it reports | Added here (`isbl/baseline/sfl.py`) |
|---|---|---|
| [Spectrum-based Software Fault Localization: A Survey, arXiv 1607.04347](https://arxiv.org/pdf/1607.04347) | Survey of SBFL techniques | Tarantula, Jaccard, Op2, Barinel, Kulczynski2, Wong2, Ochiai2, Sørensen-Dice, DStar(3) next to Ochiai and DStar(2) |
| [Zou et al., *An Empirical Study of Fault Localization Families and Their Combinations*, arXiv 1803.09939](https://arxiv.org/pdf/1803.09939) | Compares fault-localisation families and their combinations | background for combining families; not implemented |

## 6. Ideas found but not implemented

- **Stack-trace boosting.** BRTracer+ boosts files named in the top stack-trace frames (search snippet); another study found reports containing stack traces can *hurt* some IR tools. Boosting was not implemented. What we did observe: Lang-2's report contains 49 stack-frame lines from an *unrelated* project (Maven Surefire / TestNG), Lang-1 and Lang-3 contain none; stripping those lines (`clean_query`, `strip_stack_traces`) improves the IR ranking on Lang-2 (e.g. TF-IDF buggy-file rank 5 -> 1).
- **Similar-bug history** (BugLocator), **code-change history** (BLIA), **query reformulation**, **deep-learning retrieval**, **call-frequency tie-breaking**: all need data or models beyond this single-project set-up.

## 7. Cosine similarity audit (done in this repo)

`scripts/run/cosine_audit.py` checks the paper's cosine (formula 1) on Lang-1/2/3:
our implementation equals scikit-learn's `cosine_similarity` and SciPy's cosine distance to 1e-16, stays in [0, 1], is symmetric and
scale-invariant, and returns 0 for a zero vector. The weakness is the **weighting**, not the arithmetic: for the top-ranked
(wrong) file, 88-100% of the cosine comes from terms present in more than half of all files ("not", "string", "java", "method").
See `results/experiments/cosine_audit_*.csv`.
