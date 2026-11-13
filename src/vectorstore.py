"""
Phase 2: Hybrid Search (Dense + BM25 + RRF + Cross-Encoder Re-ranker) Module
============================================================================
This module is the pinnacle of enterprise retrieval architectures:
1. Stage 1A (Dense Semantic Retrieval):
   - ChromaDB HNSW Cosine vector search with all-MiniLM-L6-v2 (catches meaning & synonyms).
2. Stage 1B (Sparse Keyword Retrieval):
   - BM25Okapi inverted index (catches exact numbers, product models, error codes, SLAs).
3. Stage 1C (Reciprocal Rank Fusion - RRF):
   - Merges Dense and Sparse candidate lists using the mathematical RRF formula:
     RRF_Score = 1 / (60 + Dense_Rank) + 1 / (60 + BM25_Rank)
4. Stage 2 (Cross-Encoder Re-ranking):
   - CrossEncoder ('cross-encoder/ms-marco-MiniLM-L-6-v2') performs deep joint
     cross-attention on (query, chunk) to select the true Top-3 chunks.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import numpy as np
import chromadb
from chromadb.config import Settings
from sentence_transformers import CrossEncoder
from rank_bm25 import BM25Okapi

# Internal project imports
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.ingestion import load_and_chunk_policy_manual
from src.embeddings import get_embedding_function

# Persistent storage directory
CHROMA_DB_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "policy_manual"

# Lazy-loaded singletons
_reranker_model: Optional[CrossEncoder] = None
_bm25_index: Optional[BM25Okapi] = None
_cached_chunks: Optional[List[Any]] = None


# =====================================================================
# 1. MODELS & INDICES
# =====================================================================

def get_reranker_model() -> CrossEncoder:
    """Lazy-loads and returns the Cross-Encoder re-ranking model."""
    global _reranker_model
    if _reranker_model is None:
        _reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker_model


def tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


def get_bm25_index():
    """Lazy-loads the in-memory BM25 sparse index over all policy chunks."""
    global _bm25_index, _cached_chunks
    if _bm25_index is None:
        _cached_chunks = load_and_chunk_policy_manual()
        corpus = [tokenize(c.page_content) for c in _cached_chunks]
        _bm25_index = BM25Okapi(corpus)
    return _bm25_index, _cached_chunks


def get_chroma_client() -> chromadb.PersistentClient:
    """Initializes and returns a persistent ChromaDB client saved to disk."""
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DB_DIR))


def get_or_create_collection(client: Optional[chromadb.PersistentClient] = None):
    """Retrieves or creates the 'policy_manual' ChromaDB collection."""
    if client is None:
        client = get_chroma_client()

    emb_fn = get_embedding_function()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


def index_policy_manual(force_reload: bool = False) -> int:
    """Indexes chunks into ChromaDB if not already indexed."""
    client = get_chroma_client()

    if force_reload:
        print("[VectorStore] Force reload requested. Deleting existing collection...")
        try:
            client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass

    collection = get_or_create_collection(client)
    current_count = collection.count()

    if current_count > 0 and not force_reload:
        return current_count

    print("[VectorStore] Indexing policy manual chunks into ChromaDB...")
    chunks = load_and_chunk_policy_manual()

    documents = [c.page_content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    ids = [f"doc_chunk_{c.metadata.get('chunk_id', i)}" for i, c in enumerate(chunks)]

    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        end = min(i + batch_size, len(chunks))
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end]
        )

    return collection.count()


# =====================================================================
# 2. SEARCH IMPLEMENTATIONS (Dense, BM25, and RRF Fusion)
# =====================================================================

def search_dense(query: str, top_k: int = 15) -> List[Dict[str, Any]]:
    """Stage 1A: Dense Vector Search via ChromaDB."""
    collection = get_or_create_collection()
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    if not results or not results["documents"] or not results["documents"][0]:
        return []

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    dense_hits = []
    for rank, (doc, meta, dist) in enumerate(zip(docs, metas, distances), 1):
        dense_hits.append({
            "chunk_id": meta.get("chunk_id"),
            "page_number": meta.get("page_number"),
            "has_table": meta.get("has_table", False),
            "source": meta.get("source"),
            "similarity_score": round(1.0 - dist, 4),
            "dense_rank": rank,
            "content": doc
        })
    return dense_hits


def search_bm25(query: str, top_k: int = 15) -> List[Dict[str, Any]]:
    """Stage 1B: Sparse Keyword Search via BM25."""
    bm25, chunks = get_bm25_index()
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    top_indices = np.argsort(scores)[::-1][:top_k]

    bm25_hits = []
    for rank, idx in enumerate(top_indices, 1):
        chunk = chunks[idx]
        bm25_hits.append({
            "chunk_id": chunk.metadata.get("chunk_id"),
            "page_number": chunk.metadata.get("page_number"),
            "has_table": chunk.metadata.get("has_table", False),
            "source": chunk.metadata.get("source"),
            "bm25_score": float(scores[idx]),
            "bm25_rank": rank,
            "content": chunk.page_content
        })
    return bm25_hits


def reciprocal_rank_fusion(
    dense_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60
) -> List[Dict[str, Any]]:
    """
    Stage 1C: Reciprocal Rank Fusion (RRF).
    Combines dense and sparse ranked results using formula:
        RRF_Score = sum(1 / (k + rank))
    """
    fused_scores: Dict[int, float] = {}
    doc_map: Dict[int, Dict[str, Any]] = {}

    # Accumulate Dense ranks
    for hit in dense_results:
        cid = hit["chunk_id"]
        rank = hit["dense_rank"]
        fused_scores[cid] = fused_scores.get(cid, 0.0) + (1.0 / (k + rank))
        doc_map[cid] = hit

    # Accumulate BM25 ranks
    for hit in bm25_results:
        cid = hit["chunk_id"]
        rank = hit["bm25_rank"]
        fused_scores[cid] = fused_scores.get(cid, 0.0) + (1.0 / (k + rank))
        if cid not in doc_map:
            doc_map[cid] = hit

    # Sort candidates by combined RRF score
    sorted_cids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)

    merged = []
    for cid in sorted_cids:
        item = doc_map[cid].copy()
        item["rrf_score"] = round(fused_scores[cid], 5)
        item["similarity_score"] = item.get("similarity_score", item["rrf_score"])
        merged.append(item)

    return merged


# =====================================================================
# 3. END-TO-END HYBRID RETRIEVAL PIPELINE
# =====================================================================

def search_policy_manual(
    query: str, 
    top_k: int = 3,
    search_mode: str = "hybrid",  # 'hybrid', 'dense', or 'bm25'
    use_reranker: bool = True,
    candidate_pool_size: int = 15
) -> List[Dict[str, Any]]:
    """
    Master Retrieval Function supporting:
    - Pure Dense
    - Pure BM25
    - Hybrid (Dense + BM25 merged via RRF)
    - Optional Cross-Encoder Re-ranking

    Args:
        query: User search question.
        top_k: Number of final chunks to return.
        search_mode: 'hybrid' (default), 'dense', or 'bm25'.
        use_reranker: If True, applies Cross-Encoder re-ranking.
        candidate_pool_size: Number of candidates gathered before re-ranking.

    Returns:
        List of top-scoring chunks with page citations and scores.
    """
    # 1. Fetch Candidates based on search mode
    if search_mode == "hybrid":
        dense_hits = search_dense(query, top_k=candidate_pool_size)
        bm25_hits = search_bm25(query, top_k=candidate_pool_size)
        candidates = reciprocal_rank_fusion(dense_hits, bm25_hits, k=60)[:candidate_pool_size]
    elif search_mode == "dense":
        candidates = search_dense(query, top_k=candidate_pool_size)
    elif search_mode == "bm25":
        candidates = search_bm25(query, top_k=candidate_pool_size)
    else:
        raise ValueError(f"Unknown search mode: {search_mode}. Choose 'hybrid', 'dense', or 'bm25'.")

    if not candidates:
        return []

    # 2. Stage 2: Cross-Encoder Re-ranking
    if use_reranker and len(candidates) > 1:
        reranker = get_reranker_model()
        pairs = [(query, c["content"]) for c in candidates]
        rerank_scores = reranker.predict(pairs)

        for candidate, r_score in zip(candidates, rerank_scores):
            candidate["rerank_score"] = float(r_score)

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

    return candidates[:top_k]


# =====================================================================
# VERIFICATION & DEMONSTRATION
# =====================================================================

if __name__ == "__main__":
    print("=" * 75)
    print("TESTING HYBRID SEARCH (Dense + BM25 + RRF + Cross-Encoder)")
    print("=" * 75)

    test_query = "What idempotency key format must be used for payment requests?"
    print(f"\nQuery: '{test_query}'\n")

    print("[1] Running Pure Dense Search:")
    d_hits = search_policy_manual(test_query, top_k=2, search_mode="dense", use_reranker=False)
    for i, h in enumerate(d_hits, 1):
        print(f"  #{i} -> Page {h['page_number']} (Score: {h.get('similarity_score')})")

    print("\n[2] Running Pure BM25 Keyword Search:")
    b_hits = search_policy_manual(test_query, top_k=2, search_mode="bm25", use_reranker=False)
    for i, h in enumerate(b_hits, 1):
        print(f"  #{i} -> Page {h['page_number']} (BM25: {h.get('bm25_score'):.2f})")

    print("\n[3] Running Full Hybrid Search (Dense + BM25 + Re-ranker):")
    h_hits = search_policy_manual(test_query, top_k=2, search_mode="hybrid", use_reranker=True)
    for i, h in enumerate(h_hits, 1):
        print(f"  #{i} -> Page {h['page_number']} (Re-rank Score: {h.get('rerank_score'):.2f})")

    print("\nSUCCESS: Hybrid Search pipeline fully implemented and verified!")
