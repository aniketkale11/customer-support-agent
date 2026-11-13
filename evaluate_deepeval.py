"""
RAG Triad Evaluation Benchmark using DeepEval
=============================================
This benchmark evaluates our RAG pipeline on the 3 core RAG Triad metrics:
1. Faithfulness (Groundedness): Did the LLM invent facts not in the retrieved chunks?
2. Answer Relevancy: Did the LLM directly answer what was asked?
3. Contextual Relevancy: Were the retrieved ChromaDB chunks relevant to the query?

Judge Model:
Google Gemini (gemini-3.5-flash-lite) wrapped in DeepEvalBaseLLM.
"""

import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure direct connectivity if proxy env vars exist
if "HTTPS_PROXY" in os.environ and "127.0.0.1:58080" in os.environ.get("HTTPS_PROXY", ""):
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        os.environ.pop(k, None)

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load environment variables
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY is missing from environment. Please check your .env file.")

# DeepEval imports
try:
    from deepeval.test_case import LLMTestCase
    from deepeval.metrics import (
        FaithfulnessMetric,
        AnswerRelevancyMetric,
        ContextualRelevancyMetric,
    )
    from deepeval.models.base_model import DeepEvalBaseLLM
except ImportError:
    print("❌ ERROR: 'deepeval' is not installed yet!")
    print("👉 Please run: .venv\\Scripts\\python.exe -m pip install deepeval")
    sys.exit(1)

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.vectorstore import search_policy_manual
from src.rag import format_citations


# =====================================================================
# 1. CUSTOM DEEPEVAL GEMINI JUDGE WRAPPER
# =====================================================================
class GeminiJudge(DeepEvalBaseLLM):
    """
    Custom DeepEvalBaseLLM wrapper to use Google Gemini as the evaluation judge.
    Enables running DeepEval without requiring an OpenAI API key!
    """
    def __init__(self, model_name: str = "gemini-3.5-flash-lite"):
        self.model_name = model_name
        self.model = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.0,
        )

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        res = self.model.invoke(prompt)
        content = res.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in content]
            return "".join(parts)
        return str(content)

    async def a_generate(self, prompt: str) -> str:
        res = await self.model.ainvoke(prompt)
        content = res.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in content]
            return "".join(parts)
        return str(content)

    def get_model_name(self) -> str:
        return self.model_name


# Helper to clean Gemini output text
def clean_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in content]
        return "".join(parts)
    return str(content)


# =====================================================================
# 2. RUN EVALUATION BENCHMARK
# =====================================================================
def run_deepeval_benchmark():
    print("=" * 75)
    print("🔺 RAG TRIAD EVALUATION BENCHMARK (DeepEval + Google Gemini Judge)")
    print("=" * 75)

    # 1. Load Golden Dataset
    dataset_path = BASE_DIR / "data" / "golden_dataset.json"
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"Loaded {len(test_cases)} test cases from {dataset_path.name}\n")

    # 2. Initialize Gemini Judge & LLM Generator
    judge = GeminiJudge(model_name="gemini-3.5-flash-lite")
    generator_llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        google_api_key=api_key,
        temperature=0.0,
    )

    # 3. Initialize the 3 Triad Metrics (Threshold: 0.70)
    metric_faithfulness = FaithfulnessMetric(threshold=0.7, model=judge)
    metric_answer_rel = AnswerRelevancyMetric(threshold=0.7, model=judge)
    metric_context_rel = ContextualRelevancyMetric(threshold=0.7, model=judge)

    results = []
    start_time = time.time()

    for idx, tc in enumerate(test_cases, 1):
        tc_id = tc["id"]
        query = tc["query"]
        topic = tc.get("topic", "Policy Query")

        print(f"[{idx}/{len(test_cases)}] Evaluating {tc_id}: '{topic}'...")

        # Step A: Retrieve Chunks from ChromaDB
        raw_results = search_policy_manual(query=query, top_k=3)
        retrieval_context = [r.get("content", "").strip() for r in raw_results if r.get("content")]

        # Step B: Generate Answer from Gemini using Retrieved Chunks
        citations = format_citations(raw_results)
        prompt = (
            f"You are the official customer support agent for Apex Electronics.\n"
            f"Answer the customer question strictly using ONLY the policy snippets below.\n"
            f"If the policy does not state the answer, say you cannot confirm.\n\n"
            f"POLICY CONTEXT:\n{citations}\n\n"
            f"CUSTOMER QUESTION:\n{query}"
        )
        ai_msg = generator_llm.invoke([HumanMessage(content=prompt)])
        actual_output = clean_text(ai_msg.content)

        # Step C: Create DeepEval LLMTestCase
        test_case_obj = LLMTestCase(
            input=query,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
        )

        # Step D: Grade the 3 Triad Metrics
        try:
            metric_faithfulness.measure(test_case_obj)
            faith_score = metric_faithfulness.score
            faith_reason = metric_faithfulness.reason
        except Exception as e:
            faith_score, faith_reason = 0.0, f"Error: {e}"

        try:
            metric_answer_rel.measure(test_case_obj)
            ans_rel_score = metric_answer_rel.score
            ans_rel_reason = metric_answer_rel.reason
        except Exception as e:
            ans_rel_score, ans_rel_reason = 0.0, f"Error: {e}"

        try:
            metric_context_rel.measure(test_case_obj)
            ctx_rel_score = metric_context_rel.score
            ctx_rel_reason = metric_context_rel.reason
        except Exception as e:
            ctx_rel_score, ctx_rel_reason = 0.0, f"Error: {e}"

        results.append({
            "id": tc_id,
            "topic": topic,
            "faithfulness": faith_score,
            "answer_relevancy": ans_rel_score,
            "contextual_relevancy": ctx_rel_score,
            "faith_reason": faith_reason,
            "ans_reason": ans_rel_reason,
        })

        print(f"    -> Faithfulness: {faith_score:.2f} | Answer Rel: {ans_rel_score:.2f} | Context Rel: {ctx_rel_score:.2f}\n")

    elapsed = time.time() - start_time

    # =====================================================================
    # 3. PRINT SUMMARY BENCHMARK REPORT TABLE
    # =====================================================================
    print("\n" + "=" * 90)
    print("                       DEEPEVAL RAG TRIAD SCORECARD")
    print("=" * 90)
    header = f"{'ID':<7} | {'Topic':<30} | {'Context Rel':<11} | {'Faithfulness':<12} | {'Answer Rel':<10}"
    print(header)
    print("-" * 90)

    avg_ctx = sum(r["contextual_relevancy"] for r in results) / len(results)
    avg_faith = sum(r["faithfulness"] for r in results) / len(results)
    avg_ans = sum(r["answer_relevancy"] for r in results) / len(results)

    for r in results:
        ctx_str = f"{r['contextual_relevancy']:.2f}"
        faith_str = f"{r['faithfulness']:.2f}"
        ans_str = f"{r['answer_relevancy']:.2f}"
        print(f"{r['id']:<7} | {r['topic'][:30]:<30} | {ctx_str:<11} | {faith_str:<12} | {ans_str:<10}")

    print("-" * 90)
    print(f"{'AVERAGE':<39} | {avg_ctx:<11.2f} | {avg_faith:<12.2f} | {avg_ans:<10.2f}")
    print("=" * 90)
    print(f"⏱️ Total Benchmark Duration: {elapsed:.1f}s ({elapsed / len(results):.1f}s / test case)")
    print("=" * 90)


if __name__ == "__main__":
    run_deepeval_benchmark()

