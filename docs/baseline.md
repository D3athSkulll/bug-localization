# Baseline metadata (setup phase: environment and one-bug smoke test; baseline not implemented yet)
Paper: Statement-Level Software Bug Localization based on Information Retrieval and Spectrum (Jingwen Li et al., 2023)
Defects4J: v1.4.0, commit fcf6b9bb030e0f5f03ebab112eb4d4b622f2f315
buglocalization: bbd67ea65956748cc17a9c26e076aa9933a03008 (Naplues/buglocalization; contains BugLocator)
Java: Temurin OpenJDK 1.8.0_504 (portable, tools/). Python: 3.7.16 (legacy), 3.12.4 (modern). Perl: 5.38.2 (Git msys). OS: Windows 11 native.
Smoke-test bug: Lang-1 (LANG-747). buggy 396afc3e4693cfee182efe582455f2d97058c068, fixed d1a45e9738de5b3e299bb51e987565dcce55fee6 (apache/commons-lang GitHub hashes; d4j's own hashes 2c454a4c.../687b2e62... come from an unavailable mirror, remapped by matching the patch).
Command: bash scripts/run/smoke_lang1.sh
Observed: compiles; NumberUtilsTest 82 run, 1 error = TestLang747 NumberFormatException "80000000", identical to framework/projects/Lang/trigger_tests/1.

