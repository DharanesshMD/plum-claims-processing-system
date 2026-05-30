"use client";

import { useEffect, useState, use } from "react";
import { getClaim } from "@/lib/api";
import type { ClaimDecision } from "@/lib/types";

export default function ClaimDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const [claim, setClaim] = useState<ClaimDecision | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getClaim(resolvedParams.id)
      .then(setClaim)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [resolvedParams.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <svg className="h-8 w-8 animate-spin text-violet-400" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card border-rose-500/30 bg-rose-500/5 p-6">
        <h2 className="text-lg font-semibold text-rose-400">Error</h2>
        <p className="mt-2 text-sm text-slate-400">{error}</p>
        <a href="/" className="mt-4 inline-block text-sm text-violet-400 hover:underline">← Back to Dashboard</a>
      </div>
    );
  }

  if (!claim) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <a href="/" className="text-slate-400 hover:text-white">←</a>
        <h1 className="text-2xl font-bold text-white">{claim.claim_id}</h1>
        <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold
          ${claim.decision === "APPROVED" ? "badge-approved" :
            claim.decision === "PARTIAL" ? "badge-partial" :
            claim.decision === "REJECTED" ? "badge-rejected" :
            claim.decision === "MANUAL_REVIEW" ? "badge-manual-review" : "badge-stopped"}`}>
          {claim.decision || "STOPPED EARLY"}
        </span>
      </div>

      {/* Decision Summary */}
      <div className="glass-card p-6">
        <div className="grid gap-6 md:grid-cols-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Approved Amount</p>
            <p className="mt-1 text-3xl font-bold text-emerald-400">
              {claim.approved_amount != null ? `₹${claim.approved_amount.toLocaleString()}` : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Confidence</p>
            <p className="mt-1 text-3xl font-bold text-violet-400">{(claim.confidence_score * 100).toFixed(0)}%</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Created</p>
            <p className="mt-1 text-sm text-slate-300">{new Date(claim.created_at).toLocaleString()}</p>
          </div>
        </div>
        <div className="mt-4 border-t border-white/5 pt-4">
          <p className="text-sm text-slate-300">{claim.explanation}</p>
        </div>
      </div>

      {/* Rejection Reasons */}
      {claim.rejection_reasons.length > 0 && (
        <div className="glass-card border-rose-500/20 p-6">
          <h3 className="text-sm font-semibold text-rose-400">Rejection Reasons</h3>
          <ul className="mt-2 space-y-1">
            {claim.rejection_reasons.map((r, i) => (
              <li key={i} className="text-sm text-slate-300">• {r.replace(/_/g, " ")}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Amount Breakdown */}
      {claim.amount_breakdown && (
        <div className="glass-card p-6">
          <h3 className="mb-4 text-sm font-semibold text-white">Calculation Steps</h3>
          <div className="space-y-3">
            {claim.amount_breakdown.calculation_steps.map((step, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-500/10 text-xs font-bold text-violet-400">
                  {i + 1}
                </div>
                <span className="text-sm text-slate-300">{step}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Full Trace */}
      {claim.trace && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">Full Pipeline Trace</h3>
            <span className="text-xs text-slate-500">
              Status: <span className="text-slate-300">{claim.trace.overall_status}</span>
            </span>
          </div>
          <div className="space-y-6">
            {claim.trace.agent_traces.map((agent, i) => (
              <div key={i} className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${
                      agent.status === "SUCCESS" ? "bg-emerald-400" :
                      agent.status === "FAILED" ? "bg-rose-400" : "bg-amber-400"
                    }`} />
                    <span className="text-sm font-semibold text-white">{agent.agent_name}</span>
                  </div>
                  <span className={`text-xs font-medium
                    ${agent.status === "SUCCESS" ? "text-emerald-400" :
                      agent.status === "FAILED" ? "text-rose-400" : "text-amber-400"}`}>
                    {agent.status}
                  </span>
                </div>
                {agent.error && (
                  <p className="mt-2 text-xs text-rose-400 bg-rose-500/5 rounded px-2 py-1">Error: {agent.error}</p>
                )}
                <div className="mt-3 space-y-1.5">
                  {agent.checks_performed.map((check, j) => (
                    <div key={j} className="flex items-start gap-2">
                      <span className={`mt-0.5 text-xs ${
                        check.status === "PASS" || check.status === "SUCCESS" ? "text-emerald-400" :
                        check.status === "FAIL" ? "text-rose-400" :
                        check.status === "WARNING" ? "text-amber-400" : "text-slate-500"
                      }`}>
                        {check.status === "PASS" || check.status === "SUCCESS" ? "✓" :
                         check.status === "FAIL" ? "✗" :
                         check.status === "WARNING" ? "⚠" : "○"}
                      </span>
                      <div>
                        <span className="text-xs font-medium text-slate-400">[{check.check_name}]</span>
                        <span className="ml-1 text-xs text-slate-500">{check.message}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
