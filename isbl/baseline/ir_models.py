"""IR similarity models for the file-ranking step (Step A). All models share one interface:

    rank(model, query_text, files, prep=..., query_fields=..., name_match_weight=0.0, **model_params)
        -> [(file_id, score)] best first (ties broken by file id)

Models (see docs/literature.md for the sources of each idea):
  tf_cosine      raw term-frequency cosine - what the ISBL paper describes (section II-A, formula 1)
  tfidf_authors  the authors' repo script: CountVectorizer -> TfidfTransformer(smooth_idf=False) -> cosine
  tfidf_smooth   sklearn-style smoothed tf-idf, raw tf, cosine
  tfidf_sublinear sublinear tf (1+ln tf) x smoothed idf on both sides, cosine
  bm25           Okapi BM25 (k1=1.2, b=0.75, Lucene-style non-negative idf)
  rvsm           BugLocator's revised VSM: log-tf x log-idf cosine times a logistic bonus for longer files
  lm_dirichlet   query-likelihood language model with Dirichlet smoothing (mu=2000)
  jaccard        |Q ∩ D| / |Q ∪ D| on unique terms
  containment    |Q ∩ D| / |Q| : share of the query terms that occur in the file
  lsi            latent semantic indexing: sublinear tf-idf -> truncated SVD -> cosine in the latent space
  bluir          BLUiR-style structured retrieval: BM25 between {summary, description} and the file's
                 {class name, method names, identifiers, comments} fields, summed
  rrf            reciprocal-rank fusion of several of the models above
`name_match_weight` > 0 adds a bonus when the file's class name appears verbatim as a word of the bug report.
Nothing here uses the fixed version, the answer key or the tests."""
import math
import re
from collections import Counter

from isbl.baseline import ir

PAPER_PREP = {"remove_keywords": True, "remove_stopwords": True}
_PREP_KEYS = ("split_identifiers", "remove_keywords", "remove_stopwords", "stem", "drop_license")


def _prep_opts(prep):
    return {k: v for k, v in (prep or {}).items() if k in _PREP_KEYS}


def _df(docs):
    df = Counter()
    for d in docs:
        df.update(set(d))
    return df


def _l2(v):
    n = math.sqrt(sum(w * w for w in v.values()))
    return {t: w / n for t, w in v.items()} if n > 0 else {}


# ------------------------------------------------------------------------------------------- models
def tf_cosine(q, docs):
    qv = dict(Counter(q))
    return [ir.cosine_similarity(dict(Counter(d)), qv) for d in docs]


def tfidf_authors(q, docs):
    vecs = ir.build_term_vector(list(docs) + [q])            # query appended to the corpus, as in vsm.py
    return [ir.cosine_similarity(v, vecs[-1]) for v in vecs[:-1]]


def _smooth_idf(docs):
    n, df = len(docs), _df(docs)
    return {t: math.log((1.0 + n) / (1.0 + c)) + 1.0 for t, c in df.items()}


def tfidf_smooth(q, docs):
    idf = _smooth_idf(docs)
    qv = _l2({t: c * idf[t] for t, c in Counter(q).items() if t in idf})
    out = []
    for d in docs:
        dv = _l2({t: c * idf[t] for t, c in Counter(d).items()})
        out.append(ir.cosine_similarity(dv, qv))
    return out


def tfidf_sublinear(q, docs):
    idf = _smooth_idf(docs)
    w = lambda c: 1.0 + math.log(c)
    qv = _l2({t: w(c) * idf[t] for t, c in Counter(q).items() if t in idf})
    return [ir.cosine_similarity(_l2({t: w(c) * idf[t] for t, c in Counter(d).items()}), qv) for d in docs]


