# Component Contracts

This document defines the input/output contracts for every component in the claims processing pipeline.

---

## 1. Document Validator (Agent 1)

**Purpose**: Catch document problems before any processing begins.

### Input
```python
ClaimInput:
    member_id: str
    claim_category: ClaimCategory  # CONSULTATION, DENTAL, etc.
    documents: list[DocumentInput]
        file_id: str
        actual_type: str           # "PRESCRIPTION", "HOSPITAL_BILL", etc.
        quality: str | None        # "GOOD", "UNREADABLE"
```

### Output
```python
DocumentValidationResult:
    is_valid: bool
    issues: list[DocumentIssue]
        issue_type: "WRONG_DOCUMENT_TYPE" | "MISSING_REQUIRED_DOCUMENT" | "UNREADABLE_DOCUMENT"
        severity: "ERROR" | "WARNING"
        message: str               # User-facing, specific
    error_message: str | None      # The primary error for the user
```

### Pipeline Behavior
- **is_valid=True**: Continue to Agent 2
- **is_valid=False**: Stop pipeline, return error immediately (no decision made)

### Error Messages (by test case)
- **TC001** (wrong type): *"Missing required document(s) for Consultation claim: Hospital Bill"*
- **TC002** (unreadable): *"The uploaded hospital bill is unreadable. Please re-upload a clearer photo."*

---

## 2. Document Parser (Agent 2)

**Purpose**: Extract structured data from documents (prescriptions, bills).

### Input
```python
ClaimInput.documents: list[DocumentInput]
    content: dict | None           # Structured content (test cases)
    patient_name_on_doc: str|None  # Name visible on document
```

### Output
```python
list[ExtractedDocument]:
    file_id: str
    document_type: str
    patient_name: str | None
    doctor_name: str | None
    diagnosis: str | None
    treatment: str | None
    document_date: date | None
    medicines: list[str]
    tests_ordered: list[str]
    line_items: list[ExtractedLineItem]
        description: str
        amount: float
    total_amount: float | None
    confidence: float              # 1.0 for structured, 0.5 for minimal
```

### Behavior
- **With `content` dict**: Parses directly (test case path), confidence=1.0
- **Without `content`**: Creates minimal extraction from metadata, confidence=0.5
- **On failure**: Graceful degradation (pipeline continues with reduced confidence)

---

## 3. Cross-Document Verifier (Agent 3)

**Purpose**: Detect inconsistencies across documents.

### Input
```python
ClaimInput.documents[].patient_name_on_doc: str | None
list[ExtractedDocument]  # From Agent 2
```

### Output
```python
CrossVerificationResult:
    is_consistent: bool
    mismatches: list[CrossDocMismatch]
        mismatch_type: "PATIENT_NAME" | "DATE" | "AMOUNT" | "PROVIDER"
        description: str
        values_found: dict[str, str]  # file_id -> value
    error_message: str | None
```

### Pipeline Behavior
- **is_consistent=True**: Continue to Agent 4
- **is_consistent=False**: Stop pipeline, return error (no decision made)

### Matching Algorithm
- Uses `thefuzz.fuzz.ratio()` with threshold 80 for name matching
- Handles minor variations: "Rajesh Kumar" ≈ "Rajesh Kumar" (pass)
- Catches different patients: "Rajesh Kumar" ≠ "Priya Singh" (fail)

---

## 4. Policy Evaluator (Agent 4)

**Purpose**: Apply all policy rules deterministically. This is the most critical agent.

### Input
```python
ClaimInput:
    member_id: str
    claim_category: ClaimCategory
    treatment_date: date
    claimed_amount: float
    hospital_name: str | None
    ytd_claims_amount: float
    claims_history: list[ClaimHistoryEntry]

list[ExtractedDocument]  # From Agent 2
```

### Output
```python
PolicyEvaluationResult:
    is_eligible: bool
    hard_rejections: list[str]     # e.g. ["WAITING_PERIOD", "EXCLUDED_CONDITION"]
    warnings: list[str]
    fraud_signals: list[str]
    excluded_line_items: list[dict] # {description, amount, reason}
    covered_line_items: list[dict]  # {description, amount}
    eligible_amount: float         # After exclusions, before discounts
    requires_manual_review: bool
    checks: list[CheckResult]      # Full audit trail
```

### Checks Performed (12 total)
1. **member_eligibility** — Member exists in policy roster
2. **initial_waiting_period** — Treatment date > join_date + 30 days
3. **condition_waiting_period** — Condition-specific waits (diabetes=90d)
4. **exclusion_check** — Global exclusions (cosmetic, self-inflicted)
5. **category_coverage** — Category is covered under policy
6. **line_item_analysis** — Per-item coverage (e.g., teeth whitening excluded)
7. **per_claim_limit** — Claimed amount ≤ ₹5,000 (for categories without higher sub-limit)
8. **sub_limit** — Category sub-limit check (informational)
9. **annual_limit** — YTD + current ≤ annual OPD limit
10. **pre_authorization** — Required for high-value diagnostics (MRI, CT)
11. **fraud_detection** — Same-day claims, monthly limits, high-value thresholds
12. **network_hospital** — Network hospital discount detection

