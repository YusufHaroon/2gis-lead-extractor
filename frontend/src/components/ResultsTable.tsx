"use client";

import type { BusinessRecord } from "@/lib/types";

interface Props {
  records: BusinessRecord[];
  children?: React.ReactNode; // actions (e.g. the export button) shown in the header
}

/** Keep only characters a dialer understands; the displayed number is never changed. */
const telHref = (phone: string) => `tel:${phone.replace(/[^\d+]/g, "")}`;

export default function ResultsTable({ records, children }: Props) {
  if (records.length === 0) return null;

  return (
    <section aria-labelledby="results-heading" className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 sm:px-6">
        <h2 id="results-heading" className="text-sm font-medium text-slate-700">
          Results <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs tabular-nums text-slate-600">{records.length}</span>
        </h2>
        {children}
      </div>

      <div className="max-h-[60vh] overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 shadow-[inset_0_-1px_0] shadow-slate-200">
            <tr>
              <th scope="col" className="px-4 py-2.5 font-medium sm:px-6">Business Name</th>
              <th scope="col" className="w-[40%] px-4 py-2.5 font-medium sm:w-56 sm:px-6">Phone Number</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {records.map((r, i) => (
              <tr key={`${i}-${r.business_name}`} className="hover:bg-slate-50/70">
                <td className="break-words px-4 py-2.5 text-slate-900 sm:px-6">{r.business_name}</td>
                <td className="whitespace-nowrap px-4 py-2.5 tabular-nums text-slate-700 sm:px-6">
                  {r.phone_number ? (
                    <a href={telHref(r.phone_number)} className="hover:text-indigo-600 hover:underline">{r.phone_number}</a>
                  ) : (
                    <span className="sr-only">No phone number</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
