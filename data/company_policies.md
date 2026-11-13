# Apex Electronics — Global Customer Support & Service Operations Manual
**Document ID:** SOP-POL-2026-V2.1  
**Classification:** Internal Support Operations & Public Policy Manual  
**Effective Date:** October 1, 2026  
**Last Reviewed:** October 2026  
**Applicability:** All Consumer Electronics E-Commerce Orders & Support Channels  

---

## 1. Executive Summary & Purpose
This policy document governs customer service operations, return merchandise authorizations (RMA), refund eligibility adjudication, and customer resolution workflows for **Apex Electronics**.

The guidelines contained herein serve as the authoritative standard for human support specialists, tier-2 escalations, and automated decision-support agents. All financial remedies (refunds, credits, or fee waivers) must strictly comply with the stipulations, verification gates, and authorization thresholds detailed in this manual.

---

## 2. Standard Return Policy & Window

### 2.1 Standard 14-Day Return Window
* **Window Duration:** Customers may initiate a return request within **fourteen (14) calendar days** starting from the recorded carrier delivery date.
* **Eligible Categories:** Laptops, desktop accessories, computer peripherals (monitors, keyboards, mice, USB-C hubs), smart home devices, and wearable fitness trackers.
* **Condition of Return:**
  1. The item must be in its original manufacturer packaging with all serial numbers, warranty cards, manuals, cables, and power adapters intact.
  2. Products returned due to "buyer’s remorse" or "changed mind" must show no signs of physical wear, liquid ingress, cosmetic scratches, or unauthorized disassembly.
  3. Factory seals broken on specific hygienic or security-sensitive devices are subject to section 2.3.

### 2.2 Proof of Purchase Requirement
To qualify for a Return Merchandise Authorization (RMA):
* The customer must provide a valid **Order ID** (e.g., `ORD1001`) originating from an authenticated customer account.
* Guest checkout orders must be validated using the customer's verified billing email address and transaction payment reference (`payment_id`).

### 2.3 Final Sale & Non-Returnable Items
The following merchandise is strictly non-returnable and non-refundable unless verified as Dead on Arrival (DOA) under Section 4:
1. **Hygiene-Sensitive Audio Products:** In-ear monitors and silicone-tip earbuds once the manufacturer hygiene seal is broken or tampered with.
2. **Digital Consumables & Software Licenses:** Activated downloadable software keys, gift cards, and prepaid service subscriptions.
3. **Customized / Personalized Hardware:** Engraved devices, customized chassis modifications, and custom cable assemblies.
4. **Clearance / As-Is Items:** Products explicitly marked as `FINAL SALE` or `REFURBISHED GRADE-C` on the storefront checkout receipt.

---

## 3. Return Receipt, Processing, and Quality Inspection (QA)

### 3.1 Return Lifecycle & Status Transitions
Every customer return follows a mandatory four-stage lifecycle:
1. `REQUESTED`: The customer submits a return request. A prepaid shipping label or pickup schedule is issued. No refund may be issued at this stage.
2. `IN_TRANSIT`: The carrier has scanned the package into the logistics network.
3. `RECEIVED`: The return package has physically arrived at the Apex Electronics Central Fulfillment Facility.
4. `INSPECTED`: The QA engineering team evaluates the hardware against the reported return reason.

### 3.2 Mandatory Inspection Verification
**No refund shall be disbursed or processed prior to formal receipt and QA inspection.**
* **Passed Inspection:** The returned merchandise matches the serial number on file, contains all accessories, and matches the reported condition (Unopened or Lightly Used without damage). The return status updates to `PASSED_INSPECTION`.
* **Defect Confirmed:** For products returned as defective, QA testing reproduces hardware malfunction under standard operating conditions. The return status updates to `DEFECT_CONFIRMED`.
* **Inspection Failed / Rejected:** The returned item shows customer-induced physical trauma, water damage, mismatched serial numbers, missing internal components, or is outside the valid return window. The return is marked `REJECTED`, and the product is returned to the customer at their expense.

---

## 4. Defective Products & Damaged on Arrival (DOA)

### 4.1 Reporting Window for Damaged Goods
* Customers must report transit damage or cosmetic defects within **forty-eight (48) hours** of carrier delivery.
* Clear photographic evidence showing the exterior shipping container, shipping label, and damaged merchandise must be uploaded to the support ticket.
* Damaged items reported within the 48-hour window are exempt from the standard restocking surcharge and are eligible for immediate expedited pickup.

### 4.2 Manufacturer Warranty & Latent Defects
* Hardware failure occurring after the 14-day return window but within the first twelve (12) months is governed under the **Apex Limited Hardware Warranty**.
* Support agents shall direct warranty claims to authorized service centers or initiate a warranty repair ticket rather than an immediate retail refund.

---

## 5. Refund Operations, Payment Channels, & Timelines

### 5.1 Refund Eligibility Criteria
A refund transaction is authorized if and only if all the following conditions are met:
1. Order status is confirmed as `Delivered` in historical records.
2. The associated return is in status `RECEIVED` with an inspection outcome of `Passed inspection` or `Defect confirmed`.
3. Total cumulative refunds on the order do not exceed the original transaction value (`order_total`).
4. The refund request was submitted within the 14-day policy window, or possesses a valid supervisor-approved warranty override.

