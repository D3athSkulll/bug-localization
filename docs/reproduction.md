# Reproduction status - Lang-1 ONLY (scope decided 2026-10-14: complete working of this single bug)
Not a reproduction of the paper's 373-bug numbers; nothing here is claimed to match them.

1. Environment: Windows 11 native; JDK 8 (Temurin 8u504); Python 3.7.16 (legacy) / 3.12.4 (modern); JaCoCo 0.8.12; Defects4J v1.4.0 metadata.
2. Commits: see docs/baseline.md.  3. Defects4J version: 1.4.0 (metadata only; the Defects4J CLI was not run, see environment-audit.md).
4. Bug evaluated: Lang-1 (LANG-747, NumberUtils.createNumber hex handling; buggy lines 467, 468, 471 of NumberUtils.java).
5. Bug report: Apache Jira LANG-747, summary + description -> data/bug_reports/Lang-1.json.
6. Source processing: all 108 .java files under src/main/java of the buggy checkout.
7. IR (now follows paper II-A): lowercase 2+ char word tokens, Java keywords and stop words removed, raw word-frequency vectors, cosine (formula 1). The authors' repo script (TF-IDF, no removal) is kept as ir_mode "tfidf". Buggy file rank: 8/108 (paper-style) vs 1/108 (TF-IDF). Paper does not say how identifiers are split; we do not split them (assumption).
8. k: fraction of files, ceil(k*N); k=0.5 headline, 0.1..0.9 swept (results/raw/Lang-1_tf_*_sweep_k.csv). The buggy file is inside the top-k for every k from 0.1 to 0.9 (rank 8 of 108).
9. Spectrum: JaCoCo line coverage per test method (executable source line = statement; main classes only). Two test scopes: Defects4J relevant tests (173 tests) and the full Lang suite (2290 tests). Failing = Defects4J trigger test only (TestLang747); 7 other failures in the full suite (locale/JDK 8 vs 7 differences) are removed, as Defects4J does. Abstract test base classes are skipped.
10. Reduction (paper II-B): drop coverage outside the top-k files, then drop tests that cover nothing left; nf is counted on the reduced test set.
11. Ochiai: ef/sqrt((ef+nf)(ef+ep)), 0 if denominator 0.  12. DStar: ef^2/(ep+nf), inf if ep+nf=0 and ef>0 (exponent 2 is an assumption).
13. Ranking: descending score; ties -> worst-case rank by default; worst/average/best are all recorded.
14. Metrics: rank = best-ranked buggy statement; TOP@N counts bugs with rank <= N; MRR = mean(1/rank). Answer key = lines changed by the fix diff (git diff buggy fixed); evaluation only.
15. Results (k=0.5, paper-style IR). Rank worst/average/best:
   relevant tests (173):  Ochiai 6/3.5/1 | ISBL-Ochiai 6/3.5/1 | DStar 6/3.5/1 | ISBL-DStar 6/3.5/1   (statements 981 -> 913)
   full suite (2273):     Ochiai 6/3.5/1 | ISBL-Ochiai 6/3.5/1 | DStar 6/3.5/1 | ISBL-DStar 6/3.5/1   (statements 11102 -> 6593)
   Worst-case ties: TOP@1/3/5 = 0/0/0, MRR 0.167. Best-case ties: rank 1.
   Why identical: six lines of NumberUtils.java (462, 463, 467, 468, 471, 474) are executed by exactly the same four tests - the failing TestLang747 and three passing tests (testCreateNumber, testCreateNumberMagnitude, testIsNumber) - so they have identical (ef,ep,nf,np) = (1,3,0,166) and tie at Ochiai 0.50 / DStar 0.33. Three of the six (467, 468, 471) are the buggy lines. No test can separate them because no test executes one of these lines without the others. The IR filter removes unrelated statements (up to 41%) but cannot split tied lines inside the buggy file, so the best statement rank does not change. On this bug ISBL = plain Ochiai/DStar. (An earlier version of this note wrongly said ep = 0; the --explain output corrects that.)
16-18. Paper comparison: not possible with one bug. Open discrepancies: tie handling and DStar exponent unspecified in the paper; BugLocator/Gharibi filters not implemented; JaCoCo instead of Defects4J's coverage tool; commit hashes remapped to GitHub history; Maven instead of Defects4J's Ant; TypeUtilsTest excluded (javac 8).
Note: an earlier draft run used the full suite WITHOUT the trigger-test filter and showed ISBL beating DStar (rank 67 -> 33). That was an artifact of 17 spurious failing tests (abstract classes run directly + JDK/locale failures) and is superseded by the numbers above.
Tests: 49 unit tests pass on Python 3.7 and 3.12.
Run: .\scripts\run\demo.ps1 | python -m isbl.baseline.pipeline configs\lang1_k50.json (relevant tests) or configs\lang1_k50_alltests.json (full suite, ~2.5 min on first run).

## Profiling and extra metrics (added 2026-10-14)
Every run now logs per-stage wall-clock time (results/raw/<tag>_timing.csv, printed table) and, for each method row, IR / spectrum / localisation diagnostics (results/raw/<tag>.csv and .json).
Where the time goes (Lang-1, k=0.5):
| scope | total | coverage collection (JVM+JaCoCo) | everything else |
| relevant tests (173) | 9.9 s | 9.7 s (98%) | 0.2 s |
| full suite (2280)    | 231.9 s | 231.1 s (99.6%) | ~0.8 s |
Inside the JVM run, the JaCoCo class analysis that is repeated after EVERY test takes 97.7% (relevant) / 93.5% (full suite) of the time; running the project's tests takes only 0.6% / 6.0% (13.9 s for 2280 tests). Candidate optimisation (not yet done): analyse only classes whose probes were hit by the test, or compute the probe->line map once per class, instead of re-analysing all classes per test. IR (0.12 s), spectrum construction, SFL scoring and metrics are all negligible at one-bug scale; IR and SFL scoring would only matter at hundreds of bugs.
New metrics (per row): IR - buggy-file rank/percentile (= smallest k that keeps it), buggy-file cosine, top-1 cosine, top1-top2 gap, score entropy (candidate adaptive-k signal), files with cosine>0, recall@k; spectrum - matrix density, avg statements/test, avg tests/statement; reduction - % statements and tests removed; localisation - exam score, wasted effort, mean/median buggy rank, #distinct scores, tie-group size containing the best buggy line and how many of it are buggy, buggy-line score vs top score, TOP@10.
Lang-1 reading: only 5 distinct score values over 913 statements; the best buggy line sits in a 6-way tie (3 of 6 buggy), so exam score is tiny (0.0066) but TOP@N is 0 under worst-case ties - the problem is ties, not the retrieval.
Tests: 104 unit tests (python 3.7 and 3.12; 63 for the baseline, 41 added with the IR models, hybrid ranking, metrics and answer key).
