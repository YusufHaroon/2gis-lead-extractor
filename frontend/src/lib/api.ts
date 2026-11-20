import type { BusinessRecord, JobCreate, JobInfo } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// TODO (Phase 4): implement fetch helpers
export async function startJob(_req: JobCreate): Promise<JobInfo> {
  throw new Error("TODO");
}
export async function getJob(_id: string): Promise<JobInfo> {
  throw new Error("TODO");
}
export async function getResults(_id: string): Promise<BusinessRecord[]> {
  throw new Error("TODO");
}
export const exportUrl = (id: string) => `${API}/api/jobs/${id}/export`;