### Rejection Codes
| Code | Meaning | Example |
|------|---------|---------|
| `MEMBER_NOT_FOUND` | Member not in policy roster | Invalid member_id |
| `INITIAL_WAITING_PERIOD` | Within 30-day wait | Treatment before join_date+30d |
| `WAITING_PERIOD` | Condition-specific wait | Diabetes within 90 days |
| `EXCLUDED_CONDITION` | Global exclusion | Cosmetic procedures |
| `CATEGORY_NOT_COVERED` | Category not in policy | — |
| `PER_CLAIM_EXCEEDED` | Amount > per-claim limit | ₹7,500 > ₹5,000 |
| `ANNUAL_LIMIT_EXHAUSTED` | YTD ≥ annual limit | — |
| `PRE_AUTH_MISSING` | Pre-auth required but missing | MRI without pre-auth |

---

## 5. Decision Maker (Agent 5)

**Purpose**: Calculate final approved amount and produce the decision.

### Input
```python
ClaimInput                    # Original claim
PolicyEvaluationResult        # From Agent 4
list[ExtractedDocument]       # From Agent 2
pipeline_confidence: float    # From orchestrator
component_failed: bool        # True if any agent failed
```

### Output
```python
ClaimDecision:
    claim_id: str
    decision: "APPROVED" | "PARTIAL" | "REJECTED" | "MANUAL_REVIEW" | None
    approved_amount: float | None
    rejection_reasons: list[str]
    confidence_score: float
    explanation: str              # Human-readable summary
    line_item_decisions: list[LineItemDecision]
    amount_breakdown: AmountBreakdown
        claimed_amount: float
        network_discount_percent: float
        network_discount_amount: float
        copay_percent: float
        copay_amount: float
        approved_amount: float
        calculation_steps: list[str]
    trace: FullTrace
    warnings: list[str]
```

### Decision Logic
```
if hard_rejections → REJECTED
elif fraud_signals → MANUAL_REVIEW
elif excluded_items exist → PARTIAL (only covered items approved)
elif component_failed → MANUAL_REVIEW
else → APPROVED
```

### Amount Calculation
```
1. Start with eligible_amount (from line items or full claim)
2. Apply network discount (if network hospital)
3. Apply co-pay deduction
4. Cap at remaining annual limit
5. Round to 2 decimal places
```

---

## Orchestrator (LangGraph)

**Purpose**: Wire all 5 agents into a state graph with conditional edges.

### State Type
```python
ClaimPipelineState:
    claim_input: ClaimInput
    claim_id: str
    validation_result: DocumentValidationResult | None
    extracted_documents: list[ExtractedDocument]
    cross_verification: CrossVerificationResult | None
    policy_evaluation: PolicyEvaluationResult | None
    decision: ClaimDecision | None
    trace: FullTrace
    current_confidence: float      # Starts at 1.0, decreases on failures
    should_stop: bool
    component_failed: bool
```

### Graph Topology
```
START → validate_documents
    → [if valid] → parse_documents → cross_verify
        → [if consistent] → evaluate_policy → make_decision → END
        → [if inconsistent] → END (with error decision)
    → [if invalid] → END (with error decision)
```

### Error Handling
Every node is wrapped in `try/except`. On component failure:
1. Log error to trace
2. Reduce `current_confidence` by 0.2 (minimum 0.3)
3. Set `component_failed = True`
4. Continue pipeline (graceful degradation)

---

## Policy Service

**Purpose**: Single source of truth for policy rules. All agents query this service.

### Key Methods
```python
get_member(member_id) → Member | None
get_member_join_date(member_id) → date | None
get_category_config(category) → OPDCategory | None
get_document_requirements(category) → DocumentRequirement | None
is_network_hospital(name) → bool
is_excluded_condition(diagnosis, treatment) → (bool, str)
is_excluded_procedure(description, category) → (bool, str)
get_condition_waiting_period_days(condition) → int | None
requires_pre_auth(category, amount, tests, line_items) → (bool, str)
```

### Properties
```python
per_claim_limit: float          # ₹5,000
annual_opd_limit: float         # ₹20,000
fraud_thresholds: FraudThresholds
```

---

## API Contracts

### POST /api/claims
- **Request**: `ClaimInput` (JSON body)
- **Response**: `ClaimDecision` (includes full trace)

### GET /api/claims
- **Response**: `list[ClaimSummary]`

### GET /api/claims/{claim_id}
- **Response**: `ClaimDecision` (full JSON from database)

### POST /api/claims/eval
- **Response**: `EvalReport` with summary + per-test results

### GET /health
- **Response**: `{ status: "healthy", service: "...", version: "1.0.0" }`
