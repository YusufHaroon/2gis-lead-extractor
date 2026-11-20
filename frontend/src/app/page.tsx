"use client";

import { useEffect, useMemo, useState } from "react";

import ExportButton from "@/components/ExportButton";
import JobStatus from "@/components/JobStatus";
import ResultsTable from "@/components/ResultsTable";
import SearchPanel from "@/components/SearchPanel";
import { getSources } from "@/lib/api";
import type { SourceInfo } from "@/lib/types";
import { useJob } from "@/lib/useJob";

const SOURCES_RETRY_MS = 5000;

export default function Home() {
  const { job, query, records, submitting, cancelling, busy, startError, connectionWarning, start, cancel } = useJob();
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [sourcesError, setSourcesError] = useState<string | null>(null);

  // Load the source list; if the backend is down, keep retrying so the page recovers on its own.
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () =>
      getSources()
        .then((s) => {
          if (stopped) return;
          setSources(s);
          setSourcesError(null);
        })
        .catch((err: Error) => {
          if (stopped) return;
          setSourcesError(err.message);
          timer = setTimeout(load, SOURCES_RETRY_MS);
        });
    load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, []);

  const withPhone = useMemo(() => records.filter((r) => r.phone_number).length, [records]);

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-8 sm:py-10">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Business Lead Extractor</h1>
        <p className="text-sm text-slate-600">
          Search businesses by category and location, review names and one phone number each, and export to Excel.
        </p>
      </header>

      {sourcesError && (
        <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {sourcesError}
        </p>
      )}

      <SearchPanel sources={sources} busy={busy} submitting={submitting} error={startError} onSubmit={start} />

      <JobStatus
        job={job}
        query={query}
        recordCount={records.length}
        withPhoneCount={withPhone}
        cancelling={cancelling}
        connectionWarning={connectionWarning}
        onCancel={cancel}
      />

      <ResultsTable records={records}>
        <ExportButton job={job} recordCount={records.length} />
      </ResultsTable>

      <footer className="pt-2 text-xs text-slate-500">
        Only permitted data sources are available. Results are limited to what the source makes available, and Excel
        export is enabled only where the source licence allows it. Use collected numbers in line with applicable
        marketing, privacy and telemarketing rules.
      </footer>
    </main>
  );
}
