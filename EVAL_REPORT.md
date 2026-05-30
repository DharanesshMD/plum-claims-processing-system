# Evaluation Report

**Pass Rate: 12/12 (100%)**

| Metric | Value |
|--------|-------|
| Total Tests | 12 |
| Passed | 12 |
| Failed | 0 |
| Pass Rate | 12/12 (100%) |

---

## ✅ TC001: Wrong Document Uploaded

| | Expected | Actual |
|---|---|---|
| Decision | (early stop) | (early stop) |
| Confidence | — | 100% |

**Explanation**: Missing required document(s) for Consultation claim: Hospital Bill. Please upload the required documents.

**Checks**:
- ✓ early_stop
- ✓ system_must: Stop before making any claim decision...
- ✓ system_must: Tell the member specifically what document type was uploaded...
- ✓ system_must: Not return a generic error — the message must name the uploa...

**Pipeline**: DocumentValidator(FAILED)

---

## ✅ TC002: Unreadable Document

| | Expected | Actual |
|---|---|---|
| Decision | (early stop) | (early stop) |
| Confidence | — | 100% |

**Explanation**: The uploaded pharmacy bill ('blurry_bill.jpg') is unreadable. The image appears to be blurry or too low quality to extract information from. Please re-upload a clearer photo or scan of your pharmacy bill.

**Checks**:
- ✓ early_stop
- ✓ system_must: Identify that the pharmacy bill cannot be read...
- ✓ system_must: Ask the member to re-upload that specific document...
- ✓ system_must: Not reject the claim outright...

**Pipeline**: DocumentValidator(FAILED)

---

## ✅ TC003: Documents Belong to Different Patients

| | Expected | Actual |
|---|---|---|
| Decision | (early stop) | (early stop) |
| Confidence | — | 70% |

**Explanation**: The uploaded documents appear to belong to different people. We found the following names: "Rajesh Kumar", "Arjun Mehta". All documents for a claim must belong to the same patient. Please verify and re-upload the correct documents.

**Checks**:
- ✓ early_stop
- ✓ system_must: Detect that the documents belong to different people...
- ✓ system_must: Surface this to the member with the specific names found on ...
- ✓ system_must: Not proceed to a claim decision...

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(FAILED)

---

## ✅ TC004: Clean Consultation — Full Approval

| | Expected | Actual |
|---|---|---|
| Decision | APPROVED | APPROVED |
| Amount | ₹1,350 | ₹1,350 |
| Confidence | — | 100% |

**Explanation**: Claim approved for ₹1,350. Calculation: Starting amount: ₹1,500 → Co-pay (10.0%): -₹150 → Final approved amount: ₹1,350

**Checks**:
- ✓ decision_type
- ✓ approved_amount
- ✓ confidence_score

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(SUCCESS) → DecisionMaker(SUCCESS)

---

## ✅ TC005: Waiting Period — Diabetes

| | Expected | Actual |
|---|---|---|
| Decision | REJECTED | REJECTED |
| Confidence | — | 95% |

**Explanation**: Claim rejected. Condition 'Type 2 Diabetes Mellitus' has a 90-day waiting period. Member joined on 2024-09-01 and is eligible for Diabetes-related claims from 2024-11-30.

**Checks**:
- ✓ decision_type
- ✓ system_must: State the date from which the member will be eligible for di...
- ✓ rejection_reason: WAITING_PERIOD

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(FAILED) → DecisionMaker(SUCCESS)

---

## ✅ TC006: Dental Partial Approval — Cosmetic Exclusion

| | Expected | Actual |
|---|---|---|
| Decision | PARTIAL | PARTIAL |
| Amount | ₹8,000 | ₹8,000 |
| Confidence | — | 100% |

**Explanation**: Partial approval: ₹8,000 of ₹12,000 approved. Excluded items: 'Teeth Whitening' (₹4,000). Calculation: Starting amount: ₹8,000 → Final approved amount: ₹8,000

**Checks**:
- ✓ decision_type
- ✓ approved_amount
- ✓ system_must: Itemize which line items were approved and which were reject...
- ✓ system_must: State the reason for each rejection at the line-item level...

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(SUCCESS) → DecisionMaker(SUCCESS)

---

## ✅ TC007: MRI Without Pre-Authorization

| | Expected | Actual |
|---|---|---|
| Decision | REJECTED | REJECTED |
| Confidence | — | 95% |

