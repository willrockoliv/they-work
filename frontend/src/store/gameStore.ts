import { create } from 'zustand';

import { CHAT_LOG_LIMIT, PAUSE_BUFFER_LIMIT } from '@/services/config';
import type { ConnectionState } from '@/services/socket';
import type {
  ChatHistoryMessage,
  ReasoningStepType,
  ResourceStatusResponse,
} from '@/types/api';
import type { GameEvent, RequestEventData, SessionEventData, StepEventData } from '@/types/events';
import type { GameAgent, GameClock, GameEconomy, GameState, OfficeLayout } from '@/types/game';
import type { GraphEdge, GraphTask } from '@/types/network';

export type MessageKind = ReasoningStepType | 'TASK' | 'SYSTEM';
export type NotificationSeverity = 'info' | 'success' | 'warning' | 'critical';

export interface ChatMessage {
  id: string;
  agentId: string | null;
  agentName: string;
  kind: MessageKind;
  text: string;
  at: string;
}

export interface Notification {
  id: string;
  severity: NotificationSeverity;
  title: string;
  body: string;
  at: string;
}

export interface Bubble {
  text: string;
  kind: MessageKind;
  at: number;
}

export type SimulationSpeed = 1 | 2 | 4;

export interface GameStoreState {
  layout: OfficeLayout | null;
  agents: Record<string, GameAgent>;
  order: string[];
  clock: GameClock | null;
  resources: ResourceStatusResponse | null;
  economy: GameEconomy | null;
  sessions: Record<string, SessionEventData>;
  liveSteps: Record<string, StepEventData[]>;
  bubbles: Record<string, Bubble>;
  messages: ChatMessage[];
  notifications: Notification[];
  connection: ConnectionState;
  paused: boolean;
  speed: SimulationSpeed;
  buffered: GameEvent[];
  revision: number;

  /** Rede corporativa: arestas, tarefas e pedidos recebidos ao vivo. */
  networkEdges: GraphEdge[];
  networkTasks: Record<string, GraphTask>;
  networkRequests: Record<string, RequestEventData>;
  networkRevision: number;

  hydrate: (state: GameState) => void;
  applyEvent: (event: GameEvent) => void;
  setConnection: (connection: ConnectionState) => void;
  setPaused: (paused: boolean) => void;
  togglePaused: () => void;
  setSpeed: (speed: SimulationSpeed) => void;
  dismissNotification: (id: string) => void;
  clearMessages: () => void;
  /** Insere falas anteriores ao log vivo, sem duplicar ids já conhecidos. */
  loadHistory: (history: ChatHistoryMessage[]) => void;
  reset: () => void;
}

let sequence = 0;
/** Identificador estável e monotônico — não depende de `crypto` nem do relógio. */
function nextId(prefix: string): string {
  sequence += 1;
  return `${prefix}-${sequence}`;
}

/** Teto da fila de arestas do grafo mantida em memória no cliente. */
const NETWORK_EDGE_LIMIT = 400;

const MESSAGE_PREFIX: Record<MessageKind, string> = {
  TASK: 'Tarefa',
  THOUGHT: 'Pensando',
  ACTION: 'Usando',
  OBSERVATION: 'Observou',
  CONCLUSION: 'Concluiu',
  SYSTEM: 'Sistema',
};

function initialState() {
  return {
    layout: null as OfficeLayout | null,
    agents: {} as Record<string, GameAgent>,
    order: [] as string[],
    clock: null as GameClock | null,
    resources: null as ResourceStatusResponse | null,
    economy: null as GameEconomy | null,
    sessions: {} as Record<string, SessionEventData>,
    liveSteps: {} as Record<string, StepEventData[]>,
    bubbles: {} as Record<string, Bubble>,
    messages: [] as ChatMessage[],
    notifications: [] as Notification[],
    connection: 'closed' as ConnectionState,
    paused: false,
    speed: 1 as SimulationSpeed,
    buffered: [] as GameEvent[],
    revision: 0,
    networkEdges: [] as GraphEdge[],
    networkTasks: {} as Record<string, GraphTask>,
    networkRequests: {} as Record<string, RequestEventData>,
    networkRevision: 0,
  };
}

function truncate(text: string, limit = 160): string {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean.length > limit ? `${clean.slice(0, limit - 1)}…` : clean;
}

