import type { DecisionSource, GraphTask } from '@/types/network';

const SOURCE_LABEL: Record<DecisionSource, string> = {
  MODEL: 'veredito do modelo',
  UNAVAILABLE: 'modelo indisponível',
  INVALID_OUTPUT: 'saída inválida do modelo',
  HEURISTIC_SHADOW: 'heurística (modo shadow)',
  ATTEMPT_LIMIT: 'limite de tentativas',
  CEO_FALLBACK: 'desempate conservador do CEO',
};

interface ReviewEvidencePanelProps {
  task: GraphTask;
}

/** Por que o Chief decidiu: origem do veredito, critérios com citações e vetos. */
export function ReviewEvidencePanel({ task }: ReviewEvidencePanelProps): React.JSX.Element | null {
  const evidence = task.review_evidence;
  if (!task.decision_source) return null;

  const criteria = evidence.criteria ?? [];
  const vetoes = evidence.vetoes ?? [];
  const errors = evidence.errors ?? [];
  const completed = evidence.protocolo_completado_pelo_sistema ?? [];

  return (
    <details className="review-evidence">
      <summary>
        Origem: {SOURCE_LABEL[task.decision_source]}
        {evidence.mode ? ` · modo ${evidence.mode}` : ''}
      </summary>

      {evidence.model_decision || evidence.heuristic ? (
        <p>
          Modelo: {evidence.model_decision ?? 'sem veredito'} · heurística:{' '}
          {evidence.heuristic ?? '—'}
          {evidence.agrees === true ? ' · concordam' : ''}
          {evidence.agrees === false ? ' · divergem' : ''}
        </p>
      ) : null}

      {evidence.verdict ? (
        <p>
          {evidence.verdict.justificativa}{' '}
          <span className="muted">(evidências: {evidence.verdict.evidencias.join(', ')})</span>
        </p>
      ) : null}

      {criteria.length > 0 ? (
        <ul className="review-criteria" aria-label="Critérios de aceitação">
          {criteria.map((item, index) => (
            <li key={item.id ?? index} data-met={item.atendido}>
              <span aria-hidden="true">{item.atendido ? '✔' : '✘'}</span> {item.criterio}
              {item.citacao ? <q>{item.citacao}</q> : null}
              {!item.atendido && item.motivo ? (
                <span className="muted"> — {item.motivo}</span>
              ) : null}
              {item.metodo ? <span className="muted"> [{item.metodo}]</span> : null}
            </li>
          ))}
        </ul>
      ) : null}

      {vetoes.length > 0 ? <p className="review-veto">Vetos: {vetoes.join('; ')}</p> : null}
      {completed.length > 0 ? (
        <p className="muted">Ferramentas executadas pelo sistema: {completed.join(', ')}</p>
      ) : null}
      {errors.length > 0 ? <p className="muted">Erros: {errors.join('; ')}</p> : null}
    </details>
  );
}
