# ISBL Bug Localization Workspace

This repository reproduces the core filtering-and-scoring idea from **“Statement-level Software Bug Localization based on Information Retrieval and Spectrum”** (Li, Yue, Lan, and Cui, 2023) and adds a local three-bug experiment.

> **Current scope:** Lang-1, Lang-2, and Lang-3 from Defects4J 1.4.0 are prepared and runnable. This is a reconstruction and case study, not a reproduction of the paper's 373-bug results. The repository does not claim to match the paper's published numbers.

## What it does

ISBL combines bug-report text with test-coverage evidence:

1. Rank Java source files using the bug report as a query.
2. Keep the top `k%` of files.
3. Build a spectrum from passing and failing tests restricted to those files.
4. Score executable source lines with spectrum formulas such as Ochiai or DStar.
5. Compare the ranking with patch-derived answer-key lines.

The statement-level candidates are JaCoCo executable Java source lines. A single line can represent multiple Java statements, and the answer key may point to the first existing buggy-side line for an omitted guard.

## Results at a glance

The latest cross-bug experiment uses relevant tests and records file ranking, false exclusion, statement ranking, tie behavior, and hybrid ranking variants.

| Item | Lang-1 | Lang-2 | Lang-3 |
|---|---|---:|---:|
| Jira bug | LANG-747 | LANG-879 | LANG-693 |
| Bug type | Wrong condition | Missing validation | Missing precision guards |
| Buggy lines | 467, 468, 471 | 92 | 593, 597, 601, 605 |
| Relevant tests | 173 | 14 | 172 |
| Statements in the full spectrum | 981 | 208 | 979 |
| Raw-TF buggy-file rank | 8 / 108 | 23 / 108 | 16 / 108 |
| Sublinear TF-IDF buggy-file rank | 1 / 108 | 1 / 108 | 1 / 108 |

Key findings:

- Eight of 23 tested IR configurations rank every buggy file first in this three-bug sample.
- Raw-TF cosine loses the buggy file in 2 of 3 bugs at a 10% file cutoff, while sublinear TF-IDF keeps all three.
- The 10% sublinear-TF-IDF run removes about 46% of covered statements on average.
- Ochiai and the other identical-count spectrum formulas cannot split statement ties because equal coverage counts produce equal scores.
- The exploratory statement-text tie-breaker improves average-tie ranks from `3.5, 3, 3.5` to `2, 3, 2`; it makes no change on Lang-2.
- These are indicative results from three bugs, not evidence of general superiority.

Full tables and caveats are in [`docs/experiments.md`](docs/experiments.md). The full narrative report is [`docs/REPORT.md`](docs/REPORT.md).

## Repository layout

```text
configs/                 Baseline and experiment configurations
data/                    Bug reports and saved coverage
docs/                    Reproduction notes, report, metrics, architecture and figures
isbl/baseline/           IR, spectrum, SFL, ranking and pipeline code
isbl/evaluation/         Metrics and diagnostics
isbl/experiments/        Cross-bug experiment engine
results/                 CSV summaries and Excel workbooks
scripts/bugs/            Lang bug preparation
scripts/run/             Demos, experiments, sweeps and workbook builders
scripts/setup/           Windows/JDK/Python environment setup
tests/                   Unit tests
```

## Prerequisites

The Windows-native setup is documented in [`docs/reproduction.md`](docs/reproduction.md), [`docs/baseline.md`](docs/baseline.md), and [`docs/environment-audit.md`](docs/environment-audit.md).

Required external workspaces and tools are:

- Temurin OpenJDK 8
- Maven
- JaCoCo 0.8.12
- Python 3.7 for the legacy environment or Python 3.12 for the modern environment
- A buggy-side Apache Commons Lang checkout
- Defects4J metadata for Lang-1, Lang-2, and Lang-3

The upstream repositories, JDK, compiled runner, virtual environments, and machine-specific classpaths are intentionally not stored in git.

## Fresh setup on Windows

Clone the pinned external sources, install Java 8 and JaCoCo, and create both Python environments:

```powershell
git clone https://github.com/rjust/defects4j.git
git -C defects4j checkout v1.4.0

git clone https://github.com/apache/commons-lang.git work-lang

source scripts/setup/env.sh
mvn -f scripts/setup/jacoco-pom.xml dependency:copy-dependencies -DoutputDirectory=tools/jacoco
mkdir -p tools/runner
javac -cp "tools/jacoco/*" -d tools/runner isbl/baseline/java/CoverageRunner.java

conda create -p envs/legacy37 python=3.7 -y
envs/legacy37/python -m pip install -r requirements/legacy.txt pytest==7.4.4

py -3.12 -m venv envs/modern312
envs/modern312/Scripts/python -m pip install -r requirements/modern.txt -r requirements/development.txt
```

Prepare Lang-1 and write its classpath:

```bash
bash scripts/run/smoke_lang1.sh
(cd work-lang && mvn -q dependency:build-classpath -Dmdep.outputFile=../data/cp.txt)
```

For Lang-2 and Lang-3, run:

```powershell
. .\scripts\setup\env.ps1
python scripts\bugs\prepare_lang_bug.py 2 3
```

## Run the baseline

All commands below run from the repository root.

```powershell
# Activate Java 8 and the Python environment
. .\scripts\setup\env.ps1

# Lang-1 baseline with printed explanation
python -m isbl.baseline.pipeline configs\lang1_k50.json --explain

# Recollect JaCoCo coverage instead of using the saved matrix
python -m isbl.baseline.pipeline configs\lang1_k50.json --recollect --explain

# Relevant-test file and statement sweep
python scripts\run\sweep_k.py configs\lang1_k50.json

# Full Lang-1 suite
python -m isbl.baseline.pipeline configs\lang1_k50_alltests.json

# Lang-2 or Lang-3
python -m isbl.baseline.pipeline configs\bugs\Lang-2.json --explain
python -m isbl.baseline.pipeline configs\bugs\Lang-3.json --explain
```

