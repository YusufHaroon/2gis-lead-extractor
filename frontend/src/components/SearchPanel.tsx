"use client";

import { FormEvent, useEffect, useState } from "react";

import { CATEGORIES } from "@/lib/categories";
import type { JobCreate, SourceInfo } from "@/lib/types";

const MAX_TEXT = 100;

interface Props {
  sources: SourceInfo[];
  busy: boolean;
  submitting: boolean;
  error: string | null;
  onSubmit: (req: JobCreate) => void;
}

type FieldErrors = Partial<Record<"category" | "location" | "maxResults", string>>;

function validate(category: string, location: string, maxResults: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!category.trim()) errors.category = "Enter or pick a category.";
  else if (category.trim().length > MAX_TEXT) errors.category = `Keep it under ${MAX_TEXT} characters.`;
  if (!location.trim()) errors.location = "Enter a city or country.";
  else if (location.trim().length > MAX_TEXT) errors.location = `Keep it under ${MAX_TEXT} characters.`;
  if (maxResults.trim()) {
    const n = Number(maxResults);
    if (!Number.isInteger(n) || n < 1) errors.maxResults = "Use a whole number of 1 or more.";
  }
  return errors;
}

const inputClass =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition " +
  "placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 " +
  "disabled:cursor-not-allowed disabled:bg-slate-100 aria-[invalid=true]:border-rose-400";

function Field({ id, label, hint, error, children }: {
  id: string; label: string; hint?: string; error?: string; children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">{label}</label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-xs text-rose-600">{error}</p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}

export default function SearchPanel({ sources, busy, submitting, error, onSubmit }: Props) {
  const enabledSources = sources.filter((s) => s.enabled);
  const [category, setCategory] = useState("");
  const [location, setLocation] = useState("");
  const [maxResults, setMaxResults] = useState("");
  const [source, setSource] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});

  // Pre-select the server's default source once the list arrives.
  useEffect(() => {
    if (!source && enabledSources.length) {
      setSource((enabledSources.find((s) => s.is_default) ?? enabledSources[0]).name);
    }
  }, [enabledSources, source]);

  const selected = enabledSources.find((s) => s.name === source);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const found = validate(category, location, maxResults);
    setErrors(found);
    if (Object.keys(found).length) return;
    onSubmit({
      category: category.trim(),
      location: location.trim(),
      ...(maxResults.trim() ? { max_results: Number(maxResults) } : {}),
      ...(source ? { source } : {}),
    });
  }

  const describedBy = (id: keyof FieldErrors, hasHint = false) =>
    errors[id] ? `${id}-error` : hasHint ? `${id}-hint` : undefined;

  return (
    <section aria-labelledby="search-heading" className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
      <h2 id="search-heading" className="sr-only">Search</h2>
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="category" label="Category" hint="Pick a suggestion or type your own." error={errors.category}>
            <input
              id="category"
              list="category-options"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Restaurants"
              maxLength={MAX_TEXT}
              autoComplete="off"
              disabled={busy}
              aria-invalid={!!errors.category}
              aria-describedby={describedBy("category", true)}
              className={inputClass}
            />
            <datalist id="category-options">
              {CATEGORIES.map((c) => <option key={c} value={c} />)}
            </datalist>
          </Field>

          <Field id="location" label="City or country" error={errors.location}>
            <input
              id="location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Dubai"
              maxLength={MAX_TEXT}
              disabled={busy}
              aria-invalid={!!errors.location}
              aria-describedby={describedBy("location")}
              className={inputClass}
            />
          </Field>

          <Field id="maxResults" label="Max results (optional)" hint="Leave blank for the server limit." error={errors.maxResults}>
            <input
              id="maxResults"
              type="number"
              inputMode="numeric"
              min={1}
              step={1}
              value={maxResults}
              onChange={(e) => setMaxResults(e.target.value)}
              placeholder="e.g. 50"
              disabled={busy}
              aria-invalid={!!errors.maxResults}
              aria-describedby={describedBy("maxResults", true)}
              className={inputClass}
            />
          </Field>

          {enabledSources.length > 0 && (
            <Field
              id="source"
              label="Data source"
              hint={selected && !selected.export_allowed ? "Excel export is not permitted for this source." : undefined}
            >
              <select
                id="source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                disabled={busy}
                aria-describedby={selected && !selected.export_allowed ? "source-hint" : undefined}
                className={inputClass}
              >
                {enabledSources.map((s) => (
                  <option key={s.name} value={s.name}>{s.label}</option>
                ))}
              </select>
            </Field>
          )}
        </div>

        {error && (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:cursor-not-allowed disabled:bg-slate-400 sm:w-auto"
        >
          {busy && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />}
          {submitting ? "Starting…" : busy ? "Collection running…" : "Start Collection"}
        </button>
      </form>
    </section>
  );
}
