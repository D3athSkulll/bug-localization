import math

import pytest

from isbl.baseline import ir


def vec(a, b):
    v = ir.build_term_vector([ir.preprocess_source_file(a), ir.preprocess_bug_report(b)])
    return v[0], v[1]


def sim(a, b):
    return ir.cosine_similarity(*vec(a, b))


# ---- cosine similarity -------------------------------------------------
def test_cosine_same_vector_is_one():
    v = {"a": 1.0, "b": 2.0}
    assert ir.cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero():
    assert ir.cosine_similarity({"a": 1.0}, {"b": 1.0}) == 0.0


def test_cosine_zero_vector_is_safe():
    assert ir.cosine_similarity({}, {"a": 1.0}) == 0.0
    assert ir.cosine_similarity({}, {}) == 0.0


# ---- IR behaviour -------------------------------------------------------
def test_identical_documents():
    assert sim("parse number hex", "parse number hex") == pytest.approx(1.0)


def test_completely_different_documents():
    assert sim("alpha beta gamma", "delta epsilon zeta") == 0.0


def test_empty_document():
    assert sim("", "some query text") == 0.0
    assert ir.preprocess_source_file("") == []
    assert ir.preprocess_bug_report(None) == []


def test_one_token_document():
    assert sim("checksum", "checksum") == pytest.approx(1.0)
    assert ir.preprocess_source_file("x") == []  # sklearn default drops 1-char tokens


def test_stop_word_only_document_default_keeps_them_optional_removes_them():
    assert ir.preprocess_bug_report("the of and") == ["the", "of", "and"]  # authors' baseline: no stop-word removal
    assert ir.preprocess_bug_report("the of and", remove_stopwords=True) == []


def test_repeated_terms_raise_term_frequency_weight():
    docs = [["foo", "foo", "foo", "bar"], ["foo", "bar", "bar", "bar"], ["baz"]]
    v = ir.build_term_vector(docs)
    assert v[0]["foo"] > v[0]["bar"]
    assert v[1]["bar"] > v[1]["foo"]


def test_source_code_keywords_kept_by_default_removed_on_request():
    text = "public static void main"
    assert "public" in ir.preprocess_source_file(text)
    assert ir.preprocess_source_file(text, remove_keywords=True) == ["main"]


def test_camel_case_not_split_in_baseline_but_split_optionally():
    assert ir.preprocess_source_file("calculateFileChecksum") == ["calculatefilechecksum"]
    toks = ir.preprocess_source_file("calculateFileChecksum", split_identifiers=True)
    assert set(toks) >= {"calculate", "file", "checksum", "calculatefilechecksum"}


def test_snake_case_not_split_in_baseline_but_split_optionally():
    assert ir.preprocess_source_file("calc_file_checksum") == ["calc_file_checksum"]
    toks = ir.preprocess_source_file("calc_file_checksum", split_identifiers=True)
    assert set(toks) >= {"calc", "file", "checksum"}


def test_vectors_are_l2_normalised():
    v = ir.build_term_vector([["a", "b", "b"], ["c"]])
    for x in v:
        assert math.sqrt(sum(w * w for w in x.values())) == pytest.approx(1.0)


def test_rank_files_orders_by_similarity():
    files = {"A.java": "hex number parse", "B.java": "network socket", "C.java": "image render"}
    ranked = ir.rank_files("hex number parse failure", files)
    assert ranked[0][0] == "A.java"
    assert [f for f, _ in ranked][1:] == ["B.java", "C.java"]  # tie broken by file id


def test_select_top_k_fraction_and_absolute():
    ranked = [("f%d" % i, 1.0 - i / 100.0) for i in range(10)]
    assert ir.select_top_k(ranked, 0.5) == ["f0", "f1", "f2", "f3", "f4"]
    assert ir.select_top_k(ranked, 0.01) == ["f0"]  # at least one file
    assert len(ir.select_top_k(ranked, 1.0)) == 10
    assert len(ir.select_top_k(ranked, 3)) == 3
    assert ir.select_top_k([], 0.5) == []


def test_matches_authors_sklearn_pipeline():
    """Authors' vsm.py: CountVectorizer -> TfidfTransformer(smooth_idf=False) -> cosine."""
    sk = pytest.importorskip("sklearn.feature_extraction.text")
    import numpy as np
    corpus = ["public int parse hex number hex", "socket network connect number", "render image pixel",
              "hex number parse failure parse"]
    X = sk.CountVectorizer().fit_transform(corpus)
    V = sk.TfidfTransformer(smooth_idf=False).fit_transform(X).toarray()
    expected = [float(np.dot(V[i], V[-1])) for i in range(len(corpus) - 1)]
    vecs = ir.build_term_vector([ir.preprocess_source_file(c) for c in corpus])
    got = [ir.cosine_similarity(vecs[i], vecs[-1]) for i in range(len(corpus) - 1)]
    assert got == pytest.approx(expected, abs=1e-9)


# ---- paper mode (section II-A): raw term-frequency cosine ------------------------
def test_tf_mode_ranks_by_raw_frequency_and_ignores_idf():
    files = {"A.java": "hex hex hex number", "B.java": "number number number number"}
    r = ir.rank_files("hex", files, mode="tf")
    assert r[0][0] == "A.java" and r[1][1] == 0.0


def test_tf_mode_with_paper_preprocessing_drops_keywords_and_stopwords():
    files = {"A.java": "public static the of hex", "B.java": "public static the of network"}
    r = ir.rank_files("the hex of public", files, mode="tf", remove_keywords=True, remove_stopwords=True)
    assert r[0][0] == "A.java" and r[0][1] == pytest.approx(1.0)  # only 'hex' survives in both


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        ir.rank_files("x", {"A": "x"}, mode="bm25")
