import math

import pytest

from isbl.baseline import ranking, sfl, spectrum
from isbl.evaluation import metrics


# ---- Ochiai --------------------------------------------------------------
def test_ochiai_basic():
    assert sfl.ochiai(1, 0, 0, 5) == pytest.approx(1.0)
    assert sfl.ochiai(1, 1, 1, 3) == pytest.approx(0.5)


def test_ochiai_nef_zero():  # covered by no failing test
    assert sfl.ochiai(0, 3, 2, 1) == 0.0


def test_ochiai_nf_zero():  # every failing test covers it
    assert sfl.ochiai(2, 2, 0, 1) == pytest.approx(2 / math.sqrt(2 * 4))


def test_ochiai_nep_zero():  # no passing test covers it
    assert sfl.ochiai(1, 0, 1, 4) == pytest.approx(1 / math.sqrt(2))


def test_ochiai_all_tests_fail():
    assert sfl.ochiai(3, 0, 0, 0) == pytest.approx(1.0)


def test_ochiai_all_tests_pass():
    assert sfl.ochiai(0, 4, 0, 0) == 0.0


def test_ochiai_statement_covered_by_every_test():
    assert sfl.ochiai(2, 3, 0, 0) == pytest.approx(2 / math.sqrt(2 * 5))


def test_ochiai_statement_covered_by_no_test():
    assert sfl.ochiai(0, 0, 2, 3) == 0.0
    assert sfl.ochiai(0, 0, 0, 0) == 0.0


# ---- DStar ---------------------------------------------------------------
def test_dstar_basic():
    assert sfl.dstar(2, 1, 1, 0) == pytest.approx(4 / 2)
    assert sfl.dstar(2, 1, 1, 0, star=3) == pytest.approx(8 / 2)


def test_dstar_nef_zero():
    assert sfl.dstar(0, 3, 2, 1) == 0.0


def test_dstar_zero_denominator_with_failure_is_inf():  # ep == 0 and nf == 0
    assert sfl.dstar(2, 0, 0, 5) == float("inf")


def test_dstar_zero_denominator_without_failure_is_zero():
    assert sfl.dstar(0, 0, 0, 5) == 0.0


def test_dstar_all_tests_fail_and_all_pass():
    assert sfl.dstar(3, 0, 0, 0) == float("inf")
    assert sfl.dstar(0, 4, 0, 0) == 0.0


def test_dstar_statement_covered_by_every_test_and_by_none():
    assert sfl.dstar(2, 3, 0, 0) == pytest.approx(4 / 3)
    assert sfl.dstar(0, 0, 2, 3) == 0.0


def test_dstar_nep_zero():
    assert sfl.dstar(1, 0, 1, 4) == pytest.approx(1.0)


# ---- spectrum ------------------------------------------------------------
TESTS = [
    ("t1", False, {"A.java": {1, 2}, "B.java": {5}}),
    ("t2", True, {"A.java": {1}}),
    ("t3", True, {"B.java": {5}, "C.java": {9}}),
]


def test_build_spectrum_counts():
    s = spectrum.build_spectrum(TESTS)
    assert s[("A.java", 1)] == (1, 1, 0, 1)   # ef ep nf np
    assert s[("A.java", 2)] == (1, 0, 0, 2)
    assert s[("B.java", 5)] == (1, 1, 0, 1)
    assert s[("C.java", 9)] == (0, 1, 1, 1)
    assert ("A.java", 3) not in s


def test_reduce_spectrum_keeps_only_suspicious_files():
    s = spectrum.build_spectrum(TESTS)
    r = spectrum.reduce_spectrum(s, ["A.java"])
    assert {f for f, _ in r} == {"A.java"}
    assert spectrum.reduce_spectrum(s, []) == {}


def test_parse_coverage_roundtrip(tmp_path):
    p = tmp_path / "c.tsv"
    p.write_text("T\tt1\tFAIL\nC\tA.java\t1,2\nT\tt2\tPASS\nC\tA.java\t1\n", encoding="utf-8")
    t = spectrum.parse_coverage(str(p))
    assert t == [("t1", False, {"A.java": {1, 2}}), ("t2", True, {"A.java": {1}})]


