export type EventType =
  | "agent_spawned"
  | "agent_message"
  | "consensus_start"
  | "consensus_vote"
  | "consensus_reached"
  | "layer_complete"
  | "loop_iteration"
  | "pipeline_complete"
  | "error";

export type LayerName = "extraction" | "detection" | "correction";

export type Severity = "high" | "medium" | "low";

export type Verdict = "pass" | "minor_revision" | "deeper_review";

export type JobStatus =
  | "accepted"
  | "extracting"
  | "detecting"
  | "correcting"
  | "complete"
  | "error";

export interface AgentEvent {
  job_id: string;
  layer: LayerName;
  event_type: EventType;
  agent_name: string;
  message: string;
  metadata: Record<string, unknown>;
}

export interface Correction {
  flaw_category: string;
  suggestion: string;
  explanation: string;
  priority: Severity;
  references: string[];
}

export interface RecommendationSet {
  job_id: string;
  recommendations: Correction[];
  flaws_found: boolean;
  inner_loop_count: number;
  outer_loop_count: number;
  analysis_seconds: number;
}

export interface UploadResponse {
  job_id: string;
  status: JobStatus;
}

export interface JobResult {
  job_id: string;
  status: JobStatus;
  recommendations?: RecommendationSet;
  error?: string;
}
