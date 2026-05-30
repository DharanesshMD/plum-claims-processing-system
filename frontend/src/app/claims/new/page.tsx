"use client";

import { useCallback, useRef, useState } from "react";
import { submitClaim, submitClaimStream } from "@/lib/api";
import type { ClaimDecision } from "@/lib/types";

const CATEGORIES = [
  { value: "CONSULTATION", label: "Consultation" },
  { value: "DIAGNOSTIC", label: "Diagnostic" },
  { value: "PHARMACY", label: "Pharmacy" },
  { value: "DENTAL", label: "Dental" },
  { value: "VISION", label: "Vision" },
  { value: "ALTERNATIVE_MEDICINE", label: "Alternative Medicine" },
];

const DOC_TYPES = [
  "PRESCRIPTION",
  "HOSPITAL_BILL",
  "LAB_REPORT",
  "DISCHARGE_SUMMARY",
  "PHARMACY_BILL",
];

const MEMBERS = [
  { id: "EMP001", name: "Rajesh Kumar" },
  { id: "EMP002", name: "Priya Singh" },
  { id: "EMP003", name: "Amit Verma" },
  { id: "EMP004", name: "Sneha Reddy" },
  { id: "EMP005", name: "Vikram Joshi" },
  { id: "EMP006", name: "Kavita Nair" },
  { id: "EMP007", name: "Suresh Patil" },
  { id: "EMP008", name: "Ravi Menon" },
  { id: "EMP009", name: "Anita Desai" },
  { id: "EMP010", name: "Deepak Shah" },
];

const TEST_PRESETS = [
  { label: "TC004: Clean Approval", caseId: "TC004" },
  { label: "TC001: Wrong Document", caseId: "TC001" },
  { label: "TC005: Waiting Period", caseId: "TC005" },
  { label: "TC006: Dental Partial", caseId: "TC006" },
  { label: "TC009: Fraud Signal", caseId: "TC009" },
  { label: "TC010: Network Discount", caseId: "TC010" },
  { label: "TC011: Component Failure", caseId: "TC011" },
];

interface UploadedFile {
  fileId: string;
  fileName: string;
  contentType: string;
  docType: string;
  status: "uploading" | "done" | "error";
  errorMsg?: string;
}

