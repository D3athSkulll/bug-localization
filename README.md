# ISBL reproduction workspace

Reproduction of **"Statement-level Software Bug Localization based on Information Retrieval and Spectrum"** (Li, Yue, Lan, Cui; IEEE SMC 2023) on Windows 11, without WSL.

## Step 1 status: environment and smoke test

- Historical environment: JDK 8 (Temurin 8u504, portable), Python 3.7.16, Defects4J v1.4.0. A second Python 3.12 environment is kept for later work.
- Smoke test on one bug, **Defects4J Lang-1 (LANG-747)**: check out the buggy version of Apache Commons Lang, compile it with Maven on JDK 8, run the tests, and reproduce the documented failure (`TestLang747`: `NumberFormatException: For input string: "80000000"`).
- Run it with `bash scripts/run/smoke_lang1.sh` after the setup below.

### Setup (Windows)

1. Clone the pinned upstream sources next to this folder's contents:
   - `git clone https://github.com/rjust/defects4j.git` then `git -C defects4j checkout v1.4.0`
   - `git clone https://github.com/Naplues/buglocalization.git` then `git -C buglocalization checkout bbd67ea65956748cc17a9c26e076aa9933a03008`
   - `git clone https://github.com/apache/commons-lang.git work-lang`
2. Portable Temurin JDK 8 (8u504) unzipped to `tools/jdk8u504-b01`.
3. Python 3.7: `conda create -p envs/legacy37 python=3.7`, then install `requirements/legacy.txt`. Python 3.12: a venv at `envs/modern312` with `requirements/modern.txt`.
4. Defects4J's own project download host is offline, so the smoke test checks Lang-1 out of the upstream Apache repository using the commit hashes in `docs/baseline.md`.

Files: `docs/environment-audit.md` (what was found and the blockers), `docs/baseline.md` (pinned versions), `requirements/`, `scripts/setup/`, `scripts/run/smoke_lang1.sh`, `data/bug_reports/Lang-1.json`.

Nothing in this workspace is a reproduction of the paper's results yet.
