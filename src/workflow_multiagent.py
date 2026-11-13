"""
Multi-Agent Specialist Workflow Module (README Section 6)
=========================================================
Coordinates two specialized agents:
1. 🕵️ Investigation Specialist (SQL Tools)
2. 📖 Policy Specialist (ChromaDB RAG Tool)

Architecture:
               [Customer Message]
                       │
                       ▼
            [Supervisor Router Node]
             (Classifies intent)
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
[investigation_agent]        [policy_agent]
         │                           │
         ▼                           ▼
[investigation_tools]        [policy_tools]
   (SQL Database)               (ChromaDB)
         │                           │
         └─────────────┬─────────────┘
                       ▼
                    [END]
"""

import sys
import json
from pathlib import Path
from typing import Annotated, Sequence, TypedDict, Optional, Literal

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
import os

from src.agent import (
    call_investigation_agent,
    call_policy_agent,
    INVESTIGATION_TOOLS,
    POLICY_TOOLS,
)


# =====================================================================
# 1. MULTI-AGENT WORKFLOW STATE
# =====================================================================
class MultiAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    customer_id: Optional[str]
    order_id: Optional[str]
    selected_specialist: Optional[str]


# =====================================================================
# 2. SUPERVISOR ROUTER NODE
# =====================================================================
ROUTER_PROMPT = """You are the Dispatcher for Apex Electronics customer support.
Your job is to read the customer's message and decide which specialist should handle it:

1. 'investigation': For questions about customer orders, delivery tracking, package arrival, return inspection, or refund status (needs SQL database).
2. 'policy': For general questions about return windows, warranty coverage, restocking fees, or damaged delivery rules (needs policy manual).

Reply with ONLY ONE WORD: 'investigation' or 'policy'.
"""

def router_node(state: MultiAgentState) -> dict:
    """Classifies the customer query and routes to the right specialist."""
    messages = state["messages"]
    last_user_msg = messages[-1].content

    api_key = os.getenv("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        google_api_key=api_key,
        temperature=0.0,
    )
    
    prompt = f"{ROUTER_PROMPT}\n\nCustomer Message: '{last_user_msg}'"
    res = llm.invoke([HumanMessage(content=prompt)])
    decision = res.content.strip().lower()

    if "policy" in decision:
        specialist = "policy"
    else:
        specialist = "investigation"

    return {"selected_specialist": specialist}


def route_after_supervisor(state: MultiAgentState) -> Literal["investigation_agent", "policy_agent"]:
    """Conditional Edge: Directs to the selected specialist."""
    if state.get("selected_specialist") == "policy":
        return "policy_agent"
    return "investigation_agent"


# =====================================================================
# 3. SPECIALIST NODES & CONDITIONAL EDGES
# =====================================================================
# Investigation Specialist Node
def investigation_node(state: MultiAgentState) -> dict:
    response = call_investigation_agent(state["messages"])
    return {"messages": [response]}

def check_investigation_tools(state: MultiAgentState) -> str:
    messages = state["messages"]
    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "investigation_tools"
    return END


# Policy Specialist Node
def policy_node(state: MultiAgentState) -> dict:
    response = call_policy_agent(state["messages"])
    return {"messages": [response]}

def check_policy_tools(state: MultiAgentState) -> str:
    messages = state["messages"]
    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "policy_tools"
    return END


# =====================================================================
# 4. ASSEMBLE MULTI-AGENT STATEGRAPH
# =====================================================================
def build_multiagent_workflow():
    """Builds and compiles the multi-agent specialist StateGraph."""
    workflow = StateGraph(MultiAgentState)

    # 1. Add Nodes
    workflow.add_node("router", router_node)
    
    # Specialist 1: Investigation (SQL)
    workflow.add_node("investigation_agent", investigation_node)
    workflow.add_node("investigation_tools", ToolNode(INVESTIGATION_TOOLS))

    # Specialist 2: Policy (RAG)
    workflow.add_node("policy_agent", policy_node)
    workflow.add_node("policy_tools", ToolNode(POLICY_TOOLS))

    # 2. Add Edges
    workflow.add_edge(START, "router")
    
    # Router conditional edge
    workflow.add_conditional_edges(
        "router",
        route_after_supervisor,
        {
            "investigation_agent": "investigation_agent",
            "policy_agent": "policy_agent",
        }
    )

    # Investigation Loop
    workflow.add_conditional_edges(
        "investigation_agent",
        check_investigation_tools,
        {
            "investigation_tools": "investigation_tools",
            END: END,
        }
    )
    workflow.add_edge("investigation_tools", "investigation_agent")

    # Policy Loop
    workflow.add_conditional_edges(
        "policy_agent",
        check_policy_tools,
        {
            "policy_tools": "policy_tools",
            END: END,
        }
    )
    workflow.add_edge("policy_tools", "policy_agent")

    # Compile with MemorySaver Checkpointer
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app


# =====================================================================
# 5. DEMONSTRATION & TEST
# =====================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("APEX ELECTRONICS: MULTI-AGENT SPECIALISTS WORKFLOW")
    print("=" * 70)

    app = build_multiagent_workflow()
    config = {"configurable": {"thread_id": "multiagent-demo-01"}}

    # Test 1: Policy Question -> Should route to Policy Specialist
    print("\n--- Test 1: Policy Query ---")
    q1 = "What is the return window for electronics?"
    print(f"[Customer]: {q1}")
    res1 = app.invoke({"messages": [HumanMessage(content=q1)]}, config=config)
    print(f"[Specialist Assigned]: {res1['selected_specialist'].upper()}")
    print(f"[Response]: {res1['messages'][-1].content}\n")

    # Test 2: Order Fact Question -> Should route to Investigation Specialist
    print("\n--- Test 2: Investigation Query ---")
    q2 = "Can you look up the status of my order ORD1001?"
    print(f"[Customer]: {q2}")
    res2 = app.invoke({"messages": [HumanMessage(content=q2)]}, config=config)
    print(f"[Specialist Assigned]: {res2['selected_specialist'].upper()}")
    print(f"[Response]: {res2['messages'][-1].content}\n")

