# IRE project presenter guide

Companion to the 20-slide PowerPoint, in presentation order. The **Say** paragraph is the spoken explanation. The questions below it are for discussion or viva preparation. Unless a slide says otherwise, values refer to the three-bug Commons Lang experiment in the local checkout at commit `59d1a02`.

## 01. Statement-level bug localization

**Say.** Our IRE project ranks executable Java lines to help a developer decide where to inspect first. We combine the text of a Jira bug report with line coverage from passing and failing tests. The right side shows the opening example. On Lang-1, six lines of `NumberUtils.java` get the same Ochiai score of 0.500. The developer’s patch marks three of those six lines as buggy. This example gives us two research questions. Can text retrieval keep the right file in a smaller shortlist? Can text about the individual line improve the order when tests give equal scores?

- **What does ISBL stand for?** Statement-level bug localization based on information retrieval and spectrum. The reference method filters source files by text and then scores lines using test coverage.
- **Does a high score prove a line caused the bug?** It prioritizes a line for inspection. The analyst still diagnoses the defect and validates a fix.

[Supplied Li et al. paper](../Statement-Level_Software_Bug_Localization_Based_on_Information_Retrieval_and_Spectrum.pdf) · [Lang-1 spectrum scores](../ire-buglocalization/results/raw/Lang-1_tf_relevant_k0.5_spectrum_scores.csv)

## 02. What the project localizes

**Say.** At file level, the report is a query and each Java file is a document. The IR model ranks the 108 files by textual evidence. At statement level, each candidate is a covered source line, identified by file and line number. The spectrum ranks those candidates using observed test behavior. We compared plain spectrum-based fault localization (SFL), ISBL with a file cutoff, and our hybrid reranking. We then checked where the answer-key lines appear in the lists.

- **Why run three kinds of methods?** Plain SFL gives the coverage-only baseline. ISBL measures what changes after file filtering. Hybrid ranking measures what happens when report text also helps order the lines.
- **Why talk about line coverage when the paper says “statement”?** The local implementation uses JaCoCo executable Java source lines as proxies for statements. Multiple Java statements can share one mapped line.
- **What is the study’s scope?** Three Apache Commons Lang bugs from Defects4J v1.4.0. The paper reports 373 buggy versions across six projects. Our sample supports a case study and a working local reconstruction.

[Experiment design](../ire-buglocalization/docs/experiments.md) · [Supplied paper, Sections II–III](../Statement-Level_Software_Bug_Localization_Based_on_Information_Retrieval_and_Spectrum.pdf)

## 03. Dataset and answer key

**Say.** Lang-1 is a wrong condition. A hex value such as `0x80000000` has eight digits, but exceeds the signed 32-bit integer maximum `0x7FFFFFFF`. Lang-2 lacks a locale-validation guard. Its patch-derived location is line 92. Lang-3 lacks precision-related conditions and has four answer-key locations. The listed tests and lines are the relevant-test full spectra before IR filtering. We ran the buggy code with JDK 8, Maven-built classes and per-test JaCoCo. The documented Defects4J trigger had to fail for acceptance.

- **How did you get buggy Java revisions on Windows?** Lang-1 uses a mapped Apache history commit and relevant fixed-side tests. For Lang-2/3, the preparation script locates a fixed commit, applies the Defects4J source patch in the direction that recreates buggy source, and keeps the trigger-reproducing tests.
- **How can a missing line have a line number?** The answer-key parser uses the first existing buggy-side line after the omission as the scoring location. It is a proxy for the gap.
- **Could the fix leak into ranking?** Source and report text, test outcomes and observed coverage drive the rank. The patch supplies reference labels for scoring after ranking.

[Experiment workbook, Bugs sheet](../ire-buglocalization/results/Lang-1-2-3_experiments.xlsx) · [Preparation and limits](../ire-buglocalization/docs/experiments.md) · [Answer-key parser](../ire-buglocalization/isbl/baseline/answer_key.py)

## 04. Previous pipeline

**Say.** Follow the top row from left to right. The first implementation tokenized the bug report and Java sources, removed Java keywords and selected stop words, counted terms, and ranked files by cosine. Lang-1 kept the top 54 files at a 50% cutoff. The second row starts separately with the JaCoCo test spectrum. The file shortlist restricts line coverage. Tests covering no remaining lines are dropped, then spectrum counts are rebuilt. Follow the bottom row from right to left. Ochiai or DStar scores the lines, ties are ranked, and the patch grades the result. Plain SFL follows the full-spectrum branch and supplies the comparison.

