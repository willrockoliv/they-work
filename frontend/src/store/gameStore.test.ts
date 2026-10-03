import { describe, expect, it } from 'vitest';

import { makeAgent, makeGameState } from '@/test/fixtures';
import type { SessionEventData, StepEventData } from '@/types/events';

import { useGameStore } from './gameStore';

function store() {
  return useGameStore.getState();
}

function session(overrides: Partial<SessionEventData> = {}): SessionEventData {
  return {
    id: 'session-1',
    agent_id: 'agent-1',
    task: 'Avaliar retenção de clientes',
    status: 'RUNNING',
    model_name: 'llama3.2:3b',
    step_count: 0,
    total_tokens: 0,
    duration_ms: 0,
    conclusion: null,
    error: null,
    ...overrides,
  };
}

function step(overrides: Partial<StepEventData> = {}): StepEventData {
  return {
    id: 1,
    session_id: 'session-1',
    sequence: 1,
    step_type: 'THOUGHT',
    content: 'Preciso dos dados de churn.',
    model_name: 'llama3.2:3b',
    tokens: 12,
    duration_ms: 240,
    payload: {},
    created_at: '2026-10-03T09:05:00+00:00',
    ...overrides,
  };
}

describe('gameStore', () => {
  it('hidrata o mundo a partir do snapshot', () => {
    store().hydrate(makeGameState());
    const state = store();
    expect(state.order).toEqual(['agent-1']);
    expect(state.agents['agent-1']?.name).toBe('CEO');
    expect(state.layout?.columns).toBe(40);
    expect(state.clock?.label).toBe('09:30');
  });

  it('adiciona e remove agentes conforme os eventos do mundo', () => {
    store().hydrate(makeGameState());
    const novo = makeAgent({ id: 'agent-2', name: 'Analista', agent_type: 'SUBAGENT' });

    store().applyEvent({ event: 'agent.joined', agent_id: 'agent-2', data: novo });
    expect(store().order).toEqual(['agent-1', 'agent-2']);
    expect(store().notifications.at(-1)?.title).toBe('Novo agente contratado');

    store().applyEvent({ event: 'agent.left', agent_id: 'agent-2', data: novo });
    expect(store().order).toEqual(['agent-1']);
    expect(store().agents['agent-2']).toBeUndefined();
  });

  it('avisa quando um agente fica bloqueado', () => {
    store().hydrate(makeGameState());
    store().applyEvent({
      event: 'agent.status',
      agent_id: 'agent-1',
      data: { activity: 'BLOCKED', status: 'BLOCKED', model_name: null, reasoning: null },
    });
    expect(store().agents['agent-1']?.activity).toBe('BLOCKED');
    expect(store().notifications.at(-1)?.severity).toBe('warning');
  });

  it('ignora movimento de agente desconhecido', () => {
    store().hydrate(makeGameState());
    const revisao = store().revision;
    store().applyEvent({
      event: 'agent.moved',
      agent_id: 'fantasma',
      data: {
        agent_id: 'fantasma',
        seat_id: null,
        x: 1,
        y: 1,
        target_x: 1,
        target_y: 1,
        manual: true,
      },
    });
    expect(store().revision).toBe(revisao);
  });

  it('transforma o ciclo ReAct em falas e progresso', () => {
    store().hydrate(makeGameState());
    store().applyEvent({ event: 'session.started', session_id: 'session-1', data: session() });
    expect(store().agents['agent-1']?.activity).toBe('THINKING');

    store().applyEvent({ event: 'step', session_id: 'session-1', data: step() });
    expect(store().liveSteps['session-1']).toHaveLength(1);
    expect(store().messages.at(-1)?.kind).toBe('THOUGHT');
    expect(store().bubbles['agent-1']?.text).toContain('churn');

    store().applyEvent({
      event: 'session.finished',
      session_id: 'session-1',
      data: session({
        status: 'COMPLETED',
        conclusion: 'Reter os clientes premium.',
        step_count: 1,
      }),
    });
    expect(store().agents['agent-1']?.activity).toBe('IDLE');
    expect(store().agents['agent-1']?.reasoning?.progress).toBe(1);
    expect(store().notifications.at(-1)?.severity).toBe('success');
    // O passo CONCLUSION já falou pelo agente: o fim da sessão não duplica a fala.
    expect(store().messages.filter((message) => message.kind === 'CONCLUSION')).toHaveLength(0);
  });

  it('o fracasso da sessão vira fala e alerta', () => {
    store().hydrate(makeGameState());
    store().applyEvent({ event: 'session.started', session_id: 'session-1', data: session() });
    store().applyEvent({
      event: 'session.finished',
      session_id: 'session-1',
      data: session({ status: 'FAILED', error: 'Modelo indisponível.' }),
    });

    expect(store().agents['agent-1']?.activity).toBe('BLOCKED');
    expect(store().messages.at(-1)?.text).toBe('Modelo indisponível.');
    expect(store().notifications.at(-1)?.severity).toBe('warning');
  });

  it('alerta quando a Natureza muda de regime', () => {
    store().hydrate(makeGameState());
    const critico = { ...makeGameState().resources, status: 'CRITICAL' as const };
    store().applyEvent({ event: 'nature.status', agent_id: null, data: critico });
    expect(store().resources?.status).toBe('CRITICAL');
    expect(store().notifications.at(-1)?.severity).toBe('critical');
  });

  it('represa eventos enquanto pausado e reaplica ao retomar', () => {
    store().hydrate(makeGameState());
    store().setPaused(true);

    store().applyEvent({ event: 'session.started', session_id: 'session-1', data: session() });
    store().applyEvent({ event: 'step', session_id: 'session-1', data: step() });

    expect(store().buffered).toHaveLength(2);
    expect(store().agents['agent-1']?.activity).toBe('IDLE');

    store().setPaused(false);
    expect(store().buffered).toHaveLength(0);
    expect(store().agents['agent-1']?.activity).toBe('THINKING');
    expect(store().liveSteps['session-1']).toHaveLength(1);
  });

  it('o heartbeat não altera o estado', () => {
    store().hydrate(makeGameState());
    const antes = store().revision;
    store().applyEvent({ event: 'heartbeat' });
    expect(store().revision).toBe(antes);
  });

  it('o tick atualiza relógio, recursos e economia sem tocar nos agentes', () => {
    store().hydrate(makeGameState());
    const snapshot = makeGameState();
    store().applyEvent({
      event: 'game.tick',
      data: {
        clock: { day: 2, hour: 11, minute: 0, label: '11:00', elapsed_seconds: 660 },
        resources: snapshot.resources,
        economy: { ...snapshot.economy, delivered: 7 },
      },
    });
    expect(store().clock?.day).toBe(2);
    expect(store().economy?.delivered).toBe(7);
    expect(store().order).toEqual(['agent-1']);
  });
});
