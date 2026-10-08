"""Small-corpus BM25 keyword search combined with dense search by rank fusion."""

from collections import Counter
import math
import re
import unicodedata

from scripts.local_index import COLLECTION, document_filter, search_index

HYBRID_CONFIG = {"bm25_k1": 1.2, "bm25_b": 0.75, "rrf_constant": 60, "candidate_limit": 20}


def terms(text):
    return re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", text).lower())


def bm25_rank(question, passages):
    query = set(terms(question))
    counts = [Counter(terms(p["text"])) for p in passages]
    if not counts or not query:
        return []
    lengths = [sum(c.values()) for c in counts]
    average = sum(lengths) / len(lengths)
    if average == 0:
        return []
    df = Counter(term for c in counts for term in c)
    k1, b = HYBRID_CONFIG["bm25_k1"], HYBRID_CONFIG["bm25_b"]
    ranked = []
    for passage, count, length in zip(passages, counts, lengths):
        score = 0.0
        for term in query:
            tf = count[term]
            if tf:
                idf = math.log(1 + (len(counts) - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / average))
        if score > 0:
            ranked.append({**passage, "bm25_score": score})
    return sorted(ranked, key=lambda h: (-h["bm25_score"], h["chunk_id"]))


def fuse_ranks(dense, lexical, top_k):
    combined = {}
    for method, hits in [("dense", dense), ("lexical", lexical)]:
        for rank, hit in enumerate(hits, 1):
            entry = combined.setdefault(hit["chunk_id"], {**hit, "rrf_score": 0.0})
            entry[f"{method}_rank"] = rank
            if method == "dense":
                entry["dense_score"] = hit["score"]
            else:
                entry["bm25_score"] = hit["bm25_score"]
            entry["rrf_score"] += 1 / (HYBRID_CONFIG["rrf_constant"] + rank)
    ranked = sorted(combined.values(), key=lambda h: (-h["rrf_score"], h["chunk_id"]))
    # Explicit score_type prevents interpreting a fused score as cosine similarity.
    return [{**h, "score": h["rrf_score"], "score_type": "rrf"} for h in ranked[:top_k]]


def search_keywords(client, question, top_k=3, document_id=None):
    passages, offset = [], None
    while True:
        points, offset = client.scroll(COLLECTION, offset=offset, limit=256,
                                       scroll_filter=document_filter(document_id) if document_id is not None else None,
                                       with_payload=True, with_vectors=False)
        passages.extend(p.payload for p in points)
        if offset is None:
            break
    return [{**hit, "score": hit["bm25_score"], "score_type": "bm25"}
            for hit in bm25_rank(question, passages)[:top_k]]


def search_hybrid(client, question, vector, top_k=3, document_id=None):
    limit = max(top_k, HYBRID_CONFIG["candidate_limit"])
    dense = [{"score": hit.score, **hit.payload}
             for hit in search_index(client, vector, limit, document_id)]
    lexical = search_keywords(client, question, limit, document_id)
    return fuse_ranks(dense, lexical, top_k)
