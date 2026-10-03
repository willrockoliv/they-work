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
};