export const useGameStore = create<GameStoreState>()((set, get) => {
  function pushMessage(
    draft: Pick<GameStoreState, 'messages' | 'bubbles'>,
    agentId: string | null,
    agentName: string,
    kind: MessageKind,
    text: string,
    at: string,
    id?: string,
  ): void {
    const message: ChatMessage = { id: id ?? nextId('msg'), agentId, agentName, kind, text, at };
    draft.messages = [...draft.messages, message].slice(-CHAT_LOG_LIMIT);
    if (agentId) {
      draft.bubbles = { ...draft.bubbles, [agentId]: { text, kind, at: Date.now() } };
    }
  }

  function notify(
    notifications: Notification[],
    severity: NotificationSeverity,
    title: string,
    body: string,
  ): Notification[] {
    const notification: Notification = {
      id: nextId('ntf'),
      severity,
      title,
      body,
      at: new Date().toISOString(),
    };
    return [...notifications, notification].slice(-8);
  }

  function reduce(state: GameStoreState, event: GameEvent): Partial<GameStoreState> {
    const draft = { messages: state.messages, bubbles: state.bubbles };

    switch (event.event) {
      case 'heartbeat':
        return {};

      case 'game.snapshot': {
        const agents: Record<string, GameAgent> = {};
        for (const agent of event.data.agents) agents[agent.id] = agent;
        return {
          layout: event.data.layout,
          agents,
          order: event.data.agents.map((agent) => agent.id),
          clock: event.data.clock,
          resources: event.data.resources,
          economy: event.data.economy,
          revision: state.revision + 1,
        };
      }

      case 'game.tick':
        return {
          clock: event.data.clock,
          resources: event.data.resources,
          economy: event.data.economy,
        };

      case 'agent.joined': {
        pushMessage(
          draft,
          event.agent_id,
          event.data.name,
          'SYSTEM',
          `${event.data.job_title ?? event.data.name} entrou na empresa.`,
          new Date().toISOString(),
        );
        return {
          agents: { ...state.agents, [event.agent_id]: event.data },
          order: state.order.includes(event.agent_id)
            ? state.order
            : [...state.order, event.agent_id],
          messages: draft.messages,
          bubbles: draft.bubbles,
          notifications: notify(
            state.notifications,
            'info',
            'Novo agente contratado',
            `${event.data.name} assumiu o posto ${event.data.seat_id ?? 'indefinido'}.`,
          ),
          revision: state.revision + 1,
        };
      }

      case 'agent.left': {
        const agents = { ...state.agents };
        delete agents[event.agent_id];
        const bubbles = { ...state.bubbles };
        delete bubbles[event.agent_id];
        pushMessage(
          { messages: draft.messages, bubbles },
          null,
          event.data.name,
          'SYSTEM',
          `${event.data.name} foi desligado.`,
          new Date().toISOString(),
        );
        return {
          agents,
          order: state.order.filter((id) => id !== event.agent_id),
          bubbles,
          messages: draft.messages,
          revision: state.revision + 1,
        };
      }

      case 'agent.status': {
        const current = state.agents[event.agent_id];
        if (!current) return {};
        const updated: GameAgent = { ...current, ...event.data };
        const blocked = event.data.status === 'BLOCKED' && current.status !== 'BLOCKED';
        return {
          agents: { ...state.agents, [event.agent_id]: updated },
          notifications: blocked
            ? notify(
                state.notifications,
                'warning',
                'Agente bloqueado',
                `${current.name} está impedido de avançar — verifique o orçamento da Natureza.`,
              )
            : state.notifications,
          revision: state.revision + 1,
        };
      }

      case 'agent.moved': {
        const current = state.agents[event.agent_id];
        if (!current) return {};
        return {
          agents: {
            ...state.agents,
            [event.agent_id]: { ...current, position: event.data, seat_id: event.data.seat_id },
          },
          revision: state.revision + 1,
        };
      }

      case 'nature.status': {
        const severity: NotificationSeverity =
          event.data.status === 'CRITICAL'
            ? 'critical'
            : event.data.status === 'WARNING'
              ? 'warning'
              : 'success';
        return {
          resources: event.data,
          notifications: notify(
            state.notifications,
            severity,
            `A Natureza está ${event.data.status}`,
            event.data.narrative,
          ),
        };
      }

      case 'session.started': {
        const agentId = event.data.agent_id;
        const agent = agentId ? state.agents[agentId] : undefined;
        pushMessage(
          draft,
          agentId,
          agent?.name ?? 'Agente',
          'TASK',
          event.data.task,
          new Date().toISOString(),
          `task-${event.data.id}`,
        );
        return {
          sessions: { ...state.sessions, [event.session_id]: event.data },
          liveSteps: { ...state.liveSteps, [event.session_id]: [] },
          agents:
            agentId && agent
              ? {
                  ...state.agents,
                  [agentId]: {
                    ...agent,
                    activity: 'THINKING',
                    reasoning: {
                      session_id: event.data.id,
                      status: event.data.status,
                      task: event.data.task,
                      model_name: event.data.model_name,
                      step_count: event.data.step_count,
                      total_tokens: event.data.total_tokens,
                      progress: 0,
                      elapsed_ms: 0,
                      conclusion: null,
                      error: null,
                      started_at: new Date().toISOString(),
                    },
                  },
                }
              : state.agents,
          messages: draft.messages,
          bubbles: draft.bubbles,
          revision: state.revision + 1,
        };
      }

      case 'step': {
        const session = state.sessions[event.data.session_id];
        const agentId = session?.agent_id ?? null;
        const agent = agentId ? state.agents[agentId] : undefined;
        pushMessage(
          draft,
          agentId,
          agent?.name ?? 'Agente',
          event.data.step_type,
          event.data.content,
          event.data.created_at,
          `step-${event.data.id}`,
        );
        const steps = state.liveSteps[event.data.session_id] ?? [];
        return {
          liveSteps: {
            ...state.liveSteps,
            [event.data.session_id]: [...steps, event.data],
          },
          agents:
            agentId && agent?.reasoning
              ? {
                  ...state.agents,
                  [agentId]: {
                    ...agent,
                    reasoning: {
                      ...agent.reasoning,
                      step_count: event.data.sequence,
                      total_tokens: agent.reasoning.total_tokens + event.data.tokens,
                    },
                  },
                }
              : state.agents,
          messages: draft.messages,
          bubbles: draft.bubbles,
          revision: state.revision + 1,
        };
      }

      case 'session.finished': {
        const agentId = event.data.agent_id;
        const agent = agentId ? state.agents[agentId] : undefined;
        const succeeded = event.data.status === 'COMPLETED';
        // O passo CONCLUSION já anunciou o desfecho feliz; só o fracasso vira fala.
        if (!succeeded) {
          pushMessage(
            draft,
            agentId,
            agent?.name ?? 'Agente',
            'SYSTEM',
            event.data.error ?? 'Sessão encerrada sem conclusão.',
            new Date().toISOString(),
            `fail-${event.data.id}`,
          );
        }
        return {
          sessions: { ...state.sessions, [event.session_id]: event.data },
          agents:
            agentId && agent
              ? {
                  ...state.agents,
                  [agentId]: {
                    ...agent,
                    activity: succeeded ? 'IDLE' : 'BLOCKED',
                    reasoning: agent.reasoning
                      ? {
                          ...agent.reasoning,
                          status: event.data.status,
                          step_count: event.data.step_count,
                          total_tokens: event.data.total_tokens,
                          elapsed_ms: event.data.duration_ms,
                          progress: 1,
                          conclusion: event.data.conclusion,
                          error: event.data.error,
                        }
                      : null,
                  },
                }
              : state.agents,
          notifications: notify(
            state.notifications,
            succeeded ? 'success' : 'warning',
            succeeded ? 'Entrega concluída' : 'Raciocínio interrompido',
            `${agent?.name ?? 'Um agente'}: ${truncate(
              event.data.conclusion ?? event.data.error ?? '',
              90,
            )}`,
          ),
          messages: draft.messages,
          bubbles: draft.bubbles,
          revision: state.revision + 1,
        };
      }

      case 'network.edge': {
        // O barramento pode reentregar uma aresta: a chave é o id, nunca a ordem.
        if (state.networkEdges.some((edge) => edge.id === event.data.id)) return {};
        return {
          networkEdges: [...state.networkEdges, event.data].slice(-NETWORK_EDGE_LIMIT),
          networkRevision: state.networkRevision + 1,
        };
      }

      case 'network.task':
        return {
          networkTasks: { ...state.networkTasks, [event.data.id]: event.data },
          networkRevision: state.networkRevision + 1,
        };

      case 'network.request': {
        const closed = event.data.status === 'COMPLETED' || event.data.status === 'FAILED';
        return {
          networkRequests: { ...state.networkRequests, [event.data.id]: event.data },
          networkRevision: state.networkRevision + 1,
          notifications: closed
            ? notify(
                state.notifications,
                event.data.status === 'COMPLETED' ? 'success' : 'warning',
                `Pedido ${event.data.status === 'COMPLETED' ? 'concluído' : 'encerrado'}`,
                `${event.data.topic}: ${truncate(event.data.narrative ?? '', 90)}`,
              )
            : state.notifications,
        };
      }

      default:
        return {};
    }
  }

  return {
    ...initialState(),

    hydrate: (state) => get().applyEvent({ event: 'game.snapshot', data: state }),

    applyEvent: (event) => {
      const state = get();
      if (state.paused && event.event !== 'game.snapshot') {
        set({ buffered: [...state.buffered, event].slice(-PAUSE_BUFFER_LIMIT) });
        return;
      }
      set(reduce(state, event));
    },

    setConnection: (connection) => set({ connection }),

    setPaused: (paused) => {
      if (paused) {
        set({ paused: true });
        return;
      }
      // Ao retomar, os eventos represados são reaplicados na ordem de chegada.
      const pending = get().buffered;
      set({ paused: false, buffered: [] });
      for (const event of pending) get().applyEvent(event);
    },

    togglePaused: () => get().setPaused(!get().paused),

    setSpeed: (speed) => set({ speed }),

    dismissNotification: (id) =>
      set((state) => ({ notifications: state.notifications.filter((n) => n.id !== id) })),

    clearMessages: () => set({ messages: [] }),

    loadHistory: (history) => {
      const known = new Set(get().messages.map((message) => message.id));
      const older: ChatMessage[] = history
        .filter((message) => !known.has(message.id))
        .map((message) => ({
          id: message.id,
          agentId: message.agent_id,
          agentName: message.agent_name,
          kind: message.kind,
          text: message.text,
          at: message.at,
        }));
      if (older.length === 0) return;
      set((state) => ({
        messages: [...older, ...state.messages]
          .sort((a, b) => Date.parse(a.at) - Date.parse(b.at))
          .slice(-CHAT_LOG_LIMIT),
      }));
    },

    reset: () => set(initialState()),
  };
});

export { MESSAGE_PREFIX };
