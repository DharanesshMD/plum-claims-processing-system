"use client";

import { useState, useEffect } from "react";

const PRESETS = [
  { case_id: "TC001", case_name: "Wrong Document Uploaded" },
  { case_id: "TC002", case_name: "Unreadable Document" },
  { case_id: "TC003", case_name: "Documents Belong to Different Patients" },
  { case_id: "TC004", case_name: "Clean Consultation — Full Approval" },
  { case_id: "TC005", case_name: "Waiting Period — Diabetes" },
  { case_id: "TC006", case_name: "Dental Partial Approval — Cosmetic Exclusion" },
  { case_id: "TC007", case_name: "MRI Without Pre-Authorization" },
  { case_id: "TC008", case_name: "Per-Claim Limit Exceeded" },
  { case_id: "TC009", case_name: "Fraud Signal — Multiple Same-Day Claims" },
  { case_id: "TC010", case_name: "Network Hospital — Discount Applied" },
  { case_id: "TC011", case_name: "Component Failure — Graceful Degradation" },
  { case_id: "TC012", case_name: "Excluded Treatment" }
];

interface TestCaseResult {
  case_id: string;
  case_name: string;
  status: "PENDING" | "RUNNING" | "PASS" | "FAIL" | "ERROR";
  expected_decision?: string | null;
  actual_decision?: string | null;
  expected_amount?: number | null;
  actual_amount?: number | null;
  confidence_score?: number;
  explanation?: string;
  checks?: Array<{ passed: boolean; check: string; expected?: any; actual?: any }>;
  full_decision?: any;
  error?: string;
}

