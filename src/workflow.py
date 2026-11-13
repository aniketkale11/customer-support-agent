"""
Workflow Module: LangGraph State, Human Approval (HITL), and Routing
=====================================================================
Coordinates the end-to-end resolution workflow:
1. AgentState: Tracks messages, proposal metadata, and approval decisions.
2. Nodes:
   - "agent": LLM reasoning (investigates orders, policies, stages proposals).
   - "tools": Executes read tools & proposal creation.
   - "human_approval": Pauses workflow via interrupt() for supervisor review.
   - "execute_refund": Deterministic code execution of approved refunds.
3. Routing:
   - "agent" -> "tools" (if tool calls requested)
   - "tools" -> "human_approval" (if a new refund proposal was created)
   - "tools" -> "agent" (for standard read tools)
   - "human_approval" -> "execute_refund" (after supervisor decision)
   - "execute_refund" -> END
"""

import sys
import json
import uuid
from pathlib import Path
from typing import Annotated, Sequence, TypedDict, Optional

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

# Import Agent brain and tools
from src.agent import call_agent, SUPPORT_TOOLS
from src.tools import execute_approved_refund


# =====================================================================
# 1. EXPANDED WORKFLOW STATE (README Section 10)
# =====================================================================
class AgentState(TypedDict):
    """
    Workflow state containing conversation history and approval metadata.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    customer_id: Optional[str]
    order_id: Optional[str]
    proposed_action_id: Optional[str]
    proposed_amount: Optional[float]
    proposal_reason: Optional[str]
    approval_status: Optional[str]
    reviewer_id: Optional[str]


# =====================================================================
# 2. WORKFLOW NODES
# =====================================================================
def agent_node(state: AgentState) -> dict:
    """Node: Agent Reasoning Step."""
    response = call_agent(state["messages"])
    return {"messages": [response]}


def human_approval_node(state: AgentState) -> dict:
    """
    Node: Human-in-the-Loop Approval (README Section 11).
    Pauses the workflow using interrupt() and waits for supervisor decision.
    """
    # 1. Package proposal details for the supervisor screen
    approval_request = {
        "action": "REFUND_APPROVAL_REQUIRED",
        "proposal_id": state.get("proposed_action_id"),
        "order_id": state.get("order_id"),
        "amount": state.get("proposed_amount"),
        "reason": state.get("proposal_reason"),
    }

    # 2. PAUSE WORKFLOW: Execution stops here until resumed by UI
    decision = interrupt(approval_request)

    # 3. When resumed, decision contains {'decision': 'APPROVED'/'REJECTED', 'reviewer_id': '...'}
    return {
        "approval_status": decision.get("decision", "REJECTED"),
        "reviewer_id": decision.get("reviewer_id", "SUPERVISOR"),
    }


def execute_refund_node(state: AgentState) -> dict:
    """
    Node: Deterministic Execution of Approved Refund (Financial Safety).
    The LLM cannot disburse money; this code executes strictly after approval.
    """
    decision = state.get("approval_status")
    proposal_id = state.get("proposed_action_id")
    order_id = state.get("order_id")
    amount = state.get("proposed_amount", 0.0)
    reviewer = state.get("reviewer_id", "Supervisor")

    if decision == "APPROVED":
        # Generate idempotent key to protect against duplicate payments
        idempotency_key = f"IDEMP-{proposal_id}"
        
        # Call deterministic payment execution tool
        result = execute_approved_refund.invoke({
            "proposal_id": proposal_id,
            "idempotency_key": idempotency_key
        })

        if result.get("success"):
            txn_id = result.get("provider_transaction_id", "N/A")
            confirmation_text = (
                f"✅ **Supervisor Approval Verified** (Reviewer: {reviewer})\n\n"
                f"Your refund of **₹{amount:,.2f}** for order **{order_id}** has been successfully executed with our payment provider.\n"
                f"- **Proposal ID:** `{proposal_id}`\n"
                f"- **Transaction ID:** `{txn_id}`\n"
                f"- **Status:** `COMPLETED`\n\n"
                f"The amount should reflect in your original payment method in 3–5 business days."
            )
        else:
            confirmation_text = f"❌ Execution error: {result.get('error', 'Unknown payment error')}"

    else:
        # Rejected by human supervisor
        confirmation_text = (
            f"ℹ️ **Supervisor Review Update**\n\n"
            f"Your refund request for order **{order_id}** was reviewed by supervisor ({reviewer}) and was not approved under standard policy. "
            f"Please reach out to support if you have additional evidence or documentation."
        )

    return {
        "messages": [AIMessage(content=confirmation_text)]
    }


# =====================================================================
# 3. ROUTING LOGIC
# =====================================================================
def check_after_agent(state: AgentState) -> str:
    """Routes to 'tools' if tool calls are requested; otherwise finishes."""
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


def check_after_tools(state: AgentState) -> dict:
    """
    Inspects tool outputs.
    If a refund is in 'PENDING_APPROVAL' (either newly proposed or retrieved from DB),
    routes to 'human_approval' node to trigger supervisor interrupt().
    Otherwise loops back to 'agent' for standard Q&A.
    """
    messages = state["messages"]
    
    # Inspect the most recent tool execution
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            try:
                # Parse tool output
                content = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                if isinstance(content, dict):
                    status = content.get("status") or content.get("refund_status")
                    if status == "PENDING_APPROVAL":
                        proposal_id = content.get("proposal_id") or content.get("refund_id")
                        amount = content.get("requested_amount") or content.get("amount") or 0.0
                        order_id = content.get("order_id")
                        reason = content.get("notes") or content.get("message") or "Policy return verified"
                        
                        return Command(
                            goto="human_approval",
                            update={
                                "proposed_action_id": proposal_id,
                                "proposed_amount": float(amount),
                                "order_id": order_id,
                                "proposal_reason": reason,
                            }
                        )
            except Exception:
                pass
            break

    # Standard tool execution (read tools) -> return to agent
    return Command(goto="agent")


# =====================================================================
# 4. ASSEMBLE STATEGRAPH WORKFLOW
# =====================================================================
def build_workflow():
    """
    Constructs and compiles the full LangGraph workflow with Human-in-the-Loop.
    """
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(SUPPORT_TOOLS))
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("execute_refund", execute_refund_node)

    # 2. Add Edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", check_after_agent, {"tools": "tools", END: END})

    # Tools node uses Command() to dynamically route to 'human_approval' or 'agent'
    workflow.add_node("router_tools", check_after_tools)
    workflow.add_edge("tools", "router_tools")

    # Human approval routes to execution
    workflow.add_edge("human_approval", "execute_refund")
    workflow.add_edge("execute_refund", END)

    # 3. Checkpointer (Mandatory for interrupt and state persistence)
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app