- **Why rebuild the counts?** Filtering can remove test rows as well as candidate columns. The failing/passing totals used by the formulas must come from that reduced test set.
- **Can the file filter save the cost of collecting coverage?** In this implementation, the runner gathers per-test coverage before applying the file filter. The filter reduces the candidates ranked and inspected. Coverage-runner optimization addresses a different cost.
- **Is this the exact published retrieval tool?** This is our raw-TF implementation of the filter idea. The paper’s main experiments used the BugLocator and Gharibi tools.

[Original pipeline diagram](../ire-buglocalization/docs/images/pipeline_original.png) · [Baseline pipeline](../ire-buglocalization/isbl/baseline/pipeline.py)

## 05. Updated pipeline

**Say.** The updated experiments run the same architecture across three bugs. The report side compares 12 model families across 23 configurations, with optional stack-frame cleaning, identifier splitting, stemming, license removal and class-name matching. The test side uses the faster per-test coverage runner. We score full or reduced spectra and compare spectrum-only ranks with hybrid sort keys. Evaluation now records file retrieval, statement ranking, search effort, exclusion and paired comparisons. The raw coverage, scores and summaries go to separate CSVs and Excel sheets.

- **Do all 11 SFL formulas run with every IR model?** The SFL-only comparison runs all 11. The ISBL and hybrid comparisons use Ochiai and DStar. ISBL uses 10%, 25% and 50% cutoffs. The hybrid grid uses 50% and 100%.
- **What does 100% mean in the hybrid grid?** Every file is eligible, so there is no file exclusion by IR score. The file and text scores can still affect the hybrid order.
- **Is cleaning applied to both text signals?** It is optional for the file ranker. The implementation caches a separate statement-text score from the original report using the split-and-stem preprocessing settings.

[Updated pipeline diagram](../ire-buglocalization/docs/images/pipeline_new.png) · [Experiment engine](../ire-buglocalization/isbl/experiments/engine.py)

## 06. Coverage and suspiciousness

**Say.** For each line, `ef` counts failing tests that executed it and `ep` counts passing tests that executed it. `nf` and `np` count failing and passing tests that skipped it. In the reduced Lang-1 spectrum, the six tied lines each have `(ef, ep, nf, np) = (1, 3, 0, 166)`. Therefore Ochiai is `1 / sqrt(1 × 4) = 0.500` and DStar with exponent 2 is `1² / (3 + 0) = 0.333`. There are 170 tests because `1 + 3 + 0 + 166 = 170`.

The other implemented formulas use the same four counts:

| Formula | Implemented expression |
|---|---|
| Tarantula | `f / (f + p)`, with `f = ef/(ef+nf)` and `p = ep/(ep+np)` |
| Jaccard | `ef / (ef + nf + ep)` |
| Sørensen–Dice | `2ef / (2ef + nf + ep)` |
| Kulczynski2 | `0.5 × [ef/(ef+nf) + ef/(ef+ep)]` |
| Op2 | `ef − ep/(ep+np+1)` |
| Barinel | `1 − ep/(ep+ef)` when `ep+ef > 0`, otherwise 0 |
| Wong2 | `ef − ep` |
| Ochiai2 | `ef×np / sqrt[(ef+ep)(nf+np)(ef+nf)(ep+np)]` |
| DStar3 | `ef³ / (ep + nf)` |

- **What happens at DStar’s zero denominator?** The scorer gives positive infinity if a failing test covers the line and the denominator is zero. It gives zero when the numerator is also zero. Hybrid ranking replaces infinity with one more than the maximum finite score to preserve its priority.
- **Why can a different formula still leave the tie?** Identical inputs yield identical outputs for any deterministic formula over the four counts. Extra evidence must distinguish the lines.

[SFL formulas](../ire-buglocalization/isbl/baseline/sfl.py) · [Lang-1 coverage and spectrum workbook](../ire-buglocalization/results/Lang-1_results.xlsx)

## 07. Information retrieval models

**Say.** Raw cosine measures the angle between the query and file token-count vectors. It length-normalizes the comparison, but frequently shared terms can still account for most of the dot product. Smoothed TF-IDF uses `idf(t) = ln[(N+1)/(df(t)+1)] + 1`. The sublinear variant replaces a positive term count with `1 + ln(tf)`. For a term found in all 108 files, the smoothed IDF is 1. For a term found in one file, it is `1 + ln(109/2) ≈ 5.00`. The two changes give rare matches more influence and reduce the effect of repeated terms.