function RunningProgressBar({ active }: { active: boolean }) {
  const [progress, setProgress] = useState(10);

  useEffect(() => {
    if (!active) {
      setProgress(10);
      return;
    }
    const interval = setInterval(() => {
      setProgress(p => {
        if (p >= 90) return p;
        const step = p < 50 ? 8 : p < 75 ? 4 : 2;
        return p + step;
      });
    }, 300);
    return () => clearInterval(interval);
  }, [active]);

  if (!active) return null;

  return (
    <div className="mt-2 w-full max-w-md">
      <div className="flex justify-between text-[10px] text-slate-400 mb-1">
        <span>Running Agent Pipeline...</span>
        <span>{progress}%</span>
      </div>
      <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 rounded-full transition-all duration-300 animate-pulse"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

export default function EvalPage() {
  const [results, setResults] = useState<TestCaseResult[]>(
    PRESETS.map(p => ({ ...p, status: "PENDING", thinking: "" }))
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expandedCase, setExpandedCase] = useState<string | null>(null);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiBase}/api/claims/eval/cases`)
      .then(res => {
        if (!res.ok) throw new Error("Failed to fetch cases");
        return res.json();
      })
      .then(data => {
        setResults(data.map((tc: any) => ({
          case_id: tc.case_id,
          case_name: tc.case_name,
          status: "PENDING",
          expected_decision: tc.expected?.decision,
          expected_amount: tc.expected?.approved_amount,
          description: tc.description,
          input: tc.input,
          thinking: "",
        })));
      })
      .catch(err => {
        console.error("Failed to fetch test cases from API:", err);
      });
  }, []);

  const total = results.length;
  const passed = results.filter(r => r.status === "PASS").length;
  const failed = results.filter(r => r.status === "FAIL" || r.status === "ERROR").length;
  const completed = results.filter(r => r.status !== "PENDING" && r.status !== "RUNNING").length;
  const passRatePercent = completed > 0 ? (passed / completed) * 100 : 0;
  const passRateStr = completed > 0 ? `${passed}/${completed} (${passRatePercent.toFixed(0)}%)` : "0/0 (0%)";
  const overallProgressPercent = total > 0 ? (completed / total) * 100 : 0;

  async function handleRunEval() {
    setLoading(true);
    setStarted(true);
    setError("");
    setResults(prev => {
      const copy = prev.map((p, idx) => ({
        ...p,
        status: idx === 0 ? ("RUNNING" as const) : ("PENDING" as const),
        thinking: "",
        actual_decision: undefined,
        actual_amount: undefined,
        confidence_score: undefined,
        explanation: undefined,
        checks: undefined,
        full_decision: undefined,
        error: undefined,
      }));
      return copy;
    });
    if (results.length > 0) {
      setExpandedCase(results[0].case_id);
    }

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiBase}/api/claims/eval`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());

      const reader = res.body?.getReader();
      if (!reader) throw new Error("ReadableStream not supported");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.trim().startsWith("data: ")) {
            const dataStr = line.replace("data: ", "").trim();
            try {
              const payload = JSON.parse(dataStr);

              if (payload.type === "thinking_start") {
                const idx = payload.index;
                setResults(prev => {
                  const copy = [...prev];
                  copy[idx] = {
                    ...copy[idx],
                    status: "RUNNING",
                    thinking: "",
                  };
                  return copy;
                });
                setExpandedCase(payload.case_id);
              } else if (payload.type === "thinking_delta") {
                const idx = payload.index;
                const text = payload.text;
                setResults(prev => {
                  const copy = [...prev];
                  copy[idx] = {
                    ...copy[idx],
                    status: "RUNNING",
                    thinking: (copy[idx].thinking || "") + text,
                  };
                  return copy;
                });
              } else if (payload.type === "thinking_end") {
                // Done thinking
              } else if (payload.type === "result") {
                const idx = payload.index;
                setResults(prev => {
                  const copy = [...prev];
                  copy[idx] = {
                    ...copy[idx],
                    status: payload.status,
                    expected_decision: payload.expected_decision,
                    actual_decision: payload.actual_decision,
                    expected_amount: payload.expected_amount,
                    actual_amount: payload.actual_amount,
                    confidence_score: payload.confidence_score,
                    explanation: payload.explanation,
                    checks: payload.checks,
                    full_decision: payload.full_decision,
                    error: payload.error
                  };

                  const nextIdx = idx + 1;
                  if (nextIdx < copy.length && copy[nextIdx].status === "PENDING") {
                    copy[nextIdx].status = "RUNNING";
                  }
                  return copy;
                });
              }
            } catch (jsonErr) {
              console.error("Failed to parse event JSON:", jsonErr);
            }
          }
        }
      }

      setResults(prev => prev.map(r => r.status === "RUNNING" || r.status === "PENDING" ? { ...r, status: "ERROR", error: "Stream terminated" } : r));

    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Evaluation Report</h1>
          <p className="mt-1 text-sm text-slate-400">Run all 12 test cases to verify the claims pipeline</p>
        </div>
        <button
          onClick={handleRunEval}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-500/25 transition hover:shadow-emerald-500/40 hover:brightness-110 disabled:opacity-50"
        >
          {loading ? (
            <>
              <svg className="h-4 w-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Running {completed}/{total}...
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
              </svg>
              Run Evaluation Suite
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="glass-card border-rose-500/30 bg-rose-500/5 p-4">
          <p className="text-sm text-rose-400">{error}</p>
        </div>
      )}

      {started && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className="glass-card p-5 text-center">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Total Tests</p>
              <p className="mt-1 text-4xl font-bold text-white">{total}</p>
            </div>
            <div className="glass-card p-5 text-center">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Passed</p>
              <p className="mt-1 text-4xl font-bold text-emerald-400">{passed}</p>
            </div>
            <div className="glass-card p-5 text-center">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Failed</p>
              <p className="mt-1 text-4xl font-bold text-rose-400">{failed}</p>
            </div>
            <div className="glass-card p-5 text-center">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Pass Rate</p>
              <p className="mt-1 text-4xl font-bold text-violet-400">{passRateStr}</p>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="glass-card p-4">
            <div className="flex items-center gap-3">
              <div className="flex-1 h-3 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-500"
                  style={{ width: `${overallProgressPercent}%` }}
                />
              </div>
              <span className="text-sm font-bold text-white">{completed}/{total}</span>
            </div>
          </div>

          {/* Test Results */}
          <div className="space-y-3">
            {results.map((tc) => (
              <div
                key={tc.case_id}
                className={`glass-card overflow-hidden transition-all duration-300 ${
                  tc.status === "RUNNING" ? "ring-2 ring-emerald-500/50 bg-emerald-500/[0.02]" : ""
                }`}
              >
                <button
                  onClick={() => setExpandedCase(expandedCase === tc.case_id ? null : tc.case_id)}
                  disabled={tc.status === "PENDING"}
                  className={`flex w-full items-center justify-between px-6 py-4 text-left transition ${
                    tc.status === "PENDING" ? "cursor-not-allowed opacity-60" : "hover:bg-white/[0.02]"
                  }`}
                >
                  <div className="flex items-center gap-4 flex-1">
                    <div className={`flex h-9 w-9 items-center justify-center rounded-xl text-sm font-bold
                      ${tc.status === "PASS" ? "bg-emerald-500/10 text-emerald-400" :
                        tc.status === "FAIL" || tc.status === "ERROR" ? "bg-rose-500/10 text-rose-400" :
                        tc.status === "RUNNING" ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-800 text-slate-500"}`}>
                      {tc.status === "PASS" ? "✓" :
                       tc.status === "FAIL" || tc.status === "ERROR" ? "✗" :
                       tc.status === "RUNNING" ? (
                         <svg className="h-4 w-4 animate-spin text-emerald-400" fill="none" viewBox="0 0 24 24">
                           <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                           <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                         </svg>
                       ) : "•"}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono text-slate-400">{tc.case_id}</span>
                        <span className="text-sm font-semibold text-white">{tc.case_name}</span>
                        {tc.status === "RUNNING" && (
                          <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium text-emerald-400 animate-pulse">
                            Processing
                          </span>
                        )}
                        {tc.status === "PENDING" && (
                          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                            Queued
                          </span>
                        )}
                      </div>
                      <RunningProgressBar active={tc.status === "RUNNING"} />
                      {tc.explanation && (
                        <p className="mt-0.5 text-xs text-slate-500 line-clamp-1">{tc.explanation}</p>
                      )}
                      {tc.error && (
                        <p className="mt-0.5 text-xs text-rose-400">{tc.error}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {tc.expected_decision && (
                      <div className="text-right">
                        <p className="text-xs text-slate-500">Expected</p>
                        <p className="text-xs font-mono text-slate-400">{tc.expected_decision} {tc.expected_amount != null && `/ ₹${tc.expected_amount.toLocaleString()}`}</p>
                      </div>
                    )}
                    <div className="text-right">
                      <p className="text-xs text-slate-500">Actual</p>
                      <p className="text-xs font-mono text-slate-300">{tc.actual_decision || "—"} {tc.actual_amount != null && `/ ₹${tc.actual_amount.toLocaleString()}`}</p>
                    </div>
                    {tc.status !== "PENDING" && (
                      <svg className={`h-4 w-4 text-slate-500 transition ${expandedCase === tc.case_id ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                      </svg>
                    )}
                  </div>
                </button>

                {expandedCase === tc.case_id && (
                  <div className="border-t border-white/5 px-6 py-5 space-y-5 bg-white/[0.01]">
                    {/* Grid for Specification and Reasoning */}
                    <div className="grid gap-6 md:grid-cols-2">
                      {/* Left: Test Case Specification */}
                      <div className="space-y-3">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Test Case Specification</h4>
                        <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 space-y-3">
                          {tc.description && (
                            <div>
                              <p className="text-[10px] uppercase font-bold text-slate-500">Description</p>
                              <p className="text-xs text-slate-300 mt-0.5">{tc.description}</p>
                            </div>
                          )}
                          {tc.input && (
                            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/5">
                              <div>
                                <p className="text-[10px] uppercase font-bold text-slate-500">Category</p>
                                <p className="text-xs text-slate-300 font-medium">{tc.input.claim_category}</p>
                              </div>
                              <div>
                                <p className="text-[10px] uppercase font-bold text-slate-500">Claimed Amount</p>
                                <p className="text-xs text-slate-300 font-semibold">₹{tc.input.claimed_amount?.toLocaleString()}</p>
                              </div>
                            </div>
                          )}
                          {tc.input?.documents && (
                            <div className="pt-2 border-t border-white/5">
                              <p className="text-[10px] uppercase font-bold text-slate-500 mb-1">Submitted Documents</p>
                              <div className="space-y-1">
                                {tc.input.documents.map((doc: any, idx: number) => (
                                  <div key={idx} className="flex items-center justify-between text-xs py-1 px-2 rounded bg-white/5">
                                    <span className="text-slate-300 font-mono truncate max-w-[180px]">{doc.file_name || `Doc ${doc.file_id}`}</span>
                                    <span className="text-[10px] font-semibold text-slate-500 uppercase">{doc.actual_type}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Right: Model Reasoning */}
                      <div className="space-y-3">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-2">
                          Model Reasoning
                          {tc.status === "RUNNING" && !tc.explanation && (
                            <span className="flex h-2 w-2 relative">
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                            </span>
                          )}
                        </h4>
                        <div className="rounded-xl border border-teal-500/20 bg-teal-500/[0.02] p-4 min-h-[140px] flex flex-col justify-between">
                          <p className="text-xs text-teal-100/90 whitespace-pre-wrap leading-relaxed">
                            {tc.thinking || "Waiting for LLM analysis..."}
                            {tc.status === "RUNNING" && !tc.explanation && (
                              <span className="inline-block w-1.5 h-3.5 ml-1 bg-teal-400 animate-pulse" />
                            )}
                          </p>
                          {tc.status === "RUNNING" && (
                            <p className="text-[10px] text-teal-400/60 mt-3 border-t border-teal-500/10 pt-2 animate-pulse">
                              Streaming model thoughts live...
                            </p>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Bottom row: Checks & Pipeline */}
                    <div className="grid gap-6 md:grid-cols-2 pt-2">
                      {/* Verification Checks */}
                      {tc.checks && tc.checks.length > 0 && (
                        <div className="space-y-3">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Verification Checks</h4>
                          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 space-y-1.5 font-mono">
                            {tc.checks.map((check, i) => (
                              <div key={i} className="flex items-start gap-2 text-xs">
                                <span className={check.passed ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                                  {check.passed ? "✓" : "✗"}
                                </span>
                                <div className="flex-1">
                                  <span className="text-slate-300 font-medium">{check.check.replace(/_/g, " ")}</span>
                                  {check.expected !== undefined && !check.passed && (
                                    <p className="text-[10px] text-slate-500 mt-0.5">
                                      Expected: <span>{JSON.stringify(check.expected)}</span>, got: <span className="text-rose-400">{JSON.stringify(check.actual)}</span>
                                    </p>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Trace */}
                      {tc.full_decision?.trace && (
                        <div className="space-y-3">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Agent Pipeline</h4>
                          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 space-y-3">
                            <div className="flex flex-wrap gap-2">
                              {tc.full_decision.trace.agent_traces.map((agent: any, i: number) => (
                                <div key={i}
                                  className={`rounded-lg px-2.5 py-1 text-[10px] font-medium border
                                    ${agent.status === "SUCCESS" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                                      agent.status === "FAILED" ? "bg-rose-500/10 text-rose-400 border-rose-500/20" :
                                      "bg-amber-500/10 text-amber-400 border-amber-500/20"}`}>
                                  {agent.agent_name}
                                </div>
                              ))}
                            </div>
                            {tc.explanation && (
                              <div className="border-t border-white/5 pt-2">
                                <p className="text-[10px] uppercase font-bold text-slate-500">Pipeline Explanation</p>
                                <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">{tc.explanation}</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Initial State */}
      {!started && (
        <div className="glass-card flex flex-col items-center justify-center py-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10">
            <svg className="h-8 w-8 text-emerald-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <h3 className="mt-4 text-lg font-semibold text-white">Ready to Evaluate</h3>
          <p className="mt-1 max-w-md text-center text-sm text-slate-400">
            Click &quot;Run Evaluation Suite&quot; to process all 12 test cases through the pipeline
            and verify correct decisions, amounts, and rejection reasons.
          </p>
        </div>
      )}
    </div>
  );
}
