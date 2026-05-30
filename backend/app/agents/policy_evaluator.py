"""Agent 4: Policy Evaluator — Deterministic policy rule engine.

This is the most critical agent: it applies ALL policy rules from policy_terms.json.
No LLM is used here — every check is deterministic, testable, and logged to the trace.
"""


from datetime import date, datetime, timedelta

from app.models.claim import ClaimInput
from app.models.document import ExtractedDocument
from app.models.trace import CheckResult
from app.services.policy_service import PolicyService


class PolicyEvaluationResult:
    """Aggregated result of all policy checks."""

    def __init__(self):
        self.checks: list[CheckResult] = []
        self.is_eligible: bool = True
        self.hard_rejections: list[str] = []
        self.warnings: list[str] = []
        self.fraud_signals: list[str] = []
        self.excluded_line_items: list[dict] = []  # {description, amount, reason}
        self.covered_line_items: list[dict] = []   # {description, amount}
        self.requires_manual_review: bool = False
        self.manual_review_reasons: list[str] = []
        self.eligible_amount: float = 0.0
        self.per_claim_capped: bool = False
        self.waiting_period_end_date: date | None = None

    @property
    def has_hard_rejection(self) -> bool:
        return len(self.hard_rejections) > 0

    def add_check(self, check: CheckResult):
        self.checks.append(check)
        if check.status == "FAIL":
            self.is_eligible = False


