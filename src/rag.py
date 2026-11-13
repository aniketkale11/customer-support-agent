"""
Phase 2: RAG Retrieval Pipeline & Agent Tool
=============================================
This module is the final bridge between ChromaDB and the LangGraph agent:
1. Exposes the official LangChain `@tool def search_policy(query: str) -> str`.
2. Queries ChromaDB for the Top-K matching policy chunks.
3. Enforces a Similarity Score Guardrail:
   - If similarity score is below threshold (0.25), it returns a graceful fallback
     instead of letting the LLM hallucinate an answer.
4. Formats clean citations:
   - "[Source: Apex_Electronics_Customer_Support_Manual.pdf | Page X | Match Confidence: Y.YY]"
"""

from pathlib import Path
from typing import List, Dict, Any
from langchain_core.tools import tool

# Internal imports
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.vectorstore import search_policy_manual

# Minimum similarity confidence threshold to prevent hallucinations
MIN_CONFIDENCE_THRESHOLD = 0.25


def format_citations(results: List[Dict[str, Any]]) -> str:
    """
    Format raw ChromaDB results into a clean, cited string
    that includes source document, page number, and similarity score.
    """
    if not results:
        return "No relevant policy documents found."

    formatted_sections = []
    for idx, res in enumerate(results, 1):
        source = res.get("source", "Policy Manual")
        page = res.get("page_number", "Unknown")
        score = res.get("similarity_score", 0.0)
        content = res.get("content", "").strip()

        section = (
            f"--- [Snippet #{idx} | Source: {source} | Page {page} | Confidence: {score:.2f}] ---\n"
            f"{content}\n"
        )
        formatted_sections.append(section)

    return "\n".join(formatted_sections)


@tool
def search_policy(query: str) -> str:
    """Search company policy documents for rules on returns, refunds, warranties, and exceptions.

    Use this tool whenever a customer asks about return windows, eligibility,
    restocking fees, damaged delivery procedures, or supervisor approval limits.

    Args:
        query: Specific search phrase (e.g., 'earphones return window', 'damaged package photo requirement').

    Returns:
        Relevant policy sections with source document, page numbers, and confidence scores.
    """
    # 1. Retrieve top 3 matching chunks from ChromaDB
    raw_results = search_policy_manual(query=query, top_k=3)

    if not raw_results:
        return f"No policy information found for query: '{query}'."

    # 2. Guardrail Check: Check top result confidence
    top_score = raw_results[0].get("similarity_score", 0.0)
    if top_score < MIN_CONFIDENCE_THRESHOLD:
        return (
            f"No confident policy match found for query: '{query}' (Top confidence: {top_score:.2f} < {MIN_CONFIDENCE_THRESHOLD}). "
            "Please consult an internal operations supervisor for clarification."
        )

    # 3. Format citations for the Agent
    return format_citations(raw_results)


# =====================================================================
# LIVE VERIFICATION & DEMONSTRATION
# =====================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("STEP 4: RAG TOOL VERIFICATION (search_policy)")
    print("=" * 65)

    print(f"Tool Name: {search_policy.name}")
    print(f"Tool Description: {search_policy.description[:70]}...\n")

    # Test 1: Valid Return Policy Query
    valid_query = "What is the return policy for damaged delivery items?"
    print(f"[1] Testing Valid Query: '{valid_query}'")
    print("-" * 65)
    tool_output_1 = search_policy.invoke({"query": valid_query})
    print(tool_output_1)

    # Test 2: Table-specific Approval Query
    table_query = "Who has authority to approve refunds over INR 10,000?"
    print(f"\n[2] Testing Table/Approval Query: '{table_query}'")
    print("-" * 65)
    tool_output_2 = search_policy.invoke({"query": table_query})
    print(tool_output_2)

    # Test 3: Irrelevant Query (Testing the Confidence Guardrail!)
    junk_query = "How do I bake a homemade chocolate cake?"
    print(f"\n[3] Testing Irrelevant Query (Guardrail Test): '{junk_query}'")
    print("-" * 65)
    tool_output_3 = search_policy.invoke({"query": junk_query})
    print(tool_output_3)

    print("\nSUCCESS: search_policy RAG tool verified with guardrails and citations!")
