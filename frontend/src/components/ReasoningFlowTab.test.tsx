import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useGameStore } from '@/store/gameStore';
import { makeAgent, makeGameState } from '@/test/fixtures';
import type { ReasoningFlowResponse } from '@/types/api';

import { ReasoningFlowTab } from './ReasoningFlowTab';

// `vi.mock` é içado para o topo do arquivo: a fábrica não pode fechar sobre
// variáveis do módulo, por isso o fluxograma é construído dentro dela.
vi.mock('@/services/api', () => {
  const flow: ReasoningFlowResponse = {
    nodes: [
      {
        id: 'task',
        type: 'TASK',
        label: 'Tarefa',
        content: 'Avaliar retenção',
        icon: 'clipboard',
        color: '#64748b',
        column: 0,
        row: 0,
        payload: {},
        meta: {},
      },
      {
        id: 'step-1',
        type: 'THOUGHT',
        label: 'Pensamento 1',
        content: 'Preciso dos dados de churn.',
        icon: 'brain',
        color: '#6366f1',
        column: 1,
        row: 0,
        payload: {},
        meta: { tokens: 12, duration_ms: 240 },
      },
    ],
    edges: [
      { id: 'edge-task-step-1', source: 'task', target: 'step-1', kind: 'SEQUENCE', label: '' },
    ],
    meta: {
      session_id: 'session-1',
      agent_id: 'agent-1',
      status: 'COMPLETED',
      step_count: 1,
      total_tokens: 12,
      duration_ms: 240,
      conclusion: 'Reter os clientes premium.',
      error: null,
      columns: [],
      rows: 1,
    },
  };
  return {
    api: {
      reasoningFlow: vi.fn().mockResolvedValue(flow),
      sessionFlow: vi.fn().mockResolvedValue(flow),
    },
  };
});

const comRaciocinio = makeAgent({
  activity: 'THINKING',
  reasoning: {
    session_id: 'session-1',
    status: 'RUNNING',
    task: 'Avaliar retenção',
    model_name: 'llama3.2:3b',
    step_count: 1,
    total_tokens: 12,
    progress: 0.25,
    elapsed_ms: 240,
    conclusion: null,
    error: null,
    started_at: '2026-10-03T09:05:00+00:00',
  },
});

describe('ReasoningFlowTab', () => {
  it('renderiza o fluxograma vindo da API', async () => {
    useGameStore.getState().hydrate(makeGameState());
    render(<ReasoningFlowTab agent={makeAgent()} />);

    expect(await screen.findByText('Pensamento 1')).toBeInTheDocument();
    expect(screen.getByText('Preciso dos dados de churn.')).toBeInTheDocument();
    expect(screen.getByText('Reter os clientes premium.')).toBeInTheDocument();
  });

  it('não entra em loop de render quando o agente tem sessão ao vivo', async () => {
    // Regressão: um seletor que devolvia `[]` novo a cada chamada estourava o
    // `useSyncExternalStore` com "Maximum update depth exceeded".
    useGameStore.getState().hydrate(makeGameState([comRaciocinio]));
    render(<ReasoningFlowTab agent={comRaciocinio} />);

    expect(await screen.findByText('Pensamento 1')).toBeInTheDocument();
  });

  it('prefere os passos ao vivo enquanto a sessão corre', async () => {
    const game = useGameStore.getState();
    game.hydrate(makeGameState([comRaciocinio]));
    game.applyEvent({
      event: 'session.started',
      session_id: 'session-1',
      data: {
        id: 'session-1',
        agent_id: 'agent-1',
        task: 'Avaliar retenção',
        status: 'RUNNING',
        model_name: 'llama3.2:3b',
        step_count: 0,
        total_tokens: 0,
        duration_ms: 0,
        conclusion: null,
        error: null,
      },
    });
    for (const sequence of [1, 2]) {
      game.applyEvent({
        event: 'step',
        session_id: 'session-1',
        data: {
          id: sequence,
          session_id: 'session-1',
          sequence,
          step_type: sequence === 1 ? 'THOUGHT' : 'ACTION',
          content: `Passo ao vivo ${sequence}`,
          model_name: 'llama3.2:3b',
          tokens: 5,
          duration_ms: 50,
          payload: {},
          created_at: '2026-10-03T09:05:00+00:00',
        },
      });
    }

    render(<ReasoningFlowTab agent={comRaciocinio} />);
    expect(await screen.findByText('Passo ao vivo 2')).toBeInTheDocument();
  });
});
