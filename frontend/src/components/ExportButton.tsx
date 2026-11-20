"use client";

import { exportUrl } from "@/lib/api";
import type { JobInfo } from "@/lib/types";

interface Props {
  job: JobInfo | null;
  recordCount: number;
}

function disabledReason(job: JobInfo, recordCount: number): string | null {
  if (!job.export_allowed) return "Export is not permitted for this data source.";
  if (job.status === "running") return "Available when the search completes.";
  if (job.status !== "completed") return "Export is only available for completed searches.";
  if (recordCount === 0) return "Nothing to export.";
  return null;
}

const DownloadIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden>
    <path d="M10.75 2.75a.75.75 0 0 0-1.5 0v8.614L6.295 8.235a.75.75 0 1 0-1.09 1.03l4.25 4.5a.75.75 0 0 0 1.09 0l4.25-4.5a.75.75 0 0 0-1.09-1.03l-2.955 3.129V2.75Z" />
    <path d="M3.5 12.75a.75.75 0 0 0-1.5 0v2.5A2.75 2.75 0 0 0 4.75 18h10.5A2.75 2.75 0 0 0 18 15.25v-2.5a.75.75 0 0 0-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5Z" />
  </svg>
);

export default function ExportButton({ job, recordCount }: Props) {
  if (!job) return null;
  const reason = disabledReason(job, recordCount);
  const base = "inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold shadow-sm transition";

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {reason && <span id="export-reason" className="text-xs text-slate-500">{reason}</span>}
      {reason ? (
        <button type="button" disabled aria-describedby="export-reason" className={`${base} cursor-not-allowed bg-slate-200 text-slate-500`}>
          <DownloadIcon /> Download Excel
        </button>
      ) : (
        <a href={exportUrl(job.job_id)} download className={`${base} bg-emerald-600 text-white hover:bg-emerald-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600`}>
          <DownloadIcon /> Download Excel
        </a>
      )}
    </div>
  );
}
