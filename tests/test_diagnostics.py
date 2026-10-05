import math
import time

import pytest

from isbl.baseline import ranking, sfl, spectrum
from isbl.baseline.timing import StageTimer
from isbl.evaluation import diagnostics as d


# ---- timing -------------------------------------------------------------------------------------
def test_stage_timer_records_order_and_accumulates():
    t = StageTimer()
    with t("a"):
        time.sleep(0.01)
    with t("b"):
        pass
    with t("a"):
        time.sleep(0.01)
    assert list(t.stages) == ["a", "b"]
    assert t.stages["a"] >= 0.02 - 1e-3
    assert t.total() == pytest.approx(sum(t.stages.values()))
    assert "TOTAL" in t.table()


def test_stage_timer_records_even_on_exception():
    t = StageTimer()
    with pytest.raises(ValueError):
        with t("boom"):
            raise ValueError
    assert "boom" in t.stages


# ---- IR diagnostics -------------------------------------------------------------------------------
RANKED = [("A", 0.5), ("B", 0.3), ("C", 0.2), ("D", 0.0)]


def test_ir_diagnostics_buggy_file_found():
    r = d.ir_diagnostics(RANKED, {"C"}, 2)
    assert r["ir_buggy_file_rank"] == 3
    assert r["ir_buggy_file_rank_percentile"] == pytest.approx(0.75)   # minimum k that keeps the buggy file
    assert r["ir_buggy_file_cosine"] == 0.2
    assert r["ir_buggy_file_recall_at_k"] == 0.0                        # rank 3 > 2 kept files
    assert r["ir_score_gap_top1_top2"] == pytest.approx(0.2)
    assert r["ir_files_with_nonzero_cosine"] == 3
    assert r["ir_files_dropped"] == 2


def test_ir_diagnostics_recall_hit_and_missing_file():
    assert d.ir_diagnostics(RANKED, {"A"}, 1)["ir_buggy_file_recall_at_k"] == 1.0
    r = d.ir_diagnostics(RANKED, {"Z"}, 2)
    assert r["ir_buggy_file_rank"] is None and r["ir_buggy_file_recall_at_k"] == 0.0


def test_ir_entropy_uniform_vs_peaked():
    uni = d.ir_diagnostics([("A", 1.0), ("B", 1.0), ("C", 1.0), ("D", 1.0)], {"A"}, 2)["ir_score_entropy_bits"]
    peak = d.ir_diagnostics([("A", 1.0), ("B", 0.001), ("C", 0.001), ("D", 0.001)], {"A"}, 2)["ir_score_entropy_bits"]
    assert uni == pytest.approx(2.0) and peak < uni


def test_ir_entropy_all_zero_is_zero():
    assert d.ir_diagnostics([("A", 0.0), ("B", 0.0)], {"A"}, 1)["ir_score_entropy_bits"] == 0.0


def test_ir_diagnostics_empty():
    r = d.ir_diagnostics([], {"A"}, 0)
    assert r["ir_num_files"] == 0 and r["ir_buggy_file_rank"] is None


# ---- spectrum / reduction diagnostics --------------------------------------------------------------
TESTS = [("f", False, {"A": {1, 2}}), ("p", True, {"A": {1}, "B": {5}})]


def test_spectrum_diagnostics_density():
    spec = spectrum.build_spectrum(TESTS)
    r = d.spectrum_diagnostics(TESTS, spec)
    assert r["sp_num_tests"] == 2 and r["sp_num_failed_tests"] == 1 and r["sp_num_statements"] == 3
    assert r["sp_matrix_cells"] == 6
    assert r["sp_matrix_density"] == pytest.approx(4 / 6.0)             # 4 covered cells out of 6
    assert r["sp_avg_statements_per_test"] == pytest.approx(2.0)


def test_spectrum_diagnostics_empty():
    r = d.spectrum_diagnostics([], {})
    assert r["sp_matrix_density"] == 0.0


def test_reduction_diagnostics_percentages():
    full = spectrum.build_spectrum(TESTS)
    red_tests = spectrum.reduce_tests(TESTS, ["A"])
    r = d.reduction_diagnostics(TESTS, red_tests, full, spectrum.build_spectrum(red_tests))
    assert r["red_statements_removed"] == 1 and r["red_statements_removed_pct"] == pytest.approx(100 / 3.0)
    assert r["red_tests_removed"] == 0


# ---- localisation diagnostics ------------------------------------------------------------------------
def _loc(bug):
    spec = {("A", 1): (1, 0, 0, 3), ("A", 2): (1, 0, 0, 3), ("A", 3): (1, 2, 0, 1), ("A", 4): (0, 2, 1, 1)}
    ranks, scores = ranking.rank_statements(spec, sfl.ochiai, tie="worst")
    return d.localization_diagnostics(spec, scores, ranks, bug)


def test_localization_tie_group_and_exam():
    r = _loc({("A", 1)})
    assert r["loc_best_buggy_rank"] == 2                                # worst-case rank in a 2-way tie
    assert r["loc_tie_group_size"] == 2 and r["loc_buggy_in_tie_group"] == 1
    assert r["loc_exam_score"] == pytest.approx(2 / 4.0)
    assert r["loc_wasted_effort"] == 1
    assert r["loc_distinct_scores"] == 3
    assert r["loc_best_buggy_score_over_top"] == pytest.approx(1.0)


def test_localization_multiple_buggy_and_missing():
    r = _loc({("A", 1), ("A", 2), ("A", 9)})
    assert r["loc_num_buggy_statements"] == 3 and r["loc_num_buggy_in_spectrum"] == 2
    assert r["loc_buggy_in_tie_group"] == 2 and r["loc_mean_buggy_rank"] == 2
    miss = _loc({("Z", 1)})
    assert miss["loc_best_buggy_rank"] is None and miss["loc_tie_group_size"] is None


def test_localization_median_even_and_odd():
    assert d._median([1, 3]) == 2.0 and d._median([5, 1, 3]) == 3 and d._median([]) is None


# ---- runner stats ---------------------------------------------------------------------------------------
def test_parse_runner_stats(tmp_path):
    p = tmp_path / "c.tsv"
    p.write_text("T\tt\tPASS\nM\t5\t10\t20\t300\t400\n", encoding="utf-8")
    assert spectrum.parse_runner_stats(str(p)) == {
        "tests": 5, "test_exec_ms": 10, "jacoco_dump_ms": 20, "jacoco_analyze_ms": 300, "jvm_total_ms": 400}
    q = tmp_path / "d.tsv"
    q.write_text("T\tt\tPASS\n", encoding="utf-8")
    assert spectrum.parse_runner_stats(str(q)) is None
