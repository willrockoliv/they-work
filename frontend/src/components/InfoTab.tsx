import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';
import type { GameAgent } from '@/types/game';

function duration(ms: number): string {
  if (ms < 1_000) return `${ms} ms`;
  const seconds = ms / 1_000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

const ACTIVITY_LABEL: Record<GameAgent['activity'], string> = {
  IDLE: 'Ocioso',
  THINKING: 'Raciocinando',
  WORKING: 'Trabalhando',
  BLOCKED: 'Bloqueado',
  TERMINATED: 'Desligado',
};

/** Aba "Info": quem é o agente, em que modelo roda e quanto já consumiu. */
export function InfoTab({ agent }: { agent: GameAgent }): React.JSX.Element {
  const sessions = useGameStore((state) => state.sessions);
  const focusOn = useUiStore((state) => state.focusOn);
  const reasoning = agent.reasoning;
  const liveSession = reasoning ? sessions[reasoning.session_id] : undefined;

  return (
    <div>
      <dl className="fields">
        <dt>Função</dt>
        <dd>{agent.job_title ?? agent.role}</dd>

        <dt>Papel</dt>
        <dd>{agent.role}</dd>

        <dt>Tipo</dt>
        <dd>{agent.agent_type === 'CHIEF' ? 'Diretoria' : 'Subagente'}</dd>

        <dt>Estado</dt>
        <dd>{ACTIVITY_LABEL[agent.activity]}</dd>

        <dt>Modelo</dt>
        <dd>{agent.model_name ?? '—'}</dd>

        <dt>RAM estimada</dt>
        <dd>{agent.estimated_ram_mb} MB</dd>

        <dt>Posto</dt>
        <dd>{agent.seat_id ?? '—'}</dd>

        <dt>Contratado em</dt>
        <dd>{new Date(agent.created_at).toLocaleString('pt-BR')}</dd>
      </dl>

      {agent.position ? (
        <button
          type="button"
          style={{ marginTop: 12 }}
          onClick={() => focusOn(agent.position!.x, agent.position!.y, 1.6)}
        >
          Centralizar câmera
        </button>
      ) : null}

      <h3 className="section-title">Tarefa atual</h3>
      {reasoning ? (
        <>
          <p style={{ margin: '0 0 10px', fontSize: 13 }}>{reasoning.task}</p>
          <div
            className="progress"
            role="progressbar"
            aria-valuenow={Math.round(reasoning.progress * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <i style={{ width: `${Math.round(reasoning.progress * 100)}%` }} />
          </div>
          <dl className="fields" style={{ marginTop: 10 }}>
            <dt>Status</dt>
            <dd>{liveSession?.status ?? reasoning.status}</dd>

            <dt>Passos</dt>
            <dd>{reasoning.step_count}</dd>

            <dt>Tokens</dt>
            <dd>{reasoning.total_tokens}</dd>

            <dt>Decorrido</dt>
            <dd>{duration(reasoning.elapsed_ms)}</dd>
          </dl>
          {reasoning.conclusion ? (
            <>
              <h3 className="section-title">Conclusão</h3>
              <p style={{ margin: 0, fontSize: 13 }}>{reasoning.conclusion}</p>
            </>
          ) : null}
          {reasoning.error ? (
            <>
              <h3 className="section-title">Erro</h3>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--crit)' }}>{reasoning.error}</p>
            </>
          ) : null}
        </>
      ) : (
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
          Este agente ainda não produziu nenhum raciocínio.
        </p>
      )}
    </div>
  );
}