# ---- ranking ---------------------------------------------------------------
def test_rank_statements_tie_handling():
    sp = {("A", 1): (1, 0, 0, 0), ("A", 2): (1, 0, 0, 0), ("A", 3): (0, 1, 1, 0)}
    worst, _ = ranking.rank_statements(sp, sfl.ochiai, tie="worst")
    best, _ = ranking.rank_statements(sp, sfl.ochiai, tie="best")
    avg, _ = ranking.rank_statements(sp, sfl.ochiai, tie="average")
    assert worst[("A", 1)] == 2 and best[("A", 1)] == 1 and avg[("A", 1)] == 1.5
    assert worst[("A", 3)] == best[("A", 3)] == 3


def test_rank_statements_empty():
    assert ranking.rank_statements({}, sfl.ochiai) == ({}, {})


# ---- metrics -----------------------------------------------------------------
def test_top_n_and_mrr_rank_1_3_5():
    ranks = [1, 3, 5]
    assert metrics.top_n(ranks, 1) == 1
    assert metrics.top_n(ranks, 3) == 2
    assert metrics.top_n(ranks, 5) == 3
    assert metrics.mrr(ranks) == pytest.approx((1 + 1 / 3 + 1 / 5) / 3)


def test_rank_greater_than_n():
    assert metrics.top_n([6, 50], 5) == 0
    assert metrics.mrr([10]) == pytest.approx(0.1)


def test_missing_buggy_statement_counts_as_zero():
    r = metrics.bug_rank({("A", 1): 1}, {("B", 7)})
    assert r is None
    assert metrics.top_n([r], 5) == 0
    assert metrics.mrr([r, 1]) == pytest.approx(0.5)


def test_multiple_buggy_statements_use_best_rank():
    ranks = {("A", 1): 4, ("A", 2): 2, ("A", 3): 9}
    assert metrics.bug_rank(ranks, {("A", 1), ("A", 2), ("Z", 0)}) == 2


def test_empty_metrics():
    assert metrics.mrr([]) == 0.0


def test_file_recall_at_k():
    assert metrics.file_recall_at_k(["A", "B"], ["B"]) == 1.0
    assert metrics.file_recall_at_k(["A"], ["B"]) == 0.0


# ---- paper II-B spectrum reduction (drop tests that cover nothing left) ------------
def test_reduce_tests_drops_empty_tests_and_recomputes_nf():
    tests = [("f1", False, {"A.java": {1}}), ("f2", False, {"B.java": {2}}), ("p1", True, {"B.java": {2}})]
    red = spectrum.reduce_tests(tests, ["A.java"])
    assert [t[0] for t in red] == ["f1"]                      # f2 and p1 covered only B.java
    assert spectrum.build_spectrum(red)[("A.java", 1)] == (1, 0, 0, 0)   # nf counted on the reduced test set


def test_reduce_tests_can_remove_all_failing_tests_when_buggy_file_excluded():
    tests = [("f1", False, {"B.java": {2}}), ("p1", True, {"A.java": {1}})]
    sp = spectrum.build_spectrum(spectrum.reduce_tests(tests, ["A.java"]))
    assert all(v[0] == 0 for v in sp.values())               # no failing test left -> nothing can be localised


# ---- Defects4J trigger-test convention ---------------------------------------------
def test_parse_trigger_tests(tmp_path):
    p = tmp_path / "t"
    p.write_text("--- a.b.CTest::testX\njava.lang.Foo\n\tat x\n--- a.b.CTest::testY\n", encoding="utf-8")
    assert spectrum.parse_trigger_tests(str(p)) == {"testX(a.b.CTest)", "testY(a.b.CTest)"}


def test_keep_trigger_failures_removes_other_failures_only():
    tests = [("testX(a.b.CTest)", False, {}), ("other(a.OTest)", False, {}), ("ok(a.OTest)", True, {})]
    kept, removed = spectrum.keep_trigger_failures(tests, {"testX(a.b.CTest)"})
    assert [t[0] for t in kept] == ["testX(a.b.CTest)", "ok(a.OTest)"]
    assert removed == ["other(a.OTest)"]
