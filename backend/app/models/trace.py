"""Trace models for full decision observability."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    """Result of a single check performed by an agent."""

    check_name: str
    status: Literal["PASS", "FAIL", "WARNING", "SKIPPED", "SUCCESS"]
    message: str
    details: Optional[dict] = None


class TraceEntry(BaseModel):
    """Trace of a single agent's execution."""

    agent_name: str
    started_at: datetime
    completed_at: datetime
    status: Literal["SUCCESS", "FAILED", "DEGRADED", "SKIPPED"]
    input_summary: dict = Field(default_factory=dict)
    output_summary: dict = Field(default_factory=dict)
    checks_performed: list[CheckResult] = Field(default_factory=list)
    confidence_impact: float = 0.0
    error: Optional[str] = None


class FullTrace(BaseModel):
    """Full trace of the entire claim processing pipeline."""

    claim_id: str
    pipeline_started_at: datetime
    pipeline_completed_at: Optional[datetime] = None
    agent_traces: list[TraceEntry] = Field(default_factory=list)
    overall_status: str = "PENDING"
    confidence_breakdown: dict[str, float] = Field(default_factory=dict)
