# Experiments: better IR models, more metrics, other Lang bugs, hybrid ranking

Written for: the project owner and the faculty reviewer. Date of results: 2026-10-25.
**Scope: Lang-1, Lang-2 and Lang-3 only (3 bugs of Defects4J's 395; the ISBL paper uses 373).** The differences below
are small counts and indicative only; no significance is claimed. No parameter was tuned on these bugs: every
configuration was fixed in advance (see `isbl/experiments/engine.py`).

## 1. What was asked and what was done

| Request | Done |
|---|---|
| Add more metrics for comparison | File level: Top@1/5/10, MRR, MAP, nDCG@10, recall@k% of files. Statement level: TOP@1/3/5 (worst-case and average ties), MRR (3 tie rules), MAP, nDCG@10, recall@10, EXAM, wasted effort, win/draw/lose vs Ochiai, bootstrap CI, Wilcoxon p (`isbl/evaluation/metrics.py`) |
| Check the cosine similarity properly | `scripts/run/cosine_audit.py`: arithmetic verified against scikit-learn and SciPy; properties verified; per-term diagnosis of why the wrong file wins (section 3) |
| Try tf-idf and more proper IR measures | 12 models in `isbl/baseline/ir_models.py`: raw-tf cosine (paper), authors' tf-idf, smoothed tf-idf, sublinear tf-idf, BM25, BugLocator rVSM, Dirichlet language model, Jaccard, containment, LSI, BLUiR-style structured BM25, rank fusion; plus options: identifier splitting, stemming, licence-header removal, stack-trace cleaning, class-name bonus |
| Webscrape relevant papers for new metrics, add to the code | `docs/literature.md` (11 sources, abstracts/snippets only) and the code additions it maps to |
| Find more types of bugs | Three different bug types (below), plus 9 more SFL formulas and a hybrid ranking that uses the bug report to break spectrum ties |
| Run on other Lang bugs | Lang-2 and Lang-3 prepared with `scripts/bugs/prepare_lang_bug.py` (commit mapping, Defects4J patch, JDK 8 compile, Jira report, coverage, trigger-test sanity check) |

## 2. The three bugs

| Bug | Jira | Type | Buggy lines (answer key) | Tests | Statements | Report |
|---|---|---|---|---|---|---|
| Lang-1 | LANG-747 | wrong condition (counts hex digits instead of checking the value) | `NumberUtils.java` 467, 468, 471 | 173 | 981 | 662 chars |
| Lang-2 | LANG-879 | missing validation (omission of a guard clause) | `LocaleUtils.java` 92 (line after the missing guard) | 14 | 208 | 8,265 chars, contains 49 stack-frame lines of an **unrelated** project |
| Lang-3 | LANG-693 | missing precision branches (omission of conditional guards) | `NumberUtils.java` 593, 597, 601, 605 | 172 | 979 | 480 chars |

How a bug is built (all on Windows, no Defects4J command line): find the fixing commit in the Apache history whose tree
accepts Defects4J's `N.src.patch`, check it out in a `git worktree`, apply the patch (it turns the fixed source into the buggy source),
keep the fixed tests, compile with Maven on JDK 8, run the Defects4J relevant tests under the per-test JaCoCo runner, and **require that every Defects4J trigger test fails**
(otherwise the bug is rejected). Lessons: the Windows clone of Defects4J has CRLF patch files, which had to be normalised to LF; test files javac 8 cannot compile
(`TypeUtilsTest`) are removed, as for Lang-1. The answer key is read directly from the Defects4J patch (`isbl/baseline/answer_key.py`);
for an omission bug it is the first buggy line after the gap (same rule as before).

## 3. Cosine audit (the paper's formula 1, raw term frequency)

| Check | Result |
|---|---|
| Our cosine vs scikit-learn `cosine_similarity` | max abs difference 4e-17 to 6e-17 on all three bugs; identical ranking |
| Our cosine vs SciPy `cosine` distance | max abs difference 8e-17 to 1.1e-16 |
| Properties | values in [0, 1]; self-similarity 1; symmetric; unchanged when the query counts are multiplied by 7; zero vector gives 0 |

So the arithmetic is right; the **weighting** is the problem. For the top-ranked (wrong) file, the share of its cosine that comes from words occurring in more than half of all files is 91% (Lang-1: `Validate.java`, driven by "not", "string"), 100% (Lang-2: `JavaVersion.java`, driven by "java", "org", "apache" from the pasted trace) and 88% (Lang-3: `MethodUtils.java`, driven by "method"). The buggy file is ranked 8th, 23rd and 16th. The paper's stop-word list is not published; ours does not contain "not" (a likely difference). Details: `results/experiments/cosine_audit_*.csv`.

## 4. File level: which IR configuration ranks the buggy file best?

(`|` in names is shown as `/`.) Rank of the buggy file among 108 files, Lang-1 / Lang-2 / Lang-3. Preprocessing: `paper` = Java keywords and stop words removed; `split+stem` = also licence header removed, identifiers split, Snowball stemming; `+clean` = stack-frame lines removed from the report; `+name` = bonus for a class name that occurs in the report.

| IR configuration | buggy-file rank | Top@1 | Top@5 | MRR | MAP | nDCG@10 | recall@10% files |
|---|---|---|---|---|---|---|---|
| bm25 / split+stem +name | 1/1/1 | 3 | 3 | 1.000 | 1.000 | 1.000 | 1.00 |
| rvsm / paper | 1/1/1 | 3 | 3 | 1.000 | 1.000 | 1.000 | 1.00 |
| rvsm / split+stem +clean | 1/1/1 | 3 | 3 | 1.000 | 1.000 | 1.000 | 1.00 |
| tfidf_authors / none | 1/1/1 | 3 | 3 | 1.000 | 1.000 | 1.000 | 1.00 |
| tfidf_smooth / paper | 1/1/1 | 3 | 3 | 1.000 | 1.000 | 1.000 | 1.00 |
| tfidf_sublinear / paper | 1/1/1 | 3 | 3 | 1.000 | 1.000 | 1.000 | 1.00 |
| tfidf_sublinear / split+stem +clean | 1/1/1 | 3 | 3 | 1.000 | 1.000 | 1.000 | 1.00 |
| tfidf_sublinear / split+stem +name | 1/1/1 | 3 | 3 | 1.000 | 1.000 | 1.000 | 1.00 |
| rvsm / split+stem | 1/2/1 | 2 | 3 | 0.833 | 0.833 | 0.877 | 1.00 |
| bluir_like / split+stem +clean | 1/3/1 | 2 | 3 | 0.778 | 0.778 | 0.833 | 1.00 |
| lm_dirichlet / split+stem +clean | 1/5/1 | 2 | 3 | 0.733 | 0.733 | 0.796 | 1.00 |
| lsi / split+stem | 1/5/1 | 2 | 3 | 0.733 | 0.733 | 0.796 | 1.00 |
| tfidf_sublinear / split+stem | 1/5/1 | 2 | 3 | 0.733 | 0.733 | 0.796 | 1.00 |
| rrf(bm25,tfidf,rvsm) / split+stem | 1/6/1 | 2 | 2 | 0.722 | 0.722 | 0.785 | 1.00 |
| bm25 / paper | 1/8/1 | 2 | 2 | 0.708 | 0.708 | 0.772 | 1.00 |
| bm25 / split+stem +clean | 1/9/1 | 2 | 2 | 0.704 | 0.704 | 0.767 | 1.00 |
| bluir_like / split+stem | 1/11/1 | 2 | 2 | 0.697 | 0.697 | 0.667 | 1.00 |
| bm25 / split+stem | 1/26/1 | 2 | 2 | 0.679 | 0.679 | 0.667 | 0.67 |
| lm_dirichlet / split+stem | 1/35/1 | 2 | 2 | 0.676 | 0.676 | 0.667 | 0.67 |
| jaccard / paper | 1/5/2 | 1 | 3 | 0.567 | 0.567 | 0.673 | 1.00 |
| containment / paper | 1/8/2 | 1 | 2 | 0.542 | 0.542 | 0.649 | 1.00 |
| tf_cosine / paper +clean | 8/10/16 | 0 | 0 | 0.096 | 0.096 | 0.202 | 0.67 |
| **tf_cosine / paper (the ISBL paper)** | **8/23/16** | 0 | 0 | 0.077 | 0.077 | 0.105 | 0.33 |

Reading (3 bugs, so a ceiling effect hides differences between the top rows):
- Every idf-weighted model (tf-idf variants, rVSM, LSI) ranks the buggy file 1st on Lang-1 and Lang-3. The paper's raw-tf cosine is last.
- On Lang-2 the pasted trace hurts: removing stack frames moves the buggy file 23 -> 10 (raw tf), 5 -> 1 (tf-idf), 2 -> 1 (rVSM), 11 -> 3 (BLUiR-like), 35 -> 5 (LM); BM25 improves only 26 -> 9.
- Identifier splitting and stemming are not an automatic win: on Lang-2 the buggy file falls from 1st to 5th (tf-idf), from 1st to 2nd (rVSM) and from 8th to 26th (BM25) when `split+stem` is switched on.
- The worst cases are rank 35 (Dirichlet LM, `split+stem`, Lang-2) and rank 26 (BM25, `split+stem`, Lang-2); recall@25% of files is 0.67 for the LM, 1.00 for the others.

### 4b. False exclusion: does the top-k filter throw the buggy file away?

This is the failure mode the ISBL paper itself names (Math-51 there). "lost" = bugs (of 3) whose buggy file is not among the kept files, so the bug cannot be localised;
"cut" = mean share of the spectrum's statements removed (a lost bug inflates the cut, so read the two together).

| IR configuration | k = 10%: lost / cut | k = 25%: lost / cut | k = 50%: lost / cut |
|---|---|---|---|
| **tf_cosine / paper (the ISBL paper)** | **2/3 / 62%** | 0/3 / 19% | 0/3 / 5% |
| tf_cosine / paper +clean | 1/3 / 47% | 0/3 / 19% | 0/3 / 5% |
| tfidf_sublinear / paper | 0/3 / 47% | 0/3 / 24% | 0/3 / 14% |
| tfidf_sublinear / split+stem +clean | 0/3 / 46% | 0/3 / 27% | 0/3 / 15% |
| rvsm / paper | 0/3 / 44% | 0/3 / 27% | 0/3 / 15% |
| bluir_like / split+stem +clean | 0/3 / 46% | 0/3 / 21% | 0/3 / 9% |
| bm25 / paper | 0/3 / 46% | 0/3 / 20% | 0/3 / 7% |
| bm25 / split+stem | 1/3 / 48% | 0/3 / 29% | 0/3 / 11% |
| lm_dirichlet / split+stem | 1/3 / 71% | 1/3 / 69% | 0/3 / 51% |

(all 23 configurations: `results/experiments/false_exclusion.csv`, sheet `False_Exclusion`.) With the paper's raw-tf IR the filter has to stay at k >= 25% to be safe on these bugs and then removes only 19% (k = 25%) or 5% (k = 50%) of the statements; a tf-idf, rVSM or BLUiR-style ranking keeps the buggy file even at k = 10% while cutting 44-47% of the spectrum. **That, not a different statement ranking, is where a better IR step pays off here.**

## 5. Statement level

Best buggy-statement rank per bug (Lang-1/2/3) with tied statements averaged; "worst" counts a tied statement at the end of its tie group.

| Method | rank per bug (ties averaged) | TOP@1/3/5 (worst-case ties) | MRR worst | MRR avg | MAP avg | EXAM avg | W/D/L vs Ochiai |
|---|---|---|---|---|---|---|---|
| SFL: Ochiai (also DStar, Tarantula, Jaccard, Op2, Barinel, Kulczynski2, Ochiai2, Sorensen-Dice, DStar3) | 3.5 / 3 / 3.5 | 0/0/2 | 0.206 | 0.302 | 0.327 | 0.0072 | 0/3/0 |
| SFL: Wong2 | 628 / 201 / 631 | 0/0/0 | 0.003 | 0.003 | 0.004 | 0.7503 | 0/0/3 |
| ISBL, raw-tf IR (the paper), k = 0.5, Ochiai | 3.5 / 3 / 3.5 | 0/0/2 | 0.206 | 0.302 | 0.327 | 0.0072 | 0/3/0 |
| ISBL, tf-idf + clean, k = 0.5, Ochiai | 3.5 / 3 / 3.5 | 0/0/2 | 0.206 | 0.302 | 0.327 | 0.0072 | 0/3/0 |
| Hybrid tie_file (+ file IR score), k = 0.5 | 3.5 / 3 / 3.5 | 0/0/2 | 0.206 | 0.302 | 0.329 | 0.0072 | 0/3/0 |
| **Hybrid tie_text (+ statement text), k = 0.5** | **2 / 3 / 2** | **0/2/3** | 0.417 | 0.444 | 0.376 | 0.0062 | 2/1/0 |
| **Hybrid tie_file_text, k = 0.5** | **2 / 3 / 2** | **0/2/3** | 0.417 | 0.444 | 0.377 | 0.0062 | 2/1/0 |
| Hybrid linear a = 0.3, k = 0.5 | 3.5 / 3 / 3.5 | 0/0/2 | 0.206 | 0.302 | 0.329 | 0.0072 | 0/3/0 |
| Hybrid linear a = 0.3, b = 0.3, k = 0.5 | 2 / 6 / 5 | 0/1/2 | 0.281 | 0.289 | 0.297 | 0.0120 | 1/0/2 |

(The hybrid rows use TF-IDF with split+stem and +clean as the IR model; all eight IR models in `HYBRID_IR` behave the same, see `results/experiments/statement_level_summary.csv`.)

Findings:
1. **No SFL formula beats Ochiai here** (Wong2 is far worse). Lines with identical (ef, ep, nf, np) get identical scores under every formula, so formula choice cannot break the ties that dominate these bugs (tie groups of 6, 3 and 4).
2. **A better file ranking does not change the statement ranking when the buggy file survives the filter** (it does for every model at k = 50%): the ties are inside the buggy file. What changes is how aggressively the spectrum can be cut safely (section 4b): at k = 50% the paper's raw-tf IR removes 6.9% / 0% / 7.2% of the statements of Lang-1/2/3 and tf-idf + clean removes 19.9% / 0% / 25.4%; at k = 10% tf-idf + clean removes 43.1% / 54.3% / 40.3% with the buggy file kept, while the paper's raw-tf IR loses the buggy file on 2 of 3 bugs (their ISBL rows then have no buggy statement to rank).
3. **Exact-tie breaking with the report's words on each statement helps**: expected rank 3.5 -> 2 on Lang-1 and Lang-3 (worst-case 6 -> 2 and 5 -> 2), no change on Lang-2. TOP@3 goes from 0 to 2 bugs under worst-case ties. Caveat: the *best*-case rank on Lang-1 gets worse (1 -> 2): the method narrows the uncertainty of the tie, it does not guarantee rank 1.
4. **How scores are combined matters**: a lexicographic key (SFL score first, text only for exact ties) helps; a normalised linear blend with the same information is worse than plain Ochiai (1 win, 2 losses).
5. The file score as a tie-breaker changes nothing, because tied statements share a file.

Selection caveat: `tie_text` / `tie_file_text` were the best of 12 hybrid variants evaluated on these same three bugs (all variants are in the CSV and in the `Hybrid_Modes` sheet). Treat the result as a hypothesis to confirm on more bugs.

## 6. Reproduce

```powershell
. .\scripts\setup\env.ps1
python scripts\bugs\prepare_lang_bug.py 2 3     # one-time: needs Maven, internet (Maven Central, Apache Jira), JDK 8 in tools\
python scripts\run\cosine_audit.py              # cosine correctness and diagnosis
python scripts\run\run_experiments.py           # all tables, about 50 s (coverage is cached)
envs\modern312\Scripts\python scripts\run\build_excel_experiments.py   # results\Lang-1-2-3_experiments.xlsx
python -m pytest -q tests                       # 104 tests
```

## 7. Limits and what is not done

- Three bugs from one project; the other 62 Lang bugs and the other five projects are not run (the preparation script supports `all`, but each bug needs a Maven compile and downloads).
- IR/hybrid configurations are not tuned (by design), and with n = 3 the bootstrap CI and Wilcoxon columns are not informative.
- Not implemented: BugLocator's similar-bug history, stack-trace boosting, call-frequency tie-breaking, learned/semantic retrieval. The BLUiR-style model uses regex field extraction, not a Java parser.
- Relevant tests only (Defects4J's list); the full-suite spectrum was only compared for Lang-1.
- Statement text score and hybrid modes are our own exploratory extension, not part of the ISBL paper.
