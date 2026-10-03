import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';
import { makeAgent, makeGameState } from '@/test/fixtures';

import { SidePanel } from './SidePanel';

vi.mock('@/services/api', () => ({
  api: {
    reasoningFlow: vi.fn().mockResolvedValue({
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
      ],
      edges: [],
      meta: {
        session_id: 's1',
        agent_id: 'agent-1',
        status: 'COMPLETED',
        step_count: 0,
        total_tokens: 0,
        duration_ms: 0,
        conclusion: null,
        error: null,
        columns: [],
        rows: 1,
      },
    }),
    sessionFlow: vi.fn(),
    agentHistory: vi.fn().mockResolvedValue({ total: 0, sessions: [] }),
  },
}));

describe('SidePanel', () => {
  it('convida a selecionar um agente quando nada está selecionado', () => {
    render(<SidePanel />);
    expect(screen.getByText(/clique num agente/i)).toBeInTheDocument();
  });

  it('mostra os dados do agente selecionado', () => {
    useGameStore.getState().hydrate(makeGameState());
    useUiStore.getState().selectAgent('agent-1');
    render(<SidePanel />);

    expect(screen.getByRole('heading', { name: 'CEO' })).toBeInTheDocument();
    expect(screen.getByText('Chief Executive Officer')).toBeInTheDocument();
    expect(screen.getByText('desk-ceo')).toBeInTheDocument();
    expect(screen.getByText(/ainda não produziu nenhum raciocínio/i)).toBeInTheDocument();
  });

  it('exibe a barra de progresso quando há raciocínio em curso', () => {
    const agente = makeAgent({
      activity: 'THINKING',
      reasoning: {
        session_id: 'session-1',
        status: 'RUNNING',
        task: 'Avaliar retenção de clientes',
        model_name: 'llama3.2:3b',
        step_count: 2,
        total_tokens: 48,
        progress: 0.5,
        elapsed_ms: 1500,
        conclusion: null,
        error: null,
        started_at: '2026-10-03T09:05:00+00:00',
      },
    });
    useGameStore.getState().hydrate(makeGameState([agente]));
    useUiStore.getState().selectAgent('agent-1');
    render(<SidePanel />);

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50');
    expect(screen.getByText('Avaliar retenção de clientes')).toBeInTheDocument();
  });

  it('troca de aba e fecha o painel', async () => {
    const user = userEvent.setup();
    useGameStore.getState().hydrate(makeGameState());
    useUiStore.getState().selectAgent('agent-1');
    render(<SidePanel />);

    await user.click(screen.getByRole('tab', { name: 'Histórico' }));
    expect(useUiStore.getState().panelTab).toBe('history');
    expect(await screen.findByText(/nenhuma tarefa registrada/i)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /fechar painel/i }));
    expect(useUiStore.getState().selectedAgentId).toBeNull();
  });
});
