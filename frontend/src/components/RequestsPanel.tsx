import { useEffect, useState } from 'react';

import { api } from '@/services/api';
import { ApiError } from '@/services/http';
import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';
import type { InitialRequestRead, RequestGraphResponse, TaskStatus } from '@/types/network';

import { NetworkGraph } from './NetworkGraph';

const STATUS_LABEL: Record<string, string> = {
  PROPOSED: '⏳ proposto',
  DELIBERATING: '🗣️ em deliberação',
  IN_EXECUTION: '🔄 em execução',
  AWAITING_FEEDBACK: '📥 aguardando veredito',
  COMPLETED: '✅ concluído',
  FAILED: '⚠️ encerrado',
};

const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  PENDING: 'pendente',
  ACKNOWLEDGED: 'reconhecida',
  IN_PROGRESS: 'em andamento',
  AWAITING_REVIEW: 'aguardando revisão',
  COMPLETED: 'concluída',
  REJECTED: 'rejeitada',
  CANCELLED: 'cancelada',
};

interface RequestDetail {
  request: InitialRequestRead;
  graph: RequestGraphResponse;
}

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  return error instanceof Error ? error.message : 'Falha inesperada.';
}

/** Aba "Pedidos": formulário, lista e o grafo vivo do pedido selecionado. */
export function RequestsPanel(): React.JSX.Element {
  const selectedRequestId = useUiStore((state) => state.selectedRequestId);
  const selectRequest = useUiStore((state) => state.selectRequest);
  // Uma mutação do grafo chegando pelo socket é o gatilho para rebuscar o detalhe.
  const networkRevision = useGameStore((state) => state.networkRevision);

  const [requests, setRequests] = useState<InitialRequestRead[]>([]);
  const [listRevision, setListRevision] = useState(0);
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [founded, setFounded] = useState<boolean | null>(null);
  const [topic, setTopic] = useState('');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Os efeitos só disparam o I/O: todo `setState` acontece ao resolver a promessa,
  // nunca no corpo do efeito (regra `react-hooks/set-state-in-effect`).
  useEffect(() => {
    let cancelled = false;
    void api
      .companyStatus()
      .then((response) => {
        if (!cancelled) setFounded(response.total > 0);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(describe(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [listRevision]);

  useEffect(() => {
    let cancelled = false;
    void api
      .requests()
      .then((response) => {
        if (!cancelled) setRequests(response.requests);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(describe(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [listRevision, networkRevision]);

  useEffect(() => {
    if (!selectedRequestId) return undefined;
    let cancelled = false;
    void api
      .requestDetail(selectedRequestId)
      .then((response) => {
        if (!cancelled) setDetail(response);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(describe(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRequestId, networkRevision]);

  // Derivado, não sincronizado: o detalhe obsoleto some sem precisar de `setState`.
  const shown = detail && detail.request.id === selectedRequestId ? detail : null;

  async function found(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await api.bootstrapCompany();
      setFounded(true);
      setListRevision((value) => value + 1);
    } catch (cause) {
      setError(describe(cause));
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await api.submitRequest(topic.trim(), description.trim());
      setTopic('');
      setDescription('');
      setDetail(response);
      selectRequest(response.request.id);
      // Submeter é pedir para a empresa trabalhar: o turno começa sozinho, em
      // segundo plano, e o grafo cresce pelos eventos do WebSocket.
      await api.startCycle(response.request.id);
      setListRevision((value) => value + 1);
    } catch (cause) {
      setError(describe(cause));
    } finally {
      setBusy(false);
    }
  }

  async function advance(): Promise<void> {
    if (!selectedRequestId) return;
    setBusy(true);
    setError(null);
    try {
      await api.startCycle(selectedRequestId);
      setListRevision((value) => value + 1);
    } catch (cause) {
      setError(describe(cause));
    } finally {
      setBusy(false);
    }
  }

  const canSubmit =
    founded === true && topic.trim().length >= 3 && description.trim().length >= 3 && !busy;

  return (
    <section className="requests-panel" aria-label="Pedidos ao conselho">
      <form onSubmit={(event) => void submit(event)}>
        <h3>Novo pedido ao conselho</h3>

        {founded === false ? (
          <div className="founding" role="status">
            <p>
              A empresa ainda não foi fundada: não há CEO para receber o pedido nem
              diretorias para deliberar.
            </p>
            <button type="button" onClick={() => void found()} disabled={busy}>
              {busy ? 'Fundando…' : 'Fundar a empresa'}
            </button>
          </div>
        ) : null}

        <label htmlFor="request-topic">Tópico</label>
        <input
          id="request-topic"
          value={topic}
          maxLength={255}
          placeholder="Fundar uma startup de triagem documental"
          onChange={(event) => setTopic(event.target.value)}
        />
        <label htmlFor="request-description">Descrição</label>
        <textarea
          id="request-description"
          value={description}
          rows={4}
          placeholder="Quem é o cliente, qual é a dor e como a empresa ganha dinheiro com isso."
          onChange={(event) => setDescription(event.target.value)}
        />
        <button type="submit" disabled={!canSubmit}>
          {busy ? 'Enviando…' : 'Submeter ao CEO'}
        </button>
      </form>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="requests-list">
        <h3>Pedidos</h3>
        {requests.length === 0 ? (
          <p className="empty">Nenhum pedido submetido ainda.</p>
        ) : (
          <ul>
            {requests.map((request) => (
              <li key={request.id}>
                <button
                  type="button"
                  aria-pressed={request.id === selectedRequestId}
                  onClick={() => selectRequest(request.id)}
                >
                  <strong>{request.topic}</strong>
                  <span>{STATUS_LABEL[request.status] ?? request.status}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {shown ? (
        <div className="request-detail">
          <header>
            <h3>{shown.request.topic}</h3>
            <button type="button" onClick={() => void advance()} disabled={busy}>
              {busy ? 'Iniciando…' : 'Avançar um turno'}
            </button>
          </header>
          {shown.request.narrative ? <p>{shown.request.narrative}</p> : null}

          <NetworkGraph graph={shown.graph} />

          <h4>Tarefas</h4>
          {shown.graph.tasks.length === 0 ? (
            <p className="empty">Nenhuma tarefa delegada ainda.</p>
          ) : (
            <ul className="task-list">
              {shown.graph.tasks.map((task) => (
                <li key={task.id} data-status={task.status}>
                  <strong>{task.title}</strong>
                  <span>
                    {TASK_STATUS_LABEL[task.status]} · tentativa {task.attempt}
                    {task.decision ? ` · ${task.decision}` : ''}
                    {task.quality_score > 0 ? ` · qualidade ${task.quality_score}/100` : ''}
                  </span>
                  {task.decision_rationale ? (
                    <p className="muted">{task.decision_rationale}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </section>
  );
}
