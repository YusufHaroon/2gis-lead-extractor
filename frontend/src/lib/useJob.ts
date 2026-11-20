"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, cancelJob, getJob, getResults, startJob } from "./api";
import type { BusinessRecord, JobCreate, JobInfo, SearchQuery } from "./types";
import { TERMINAL_STATUSES } from "./types";

const POLL_INTERVAL_MS = 1000;
const MAX_CONSECUTIVE_POLL_FAILURES = 5;

/**
 * Owns the current search job: starting it, polling status + results until it reaches a
 * terminal state, cancelling, and surfacing errors. Components only render what it returns.
 */
export function useJob() {
  const [job, setJob] = useState<JobInfo | null>(null);
  const [query, setQuery] = useState<SearchQuery | null>(null);
  const [records, setRecords] = useState<BusinessRecord[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [connectionWarning, setConnectionWarning] = useState<string | null>(null);

  const jobId = job?.job_id;
  const isRunning = job?.status === "running";

  // Poll while the job is running. Re-subscribes only when the job or its running state changes.
  useEffect(() => {
    if (!jobId || !isRunning) return;

    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;

    const failLocally = (message: string) =>
      setJob((j) => (j && j.job_id === jobId ? { ...j, status: "failed", error: message } : j));

    const tick = async () => {
      try {
        const [info, partial] = await Promise.all([getJob(jobId), getResults(jobId)]);
        if (stopped) return;
        failures = 0;
        setConnectionWarning(null);

        if (TERMINAL_STATUSES.has(info.status)) {
          // Results may have been read just before the final records landed - fetch once more.
          const final = await getResults(jobId);
          if (stopped) return;
          setRecords(final);
          setJob(info);
          return;
        }
        setRecords(partial);
        setJob(info);
      } catch (err) {
        if (stopped) return;
        if (err instanceof ApiError && err.status === 404) {
          failLocally("This search is no longer available on the server (it may have restarted). Please start a new search.");
          return;
        }
        failures += 1;
        if (failures >= MAX_CONSECUTIVE_POLL_FAILURES) {
          setConnectionWarning(null);
          failLocally("Lost connection to the server while the search was running. Please check the backend and try again.");
          return;
        }
        setConnectionWarning("Connection problem - retrying…");
      }
      timer = setTimeout(tick, POLL_INTERVAL_MS);
    };

    timer = setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [jobId, isRunning]);

  useEffect(() => {
    if (!isRunning) setCancelling(false);
  }, [isRunning]);

  const start = useCallback(
    async (req: JobCreate) => {
      if (submitting || isRunning) return; // no duplicate submissions
      setSubmitting(true);
      setStartError(null);
      setConnectionWarning(null);
      try {
        const info = await startJob(req);
        setRecords([]);
        setQuery({ category: req.category, location: req.location });
        setJob(info);
      } catch (err) {
        setStartError(err instanceof Error ? err.message : "Could not start the search.");
      } finally {
        setSubmitting(false);
      }
    },
    [submitting, isRunning],
  );

  const cancel = useCallback(async () => {
    if (!jobId || !isRunning || cancelling) return;
    setCancelling(true);
    try {
      await cancelJob(jobId); // the status change arrives with the next poll
    } catch (err) {
      // 409 = it finished in the meantime; the next poll shows the real state.
      if (!(err instanceof ApiError && err.status === 409)) {
        setCancelling(false);
        setConnectionWarning(err instanceof Error ? err.message : "Could not cancel the search.");
      }
    }
  }, [jobId, isRunning, cancelling]);

  return {
    job,
    query,
    records,
    submitting,
    cancelling,
    busy: submitting || isRunning,
    startError,
    connectionWarning,
    start,
    cancel,
  };
}
