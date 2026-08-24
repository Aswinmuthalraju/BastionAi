export interface User {
  user_id: string;
  username: string;
  full_name: string;
  role: "operator" | "engineer" | "admin" | string;
  department: string;
  data_scopes: string[];
}

export interface LoginResponse {
  status: string;
  auth_method: string;
  user: User;
  access_token: string;
  token_type: string;
}

export interface RiskAnalysis {
  total_risk_score: number;
  autonomy_tier: string;
  sensitivity: number;
  tool_danger: number;
  reversibility: number;
  risk_factors: string[];
  requires_human_pause: boolean;
}

export interface DriftAnalysis {
  drift_score: number;
  drift_threshold: number;
  is_drifted: boolean;
  expected_node: string;
  proposed_action: string;
  step_index: number;
  recommended_autonomy_tier: string;
  degraded: boolean;
}

export interface Passport {
  task_id: string;
  user_id: string;
  user_role: string;
  data_scope: string[];
  allowed_models: string[];
  allowed_tools: string[];
  autonomy_required: string;
  risk_score: number;
  risk_factors: string[];
  created_at: number;
}

export interface EvidenceCitation {
  citation_id: string;
  source_doc: string;
  page_number: number;
  bounding_box: { x1: number; y1: number; x2: number; y2: number };
  chunk_id: string;
  snippet: string;
  similarity: number;
  model_used: string;
  timestamp: string;
}

export interface ProvenanceStage {
  stage: string;
  status: string;
  detail: Record<string, unknown>;
}

export interface ChatResponse {
  status:
    | "completed"
    | "approval_required"
    | "quarantined_and_blocked"
    | "rejected"
    | "error";
  passport?: Passport;
  risk_analysis?: RiskAnalysis;
  drift_analysis?: DriftAnalysis;
  agent_response?: string;
  evidence_citations?: EvidenceCitation[];
  trace_message?: string | null;
  provenance?: ProvenanceStage[];
  message?: string;
  reason?: string;
  route_info?: { model_id: string; model_name: string; served_model: string };
}

export interface ModelManifestEntry {
  id: string;
  name: string;
  endpoint: string;
  served_model?: string;
  modality: string;
  context_window: number;
  task_tags: string[];
  is_default: boolean;
  deployment_note?: string;
}

export interface DocumentRecord {
  doc_id: string;
  filename: string;
  content_type: string;
  data_scope: string;
  allowed_roles: string;
  page_count: number;
  status: string;
  uploaded_by: string;
  uploaded_at: number;
  error: string | null;
}

export interface UploadResult {
  doc_id: string;
  filename: string;
  status: string;
  page_count: number;
  indexed_chunks: number;
  quarantined_chunks: number;
  mentioned_equipment: string[];
  error: string | null;
}

export interface AuditLogEntry {
  event_id: string;
  user_id: string;
  action: string;
  risk_tier: string;
  outcome: string;
  details: string;
  timestamp: string;
}

export interface QuarantineAlert {
  item_id: string;
  content_snippet: string;
  source: string;
  page: number;
  trace: string;
  quarantined_at: string;
}

export interface MemoryEntry {
  entry_id: string;
  content: string;
  category: string;
  importance: number;
  recency_score: number;
  composite_score: number;
  task_id: string;
  timestamp: string;
}

export interface GraphNode {
  id: string;
  label: string;
  name: string;
  [key: string]: unknown;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface GraphLineage {
  query_equipment: string;
  cypher_executed: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface HealthReport {
  status: "healthy" | "degraded";
  checks: Record<string, { reachable: boolean; [key: string]: unknown }>;
}