def bm25(q, docs, k1=1.2, b=0.75):
    n = len(docs)
    df = _df(docs)
    avgdl = (sum(len(d) for d in docs) / float(n)) or 1.0
    idf = {t: math.log(1.0 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    qc = Counter(q)
    out = []
    for d in docs:
        tf = Counter(d)
        dl = len(d)
        s = 0.0
        for t, qf in qc.items():
            f = tf.get(t, 0)
            if f:
                s += qf * idf[t] * (f * (k1 + 1.0)) / (f + k1 * (1.0 - b + b * dl / avgdl))
        out.append(s)
    return out


def rvsm(q, docs):
    """BugLocator (Zhou, Zhang, Lo - ICSE 2012): rVSM(q,d) = g(#terms(d)) * cos(q,d), tf = log(f)+1,
    idf = log(N/df), g(x) = 1/(1+exp(-N(x))), N() min-max normalises the document lengths.
    The similar-bug history component of BugLocator is NOT used (no bug-report history here)."""
    n = len(docs)
    df = _df(docs)
    idf = {t: math.log(float(n) / c) for t, c in df.items()}
    lens = [len(d) for d in docs]
    lo, hi = min(lens), max(lens)
    qv = {t: (math.log(c) + 1.0) * idf.get(t, 0.0) for t, c in Counter(q).items() if t in idf}
    out = []
    for d, L in zip(docs, lens):
        dv = {t: (math.log(c) + 1.0) * idf[t] for t, c in Counter(d).items()}
        x = (L - lo) / float(hi - lo) if hi > lo else 0.0
        out.append(ir.cosine_similarity(dv, qv) / (1.0 + math.exp(-x)))
    return out


def lm_dirichlet(q, docs, mu=2000.0):
    coll = Counter()
    for d in docs:
        coll.update(d)
    total = float(sum(coll.values())) or 1.0
    out = []
    for d in docs:
        tf, dl, s = Counter(d), len(d), 0.0
        for t in q:
            cf = coll.get(t, 0)
            if cf:
                s += math.log((tf.get(t, 0) + mu * cf / total) / (dl + mu))
        out.append(s)
    return out


def jaccard(q, docs):
    qs = set(q)
    return [len(qs & set(d)) / float(len(qs | set(d)) or 1) for d in docs]


def containment(q, docs):
    qs = set(q)
    return [len(qs & set(d)) / float(len(qs) or 1) for d in docs]


def lsi(q, docs, k=50):
    import numpy as np
    vocab = sorted({t for d in docs for t in d})
    index = {t: i for i, t in enumerate(vocab)}
    idf = _smooth_idf(docs)
    A = np.zeros((len(docs), len(vocab)))
    for r, d in enumerate(docs):
        for t, c in Counter(d).items():
            A[r, index[t]] = (1.0 + math.log(c)) * idf[t]
    nrm = np.linalg.norm(A, axis=1, keepdims=True)
    A = A / np.where(nrm == 0, 1.0, nrm)
    qv = np.zeros(len(vocab))
    for t, c in Counter(q).items():
        if t in index:
            qv[index[t]] = (1.0 + math.log(c)) * idf[t]
    qn = np.linalg.norm(qv)
    if qn == 0:
        return [0.0] * len(docs)
    qv = qv / qn
    _, _, Vt = np.linalg.svd(A, full_matrices=False)
    kk = max(1, min(k, Vt.shape[0]))
    P = Vt[:kk].T
    D, Q = A @ P, qv @ P
    dn, qn2 = np.linalg.norm(D, axis=1), np.linalg.norm(Q)
    if qn2 == 0:
        return [0.0] * len(docs)
    return [float(x) for x in (D @ Q) / np.where(dn == 0, 1.0, dn) / qn2]


MODELS = {"tf_cosine": tf_cosine, "tfidf_authors": tfidf_authors, "tfidf_smooth": tfidf_smooth,
          "tfidf_sublinear": tfidf_sublinear, "bm25": bm25, "rvsm": rvsm, "lm_dirichlet": lm_dirichlet,
          "jaccard": jaccard, "containment": containment, "lsi": lsi}


# ------------------------------------------------------------------------------ structured (BLUiR-like)
_BLOCK_OR_LINE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
_METHOD = re.compile(r"(?:public|protected|private|static|final|abstract|synchronized|native)\s+[\w<>\[\]?,.\s]*?\s(\w+)\s*\(")
_IDENT = re.compile(r"[A-Za-z_]\w*")


def extract_fields(text, file_id):
    """Heuristic Java field extraction (no parser): class name, method names, other identifiers, comments."""
    text = ir._LICENSE.sub(" ", text, count=1)
    comments = " ".join(_BLOCK_OR_LINE.findall(text))
    code = _BLOCK_OR_LINE.sub(" ", text)
    code = re.sub(r'"(?:\\.|[^"\\])*"', " ", code)
    methods = _METHOD.findall(code)
    idents = [w for w in _IDENT.findall(code) if w not in ir.JAVA_KEYWORDS]
    cls = file_id.rsplit("/", 1)[-1].replace(".java", "")
    return {"class": cls, "method": " ".join(methods), "ident": " ".join(idents), "comment": comments}


def _bluir(query_text, files, ids, prep, query_fields, **params):
    p = dict(_prep_opts(prep))
    p["split_identifiers"] = True                              # BLUiR-style: identifiers are split
    fields = {i: extract_fields(files[i], i) for i in ids}
    qf = query_fields or {"all": query_text}
    qtok = {name: ir.preprocess_bug_report(txt, **p) for name, txt in qf.items()}
    total = [0.0] * len(ids)
    for fname in ("class", "method", "ident", "comment"):
        dt = [ir.preprocess_source_file(fields[i][fname], **p) for i in ids]
        for qname, q in qtok.items():
            for k, s in enumerate(bm25(q, dt, **params)):
                total[k] += s
    return total


# ------------------------------------------------------------------------------------------ interface
def _minmax(xs):
    lo, hi = min(xs), max(xs)
    return [0.0 if hi == lo else (x - lo) / (hi - lo) for x in xs]


def _sorted(ids, scores):
    return sorted(zip(ids, scores), key=lambda x: (-x[1], x[0]))


_FRAME = re.compile(r"^[ \t]*(?:at[ \t]+[\w.$<>/]+\([^)\n]*\)|\.\.\.[ \t]*\d+[ \t]+(?:more|common frames omitted)|"
                    r"Caused by:.*)[ \t]*$", re.M)


def strip_stack_traces(text):
    """Remove Java stack-frame lines ("at pkg.Class.method(File.java:12)", "... 5 more", "Caused by: ...") from a bug
    report. Reports often paste traces of unrelated code (Lang-2: Maven Surefire / TestNG frames) that add noise terms
    such as java, org, apache. Generic cleaning, uses nothing but the report text."""
    return _FRAME.sub("", text or "")


def rank(model, query_text, files, prep=None, query_fields=None, name_match_weight=0.0, clean_query=False, **params):
    ids = sorted(files)
    prep = prep or {}
    if clean_query:
        query_text = strip_stack_traces(query_text)
        if query_fields:
            query_fields = {k: strip_stack_traces(v) for k, v in query_fields.items()}
    if model == "rrf":
        k0 = params.get("k", 60)
        fused = Counter()
        for sub in params["models"]:
            sub = dict(sub)
            r = rank(sub.pop("model"), query_text, files, prep=sub.pop("prep", prep), query_fields=query_fields, **sub)
            for pos, (fid, _) in enumerate(r, start=1):
                fused[fid] += 1.0 / (k0 + pos)
        scores = [fused[i] for i in ids]
    elif model == "bluir":
        scores = _bluir(query_text, files, ids, prep, query_fields, **params)
    elif model in MODELS:
        opts = _prep_opts(prep)
        docs = [ir.preprocess_source_file(files[i], **opts) for i in ids]
        scores = MODELS[model](ir.preprocess_bug_report(query_text, **opts), docs, **params)
    else:
        raise ValueError("unknown IR model: %s" % model)
    if name_match_weight:
        words = set(re.findall(r"[A-Za-z0-9_]+", query_text.lower()))
        base = _minmax(scores)
        scores = [b + name_match_weight * (1.0 if i.rsplit("/", 1)[-1].replace(".java", "").lower() in words else 0.0)
                  for b, i in zip(base, ids)]
    return _sorted(ids, scores)
