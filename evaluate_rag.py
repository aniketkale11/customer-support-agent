"""
RAG Scientific Evaluation Benchmark (Golden Dataset)
====================================================
This script evaluates our ChromaDB RAG retrieval pipeline against our
Golden Evaluation Dataset stored in 'data/golden_dataset.json'.

Metrics Evaluated:
1. Hit Rate @ 1: Did the correct page appear as the #1 top hit?
2. Hit Rate @ 3: Did the correct page appear anywhere in the Top-3 hits?
3. MRR (Mean Reciprocal Rank): Measures ranking position quality (1.0 = perfect #1 every time).
4. Average Latency (ms): Execution speed per query.
"""

import json
import time
from typing import List, Dict, Any
from pathlib import Path
import sys

# Project root
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.vectorstore import search_policy_manual

GOLDEN_DATASET_PATH = BASE_DIR / "data" / "golden_dataset.json"


def load_golden_dataset() -> List[Dict[str, Any]]:
    """Loads the golden dataset from data/golden_dataset.json."""
    if not GOLDEN_DATASET_PATH.exists():
        raise FileNotFoundError(f"Golden dataset not found at: {GOLDEN_DATASET_PATH}")
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_retrieval_pipeline() -> Dict[str, Any]:
    dataset = load_golden_dataset()

    print("=" * 85)
    print("RAG GOLDEN DATASET RETRIEVAL BENCHMARK")
    print("=" * 85)
    print(f"Dataset File: {GOLDEN_DATASET_PATH.name}")
    print(f"Total Golden Test Cases: {len(dataset)}")
    print(f"Top-K Evaluated: 3\n")

    hits_at_1 = 0
    hits_at_3 = 0
    reciprocal_ranks = []
    latencies_ms = []

    results_table = []

    for tc in dataset:
        tc_id = tc["id"]
        query = tc["query"]
        exp_page = tc["expected_page"]

        start_time = time.perf_counter()
        retrieved_chunks = search_policy_manual(query=query, top_k=3)
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        latencies_ms.append(latency_ms)

        retrieved_pages = [c.get("page_number") for c in retrieved_chunks]
        
        # Check Rank of Expected Page
        rank = None
        for i, page in enumerate(retrieved_pages, 1):
            if page == exp_page:
                rank = i
                break

        # Calculate metrics
        if rank == 1:
            hits_at_1 += 1
            hits_at_3 += 1
            reciprocal_ranks.append(1.0)
            status = "PERFECT (#1)"
        elif rank is not None and rank <= 3:
            hits_at_3 += 1
            reciprocal_ranks.append(1.0 / rank)
            status = f"HIT (#{rank})"
        else:
            reciprocal_ranks.append(0.0)
            status = "MISS"

        top_score = retrieved_chunks[0].get("rerank_score", retrieved_chunks[0].get("similarity_score", 0.0)) if retrieved_chunks else 0.0

        results_table.append({
            "id": tc_id,
            "status": status,
            "exp_page": exp_page,
            "ret_pages": retrieved_pages,
            "rank": rank if rank else "-",
            "top_score": top_score,
            "latency": latency_ms,
            "query": query[:45] + "..." if len(query) > 45 else query
        })

    # Print Table
    print(f"{'ID':<6} | {'Status':<13} | {'Exp Page':<8} | {'Retrieved Pages':<17} | {'Top Score':<9} | {'Latency':<8} | {'Query'}")
    print("-" * 115)
    for r in results_table:
        ret_pages_str = str(r["ret_pages"])
        print(f"{r['id']:<6} | {r['status']:<13} | Page {r['exp_page']:<3} | {ret_pages_str:<17} | {r['top_score']:<9.2f} | {r['latency']:<6.1f}ms | {r['query']}")

    # Final Scorecard
    total_q = len(dataset)
    hit_rate_1 = (hits_at_1 / total_q) * 100.0
    hit_rate_3 = (hits_at_3 / total_q) * 100.0
    mrr = sum(reciprocal_ranks) / total_q
    avg_latency = sum(latencies_ms) / total_q

    print("\n" + "=" * 85)
    print("FINAL BENCHMARK SCORECARD (METRIC 1: CONTEXT RELEVANCE)")
    print("=" * 85)
    print(f"  Hit Rate @ 1 (Found at Rank #1):  {hit_rate_1:.1f}% ({hits_at_1}/{total_q})")
    print(f"  Hit Rate @ 3 (Found in Top 3):    {hit_rate_3:.1f}% ({hits_at_3}/{total_q})")
    print(f"  MRR (Mean Reciprocal Rank):       {mrr:.3f} / 1.000")
    print(f"  Average Latency:                  {avg_latency:.1f} ms per query")
    print("=" * 85)

    return {
        "hit_rate_1": hit_rate_1,
        "hit_rate_3": hit_rate_3,
        "mrr": mrr,
        "avg_latency": avg_latency
    }


if __name__ == "__main__":
    evaluate_retrieval_pipeline()
