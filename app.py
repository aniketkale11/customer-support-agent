"""
Apex Electronics - Customer Support Resolution Agent (Streamlit UI)
===================================================================
Role-Based Access Control (RBAC) Architecture:
1. Tab 1: 🧑‍💼 Customer Portal (Chat Only - Zero approval buttons)
2. Tab 2: 👔 Internal Supervisor Queue (Evidence Review & Authorization)
"""

import os
import sys
import uuid
import json
from pathlib import Path

# Add project root and customer-support-agent to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Ensure direct connectivity if proxy env vars exist
if "HTTPS_PROXY" in os.environ and "127.0.0.1:58080" in os.environ.get("HTTPS_PROXY", ""):
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        os.environ.pop(k, None)

import streamlit as st
from dotenv import load_dotenv

# Ensure environment variables (like LangSmith and API keys) are freshly loaded
load_dotenv(override=True)

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.types import Command
from src.workflow import build_workflow
from src.database import query_db
from src.guardrails import check_input_guardrail, sanitize_and_wrap_input
from src.semantic_cache import (
    check_semantic_cache,
    store_in_semantic_cache,
    is_cacheable_query,
    get_cache_stats,
    seed_default_cache,
    clear_semantic_cache
)


# =====================================================================
# 1. PAGE CONFIGURATION
# =====================================================================
st.set_page_config(
    page_title="Apex Electronics Support System",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =====================================================================
# 2. WORKFLOW CACHING
# =====================================================================
@st.cache_resource
def get_compiled_workflow():
    """Compiles and caches the LangGraph StateGraph workflow."""
    return build_workflow()

workflow_app = get_compiled_workflow()


# =====================================================================
# 3. HELPER PARSER & SESSION STATE
# =====================================================================
def extract_clean_text(content) -> str:
    """Parses AIMessage content into a clean string, unpacking Gemini dict blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"session-{uuid.uuid4().hex[:8]}"

if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": "Hello! I am your Apex Electronics Resolution Assistant. How can I assist you with your orders, returns, or support policies today?",
            "tools_called": []
        }
    ]


# =====================================================================
# 4. SIDEBAR - SYSTEM DASHBOARD
# =====================================================================
with st.sidebar:
    st.title("🎧 System Control")
    st.caption("Forward Deployed AI Engineer Architecture")

    st.markdown("---")
    st.subheader("🔒 Security & RBAC")
    st.markdown(
        """
        - **Customer Portal:** Read-only & proposal staging.
        - **Supervisor Desk:** Authorized financial execution.
        - **Workflow Guard:** `LangGraph interrupt()`
        - **Input Guardrail:** Active Injection Bouncer
        - **Data Boundary:** XML Delimiter Isolation
        """
    )

    # Architecture Flowchart Image
    graph_img_path = BASE_DIR / "workflow_graph.png"
    if graph_img_path.exists():
        with st.expander("📊 View Architecture Flowchart", expanded=False):
            st.image(str(graph_img_path), caption="LangGraph State Machine with HITL", use_container_width=True)

    st.markdown("---")
    st.subheader("⚡ Semantic Cache")
    cache_stats = get_cache_stats()
    st.markdown(
        f"""
        - **Status:** Active 🟢
        - **Cached Entries:** `{cache_stats['total_cached_entries']}`
        - **Threshold:** `{cache_stats['similarity_threshold']}`
        - **Engine:** ChromaDB (`all-MiniLM-L6-v2`)
        """
    )
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("🌱 Pre-warm", use_container_width=True, help="Seed common FAQ responses"):
            added = seed_default_cache()
            st.toast(f"Seeded {added} common policy Q&As into cache!", icon="⚡")
            st.rerun()
    with col_c2:
        if st.button("🗑️ Purge", use_container_width=True, help="Clear cache"):
            clear_semantic_cache()
            st.toast("Semantic cache cleared!", icon="🧹")
            st.rerun()

    st.markdown("---")
    st.subheader("💡 Quick Test Scenarios")
    
    quick_queries = [
        ("Return Policy", "What is the return window for electronics?"),
        ("Order Status", "Where is my order ORD1001?"),
        ("Check Refund Status", "Can you check refund status for ORD1018?"),
        ("New Return Inquiry", "Has my returned package for ORD1003 arrived?"),
    ]

    for label, query_text in quick_queries:
        if st.button(f"👉 {label}", use_container_width=True):
            st.session_state.pending_input = query_text

    st.markdown("---")
    if st.button("🔄 Reset Conversation Thread", use_container_width=True):
        st.session_state.thread_id = f"session-{uuid.uuid4().hex[:8]}"
        st.session_state.pending_approval = None
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "Conversation reset. How can I help you today?",
                "tools_called": []
            }
        ]
        st.rerun()

    st.caption(f"Session Thread ID: `{st.session_state.thread_id}`")


# =====================================================================
# 5. ROLE-BASED TABS INTERFACE
# =====================================================================
tab_customer, tab_supervisor = st.tabs([
    "🧑‍💼 Customer Support Portal", 
    "👔 Internal Supervisor Queue"
])


# =====================================================================
# TAB 1: CUSTOMER PORTAL (CHAT ONLY - ZERO APPROVAL BUTTONS)
# =====================================================================
with tab_customer:
    st.title("Apex Electronics Customer Resolution")
    st.caption("Ask questions about orders, deliveries, returns, or warranty policies.")

    # Render customer conversation history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            if msg.get("cached_info"):
                ci = msg["cached_info"]
                st.caption(
                    f"⚡ *Served from Semantic Cache ({ci['similarity_score'] * 100:.1f}% match | {ci['latency_ms']}ms | 0 LLM Tokens)*"
                )
            st.markdown(msg["content"])
            
            # Display tools called (if any)
            if msg.get("tools_called"):
                with st.expander("🔍 Tools Used Behind the Scenes", expanded=False):
                    for t in msg["tools_called"]:
                        st.markdown(f"- **Tool:** `{t['name']}`")
                        st.markdown(f"  - **Arguments:** `{t['args']}`")
                        if t.get("result"):
                            st.code(str(t["result"])[:300] + ("..." if len(str(t["result"])) > 300 else ""), language="json")

    # Customer Chat Input
    user_input = st.chat_input("Type your message or question here...")

    if "pending_input" in st.session_state and st.session_state.pending_input:
        user_input = st.session_state.pending_input
        del st.session_state["pending_input"]

    if user_input:
        # Display User Message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # -----------------------------------------------------------------
        # LAYER 1: INPUT GUARDRAIL BOUNCER (Prompt Injection Check)
        # -----------------------------------------------------------------
        guard_result = check_input_guardrail(user_input)

        if not guard_result.is_safe:
            # Blocked before reaching Gemini (Zero cost, Zero risk!)
            blocked_reply = guard_result.safe_message
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": blocked_reply
            })
            with st.chat_message("assistant"):
                st.markdown(blocked_reply)
        else:
            # If the query was reviewed by the Semantic Guard and cleared as safe
            if guard_result.evaluated_by_guard and guard_result.is_safe:
                st.toast(f"🛡️ Guardrail: False alarm cleared ({guard_result.guard_reason})", icon="ℹ️")

            # -------------------------------------------------------------
            # LAYER 2: SEMANTIC CACHE CHECK (Zero Cost, < 20ms Latency)
            # -------------------------------------------------------------
            cached_result = check_semantic_cache(user_input)

            if cached_result and cached_result.get("hit"):
                cached_answer = cached_result["response"]
                sim_pct = cached_result["similarity_score"] * 100.0
                latency = cached_result["latency_ms"]

                with st.chat_message("assistant"):
                    st.caption(
                        f"⚡ *Served from Semantic Cache ({sim_pct:.1f}% match | {latency:.1f}ms | 0 LLM Tokens)*"
                    )
                    st.markdown(cached_answer)

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": cached_answer,
                    "tools_called": [],
                    "cached_info": cached_result
                })
            else:
                # -------------------------------------------------------------
                # LAYER 3: XML DELIMITER WRAPPING & AGENT WORKFLOW
                # -------------------------------------------------------------
                wrapped_input = sanitize_and_wrap_input(user_input)

                # Invoke Agent Workflow with XML Delimited Input
                with st.chat_message("assistant"):
                    with st.spinner("Investigating records & policies..."):
                        config = {"configurable": {"thread_id": st.session_state.thread_id}}
                        inputs = {"messages": [HumanMessage(content=wrapped_input)]}

                    try:
                        result = workflow_app.invoke(inputs, config=config)
                        
                        # Check if the workflow paused on an interrupt()
                        state_snapshot = workflow_app.get_state(config)
                        pending_interrupt = None
                        for task in state_snapshot.tasks:
                            if hasattr(task, "interrupts") and task.interrupts:
                                pending_interrupt = task.interrupts[0].value
                                break

                        result_messages = result.get("messages", [])
                        tools_called = []
                        final_response = "I have reviewed your inquiry."

                        for m in result_messages:
                            if hasattr(m, "tool_calls") and m.tool_calls:
                                for tc in m.tool_calls:
                                    tools_called.append({
                                        "name": tc.get("name"),
                                        "args": tc.get("args")
                                    })
                            elif isinstance(m, ToolMessage):
                                if tools_called:
                                    tools_called[-1]["result"] = extract_clean_text(m.content)
                            elif isinstance(m, AIMessage) and m.content:
                                final_response = extract_clean_text(m.content)

                        # If an interrupt occurred, ensure customer sees a clear status update
                        if pending_interrupt:
                            st.session_state.pending_approval = pending_interrupt
                            final_response = (
                                f"📋 **Refund Proposal Staged (Awaiting Supervisor Review)**\n\n"
                                f"Your return has passed inspection and a formal proposal (`{pending_interrupt.get('proposal_id')}`) "
                                f"for **₹{pending_interrupt.get('amount', 0.0):,.2f}** has been generated.\n\n"
                                f"Under company financial controls, this has been submitted to the **Supervisor Approval Queue**. "
                                f"You will receive confirmation once the supervisor approves and executes the refund."
                            )

                        # Render response
                        st.markdown(final_response)

                        if tools_called:
                            with st.expander("🔍 Tools Used Behind the Scenes", expanded=False):
                                for t in tools_called:
                                    st.markdown(f"- **Tool:** `{t['name']}`")
                                    st.markdown(f"  - **Arguments:** `{t['args']}`")
                                    if t.get("result"):
                                        st.code(str(t["result"])[:300] + ("..." if len(str(t["result"])) > 300 else ""), language="json")

                        # -------------------------------------------------------------
                        # LAYER 4: POPULATE SEMANTIC CACHE (IF ELIGIBLE)
                        # -------------------------------------------------------------
                        if not pending_interrupt and is_cacheable_query(user_input):
                            tool_names = [t.get("name") for t in tools_called if t.get("name")]
                            stored = store_in_semantic_cache(user_input, final_response, tool_names)
                            if stored:
                                st.toast("⚡ Policy response cached for instant future lookups!", icon="💾")

                        # Save to chat history
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": final_response,
                            "tools_called": tools_called
                        })

                        # If pending approval, trigger notification
                        if pending_interrupt:
                            st.toast("🔔 New refund proposal routed to Supervisor Queue!", icon="⚠️")

                    except Exception as e:
                        error_msg = f"An error occurred: {str(e)}"
                        st.error(error_msg)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": error_msg,
                            "tools_called": []
                        })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg,
                        "tools_called": []
                    })


# =====================================================================
# TAB 2: INTERNAL SUPERVISOR QUEUE (ADMIN CONTROLS)
# =====================================================================
with tab_supervisor:
    st.title("👔 Internal Operations & Supervisor Desk")
    st.caption("Authorized review queue for financial actions and refund approvals (README Section 11)")

    # 1. Active Pending Approval from Workflow
    if st.session_state.pending_approval:
        req = st.session_state.pending_approval
        st.error("🚨 ACTION REQUIRED: 1 Pending Refund Proposal Awaiting Review")
        
        with st.container(border=True):
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.markdown(f"**Proposal ID:** `{req.get('proposal_id', 'N/A')}`")
                st.markdown(f"**Order ID:** `{req.get('order_id', 'N/A')}`")
                st.markdown(f"**Proposed Amount:** :green[**₹{req.get('amount', 0.0):,.2f}**]")
            with col_info2:
                st.markdown(f"**Workflow Thread:** `{st.session_state.thread_id}`")
                st.markdown(f"**Evidence / Notes:** {req.get('reason', 'Policy criteria confirmed')}")
                st.markdown("**Reviewer:** `Alice (Senior Operations Supervisor)`")

            st.markdown("---")
            col_b1, col_b2 = st.columns(2)
            config = {"configurable": {"thread_id": st.session_state.thread_id}}

            with col_b1:
                if st.button("✅ Approve & Disburse Refund", type="primary", use_container_width=True):
                    with st.spinner("Executing payment transaction with mock provider..."):
                        resume_cmd = Command(resume={"decision": "APPROVED", "reviewer_id": "SUPERVISOR_ALICE"})
                        res = workflow_app.invoke(resume_cmd, config=config)
                        final_msg = res["messages"][-1]
                        
                        # Append confirmation to customer chat
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": extract_clean_text(final_msg.content),
                            "tools_called": []
                        })
                        st.session_state.pending_approval = None
                        st.success("✅ Refund successfully executed! Customer notified.")
                        st.rerun()

            with col_b2:
                if st.button("❌ Reject Refund Request", use_container_width=True):
                    with st.spinner("Recording rejection decision..."):
                        resume_cmd = Command(resume={"decision": "REJECTED", "reviewer_id": "SUPERVISOR_ALICE"})
                        res = workflow_app.invoke(resume_cmd, config=config)
                        final_msg = res["messages"][-1]
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": extract_clean_text(final_msg.content),
                            "tools_called": []
                        })
                        st.session_state.pending_approval = None
                        st.info("Refund rejected. Rejection recorded in customer chat.")
                        st.rerun()
    else:
        st.success("✅ All clear! No refund proposals currently pending review for this thread.")

    st.markdown("---")
    st.subheader("📊 Live Refund Ledger (Database Audit)")
    
    # Query database for all refund records
    refund_rows = query_db(
        "SELECT refund_id, order_id, customer_id, requested_amount, approved_amount, refund_status, provider_transaction_id, notes FROM refunds ORDER BY rowid DESC LIMIT 10"
    )
    if refund_rows:
        st.dataframe(refund_rows, use_container_width=True)
    else:
        st.info("No records in refunds ledger.")
