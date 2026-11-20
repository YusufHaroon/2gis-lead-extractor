export type JobStatus = "idle" | "running" | "completed" | "failed" | "cancelled";

export interface JobCreate {
  category: string;
  location: string;
  max_results?: number;
  source?: string;
}

export interface JobInfo {
  job_id: string;
  status: JobStatus;
  collected: number;
  total_expected: number | null;
  export_allowed: boolean;
  error: string | null;
}

export interface BusinessRecord {
  business_name: string;
  phone_number: string | null;
}
