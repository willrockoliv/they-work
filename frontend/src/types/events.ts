/** Mensagens do canal `/ws/game-state`. Espelham `backend/app/routes/ws.py`. */

import type { ReasoningStatus, ReasoningStepRead } from './api';
import type { GameAgent, GameClock, GameEconomy, GameState, Position } from './game';
import type { ResourceStatusResponse } from './api';

export interface SessionEventData {
  id: string;
  agent_id: string | null;
  task: string;
  status: ReasoningStatus;
  model_name: string | null;
  step_count: number;
  total_tokens: number;
  duration_ms: number;
  conclusion: string | null;
  error: string | null;
}

export interface StepEventData extends ReasoningStepRead {
  session_id: string;
}

export type GameEvent =
  | { event: 'game.snapshot'; data: GameState }
  | {
      event: 'game.tick';
      data: { clock: GameClock; resources: ResourceStatusResponse; economy: GameEconomy };
    }
  | { event: 'agent.joined'; agent_id: string; data: GameAgent }
  | { event: 'agent.left'; agent_id: string; data: GameAgent }
  | {
      event: 'agent.status';
      agent_id: string;
      data: Pick<GameAgent, 'activity' | 'status' | 'model_name' | 'reasoning'>;
    }
  | { event: 'agent.moved'; agent_id: string; data: Position }
  | { event: 'nature.status'; agent_id: string | null; data: ResourceStatusResponse }
  | { event: 'session.started'; session_id: string; data: SessionEventData }
  | { event: 'session.finished'; session_id: string; data: SessionEventData }
  | { event: 'step'; session_id: string; data: StepEventData }
  | { event: 'heartbeat' };

export type GameEventName = GameEvent['event'];

/** Guarda de tipo: descarta qualquer payload que não seja um evento conhecido. */
export function isGameEvent(value: unknown): value is GameEvent {
  return (
    typeof value === 'object' &&
    value !== null &&
    'event' in value &&
    typeof (value as { event: unknown }).event === 'string'
  );
}
