# Architecture — Plum Claims Processing System

## System Overview

A multi-agent AI system for processing health insurance OPD claims. The system takes claim documents (prescriptions, bills) and policy data as input, runs them through a 5-agent pipeline, and produces a decision with full traceability.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                         │
│  Dashboard │ Submit Claim │ Claim Detail │ Eval Report             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST API
┌──────────────────────────────▼──────────────────────────────────────┐
│                      FastAPI Backend                                │
│  POST /api/claims │ GET /api/claims/{id} │ POST /api/claims/eval   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                 LangGraph State Pipeline                            │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ Agent 1  │──>│ Agent 2  │──>│ Agent 3  │──>│ Agent 4  │──┐     │
│  │Validator │   │ Parser   │   │Cross-Ver │   │PolicyEval│  │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │     │
│       │                              │                       │     │
│       │ early stop                   │ early stop            ▼     │
│       └──────────────┬───────────────┘                ┌──────────┐ │
│                      │                                │ Agent 5  │ │
│                      ▼                                │ Decision │ │
│                    [END]                               │  Maker   │ │
│                                                       └──────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   SQLite Database   │
                    │  (Claims + Traces)  │
                    └─────────────────────┘
                    ┌─────────────────────┐
                    │  policy_terms.json  │
                    │   (Single Source    │
                    │    of Truth)        │
                    └─────────────────────┘
```

## Design Decisions

### 1. Deterministic Policy Logic (No LLM for Decisions)

**Why**: LLMs are non-deterministic. Insurance claim decisions must be reproducible and auditable. A claim processed twice must produce the same result.

**How**: All policy rules, limits, exclusions, waiting periods, and amount calculations are hardcoded in `PolicyService` → `PolicyEvaluator` → `DecisionMaker`. LLMs are only used for document understanding (parsing handwritten prescriptions, OCR).

### 2. LangGraph State Graph (Not Simple Sequential)

**Why**: Claims need conditional control flow:
- Wrong document type → stop immediately, don't process further
- Patient name mismatch across documents → stop with specific error
- Component failure → continue with degraded confidence

**How**: `StateGraph` with conditional edges (`should_continue_after_validation`, `should_continue_after_cross_verify`). The state is a typed dict that flows through all agents, accumulating checks and decisions.

### 3. Single Source of Truth: policy_terms.json

**Why**: Policy rules change. Hardcoding limits across 5 agents would lead to inconsistencies.

**How**: `PolicyService` loads `policy_terms.json` once, provides typed queries (`get_category_config`, `is_excluded_condition`, `requires_pre_auth`). All agents import `PolicyService`, never read the JSON directly.

### 4. Graceful Degradation

**Why**: In production, any component can fail (LLM timeout, OCR service down). The system must not crash — it should degrade gracefully.

**How**: Every node in the pipeline is wrapped in `try/except`. Failures are logged to the trace, confidence is reduced by 0.2, and the pipeline continues. The `DecisionMaker` sees `component_failed=True` and adds warnings.

### 5. Full Observability via Trace

**Why**: Insurance is regulated. Every decision must be explainable — which checks ran, what passed, what failed, why.

**How**: Every agent appends a `TraceEntry` to the `FullTrace`. Each entry contains:
- `checks_performed`: List of `CheckResult` (check_name, status, message, details)
- `input_summary` / `output_summary`: What the agent received and produced
- `error`: If the component failed

The full trace is returned in every API response and stored in the database.

### 6. Multi-LLM Provider Support for Document Extraction

**Why**: Extracting detailed schema fields from doctors' prescriptions and hospital bills requires a powerful vision/text agent capable of interpreting handwritten notes and unstructured formats. Different environments may prefer different LLM partners (Cursor, Google Antigravity, or NVIDIA NIM) depending on deployment locality, cost, or features like thinking outputs.

**How**: When a claim is submitted with unstructured documents, the `DocumentParser` calls the LLM service router. The router delegates to the configured provider:
- **Cursor SDK**: Spawns a local programmatic agent using the `gpt-5.4-nano` model.
- **Google Antigravity SDK**: Uses the `google-antigravity` async agent client.
- **NVIDIA NIM**: Uses the `openai` SDK to call NVIDIA's NIM API base URL, utilizing `deepseek-ai/deepseek-v4-flash` to extract fields and stream step-by-step reasoning.
All providers support metadata-based fallback to preserve 12/12 passing claims during rate-limiting or network issues.


## Agent Responsibilities

| Agent | Role | LLM? | Can Stop Pipeline? |
|-------|------|-------|--------------------|
| **DocumentValidator** | Check document types, quality | No | Yes (wrong type, unreadable) |
| **DocumentParser** | Extract structured data from docs | Yes (Cursor SDK) | No (degrades gracefully) |
| **CrossDocVerifier** | Verify consistency across docs | No | Yes (patient name mismatch) |
| **PolicyEvaluator** | Apply all policy rules deterministically | No | No (adds rejections to result) |
| **DecisionMaker** | Calculate final amount, make decision | No | No (always produces a decision) |

## Amount Calculation Flow (DecisionMaker)

```
claimed_amount (or eligible_amount from line items)
    │
    ├── Network discount (if network hospital)
    │   └── amount * (1 - discount_percent)
    │
    ├── Co-pay deduction
    │   └── amount * (1 - copay_percent)
    │
    └── Annual limit cap
        └── min(amount, annual_limit - ytd_claims)
```

**Key insight**: Sub-limits are annual category limits, not per-claim caps. The per-claim limit (₹5,000) only applies to categories whose sub_limit ≤ per_claim_limit (e.g., CONSULTATION sub_limit=₹2,000 < ₹5,000, so per-claim limit applies). DENTAL has sub_limit=₹10,000 > ₹5,000, so it's governed by its own sub_limit.

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | FastAPI + Python 3.14 | Type safety, async, Pydantic v2 |
| Pipeline | LangGraph | State-based graph with conditional edges |
| LLM Engine | Cursor, Antigravity, or NVIDIA NIM | Modular LLM engine supporting multiple models and API thought streaming |
| Models | Pydantic v2 | Strict validation, JSON serialization |
| Database | SQLite + SQLAlchemy | Zero-config, stores full decision JSON |
| Frontend | Next.js 15 + Tailwind | App Router, server components |
| Matching | thefuzz | Fuzzy name matching for cross-verification |

## Directory Structure

```
backend/
├── app/
│   ├── agents/           # 5 agents + orchestrator
│   │   ├── document_validator.py
│   │   ├── document_parser.py
│   │   ├── cross_verifier.py
│   │   ├── policy_evaluator.py
│   │   ├── decision_maker.py
│   │   └── orchestrator.py
│   ├── api/              # FastAPI routes
│   │   └── claims.py
│   ├── db/               # Database layer
│   │   └── database.py
│   ├── models/           # Pydantic data models
│   │   ├── claim.py
│   │   ├── document.py
│   │   ├── policy.py
│   │   └── trace.py
│   ├── services/         # Business logic services
│   │   └── policy_service.py
│   ├── config.py
│   └── main.py
├── pyproject.toml
└── tests/

frontend/
├── src/
│   ├── app/              # Next.js App Router pages
│   │   ├── page.tsx      # Dashboard
│   │   ├── eval/         # Evaluation report
│   │   └── claims/       # Claim submission + detail
│   ├── lib/              # API client + types
│   └── components/       # Shared UI components
```
