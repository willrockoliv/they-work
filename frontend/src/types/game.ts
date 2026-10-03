/** Contratos do mundo 2D. Espelham `backend/app/schemas/game.py`. */

import type {
  AgentActivity,
  AgentRole,
  AgentStatus,
  AgentType,
  ReasoningStatus,
  ResourceStatusResponse,
} from './api';

export type RoomKind = 'EXECUTIVE' | 'MEETING' | 'WORKSTATIONS' | 'BENCH' | 'SERVER';
export type SeatKind = 'CHIEF' | 'MEETING' | 'WORKSTATION' | 'BENCH';

export interface Room {
  id: string;
  label: string;
  kind: RoomKind;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Seat {
  id: string;
  kind: SeatKind;
  room_id: string;
  x: number;
  y: number;
  index: number;
  role: AgentRole | null;
}

export interface Hotspot {
  id: string;
  room_id: string;
  label: string;
  x: number;
  y: number;
}

export interface OfficeLayout {
  tile_size: number;
  columns: number;
  rows: number;
  rooms: Room[];
  seats: Seat[];
  hotspots: Hotspot[];
}

export interface Position {
  agent_id: string;
  seat_id: string | null;
  x: number;
  y: number;
  target_x: number;
  target_y: number;
  manual: boolean;
}

export interface AgentReasoning {
  session_id: string;
  status: ReasoningStatus;
  task: string;
  model_name: string | null;
  step_count: number;
  total_tokens: number;
  progress: number;
  elapsed_ms: number;
  conclusion: string | null;
  error: string | null;
  started_at: string;
}

export interface GameAgent {
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
  activity: AgentActivity;
  seat_id: string | null;
  room_id: string | null;
  position: Position | null;
  reasoning: AgentReasoning | null;
}

export interface GameClock {
  day: number;
  hour: number;
  minute: number;
  label: string;
  elapsed_seconds: number;
}

export interface GameEconomy {
  sessions: number;
  delivered: number;
  total_tokens: number;
  cost_mb_s: number;
  revenue_tokens: number;
  roi: number;
}

export interface GameState {
  clock: GameClock;
  resources: ResourceStatusResponse;
  economy: GameEconomy;
  layout: OfficeLayout;
  agents: GameAgent[];
}
