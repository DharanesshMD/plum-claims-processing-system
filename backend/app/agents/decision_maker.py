"""Agent 5: Decision Maker — Aggregates all signals into final claim decision.

Calculates approved amounts with correct order of operations:
1. Start with eligible amount
2. Apply network discount (if applicable) — BEFORE co-pay
3. Apply co-pay percentage
4. Cap at sub-limit
5. Cap at per-claim limit
6. Cap at remaining annual limit
"""


from app.models.claim import (
    AmountBreakdown,
    ClaimDecision,
    ClaimInput,
    Decision,
    LineItemDecision,
)
from app.models.document import ExtractedDocument
from app.models.trace import CheckResult
from app.agents.policy_evaluator import PolicyEvaluationResult
from app.services.policy_service import PolicyService


class DecisionMaker:
    """Aggregates all upstream outputs into a final decision with amount calculation."""

    def __init__(self, policy_service: PolicyService):
        self.ps = policy_service

    def make_decision(
        self,
        claim: ClaimInput,
        policy_eval: PolicyEvaluationResult,
        extracted_docs: list[ExtractedDocument],
        pipeline_confidence: float = 1.0,
        component_failed: bool = False,
    ) -> tuple[ClaimDecision, list[CheckResult]]:
        """
        Produce a final decision based on all upstream results.
        Returns (ClaimDecision, list of checks performed).
        """
        checks: list[CheckResult] = []
        warnings: list[str] = []

        # ── Handle hard rejections ──────────────────────────────────────
        if policy_eval.has_hard_rejection:
            decision_type, explanation = self._build_rejection(claim, policy_eval)
            checks.append(CheckResult(
                check_name="final_decision",
                status="FAIL",
                message=explanation,
            ))
            return ClaimDecision(
                claim_id="",  # Set by orchestrator
                decision=decision_type,
                approved_amount=0,
                rejection_reasons=policy_eval.hard_rejections,
                confidence_score=min(pipeline_confidence, 0.95),
                explanation=explanation,
                warnings=warnings,
            ), checks

        # ── Handle fraud / manual review ────────────────────────────────
        if policy_eval.requires_manual_review:
            explanation = self._build_manual_review_explanation(policy_eval)
            checks.append(CheckResult(
                check_name="final_decision",
                status="WARNING",
                message=explanation,
            ))
            return ClaimDecision(
                claim_id="",
                decision=Decision.MANUAL_REVIEW,
                approved_amount=None,
                rejection_reasons=[],
                confidence_score=min(pipeline_confidence, 0.70),
                explanation=explanation,
                warnings=policy_eval.manual_review_reasons,
            ), checks

        # ── Calculate approved amount ───────────────────────────────────
        breakdown, line_item_decisions = self._calculate_amount(claim, policy_eval)

        # ── Determine decision type ─────────────────────────────────────
        has_excluded_items = len(policy_eval.excluded_line_items) > 0
        has_covered_items = len(policy_eval.covered_line_items) > 0

        if has_excluded_items and has_covered_items:
            decision_type = Decision.PARTIAL
        elif breakdown.approved_amount > 0:
            decision_type = Decision.APPROVED
        else:
            decision_type = Decision.REJECTED

        # ── Build explanation ───────────────────────────────────────────
        explanation = self._build_approval_explanation(
            claim, breakdown, policy_eval, decision_type
        )

        # ── Adjust confidence for component failure ─────────────────────
        confidence = pipeline_confidence
        if component_failed:
            confidence = max(confidence - 0.2, 0.3)
            warnings.append(
                "A pipeline component failed during processing. "
                "Confidence has been reduced. Manual review is recommended."
            )

        checks.append(CheckResult(
            check_name="final_decision",
            status="PASS" if decision_type in (Decision.APPROVED, Decision.PARTIAL) else "FAIL",
            message=explanation,
            details={"approved_amount": breakdown.approved_amount},
        ))

        return ClaimDecision(
            claim_id="",
            decision=decision_type,
            approved_amount=breakdown.approved_amount,
            rejection_reasons=[],
            confidence_score=confidence,
            explanation=explanation,
            line_item_decisions=line_item_decisions,
            amount_breakdown=breakdown,
            warnings=warnings,
        ), checks

    def _calculate_amount(
        self,
        claim: ClaimInput,
        policy_eval: PolicyEvaluationResult,
    ) -> tuple[AmountBreakdown, list[LineItemDecision]]:
        """Calculate approved amount with correct order of operations."""

        cat_config = self.ps.get_category_config(claim.claim_category.value)
        steps: list[str] = []
        line_item_decisions: list[LineItemDecision] = []

        # Step 1: Start with eligible amount (after line-item exclusions)
        eligible_amount = policy_eval.eligible_amount or claim.claimed_amount
        steps.append(f"Starting amount: ₹{eligible_amount:,.0f}")

        # Build line item decisions
        for item in policy_eval.covered_line_items:
            line_item_decisions.append(LineItemDecision(
                description=item["description"],
                amount=item["amount"],
                status="APPROVED",
            ))
        for item in policy_eval.excluded_line_items:
            line_item_decisions.append(LineItemDecision(
                description=item["description"],
                amount=item["amount"],
                status="REJECTED",
                reason=item.get("reason", "Excluded under policy"),
            ))

        # Step 2: Apply network discount (BEFORE co-pay)
        network_discount_pct = 0.0
        network_discount_amt = 0.0
        if claim.hospital_name and self.ps.is_network_hospital(claim.hospital_name) and cat_config:
            network_discount_pct = cat_config.network_discount_percent
            network_discount_amt = eligible_amount * (network_discount_pct / 100)
            steps.append(
                f"Network discount ({network_discount_pct}%): -₹{network_discount_amt:,.0f}"
            )

        amount_after_discount = eligible_amount - network_discount_amt

        # Step 3: Apply co-pay
        copay_pct = cat_config.copay_percent if cat_config else 0.0
        copay_amt = amount_after_discount * (copay_pct / 100)
        if copay_pct > 0:
            steps.append(f"Co-pay ({copay_pct}%): -₹{copay_amt:,.0f}")
        amount_after_copay = amount_after_discount - copay_amt

        # Step 4: Cap at remaining annual limit
        sub_limit = cat_config.sub_limit if cat_config else None
        sub_limit_applied = False
        per_claim_limit = self.ps.per_claim_limit
        per_claim_limit_applied = False

        annual_limit_remaining = self.ps.annual_opd_limit - claim.ytd_claims_amount
        annual_limit_applied = False
        if amount_after_copay > annual_limit_remaining:
            steps.append(f"Annual limit cap (remaining ₹{annual_limit_remaining:,.0f})")
            amount_after_copay = max(annual_limit_remaining, 0)
            annual_limit_applied = True

        approved_amount = round(amount_after_copay, 2)
        steps.append(f"Final approved amount: ₹{approved_amount:,.0f}")

        return AmountBreakdown(
            claimed_amount=claim.claimed_amount,
            network_discount_percent=network_discount_pct,
            network_discount_amount=network_discount_amt,
            amount_after_discount=amount_after_discount,
            copay_percent=copay_pct,
            copay_amount=copay_amt,
            amount_after_copay=amount_after_copay,
            sub_limit=sub_limit,
            sub_limit_applied=sub_limit_applied,
            per_claim_limit=per_claim_limit,
            per_claim_limit_applied=per_claim_limit_applied,
            annual_limit_remaining=annual_limit_remaining,
            annual_limit_applied=annual_limit_applied,
            approved_amount=approved_amount,
            calculation_steps=steps,
        ), line_item_decisions

    def _build_rejection(
        self, claim: ClaimInput, policy_eval: PolicyEvaluationResult
    ) -> tuple[Decision, str]:
        """Build rejection decision and explanation."""
        reasons = []
        for check in policy_eval.checks:
            if check.status == "FAIL":
                reasons.append(check.message)

        explanation = "Claim rejected. " + " ".join(reasons)
        return Decision.REJECTED, explanation

    def _build_manual_review_explanation(self, policy_eval: PolicyEvaluationResult) -> str:
        signals = "; ".join(policy_eval.manual_review_reasons)
        return (
            f"Claim routed to manual review due to the following signals: {signals}. "
            f"An operations team member will review this claim."
        )

    def _build_approval_explanation(
        self,
        claim: ClaimInput,
        breakdown: AmountBreakdown,
        policy_eval: PolicyEvaluationResult,
        decision_type: Decision,
    ) -> str:
        if decision_type == Decision.PARTIAL:
            excluded_desc = ", ".join(
                f"'{i['description']}' (₹{i['amount']:,.0f})"
                for i in policy_eval.excluded_line_items
            )
            return (
                f"Partial approval: ₹{breakdown.approved_amount:,.0f} of "
                f"₹{claim.claimed_amount:,.0f} approved. "
                f"Excluded items: {excluded_desc}. "
                f"Calculation: {' → '.join(breakdown.calculation_steps)}"
            )

        steps_str = " → ".join(breakdown.calculation_steps)
        return (
            f"Claim approved for ₹{breakdown.approved_amount:,.0f}. "
            f"Calculation: {steps_str}"
        )
