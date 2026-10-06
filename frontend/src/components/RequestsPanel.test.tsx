import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RequestsPanel } from '@/components/RequestsPanel';
import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';

vi.mock('@/services/api', () => ({
  api: {
    requests: vi.fn(),
    requestDetail: vi.fn(),
    submitRequest: vi.fn(),
    runCycle: vi.fn(),
    startCycle: vi.fn(),
    companyStatus: vi.fn(),
    bootstrapCompany: vi.fn(),
  },
}));

const { api } = await import('@/services/api');

const REQUEST = {
  id: 'req-1',
  topic: 'Fundar uma startup de triagem documental',
  description: 'Automação de triagem para escritórios de médio porte.',
  submitted_by: 'OBSERVER',
  status: 'DELIBERATING' as const,
  thread_id: null,
  outcome: null,
  narrative: 'O conselho aprovou com ressalvas.',
  current_state: {},
  created_at: '2026-10-05T10:00:00Z',
  resolved_at: null,
};

const GRAPH = {
  request_id: 'req-1',
  topic: REQUEST.topic,
  status: 'DELIBERATING' as const,
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
  ],
  edges: [
    {
      id: 'e1',
      request_id: 'req-1',
      task_id: null,
      sender_agent_id: 'observer',
      recipient_agent_id: 'ceo',
      communication_type: 'REQUEST' as const,
      status: 'PENDING' as const,
      summary: REQUEST.topic,
      content: {},
      reasoning_session_id: null,
      created_at: null,
    },
  ],
  tasks: [
    {
      id: 't1',
      request_id: 'req-1',
      parent_task_id: null,
      assigned_by_chief_id: 'ceo',
      assigned_to_agent_id: 'dev',
      title: 'Frente de tecnologia',
      task_description: 'Desenhar a arquitetura',
      status: 'COMPLETED' as const,
      attempt: 1,
      quality_score: 88,
      decision: 'APPROVE' as const,
      decision_rationale: 'Entrega completa.',
      report_summary: null,
      report_reasoning_session_id: null,
      review_reasoning_session_id: null,
    },
  ],
};

describe('RequestsPanel', () => {
  beforeEach(() => {
    vi.mocked(api.requests).mockResolvedValue({ total: 1, requests: [REQUEST] });
    vi.mocked(api.requestDetail).mockResolvedValue({ request: REQUEST, graph: GRAPH });
    vi.mocked(api.submitRequest).mockResolvedValue({ request: REQUEST, graph: GRAPH });
    vi.mocked(api.startCycle).mockResolvedValue({ request: REQUEST, started: true });
    vi.mocked(api.companyStatus).mockResolvedValue({
      created: 0,
      total: 5,
      profiles: 5,
      chiefs: [],
    });
    vi.mocked(api.bootstrapCompany).mockResolvedValue({
      created: 5,
      total: 5,
      profiles: 5,
      chiefs: [],
    });
    useGameStore.getState().reset();
    useUiStore.getState().selectRequest(null);
  });

  it('lista os pedidos vindos da API', async () => {
    render(<RequestsPanel />);
    expect(await screen.findByText(REQUEST.topic)).toBeInTheDocument();
  });

  it('mantém o botão de submissão travado enquanto o formulário está incompleto', async () => {
    render(<RequestsPanel />);
    const submit = screen.getByRole('button', { name: 'Submeter ao CEO' });
    expect(submit).toBeDisabled();

    await userEvent.type(screen.getByLabelText('Tópico'), 'Fundar');
    expect(submit).toBeDisabled();

    await userEvent.type(screen.getByLabelText('Descrição'), 'Produto para advogados.');
    await waitFor(() => {
      expect(submit).toBeEnabled();
    });
  });

  it('oferece fundar a empresa quando não há conselho', async () => {
    vi.mocked(api.companyStatus).mockResolvedValue({
      created: 0,
      total: 0,
      profiles: 0,
      chiefs: [],
    });
    render(<RequestsPanel />);

    const button = await screen.findByRole('button', { name: 'Fundar a empresa' });
    expect(screen.getByText(/ainda não foi fundada/i)).toBeInTheDocument();

    // Sem conselho o formulário fica travado mesmo preenchido.
    await userEvent.type(screen.getByLabelText('Tópico'), 'Fundar');
    await userEvent.type(screen.getByLabelText('Descrição'), 'Produto para advogados.');
    expect(screen.getByRole('button', { name: 'Submeter ao CEO' })).toBeDisabled();

    await userEvent.click(button);
    expect(vi.mocked(api.bootstrapCompany)).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText(/ainda não foi fundada/i)).not.toBeInTheDocument();
    });
  });

  it('submeter já põe a empresa para trabalhar', async () => {
    render(<RequestsPanel />);

    await userEvent.type(screen.getByLabelText('Tópico'), 'Fundar uma startup');
    await userEvent.type(screen.getByLabelText('Descrição'), 'Produto para advogados.');
    await userEvent.click(screen.getByRole('button', { name: 'Submeter ao CEO' }));

    await waitFor(() => {
      expect(vi.mocked(api.startCycle)).toHaveBeenCalledWith(REQUEST.id);
    });
  });

  it('abre o grafo e as tarefas do pedido selecionado', async () => {
    useUiStore.getState().selectRequest('req-1');
    render(<RequestsPanel />);

    await waitFor(() => {
      expect(screen.getByText('Frente de tecnologia')).toBeInTheDocument();
    });
    expect(screen.getByText(/qualidade 88\/100/)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Grafo de comunicações/ })).toBeInTheDocument();
  });

  it('avança um turno em segundo plano', async () => {
    useUiStore.getState().selectRequest('req-1');
    render(<RequestsPanel />);

    const button = await screen.findByRole('button', { name: 'Avançar um turno' });
    await userEvent.click(button);

    expect(vi.mocked(api.startCycle)).toHaveBeenCalledWith('req-1');
  });
});
