"""Claim Pipeline Orchestrator — LangGraph state graph that wires all 5 agents.

State flows: validate → parse → cross-verify → policy-evaluate → decide
Early exits: validation/cross-verify failures short-circuit to decision.
Graceful degradation: component failures are caught, logged, and the pipeline continues.
"""


import uuid
from datetime import datetime
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.cross_verifier import CrossDocumentVerifier
from app.agents.decision_maker import DecisionMaker
from app.agents.document_parser import DocumentParser
from app.agents.document_validator import DocumentValidator
from app.agents.policy_evaluator import PolicyEvaluationResult, PolicyEvaluator
from app.models.claim import ClaimDecision, ClaimInput, Decision
from app.models.document import (
    CrossVerificationResult,
    DocumentValidationResult,
    ExtractedDocument,
)
from app.models.trace import CheckResult, FullTrace, TraceEntry
from app.services.policy_service import PolicyService, get_policy_service


# ── Pipeline State ──────────────────────────────────────────────────────

class ClaimPipelineState(TypedDict):
    claim_input: ClaimInput
    claim_id: str
    validation_result: Optional[DocumentValidationResult]
    extracted_documents: list[ExtractedDocument]
    cross_verification: Optional[CrossVerificationResult]
    policy_evaluation: Optional[PolicyEvaluationResult]
    decision: Optional[ClaimDecision]
    trace: FullTrace
    current_confidence: float
    should_stop: bool
    component_failed: bool
    error_message: Optional[str]


# ── Node Functions ──────────────────────────────────────────────────────

def validate_documents_node(state: ClaimPipelineState) -> dict:
    """Agent 1: Document Validator node."""
    started = datetime.utcnow()
    claim = state["claim_input"]
    ps = get_policy_service()
    validator = DocumentValidator(ps)

    try:
        result, checks = validator.validate(claim)
    except Exception as e:
        # Graceful degradation
        return _handle_component_failure(state, "DocumentValidator", started, str(e))

    completed = datetime.utcnow()
    status = "SUCCESS" if result.is_valid else "FAILED"

    trace_entry = TraceEntry(
        agent_name="DocumentValidator",
        started_at=started,
        completed_at=completed,
        status=status,
        input_summary={
            "document_count": len(claim.documents),
            "claim_category": claim.claim_category.value,
        },
        output_summary={
            "is_valid": result.is_valid,
            "issue_count": len(result.issues),
            "error_message": result.error_message,
        },
        checks_performed=checks,
    )

    trace = state["trace"]
    trace.agent_traces.append(trace_entry)

    if not result.is_valid:
        # Early stop — build a rejection decision immediately
        decision = ClaimDecision(
            claim_id=state["claim_id"],
            decision=None,  # No decision made — stopped early
            approved_amount=None,
            confidence_score=state["current_confidence"],
            explanation=result.error_message or "Document validation failed.",
            trace=trace,
            created_at=datetime.utcnow(),
        )
        trace.pipeline_completed_at = datetime.utcnow()
        trace.overall_status = "STOPPED_EARLY"

        return {
            "validation_result": result,
            "should_stop": True,
            "decision": decision,
            "trace": trace,
        }

    return {
        "validation_result": result,
        "trace": trace,
    }


def parse_documents_node(state: ClaimPipelineState) -> dict:
    """Agent 2: Document Parser node."""
    started = datetime.utcnow()
    claim = state["claim_input"]
    parser = DocumentParser()

    try:
        # Simulate component failure if requested
        if claim.simulate_component_failure:
            raise RuntimeError("Simulated component failure in DocumentParser")

        extracted, checks = parser.parse(claim)
    except Exception as e:
        return _handle_component_failure(state, "DocumentParser", started, str(e))

    completed = datetime.utcnow()

    trace_entry = TraceEntry(
        agent_name="DocumentParser",
        started_at=started,
        completed_at=completed,
        status="SUCCESS",
        input_summary={"document_count": len(claim.documents)},
        output_summary={
            "extracted_count": len(extracted),
            "diagnoses": [d.diagnosis for d in extracted if d.diagnosis],
        },
        checks_performed=checks,
    )

    trace = state["trace"]
    trace.agent_traces.append(trace_entry)

    return {
        "extracted_documents": extracted,
        "trace": trace,
    }


