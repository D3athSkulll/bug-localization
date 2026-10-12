# ISBL Reproduction Workspace

Local, Windows-native reproduction of the paper **"Statement-level Software Bug Localization based on Information Retrieval and Spectrum"** (Li, Yue, Lan, Cui; IEEE SMC 2023).

> **Status (2026-10-15): one bug (Defects4J Lang-1) works end to end. The paper is NOT reproduced.**
> The paper evaluates 373 bugs; this workspace has run 1. Nothing here is claimed to match the paper's numbers.
> The upstream clones, JDK and Python environments are not stored in this repository; see "Setting up from a fresh clone" below.

---

## 1. What the project is

A bug is hidden somewhere in a large program. The paper's method (ISBL) finds the buggy **line** using two clues:

| Clue | Question it answers | How |
|---|---|---|
| Bug report (text) | Which **files** look related to the complaint? | Compare the report's words with each source file's words (cosine similarity) and keep the top k% of files. |
| Tests (pass/fail + which lines ran) | Which **lines** do the failing tests point at? | Record which lines each test runs, then score each line with a formula (**Ochiai** or **DStar**). |

ISBL does the file filter first, so only lines inside likely files compete in the scoring. The paper claims this beats plain Ochiai/DStar.

## 2. Pipeline (what runs, in order)

```
START  scripts/run/demo.ps1  (sets Java 8 + Python 3.7)
  :
  v
Checkout buggy Lang-1, compile, run tests ........ scripts/run/smoke_lang1.sh   -> 1 test fails
  :
  v
INPUT  bug report (data/bug_reports/Lang-1.json) + config (configs/lang1_k50.json, k = 50%)
  :
  v
[A] IR step ...................................... isbl/baseline/ir.py
    cosine(bug report, each of 108 files) -> keep top 50% = 54 files
  :
  v
[B] Coverage ..................................... isbl/baseline/java/CoverageRunner.java + JaCoCo
    run tests, record which lines each test executes (and pass/fail)
  :
  v
    Clean: only Defects4J's documented trigger test counts as failing
  :
  +-----------------------------+
  v                             v
FULL spectrum                  REDUCED spectrum (paper section II-B)
(no IR filter)                 drop lines of dropped files, then drop tests covering nothing left
  :                             :
  v                             v
[C] Score every line: Ochiai and DStar ........... isbl/baseline/sfl.py
  :                             :
  +-------------+---------------+
                v
    Rank lines (ties: worst / average / best) .... isbl/baseline/ranking.py
                v
[D] Compare with the real buggy lines ............ isbl/evaluation/metrics.py, diagnostics.py
    (answer key = lines changed by the developers' fix; never used by the search)
                v
END    results/raw/*.csv, *.json, *_timing.csv  + printed tables
```

An older HTML flowchart is in `docs/flowchart.html` (first version of the pipeline only).

## 3. The bug: Defects4J Lang-1 (LANG-747)

