import type { BusinessRecord, JobCreate, JobInfo, SourceInfo } from "./types";

const API = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

/** An API failure with a message that is safe and useful to show to the user. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // FastAPI 422: [{loc: ["body", "category"], msg: "..."}]
      return (detail as ValidationIssue[])
        .map((d) => {
          const field = d.loc?.filter((p) => p !== "body").join(".");
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join("; ");
    }
  } catch {
    // non-JSON error body - fall through
  }
  return `Request failed (HTTP ${res.status}).`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Can't reach the server. Check that the backend is running and try again.", 0);
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  return (await res.json()) as T;
}

const job = (id: string) => `/api/jobs/${encodeURIComponent(id)}`;

export const startJob = (req: JobCreate) =>
  request<JobInfo>("/api/jobs", { method: "POST", body: JSON.stringify(req) });

export const getJob = (id: string) => request<JobInfo>(job(id));

export const getResults = (id: string) => request<BusinessRecord[]>(`${job(id)}/results`);

export const cancelJob = (id: string) => request<JobInfo>(`${job(id)}/cancel`, { method: "POST" });

export const getSources = () => request<SourceInfo[]>("/api/sources");

export const exportUrl = (id: string) => `${API}${job(id)}/export`;
