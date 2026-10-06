import type {
  AgentRead,
  CommunicationsResponse,
  NatureAlertsResponse,
  ReasoningFlowResponse,
  ReasoningSessionDetail,
  ReasoningSessionsResponse,
  ResourceStatusResponse,
} from '@/types/api';
import type { GameState, OfficeLayout, Position } from '@/types/game';
import type {
  BootstrapResponse,
  InitialRequestsResponse,
  RequestDetailResponse,
  RequestGraphResponse,
  RunCycleResponse,
  StartCycleResponse,
} from '@/types/network';

import { request } from './http';

export interface AgentsStatusResponse {
  total: number;
  chiefs: AgentRead[];
  subagents: AgentRead[];
}

export const api = {
  gameState: (includeTerminated = false) =>
    request<GameState>('/game/state', { query: { include_terminated: includeTerminated } }),

  officeMap: () => request<OfficeLayout>('/game/map'),

  agents: () => request<AgentsStatusResponse>('/agents/status'),

  position: (agentId: string) => request<Position>(`/agents/${agentId}/position`),

  move: (agentId: string, x: number, y: number) =>
    request<Position>(`/agents/${agentId}/move`, { method: 'POST', body: { x, y } }),

  recall: (agentId: string) => request<Position>(`/agents/${agentId}/recall`, { method: 'POST' }),

  reasoningFlow: (agentId: string) =>
    request<ReasoningFlowResponse>(`/agents/${agentId}/reasoning-flow`),

  sessionFlow: (sessionId: string) =>
    request<ReasoningFlowResponse>(`/reasoning/sessions/${sessionId}/flow`),

  session: (sessionId: string) =>
    request<ReasoningSessionDetail>(`/reasoning/sessions/${sessionId}`),

  agentHistory: (agentId: string, limit = 10) =>
    request<ReasoningSessionsResponse>('/reasoning/sessions', {
      query: { agent_id: agentId, limit },
    }),

  resources: () => request<ResourceStatusResponse>('/resources/status'),

  alerts: () => request<NatureAlertsResponse>('/nature/alerts'),

  communications: (limit = 50) =>
    request<CommunicationsResponse>('/council/communications', { query: { limit } }),

  // --- Rede corporativa (Fase 5) ---

  companyStatus: () => request<BootstrapResponse>('/company/status'),

  bootstrapCompany: () =>
    request<BootstrapResponse>('/company/bootstrap', { method: 'POST' }),

  submitRequest: (topic: string, description: string) =>
    request<RequestDetailResponse>('/council/request-action', {
      method: 'POST',
      body: { topic, description, submitted_by: 'OBSERVER', auto_deliberate: true },
    }),

  requests: (limit = 25) =>
    request<InitialRequestsResponse>('/council/requests', { query: { limit } }),

  requestDetail: (requestId: string) =>
    request<RequestDetailResponse>(`/council/requests/${requestId}`),

  requestGraph: (requestId: string) =>
    request<RequestGraphResponse>(`/council/requests/${requestId}/graph`),

  runCycle: (requestId: string) =>
    request<RunCycleResponse>(`/council/requests/${requestId}/run-cycle`, { method: 'POST' }),

  /** Dispara o turno em segundo plano; o progresso chega pelos eventos `network.*`. */
  startCycle: (requestId: string) =>
    request<StartCycleResponse>(`/council/requests/${requestId}/start`, { method: 'POST' }),
};