Use these definitions if asked about the other rankers:

| Model | How its score is formed |
|---|---|
| Authors-style TF-IDF | Raw TF with unsmoothed IDF `1 + ln(N/df)`, fitted over the files plus query, then cosine |
| Smoothed TF-IDF | Raw TF times smoothed IDF, then cosine |
| BM25 | `Σ qtf(t) × idf_B(t) × tf(t,d)(k₁+1) / [tf(t,d)+k₁(1−b+b·L/avgL)]`. `idf_B(t)=ln[1+(N−df+0.5)/(df+0.5)]`, `k₁=1.2`, `b=0.75` |
| rVSM | Cosine using log TF and `ln(N/df)` multiplied by `1/(1+exp(−x))`. `x` is min-max normalized file token count |
| Dirichlet language model | Sum over in-vocabulary query tokens of `ln[(tf(t,d)+μ·p(t|collection))/(L+μ)]`, with `μ=2000` and `L` the document token count |
| LSI | Project normalized sublinear TF-IDF vectors onto up to 50 right-singular directions, then compute cosine |
| Jaccard and containment | `|Q∩D|/|Q∪D|` and `|Q∩D|/|Q|`, with sets of distinct query and file tokens |
| BLUiR-style | Sum BM25 scores over report fields and class, method, identifier and comment fields extracted with regular expressions |
| Reciprocal rank fusion | `Σ 1/(60 + rank_model(file))` across the configured rankers |

- **Is rVSM the full BugLocator implementation?** It is the text similarity component with a length factor. The project has no similar-bug history component.
- **Does preprocessing always help?** Lang-2’s sublinear TF-IDF file rank changes from 1 with the basic preprocessing to 5 with split-and-stem, then returns to 1 with stack-frame cleaning.

[IR implementation](../ire-buglocalization/isbl/baseline/ir_models.py) · [Project literature scan](../ire-buglocalization/docs/literature.md)

## 08. Cosine audit and query noise

**Say.** The audit compared our raw-TF cosine with scikit-learn and with one minus SciPy’s cosine distance. The scikit-learn comparison preserved file order for every bug. The largest SciPy difference was about `1.1 × 10⁻¹⁶`. The audit also checked symmetry, self-similarity, zero vectors and invariance when the query counts were multiplied by seven. In Lang-2, copied stack frames inject words such as `java`, `org` and `apache`. The wrong top file, `JavaVersion.java`, gets effectively all its dot-product contribution from terms found in more than half of the files.

- **How did you calculate a word’s contribution?** For a shared term, divide `tf(t,q) × tf(t,d)` by the query–document dot product. The cosine denominator is constant across terms of the same pair, so it cancels when taking a share.
- **Did removing stack frames solve the raw-TF ranking?** It moved `LocaleUtils.java` from rank 23 to rank 10. Cleaned sublinear TF-IDF put it at rank 1. These are separate settings.
- **What does the numerical agreement establish?** The score arithmetic behaves as intended for the raw-TF experiment. Retrieval quality depends on which tokens the vectors represent and how they are weighted.

[Audit correctness CSV](../ire-buglocalization/results/experiments/cosine_audit_correctness.csv) · [Term contributions](../ire-buglocalization/results/experiments/cosine_audit_why.csv)

## 09. First-hit ranking metrics

**Say.** Let `r_b` be the lowest rank assigned to any answer-key item for bug `b`. `TOP@N = sum over bugs of 1[r_b ≤ N]`. It is a count. `MRR = (1/B) × sum over bugs of 1/r_b`, with zero contribution from a missing answer. If a tie group occupies positions `a…b`, best rank is `a`, worst is `b`, and average rank is `(a+b)/2`. For the six tied first-place lines on Lang-1, those are 1, 6 and 3.5. Average-tie reciprocal rank is `1/3.5 = 0.286`.

- **Why report three tie rules?** A developer could inspect equally scored lines in different orders. Reporting the range and midpoint shows how sensitive the result is to the tie convention.
- **Is 1/3.5 the expected reciprocal rank of randomly shuffling those lines?** It is the reciprocal of the assigned midpoint. The experiment uses that deterministic convention. Random shuffling would require a separate calculation, especially with three buggy lines in the tie group.
- **What cutoffs appear in the outputs?** File summaries report Top@1/5/10. The three-bug line summaries report TOP@1/3/5 with worst and average ties, and MRR with all three tie rules. The raw baseline also logs TOP@10.