- **Project:** Apache Commons Lang, method `NumberUtils.createNumber(String)` in `org/apache/commons/lang3/math/NumberUtils.java`.
- **Symptom:** `createNumber("0x80000000")` throws `NumberFormatException: For input string: "80000000"`.
- **Cause:** the code decides between `int` and `long` by counting hex digits. Eight hex digits are treated as `int`, but a value from `0x80000000` to `0xFFFFFFFF` does not fit in an `int`.
- **Real buggy lines (answer key):** lines **467, 468 and 471** of `NumberUtils.java`.
- **Failing test:** `TestLang747` in `NumberUtilsTest`. It matches Defects4J's own recorded failure (`defects4j/framework/projects/Lang/trigger_tests/1`).
- **Versions:** buggy commit `396afc3e4693cfee182efe582455f2d97058c068`, fixed commit `d1a45e9738de5b3e299bb51e987565dcce55fee6` (apache/commons-lang GitHub hashes, matched by patch because Defects4J's own mirror is offline).

## 4. Results (Lang-1, k = 50%)

All numbers come from `results/raw/`. "Rank" is the best-ranked real buggy line. Ties are reported three ways because the paper does not say how to break them.

### 4.1 Main result, relevant tests (173 tests)

| Method | Tests used | Statements | Rank worst / avg / best | TOP@1 / 3 / 5 (worst ties) | MRR (worst ties) |
|---|---|---|---|---|---|
| Ochiai | 173 | 981 | 6 / 3.5 / 1 | 0 / 0 / 0 | 0.1667 |
| ISBL + Ochiai | 170 | 913 | 6 / 3.5 / 1 | 0 / 0 / 0 | 0.1667 |
| DStar | 173 | 981 | 6 / 3.5 / 1 | 0 / 0 / 0 | 0.1667 |
| ISBL + DStar | 170 | 913 | 6 / 3.5 / 1 | 0 / 0 / 0 | 0.1667 |

With best-case ties the rank is 1, so TOP@1/3/5 = 1/1/1 and MRR = 1.0. With average ties the rank is 3.5.

### 4.2 Full Lang test suite (2,273 tests after cleaning)

| Method | Tests used | Statements | Rank worst / avg / best | MRR (worst ties) |
|---|---|---|---|---|
| Ochiai | 2273 | 11,102 | 6 / 3.5 / 1 | 0.1667 |
| ISBL + Ochiai | 1569 | 6,593 | 6 / 3.5 / 1 | 0.1667 |
| DStar | 2273 | 11,102 | 6 / 3.5 / 1 | 0.1667 |
| ISBL + DStar | 1569 | 6,593 | 6 / 3.5 / 1 | 0.1667 |

The IR filter removes **40.6%** of statements here, and the buggy line's rank is unchanged.

### 4.3 What the IR (text matching) step found

| Metric | Value |
|---|---|
| Buggy file | `math/NumberUtils.java` |
| Buggy file IR rank | **8 of 108** |
| Smallest k that keeps it | 7.4% (any k from 10% to 90% keeps it) |
| Buggy file cosine / top-1 cosine | 0.1198 / 0.1560 (`Validate.java`) |
| Gap between top-1 and top-2 | 0.0024 |
| Score entropy | 6.65 bits (max for 108 files is about 6.75, so the scores are almost flat) |
| Files kept at k = 50% | 54 of 108 |

### 4.4 Why the filter did not help on this bug

| Fact | Value |
|---|---|
| Lines tied at the top score | 6 (lines 462, 463, 467, 468, 471, 474) |
| Of those, real buggy lines | 3 (467, 468, 471) |
| Tests that run those six lines | 4: the failing `TestLang747` plus passing `testCreateNumber`, `testCreateNumberMagnitude`, `testIsNumber` |
| (ef, ep, nf, np) of each tied line | (1, 3, 0, 166) |
| Ochiai / DStar score of each tied line | 0.50 / 0.33 |
| Distinct score values across 913 statements | only 5 |
| Exam score (share of the list read) | 0.0061 plain, 0.0066 with ISBL |

No test runs one of the six lines without the others, so no spectrum formula can separate them. The IR filter removes unrelated statements but cannot split ties inside the one file that must stay. **On this bug, ISBL equals plain Ochiai/DStar.**

### 4.5 Effect of k (relevant tests, ISBL)

| k | Files kept | Buggy file kept? | Statements | Rank worst / avg / best |
|---|---|---|---|---|
| 10% | 11 | yes | 481 | 6 / 3.5 / 1 |
| 20% | 22 | yes | 671 | 6 / 3.5 / 1 |
| 30% | 33 | yes | 811 | 6 / 3.5 / 1 |
| 40% | 44 | yes | 913 | 6 / 3.5 / 1 |
| 50% | 54 | yes | 913 | 6 / 3.5 / 1 |
| 60% to 80% | 65 to 87 | yes | 913 | 6 / 3.5 / 1 |
| 90% | 98 | yes | 981 | 6 / 3.5 / 1 |

The result is the same at every k, because the buggy file always survives and the tie is inside it.

### 4.6 Where the time goes

| Scope | Total | Coverage collection (JVM + JaCoCo) | All other stages |
|---|---|---|---|
| Relevant tests (173) | 9.9 s | 9.7 s (98%) | about 0.2 s |
| Full suite (2,280 tests) | 231.9 s | 231.1 s (99.6%) | under 1 s |

Inside the JVM coverage run:

| Part | Relevant tests | Full suite |
|---|---|---|
| JaCoCo class analysis, repeated after every test | 97.7% | 93.5% |
| Running the project's own tests | 0.6% | 6.0% (13.9 s for 2,280 tests) |
| JaCoCo dump of coverage data | 0.1% | 0.1% |
| JVM startup and other | 1.5% | 0.4% |

IR (about 0.12 s), spectrum building, scoring and metrics are negligible at one-bug scale. A repeated-analysis fix is the obvious first optimisation, but it is not implemented. (A run right after opening the editor can show `01 load_source_files` as slow because the disk cache is cold. That is not a real bottleneck.)

## Setting up from a fresh clone (Windows)

Run from the repository root (Git Bash for the `bash`/`mvn` lines).

```bash
# 1. Pinned upstream sources (ignored by git)
git clone https://github.com/rjust/defects4j.git && git -C defects4j checkout v1.4.0
git clone https://github.com/Naplues/buglocalization.git && git -C buglocalization checkout bbd67ea65956748cc17a9c26e076aa9933a03008
git clone https://github.com/apache/commons-lang.git work-lang

# 2. Portable Temurin JDK 8 (8u504) unzipped to tools/jdk8u504-b01 (no admin rights needed)
# 3. JaCoCo 0.8.12 + ASM jars, then compile the per-test coverage runner
source scripts/setup/env.sh
mvn -f scripts/setup/jacoco-pom.xml dependency:copy-dependencies -DoutputDirectory=tools/jacoco
mkdir -p tools/runner && javac -cp "tools/jacoco/*" -d tools/runner isbl/baseline/java/CoverageRunner.java

# 4. Python environments
conda create -p envs/legacy37 python=3.7 -y && envs/legacy37/python -m pip install -r requirements/legacy.txt pytest==7.4.4
py -3.12 -m venv envs/modern312 && envs/modern312/Scripts/python -m pip install -r requirements/modern.txt -r requirements/development.txt

# 5. Check out, compile and test Lang-1 (buggy source + fixed-commit tests), then write the test classpath
bash scripts/run/smoke_lang1.sh
(cd work-lang && mvn -q dependency:build-classpath -Dmdep.outputFile=../data/cp.txt)
```

`data/cp.txt` holds absolute paths for this machine and is not committed. The first pipeline run needs `--recollect` to create the coverage file.

## 5. How to run it

All commands are for PowerShell, from this folder.

```powershell
cd <path-to-this-repository>

# 1. Full demo: versions, checkout, compile, failing test, 63 unit tests, baseline with explanations (about 1 minute)
.\scripts\run\demo.ps1
# if PowerShell blocks scripts:
powershell -ExecutionPolicy Bypass -File .\scripts\run\demo.ps1

# 2. Just the baseline with all the printed tables (Java 8 + Python 3.7 on the PATH first; note the dot-space)
. .\scripts\setup\env.ps1
python -m isbl.baseline.pipeline configs\lang1_k50.json --explain

# 3. Unit tests only
python -m pytest -q tests

# 4. Full Lang test suite (about 4 minutes the first time; add --recollect to re-run coverage)
python -m isbl.baseline.pipeline configs\lang1_k50_alltests.json

# 5. k sweep from 10% to 90%
python scripts\run\sweep_k.py configs\lang1_k50.json

# 6. Excel workbook: one sheet per results CSV, plus a formula-driven Summary and a Guide
envs\modern312\Scripts\python scripts\run\build_excel.py     # writes results\Lang-1_results.xlsx
```

Open `results\Lang-1_results.xlsx` in Excel (formulas calculate when it opens; previewers that do not calculate may show blank summary cells).

Flags for the pipeline: `--explain` prints the cosine table and the coverage matrix. `--recollect` re-runs the tests and JaCoCo instead of reading the saved coverage file.

## 6. Output files (in `results/raw/`)

| File | Contents |
|---|---|
| `Lang-1_tf_relevant_k0.5.csv` / `.json` | Result row per method, with TOP@N, MRR and all extra metrics |
| `..._timing.csv` | Seconds and share per pipeline stage, plus the JVM breakdown |
| `..._ir_cosine.csv` | Cosine similarity of all 108 files |
| `..._spectrum_scores.csv` | ef, ep, nf, np, Ochiai, DStar and rank for each statement |
| `..._coverage_matrix.csv` | Full test x statement matrix (open in Excel) |
| `..._sweep_k.csv` | The k sweep |
| `Lang-1_tf_all_*` | The same files for the full-suite scope |

Metrics logged per method row: TOP@1/3/5/10, MRR, worst/average/best rank, IR buggy-file rank and percentile, cosine, top-1 gap, score entropy, recall@k, matrix density, statements and tests removed, exam score, wasted effort, mean and median buggy rank, number of distinct scores, tie-group size and how many of it are buggy.

## 7. Repository layout

```
configs/                lang1_k50.json (relevant tests), lang1_k50_alltests.json (full suite)
data/                   bug reports, saved coverage files, classpath (git-ignored)
docs/                   environment-audit.md, baseline.md, reproduction.md, flowchart.html
isbl/baseline/          ir.py, spectrum.py, sfl.py, ranking.py, timing.py, report.py, pipeline.py
isbl/baseline/java/     CoverageRunner.java (per-test JaCoCo coverage + its own timing)
isbl/evaluation/        metrics.py (TOP@N, MRR), diagnostics.py (extra metrics)
requirements/           legacy.txt (py3.7), modern.txt (py3.12), development.txt
results/raw/            all outputs
scripts/setup/          env.ps1, env.sh (put Java 8 + Python 3.7 on the PATH)
scripts/run/            demo.ps1, smoke_lang1.sh, sweep_k.py
tests/                  63 unit tests
tools/, envs/           portable JDK 8, JaCoCo, compiled runner; Python environments
buglocalization/        Naplues/buglocalization @ bbd67ea6 (contains the authors' IR script and BugLocator)
defects4j/              rjust/defects4j, tag v1.4.0 @ fcf6b9bb
work-lang/              scratch checkout of apache/commons-lang (the program being debugged)
```

## 8. Environment

| Item | Version |
|---|---|
| OS | Windows 11, native (WSL not used) |
| Java | Temurin OpenJDK 1.8.0_504 (portable, `tools/`) |
| Python, historical | 3.7.16 (`envs/legacy37`), numpy 1.21.6, scikit-learn 1.0.2 |
| Python, modern | 3.12.4 (`envs/modern312`), numpy 2.5.3, scikit-learn 1.9.1 |
| Coverage tool | JaCoCo 0.8.12 |
| Defects4J | v1.4.0 (metadata only; the Defects4J command line never ran) |
| Build | Maven 3.9.9 |
| Perl | 5.38.2 (Git for Windows). SVN not installed. |

## 9. Tests

63 unit tests pass on Python 3.7 and 3.12 (`python -m pytest -q tests`). They cover cosine similarity (identical, orthogonal, zero and empty vectors, repeated terms, keywords, camelCase and snake_case), Ochiai and DStar edge cases (all tests fail, all pass, covered by every test, covered by none), spectrum reduction, ranking ties, TOP@N and MRR (rank 1, 3, 5, beyond N, missing and multiple buggy lines), the extra diagnostics, and the timer. One test checks that the IR matches the authors' scikit-learn pipeline to 1e-9.

## 10. Known differences from the paper (all unresolved)

1. **File filters.** The paper uses BugLocator (rVSM) and Gharibi to filter files. This workspace implements only a plain vector-space version with raw term frequency, Java keyword and stop-word removal. Neither paper tool is implemented.
2. **Identifier splitting** is not done, because the paper does not say. `ir_mode: "tfidf"` (the authors' repo script) is available as an alternative, and it ranks the buggy file 1st instead of 8th.
3. **Tie handling and the DStar exponent** (set to 2) are my assumptions. The paper states neither, and its printed DStar formula is garbled in the PDF.
4. **Coverage tool.** JaCoCo line coverage replaces Defects4J's own coverage tooling. Only main-code lines are counted as statements.
5. **Failing tests.** Only the Defects4J trigger test counts as failing. Seven other failures in the full suite (locale and Java 8 versus 7 differences) were removed, and abstract test base classes are skipped.
6. **Workarounds.** Commit hashes were remapped to GitHub history, Maven replaces Defects4J's Ant, and `TypeUtilsTest.java` was excluded because javac 8 cannot compile it.
7. **Repository assumption.** `buglocalization` is Naplues/buglocalization, chosen from a GitHub name search and not confirmed. It contains no ISBL or Defects4J code, so ISBL here is rebuilt from the paper's text.

## 11. What is not done

- Only 1 of 373 bugs, in 1 of 6 projects.
- No comparison with the paper's Table III (Ochiai TOP@1/3/5 = 36/84/105, MRR 0.217; ISBL 40/86/109, MRR 0.224) or Table IV (k sweep).
- BugLocator and Gharibi filters.
- The Defects4J command line (needs SVN and Perl modules; its project download host is gone).
- Coverage-speed optimisation.
- No improvements (BM25, TF-IDF comparison, identifier splitting, semantic retrieval, adaptive k).
- The tag `baseline-authors-v1` and branch `research-improvements` from the original plan are not created.
- `docs/architecture.md` is empty, and `docs/experiments.md` does not exist.

## 12. Glossary

- **IR (information retrieval):** ranking files by how similar their words are to the bug report.
- **Cosine similarity:** a score from 0 to 1 for how alike two word-count vectors are.
- **Spectrum:** the record of which lines each test executes, plus each test's pass/fail result.
- **ef / ep / nf / np:** for one line, the number of failing tests that run it, passing tests that run it, failing tests that miss it, and passing tests that miss it.
- **Ochiai:** `ef / sqrt((ef + nf) * (ef + ep))`. **DStar:** `ef^2 / (ep + nf)`. Higher means more suspicious.
- **k:** the share of top-ranked files kept as suspicious (50% in the paper's recommended setting).
- **TOP@N:** the number of bugs whose real buggy line is in the top N of the ranking. **MRR:** the average of 1/rank.
- **Exam score:** buggy rank divided by the number of statements, the share of the list a developer reads. **Wasted effort:** statements read before the bug.
- **Tie group:** statements with exactly the same score as the buggy line.

## 13. More detail

`docs/reproduction.md` (step-by-step answers to the plan's 18 questions), `docs/baseline.md` (pinned versions and commands), `docs/environment-audit.md` (what was found and the blockers).
