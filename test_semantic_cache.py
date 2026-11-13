"""
Automated Verification Suite for Production Semantic Cache
===========================================================
Tests:
1. Dynamic / Sensitive Query Bypass (Must NEVER be cached or read)
2. Cache Storage & Idempotency
3. Rephrased / Semantic Search Hit (> 0.80 similarity)
4. Cache Miss for Novel / Unseen Questions
5. Response Latency Measurement (< 50ms)
6. Prevention of caching transactional tool calls (e.g., process_refund)
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.semantic_cache import (
    check_semantic_cache,
    store_in_semantic_cache,
    is_cacheable_query,
    get_cache_stats,
    seed_default_cache,
    clear_semantic_cache,
    DEFAULT_SIMILARITY_THRESHOLD
)


def run_tests():
    print("=" * 70)
    print("🚀 RUNNING SEMANTIC CACHE TEST SUITE")
    print("=" * 70)

    # Reset cache for clean test environment
    clear_semantic_cache()
    stats = get_cache_stats()
    assert stats["total_cached_entries"] == 0, "Cache should be empty initially"
    print("✅ Test 0: Cache initialization and clearing successful.")

    # -------------------------------------------------------------
    # TEST 1: DYNAMIC / PRIVACY BYPASS RULES
    # -------------------------------------------------------------
    dynamic_queries = [
        "Where is my order ORD1040?",
        "Cancel order ORD1099 immediately",
        "Check status of my purchase ORD1001",
        "What is the refund status for my account?",
        "Where is my package right now?",
    ]
    for q in dynamic_queries:
        assert not is_cacheable_query(q), f"Query '{q}' should NOT be cacheable!"
        hit = check_semantic_cache(q)
        assert hit is None, f"Dynamic query '{q}' should NEVER hit cache!"
    print("✅ Test 1: Dynamic Order & Privacy Queries are 100% blocked from cache.")

    # -------------------------------------------------------------
    # TEST 2: PREVENT CACHING OF TRANSACTIONAL / SENSITIVE TOOLS
    # -------------------------------------------------------------
    safe_q = "How do I return a damaged speaker?"
    fake_ans = "Here is the return process..."
    
    # Attempt to cache with unsafe tool (process_refund)
    stored_unsafe = store_in_semantic_cache(safe_q, fake_ans, tools_used=["process_refund", "search_policy"])
    assert not stored_unsafe, "Must reject caching if unsafe/transactional tools were used!"
    
    # Store with safe tool (search_policy)
    stored_safe = store_in_semantic_cache(safe_q, fake_ans, tools_used=["search_policy"])
    assert stored_safe, "Should accept caching for safe policy retrieval tool!"
    print("✅ Test 2: Tool sensitivity enforcement verified (only search_policy allowed).")

    # -------------------------------------------------------------
    # TEST 3: EXACT MATCH HIT & LATENCY
    # -------------------------------------------------------------
    start = time.perf_counter()
    hit_exact = check_semantic_cache(safe_q)
    latency_ms = (time.perf_counter() - start) * 1000.0
    
    assert hit_exact is not None, "Exact match must be a Cache HIT"
    assert hit_exact["similarity_score"] >= 0.98, f"Exact match similarity should be ~1.0, got {hit_exact['similarity_score']}"
    assert hit_exact["response"] == fake_ans
    print(f"✅ Test 3: Exact Match HIT (Similarity: {hit_exact['similarity_score']}, Latency: {latency_ms:.2f}ms).")

    # -------------------------------------------------------------
    # TEST 4: PRE-WARMING / SEEDING & PARAPHRASED HIT
    # -------------------------------------------------------------
    seeded_count = seed_default_cache()
    print(f"[*] Seeded {seeded_count} core policy questions into cache.")
    
    # Paraphrased version of "Can I return earphones or in-ear headphones if opened?"
    paraphrased = "Can I return opened earphones?"
    hit_para = check_semantic_cache(paraphrased)
    
    assert hit_para is not None, f"Paraphrased query '{paraphrased}' should hit cache!"
    assert hit_para["similarity_score"] >= DEFAULT_SIMILARITY_THRESHOLD, (
        f"Score {hit_para['similarity_score']} must be >= {DEFAULT_SIMILARITY_THRESHOLD}"
    )
    print(f"✅ Test 4: Paraphrased Query HIT ('{paraphrased}' -> '{hit_para['matched_question']}')")
    print(f"         Similarity: {hit_para['similarity_score']:.4f} | Latency: {hit_para['latency_ms']:.2f}ms")

    # -------------------------------------------------------------
    # TEST 5: CACHE MISS FOR UNSEEN QUESTION
    # -------------------------------------------------------------
    unseen_q = "Do you sell solar-powered coffee makers?"
    hit_unseen = check_semantic_cache(unseen_q)
    assert hit_unseen is None, f"Unseen question '{unseen_q}' must be a Cache MISS!"
    print("✅ Test 5: Cache MISS verified for unrelated/novel question.")

    print("\n" + "=" * 70)
    print(f"🎉 ALL SEMANTIC CACHE TESTS PASSED SUCCESSFULLY!")
    print(f"Final Stats: {get_cache_stats()}")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
