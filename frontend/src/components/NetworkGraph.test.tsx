import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { NetworkGraph } from '@/components/NetworkGraph';
import type { GraphEdge, RequestGraphResponse } from '@/types/network';

function edge(id: string, from: string | null, to: string, summary: string): GraphEdge {
  return {
    id,
    request_id: 'req-1',
    task_id: null,
    sender_agent_id: from,
    recipient_agent_id: to,
    communication_type: 'DELEGATION',
    status: 'PENDING',
    summary,
    content: { rationale: 'Porque sim.' },
    reasoning_session_id: null,
    created_at: null,
  };
}

const GRAPH: RequestGraphResponse = {
  request_id: 'req-1',
  topic: 'Fundar',
  status: 'IN_EXECUTION',
  nodes: [
    {
      id: 'observer',
      name: 'OBSERVER',
      role: 'OBSERVER',
      agent_type: 'OBSERVER',
      status: 'IDLE',
      reports_to: null,
    },
    { id: 'ceo', name: 'CEO', role: 'CEO', agent_type: 'CHIEF', status: 'IDLE', reports_to: null },
    { id: 'cto', name: 'CTO', role: 'CTO', agent_type: 'CHIEF', status: 'IDLE', reports_to: 'ceo' },
    {
      id: 'dev',
      name: 'Engenheiro de Software #1',
      role: 'SUBAGENT',
      agent_type: 'SUBAGENT',
      status: 'IDLE',
      reports_to: 'cto',
    },
  ],
  edges: [edge('e1', 'cto', 'dev', 'Frente de tecnologia')],
  tasks: [],
};

describe('NetworkGraph', () => {
  it('convida a submeter um pedido quando não há grafo', () => {
    render(<NetworkGraph graph={null} />);
    expect(screen.getByText(/Submeta um pedido/)).toBeInTheDocument();
  });

  it('não reduz as siglas do C-Level a uma única letra', () => {
    const { container } = render(<NetworkGraph graph={GRAPH} />);
    const labels = [...container.querySelectorAll('text')].map((node) => node.textContent);

    expect(labels).toContain('CEO');
    expect(labels).toContain('CTO');
    // "Engenheiro de Software #1" → iniciais, ignorando o sufixo "#1".
    expect(labels).toContain('ES');
  });

  it('abre o detalhe da aresta ao clicar nela', async () => {
    render(<NetworkGraph graph={GRAPH} />);
    expect(screen.getByLabelText('Legenda do grafo')).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: 'Delegação: Frente de tecnologia' }),
    );

    const detail = await screen.findByLabelText('Detalhe da comunicação');
    expect(detail).toHaveTextContent('Frente de tecnologia');
    expect(detail).toHaveTextContent('Porque sim.');
  });
});
