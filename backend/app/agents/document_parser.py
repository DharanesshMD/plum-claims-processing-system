"""Agent 2: Document Parser — Extracts structured data from documents.

For test cases with pre-structured content dicts, parses directly.
For real images/PDFs, would use Gemini vision (deferred to LLM service).
"""


from datetime import date, datetime

from app.models.claim import ClaimInput, DocumentInput
from app.models.document import ExtractedDocument, ExtractedLineItem
from app.models.trace import CheckResult
from app.services.llm_service import extract_document


class DocumentParser:
    """Extracts structured data from documents."""

    def parse(
        self,
        claim: ClaimInput,
    ) -> tuple[list[ExtractedDocument], list[CheckResult]]:
        """
        Parse all validated documents and extract structured data.
        Returns (list of extracted docs, checks for trace).
        """
        checks: list[CheckResult] = []
        extracted: list[ExtractedDocument] = []

        for doc_input in claim.documents:
            if doc_input.content:
                # Test case path: structured content already provided
                parsed = self._parse_structured_content(doc_input)
                extracted.append(parsed)
                checks.append(CheckResult(
                    check_name=f"parse_{doc_input.file_id}",
                    status="SUCCESS",
                    message=f"Extracted structured data from {doc_input.actual_type} ({doc_input.file_id}).",
                    details={
                        "document_type": doc_input.actual_type,
                        "patient_name": parsed.patient_name,
                        "fields_extracted": len([
                            f for f in [
                                parsed.patient_name, parsed.doctor_name, parsed.diagnosis,
                                parsed.hospital_name, parsed.total_amount,
                            ] if f is not None
                        ]),
                    },
                ))
            else:
                # Real document path: use configured LLM SDK extraction
                parsed = extract_document(
                    file_id=doc_input.file_id,
                    document_type=doc_input.actual_type,
                    file_name=doc_input.file_name,
                    patient_name_on_doc=doc_input.patient_name_on_doc,
                )
                extracted.append(parsed)

                from app.config import get_settings
                settings = get_settings()
                provider_key = (settings.llm_provider or "cursor").lower()

                # Detect vision extraction (confidence 0.95 = vision model was used)
                if parsed.confidence >= 0.95:
                    provider_name = "Vision AI (NVIDIA NIM)" if settings.nvidia_api_key else "Vision AI (Gemini)"
                else:
                    provider_names = {
                        "antigravity": "Google Antigravity SDK",
                        "nvidia": "NVIDIA NIM",
                        "cursor": "Cursor SDK"
                    }
                    provider_name = provider_names.get(provider_key, "Cursor SDK")

                status = "SUCCESS" if parsed.confidence > 0.5 else "DEGRADED"
                msg_suffix = f"using {provider_name}." if parsed.confidence > 0.5 else f"using fallback ({provider_name} failed/not configured)."

                checks.append(CheckResult(
                    check_name=f"parse_{doc_input.file_id}",
                    status=status,
                    message=f"Extracted data from {doc_input.actual_type} ({doc_input.file_id}) {msg_suffix}",
                    details={
                        "document_type": doc_input.actual_type,
                        "patient_name": parsed.patient_name,
                        "confidence": parsed.confidence,
                    },
                ))

        return extracted, checks

    def _parse_structured_content(self, doc: DocumentInput) -> ExtractedDocument:
        """Parse a test case document with pre-structured content."""
        content = doc.content or {}

        # Parse line items
        line_items = []
        for item in content.get("line_items", []):
            line_items.append(ExtractedLineItem(
                description=item.get("description", ""),
                amount=item.get("amount", 0),
            ))

        # Parse date
        doc_date = None
        if "date" in content:
            try:
                doc_date = datetime.strptime(content["date"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        # Parse tests ordered
        tests_ordered = content.get("tests_ordered", [])

        return ExtractedDocument(
            file_id=doc.file_id,
            document_type=doc.actual_type,
            patient_name=content.get("patient_name") or doc.patient_name_on_doc,
            doctor_name=content.get("doctor_name"),
            doctor_registration=content.get("doctor_registration"),
            hospital_name=content.get("hospital_name"),
            diagnosis=content.get("diagnosis"),
            treatment=content.get("treatment"),
            document_date=doc_date,
            medicines=content.get("medicines", []),
            tests_ordered=tests_ordered,
            line_items=line_items,
            total_amount=content.get("total"),
            confidence=1.0,  # Structured content = high confidence
        )
