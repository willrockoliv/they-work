import type { ResourceStatusResponse } from '@/types/api';
import type { GameAgent, GameState, OfficeLayout } from '@/types/game';

export const layout: OfficeLayout = {
  tile_size: 32,
  columns: 40,
  rows: 24,
  rooms: [
    { id: 'executive', label: 'Diretoria', kind: 'EXECUTIVE', x: 1, y: 1, width: 14, height: 10 },
    { id: 'floor', label: 'Estações', kind: 'WORKSTATIONS', x: 1, y: 12, width: 27, height: 11 },
  ],
  seats: [
    { id: 'desk-ceo', kind: 'CHIEF', room_id: 'executive', x: 3, y: 3, index: 0, role: 'CEO' },
    { id: 'station-0', kind: 'WORKSTATION', room_id: 'floor', x: 3, y: 15, index: 0, role: null },
  ],
  hotspots: [{ id: 'hotspot-executive', room_id: 'executive', label: 'Diretoria', x: 8, y: 6 }],
};

export const resources: ResourceStatusResponse = {
  timestamp: '2026-10-03T12:00:00+00:00',
  status: 'HEALTHY',
  narrative: 'A infraestrutura respira com folga.',
  ram_limit_mb: 16384,
  ram_total_mb: 16384,
  ram_used_mb: 4000,
  ram_allocatable_mb: 10336,
  ram_usage_ratio: 0.24,
  vram_limit_mb: 4096,
  vram_total_mb: 4096,
  vram_used_mb: 500,
  vram_allocatable_mb: 3084,
  vram_usage_ratio: 0.12,
  gpu_detected: false,
  cpu_percent: 12.5,
  queued_hirings: 0,
  active_subagents: 1,
  max_concurrent_subagents: 4,
};

export function makeAgent(overrides: Partial<GameAgent> = {}): GameAgent {
  const id = overrides.id ?? 'agent-1';
  return {
    id,
    name: 'CEO',
    role: 'CEO',
    agent_type: 'CHIEF',
    status: 'IDLE',
    job_title: 'Chief Executive Officer',
    model_name: 'llama3.2:3b',
    estimated_ram_mb: 3000,
    reports_to_id: null,
    created_at: '2026-10-03T09:00:00+00:00',
    activity: 'IDLE',
    seat_id: 'desk-ceo',
    room_id: 'executive',
    position: {
      agent_id: id,
      seat_id: 'desk-ceo',
      x: 3,
      y: 3,
      target_x: 3,
      target_y: 3,
      manual: false,
    },
    reasoning: null,
    ...overrides,
  };
}

export function makeGameState(agents: GameAgent[] = [makeAgent()]): GameState {
  return {
    clock: { day: 1, hour: 9, minute: 30, label: '09:30', elapsed_seconds: 30 },
    resources,
    economy: {
      sessions: 2,
      delivered: 1,
      total_tokens: 1200,
      cost_mb_s: 48.5,
      revenue_tokens: 800,
      roi: 0.0206,
    },
    layout,
    agents,
  };
}
