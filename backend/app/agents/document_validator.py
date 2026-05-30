"""Agent 1: Document Validator — Early detection of document problems.

Stops the pipeline early with specific, actionable error messages if:
- Wrong document type uploaded (TC001)
- Unreadable document quality (TC002)
- Missing required documents
"""


from app.models.claim import ClaimInput
from app.models.document import (
    DocumentIssue,
    DocumentValidationResult,
    ValidatedDocument,
)
from app.models.trace import CheckResult
from app.services.policy_service import PolicyService


class DocumentValidator:
    """Validates uploaded documents against policy requirements."""

    def __init__(self, policy_service: PolicyService):
        self.ps = policy_service

    def validate(self, claim: ClaimInput) -> tuple[DocumentValidationResult, list[CheckResult]]:
        """
        Validate all documents for a claim.
        Returns (validation_result, list of checks for trace).
        """
        checks: list[CheckResult] = []
        issues: list[DocumentIssue] = []
        validated_docs: list[ValidatedDocument] = []

        # Get document requirements for this claim category
        doc_req = self.ps.get_document_requirements(claim.claim_category.value)
        if doc_req is None:
            return DocumentValidationResult(
                is_valid=False,
                issues=[DocumentIssue(
                    issue_type="MISSING_REQUIRED_DOCUMENT",
                    severity="ERROR",
                    message=f"No document requirements defined for category '{claim.claim_category.value}'.",
                )],
                error_message=f"Unknown claim category: {claim.claim_category.value}",
            ), checks

        required_types = set(doc_req.required)

        # ── Check for unreadable documents first ────────────────────────
        for doc in claim.documents:
            if doc.quality and doc.quality.upper() == "UNREADABLE":
                doc_type_label = doc.actual_type.replace("_", " ").lower()
                issue = DocumentIssue(
                    issue_type="UNREADABLE_DOCUMENT",
                    severity="ERROR",
                    message=(
                        f"The uploaded {doc_type_label} ('{doc.file_name or doc.file_id}') "
                        f"is unreadable. The image appears to be blurry or too low quality "
                        f"to extract information from. Please re-upload a clearer photo or "
                        f"scan of your {doc_type_label}."
                    ),
                    file_id=doc.file_id,
                )
                issues.append(issue)
                checks.append(CheckResult(
                    check_name="document_quality",
                    status="FAIL",
                    message=issue.message,
                    details={"file_id": doc.file_id, "quality": doc.quality},
                ))

        if issues:
            return DocumentValidationResult(
                is_valid=False,
                issues=issues,
                error_message=issues[0].message,
            ), checks

        # ── Check document types ────────────────────────────────────────
        uploaded_types: dict[str, list[str]] = {}  # type -> [file_ids]
        for doc in claim.documents:
            doc_type = doc.actual_type.upper()
            if doc_type not in uploaded_types:
                uploaded_types[doc_type] = []
            uploaded_types[doc_type].append(doc.file_id)

        # Check for missing required documents
        missing_types = required_types - set(uploaded_types.keys())

        if missing_types:
            # Check if the user uploaded wrong documents instead
            extra_types = set(uploaded_types.keys()) - required_types
            optional_types = set(doc_req.optional)
            wrong_uploads = extra_types - optional_types

            if wrong_uploads:
                # User uploaded wrong document type
                uploaded_desc = ", ".join(
                    f"{t.replace('_', ' ').title()} (x{len(uploaded_types[t])})"
                    for t in wrong_uploads
                )
                missing_desc = ", ".join(
                    t.replace("_", " ").title() for t in missing_types
                )
                error_msg = (
                    f"Document type mismatch: You uploaded {uploaded_desc}, but a "
                    f"{claim.claim_category.value.title()} claim requires a {missing_desc}. "
                    f"Please upload the correct document type."
                )
            else:
                missing_desc = ", ".join(
                    t.replace("_", " ").title() for t in missing_types
                )
                error_msg = (
                    f"Missing required document(s) for {claim.claim_category.value.title()} claim: "
                    f"{missing_desc}. Please upload the required documents."
                )

            for mt in missing_types:
                issue = DocumentIssue(
                    issue_type="MISSING_REQUIRED_DOCUMENT" if not wrong_uploads else "WRONG_DOCUMENT_TYPE",
                    severity="ERROR",
                    message=error_msg,
                    required_type=mt,
                    uploaded_type=next(iter(wrong_uploads), None) if wrong_uploads else None,
                )
                issues.append(issue)

            checks.append(CheckResult(
                check_name="document_type_validation",
                status="FAIL",
                message=error_msg,
                details={
                    "required": list(required_types),
                    "uploaded": list(uploaded_types.keys()),
                    "missing": list(missing_types),
                },
            ))

            return DocumentValidationResult(
                is_valid=False,
                issues=issues,
                error_message=error_msg,
            ), checks

        # ── All checks passed ───────────────────────────────────────────
        for doc in claim.documents:
            quality = doc.quality or "GOOD"
            validated_docs.append(ValidatedDocument(
                file_id=doc.file_id,
                detected_type=doc.actual_type.upper(),
                quality=quality,
                quality_score=1.0 if quality == "GOOD" else 0.7,
            ))

        checks.append(CheckResult(
            check_name="document_type_validation",
            status="PASS",
            message=(
                f"All required documents present for {claim.claim_category.value.title()} claim: "
                f"{', '.join(t.replace('_', ' ').title() for t in required_types)}."
            ),
            details={
                "required": list(required_types),
                "uploaded": list(uploaded_types.keys()),
                "validated_count": len(validated_docs),
            },
        ))

        return DocumentValidationResult(
            is_valid=True,
            validated_documents=validated_docs,
        ), checks
