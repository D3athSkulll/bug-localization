# Baseline metadata (setup phase only - baseline NOT implemented, no commit/tag made)
Paper: Statement-Level Software Bug Localization based on Information Retrieval and Spectrum (Jingwen Li et al., 2023)
Defects4J: v1.4.0, commit fcf6b9bb030e0f5f03ebab112eb4d4b622f2f315
buglocalization: bbd67ea65956748cc17a9c26e076aa9933a03008 (Naplues/buglocalization; contains BugLocator)
Java: Temurin OpenJDK 1.8.0_504 (portable, tools/). Python: 3.7.16 (legacy), 3.12.4 (modern). Perl: 5.38.2 (Git msys). OS: Windows 11 native.
Smoke-test bug: Lang-1 (LANG-747). buggy 396afc3e4693cfee182efe582455f2d97058c068, fixed d1a45e9738de5b3e299bb51e987565dcce55fee6 (apache/commons-lang GitHub hashes; d4j's own hashes 2c454a4c.../687b2e62... come from an unavailable mirror, remapped by matching the patch).
Command: bash scripts/run/smoke_lang1.sh
Observed: compiles; NumberUtilsTest 82 run, 1 error = TestLang747 NumberFormatException "80000000", identical to framework/projects/Lang/trigger_tests/1.

## Baseline implementation
Code: isbl/baseline/{ir,spectrum,sfl,ranking,pipeline}.py, isbl/baseline/java/CoverageRunner.java, isbl/evaluation/metrics.py. Configs: configs/lang1_k50.json (relevant tests), configs/lang1_k50_alltests.json (full suite).
Outputs: results/raw/Lang-1_tf_<scope>_k0.5.{json,csv} and ..._sweep_k.csv.
Observed (Lang-1, k=0.5): buggy file IR rank 8/108; statement rank 6 (worst ties) / 3.5 / 1 (best); ISBL equals plain Ochiai/DStar on this bug; MRR 0.167 (worst ties). Details: docs/reproduction.md.
History: three commits (environment and smoke test, baseline code and tests, results and analysis). The tag baseline-authors-v1 from the original plan is not created.
