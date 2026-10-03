/** Contratos da API do backend TheyWork. Espelham `backend/app/schemas/`. */

export type AgentRole = 'CEO' | 'CTO' | 'CMO' | 'CFO' | 'RA' | 'SUBAGENT';
export type AgentType = 'CHIEF' | 'SUBAGENT';
export type AgentStatus = 'IDLE' | 'WORKING' | 'BLOCKED' | 'TERMINATED';
export type ResourceStatus = 'HEALTHY' | 'WARNING' | 'CRITICAL';
export type TaskComplexity = 'TRIVIAL' | 'SIMPLE' | 'MODERATE' | 'COMPLEX' | 'CRITICAL';
export type ReasoningStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
export type ReasoningStepType = 'THOUGHT' | 'ACTION' | 'OBSERVATION' | 'CONCLUSION';
export type CommunicationKind =
  'DIRECTIVE' | 'ANALYSIS' | 'DECISION' | 'QUESTION' | 'ANSWER' | 'REPORT' | 'ESCALATION';

/** Estados visuais do avatar; derivado no backend em `game_service._activity`. */
export type AgentActivity = 'IDLE' | 'THINKING' | 'WORKING' | 'BLOCKED' | 'TERMINATED';

export interface ResourceStatusResponse {
  timestamp: string;
  status: ResourceStatus;
  narrative: string;
  ram_limit_mb: number;
  ram_total_mb: number;
  ram_used_mb: number;
  ram_allocatable_mb: number;
  ram_usage_ratio: number;
  vram_limit_mb: number;
  vram_total_mb: number;
  vram_used_mb: number;
  vram_allocatable_mb: number;
  vram_usage_ratio: number;
  gpu_detected: boolean;
  cpu_percent: number;
  queued_hirings: number;
  active_subagents: number;
  max_concurrent_subagents: number;
}

export interface NatureAlert {
  code: string;
  severity: ResourceStatus;
  message: string;
  narrative: string;
}

export interface NatureAlertsResponse {
  total: number;
  status: ResourceStatus;
  alerts: NatureAlert[];
}

export interface AgentRead {
  id: string;
  name: string;
  role: AgentRole;
  agent_type: AgentType;
  status: AgentStatus;
  job_title: string | null;
  model_name: string | null;
  estimated_ram_mb: number;
  reports_to_id: string | null;
  created_at: string;
  terminated_at: string | null;
}

export interface ReasoningStepRead {
  id: number;
  sequence: number;
  step_type: ReasoningStepType;
  content: string;
  model_name: string | null;
  tokens: number;
  duration_ms: number;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ReasoningSessionRead {
  id: string;
  agent_id: string | null;
  thread_id: string | null;
  task: string;
  status: ReasoningStatus;
  complexity: TaskComplexity;
  model_name: string | null;
  step_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  duration_ms: number;
  conclusion: string | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface ReasoningSessionDetail extends ReasoningSessionRead {
  steps: ReasoningStepRead[];
}

export interface ReasoningSessionsResponse {
  total: number;
  sessions: ReasoningSessionRead[];
}

export type FlowNodeType = 'TASK' | ReasoningStepType;

export interface ReasoningFlowNode {
  id: string;
  type: FlowNodeType;
  label: string;
  content: string;
  icon: string;
  color: string;
  column: number;
  row: number;
  payload: Record<string, unknown>;
  meta: Record<string, unknown>;
}

export interface ReasoningFlowEdge {
  id: string;
  source: string;
  target: string;
  kind: 'SEQUENCE' | 'LOOP';
  label: string;
}

export interface ReasoningFlowResponse {
  nodes: ReasoningFlowNode[];
  edges: ReasoningFlowEdge[];
  meta: {
    session_id: string;
    agent_id: string | null;
    status: ReasoningStatus;
    step_count: number;
    total_tokens: number;
    duration_ms: number;
    conclusion: string | null;
    error: string | null;
    columns: string[];
    rows: number;
  };
}

export interface CommunicationRead {
  id: string;
  thread_id: string;
  kind: CommunicationKind;
  from_role: AgentRole;
  to_role: AgentRole | null;
  topic: string;
  content: string;
  rationale: string | null;
  verdict: string | null;
  confidence: number;
  created_at: string;
}

export interface CommunicationsResponse {
  total: number;
  communications: CommunicationRead[];
}
