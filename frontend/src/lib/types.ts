export interface CheckResult {
  check_name: string;
  status: "PASS" | "FAIL" | "WARNING" | "SKIPPED" | "SUCCESS";
  message: string;
  details?: Record<string, unknown>;
}

export interface TraceEntry {
  agent_name: string;
  started_at: string;
  completed_at: string;
  status: "SUCCESS" | "FAILED" | "DEGRADED" | "SKIPPED";
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  checks_performed: CheckResult[];
  confidence_impact: number;
  error?: string;
}

export interface FullTrace {
  claim_id: string;
  pipeline_started_at: string;
  pipeline_completed_at: string;
  agent_traces: TraceEntry[];
  overall_status: string;
  confidence_breakdown: Record<string, number>;
}

export interface LineItemDecision {
  description: string;
  amount: number;
  status: "APPROVED" | "REJECTED";
  reason?: string;
}

export interface AmountBreakdown {
  claimed_amount: number;
  network_discount_percent: number;
  network_discount_amount: number;
  amount_after_discount: number;
  copay_percent: number;
  copay_amount: number;
  amount_after_copay: number;
  sub_limit?: number;
  sub_limit_applied: boolean;
  per_claim_limit?: number;
  per_claim_limit_applied: boolean;
  annual_limit_remaining?: number;
  annual_limit_applied: boolean;
  approved_amount: number;
  calculation_steps: string[];
}

export interface ClaimDecision {
  claim_id: string;
  decision: "APPROVED" | "PARTIAL" | "REJECTED" | "MANUAL_REVIEW" | null;
  approved_amount: number | null;
  rejection_reasons: string[];
  confidence_score: number;
  explanation: string;
  line_item_decisions: LineItemDecision[];
  amount_breakdown?: AmountBreakdown;
  trace?: FullTrace;
  warnings: string[];
  created_at: string;
}

export interface ClaimSummary {
  claim_id: string;
  member_id: string;
  claim_category: string;
  claimed_amount: number;
  decision: string | null;
  approved_amount: number | null;
  confidence_score: number;
  created_at: string;
}

export interface EvalResult {
  case_id: string;
  case_name: string;
  status: "PASS" | "FAIL" | "ERROR";
  expected_decision: string | null;
  actual_decision: string | null;
  expected_amount: number | null;
  actual_amount: number | null;
  confidence_score: number;
  explanation: string;
  checks: Array<{
    check: string;
    passed: boolean;
    expected?: unknown;
    actual?: unknown;
    message?: string;
  }>;
  full_decision?: ClaimDecision;
  error?: string;
}

export interface EvalReport {
  summary: {
    total: number;
    passed: number;
    failed: number;
    pass_rate: string;
  };
  results: EvalResult[];
}
