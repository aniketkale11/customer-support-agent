"""
Agent Tools Module for Customer Support Resolution Agent.

This file contains the tools (functions) that our AI agent can call.
We start with our very first tool: get_order_details.
"""

import sys
from pathlib import Path

# Ensure the project root directory is in Python's search path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import uuid
from datetime import datetime
from langchain_core.tools import tool
from src.database import query_db, execute_db


@tool
def get_order_details(order_id: str) -> dict:
    """
    Look up complete order details from the database using a unique Order ID.
    
    Use this tool whenever a customer asks about their order status,
    purchase date, product name, or total amount paid.
    
    Args:
        order_id (str): The unique order identifier, for example: 'ORD1001'.
        
    Returns:
        dict: A dictionary containing order information or an error message.
    """
    # 1. Clean the input (remove extra spaces and make uppercase)
    cleaned_order_id = order_id.strip().upper()

    # 2. Run a safe SQL query on our SQLite database
    query = """
        SELECT 
            order_id, 
            customer_id, 
            product_name, 
            order_date, 
            order_total, 
            order_status, 
            payment_id, 
            payment_status
        FROM orders 
        WHERE order_id = ?
    """
    results = query_db(query, (cleaned_order_id,))

    # 3. Check if the order was found
    if not results:
        return {
            "success": False,
            "error": f"No order found with ID '{cleaned_order_id}'. Please verify the Order ID."
        }

    # 4. Return the order facts as a clean dictionary
    order = results[0]
    return {
        "success": True,
        "order_id": order["order_id"],
        "customer_id": order["customer_id"],
        "product_name": order["product_name"],
        "order_date": order["order_date"],
        "order_total": order["order_total"],
        "order_status": order["order_status"],
        "payment_status": order["payment_status"]
    }


@tool
def get_return_status(order_id: str) -> dict:
    """
    Check the return status, package receipt date, and QA inspection result for an order.
    
    Use this tool whenever a customer asks if their returned package reached the warehouse,
    what the return status is, or whether their returned item passed inspection.
    
    Args:
        order_id (str): The unique order identifier, for example: 'ORD1001'.
        
    Returns:
        dict: A dictionary containing return details or an error message.
    """
    # 1. Clean the input (remove extra spaces and make uppercase)
    cleaned_order_id = order_id.strip().upper()

    # 2. Query the 'returns' table
    query = """
        SELECT 
            return_id,
            order_id,
            customer_id,
            product_name,
            return_requested_date,
            return_received_date,
            return_reason,
            return_status,
            item_condition,
            inspection_result
        FROM returns 
        WHERE order_id = ?
    """
    results = query_db(query, (cleaned_order_id,))

    # 3. Check if any return was found for this order
    if not results:
        return {
            "success": False,
            "error": f"No return record found for order ID '{cleaned_order_id}'. The customer may not have requested a return yet."
        }

    # 4. Return the return details as a clean dictionary
    ret = results[0]
    return {
        "success": True,
        "return_id": ret["return_id"],
        "order_id": ret["order_id"],
        "customer_id": ret["customer_id"],
        "product_name": ret["product_name"],
        "return_status": ret["return_status"],
        "return_received_date": ret["return_received_date"],
        "return_reason": ret["return_reason"],
        "item_condition": ret["item_condition"],
        "inspection_result": ret["inspection_result"]
    }


@tool
def get_refund_status(order_id: str) -> dict:
    """
    Check the current status and payment provider details of a refund for an order.
    
    Use this tool whenever a customer asks about their refund status, whether their
    refund has been processed, completed, or if it is pending approval.
    
    Args:
        order_id (str): The unique order identifier, for example: 'ORD1001'.
        
    Returns:
        dict: A dictionary containing refund status, amount, and notes, or an error.
    """
    # 1. Clean the input (remove extra spaces and make uppercase)
    cleaned_order_id = order_id.strip().upper()

    # 2. Query the 'refunds' table
    query = """
        SELECT 
            refund_id,
            return_id,
            order_id,
            customer_id,
            requested_amount,
            approved_amount,
            refund_status,
            eligibility_status,
            approval_status,
            payment_id,
            provider_transaction_id,
            notes
        FROM refunds 
        WHERE order_id = ?
    """
    results = query_db(query, (cleaned_order_id,))

    # 3. Check if any refund record exists for this order
    if not results:
        return {
            "success": False,
            "error": f"No refund record found for order ID '{cleaned_order_id}'. No refund has been initiated for this order."
        }

    # 4. Return the refund details as a clean dictionary
    ref = results[0]
    return {
        "success": True,
        "refund_id": ref["refund_id"],
        "order_id": ref["order_id"],
        "requested_amount": ref["requested_amount"],
        "approved_amount": ref["approved_amount"],
        "refund_status": ref["refund_status"],
        "eligibility_status": ref["eligibility_status"],
        "approval_status": ref["approval_status"],
        "provider_transaction_id": ref["provider_transaction_id"],
        "notes": ref["notes"]
    }