def cross_verify_node(state: ClaimPipelineState) -> dict:
    """Agent 3: Cross-Document Verifier node."""
    started = datetime.utcnow()
    claim = state["claim_input"]
    extracted = state.get("extracted_documents", [])
    ps = get_policy_service()
    verifier = CrossDocumentVerifier(ps)

    try:
        result, checks = verifier.verify(claim, extracted)
    except Exception as e:
        return _handle_component_failure(state, "CrossDocVerifier", started, str(e))

    completed = datetime.utcnow()
    status = "SUCCESS" if result.is_consistent else "FAILED"

    trace_entry = TraceEntry(
        agent_name="CrossDocVerifier",
        started_at=started,
        completed_at=completed,
        status=status,
        input_summary={"documents_compared": len(extracted)},
        output_summary={
            "is_consistent": result.is_consistent,
            "mismatches": len(result.mismatches),
            "error_message": result.error_message,
        },
        checks_performed=checks,
    )

    trace = state["trace"]
    trace.agent_traces.append(trace_entry)

    if not result.is_consistent:
        decision = ClaimDecision(
            claim_id=state["claim_id"],
            decision=None,
            approved_amount=None,
            confidence_score=max(state["current_confidence"] - 0.3, 0.1),
            explanation=result.error_message or "Cross-document verification failed.",
            trace=trace,
            created_at=datetime.utcnow(),
        )
        trace.pipeline_completed_at = datetime.utcnow()
        trace.overall_status = "STOPPED_EARLY"

        return {
            "cross_verification": result,
            "should_stop": True,
            "decision": decision,
            "trace": trace,
        }

    return {
        "cross_verification": result,
        "trace": trace,
    }


def evaluate_policy_node(state: ClaimPipelineState) -> dict:
    """Agent 4: Policy Evaluator node."""
    started = datetime.utcnow()
    claim = state["claim_input"]
    extracted = state.get("extracted_documents", [])
    ps = get_policy_service()
    evaluator = PolicyEvaluator(ps)

    try:
        result = evaluator.evaluate(claim, extracted)
    except Exception as e:
        return _handle_component_failure(state, "PolicyEvaluator", started, str(e))

    completed = datetime.utcnow()

    failed_checks = [c for c in result.checks if c.status == "FAIL"]
    status = "SUCCESS" if not failed_checks else "FAILED"

    trace_entry = TraceEntry(
        agent_name="PolicyEvaluator",
        started_at=started,
        completed_at=completed,
        status=status,
        input_summary={
            "claim_category": claim.claim_category.value,
            "claimed_amount": claim.claimed_amount,
            "member_id": claim.member_id,
        },
        output_summary={
            "checks_count": len(result.checks),
            "passed": len([c for c in result.checks if c.status == "PASS"]),
            "failed": len(failed_checks),
            "warnings": len([c for c in result.checks if c.status == "WARNING"]),
            "hard_rejections": result.hard_rejections,
            "fraud_signals": result.fraud_signals,
        },
        checks_performed=result.checks,
    )

    trace = state["trace"]
    trace.agent_traces.append(trace_entry)

    return {
        "policy_evaluation": result,
        "trace": trace,
    }


def make_decision_node(state: ClaimPipelineState) -> dict:
    """Agent 5: Decision Maker node."""
    started = datetime.utcnow()
    claim = state["claim_input"]
    extracted = state.get("extracted_documents", [])
    policy_eval = state.get("policy_evaluation")
    ps = get_policy_service()
    maker = DecisionMaker(ps)

    # If we don't have policy evaluation (due to component failure), create a minimal one
    if policy_eval is None:
        policy_eval = PolicyEvaluationResult()
        policy_eval.eligible_amount = claim.claimed_amount

    try:
        decision, checks = maker.make_decision(
            claim=claim,
            policy_eval=policy_eval,
            extracted_docs=extracted,
            pipeline_confidence=state["current_confidence"],
            component_failed=state.get("component_failed", False),
        )
    except Exception as e:
        return _handle_component_failure(state, "DecisionMaker", started, str(e))

    completed = datetime.utcnow()

    trace_entry = TraceEntry(
        agent_name="DecisionMaker",
        started_at=started,
        completed_at=completed,
        status="SUCCESS",
        input_summary={
            "has_policy_eval": state.get("policy_evaluation") is not None,
            "component_failed": state.get("component_failed", False),
        },
        output_summary={
            "decision": decision.decision.value if decision.decision else None,
            "approved_amount": decision.approved_amount,
            "confidence_score": decision.confidence_score,
        },
        checks_performed=checks,
    )

    trace = state["trace"]
    trace.agent_traces.append(trace_entry)
    trace.pipeline_completed_at = datetime.utcnow()
    trace.overall_status = "COMPLETED"
    trace.confidence_breakdown = {
        entry.agent_name: entry.confidence_impact
        for entry in trace.agent_traces
    }

    # Update decision with trace and claim_id
    decision.claim_id = state["claim_id"]
    decision.trace = trace

    return {
        "decision": decision,
        "trace": trace,
    }


