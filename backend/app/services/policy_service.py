"""Policy service — loads and queries policy_terms.json."""


import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from app.models.policy import (
    DocumentRequirement,
    Member,
    OPDCategory,
    PolicyTerms,
)


class PolicyService:
    """Loads policy_terms.json and provides query methods for all agents."""

    def __init__(self, policy_path: str | Path | None = None):
        if policy_path is None:
            # Default: project root / policy_terms.json
            policy_path = (
                Path(__file__).parent.parent.parent.parent / "policy_terms.json"
            )
        self._path = Path(policy_path)
        self._policy: PolicyTerms | None = None

    @property
    def policy(self) -> PolicyTerms:
        if self._policy is None:
            with open(self._path) as f:
                data = json.load(f)
            self._policy = PolicyTerms(**data)
        return self._policy

    # ── Member Queries ──────────────────────────────────────────────────

    def get_member(self, member_id: str) -> Member | None:
        for m in self.policy.members:
            if m.member_id == member_id:
                return m
        return None

    def get_member_join_date(self, member_id: str) -> date | None:
        member = self.get_member(member_id)
        if member and member.join_date:
            return datetime.strptime(member.join_date, "%Y-%m-%d").date()
        # For dependents, use primary member's join date
        if member and member.primary_member_id:
            primary = self.get_member(member.primary_member_id)
            if primary and primary.join_date:
                return datetime.strptime(primary.join_date, "%Y-%m-%d").date()
        return None

    # ── Category Queries ────────────────────────────────────────────────

    def get_category_config(self, category: str) -> OPDCategory | None:
        key = category.lower()
        return self.policy.opd_categories.get(key)

    def get_document_requirements(self, category: str) -> DocumentRequirement | None:
        return self.policy.document_requirements.get(category.upper())

    # ── Network Hospital ────────────────────────────────────────────────

    def is_network_hospital(self, hospital_name: str) -> bool:
        if not hospital_name:
            return False
        name_lower = hospital_name.lower()
        return any(h.lower() in name_lower or name_lower in h.lower()
                   for h in self.policy.network_hospitals)

    # ── Waiting Period ──────────────────────────────────────────────────

    def get_initial_waiting_period_days(self) -> int:
        return self.policy.waiting_periods.initial_waiting_period_days

    def get_condition_waiting_period_days(self, condition: str) -> int | None:
        """Get waiting period in days for a specific condition.
        Returns None if no specific waiting period applies."""
        condition_lower = condition.lower()
        for cond_key, days in self.policy.waiting_periods.specific_conditions.items():
            if cond_key.lower() in condition_lower or condition_lower in cond_key.lower():
                return days
        return None

    # ── Exclusions ──────────────────────────────────────────────────────

    def is_excluded_condition(self, diagnosis: str, treatment: str | None = None) -> tuple[bool, str | None]:
        """Check if a diagnosis or treatment is excluded.
        Returns (is_excluded, matching_exclusion_text)."""
        text_to_check = f"{diagnosis} {treatment or ''}".lower()

        # Check general exclusions
        for excl in self.policy.exclusions.conditions:
            excl_lower = excl.lower()
            # Check for keyword matches
            keywords = excl_lower.replace(" and ", " ").split()
            if any(kw in text_to_check for kw in keywords if len(kw) > 3):
                return True, excl

        return False, None

    def is_excluded_procedure(self, procedure: str, category: str) -> tuple[bool, str | None]:
        """Check if a specific procedure is excluded for a category.
        Returns (is_excluded, matching_exclusion_text)."""
        cat_config = self.get_category_config(category)
        if not cat_config:
            return False, None

        proc_lower = procedure.lower()
        for excl in cat_config.excluded_procedures:
            if excl.lower() in proc_lower or proc_lower in excl.lower():
                return True, excl

        # Also check dental/vision specific exclusions
        if category.upper() == "DENTAL":
            for excl in self.policy.exclusions.dental_exclusions:
                if excl.lower() in proc_lower or proc_lower in excl.lower():
                    return True, excl

        if category.upper() == "VISION":
            for excl in self.policy.exclusions.vision_exclusions:
                if excl.lower() in proc_lower or proc_lower in excl.lower():
                    return True, excl

        return False, None

    def is_covered_procedure(self, procedure: str, category: str) -> bool:
        """Check if a procedure is explicitly in the covered list."""
        cat_config = self.get_category_config(category)
        if not cat_config or not cat_config.covered_procedures:
            return True  # No explicit list = everything not excluded is covered
        proc_lower = procedure.lower()
        return any(cp.lower() in proc_lower or proc_lower in cp.lower()
                   for cp in cat_config.covered_procedures)

    # ── Pre-Authorization ───────────────────────────────────────────────

    def requires_pre_auth(self, category: str, claimed_amount: float,
                          tests: list[str] | None = None,
                          line_items: list[dict] | None = None) -> tuple[bool, str | None]:
        """Check if pre-authorization is required.
        Returns (required, reason)."""
        cat_config = self.get_category_config(category)
        if not cat_config:
            return False, None

        # Check high-value tests
        if cat_config.high_value_tests_requiring_pre_auth:
            threshold = cat_config.pre_auth_threshold or 0
            all_items = []
            if tests:
                all_items.extend(tests)
            if line_items:
                all_items.extend(item.get("description", "") for item in line_items)

            for item_desc in all_items:
                item_lower = item_desc.lower()
                for hv_test in cat_config.high_value_tests_requiring_pre_auth:
                    if hv_test.lower() in item_lower and claimed_amount > threshold:
                        return True, (
                            f"{hv_test} scan costing ₹{claimed_amount:,.0f} requires pre-authorization "
                            f"as it exceeds the ₹{threshold:,.0f} threshold"
                        )

        return False, None

    # ── Fraud Thresholds ────────────────────────────────────────────────

    @property
    def fraud_thresholds(self):
        return self.policy.fraud_thresholds

    # ── Coverage Limits ─────────────────────────────────────────────────

    @property
    def per_claim_limit(self) -> float:
        return self.policy.coverage.per_claim_limit

    @property
    def sum_insured(self) -> float:
        return self.policy.coverage.sum_insured_per_employee

    @property
    def annual_opd_limit(self) -> float:
        return self.policy.coverage.annual_opd_limit


@lru_cache
def get_policy_service(policy_path: str | None = None) -> PolicyService:
    return PolicyService(policy_path)