### 5.2 Disbursement Method & Processing Windows
* **Original Payment Reversal:** Refunds are credited exclusively to the original payment instrument (Credit Card, Debit Card, Net Banking, or UPI). Under anti-money-laundering (AML) regulations, refunds cannot be redirected to third-party bank accounts or alternate payment methods.
* **Banking Settlement Times:**
  * Credit/Debit Cards: 3 to 5 business days following payment gateway confirmation.
  * UPI & Digital Wallets: 24 to 48 hours following payment gateway confirmation.
* **Store Credit Option:** Customers may opt for immediate Store Credit (Apex Wallet Balance) with an added 5% incentive bonus. Store credit refunds are non-reversible.

### 5.3 Communication Protocol on Refund Status
Support representatives and automated agents must accurately convey the exact state of the refund:
* **`ON_HOLD` / `PENDING_RETURN`:** *"We are awaiting the arrival and inspection of your return package at our fulfillment center before issuing a refund."*
* **`PENDING_APPROVAL`:** *"Your refund is currently undergoing routine review with our operations supervisor and will be finalized within 24 business hours."*
* **`PROCESSING`:** *"The refund has been submitted to your payment provider. Final settlement depends on your bank's posting cycle (typically 3–5 business days)."*
* **`COMPLETED`:** *"Your payment provider has officially confirmed completion under transaction ID [Transaction ID]."*

**Strict Prohibition:** Agents must never state that a refund is "completed" or "money is in your account" while the transaction status is `PROCESSING`, `ON_HOLD`, or `PENDING_APPROVAL`.

---

## 6. Financial Controls & Human Approval Matrix

### 6.1 Purpose of Segregation of Duties
To protect against payment fraud, unauthorized treasury leakage, and agent hallucination, all financial execution requires a separation between **Proposal Creation** and **Execution Authorization**.

### 6.2 Approval Authorization Thresholds

| Action / Threshold | Automated Agent Role | Human Reviewer Role | Required Approval Level |
| :--- | :--- | :--- | :--- |
| **Order Status & Tracking Inquiry** | Fully Automated Resolution | None required | Level 0 (System) |
| **Return Label Generation (Within 14d)** | Autonomous Generation | None required | Level 0 (System) |
| **Refund $\le$ ₹1,500 (Passed Inspection)** | Prepare Proposal & Validate | Senior Reviewer (One-Click) | Level 1 Support Lead |
| **Refund $>$ ₹1,500 (Any Reason)** | Prepare Proposal & Audit Check | Mandatory Human Approval | Level 2 Support Supervisor |
| **Transit Damage Claims (DOA)** | Gather Evidence & Propose | Mandatory Evidence Review | Level 2 Support Supervisor |
| **Out-of-Policy Exceptions ($>$ 14 Days)** | Flag Ineligibility & Escalation | Discretionary Review | Operations Manager |

### 6.3 Technical Idempotency Mandate
* Every refund operation initiated with payment gateways must attach a cryptographically unique `idempotency_key` constructed as `REFUND-{order_id}-{proposal_id}`.
* In the event of network timeouts, provider socket drops, or client reconnections, the identical idempotency key must be queried before any secondary execution attempt is made. Duplicate debits or dual refunds will trigger an immediate compliance audit.

---

## 7. Order Modification, Cancellations, & Logistics Delays

### 7.1 Order Cancellation Window
* **Pre-Fulfillment:** Orders in `Pending`, `Order Placed`, or `Processing` status prior to warehouse staging may be cancelled immediately with a 100% full instant refund.
* **Post-Dispatch:** Once an order is marked `Shipped` or `In Transit` with a carrier tracking AWB number, cancellation is not possible. The customer must receive the parcel and initiate a standard return.

### 7.2 Shipping Address Corrections
* Address updates are permitted only while the order status is `Unfulfilled`.
* Once an AWB is assigned, address modifications can only be rerouted by the logistics partner if requested through customer support, with an estimated 24–48 hour delivery delay.

### 7.3 Logistics Delay & Lost Shipment SLA
* **Standard Delivery SLA:** 3 to 5 business days from shipment.
* **Express Delivery SLA:** 1 to 2 business days from shipment.
* **Lost Parcel Investigation Threshold:** If tracking displays no carrier scan activity for seven (7) consecutive calendar days, the order is declared `Lost in Transit` by Logistics. The customer may elect either an immediate free priority replacement or a 100% full refund without requiring physical return receipt.

---

## 8. Escalation & Customer Safety Protocols

### 8.1 Mandatory Human Escalation Triggers
An automated resolution workflow or first-contact support specialist must immediately escalate a ticket to Tier-2 Human Management under the following conditions:
1. **Adversarial or Fraudulent Patterns:** Multiple return claims submitted for the same serial number across disparate accounts.
2. **High-Value Item Discrepancy:** High-value hardware (> ₹10,000) where returned package weights deviate by more than 15% from the shipped parcel weight.
3. **Repeated Negative Sentiment:** Customer expresses extreme dissatisfaction, legal action intent, or formal regulatory consumer dispute notices.
4. **Policy Ambiguity:** Customer situation is not explicitly addressed in sections 2 through 7 of this manual.

### 8.2 Ticket Audit Trail Requirements
All resolution actions—including policy retrieved, citations referenced, evidence inspected, supervisor notes, and provider transaction hashes—must be permanently recorded in the system audit log (`audit_events`) with UTC timestamps.
