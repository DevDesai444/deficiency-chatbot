export type EventType =
  | "agent_spawned"
  | "agent_message"
  | "layer_start"
  | "layer_complete"
  | "selection"
  | "oracle_complete"
  | "pipeline_start"
  | "pipeline_complete"
  | "error";

export type LayerName = "parse" | "detection";

export type Severity = "high" | "medium" | "low";

export type Tier = "verified" | "corroborated" | "advisory";

export type EvidenceClass =
  | "code_verified"
  | "checklist"
  | "quote_anchored"
  | "model_judgment";

export type JobStatus = "accepted" | "parsing" | "detecting" | "complete" | "error";

export interface AgentEvent {
  job_id: string;
  layer: LayerName;
  event_type: EventType;
  agent_name: string;
  message: string;
  metadata: Record<string, unknown>;
}

export interface SimilarDeficiency {
  anda_number: string;
  product_name: string;
  deficiency_text: string;
  similarity_score: number;
}

export interface Fault {
  title: string;
  detail: string;
  category: string;
  severity: Severity;
  tier: Tier;
  evidence_class: EvidenceClass;
  confidence: number;
  evidence: string;
  section: string;
  page: number;
  table_ref: string;
  source: string;
  guidance_refs: string[];
  precedents: SimilarDeficiency[];
  novel: boolean;
  out_of_distribution: boolean;
  challenge_note: string;
}

export interface FaultReport {
  job_id: string;
  faults: Fault[];
  faults_found: boolean;
  domains_checked: string[];
  analysis_seconds: number;
}

export interface UploadResponse {
  job_id: string;
  status: JobStatus;
}

export interface JobResult {
  job_id: string;
  status: JobStatus;
  faults?: FaultReport;
  error?: string;
}
