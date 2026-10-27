import pytest

from isbl.baseline import hybrid, ranking, sfl
from isbl.baseline.answer_key import answer_key_from_patch
from isbl.evaluation import metrics as m


# ---- extra SFL formulas ----------------------------------------------------------------------------
def test_new_formulas_basic_values():
    assert sfl.tarantula(1, 0, 0, 5) == pytest.approx(1.0)
    assert sfl.tarantula(0, 3, 1, 2) == 0.0
    assert sfl.jaccard(1, 3, 0, 166) == pytest.approx(0.25)
    assert sfl.sorensen_dice(1, 3, 0, 166) == pytest.approx(0.4)
    assert sfl.kulczynski2(1, 3, 0, 166) == pytest.approx(0.625)
    assert sfl.op2(1, 3, 0, 166) == pytest.approx(1 - 3 / 170.0)
    assert sfl.barinel(1, 3, 0, 166) == pytest.approx(0.25)
    assert sfl.wong2(2, 5, 0, 0) == -3.0
    assert sfl.dstar3(2, 1, 0, 0) == pytest.approx(8.0)


def test_new_formulas_zero_and_degenerate_inputs_are_safe():
    for name, f in sfl.FORMULAS.items():
        for counts in [(0, 0, 0, 0), (0, 0, 2, 3), (0, 4, 0, 0), (3, 0, 0, 0)]:
            v = f(*counts)
            assert v == v, (name, counts)                                  # never NaN


def test_identical_counts_give_identical_scores_for_every_formula():
    """The core finding on Lang-1: lines with the same (ef,ep,nf,np) cannot be separated by ANY formula."""
    a, b = (1, 3, 0, 166), (1, 3, 0, 166)
    for name, f in sfl.FORMULAS.items():
        assert f(*a) == f(*b), name


# ---- generic ranking over tuple keys ------------------------------------------------------------------
def test_rank_keys_float_and_tuple_with_ties():
    keys = {"a": 3.0, "b": 3.0, "c": 1.0}
    assert ranking.rank_keys(keys, "worst") == {"a": 2, "b": 2, "c": 3}
    assert ranking.rank_keys(keys, "best") == {"a": 1, "b": 1, "c": 3}
    assert ranking.rank_keys(keys, "average")["a"] == 1.5
    tk = {"a": (1.0, 0.2), "b": (1.0, 0.9), "c": (0.5, 5.0)}              # lexicographic: second entry breaks the tie
    assert ranking.rank_keys(tk, "worst") == {"b": 1, "a": 2, "c": 3}
    assert ranking.rank_keys({}, "worst") == {}


def test_rank_keys_agrees_with_rank_statements():
    spec = {("A", 1): (1, 0, 0, 5), ("A", 2): (1, 3, 0, 2), ("A", 3): (0, 2, 1, 3), ("A", 4): (1, 3, 0, 2)}
    r1, scores = ranking.rank_statements(spec, sfl.ochiai, tie="worst")
    assert ranking.rank_keys(scores, "worst") == r1


# ---- hybrid keys -------------------------------------------------------------------------------------------
def test_finite_and_minmax():
    f = hybrid.finite({"a": float("inf"), "b": 2.0, "c": 0.0})
    assert f["a"] == 3.0 and f["b"] == 2.0
    assert hybrid.minmax({"a": 2.0, "b": 4.0}) == {"a": 0.0, "b": 1.0}
    assert hybrid.minmax({"a": 1.0, "b": 1.0}) == {"a": 0.0, "b": 0.0}
    assert hybrid.minmax({}) == {}


def test_tie_break_modes_only_reorder_exact_ties():
    sfl_scores = {("A", 1): 0.5, ("A", 2): 0.5, ("B", 3): 0.9, ("B", 4): 0.1}
    files = {"A": 0.2, "B": 0.1}
    text = {("A", 1): 0.0, ("A", 2): 3.0, ("B", 3): 0.0, ("B", 4): 9.0}
    k = hybrid.keys_for("tie_file_text", sfl_scores, files, text)
    r = ranking.rank_keys(k, "worst")
    assert r[("B", 3)] == 1                                               # higher SFL score always wins
    assert r[("A", 2)] == 2 and r[("A", 1)] == 3                          # tie on S and F broken by the text score
    assert r[("B", 4)] == 4                                               # lower SFL score never jumps ahead
    kf = ranking.rank_keys(hybrid.keys_for("tie_file", sfl_scores, files, text), "worst")
    assert kf[("A", 1)] == kf[("A", 2)] == 3                              # same file -> file score cannot split them