[Metrics implementation](../ire-buglocalization/isbl/evaluation/metrics.py) · [Statement summary](../ire-buglocalization/results/experiments/statement_level_summary.csv)

## 10. Metrics for all relevant items

**Say.** MRR asks how soon the first relevant item appears. MAP, nDCG and recall also use subsequent relevant items. Let `R` count all answer-key items and `r_i` be sorted retrieved relevant-item ranks. The implemented `AP = Σ(i/r_i)/R`, then MAP averages AP over bugs. For Lang-1, three buggy lines share average rank 3.5, so AP is `(1+2+3)/(3×3.5) ≈ 0.571`. Binary `DCG@K = Σ 1/log₂(r_i+1)` over relevant ranks up to `K`. Divide by the ideal DCG with `min(R,K)` relevant items in the first positions. Lang-2 has one relevant line at average rank 3, so nDCG@10 is `1/log₂(4) = 0.500`.

- **How do recall and precision differ?** Recall divides hits in the first `K` positions by `R`. Lang-3 has one of its four buggy lines within the top ten, giving 0.25. Precision divides the hits by `K`. The helper is implemented, while the standard experiment tables report recall.
- **What if the filter drops relevant items?** They contribute no terms to the sum. AP and recall still divide by the complete answer key. The implementation uses fractional and shared average ranks directly when calculating statement-level MAP, nDCG and recall.
- **When do file-level MRR and MAP coincide?** Here there is exactly one buggy file per bug. Its AP and reciprocal rank are both `1/r`, so their across-bug averages are equal.

[Metrics code](../ire-buglocalization/isbl/evaluation/metrics.py) · [Per-bug line metrics](../ire-buglocalization/results/experiments/statement_level_per_bug.csv)

## 11. Inspection effort and uncertainty

**Say.** EXAM is the first-hit rank divided by a line count. The three-bug experiment uses the same full-spectrum count for every method on a given bug. For Lang-1, rank 3.5 gives `3.5/981 ≈ 0.003568`, or 0.357%. Wasted effort is `r−1`, so the assigned average rank gives 2.5 earlier positions. The raw baseline uses the current list length. A worst rank of 6 therefore gives `6/981 ≈ 0.612%` before filtering and `6/913 ≈ 0.657%` after filtering. In the three-bug summary, missing EXAM and wasted effort values are blank and excluded from those means. Read them alongside success and exclusion.

- **How do you calculate a win, draw or loss?** Compare average-tie first-hit ranks per bug against plain Ochiai. A lower rank wins, an equal rank draws and a higher rank loses. A missed line counts as worse than any ranked line. Two misses draw.
- **How are the statistical fields calculated?** A seeded 2,000-resample percentile bootstrap gives a 95% interval for mean reciprocal rank. The two-sided Wilcoxon signed-rank test compares paired average ranks. The code encodes a miss as a large rank for that test and leaves identical comparisons blank. With three cases these fields cannot support a general superiority claim.
- **What other diagnostics did you record?** Coverage density is executed test–line pairs divided by total matrix cells. A tie-group count is the number of lines sharing the score. The raw outputs also track removed tests and lines, counts of distinct scores, mean and median buggy-line rank, cosine gap between the two top files, and score entropy `−Σ p log₂ p` after normalizing the positive cosine scores.

[Diagnostics code](../ire-buglocalization/isbl/evaluation/diagnostics.py) · [Statement metric definitions](../ire-buglocalization/isbl/evaluation/metrics.py) · [Experiment workbook, Metric_Guide](../ire-buglocalization/results/Lang-1-2-3_experiments.xlsx)

## 12. Buggy-file ranks by retrieval model

**Say.** Lower file rank is better. The embedded project output image covers Lang-1 and Lang-2. Use the table for the comparison including Lang-3. Raw-TF cosine ranks the buggy files 8, 23 and 16, so file MRR is `(1/8+1/23+1/16)/3 ≈ 0.077`. Cleaned raw TF improves only Lang-2 in that row and gives MRR 0.096. Cleaned sublinear TF-IDF with split-and-stem and basic rVSM both rank the buggy file first on all three bugs. Across the full grid, eight of the 23 configurations hit that ceiling.

