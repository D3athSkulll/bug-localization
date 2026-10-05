"""IR stage of the ISBL baseline: VSM over source files, replicating the authors' vsm.py
(CountVectorizer -> TfidfTransformer(smooth_idf=False) -> cosine; bug query appended to the corpus).

Preprocessing flags default to the authors' behaviour (plain 2+ char word tokens, lowercase, nothing
else). The optional flags exist for later improvement experiments and are OFF in the baseline."""
import math
import re
from collections import Counter

_TOKEN = re.compile(r"(?u)\b\w\w+\b")  # sklearn CountVectorizer default token_pattern
_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")
JAVA_KEYWORDS = frozenset(
    """abstract assert boolean break byte case catch char class const continue default do double
else enum extends final finally float for goto if implements import instanceof int interface long native new
package private protected public return short static strictfp super switch synchronized this throw throws
transient try void volatile while true false null""".split())
STOPWORDS = frozenset(
    "a an and are as at be by for from has he in is it its of on or that the to was were will with".split())


def _tokenize(text, split_identifiers=False, remove_keywords=False, remove_stopwords=False):
    tokens = []
    for raw in _TOKEN.findall(text):
        parts = [raw]
        if split_identifiers:
            pieces = [p for p in _CAMEL.findall(raw.replace("_", " ")) if p]
            if len(pieces) > 1:
                parts = [raw] + pieces  # keep the full identifier as well as its parts
        for p in parts:
            p = p.lower()
            if len(p) < 2:
                continue
            if remove_keywords and p in JAVA_KEYWORDS:
                continue
            if remove_stopwords and p in STOPWORDS:
                continue
            tokens.append(p)
    return tokens


def preprocess_bug_report(text, **opts):
    return _tokenize(text or "", **opts)


def preprocess_source_file(text, **opts):
    return _tokenize(text or "", **opts)


def build_term_vector(docs_tokens):
    """docs_tokens: list of token lists (the query is conventionally last, as in the authors' code).
    Returns a list of {term: weight} l2-normalised tf-idf vectors; idf = ln(N/df) + 1 (smooth_idf=False)."""
    n = len(docs_tokens)
    counts = [Counter(t) for t in docs_tokens]
    df = Counter()
    for c in counts:
        df.update(c.keys())
    idf = {t: math.log(float(n) / d) + 1.0 for t, d in df.items()}
    vectors = []
    for c in counts:
        v = {t: tf * idf[t] for t, tf in c.items()}
        norm = math.sqrt(sum(w * w for w in v.values()))
        vectors.append({t: w / norm for t, w in v.items()} if norm > 0 else {})
    return vectors


def cosine_similarity(a, b):
    """Cosine of two sparse vectors ({term: weight}). A zero/empty vector gives 0.0 (safe behaviour)."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(w * b.get(t, 0.0) for t, w in a.items())
    na = math.sqrt(sum(w * w for w in a.values()))
    nb = math.sqrt(sum(w * w for w in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def rank_files(query_text, files, mode="tfidf", **opts):
    """files: {file_id: source_text}. Returns [(file_id, score)] by score desc (ties broken by file_id).
    mode='tfidf': the authors' vsm.py (tf-idf cosine).
    mode='tf'   : the paper's text (section II-A): raw word-frequency vectors + cosine, formula (1);
                  pass remove_keywords=True, remove_stopwords=True to follow the paper's preprocessing."""
    ids = sorted(files)
    docs = [preprocess_source_file(files[i], **opts) for i in ids] + [preprocess_bug_report(query_text, **opts)]
    if mode == "tf":
        vecs = [dict(Counter(d)) for d in docs]
    elif mode == "tfidf":
        vecs = build_term_vector(docs)
    else:
        raise ValueError("unknown IR mode: %s" % mode)
    q = vecs[-1]
    scored = [(i, cosine_similarity(vecs[k], q)) for k, i in enumerate(ids)]
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored


def select_top_k(ranked, k):
    """k in (0,1]: fraction of files (ceil, at least 1). k > 1: absolute number of files."""
    n = len(ranked)
    if n == 0:
        return []
    cnt = max(1, int(math.ceil(k * n - 1e-9))) if k <= 1 else int(k)
    return [f for f, _ in ranked[:min(cnt, n)]]
