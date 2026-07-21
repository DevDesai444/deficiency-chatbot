"use client";

import { useCallback, useState } from "react";
import { UploadPanel } from "@/components/upload-panel";
import { AgentActivity } from "@/components/agent-activity";
import { Faults } from "@/components/faults";
import { uploadDocument, getJobResult } from "@/lib/api-client";
import { useAgentStream } from "@/lib/ws-client";
import type { FaultReport, JobStatus } from "@/types";

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [report, setReport] = useState<FaultReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { events } = useAgentStream(jobId);

  const handleUpload = useCallback(async (file: File) => {
    setError(null);
    setReport(null);
    setStatus("accepted");

    try {
      const { job_id } = await uploadDocument(file);
      setJobId(job_id);
      pollForResults(job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setStatus("error");
    }
  }, []);

  async function pollForResults(id: string) {
    const poll = setInterval(async () => {
      try {
        const result = await getJobResult(id);
        setStatus(result.status);

        if (result.status === "complete" && result.faults) {
          setReport(result.faults);
          clearInterval(poll);
        } else if (result.status === "error") {
          setError(result.error ?? "Analysis failed");
          clearInterval(poll);
        }
      } catch {
        // backend may not be ready yet
      }
    }, 2000);
  }

  const isProcessing =
    status !== null && status !== "complete" && status !== "error";

  return (
    <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">DefPredict</h1>
        <p className="text-gray-500 text-sm mt-1">
          CMC submission deficiency detection
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <UploadPanel onUpload={handleUpload} disabled={isProcessing} />

          {error && (
            <div className="border border-red-200 rounded-lg p-4 bg-red-50 text-red-700 text-sm">
              {error}
            </div>
          )}

          {report && <Faults report={report} />}
        </div>

        <div className="space-y-4">
          {status && (
            <div className="text-sm text-gray-500">
              Status:{" "}
              <span className="font-medium text-gray-700">{status}</span>
            </div>
          )}
          <AgentActivity events={events} />
        </div>
      </div>
    </main>
  );
}