- **Does the ceiling tell us which of those eight is best?** All eight have the same first-hit file outcome on this sample. Their lower-ranked files and coverage retained at a cutoff still differ.
- **How many raw-TF bugs hit the top ten?** One of three, because only rank 8 is at most 10. Cleaned raw TF hits two of three, at ranks 8 and 10. The reported file top thresholds are absolute ranks, while recall@10% keeps 11 files.
- **How should we present the improvement?** Say the weighted models gave better file ranks on these three bugs. Statement-level performance is a separate experiment.

[File-level summary CSV](../ire-buglocalization/results/experiments/file_level_summary.csv) · [File-level workbook](../ire-buglocalization/results/Lang-1-2-3_experiments.xlsx) · [Report chart](../ire-buglocalization/docs/images/fig_file_rank.png)

## 13. Filter size and false exclusion

**Say.** The shortlist keeps `max(1, ceil(k×N))` files. At 10% of 108, that means 11 files. Statement cut is `1 − S_retained/S_full`, averaged over bugs. At 10%, raw TF removes 61.9% of statements on average while losing Lang-2 and Lang-3. Cleaned sublinear TF-IDF keeps all three bugs and removes 45.9% on average. For Lang-2 specifically, that model retains 95 of 208 lines, so `(208−95)/208 ≈ 54.3%`. As we increase the cutoff, exclusion risk drops and the shortlist usually keeps more lines.

- **Why not judge the largest cut as the best?** It can look large because it eliminated the lines we need to find. Compare statement cut with the number of missed bugs.
- **What does “lost” mean in the CSV?** The script counts cases in which zero answer-key statements survive the reduced spectrum. On these runs each bug has one answer-key file and its buggy lines are present in the full spectrum, so the observed misses match file exclusion. The file-level recall independently checks the shortlist.
- **Can a 50% file cutoff remove zero covered lines?** Yes. For Lang-2, the 14 relevant tests touch a small set of files, and raw TF at 50% keeps every covered file. The percentage of files kept and the percentage of lines cut have different denominators.

[False-exclusion CSV](../ire-buglocalization/results/experiments/false_exclusion.csv) · [Statement counts per bug](../ire-buglocalization/results/experiments/statement_level_per_bug.csv)

## 14. Lang-1 baseline and cutoff sweep

**Say.** At a 50% cutoff, relevant tests go from 173 to 170 and 981 covered lines become 913. The cut is `(981−913)/981 = 6.9%`. In the full-suite run, the collector executes 2,280 tests. We remove seven failures outside the documented trigger set, leaving 2,273 tests. Filtering reduces the comparison from 11,102 lines to 6,593, a 40.6% cut. Both test scopes give the same best buggy-line ranks under worst, average and best ties, `6 / 3.5 / 1`. In the relevant-test sweep, the number of lines retained changes from 481 to 981, while the same tie remains.

- **Why does full-suite coverage yield a larger cut?** It covers more lines in unrelated files. The relevant selection is already concentrated around the target area.
- **Why does every sweep point keep the buggy file?** Raw TF puts `NumberUtils.java` at rank 8. The smallest tested cutoff retains 11 files. The raw workbook’s `8/108 = 7.4%` is the rank percentile, and the actual selection uses ceiling rounding.
- **What happened to the seven extra failures?** They were excluded from the analysis rather than relabeled as passing. Defects4J identifies the Lang-1 trigger failure.

[Lang-1 baseline workbook](../ire-buglocalization/results/Lang-1_results.xlsx) · [Relevant-test cutoff sweep](../ire-buglocalization/results/raw/Lang-1_tf_relevant_sweep_k.csv) · [Full-suite cutoff sweep](../ire-buglocalization/results/raw/Lang-1_tf_all_sweep_k.csv)

## 15. Statement ranking with SFL and ISBL

**Say.** Ochiai’s average-tie first-hit ranks are 3.5, 3 and 3.5. The matching worst ranks are 6, 4 and 5. Their mean reciprocal rank is `(1/6 + 1/4 + 1/5)/3 = 0.206`, and two cases reach the top five. At 50%, both ISBL examples reproduce the same first-hit ranks. Stronger IR helped us keep the target when the cutoff was smaller. Picking a better file still leaves the six-, three- and four-line groups tied at the relevant buggy scores on these cases.

