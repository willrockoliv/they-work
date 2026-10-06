import { describe, expect, it } from 'vitest';

import { useGameStore } from '@/store/gameStore';
import type { GraphEdge, GraphTask } from '@/types/network';

function edge(id: string): GraphEdge {
  return {
    id,
    request_id: 'req-1',
    task_id: null,
    sender_agent_id: 'cto',
    recipient_agent_id: 'dev',
    communication_type: 'DELEGATION',
    status: 'PENDING',
    summary: `aresta ${id}`,
    content: {},
    reasoning_session_id: null,
    created_at: null,
  };
}

function task(id: string, status: GraphTask['status']): GraphTask {
  return {
    id,
    request_id: 'req-1',
    parent_task_id: null,
    assigned_by_chief_id: 'cto',
    assigned_to_agent_id: 'dev',
    title: 'Frente de tecnologia',
    task_description: 'Desenhar a arquitetura',
    status,
    attempt: 1,
    quality_score: 0,
    decision: null,
    decision_rationale: null,
    report_summary: null,
    report_reasoning_session_id: null,
    review_reasoning_session_id: null,
  };
}

describe('gameStore — eventos da rede corporativa', () => {
  it('acumula arestas sem duplicar reentregas do barramento', () => {
    useGameStore.getState().reset();
    const { applyEvent } = useGameStore.getState();

    applyEvent({ event: 'network.edge', data: edge('e1') });
    applyEvent({ event: 'network.edge', data: edge('e2') });
    applyEvent({ event: 'network.edge', data: edge('e1') });

    expect(useGameStore.getState().networkEdges.map((item) => item.id)).toEqual(['e1', 'e2']);
  });

  it('indexa tarefas por id e sobrescreve com o estado mais recente', () => {
    useGameStore.getState().reset();
    const { applyEvent } = useGameStore.getState();

    applyEvent({ event: 'network.task', data: task('t1', 'PENDING') });
    applyEvent({ event: 'network.task', data: task('t1', 'COMPLETED') });

    const tasks = useGameStore.getState().networkTasks;
    expect(Object.keys(tasks)).toEqual(['t1']);
    expect(tasks.t1?.status).toBe('COMPLETED');
  });

  it('notifica apenas quando o pedido é encerrado', () => {
    useGameStore.getState().reset();
    const { applyEvent } = useGameStore.getState();

    applyEvent({
      event: 'network.request',
      data: { id: 'req-1', topic: 'Fundar', status: 'IN_EXECUTION', outcome: null, narrative: null },
    });
    expect(useGameStore.getState().notifications).toHaveLength(0);

    applyEvent({
      event: 'network.request',
      data: {
        id: 'req-1',
        topic: 'Fundar',
        status: 'COMPLETED',
        outcome: 'APPROVE',
        narrative: 'Tudo encerrado.',
      },
    });
    const notifications = useGameStore.getState().notifications;
    expect(notifications).toHaveLength(1);
    expect(notifications[0]?.severity).toBe('success');
  });

  it('incrementa a revisão da rede a cada mutação', () => {
    useGameStore.getState().reset();
    const { applyEvent } = useGameStore.getState();

    applyEvent({ event: 'network.edge', data: edge('e1') });
    applyEvent({ event: 'network.task', data: task('t1', 'PENDING') });

    expect(useGameStore.getState().networkRevision).toBe(2);
  });
});
