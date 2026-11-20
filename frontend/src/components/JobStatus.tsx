"use client";

import type { JobInfo, JobStatus as Status, SearchQuery } from "@/lib/types";

interface Props {
  job: JobInfo | null;
  query: SearchQuery | null;
  recordCount: number;
  withPhoneCount: number;
  cancelling: boolean;
  connectionWarning: string | null;
  onCancel: () => void;
}

const BADGE: Record<Status, { label: string; className: string }> = {
  idle: { label: "Idle", className: "bg-slate-100 text-slate-700 ring-slate-300" },
  running: { label: "Running", className: "bg-indigo-50 text-indigo-700 ring-indigo-300" },
  completed: { label: "Completed", className: "bg-emerald-50 text-emerald-700 ring-emerald-300" },
  failed: { label: "Failed", className: "bg-rose-50 text-rose-700 ring-rose-300" },
  cancelled: { label: "Cancelled", className: "bg-amber-50 text-amber-800 ring-amber-300" },
};

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "es"}`;

function message(job: JobInfo | null, query: SearchQuery | null, records: number, withPhone: number) {
  if (!job) return { text: "Choose a category and location, then start a collection.", tone: "muted" as const };
  const what = query ? `“${query.category}” in “${query.location}”` : "this search";
  const partial = records > 0 ? ` Showing ${plural(records, "business")} collected before it stopped.` : "";
  switch (job.status) {
    case "running":
      return { text: `Searching for ${what}…`, tone: "muted" as const };
    case "completed":
      return records === 0
        ? { text: `No businesses found for ${what}. Try a broader category or a different location.`, tone: "warn" as const }
        : { text: `Found ${plural(records, "business")} for ${what} — ${withPhone} with a phone number.`, tone: "success" as const };
    case "cancelled":
      return { text: `Search cancelled.${partial}`, tone: "warn" as const };
    case "failed":
      return { text: `${job.error ?? "The search failed."}${partial}`, tone: "error" as const };
    default:
      return { text: "", tone: "muted" as const };
  }
}

const TONE = {
  muted: "text-slate-600",
  success: "text-emerald-700",
  warn: "text-amber-800",
  error: "text-rose-700",
};

export default function JobStatus({ job, query, recordCount, withPhoneCount, cancelling, connectionWarning, onCancel }: Props) {
  const status: Status = job?.status ?? "idle";
  const badge = BADGE[status];
  const msg = message(job, query, recordCount, withPhoneCount);
  const running = status === "running";
  const total = job?.total_expected ?? null;
  const pct = job && total ? Math.min(100, Math.round((job.collected / total) * 100)) : null;

  return (
    <section aria-labelledby="status-heading" className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 id="status-heading" className="text-sm font-medium text-slate-700">Status</h2>
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${badge.className}`}>
            {running && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden />}
            {badge.label}
          </span>
        </div>
        {job && (
          <div className="flex items-center gap-4">
            <p className="text-sm text-slate-600">
              Collected <span className="font-semibold tabular-nums text-slate-900">{job.collected}</span>
              {running && total ? <span className="text-slate-500"> of up to {total}</span> : null}
            </p>
            {running && (
              <button
                type="button"
                onClick={onCancel}
                disabled={cancelling}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {cancelling ? "Cancelling…" : "Cancel"}
              </button>
            )}
          </div>
        )}
      </div>

      {running && pct !== null && (
        <div
          className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"
          role="progressbar"
          aria-label="Collection progress"
          aria-valuemin={0}
          aria-valuemax={total ?? undefined}
          aria-valuenow={job?.collected}
        >
          <div className="h-full rounded-full bg-indigo-500 transition-[width] duration-500" style={{ width: `${pct}%` }} />
        </div>
      )}

      <p aria-live="polite" className={`mt-3 text-sm ${TONE[msg.tone]}`}>{msg.text}</p>
      {connectionWarning && <p role="status" className="mt-1 text-xs text-amber-700">{connectionWarning}</p>}
    </section>
  );
}