**Explanation**: Claim rejected. Condition 'Suspected Lumbar Disc Herniation' has a 365-day waiting period. Member joined on 2024-04-01 and is eligible for Hernia-related claims from 2025-04-01. Pre-authorization is required but was not obtained. MRI scan costing ₹15,000 requires pre-authorization as it exceeds the ₹10,000 threshold. Please obtain pre-authorization from the insurer and resubmit the claim.

**Checks**:
- ✓ decision_type
- ✓ system_must: Explain that pre-authorization was required and not obtained...
- ✓ system_must: Tell the member what they should do to resubmit with pre-aut...
- ✓ rejection_reason: PRE_AUTH_MISSING

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(FAILED) → DecisionMaker(SUCCESS)

---

## ✅ TC008: Per-Claim Limit Exceeded

| | Expected | Actual |
|---|---|---|
| Decision | REJECTED | REJECTED |
| Confidence | — | 95% |

**Explanation**: Claim rejected. Claimed amount ₹7,500 exceeds the per-claim limit of ₹5,000. The maximum claimable amount per visit is ₹5,000.

**Checks**:
- ✓ decision_type
- ✓ system_must: State the per-claim limit and the claimed amount clearly in ...
- ✓ rejection_reason: PER_CLAIM_EXCEEDED

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(FAILED) → DecisionMaker(SUCCESS)

---

## ✅ TC009: Fraud Signal — Multiple Same-Day Claims

| | Expected | Actual |
|---|---|---|
| Decision | MANUAL_REVIEW | MANUAL_REVIEW |
| Confidence | — | 70% |

**Explanation**: Claim routed to manual review due to the following signals: Multiple same-day claims detected: 4 claims on 2024-10-30 (limit: 2). An operations team member will review this claim.

**Checks**:
- ✓ decision_type
- ✓ system_must: Flag the unusual same-day claim pattern...
- ✓ system_must: Route to manual review rather than auto-rejecting...
- ✓ system_must: Include the specific signals that triggered the flag in the ...

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(SUCCESS) → DecisionMaker(SUCCESS)

---

## ✅ TC010: Network Hospital — Discount Applied

| | Expected | Actual |
|---|---|---|
| Decision | APPROVED | APPROVED |
| Amount | ₹3,240 | ₹3,240 |
| Confidence | — | 100% |

**Explanation**: Claim approved for ₹3,240. Calculation: Starting amount: ₹4,500 → Network discount (20.0%): -₹900 → Co-pay (10.0%): -₹360 → Final approved amount: ₹3,240

**Checks**:
- ✓ decision_type
- ✓ approved_amount
- ✓ system_must: Apply network discount before co-pay, not after...
- ✓ system_must: Show the breakdown of discount and co-pay in the decision ou...

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(SUCCESS) → DecisionMaker(SUCCESS)

---

## ✅ TC011: Component Failure — Graceful Degradation

| | Expected | Actual |
|---|---|---|
| Decision | APPROVED | APPROVED |
| Confidence | — | 60% |

**Explanation**: Claim approved for ₹4,000. Calculation: Starting amount: ₹4,000 → Final approved amount: ₹4,000

**Checks**:
- ✓ decision_type
- ✓ system_must: Not crash or return a 500 error...
- ✓ system_must: Indicate in the output that a component failed and was skipp...
- ✓ system_must: Return a confidence score lower than a normal full-pipeline ...
- ✓ system_must: Include a note that manual review is recommended due to inco...

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(FAILED) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(SUCCESS) → DecisionMaker(SUCCESS)

---

## ✅ TC012: Excluded Treatment

| | Expected | Actual |
|---|---|---|
| Decision | REJECTED | REJECTED |
| Confidence | — | 95% |

**Explanation**: Claim rejected. The diagnosis/treatment 'Morbid Obesity — BMI 37' falls under the policy exclusion: 'Obesity and weight loss programs'. This claim is not eligible for coverage. Claimed amount ₹8,000 exceeds the per-claim limit of ₹5,000. The maximum claimable amount per visit is ₹5,000.

**Checks**:
- ✓ decision_type
- ✓ confidence_score
- ✓ rejection_reason: EXCLUDED_CONDITION

**Pipeline**: DocumentValidator(SUCCESS) → DocumentParser(SUCCESS) → CrossDocVerifier(SUCCESS) → PolicyEvaluator(FAILED) → DecisionMaker(SUCCESS)

---

