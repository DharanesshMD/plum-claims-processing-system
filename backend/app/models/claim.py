"""Claim data models — core contracts for the entire system."""

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class Decision(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ClaimHistoryEntry(BaseModel):
    claim_id: str
    date: str
    amount: float
    provider: Optional[str] = None


class DocumentInput(BaseModel):
    """A document submitted with a claim."""

    file_id: str
    file_name: Optional[str] = None
    actual_type: str
    quality: Optional[str] = None
    content: Optional[dict] = None
    patient_name_on_doc: Optional[str] = None


class ClaimInput(BaseModel):
    """Input for a new claim submission."""

    member_id: str
    policy_id: str = "PLUM_GHI_2024"
    claim_category: ClaimCategory
    treatment_date: date
    claimed_amount: float
    hospital_name: Optional[str] = None
    ytd_claims_amount: float = 0.0
    claims_history: list[ClaimHistoryEntry] = Field(default_factory=list)
    documents: list[DocumentInput] = Field(default_factory=list)
    simulate_component_failure: bool = False


class LineItem(BaseModel):
    """A line item from a bill."""

    description: str
    amount: float


class LineItemDecision(BaseModel):
    """Decision for an individual line item."""

    description: str
    amount: float
    status: Literal["APPROVED", "REJECTED"]
    reason: Optional[str] = None


class AmountBreakdown(BaseModel):
    """Detailed breakdown of how the approved amount was calculated."""

    claimed_amount: float
    network_discount_percent: float = 0.0
    network_discount_amount: float = 0.0
    amount_after_discount: float = 0.0
    copay_percent: float = 0.0
    copay_amount: float = 0.0
    amount_after_copay: float = 0.0
    sub_limit: Optional[float] = None
    sub_limit_applied: bool = False
    per_claim_limit: Optional[float] = None
    per_claim_limit_applied: bool = False
    annual_limit_remaining: Optional[float] = None
    annual_limit_applied: bool = False
    approved_amount: float = 0.0
    calculation_steps: list[str] = Field(default_factory=list)


class ClaimDecision(BaseModel):
    """The final decision for a claim, with full traceability."""

    claim_id: str
    decision: Optional[Decision] = None
    approved_amount: Optional[float] = None
    rejection_reasons: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    explanation: str = ""
    line_item_decisions: list[LineItemDecision] = Field(default_factory=list)
    amount_breakdown: Optional[AmountBreakdown] = None
    trace: Optional["FullTrace"] = None
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClaimSummary(BaseModel):
    """Lightweight claim summary for listing."""

    claim_id: str
    member_id: str
    claim_category: ClaimCategory
    claimed_amount: float
    decision: Optional[Decision] = None
    approved_amount: Optional[float] = None
    confidence_score: float = 0.0
    created_at: datetime


from app.models.trace import FullTrace  # noqa: E402

ClaimDecision.model_rebuild()