def test_linear_and_mult_and_unknown_mode():
    s = {("A", 1): 1.0, ("A", 2): 0.0}
    f = {"A": 1.0}
    lin = hybrid.keys_for("linear", s, f, None, a=0.5)
    assert lin[("A", 1)] > lin[("A", 2)]
    mul = hybrid.keys_for("mult", s, f, None, a=0.5)
    assert mul[("A", 2)] == 0.0                                           # a zero SFL score stays zero
    with pytest.raises(ValueError):
        hybrid.keys_for("magic", s, f, None)


def test_statement_text_scores_reward_report_words_on_the_line():
    files = {"X.java": "int a;\nreturn createLong(str);\nfoo();\n", "Y.java": "int b;\nbar();\n"}
    sc = hybrid.statement_text_scores([("X.java", 2), ("X.java", 3), ("Y.java", 2)], files,
                                      "createLong fails for hex", {"split_identifiers": True, "stem": True})
    assert sc[("X.java", 2)] > 0 and sc[("X.java", 3)] == 0 and sc[("Y.java", 2)] == 0


def test_file_score_map_normalises():
    assert hybrid.file_score_map([("a", 4.0), ("b", 2.0), ("c", 0.0)]) == {"a": 1.0, "b": 0.5, "c": 0.0}
    assert hybrid.file_score_map([]) == {}


# ---- extra metrics -------------------------------------------------------------------------------------------
def test_average_precision_and_map_variants():
    assert m.average_precision([1]) == 1.0
    assert m.average_precision([2, 4]) == pytest.approx((1 / 2.0 + 2 / 4.0) / 2)
    assert m.average_precision([]) == 0.0
    assert m.ap_over_all_relevant([1], 2) == pytest.approx(0.5)           # a relevant item never retrieved counts 0


def test_ndcg_recall_precision_exam():
    assert m.ndcg_at_k([1], 10, 1) == pytest.approx(1.0)
    assert m.ndcg_at_k([3], 10, 1) == pytest.approx(0.5)                  # 1/log2(4)
    assert m.ndcg_at_k([11], 10, 1) == 0.0
    assert m.recall_at_k([1, 3, 9], 5, 4) == pytest.approx(0.5)
    assert m.precision_at_k([1, 3, 9], 5) == pytest.approx(0.4)
    assert m.exam_score(6, 981) == pytest.approx(6 / 981.0)
    assert m.exam_score(None, 981) is None


def test_win_draw_lose_and_none_is_worst():
    assert m.win_draw_lose([1, 5, None], [2, 5, 3]) == (1, 1, 1)


def test_bootstrap_ci_and_wilcoxon():
    lo, hi = m.bootstrap_ci([0.5, 0.5, 0.5])
    assert lo == hi == 0.5
    assert m.bootstrap_ci([None]) == (None, None)
    assert m.wilcoxon_p([1, 2, 3], [1, 2, 3]) is None                     # no differences -> no test


def test_all_ranks_sorted():
    assert m.all_ranks({"a": 5, "b": 2, "c": 9}, {"a", "b", "z"}) == [2, 5]


# ---- answer key from a Defects4J patch (fixed -> buggy) ------------------------------------------------------
PATCH_MOD = """diff --git a/src/main/java/p/A.java b/src/main/java/p/A.java
--- a/src/main/java/p/A.java
+++ b/src/main/java/p/A.java
@@ -10,5 +10,5 @@ class A {
     int x;
-    if (fixed()) {
+    if (buggy()) {
         y();
     }
"""
PATCH_OMIT = """diff --git a/src/main/java/p/B.java b/src/main/java/p/B.java
--- a/src/main/java/p/B.java
+++ b/src/main/java/p/B.java
@@ -20,6 +20,3 @@ class B {
     a();
-    if (guard) {
-        throw new X();
-    }
     b();
"""


def test_answer_key_modification_uses_buggy_side_lines():
    assert answer_key_from_patch(PATCH_MOD) == {("p/A.java", 11)}


def test_answer_key_omission_points_at_next_buggy_line():
    assert answer_key_from_patch(PATCH_OMIT) == {("p/B.java", 21)}        # `b();` follows the missing guard


def test_answer_key_ignores_non_source_files_and_handles_multiple_hunks():
    other = PATCH_MOD.replace("src/main/java/p/A.java", "src/test/java/p/ATest.java")
    assert answer_key_from_patch(other) == set()
    assert answer_key_from_patch(PATCH_MOD + PATCH_OMIT) == {("p/A.java", 11), ("p/B.java", 21)}
