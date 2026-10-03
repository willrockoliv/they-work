import { useEffect, useState } from 'react';

import { api } from '@/services/api';
import type { ReasoningSessionRead } from '@/types/api';
import type { GameAgent } from '@/types/game';

function duration(ms: number): string {
  return ms < 1_000 ? `${ms} ms` : `${(ms / 1_000).toFixed(1)} s`;
}

/** Aba "History": últimas tarefas do agente, com atalho para o raciocínio antigo. */
export function HistoryTab({
  agent,
  onOpenSession,
}: {
  agent: GameAgent;
  onOpenSession: (sessionId: string) => void;
}): React.JSX.Element {
  const [result, setResult] = useState<{
    key: string;
    sessions?: ReasoningSessionRead[];
    error?: string;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .agentHistory(agent.id, 10)
      .then((response) => {
        if (!cancelled) setResult({ key: agent.id, sessions: response.sessions });
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setResult({
            key: agent.id,
            error: cause instanceof Error ? cause.message : String(cause),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [agent.id]);

  const current = result?.key === agent.id ? result : null;
  const sessions = current?.sessions ?? null;
  const error = current?.error ?? null;

  if (error) return <p className="empty">{error}</p>;
  if (!sessions) return <p className="empty">Carregando histórico…</p>;
  if (sessions.length === 0) return <p className="empty">Nenhuma tarefa registrada ainda.</p>;

  return (
    <div>
      {sessions.map((session) => (
        <button
          key={session.id}
          type="button"
          className="history-item"
          onClick={() => onOpenSession(session.id)}
        >
          <strong>{session.task}</strong>
          <span className="meta">
            {session.status} · {session.step_count} passos · {duration(session.duration_ms)} ·{' '}
            {session.total_tokens} tok
          </span>
          <span className="meta">
            {session.model_name ?? 'modelo indefinido'} ·{' '}
            {new Date(session.started_at).toLocaleString('pt-BR')}
          </span>
        </button>
      ))}
    </div>
  );
}
