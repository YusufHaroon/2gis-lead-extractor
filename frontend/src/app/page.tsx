import SearchPanel from "@/components/SearchPanel";
import JobStatus from "@/components/JobStatus";
import ResultsTable from "@/components/ResultsTable";
import ExportButton from "@/components/ExportButton";

// TODO (Phase 4): wire state - start job, poll status, load results.
export default function Home() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 sm:p-8">
      <h1 className="text-2xl font-semibold">Business Lead Extractor</h1>
      <SearchPanel />
      <JobStatus />
      <ResultsTable />
      <ExportButton />
    </main>
  );
}