# ── Conditional Edges ───────────────────────────────────────────────────

def should_continue_after_validation(state: ClaimPipelineState) -> str:
    if state.get("should_stop"):
        return END
    return "parse_documents"


def should_continue_after_cross_verify(state: ClaimPipelineState) -> str:
    if state.get("should_stop"):
        return END
    return "evaluate_policy"


# ── Helper ──────────────────────────────────────────────────────────────

def _handle_component_failure(
    state: ClaimPipelineState,
    agent_name: str,
    started: datetime,
    error_msg: str,
) -> dict:
    """Handle a component failure gracefully — log it and continue."""
    completed = datetime.utcnow()

    trace_entry = TraceEntry(
        agent_name=agent_name,
        started_at=started,
        completed_at=completed,
        status="FAILED",
        input_summary={},
        output_summary={"error": error_msg},
        checks_performed=[
            CheckResult(
                check_name=f"{agent_name}_execution",
                status="FAIL",
                message=f"Component failed: {error_msg}. Pipeline continues with degraded confidence.",
            )
        ],
        confidence_impact=-0.2,
        error=error_msg,
    )

    trace = state["trace"]
    trace.agent_traces.append(trace_entry)

    new_confidence = max(state["current_confidence"] - 0.2, 0.3)

    return {
        "trace": trace,
        "current_confidence": new_confidence,
        "component_failed": True,
    }


# ── Build Graph ─────────────────────────────────────────────────────────

def build_claims_pipeline() -> StateGraph:
    """Build and compile the LangGraph state graph for claims processing."""
    graph = StateGraph(ClaimPipelineState)

    # Add nodes
    graph.add_node("validate_documents", validate_documents_node)
    graph.add_node("parse_documents", parse_documents_node)
    graph.add_node("cross_verify", cross_verify_node)
    graph.add_node("evaluate_policy", evaluate_policy_node)
    graph.add_node("make_decision", make_decision_node)

    # Add edges
    graph.add_edge(START, "validate_documents")
    graph.add_conditional_edges(
        "validate_documents",
        should_continue_after_validation,
    )
    graph.add_edge("parse_documents", "cross_verify")
    graph.add_conditional_edges(
        "cross_verify",
        should_continue_after_cross_verify,
    )
    graph.add_edge("evaluate_policy", "make_decision")
    graph.add_edge("make_decision", END)

    return graph


def get_compiled_pipeline():
    graph = build_claims_pipeline()
    return graph.compile()


async def process_claim(claim_input: ClaimInput) -> ClaimDecision:
    """Process a claim through the full pipeline."""
    claim_id = f"CLM_{uuid.uuid4().hex[:8].upper()}"

    initial_state: ClaimPipelineState = {
        "claim_input": claim_input,
        "claim_id": claim_id,
        "validation_result": None,
        "extracted_documents": [],
        "cross_verification": None,
        "policy_evaluation": None,
        "decision": None,
        "trace": FullTrace(
            claim_id=claim_id,
            pipeline_started_at=datetime.utcnow(),
        ),
        "current_confidence": 1.0,
        "should_stop": False,
        "component_failed": False,
        "error_message": None,
    }

    pipeline = get_compiled_pipeline()
    final_state = await pipeline.ainvoke(initial_state)

    decision = final_state.get("decision")
    if decision is None:
        # Should not happen, but safety net
        decision = ClaimDecision(
            claim_id=claim_id,
            decision=Decision.MANUAL_REVIEW,
            confidence_score=0.1,
            explanation="Pipeline completed without producing a decision. Manual review required.",
            trace=final_state.get("trace"),
            created_at=datetime.utcnow(),
        )

    return decision
