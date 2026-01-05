export type JobStatus = "DRAFT" | "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELED";

export interface Job {
  id: string;
  name: string;
  status: JobStatus;
  progress: number;
  createdAt: string;
  updatedAt: string;
  userId: string;
  inputs?: Record<string, unknown>;
  outputs?: JobOutput[];
  error?: string;
}

export interface JobOutput {
  name: string;
  url?: string;
  size?: string;
  type?: string;
}

export interface CreateJobInput {
  name?: string;
  file?: File;
  options?: Record<string, unknown>;
}
