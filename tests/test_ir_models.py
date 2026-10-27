import math

import pytest

from isbl.baseline import ir, ir_models as M


def ranked_ids(model, query, files, **kw):
    return [f for f, _ in M.rank(model, query, files, **kw)]


# ---- the cosine itself (audit) ---------------------------------------------------------------
def test_tf_cosine_matches_manual_formula():
    q, d = ["a", "a", "b"], ["a", "b", "b", "c"]
    expected = (2 * 1 + 1 * 2) / (math.sqrt(2 ** 2 + 1) * math.sqrt(1 + 2 ** 2 + 1))
    assert M.tf_cosine(q, [d])[0] == pytest.approx(expected)


def test_tf_cosine_properties():
    docs = [["a", "b"], ["b", "c", "c"], []]
    s = M.tf_cosine(["b", "c"], docs)
    assert all(0.0 <= x <= 1.0 + 1e-12 for x in s)
    assert s[2] == 0.0                                                   # empty document
    assert M.tf_cosine(["b", "c"] * 7, docs) == pytest.approx(s)         # scale invariant in the query
    assert M.tf_cosine(["a", "b"], [["a", "b"]])[0] == pytest.approx(1.0)


def test_cosine_matches_sklearn_and_scipy():
    sk = pytest.importorskip("sklearn.feature_extraction.text")
    pw = pytest.importorskip("sklearn.metrics.pairwise")
    docs = [["x", "y", "y"], ["y", "z"], ["x", "z", "z", "w"]]
    q = ["y", "z", "z"]
    cv = sk.CountVectorizer(analyzer=lambda t: t)
    X = cv.fit_transform(docs + [q])
    ref = pw.cosine_similarity(X[-1], X[:-1]).ravel()
    assert M.tf_cosine(q, docs) == pytest.approx(list(ref), abs=1e-12)


# ---- weighting: why raw tf is not enough --------------------------------------------------------
def test_idf_models_demote_generic_terms_that_raw_tf_rewards():
    files = {"A.java": "common " * 10, "B.java": "hex", "C.java": "common other"}
    q = "hex common"
    assert ranked_ids("tf_cosine", q, files)[0] == "A.java"              # raw tf: tie broken by id, generic term wins
    for model in ("tfidf_smooth", "tfidf_sublinear", "tfidf_authors", "bm25", "rvsm"):
        assert ranked_ids(model, q, files)[0] == "B.java", model          # idf-weighted: the rare term decides


def test_tfidf_authors_matches_sklearn_pipeline():
    sk = pytest.importorskip("sklearn.feature_extraction.text")
    import numpy as np
    docs = ["alpha beta beta gamma", "beta delta", "alpha delta delta epsilon"]
    q = "beta delta delta"
    X = sk.CountVectorizer().fit_transform(docs + [q])
    V = sk.TfidfTransformer(smooth_idf=False).fit_transform(X).toarray()
    expected = [float(np.dot(V[i], V[-1])) for i in range(3)]
    got = M.tfidf_authors(ir.preprocess_bug_report(q), [ir.preprocess_source_file(d) for d in docs])
    assert got == pytest.approx(expected, abs=1e-9)


def test_tfidf_smooth_matches_sklearn_tfidfvectorizer():
    sk = pytest.importorskip("sklearn.feature_extraction.text")
    pw = pytest.importorskip("sklearn.metrics.pairwise")
    docs = ["alpha beta beta gamma", "beta delta", "alpha delta delta epsilon", "gamma gamma"]
    q = "beta delta delta"
    tv = sk.TfidfVectorizer()
    D = tv.fit_transform(docs)
    expected = pw.cosine_similarity(tv.transform([q]), D).ravel()
    got = M.tfidf_smooth(ir.preprocess_bug_report(q), [ir.preprocess_source_file(d) for d in docs])
    assert got == pytest.approx(list(expected), abs=1e-9)


def test_tfidf_sublinear_matches_sklearn_sublinear_tf():
    sk = pytest.importorskip("sklearn.feature_extraction.text")
    pw = pytest.importorskip("sklearn.metrics.pairwise")
    docs = ["alpha beta beta beta gamma", "beta delta", "alpha delta delta epsilon", "gamma gamma"]
    q = "beta beta delta"
    tv = sk.TfidfVectorizer(sublinear_tf=True)
    D = tv.fit_transform(docs)
    expected = pw.cosine_similarity(tv.transform([q]), D).ravel()
    got = M.tfidf_sublinear(ir.preprocess_bug_report(q), [ir.preprocess_source_file(d) for d in docs])
    assert got == pytest.approx(list(expected), abs=1e-9)


# ---- BM25 / rVSM / LM / set models ---------------------------------------------------------------
def test_bm25_prefers_more_query_terms_and_shorter_documents():
    docs = [["a", "b"], ["a"] + ["pad"] * 20, ["a", "b", "c"] + ["pad"] * 2, ["z"]]
    s = M.bm25(["a", "b"], docs)
    assert s[0] > s[2] > s[1] > s[3] == 0.0                              # both terms > longer both > one term > none


def test_bm25_idf_is_non_negative():
    docs = [["common"], ["common"], ["common"]]
    assert all(x >= 0 for x in M.bm25(["common"], docs))


