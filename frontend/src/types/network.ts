/** Contratos da rede corporativa (Fase 5). Espelham `backend/app/schemas/network.py`. */

import type { AgentRead, AgentRole } from './api';

/** Estado da fundação da empresa: sem Chiefs, nenhum pedido pode ser aceito. */
export interface BootstrapResponse {
  created: number;
  total: number;
  profiles: number;
  chiefs: AgentRead[];
}

export type InitialRequestStatus =
  | 'PROPOSED'
  | 'DELIBERATING'
  | 'IN_EXECUTION'
  | 'AWAITING_FEEDBACK'
  | 'COMPLETED'
  | 'FAILED';

export type CommunicationType =
  | 'REQUEST'
  | 'OPINION'
  | 'COORDINATION'
  | 'AGENT_REQUEST'
  | 'AGENT_CREATED'
  | 'DELEGATION'
  | 'REPORT'
  | 'CONSULTATION'
  | 'ESCALATION'
  | 'DECISION';

export type CommunicationStatus = 'PENDING' | 'ACKNOWLEDGED' | 'PROCESSED';

export type TaskStatus =
  | 'PENDING'
  | 'ACKNOWLEDGED'
  | 'IN_PROGRESS'
  | 'AWAITING_REVIEW'
  | 'COMPLETED'
  | 'REJECTED'
  | 'CANCELLED';

export type ChiefDecision = 'APPROVE' | 'REJECT' | 'MODIFY' | 'CONSULT_PEERS' | 'ESCALATE';

export interface InitialRequestRead {
  id: string;
  topic: string;
  description: string;
  submitted_by: string;
  status: InitialRequestStatus;
  thread_id: string | null;
  outcome: string | null;
  narrative: string | null;
  current_state: { milestones?: { kind: string; at: string }[] };
  created_at: string;
  resolved_at: string | null;
}

export interface InitialRequestsResponse {
  total: number;
  requests: InitialRequestRead[];
}

/** Nó do grafo: um agente ou o observador humano (`id === 'observer'`). */
export interface GraphNode {
  id: string;
  name: string;
  role: string;
  agent_type: string;
  status: string;
  reports_to: string | null;
}

export interface GraphEdge {
  id: string;
  request_id: string;
  task_id: string | null;
  sender_agent_id: string | null;
  recipient_agent_id: string | null;
  communication_type: CommunicationType;
  status: CommunicationStatus;
  summary: string;
  content: Record<string, unknown>;
  reasoning_session_id: string | null;
  created_at: string | null;
}

export interface GraphTask {
  id: string;
  request_id: string;
  parent_task_id: string | null;
  assigned_by_chief_id: string | null;
  assigned_to_agent_id: string | null;
  title: string;
  task_description: string;
  status: TaskStatus;
  attempt: number;
  quality_score: number;
  decision: ChiefDecision | null;
  decision_rationale: string | null;
  report_summary: string | null;
  report_reasoning_session_id: string | null;
  review_reasoning_session_id: string | null;
}

export interface RequestGraphResponse {
  request_id: string;
  topic: string;
  status: InitialRequestStatus;
  nodes: GraphNode[];
  edges: GraphEdge[];
  tasks: GraphTask[];
}

export interface RequestDetailResponse {
  request: InitialRequestRead;
  graph: RequestGraphResponse;
}

export interface ReviewDecisionResponse {
  task: Record<string, unknown> & { id: string; title: string; status: TaskStatus };
  decision: ChiefDecision;
  rationale: string;
  quality_score: number;
  achievement_ratio: number;
  risk_level: string;
  assessment: Record<string, unknown>;
  review_reasoning_session_id: string | null;
  consulted_roles: AgentRole[];
  escalated_to_ceo: boolean;
}

export interface RunCycleResponse {
  request: InitialRequestRead;
  executed_tasks: number;
  reviews: ReviewDecisionResponse[];
  graph: RequestGraphResponse;
}

export interface StartCycleResponse {
  request: InitialRequestRead;
  /** `false` quando já havia um turno em andamento para este pedido. */
  started: boolean;
}
