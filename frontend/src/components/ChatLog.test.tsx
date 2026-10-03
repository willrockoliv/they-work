import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { useGameStore } from '@/store/gameStore';
import { makeAgent, makeGameState } from '@/test/fixtures';
import type { StepEventData } from '@/types/events';

import { ChatLog } from './ChatLog';

function step(agentName: string, content: string): StepEventData {
  return {
    id: 1,
    session_id: `session-${agentName}`,
    sequence: 1,
    step_type: 'THOUGHT',
    content,
    model_name: 'llama3.2:3b',
    tokens: 10,
    duration_ms: 100,
    payload: {},
    created_at: '2026-10-03T09:05:00+00:00',
  };
}

function seed(): void {
  const game = useGameStore.getState();
  game.hydrate(
    makeGameState([
      makeAgent(),
      makeAgent({ id: 'agent-2', name: 'Analista', agent_type: 'SUBAGENT', role: 'SUBAGENT' }),
    ]),
  );
  for (const [agentId, name] of [
    ['agent-1', 'CEO'],
    ['agent-2', 'Analista'],
  ] as const) {
    game.applyEvent({
      event: 'session.started',
      session_id: `session-${name}`,
      data: {
        id: `session-${name}`,
        agent_id: agentId,
        task: `Tarefa de ${name}`,
        status: 'RUNNING',
        model_name: 'llama3.2:3b',
        step_count: 0,
        total_tokens: 0,
        duration_ms: 0,
        conclusion: null,
        error: null,
      },
    });
    game.applyEvent({
      event: 'step',
      session_id: `session-${name}`,
      data: step(name, `Pensamento de ${name}`),
    });
  }
}

describe('ChatLog', () => {
  it('informa quando ainda não há comunicações', () => {
    render(<ChatLog />);
    expect(screen.getByText(/nenhuma comunicação registrada/i)).toBeInTheDocument();
  });

  it('lista as falas de todos os agentes', () => {
    seed();
    render(<ChatLog />);
    expect(screen.getByText(/Pensamento de CEO/)).toBeInTheDocument();
    expect(screen.getByText(/Pensamento de Analista/)).toBeInTheDocument();
  });

  it('filtra por agente', async () => {
    const user = userEvent.setup();
    seed();
    render(<ChatLog />);

    await user.selectOptions(screen.getByLabelText('Filtrar por agente'), 'agent-2');
    expect(screen.queryByText(/Pensamento de CEO/)).not.toBeInTheDocument();
    expect(screen.getByText(/Pensamento de Analista/)).toBeInTheDocument();
  });

  it('limpa o log', async () => {
    const user = userEvent.setup();
    seed();
    render(<ChatLog />);

    await user.click(screen.getByRole('button', { name: 'Limpar log' }));
    expect(useGameStore.getState().messages).toHaveLength(0);
  });
});