def test_rvsm_longer_file_gets_larger_logistic_bonus():
    short, long_ = ["a", "b"], ["a", "b"] + ["pad%d" % i for i in range(30)]
    docs = [short, long_, ["c", "d"]]
    q = ["a", "b"]
    idf = {t: math.log(3.0 / c) for t, c in M._df(docs).items()}
    cos_short = ir.cosine_similarity({"a": idf["a"], "b": idf["b"]}, {"a": idf["a"], "b": idf["b"]})
    s = M.rvsm(q, docs)
    assert s[0] == pytest.approx(cos_short / 2.0)                        # shortest: N(len)=0 so g = 1/(1+e^0) = 1/2
    # the longest file (N(len)=1) has g = 1/(1+e^-1) = 0.731 times ITS OWN cosine
    long_vec = {t: (math.log(c) + 1.0) * idf[t] for t, c in __import__("collections").Counter(long_).items()}
    qv = {t: (math.log(c) + 1.0) * idf[t] for t, c in __import__("collections").Counter(q).items()}
    assert s[1] == pytest.approx(ir.cosine_similarity(long_vec, qv) / (1.0 + math.exp(-1.0)))


def test_lm_dirichlet_scores_documents_containing_query_terms_higher():
    docs = [["a", "a", "b"], ["c", "d", "e"], ["a", "c"]]
    s = M.lm_dirichlet(["a", "b"], docs, mu=10)
    assert s[0] > s[2] > s[1]
    assert all(x <= 0 for x in s)                                        # log-probabilities


def test_jaccard_and_containment_values():
    docs = [["a", "b", "c"], ["a"], ["x"]]
    assert M.jaccard(["a", "b"], docs) == pytest.approx([2 / 3.0, 1 / 2.0, 0.0])
    assert M.containment(["a", "b"], docs) == pytest.approx([1.0, 0.5, 0.0])
    assert M.containment([], docs) == [0.0, 0.0, 0.0]


def test_lsi_outputs_one_bounded_score_per_document():
    docs = [["a", "b", "c"], ["b", "c", "d"], ["x", "y", "z"], ["a", "x"]]
    s = M.lsi(["b", "c"], docs, k=2)
    assert len(s) == 4 and all(-1.0 - 1e-9 <= x <= 1.0 + 1e-9 for x in s)
    assert s[2] < max(s[0], s[1])                                        # the unrelated document ranks low
    assert M.lsi(["nothing-known"], docs, k=2) == [0.0] * 4


# ---- structured retrieval, fusion, name bonus, preprocessing ------------------------------------
JAVA = """/* Licensed to the Apache Software Foundation (ASF) under one or more contributor licence agreements. */
package p;
// helper for parsing numbers
public class NumberUtils {
    public static Number createNumber(String str) {
        final int hexDigits = str.length();
        return createLong(str);   // inline note
    }
    private static Long createLong(final String s) { return Long.decode(s); }
}"""


def test_extract_fields_separates_class_methods_identifiers_comments():
    f = M.extract_fields(JAVA, "org/p/NumberUtils.java")
    assert f["class"] == "NumberUtils"
    assert "createNumber" in f["method"] and "createLong" in f["method"]
    assert "hexDigits" in f["ident"] and "static" not in f["ident"].split()
    assert "helper for parsing" in f["comment"] and "inline note" in f["comment"]
    assert "Licensed to the Apache" not in f["comment"]                  # licence header removed


def test_bluir_ranks_file_whose_method_names_match_the_report():
    files = {"A.java": "class A { public void foo() { int x; } }",
             "B.java": "class B { public static Number createNumber(String s) { return null; } }"}
    r = M.rank("bluir", "createNumber fails", files, query_fields={"summary": "createNumber fails", "description": ""})
    assert r[0][0] == "B.java"


def test_rrf_fuses_rankings_and_is_deterministic():
    files = {"A.java": "alpha alpha beta", "B.java": "alpha", "C.java": "beta gamma"}
    sub = [{"model": "bm25"}, {"model": "tfidf_smooth"}]
    r1 = M.rank("rrf", "alpha beta", files, models=sub)
    r2 = M.rank("rrf", "alpha beta", files, models=sub)
    assert r1 == r2 and len(r1) == 3 and r1[0][1] >= r1[1][1] >= r1[2][1]


def test_name_match_bonus_lifts_file_named_in_report():
    files = {"NumberUtils.java": "zzz", "Other.java": "number number number"}
    base = ranked_ids("tf_cosine", "number numberutils", files)
    boosted = ranked_ids("tf_cosine", "number numberutils", files, name_match_weight=1.0)
    assert base[0] == "Other.java"                                        # without the bonus the text model decides
    assert boosted[0] == "NumberUtils.java"


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        M.rank("word2vec", "q", {"A.java": "a"})


def test_stemming_and_license_stripping_options():
    assert ir.preprocess_bug_report("numbers parsing", stem=True) == ["number", "pars"]
    text = "/* Licensed to the Apache Software Foundation (ASF) under one or more */ class Foo {}"
    assert "licensed" not in ir.preprocess_source_file(text, drop_license=True)
    assert "licensed" in ir.preprocess_source_file(text)


def test_models_are_deterministic_and_return_all_files_sorted():
    files = {"B.java": "alpha beta", "A.java": "alpha beta", "C.java": "gamma"}
    for model in ("tf_cosine", "tfidf_smooth", "bm25", "rvsm", "lm_dirichlet", "jaccard", "containment", "lsi"):
        r = M.rank(model, "alpha beta", files)
        assert [f for f, _ in r][:2] == ["A.java", "B.java"], model     # equal scores -> broken by file id
        scores = [s for _, s in r]
        assert scores == sorted(scores, reverse=True)