- **Which formulas match Ochiai on first hit?** DStar, DStar3, Tarantula, Jaccard, Sørensen–Dice, Kulczynski2, Op2, Barinel and Ochiai2. Some positions deeper in the ranking can change, so small MAP differences still occur.
- **Why did Wong2 do poorly?** It directly subtracts passing coverage, `ef−ep`. On Lang-1, a buggy line with `1−3 = −2` falls behind unrelated lines scoring zero. That behavior accounts for the low first-hit ranks here.
- **Does a 50% cutoff always preserve the ranking?** It did for the first-hit results under the tested filters and these three bugs. Different test or candidate sets can change the counts or which competing lines remain.

[Statement-level summary CSV](../ire-buglocalization/results/experiments/statement_level_summary.csv) · [SFL implementation](../ire-buglocalization/isbl/baseline/sfl.py)

## 16. Hybrid ranking by statement text

**Say.** The hybrid extension adds two signals. `F` is the ranking score of the statement’s file, min-max normalized across files. `T` is the sum of `ln(1+N/df(t))` over distinct tokens shared by the statement and report. Repeating a matching term on the same line contributes once. A descending tuple `(S,T)` compares spectrum score `S` first and uses `T` if `S` is equal. `(S,F,T)` compares file score before line text within an exact spectrum tie. The linear variant uses `(1−a−b)S̃+aF̃+bT̃` after scaling the three scores within the candidate set. The grid also includes `S̃(1+aF̃)`.

- **Why would a rare word help?** In the text score, a shared token seen in fewer files receives a larger weight. Its wording also needs to occur in the report and on the line.
- **What is min-max scaling?** `(x−min)/(max−min)`. When all values are equal, the implementation returns zero for each.
- **Why compare tuples and blends?** The tuple preserves the primary spectrum order and reorders tied lines. A blend can move a line over a different spectrum score group. That added freedom can help or harm.

[Hybrid ranker](../ire-buglocalization/isbl/baseline/hybrid.py) · [Hybrid experiment grid](../ire-buglocalization/isbl/experiments/engine.py)

## 17. Why text breaks some ties

**Say.** In the Lang-1 image, the original best buggy-line rank ranges from 1 to 6, with average 3.5. Statement text gives line 474, `return createInteger(str)`, a score of 7.007 and first place because it matches report terms strongly. The first actual buggy line, 467, has a text score of 5.979 and moves to rank 2. Lines 468 and 471 share 4.771 and take worst rank 4. In Lang-2, line 92 ties with lines 89 and 93, with text scores of zero, so the three-way tie occupies positions 2 to 4 under both approaches.

- **Did the hybrid improve every tie rule on Lang-1?** Worst rank improves from 6 to 2 and average rank from 3.5 to 2. Best-case rank moves from 1 to 2 because a nonbuggy line now leads.
- **Why did the file-only score fail to split those lines?** Each group is inside a single source file, so every tied line has the same file score.
- **Why can Lang-2 be hard to score from line text?** The answer key points to a line next to a missing guard. An adjacent surviving line may have few words used in the report.

[Repository tie-range figure](../ire-buglocalization/docs/images/fig_ties.png) · [Line-by-line discussion in REPORT.md](../ire-buglocalization/docs/REPORT.md)

## 18. Hybrid results across the three bugs

**Say.** With cleaned sublinear TF-IDF, 50% of files and Ochiai, statement-text tie-breaking improves Lang-1 and Lang-3 and draws on Lang-2. Average-tie ranks go from `3.5, 3, 3.5` to `2, 3, 2`. Worst-tie ranks go from `6, 4, 5` to `2, 4, 2`. Consequently worst-case TOP@3 goes from 0 to 2 and worst-tie MRR becomes `(1/2 + 1/4 + 1/2)/3 ≈ 0.417`. With average ties, the hybrid MRR is `(1/2 + 1/3 + 1/2)/3 ≈ 0.444`, compared with 0.302 for plain Ochiai.

- **What else improved?** Average-tie MAP increases from 0.327 to 0.376 for statement text. Average nDCG@10 increases from 0.443 to 0.492. Recall@10 stays at 0.75, so the gain is mostly earlier placement of relevant lines already near the top. Mean EXAM drops from 0.719% to 0.617%, and mean wasted effort drops from 2.333 to 1.333 positions.
- **Why can the linear blend increase worst-tie MRR but lose more cases?** It gains strongly on Lang-1, but its average ranks worsen on Lang-2 and Lang-3. Different summaries emphasize different aspects of the same outcomes. Its win/draw/loss is 1/0/2.
- **Can we call the hybrid statistically better?** The comparison is exploratory. The text modes were selected from the settings evaluated on the same three bugs. The statement-text vs Ochiai Wilcoxon value is about 0.157 in the saved run.

