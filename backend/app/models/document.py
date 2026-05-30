"""Document-related models for validation and extraction."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DocumentIssue(BaseModel):
    """A specific issue found during document validation."""

    issue_type: Literal[
        "WRONG_DOCUMENT_TYPE",
        "MISSING_REQUIRED_DOCUMENT",
        "UNREADABLE_DOCUMENT",
        "DUPLICATE_DOCUMENT",
        "QUALITY_WARNING",
    ]
    severity: Literal["ERROR", "WARNING"]
    message: str
    file_id: Optional[str] = None
    uploaded_type: Optional[str] = None
    required_type: Optional[str] = None


class ValidatedDocument(BaseModel):
    """A document that has passed validation."""

    file_id: str
    detected_type: str
    quality: str = "GOOD"
    quality_score: float = 1.0


class DocumentValidationResult(BaseModel):
    """Result of validating all documents for a claim."""

    is_valid: bool
    issues: list[DocumentIssue] = Field(default_factory=list)
    validated_documents: list[ValidatedDocument] = Field(default_factory=list)
    error_message: Optional[str] = None


class ExtractedLineItem(BaseModel):
    """An extracted line item from a bill."""

    description: str
    amount: float


class ExtractedDocument(BaseModel):
    """Structured data extracted from a document."""

    file_id: str
    document_type: str
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    doctor_registration: Optional[str] = None
    hospital_name: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    document_date: Optional[date] = None
    medicines: list[str] = Field(default_factory=list)
    tests_ordered: list[str] = Field(default_factory=list)
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    total_amount: Optional[float] = None
    confidence: float = 1.0
    field_confidences: dict[str, float] = Field(default_factory=dict)


class CrossDocMismatch(BaseModel):
    """A specific mismatch found between documents."""

    mismatch_type: Literal["PATIENT_NAME", "DATE", "AMOUNT", "PROVIDER"]
    description: str
    values_found: dict[str, str] = Field(default_factory=dict)


class CrossVerificationResult(BaseModel):
    """Result of cross-document verification."""

    is_consistent: bool
    mismatches: list[CrossDocMismatch] = Field(default_factory=list)
    error_message: Optional[str] = None