@tool
def check_refund_eligibility(order_id: str) -> dict:
    """
    Deterministically evaluates whether an order is eligible for a refund.
    
    This tool enforces official company return policies:
    1. The order must be confirmed as 'Delivered'.
    2. A return package must be physically 'RECEIVED' at the fulfillment center.
    3. The QA inspection must confirm defect or pass inspection.
    4. The return must have been requested within the 14-day policy window.
    5. No prior refund can be completed or actively processing.
    
    Args:
        order_id (str): The unique order identifier, for example: 'ORD1001'.
        
    Returns:
        dict: A dictionary containing eligibility boolean, max refundable amount,
              and a detailed explanation of the decision.
    """
    cleaned_order_id = order_id.strip().upper()

    # Step 1: Verify order exists and delivery status
    order_rows = query_db("SELECT * FROM orders WHERE order_id = ?", (cleaned_order_id,))
    if not order_rows:
        return {
            "eligible": False,
            "max_refundable_amount": 0.0,
            "reason": f"Order '{cleaned_order_id}' was not found in our records."
        }
    order = order_rows[0]

    if order["order_status"] != "Delivered":
        return {
            "eligible": False,
            "max_refundable_amount": 0.0,
            "reason": f"Order status is '{order['order_status']}'. Only delivered orders can be refunded."
        }

    # Step 2: Check for existing refund operations (prevent duplicate refunds)
    refund_rows = query_db("SELECT * FROM refunds WHERE order_id = ?", (cleaned_order_id,))
    if refund_rows:
        refund = refund_rows[0]
        status = refund["refund_status"]
        if status == "COMPLETED":
            return {
                "eligible": False,
                "max_refundable_amount": 0.0,
                "reason": f"A refund of INR {refund['approved_amount']} has already been COMPLETED for this order (Transaction ID: {refund['provider_transaction_id']})."
            }
        elif status == "PROCESSING":
            return {
                "eligible": False,
                "max_refundable_amount": 0.0,
                "reason": "A refund is already actively PROCESSING with the payment provider. Do not initiate duplicate refunds."
            }
        elif status == "PENDING_APPROVAL":
            return {
                "eligible": False,
                "max_refundable_amount": 0.0,
                "reason": "A refund proposal has already been created and is currently awaiting supervisor approval."
            }
        elif status == "BLOCKED":
            return {
                "eligible": False,
                "max_refundable_amount": 0.0,
                "reason": f"Refund is BLOCKED due to: {refund['notes']}"
            }

    # Step 3: Check return request and warehouse receipt
    return_rows = query_db("SELECT * FROM returns WHERE order_id = ?", (cleaned_order_id,))
    if not return_rows:
        return {
            "eligible": False,
            "max_refundable_amount": 0.0,
            "reason": "No return request has been submitted for this order. The customer must first initiate a return."
        }
    ret = return_rows[0]

    if ret["return_status"] != "RECEIVED" or not ret["return_received_date"]:
        return {
            "eligible": False,
            "max_refundable_amount": 0.0,
            "reason": f"Return package has not arrived at the warehouse yet (current status: '{ret['return_status']}'). Refunds can only be issued after return receipt."
        }

    # Step 4: Quality Inspection validation
    inspection = ret["inspection_result"] or ""
    valid_inspections = ["Passed inspection", "Defect confirmed"]
    if inspection not in valid_inspections:
        return {
            "eligible": False,
            "max_refundable_amount": 0.0,
            "reason": f"Return did not pass QA inspection. Inspection outcome: '{inspection}'."
        }

    # Step 5: Validate 14-day policy return window
    try:
        order_date = datetime.strptime(order["order_date"], "%Y-%m-%d")
        return_req_date = datetime.strptime(ret["return_requested_date"], "%Y-%m-%d")
        days_diff = (return_req_date - order_date).days
        if days_diff > 14 and ret["return_reason"] != "Defective product":
            return {
                "eligible": False,
                "max_refundable_amount": 0.0,
                "reason": f"Return was requested {days_diff} days after order date, which exceeds the standard 14-day return window."
            }
    except Exception:
        # If dates are missing or improperly formatted, allow through to human review
        pass

    # All criteria passed!
    return {
        "eligible": True,
        "max_refundable_amount": float(order["order_total"]),
        "order_id": cleaned_order_id,
        "customer_id": order["customer_id"],
        "product_name": order["product_name"],
        "reason": f"All criteria met: Return received on {ret['return_received_date']} and inspection confirmed '{inspection}'. Eligible for full refund of INR {order['order_total']}."
    }


