import type { JobResult, UploadResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ModelOption {
  id: string;
  label: string;
}

export interface ModelsResponse {
  models: ModelOption[];
  default: string;
}

export async function getModels(): Promise<ModelsResponse> {
  const res = await fetch(`${API_BASE}/api/models`);
  if (!res.ok) {
    throw new Error(`Failed to fetch models (${res.status})`);
  }
  return res.json();
}

export async function uploadDocument(
  file: File,
  model?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (model) form.append("model", model);

  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed (${res.status}): ${text}`);
  }

  return res.json();
}

export async function getJobResult(jobId: string): Promise<JobResult> {
  const res = await fetch(`${API_BASE}/api/results/${jobId}`);

  if (!res.ok) {
    throw new Error(`Failed to fetch results (${res.status})`);
  }

  return res.json();
}
