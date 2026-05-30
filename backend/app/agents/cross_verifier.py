"""Agent 3: Cross-Document Verifier — Detects inconsistencies across documents.

Catches cases like TC003 where different documents belong to different patients.
Uses fuzzy name matching to handle minor variations.
"""


from thefuzz import fuzz

from app.models.claim import ClaimInput
from app.models.document import (
    CrossDocMismatch,
    CrossVerificationResult,
    ExtractedDocument,
)
from app.models.trace import CheckResult
from app.services.policy_service import PolicyService


# Threshold for fuzzy name matching (0-100)
NAME_MATCH_THRESHOLD = 80


class CrossDocumentVerifier:
    """Verifies consistency across all documents for a claim."""

    def __init__(self, policy_service: PolicyService):
        self.ps = policy_service

    def verify(
        self,
        claim: ClaimInput,
        extracted_docs: list[ExtractedDocument],
    ) -> tuple[CrossVerificationResult, list[CheckResult]]:
        """
        Cross-verify all documents for consistency.
        Returns (result, checks for trace).
        """
        checks: list[CheckResult] = []
        mismatches: list[CrossDocMismatch] = []

        # ── Patient name consistency ────────────────────────────────────
        self._check_patient_names(claim, extracted_docs, mismatches, checks)

        # ── Date consistency ────────────────────────────────────────────
        self._check_dates(claim, extracted_docs, mismatches, checks)

        is_consistent = len(mismatches) == 0

        error_message = None
        if not is_consistent:
            # Build user-facing error from mismatches
            name_mismatches = [m for m in mismatches if m.mismatch_type == "PATIENT_NAME"]
            if name_mismatches:
                m = name_mismatches[0]
                names = list(m.values_found.values())
                error_message = (
                    f"The uploaded documents appear to belong to different people. "
                    f"We found the following names: {', '.join(f'\"{n}\"' for n in names)}. "
                    f"All documents for a claim must belong to the same patient. "
                    f"Please verify and re-upload the correct documents."
                )

        return CrossVerificationResult(
            is_consistent=is_consistent,
            mismatches=mismatches,
            error_message=error_message,
        ), checks

    def _check_patient_names(
        self,
        claim: ClaimInput,
        extracted_docs: list[ExtractedDocument],
        mismatches: list[CrossDocMismatch],
        checks: list[CheckResult],
    ):
        """Check that patient names are consistent across all documents."""
        # Collect names from documents
        names_by_doc: dict[str, str] = {}

        # First check patient_name_on_doc from the raw input (for test cases like TC003)
        for doc_input in claim.documents:
            if doc_input.patient_name_on_doc:
                names_by_doc[doc_input.file_id] = doc_input.patient_name_on_doc

        # Also check extracted documents
        for doc in extracted_docs:
            if doc.patient_name and doc.file_id not in names_by_doc:
                names_by_doc[doc.file_id] = doc.patient_name

        if len(names_by_doc) < 2:
            checks.append(CheckResult(
                check_name="patient_name_consistency",
                status="PASS",
                message="Patient name cross-verification: insufficient documents to compare (single document or no names extracted).",
            ))
            return

        # Compare all pairs
        names = list(names_by_doc.values())
        file_ids = list(names_by_doc.keys())

        reference_name = names[0]
        inconsistent = False

        for i in range(1, len(names)):
            ratio = fuzz.ratio(reference_name.lower(), names[i].lower())
            if ratio < NAME_MATCH_THRESHOLD:
                inconsistent = True
                mismatches.append(CrossDocMismatch(
                    mismatch_type="PATIENT_NAME",
                    description=(
                        f"Patient name mismatch: '{reference_name}' (on {file_ids[0]}) "
                        f"vs '{names[i]}' (on {file_ids[i]})"
                    ),
                    values_found={file_ids[0]: reference_name, file_ids[i]: names[i]},
                ))

        if inconsistent:
            all_names = ", ".join(f"'{n}' (on {fid})" for fid, n in names_by_doc.items())
            checks.append(CheckResult(
                check_name="patient_name_consistency",
                status="FAIL",
                message=(
                    f"Patient name mismatch detected across documents: {all_names}. "
                    f"Documents may belong to different patients."
                ),
                details={"names_found": names_by_doc},
            ))
        else:
            checks.append(CheckResult(
                check_name="patient_name_consistency",
                status="PASS",
                message=f"Patient names consistent across all {len(names_by_doc)} documents: '{reference_name}'.",
            ))

        # Also verify against member record
        member = self.ps.get_member(claim.member_id)
        if member and reference_name:
            ratio = fuzz.ratio(member.name.lower(), reference_name.lower())
            if ratio < NAME_MATCH_THRESHOLD:
                checks.append(CheckResult(
                    check_name="member_identity_verification",
                    status="WARNING",
                    message=(
                        f"Patient name on documents ('{reference_name}') does not closely match "
                        f"the member name on file ('{member.name}'). Please verify identity."
                    ),
                    details={"document_name": reference_name, "member_name": member.name},
                ))
            else:
                checks.append(CheckResult(
                    check_name="member_identity_verification",
                    status="PASS",
                    message=f"Patient name matches member record: '{member.name}'.",
                ))

    def _check_dates(
        self,
        claim: ClaimInput,
        extracted_docs: list[ExtractedDocument],
        mismatches: list[CrossDocMismatch],
        checks: list[CheckResult],
    ):
        """Check date consistency across documents."""
        dates_by_doc: dict[str, str] = {}
        for doc in extracted_docs:
            if doc.document_date:
                dates_by_doc[doc.file_id] = str(doc.document_date)

        if len(dates_by_doc) < 2:
            return

        dates = list(set(dates_by_doc.values()))
        if len(dates) > 1:
            details_str = ", ".join(f"{fid}: {d}" for fid, d in dates_by_doc.items())
            checks.append(CheckResult(
                check_name="date_consistency",
                status="WARNING",
                message=f"Different dates found across documents: {details_str}.",
                details={"dates": dates_by_doc},
            ))
        else:
            checks.append(CheckResult(
                check_name="date_consistency",
                status="PASS",
                message=f"Document dates are consistent: {dates[0]}.",
            ))