export default function NewClaimPage() {
  const [memberId, setMemberId] = useState("EMP001");
  const [category, setCategory] = useState("CONSULTATION");
  const [treatmentDate, setTreatmentDate] = useState("2024-11-01");
  const [amount, setAmount] = useState("1500");
  const [hospitalName, setHospitalName] = useState("");
  const [ytdAmount, setYtdAmount] = useState("0");
  const [claimsHistoryJson, setClaimsHistoryJson] = useState("[]");
  const [simulateFailure, setSimulateFailure] = useState(false);
  const [result, setResult] = useState<ClaimDecision | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [thinkingText, setThinkingText] = useState("");
  const [isThinking, setIsThinking] = useState(false);

  // Upload state
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Test-case preset mode — when active, uses raw JSON documents instead of uploads
  const [usePreset, setUsePreset] = useState(false);
  const [presetDocsJson, setPresetDocsJson] = useState("[]");

  // ── Upload Logic ──────────────────────────────────────────────────────────

  const uploadFile = useCallback(async (file: File) => {
    const tempId = `uploading-${Date.now()}-${Math.random()}`;
    const newEntry: UploadedFile = {
      fileId: tempId,
      fileName: file.name,
      contentType: file.type,
      docType: "PRESCRIPTION",
      status: "uploading",
    };

    setUploadedFiles((prev) => [...prev, newEntry]);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("http://localhost:8000/api/documents/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errData.detail || "Upload failed");
      }

      const data = await res.json();

      setUploadedFiles((prev) =>
        prev.map((f) =>
          f.fileId === tempId
            ? { ...f, fileId: data.file_id, fileName: data.file_name, status: "done" }
            : f
        )
      );
    } catch (err) {
      setUploadedFiles((prev) =>
        prev.map((f) =>
          f.fileId === tempId
            ? { ...f, status: "error", errorMsg: err instanceof Error ? err.message : "Upload failed" }
            : f
        )
      );
    }
  }, []);

  const handleFilesSelected = useCallback(
    (files: FileList | null) => {
      if (!files) return;
      Array.from(files).forEach((f) => uploadFile(f));
    },
    [uploadFile]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDraggingOver(false);
      handleFilesSelected(e.dataTransfer.files);
    },
    [handleFilesSelected]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOver(true);
  };

  const handleDragLeave = () => setIsDraggingOver(false);

  const removeFile = (fileId: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.fileId !== fileId));
  };

  const updateDocType = (fileId: string, docType: string) => {
    setUploadedFiles((prev) =>
      prev.map((f) => (f.fileId === fileId ? { ...f, docType } : f))
    );
  };

  // ── Scroll Helper ─────────────────────────────────────────────────────────

  function scrollToBottom() {
    setTimeout(() => {
      window.scrollTo({
        top: document.documentElement.scrollHeight || document.body.scrollHeight,
        behavior: "smooth",
      });
    }, 100);
  }

  // ── Submit Handler ────────────────────────────────────────────────────────

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    setThinkingText("");
    setIsThinking(false);

    try {
      let documents: object[] = [];

      if (usePreset) {
        documents = JSON.parse(presetDocsJson);
      } else {
        const readyFiles = uploadedFiles.filter((f) => f.status === "done");
        if (readyFiles.length === 0) {
          setError("Please upload at least one document before submitting.");
          setLoading(false);
          return;
        }
        documents = readyFiles.map((f) => ({
          file_id: f.fileId,
          file_name: f.fileName,
          actual_type: f.docType,
        }));
      }

      const payload = {
        member_id: memberId,
        policy_id: "PLUM_GHI_2024",
        claim_category: category,
        treatment_date: treatmentDate,
        claimed_amount: parseFloat(amount),
        hospital_name: hospitalName || undefined,
        ytd_claims_amount: parseFloat(ytdAmount),
        documents,
        claims_history: JSON.parse(claimsHistoryJson),
        simulate_component_failure: simulateFailure,
      };

      const res = await submitClaimStream(payload);
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
                setIsThinking(true);
                setThinkingText("");
                scrollToBottom();
              } else if (payload.type === "thinking_delta") {
                setThinkingText((prev) => prev + payload.text);
              } else if (payload.type === "thinking_end") {
                setIsThinking(false);
              } else if (payload.type === "result") {
                setResult(payload.decision);
                scrollToBottom();
              } else if (payload.type === "error") {
                setError(payload.message);
              }
            } catch (jsonErr) {
              console.error("Failed to parse stream event:", jsonErr);
            }
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
      setIsThinking(false);
    }
  }

  // ── Test Preset Loader ────────────────────────────────────────────────────

  function loadPreset(caseId: string) {
    const presets: Record<string, () => void> = {
      TC001: () => {
        setMemberId("EMP001"); setCategory("CONSULTATION"); setTreatmentDate("2024-11-01"); setAmount("1500");
        setPresetDocsJson(JSON.stringify([
          { file_id: "F001", file_name: "dr_sharma_prescription.jpg", actual_type: "PRESCRIPTION" },
          { file_id: "F002", file_name: "another_prescription.jpg", actual_type: "PRESCRIPTION" },
        ], null, 2));
        setClaimsHistoryJson("[]"); setHospitalName(""); setYtdAmount("0"); setSimulateFailure(false);
      },
      TC004: () => {
        setMemberId("EMP001"); setCategory("CONSULTATION"); setTreatmentDate("2024-11-01"); setAmount("1500");
        setYtdAmount("5000"); setHospitalName("");
        setPresetDocsJson(JSON.stringify([
          { file_id: "F007", actual_type: "PRESCRIPTION", content: { doctor_name: "Dr. Arun Sharma", doctor_registration: "KA/45678/2015", patient_name: "Rajesh Kumar", date: "2024-11-01", diagnosis: "Viral Fever", medicines: ["Paracetamol 650mg", "Vitamin C 500mg"] } },
          { file_id: "F008", actual_type: "HOSPITAL_BILL", content: { hospital_name: "City Clinic, Bengaluru", patient_name: "Rajesh Kumar", date: "2024-11-01", line_items: [{ description: "Consultation Fee", amount: 1000 }, { description: "CBC Test", amount: 300 }, { description: "Dengue NS1 Test", amount: 200 }], total: 1500 } },
        ], null, 2));
        setClaimsHistoryJson("[]"); setSimulateFailure(false);
      },
      TC005: () => {
        setMemberId("EMP005"); setCategory("CONSULTATION"); setTreatmentDate("2024-10-15"); setAmount("3000");
        setPresetDocsJson(JSON.stringify([
          { file_id: "F009", actual_type: "PRESCRIPTION", content: { doctor_name: "Dr. Sunil Mehta", doctor_registration: "GJ/56789/2014", patient_name: "Vikram Joshi", diagnosis: "Type 2 Diabetes Mellitus", medicines: ["Metformin 500mg", "Glimepiride 1mg"] } },
          { file_id: "F010", actual_type: "HOSPITAL_BILL", content: { patient_name: "Vikram Joshi", date: "2024-10-15", total: 3000 } },
        ], null, 2));
        setClaimsHistoryJson("[]"); setHospitalName(""); setYtdAmount("0"); setSimulateFailure(false);
      },
      TC006: () => {
        setMemberId("EMP002"); setCategory("DENTAL"); setTreatmentDate("2024-10-15"); setAmount("12000");
        setPresetDocsJson(JSON.stringify([
          { file_id: "F011", actual_type: "HOSPITAL_BILL", content: { hospital_name: "Smile Dental Clinic", patient_name: "Priya Singh", line_items: [{ description: "Root Canal Treatment", amount: 8000 }, { description: "Teeth Whitening", amount: 4000 }], total: 12000 } },
        ], null, 2));
        setClaimsHistoryJson("[]"); setHospitalName(""); setYtdAmount("0"); setSimulateFailure(false);
      },
      TC009: () => {
        setMemberId("EMP008"); setCategory("CONSULTATION"); setTreatmentDate("2024-10-30"); setAmount("4800");
        setPresetDocsJson(JSON.stringify([
          { file_id: "F017", actual_type: "PRESCRIPTION", content: { diagnosis: "Migraine", doctor_name: "Dr. S. Khan" } },
          { file_id: "F018", actual_type: "HOSPITAL_BILL", content: { total: 4800 } },
        ], null, 2));
        setClaimsHistoryJson(JSON.stringify([
          { claim_id: "CLM_0081", date: "2024-10-30", amount: 1200, provider: "City Clinic A" },
          { claim_id: "CLM_0082", date: "2024-10-30", amount: 1800, provider: "City Clinic B" },
          { claim_id: "CLM_0083", date: "2024-10-30", amount: 2100, provider: "Wellness Center" },
        ], null, 2));
        setHospitalName(""); setYtdAmount("0"); setSimulateFailure(false);
      },
      TC010: () => {
        setMemberId("EMP010"); setCategory("CONSULTATION"); setTreatmentDate("2024-11-03"); setAmount("4500");
        setHospitalName("Apollo Hospitals"); setYtdAmount("8000");
        setPresetDocsJson(JSON.stringify([
          { file_id: "F019", actual_type: "PRESCRIPTION", content: { doctor_name: "Dr. S. Iyer", doctor_registration: "TN/56789/2013", patient_name: "Deepak Shah", diagnosis: "Acute Bronchitis", medicines: ["Amoxicillin 500mg", "Salbutamol Inhaler"] } },
          { file_id: "F020", actual_type: "HOSPITAL_BILL", content: { hospital_name: "Apollo Hospitals", patient_name: "Deepak Shah", line_items: [{ description: "Consultation Fee", amount: 1500 }, { description: "Medicines", amount: 3000 }], total: 4500 } },
        ], null, 2));
        setClaimsHistoryJson("[]"); setSimulateFailure(false);
      },
      TC011: () => {
        setMemberId("EMP006"); setCategory("ALTERNATIVE_MEDICINE"); setTreatmentDate("2024-10-28"); setAmount("4000");
        setSimulateFailure(true);
        setPresetDocsJson(JSON.stringify([
          { file_id: "F021", actual_type: "PRESCRIPTION", content: { doctor_name: "Vaidya T. Krishnan", doctor_registration: "AYUR/KL/2345/2019", diagnosis: "Chronic Joint Pain", treatment: "Panchakarma Therapy" } },
          { file_id: "F022", actual_type: "HOSPITAL_BILL", content: { hospital_name: "Ayur Wellness Centre", total: 4000, line_items: [{ description: "Panchakarma Therapy (5 sessions)", amount: 3000 }, { description: "Consultation", amount: 1000 }] } },
        ], null, 2));
        setClaimsHistoryJson("[]"); setHospitalName(""); setYtdAmount("0");
      },
    };
    presets[caseId]?.();
    setUsePreset(true);
    setUploadedFiles([]);
  }

  // ── File icon helpers ─────────────────────────────────────────────────────

  function fileIcon(contentType: string) {
    if (contentType === "application/pdf") return "📄";
    if (contentType.startsWith("image/")) return "🖼️";
    return "📎";
  }

  function fileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // ── JSX ───────────────────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white">Submit Claim</h1>
        <p className="mt-1 text-sm text-slate-400">Process a claim through the 5-agent pipeline</p>
      </div>

      {/* Test Case Presets */}
      <div className="glass-card p-5">
        <h3 className="mb-1 text-sm font-medium text-slate-400">Quick Load Test Cases</h3>
        <p className="mb-3 text-xs text-slate-600">Pre-fills the form with structured test data from <code className="text-violet-400">test_cases.json</code></p>
        <div className="flex flex-wrap gap-2">
          {TEST_PRESETS.map((p) => (
            <button
              key={p.caseId}
              onClick={() => loadPreset(p.caseId)}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:border-violet-500/30 hover:bg-violet-500/10 hover:text-violet-300"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="glass-card space-y-6 p-6">
        {/* Claim Details Grid */}
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-slate-300">Member</label>
            <select value={memberId} onChange={(e) => setMemberId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30">
              {MEMBERS.map((m) => (
                <option key={m.id} value={m.id} className="bg-[#0f1538]">{m.id} — {m.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300">Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30">
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value} className="bg-[#0f1538]">{c.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300">Treatment Date</label>
            <input type="date" value={treatmentDate} onChange={(e) => setTreatmentDate(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300">Claimed Amount (₹)</label>
            <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300">Hospital Name (optional)</label>
            <input type="text" value={hospitalName} onChange={(e) => setHospitalName(e.target.value)}
              placeholder="e.g. Apollo Hospitals"
              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-600 outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300">YTD Claims Amount (₹)</label>
            <input type="number" value={ytdAmount} onChange={(e) => setYtdAmount(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30" />
          </div>
        </div>

        {/* Document Upload Section */}
        <div className="space-y-3">
          {/* Mode toggle */}
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium text-slate-300">Documents</label>
            <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.03] p-0.5">
              <button
                type="button"
                onClick={() => { setUsePreset(false); }}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-all ${!usePreset
                  ? "bg-violet-600 text-white shadow"
                  : "text-slate-400 hover:text-slate-300"}`}
              >
                Upload Files
              </button>
              <button
                type="button"
                onClick={() => setUsePreset(true)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-all ${usePreset
                  ? "bg-violet-600 text-white shadow"
                  : "text-slate-400 hover:text-slate-300"}`}
              >
                JSON (Test Cases)
              </button>
            </div>
          </div>

          {/* File Upload Mode */}
          {!usePreset && (
            <div className="space-y-3">
              {/* Dropzone */}
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
                className={`relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all duration-200
                  ${isDraggingOver
                    ? "border-violet-500 bg-violet-500/10 scale-[1.01]"
                    : "border-white/10 bg-white/[0.02] hover:border-violet-500/40 hover:bg-violet-500/5"}`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,.pdf"
                  multiple
                  className="hidden"
                  onChange={(e) => handleFilesSelected(e.target.files)}
                  id="file-upload-input"
                />
                <div className={`mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full transition-colors ${isDraggingOver ? "bg-violet-500/20" : "bg-white/5"}`}>
                  <svg className={`h-6 w-6 transition-colors ${isDraggingOver ? "text-violet-400" : "text-slate-500"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-slate-300">
                  {isDraggingOver ? "Drop files here" : "Drag & drop files or click to browse"}
                </p>
                <p className="mt-1 text-xs text-slate-500">Supports JPEG, PNG, WEBP, HEIC images and PDFs · Max 20 MB per file</p>
              </div>

              {/* Uploaded files list */}
              {uploadedFiles.length > 0 && (
                <div className="space-y-2">
                  {uploadedFiles.map((f) => (
                    <div key={f.fileId}
                      className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition-all
                        ${f.status === "error"
                          ? "border-rose-500/20 bg-rose-500/5"
                          : f.status === "uploading"
                            ? "border-white/10 bg-white/[0.02]"
                            : "border-emerald-500/20 bg-emerald-500/5"}`}
                    >
                      {/* File icon */}
                      <span className="text-xl">{fileIcon(f.contentType)}</span>

                      {/* File info */}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-slate-300">{f.fileName}</p>
                        {f.status === "uploading" && (
                          <div className="mt-1 flex items-center gap-2">
                            <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/10">
                              <div className="h-full w-1/2 animate-pulse rounded-full bg-violet-500" />
                            </div>
                            <span className="text-[10px] text-slate-500">Uploading…</span>
                          </div>
                        )}
                        {f.status === "error" && (
                          <p className="text-xs text-rose-400">{f.errorMsg}</p>
                        )}
                        {f.status === "done" && (
                          <p className="text-xs text-emerald-400">Uploaded successfully</p>
                        )}
                      </div>

                      {/* Document type selector */}
                      {f.status === "done" && (
                        <select
                          value={f.docType}
                          onChange={(e) => updateDocType(f.fileId, e.target.value)}
                          className="rounded-lg border border-white/10 bg-[#0f1538] px-2 py-1 text-xs text-white outline-none focus:border-violet-500/50"
                        >
                          {DOC_TYPES.map((dt) => (
                            <option key={dt} value={dt}>{dt.replace("_", " ")}</option>
                          ))}
                        </select>
                      )}

                      {/* Remove button */}
                      <button
                        type="button"
                        onClick={() => removeFile(f.fileId)}
                        className="ml-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-slate-500 transition hover:bg-rose-500/10 hover:text-rose-400"
                        aria-label="Remove file"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {uploadedFiles.length === 0 && (
                <p className="text-center text-xs text-slate-600">No documents uploaded yet</p>
              )}
            </div>
          )}

          {/* JSON / Test Case Mode */}
          {usePreset && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500">
                Use Quick Load above to auto-fill, or paste a custom JSON array of document objects.
              </p>
              <textarea
                value={presetDocsJson}
                onChange={(e) => setPresetDocsJson(e.target.value)}
                rows={7}
                id="preset-docs-json"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 font-mono text-xs text-white outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30"
              />
            </div>
          )}
        </div>

        {/* Claims History */}
        <div>
          <label className="block text-sm font-medium text-slate-300">Claims History (JSON array)</label>
          <textarea value={claimsHistoryJson} onChange={(e) => setClaimsHistoryJson(e.target.value)} rows={3}
            id="claims-history-json"
            className="mt-1 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 font-mono text-xs text-white outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30" />
        </div>

        {/* Failure simulation toggle */}
        <div className="flex items-center gap-2">
          <input type="checkbox" checked={simulateFailure} onChange={(e) => setSimulateFailure(e.target.checked)}
            className="rounded border-white/10 bg-white/5" id="simulate-failure" />
          <label htmlFor="simulate-failure" className="text-sm text-slate-400">Simulate component failure (TC011)</label>
        </div>

        <button type="submit" disabled={loading}
          className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:shadow-violet-500/40 hover:brightness-110 disabled:opacity-50">
          {loading ? "Processing through pipeline…" : "Submit Claim"}
        </button>
      </form>

      {/* Error */}
      {error && (
        <div className="glass-card border-rose-500/30 bg-rose-500/5 p-4">
          <p className="text-sm text-rose-400">{error}</p>
        </div>
      )}

      {/* Model Reasoning / Agent Thinking */}
      {(isThinking || thinkingText) && (
        <div className="glass-card p-6 space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            Model Reasoning
            {isThinking && (
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
              </span>
            )}
          </h3>
          <div className="rounded-xl border border-violet-500/20 bg-violet-500/[0.02] p-4 min-h-[100px] flex flex-col justify-between">
            <p className="text-xs text-violet-100/90 whitespace-pre-wrap leading-relaxed font-mono">
              {thinkingText || "Waiting for LLM analysis..."}
              {isThinking && (
                <span className="inline-block w-1.5 h-3.5 ml-1 bg-violet-400 animate-pulse" />
              )}
            </p>
            {isThinking && (
              <p className="text-[10px] text-violet-400/60 mt-3 border-t border-violet-500/10 pt-2 animate-pulse">
                Streaming model thoughts live...
              </p>
            )}
          </div>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-6">
          <div className="glass-card p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Decision</p>
                <div className="mt-2 flex items-center gap-4">
                  <span className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-bold
                    ${result.decision === "APPROVED" ? "badge-approved" :
                      result.decision === "PARTIAL" ? "badge-partial" :
                      result.decision === "REJECTED" ? "badge-rejected" :
                      result.decision === "MANUAL_REVIEW" ? "badge-manual-review" : "badge-stopped"}`}>
                    {result.decision || "STOPPED EARLY"}
                  </span>
                  <span className="font-mono text-sm text-slate-400">{result.claim_id}</span>
                </div>
              </div>
              {result.approved_amount != null && (
                <div className="text-right">
                  <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Approved Amount</p>
                  <p className="mt-1 text-3xl font-bold text-emerald-400">₹{result.approved_amount.toLocaleString()}</p>
                </div>
              )}
            </div>
            <div className="mt-4">
              <p className="text-sm text-slate-300">{result.explanation}</p>
            </div>
            {result.confidence_score > 0 && (
              <div className="mt-4">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Confidence</span>
                  <span>{(result.confidence_score * 100).toFixed(0)}%</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-1000"
                    style={{ width: `${result.confidence_score * 100}%` }} />
                </div>
              </div>
            )}
          </div>

          {/* Amount Breakdown */}
          {result.amount_breakdown && (
            <div className="glass-card p-6">
              <h3 className="mb-3 text-sm font-semibold text-white">Amount Calculation</h3>
              <div className="space-y-2">
                {result.amount_breakdown.calculation_steps.map((step, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-violet-500/10 text-xs text-violet-400">{i + 1}</div>
                    <span className="text-slate-300">{step}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Line Item Decisions */}
          {result.line_item_decisions.length > 0 && (
            <div className="glass-card p-6">
              <h3 className="mb-3 text-sm font-semibold text-white">Line Item Decisions</h3>
              <div className="space-y-2">
                {result.line_item_decisions.map((item, i) => (
                  <div key={i} className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-4 py-2">
                    <div>
                      <span className="text-sm text-slate-300">{item.description}</span>
                      {item.reason && <span className="ml-2 text-xs text-slate-500">— {item.reason}</span>}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-slate-400">₹{item.amount.toLocaleString()}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${item.status === "APPROVED" ? "badge-approved" : "badge-rejected"}`}>
                        {item.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Trace Timeline */}
          {result.trace && (
            <div className="glass-card p-6">
              <h3 className="mb-4 text-sm font-semibold text-white">Pipeline Trace</h3>
              <div className="space-y-4">
                {result.trace.agent_traces.map((agent, i) => (
                  <div key={i} className="relative pl-8">
                    {i < result.trace!.agent_traces.length - 1 && (
                      <div className="absolute left-[13px] top-7 h-full w-0.5 bg-white/5" />
                    )}
                    <div className={`absolute left-0 top-1 flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold
                      ${agent.status === "SUCCESS" ? "bg-emerald-500/20 text-emerald-400" :
                        agent.status === "FAILED" ? "bg-rose-500/20 text-rose-400" :
                        agent.status === "DEGRADED" ? "bg-amber-500/20 text-amber-400" : "bg-slate-500/20 text-slate-400"}`}>
                      {agent.status === "SUCCESS" ? "✓" : agent.status === "FAILED" ? "✗" : "⚠"}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-white">{agent.agent_name}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold
                          ${agent.status === "SUCCESS" ? "badge-approved" :
                            agent.status === "FAILED" ? "badge-rejected" : "badge-partial"}`}>
                          {agent.status}
                        </span>
                      </div>
                      {agent.error && (
                        <p className="mt-1 text-xs text-rose-400">Error: {agent.error}</p>
                      )}
                      <div className="mt-2 space-y-1">
                        {agent.checks_performed.map((check, j) => (
                          <div key={j} className="flex items-start gap-2 text-xs">
                            <span className={`mt-0.5 ${
                              check.status === "PASS" || check.status === "SUCCESS" ? "text-emerald-400" :
                              check.status === "FAIL" ? "text-rose-400" :
                              check.status === "WARNING" ? "text-amber-400" : "text-slate-500"
                            }`}>
                              {check.status === "PASS" || check.status === "SUCCESS" ? "✓" : check.status === "FAIL" ? "✗" : check.status === "WARNING" ? "⚠" : "○"}
                            </span>
                            <span className="text-slate-400">{check.message}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="glass-card border-amber-500/20 bg-amber-500/5 p-4">
              <h4 className="text-sm font-semibold text-amber-400">Warnings</h4>
              <ul className="mt-2 space-y-1">
                {result.warnings.map((w, i) => (
                  <li key={i} className="text-xs text-amber-300/80">⚠ {w}</li>
                ))}
              </ul>
            </div>
          )}

          <a href={`/claims/${result.claim_id}`}
            className="inline-flex items-center gap-1 text-sm text-violet-400 hover:text-violet-300">
            View full claim details →
          </a>
        </div>
      )}
    </div>
  );
}
