import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ReviewEvidencePanel } from '@/components/ReviewEvidencePanel';
import type { GraphTask } from '@/types/network';

function task(overrides: Partial<GraphTask>): GraphTask {
  return {
    id: 't1',
    request_id: 'req-1',
    parent_task_id: null,
    assigned_by_chief_id: 'cfo',
    assigned_to_agent_id: 'dev',
    title: 'Frente de finanças',
    task_description: 'Calcular o ponto de equilíbrio',
    status: 'AWAITING_REVIEW',
    attempt: 3,
    quality_score: 40,
    decision: 'ESCALATE',
    decision_rationale: null,
    decision_source: null,
    review_evidence: {},
    report_summary: null,
    report_reasoning_session_id: null,
    review_reasoning_session_id: null,
    ...overrides,
  };
}

describe('ReviewEvidencePanel', () => {
  it('não renderiza nada antes da revisão', () => {
    const { container } = render(<ReviewEvidencePanel task={task({})} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('expõe vetos, ferramentas completadas pelo sistema e erros do modelo', () => {
    render(
      <ReviewEvidencePanel
        task={task({
          decision_source: 'INVALID_OUTPUT',
          review_evidence: {
            mode: 'model',
            model_decision: null,
            heuristic: 'REJECT',
            agrees: null,
            vetoes: ['placeholder: X'],
            protocolo_completado_pelo_sistema: ['checar_criterios'],
            errors: ['json_invalido: campo ausente'],
          },
        })}
      />,
    );

    expect(screen.getByText(/saída inválida do modelo · modo model/)).toBeInTheDocument();
    expect(screen.getByText(/Modelo: sem veredito/)).toBeInTheDocument();
    expect(screen.getByText('Vetos: placeholder: X')).toBeInTheDocument();
    expect(screen.getByText(/executadas pelo sistema: checar_criterios/)).toBeInTheDocument();
    expect(screen.getByText(/Erros: json_invalido/)).toBeInTheDocument();
  });
});
