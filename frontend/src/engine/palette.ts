/** Paleta de 16 bits do escritório. Todas as cores do canvas saem daqui. */

import type { AgentActivity, AgentRole } from '@/types/api';
import type { RoomKind } from '@/types/game';

export type ThemeName = 'dark' | 'light';

/** Cores que mudam com o tema; os acentos por papel e por estado são comuns aos dois. */
export interface SurfacePalette {
  background: number;
  floor: number;
  floorAlt: number;
  wall: number;
  text: number;
  textMuted: number;
  bubble: number;
  roomFill: number;
  /** Quanto do acento do cômodo tinge o piso dele. */
  roomTint: number;
}

export const THEMES: Record<ThemeName, SurfacePalette> = {
  dark: {
    background: 0x0b1120,
    floor: 0x1e293b,
    floorAlt: 0x243044,
    wall: 0x334155,
    text: 0xe2e8f0,
    textMuted: 0x94a3b8,
    bubble: 0x0f172a,
    roomFill: 0x15203a,
    roomTint: 0.16,
  },
  light: {
    background: 0xeef2f8,
    floor: 0xf8fafc,
    floorAlt: 0xe6ecf5,
    wall: 0xcbd5e1,
    text: 0x0f172a,
    textMuted: 0x51607a,
    bubble: 0xffffff,
    roomFill: 0xffffff,
    roomTint: 0.1,
  },
};

export const PALETTE = {
  deskTop: 0x7c5c3e,
  deskEdge: 0x5a4229,
  monitor: 0x0ea5e9,
  chair: 0x3f4a5c,
  selection: 0xfacc15,
} as const;

export const ROOM_COLORS: Record<RoomKind, { accent: number }> = {
  EXECUTIVE: { accent: 0x6366f1 },
  MEETING: { accent: 0x0ea5e9 },
  WORKSTATIONS: { accent: 0x14b8a6 },
  BENCH: { accent: 0xa855f7 },
  SERVER: { accent: 0xf97316 },
};

export const ROLE_COLORS: Record<AgentRole, number> = {
  CEO: 0xfacc15,
  CTO: 0x6366f1,
  CMO: 0xec4899,
  CFO: 0x22c55e,
  RA: 0x0ea5e9,
  SUBAGENT: 0x94a3b8,
};

export const ACTIVITY_COLORS: Record<AgentActivity, number> = {
  IDLE: 0x64748b,
  THINKING: 0x6366f1,
  WORKING: 0xf59e0b,
  BLOCKED: 0xef4444,
  TERMINATED: 0x475569,
};

/** Glifo exibido acima da cabeça do avatar em cada estado. */
export const ACTIVITY_GLYPHS: Record<AgentActivity, string> = {
  IDLE: '',
  THINKING: '…',
  WORKING: '⚙',
  BLOCKED: '!',
  TERMINATED: '×',
};

export const STEP_COLORS: Record<string, number> = {
  TASK: 0x64748b,
  THOUGHT: 0x6366f1,
  ACTION: 0xf59e0b,
  OBSERVATION: 0x0ea5e9,
  CONCLUSION: 0x22c55e,
  SYSTEM: 0x94a3b8,
};