Use `configs/lang1_tfidf_sublinear.json` to run Lang-1 with sublinear TF-IDF instead of the paper-style raw-TF cosine.

## Run the three-bug experiments

```powershell
. .\scripts\setup\env.ps1

# Cosine arithmetic audit and shared-term diagnosis
python scripts\run\cosine_audit.py

# 23 IR configurations, SFL formulas, cutoffs and hybrid modes
python scripts\run\run_experiments.py

# Build the combined Excel workbook
envs\modern312\Scripts\python scripts\run\build_excel_experiments.py

# Optional presenter/demo summary
.\scripts\run\demo_experiments.ps1
```

The cached experiment run writes:

- [`results/experiments/file_level_summary.csv`](results/experiments/file_level_summary.csv)
- [`results/experiments/file_level_per_bug.csv`](results/experiments/file_level_per_bug.csv)
- [`results/experiments/statement_level_summary.csv`](results/experiments/statement_level_summary.csv)
- [`results/experiments/statement_level_per_bug.csv`](results/experiments/statement_level_per_bug.csv)
- [`results/experiments/false_exclusion.csv`](results/experiments/false_exclusion.csv)
- [`results/Lang-1-2-3_experiments.xlsx`](results/Lang-1-2-3_experiments.xlsx)

Raw baseline outputs are in [`results/raw/`](results/raw/).

## Tests

Run:

```powershell
python -m pytest -q tests
```

The suite covers cosine behavior, identifier preprocessing, SFL edge cases, spectrum reduction, ranking ties, answer keys, metrics, diagnostics, and hybrid ranking.

The latest local verification run reported **104 passing unit tests** on Python 3.12.

## Pipeline implementation

- `isbl/baseline/ir.py` - baseline raw-TF cosine ranking
- `isbl/baseline/ir_models.py` - raw TF, TF-IDF, BM25, rVSM, language-model, LSI, set-model, BLUiR-style and rank-fusion implementations
- `isbl/baseline/java/CoverageRunner.java` - per-test JaCoCo coverage collector
- `isbl/baseline/spectrum.py` - full and reduced spectrum construction
- `isbl/baseline/sfl.py` - 11 spectrum suspiciousness formulas
- `isbl/baseline/hybrid.py` - file/text tie-breakers and linear hybrid ranking
- `isbl/evaluation/metrics.py` - Top@N, MRR, MAP, nDCG, recall, EXAM and wasted effort
- `isbl/evaluation/diagnostics.py` - tie, coverage and ranking diagnostics
- `isbl/experiments/engine.py` - cross-bug model and method grid

## Main baseline result: Lang-1

At a 50% file cutoff, Lang-1 retains 913 of 981 relevant-test statements. Ochiai and DStar leave the same six-way top score:

| Method | Worst / average / best buggy rank |
|---|---|
| Plain Ochiai | 6 / 3.5 / 1 |
| ISBL + Ochiai | 6 / 3.5 / 1 |
| Plain DStar | 6 / 3.5 / 1 |
| ISBL + DStar | 6 / 3.5 / 1 |

Lines 462, 463, 467, 468, 471, and 474 share identical coverage counts. Three of them are buggy. In this run, the file filter removes unrelated lines but does not break ties inside `NumberUtils.java`, so statement ranking is unchanged.

See [`results/raw/Lang-1_tf_relevant_k0.5.csv`](results/raw/Lang-1_tf_relevant_k0.5.csv), [`results/raw/Lang-1_tf_relevant_k0.5_spectrum_scores.csv`](results/raw/Lang-1_tf_relevant_k0.5_spectrum_scores.csv), and [`results/Lang-1_results.xlsx`](results/Lang-1_results.xlsx).

## Differences and limits

- The paper's 373-bug, six-project experiment is not reproduced.
- BugLocator and Gharibi are not fully reproduced.
- rVSM covers the text-similarity component, not BugLocator's similar-bug history.
- BLUiR-style fields use regular-expression extraction rather than Java parsing.
- JaCoCo line coverage replaces the paper's coverage tooling.
- A fixed DStar exponent of 2 is used.
- Only the Defects4J trigger test is classified as failing; other unrelated full-suite failures are excluded.
- Missing-code answer keys use the first existing buggy-side line after the omission.
- The hybrid statement-text modes are an exploratory project extension and were selected after inspecting the same three-bug sample.

## Documentation

| Document | Purpose |
|---|---|
| [`docs/experiments.md`](docs/experiments.md) | Latest IR, metric, exclusion and hybrid experiments |
| [`docs/REPORT.md`](docs/REPORT.md) | Complete illustrated project report |
| [`docs/reproduction.md`](docs/reproduction.md) | Reproduction decisions and step-by-step setup |
| [`docs/baseline.md`](docs/baseline.md) | Pinned baseline environment and commits |
| [`docs/environment-audit.md`](docs/environment-audit.md) | Windows environment findings and blockers |
| [`docs/architecture.md`](docs/architecture.md) | Pipeline architecture |
| [`docs/literature.md`](docs/literature.md) | Literature and metric references |
| [`IRE_ISBL_Presenter_Guide.md`](IRE_ISBL_Presenter_Guide.md) | 20-slide presentation companion |

The combined documentation PDF is [`docs/ISBL_complete_documentation.pdf`](docs/ISBL_complete_documentation.pdf).