[Hybrid and baseline summary](../ire-buglocalization/results/experiments/statement_level_summary.csv) · [Hybrid_Modes workbook sheet](../ire-buglocalization/results/Lang-1-2-3_experiments.xlsx)

## 19. Run outputs and checks

**Say.** A raw run produces outcome and coverage evidence, file cosine ranks, spectrum counts and scores, timing and method-level results. The experiment adds per-bug and summary tables, plus exclusion and audit CSVs. The Lang-1 workbook has results, sweeps, IR scores and a coverage matrix. The three-bug workbook adds file and statement summaries, hybrid modes, cosine audit and a metric guide. Its core data sheets were checked against the CSVs by configuration and bug keys. In the local verification run, all eight experiment CSVs matched, the fresh relevant coverage runs passed the trigger checks for Lang-1/2/3, and 104 unit tests passed on Python 3.12.

**Demo order.** From the repository root after setting up the local dependencies, show the report title → buggy-file rank → coverage evidence → suspicious line rank → the workbook summary. These are the main commands:

```powershell
. .\scripts\setup\env.ps1
python -m isbl.baseline.pipeline configs\lang1_k50.json --recollect --explain
python -m pytest -q tests
python scripts\run\cosine_audit.py
python scripts\run\run_experiments.py
envs\modern312\Scripts\python scripts\run\build_excel_experiments.py
```

- **Can the Excel summary look empty in a previewer?** The workbooks contain formula-driven views. Use Excel to recalculate them. The CSVs and imported data tabs carry the values used in this presentation.
- **What accounts for the reported speedup?** The report’s comparable Lang-1 timings go from about 9.5 s to 1.15 s for the JVM coverage run, about 8×. The runner now analyzes only executed classes rather than all classes after each test. The report records identical coverage output in its before/after check. The current rerun has different absolute timings. Cached-coverage timings measure a different path.
- **Which parts of the check had environment limits?** The Python 3.7 run had 101 passes and three temporary-path fixture errors under Windows sandboxing. The repository’s Edge-based documentation PDF build produced no PDF here. The existing Markdown, local figure links and published source PDF were inspectable, and the Graphviz diagrams and report images regenerated. The local checkout and cached `origin/main` were both at `59d1a02`. A live check of the GitHub remote could not connect. Older README sections describe the first Lang-1-only milestone and the original coverage runner. Use the experiment CSVs and the current experiment engine for the current scope and comparisons.

[Lang-1 workbook](../ire-buglocalization/results/Lang-1_results.xlsx) · [Three-bug workbook](../ire-buglocalization/results/Lang-1-2-3_experiments.xlsx) · [Workflow in README](../ire-buglocalization/README.md)

## 20. Findings and limits

**Say.** Close with two empirical findings. The retrieval improvement gave the filter room to be more selective. At 10%, cleaned sublinear TF-IDF kept every buggy file in this sample and cut 45.9% of covered lines on average. The ranking improvement came from applying line text to within-score ties. That moved two first hits earlier and left the Lang-2 omission example unchanged. The experiments use three bugs from a single project, with relevant test sets for the cross-bug comparison and a full-suite comparison for Lang-1. The published method and our implementation also differ in the retrieval tools and coverage setup.

- **Did we reproduce the published table?** We rebuilt and exercised the core filtering-and-scoring method. The paper’s 373-version experiment used different IR tools and wider coverage. This project evaluates the listed local cases.
- **What evidence would test whether these findings generalize?** A larger, held-out set of bugs across projects, with a fixed evaluation protocol and paired comparisons for retrieval, exclusion and line ranking.
- **Which implementation assumptions should we say out loud?** We use JaCoCo executable lines, an explicit tie policy, DStar exponent 2, and an adjacent location for missing code. The report-text hybrid is a project extension. Our rVSM covers the text component of BugLocator, and BLUiR-style fields are extracted with regular expressions.

[Experiment limits](../ire-buglocalization/docs/experiments.md) · [Project report](../ire-buglocalization/docs/REPORT.md) · [Supplied paper](../Statement-Level_Software_Bug_Localization_Based_on_Information_Retrieval_and_Spectrum.pdf)