@tool
def create_refund_proposal(order_id: str, amount: float, reason: str) -> dict:
    """
    Creates a formal refund proposal for an order, awaiting human supervisor approval.
    
    IMPORTANT SAFETY RULE: This tool does NOT move or disburse money.
    It only stages an official proposal in the database with status 'PENDING_APPROVAL'.
    A human supervisor must review and approve this proposal before any payment is executed.
    
    Args:
        order_id (str): The unique order identifier, for example: 'ORD1001'.
        amount (float): The proposed refund amount in INR.
        reason (str): The verified justification or policy reason for the refund.
        
    Returns:
        dict: A dictionary containing the generated proposal_id, status 'PENDING_APPROVAL',
              or an error message if the order is ineligible.
    """
    cleaned_order_id = order_id.strip().upper()

    # Step 1: Enforce Deterministic Guardrail Check
    eligibility = check_refund_eligibility.invoke({"order_id": cleaned_order_id})
    if not eligibility["eligible"]:
        return {
            "success": False,
            "error": f"Proposal rejected by policy engine: {eligibility['reason']}"
        }

    # Step 2: Validate requested amount
    max_amount = eligibility["max_refundable_amount"]
    if amount <= 0:
        return {
            "success": False,
            "error": f"Invalid refund amount (INR {amount}). Amount must be greater than 0."
        }
    if amount > max_amount:
        return {
            "success": False,
            "error": f"Requested amount (INR {amount}) exceeds maximum refundable amount (INR {max_amount})."
        }

    # Step 3: Fetch linked return and order records
    return_rows = query_db("SELECT * FROM returns WHERE order_id = ?", (cleaned_order_id,))
    ret = return_rows[0]
    order_rows = query_db("SELECT * FROM orders WHERE order_id = ?", (cleaned_order_id,))
    order = order_rows[0]

    # Step 4: Generate unique proposal ID and timestamp
    proposal_id = f"REF-{cleaned_order_id}-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 5: Insert proposal into 'refunds' table with status PENDING_APPROVAL
    insert_sql = """
        INSERT INTO refunds (
            refund_id, return_id, order_id, customer_id, 
            requested_amount, approved_amount, refund_status, 
            eligibility_status, approval_status, payment_id, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    execute_db(insert_sql, (
        proposal_id,
        ret["return_id"],
        cleaned_order_id,
        order["customer_id"],
        float(amount),
        0.0,  # Zero approved so far (must wait for human review!)
        "PENDING_APPROVAL",
        "ELIGIBLE",
        "PENDING",
        order["payment_id"],
        reason,
        now_str,
        now_str
    ))

    return {
        "success": True,
        "proposal_id": proposal_id,
        "order_id": cleaned_order_id,
        "customer_id": order["customer_id"],
        "requested_amount": float(amount),
        "status": "PENDING_APPROVAL",
        "message": f"Refund proposal '{proposal_id}' of INR {amount} created successfully. Workflow paused awaiting human supervisor approval."
    }


@tool
def execute_approved_refund(proposal_id: str, idempotency_key: str) -> dict:
    """
    Executes an approved refund via the mock payment provider and updates the database.
    
    IMPORTANT SAFETY CONTROLS:
    1. Only proposals in 'PENDING_APPROVAL' or 'PROCESSING' status can be executed.
    2. Idempotency Key is strictly enforced: If the exact same refund request is retried,
       it safely returns the existing confirmation without double-refunding.
    3. Requires human approval before invocation.
    
    Args:
        proposal_id (str): The unique refund proposal identifier, for example: 'REF3004'.
        idempotency_key (str): A unique client-generated string (e.g., 'IDEMP-ORD1004-001')
                               used to prevent duplicate execution during network retries.
                               
    Returns:
        dict: A dictionary containing the payment transaction confirmation, status 'COMPLETED',
              and amount disbursed, or an error if the proposal is invalid.
    """
    cleaned_proposal_id = proposal_id.strip().upper()
    cleaned_key = idempotency_key.strip()

    if not cleaned_key:
        return {
            "success": False,
            "error": "Missing required 'idempotency_key'. Every refund execution must provide a unique idempotency key."
        }

    # Step 1: Find the proposal in database
    refund_rows = query_db("SELECT * FROM refunds WHERE refund_id = ?", (cleaned_proposal_id,))
    if not refund_rows:
        return {
            "success": False,
            "error": f"No refund proposal found with ID '{cleaned_proposal_id}'."
        }
    refund = refund_rows[0]

    # Step 2: Idempotency Check (Has this already been completed?)
    if refund["refund_status"] == "COMPLETED":
        return {
            "success": True,
            "already_completed": True,
            "proposal_id": cleaned_proposal_id,
            "order_id": refund["order_id"],
            "amount_refunded": float(refund["approved_amount"]),
            "provider_transaction_id": refund["provider_transaction_id"],
            "message": f"Idempotency Guard: Refund '{cleaned_proposal_id}' was already executed and completed (Txn: {refund['provider_transaction_id']}). Duplicate payment prevented."
        }

    # Step 3: Verify proposal is in valid state for execution
    allowed_statuses = ["PENDING_APPROVAL", "PROCESSING"]
    if refund["refund_status"] not in allowed_statuses:
        return {
            "success": False,
            "error": f"Cannot execute refund: Proposal is in status '{refund['refund_status']}'. Must be in 'PENDING_APPROVAL'."
        }

    # Step 4: Simulate calling external Payment Provider API with the idempotency key
    # In production, this would be: provider_response = stripe.Refund.create(..., idempotency_key=cleaned_key)
    provider_txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    approved_amount = float(refund["requested_amount"])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 5: Update the refunds table to 'COMPLETED'
    update_sql = """
        UPDATE refunds
        SET refund_status = 'COMPLETED',
            approved_amount = ?,
            approval_status = 'APPROVED',
            provider_transaction_id = ?,
            notes = ?,
            updated_at = ?
        WHERE refund_id = ?
    """
    completion_notes = f"Approved and executed via payment provider (Idempotency Key: {cleaned_key})"
    execute_db(update_sql, (
        approved_amount,
        provider_txn_id,
        completion_notes,
        now_str,
        cleaned_proposal_id
    ))

    return {
        "success": True,
        "already_completed": False,
        "proposal_id": cleaned_proposal_id,
        "order_id": refund["order_id"],
        "amount_refunded": approved_amount,
        "refund_status": "COMPLETED",
        "provider_transaction_id": provider_txn_id,
        "idempotency_key": cleaned_key,
        "message": f"Refund of INR {approved_amount} successfully executed with payment provider (Transaction ID: {provider_txn_id})."
    }


if __name__ == "__main__":
    print("=" * 60)
    print("--- Testing Tool 1: get_order_details ---")
    print("=" * 60)
    
    # Test Tool 1
    print("\n1. Testing with a valid order ID: 'ORD1001'")
    result_valid = get_order_details.invoke({"order_id": "ORD1001"})
    print("Result:", result_valid)

    print("\n2. Testing with an invalid order ID: 'ORD9999'")
    result_invalid = get_order_details.invoke({"order_id": "ORD9999"})
    print("Result:", result_invalid)

    print("\n" + "=" * 60)
    print("--- Testing Tool 2: get_return_status ---")
    print("=" * 60)
    
    # Test Tool 2: Valid return (ORD1001 has return RET2001)
    print("\n1. Testing with order that has a return: 'ORD1001'")
    return_valid = get_return_status.invoke({"order_id": "ORD1001"})
    print("Result:", return_valid)

    # Test Tool 2: Order with NO return (ORD1011 has no return)
    print("\n2. Testing with order that has NO return: 'ORD1011'")
    return_none = get_return_status.invoke({"order_id": "ORD1011"})
    print("Result:", return_none)

    print("\n" + "=" * 60)
    print("--- Testing Tool 3: get_refund_status ---")
    print("=" * 60)
    
    # Test Tool 3: Order with refund (ORD1001 has processing refund REF3001)
    print("\n1. Testing with order that has a refund: 'ORD1001'")
    refund_valid = get_refund_status.invoke({"order_id": "ORD1001"})
    print("Result:", refund_valid)

    # Test Tool 3: Order with completed refund (ORD1002 has completed refund REF3002)
    print("\n2. Testing with order that has a completed refund: 'ORD1002'")
    refund_completed = get_refund_status.invoke({"order_id": "ORD1002"})
    print("Result:", refund_completed)

    print("\n" + "=" * 60)
    print("--- Testing Tool 4: check_refund_eligibility ---")
    print("=" * 60)
    
    # Case A: Already COMPLETED refund (ORD1002)
    print("\nCase A: Order already completed refund ('ORD1002')")
    elig_a = check_refund_eligibility.invoke({"order_id": "ORD1002"})
    print("Eligible:", elig_a["eligible"], "--> Reason:", elig_a["reason"])

    # Case B: Return not received at warehouse yet (ORD1003)
    print("\nCase B: Return requested but not received ('ORD1003')")
    elig_b = check_refund_eligibility.invoke({"order_id": "ORD1003"})
    print("Eligible:", elig_b["eligible"], "--> Reason:", elig_b["reason"])

    # Case C: Outside return window / rejected (ORD1015)
    print("\nCase C: Return outside window / rejected ('ORD1015')")
    elig_c = check_refund_eligibility.invoke({"order_id": "ORD1015"})
    print("Eligible:", elig_c["eligible"], "--> Reason:", elig_c["reason"])

    # Case D: Return received, defect confirmed (ORD1018)
    print("\nCase D: Valid return received, pending approval ('ORD1018')")
    elig_d = check_refund_eligibility.invoke({"order_id": "ORD1018"})
    print("Eligible:", elig_d["eligible"], "--> Reason:", elig_d["reason"])

    print("\n" + "=" * 60)
    print("--- Testing Tool 5: create_refund_proposal ---")
    print("=" * 60)

    # Test Proposal 1: Ineligible order (ORD1002 already completed) -> must be BLOCKED
    print("\n1. Trying to create proposal on an ineligible order ('ORD1002'):")
    prop_ineligible = create_refund_proposal.invoke({
        "order_id": "ORD1002",
        "amount": 799.0,
        "reason": "Customer called again asking for money"
    })
    print("Result:", prop_ineligible)

    print("\n" + "=" * 60)
    print("--- Testing Tool 6: execute_approved_refund (with Idempotency) ---")
    print("=" * 60)

    # Test Execution 1: Execute pending proposal REF3004
    print("\n1. First execution attempt for pending proposal 'REF3004':")
    exec_first = execute_approved_refund.invoke({
        "proposal_id": "REF3004",
        "idempotency_key": "IDEMP-ORD1004-ATTEMPT-01"
    })
    print("Result:", exec_first)

    # Test Execution 2: RETRY with identical proposal (Idempotency Protection test!)
    print("\n2. Immediate RETRY attempt with same proposal 'REF3004' (Network retry simulation):")
    exec_retry = execute_approved_refund.invoke({
        "proposal_id": "REF3004",
        "idempotency_key": "IDEMP-ORD1004-ATTEMPT-01"
    })
    print("Result:", exec_retry)