class PolicyEvaluator:
    """Deterministic policy rule evaluator. Zero LLM dependency."""

    def __init__(self, policy_service: PolicyService):
        self.ps = policy_service

    def evaluate(
        self,
        claim: ClaimInput,
        extracted_docs: list[ExtractedDocument],
    ) -> PolicyEvaluationResult:
        result = PolicyEvaluationResult()

        # 1. Member eligibility
        self._check_member_eligibility(claim, result)

        # 2. Initial waiting period
        self._check_initial_waiting_period(claim, result)

        # 3. Condition-specific waiting periods
        self._check_condition_waiting_period(claim, extracted_docs, result)

        # 4. Exclusion check
        self._check_exclusions(claim, extracted_docs, result)

        # 5. Category coverage
        self._check_category_coverage(claim, result)

        # 6. Line item analysis (covered vs excluded procedures)
        self._check_line_items(claim, extracted_docs, result)

        # 7. Per-claim limit
        self._check_per_claim_limit(claim, result)

        # 8. Sub-limit check
        self._check_sub_limit(claim, result)

        # 9. Annual limit
        self._check_annual_limit(claim, result)

        # 10. Pre-authorization
        self._check_pre_authorization(claim, extracted_docs, result)

        # 11. Fraud signals
        self._check_fraud_signals(claim, result)

        # 12. Network hospital
        self._check_network_hospital(claim, result)

        return result

    # ── Individual Checks ───────────────────────────────────────────────

    def _check_member_eligibility(self, claim: ClaimInput, result: PolicyEvaluationResult):
        member = self.ps.get_member(claim.member_id)
        if member is None:
            result.add_check(CheckResult(
                check_name="member_eligibility",
                status="FAIL",
                message=f"Member {claim.member_id} not found in the policy roster.",
            ))
            result.hard_rejections.append("MEMBER_NOT_FOUND")
            return

        result.add_check(CheckResult(
            check_name="member_eligibility",
            status="PASS",
            message=f"Member {member.name} ({claim.member_id}) is active under the policy.",
            details={"member_name": member.name, "relationship": member.relationship},
        ))

    def _check_initial_waiting_period(self, claim: ClaimInput, result: PolicyEvaluationResult):
        join_date = self.ps.get_member_join_date(claim.member_id)
        if join_date is None:
            result.add_check(CheckResult(
                check_name="initial_waiting_period",
                status="SKIPPED",
                message="Could not determine member join date.",
            ))
            return

        waiting_days = self.ps.get_initial_waiting_period_days()
        eligible_date = join_date + timedelta(days=waiting_days)

        if claim.treatment_date < eligible_date:
            result.add_check(CheckResult(
                check_name="initial_waiting_period",
                status="FAIL",
                message=(
                    f"Treatment date {claim.treatment_date} is within the {waiting_days}-day "
                    f"initial waiting period. Member joined on {join_date} and is eligible "
                    f"from {eligible_date}."
                ),
                details={
                    "join_date": str(join_date),
                    "waiting_days": waiting_days,
                    "eligible_from": str(eligible_date),
                    "treatment_date": str(claim.treatment_date),
                },
            ))
            result.hard_rejections.append("INITIAL_WAITING_PERIOD")
            result.waiting_period_end_date = eligible_date
        else:
            result.add_check(CheckResult(
                check_name="initial_waiting_period",
                status="PASS",
                message=f"Treatment date is after the initial waiting period (eligible from {eligible_date}).",
            ))

    def _check_condition_waiting_period(
        self, claim: ClaimInput, extracted_docs: list[ExtractedDocument],
        result: PolicyEvaluationResult,
    ):
        # Collect all diagnoses and treatments from extracted documents
        diagnoses = []
        for doc in extracted_docs:
            if doc.diagnosis:
                diagnoses.append(doc.diagnosis)
            if doc.treatment:
                diagnoses.append(doc.treatment)

        if not diagnoses:
            result.add_check(CheckResult(
                check_name="condition_waiting_period",
                status="PASS",
                message="No specific conditions detected requiring extended waiting period.",
            ))
            return

        join_date = self.ps.get_member_join_date(claim.member_id)
        if join_date is None:
            return

        for diagnosis in diagnoses:
            waiting_days = self.ps.get_condition_waiting_period_days(diagnosis)
            if waiting_days is not None:
                eligible_date = join_date + timedelta(days=waiting_days)
                if claim.treatment_date < eligible_date:
                    # Find which condition matched
                    condition_name = diagnosis
                    for cond_key in self.ps.policy.waiting_periods.specific_conditions:
                        if cond_key.lower() in diagnosis.lower():
                            condition_name = cond_key.replace("_", " ").title()
                            break

                    result.add_check(CheckResult(
                        check_name="condition_waiting_period",
                        status="FAIL",
                        message=(
                            f"Condition '{diagnosis}' has a {waiting_days}-day waiting period. "
                            f"Member joined on {join_date} and is eligible for {condition_name}-related "
                            f"claims from {eligible_date}."
                        ),
                        details={
                            "condition": diagnosis,
                            "waiting_days": waiting_days,
                            "eligible_from": str(eligible_date),
                        },
                    ))
                    result.hard_rejections.append("WAITING_PERIOD")
                    result.waiting_period_end_date = eligible_date
                    return

        result.add_check(CheckResult(
            check_name="condition_waiting_period",
            status="PASS",
            message="No condition-specific waiting period violations found.",
        ))

    def _check_exclusions(
        self, claim: ClaimInput, extracted_docs: list[ExtractedDocument],
        result: PolicyEvaluationResult,
    ):
        for doc in extracted_docs:
            diagnosis = doc.diagnosis or ""
            treatment = doc.treatment or ""

            is_excluded, exclusion_text = self.ps.is_excluded_condition(diagnosis, treatment)
            if is_excluded:
                result.add_check(CheckResult(
                    check_name="exclusion_check",
                    status="FAIL",
                    message=(
                        f"The diagnosis/treatment '{diagnosis or treatment}' falls under the "
                        f"policy exclusion: '{exclusion_text}'. This claim is not eligible for coverage."
                    ),
                    details={
                        "diagnosis": diagnosis,
                        "treatment": treatment,
                        "exclusion": exclusion_text,
                    },
                ))
                result.hard_rejections.append("EXCLUDED_CONDITION")
                return

        result.add_check(CheckResult(
            check_name="exclusion_check",
            status="PASS",
            message="No policy exclusions apply to this claim.",
        ))

    def _check_category_coverage(self, claim: ClaimInput, result: PolicyEvaluationResult):
        cat_config = self.ps.get_category_config(claim.claim_category.value)
        if cat_config is None or not cat_config.covered:
            result.add_check(CheckResult(
                check_name="category_coverage",
                status="FAIL",
                message=f"Category '{claim.claim_category.value}' is not covered under this policy.",
            ))
            result.hard_rejections.append("CATEGORY_NOT_COVERED")
            return

        result.add_check(CheckResult(
            check_name="category_coverage",
            status="PASS",
            message=f"Category '{claim.claim_category.value}' is covered under this policy.",
        ))

    def _check_line_items(
        self, claim: ClaimInput, extracted_docs: list[ExtractedDocument],
        result: PolicyEvaluationResult,
    ):
        """Analyze individual line items for covered vs excluded procedures."""
        all_line_items = []
        for doc in extracted_docs:
            for item in doc.line_items:
                all_line_items.append(item)

        if not all_line_items:
            # No line items to analyze — use total claimed amount
            result.covered_line_items.append({
                "description": "Total Claimed",
                "amount": claim.claimed_amount,
            })
            result.eligible_amount = claim.claimed_amount
            result.add_check(CheckResult(
                check_name="line_item_analysis",
                status="PASS",
                message="No itemized breakdown available; using total claimed amount.",
            ))
            return

        covered_total = 0.0
        excluded_total = 0.0

        for item in all_line_items:
            is_excluded, excl_text = self.ps.is_excluded_procedure(
                item.description, claim.claim_category.value
            )
            if is_excluded:
                result.excluded_line_items.append({
                    "description": item.description,
                    "amount": item.amount,
                    "reason": f"Excluded under policy: {excl_text}",
                })
                excluded_total += item.amount
            else:
                result.covered_line_items.append({
                    "description": item.description,
                    "amount": item.amount,
                })
                covered_total += item.amount

        result.eligible_amount = covered_total

        if excluded_total > 0 and covered_total > 0:
            items_str = ", ".join(
                f"'{i['description']}' (₹{i['amount']:,.0f}) — {i['reason']}"
                for i in result.excluded_line_items
            )
            result.add_check(CheckResult(
                check_name="line_item_analysis",
                status="WARNING",
                message=(
                    f"Partial coverage: ₹{covered_total:,.0f} of ₹{claim.claimed_amount:,.0f} is eligible. "
                    f"Excluded items: {items_str}"
                ),
                details={
                    "covered_amount": covered_total,
                    "excluded_amount": excluded_total,
                    "excluded_items": result.excluded_line_items,
                },
            ))
        elif excluded_total > 0 and covered_total == 0:
            result.add_check(CheckResult(
                check_name="line_item_analysis",
                status="FAIL",
                message="All line items are excluded under the policy.",
            ))
        else:
            result.add_check(CheckResult(
                check_name="line_item_analysis",
                status="PASS",
                message=f"All {len(all_line_items)} line items are covered.",
            ))

    def _check_per_claim_limit(self, claim: ClaimInput, result: PolicyEvaluationResult):
        limit = self.ps.per_claim_limit
        cat_config = self.ps.get_category_config(claim.claim_category.value)

        # Categories with their own sub_limit higher than per_claim_limit
        # are governed by their sub_limit instead
        if cat_config and cat_config.sub_limit > limit:
            result.add_check(CheckResult(
                check_name="per_claim_limit",
                status="PASS",
                message=(
                    f"{claim.claim_category.value} category has its own sub-limit "
                    f"(₹{cat_config.sub_limit:,.0f}) which supersedes the general "
                    f"per-claim limit of ₹{limit:,.0f}."
                ),
            ))
            return

        if claim.claimed_amount > limit:
            result.add_check(CheckResult(
                check_name="per_claim_limit",
                status="FAIL",
                message=(
                    f"Claimed amount ₹{claim.claimed_amount:,.0f} exceeds the per-claim limit "
                    f"of ₹{limit:,.0f}. The maximum claimable amount per visit is ₹{limit:,.0f}."
                ),
                details={
                    "claimed_amount": claim.claimed_amount,
                    "per_claim_limit": limit,
                    "excess": claim.claimed_amount - limit,
                },
            ))
            result.hard_rejections.append("PER_CLAIM_EXCEEDED")
            result.per_claim_capped = True
        else:
            result.add_check(CheckResult(
                check_name="per_claim_limit",
                status="PASS",
                message=f"Claimed amount ₹{claim.claimed_amount:,.0f} is within per-claim limit of ₹{limit:,.0f}.",
            ))

    def _check_sub_limit(self, claim: ClaimInput, result: PolicyEvaluationResult):
        cat_config = self.ps.get_category_config(claim.claim_category.value)
        if cat_config is None:
            return

        sub_limit = cat_config.sub_limit
        amount_to_check = result.eligible_amount or claim.claimed_amount

        if amount_to_check > sub_limit:
            result.add_check(CheckResult(
                check_name="sub_limit",
                status="WARNING",
                message=(
                    f"Eligible amount ₹{amount_to_check:,.0f} exceeds the "
                    f"{claim.claim_category.value} sub-limit of ₹{sub_limit:,.0f}. "
                    f"Amount will be capped at ₹{sub_limit:,.0f}."
                ),
                details={"sub_limit": sub_limit, "eligible_amount": amount_to_check},
            ))
        else:
            result.add_check(CheckResult(
                check_name="sub_limit",
                status="PASS",
                message=f"Amount is within the {claim.claim_category.value} sub-limit of ₹{sub_limit:,.0f}.",
            ))

    def _check_annual_limit(self, claim: ClaimInput, result: PolicyEvaluationResult):
        annual_limit = self.ps.annual_opd_limit
        remaining = annual_limit - claim.ytd_claims_amount

        if remaining <= 0:
            result.add_check(CheckResult(
                check_name="annual_limit",
                status="FAIL",
                message=(
                    f"Annual OPD limit of ₹{annual_limit:,.0f} has been exhausted. "
                    f"Year-to-date claims: ₹{claim.ytd_claims_amount:,.0f}."
                ),
            ))
            result.hard_rejections.append("ANNUAL_LIMIT_EXHAUSTED")
        elif claim.claimed_amount > remaining:
            result.add_check(CheckResult(
                check_name="annual_limit",
                status="WARNING",
                message=(
                    f"Claimed amount exceeds remaining annual limit. "
                    f"Remaining: ₹{remaining:,.0f} of ₹{annual_limit:,.0f}."
                ),
                details={"remaining": remaining, "ytd": claim.ytd_claims_amount},
            ))
        else:
            result.add_check(CheckResult(
                check_name="annual_limit",
                status="PASS",
                message=(
                    f"Within annual OPD limit. Remaining: ₹{remaining:,.0f} of ₹{annual_limit:,.0f}."
                ),
            ))

    def _check_pre_authorization(
        self, claim: ClaimInput, extracted_docs: list[ExtractedDocument],
        result: PolicyEvaluationResult,
    ):
        # Collect tests from docs
        all_tests = []
        all_line_items_raw = []
        for doc in extracted_docs:
            all_tests.extend(doc.tests_ordered)
            all_line_items_raw.extend(
                {"description": li.description, "amount": li.amount}
                for li in doc.line_items
            )

        requires, reason = self.ps.requires_pre_auth(
            claim.claim_category.value,
            claim.claimed_amount,
            tests=all_tests,
            line_items=all_line_items_raw,
        )

        if requires:
            result.add_check(CheckResult(
                check_name="pre_authorization",
                status="FAIL",
                message=(
                    f"Pre-authorization is required but was not obtained. {reason}. "
                    f"Please obtain pre-authorization from the insurer and resubmit the claim."
                ),
                details={"reason": reason},
            ))
            result.hard_rejections.append("PRE_AUTH_MISSING")
        else:
            result.add_check(CheckResult(
                check_name="pre_authorization",
                status="PASS",
                message="No pre-authorization required for this claim.",
            ))

    def _check_fraud_signals(self, claim: ClaimInput, result: PolicyEvaluationResult):
        thresholds = self.ps.fraud_thresholds
        signals = []

        # Same-day claims
        same_day_count = sum(
            1 for h in claim.claims_history
            if h.date == str(claim.treatment_date)
        )
        if same_day_count >= thresholds.same_day_claims_limit:
            signals.append(
                f"Multiple same-day claims detected: {same_day_count + 1} claims on "
                f"{claim.treatment_date} (limit: {thresholds.same_day_claims_limit})"
            )

        # High-value claim
        if claim.claimed_amount >= thresholds.high_value_claim_threshold:
            signals.append(
                f"High-value claim: ₹{claim.claimed_amount:,.0f} exceeds "
                f"₹{thresholds.high_value_claim_threshold:,.0f} threshold"
            )

        # Monthly claims count
        # Count claims in the same month as treatment_date
        treatment_month = claim.treatment_date.strftime("%Y-%m")
        monthly_count = sum(
            1 for h in claim.claims_history
            if h.date.startswith(treatment_month)
        )
        if monthly_count >= thresholds.monthly_claims_limit:
            signals.append(
                f"Excessive monthly claims: {monthly_count + 1} claims in {treatment_month} "
                f"(limit: {thresholds.monthly_claims_limit})"
            )

        if signals:
            result.fraud_signals = signals
            result.requires_manual_review = True
            result.manual_review_reasons.extend(signals)
            result.add_check(CheckResult(
                check_name="fraud_detection",
                status="WARNING",
                message=(
                    f"Fraud signals detected: {'; '.join(signals)}. "
                    f"Claim routed to manual review."
                ),
                details={"signals": signals, "count": len(signals)},
            ))
        else:
            result.add_check(CheckResult(
                check_name="fraud_detection",
                status="PASS",
                message="No fraud signals detected.",
            ))

    def _check_network_hospital(self, claim: ClaimInput, result: PolicyEvaluationResult):
        if not claim.hospital_name:
            result.add_check(CheckResult(
                check_name="network_hospital",
                status="PASS",
                message="No hospital specified; network discount not applicable.",
                details={"is_network": False, "discount_percent": 0},
            ))
            return

        is_network = self.ps.is_network_hospital(claim.hospital_name)
        cat_config = self.ps.get_category_config(claim.claim_category.value)
        discount = cat_config.network_discount_percent if cat_config and is_network else 0

        if is_network:
            result.add_check(CheckResult(
                check_name="network_hospital",
                status="PASS",
                message=(
                    f"'{claim.hospital_name}' is a network hospital. "
                    f"{discount}% network discount will be applied."
                ),
                details={"is_network": True, "discount_percent": discount},
            ))
        else:
            result.add_check(CheckResult(
                check_name="network_hospital",
                status="PASS",
                message=f"'{claim.hospital_name}' is not a network hospital. No discount applied.",
                details={"is_network": False, "discount_percent": 0},
            ))
