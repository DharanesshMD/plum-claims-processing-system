"use client";

import { useEffect, useState } from "react";
import { listClaims } from "@/lib/api";
import type { ClaimSummary } from "@/lib/types";

function DecisionBadge({ decision }: { decision: string | null }) {
  const config: Record<string, { class: string; label: string }> = {
    APPROVED: { class: "badge-approved", label: "Approved" },
    PARTIAL: { class: "badge-partial", label: "Partial" },
    REJECTED: { class: "badge-rejected", label: "Rejected" },
    MANUAL_REVIEW: { class: "badge-manual-review", label: "Manual Review" },
  };
  const c = decision ? config[decision] : { class: "badge-stopped", label: "Stopped Early" };
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${c.class}`}>
      {c.label}
    </span>
  );
}

export default function DashboardPage() {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listClaims()
      .then(setClaims)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const stats = {
    total: claims.length,
    approved: claims.filter((c) => c.decision === "APPROVED").length,
    rejected: claims.filter((c) => c.decision === "REJECTED").length,
    partial: claims.filter((c) => c.decision === "PARTIAL").length,
    review: claims.filter((c) => c.decision === "MANUAL_REVIEW").length,
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Claims Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            AI-powered multi-agent claims processing with full observability
          </p>
        </div>
        <a
          href="/claims/new"
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:shadow-violet-500/40 hover:brightness-110"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Claim
        </a>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        {[
          { label: "Total Claims", value: stats.total, color: "text-white" },
          { label: "Approved", value: stats.approved, color: "text-emerald-400" },
          { label: "Rejected", value: stats.rejected, color: "text-rose-400" },
          { label: "Partial", value: stats.partial, color: "text-amber-400" },
          { label: "Manual Review", value: stats.review, color: "text-blue-400" },
        ].map((s) => (
          <div key={s.label} className="glass-card p-5">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{s.label}</p>
            <p className={`mt-1 text-3xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="glass-card p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Quick Actions</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <a href="/claims/new" className="group flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.02] p-4 transition hover:border-violet-500/30 hover:bg-violet-500/5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-500/10 text-violet-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Submit New Claim</p>
              <p className="text-xs text-slate-400">Process a claim through the multi-agent pipeline</p>
            </div>
          </a>
          <a href="/eval" className="group flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.02] p-4 transition hover:border-emerald-500/30 hover:bg-emerald-500/5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Run Evaluation</p>
              <p className="text-xs text-slate-400">Execute all 12 test cases and view results</p>
            </div>
          </a>
          <div className="flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.02] p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10 text-blue-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5m.75-9 3-3 2.148 2.148A12.061 12.061 0 0 1 16.5 7.605" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-white">System Status</p>
              <p className="text-xs text-slate-400">Pipeline healthy — 5 agents active</p>
            </div>
          </div>
        </div>
      </div>

      {/* Claims Table */}
      {claims.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="border-b border-white/5 px-6 py-4">
            <h2 className="text-lg font-semibold text-white">Recent Claims</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Claim ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Member</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Category</th>
                  <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">Claimed</th>
                  <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">Approved</th>
                  <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-slate-500">Decision</th>
                  <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {claims.map((claim) => (
                  <tr key={claim.claim_id} className="transition hover:bg-white/[0.02]">
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-mono text-violet-400">
                      <a href={`/claims/${claim.claim_id}`} className="hover:underline">
                        {claim.claim_id}
                      </a>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-slate-300">{claim.member_id}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-slate-300">{claim.claim_category}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-slate-300">
                      ₹{claim.claimed_amount?.toLocaleString()}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm font-semibold text-emerald-400">
                      {claim.approved_amount != null ? `₹${claim.approved_amount.toLocaleString()}` : "—"}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-center">
                      <DecisionBadge decision={claim.decision} />
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-slate-400">
                      {(claim.confidence_score * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && claims.length === 0 && (
        <div className="glass-card flex flex-col items-center justify-center py-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-500/10">
            <svg className="h-8 w-8 text-violet-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
          </div>
          <h3 className="mt-4 text-lg font-semibold text-white">No claims yet</h3>
          <p className="mt-1 text-sm text-slate-400">Submit a claim or run the evaluation suite to get started.</p>
          <div className="mt-6 flex gap-3">
            <a href="/claims/new" className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-violet-500">
              Submit Claim
            </a>
            <a href="/eval" className="rounded-lg border border-white/10 px-4 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/5">
              Run Evaluation
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
