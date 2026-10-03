import { useCallback, useEffect, useMemo, useState } from 'react';

import { api } from '@/services/api';
import { useGameStore } from '@/store/gameStore';
import type { ReasoningFlowEdge, ReasoningFlowNode, ReasoningFlowResponse } from '@/types/api';
import type { StepEventData } from '@/types/events';
import type { GameAgent } from '@/types/game';

const NODE_ICON: Record<string, string> = {
  TASK: '▣',
  THOUGHT: '◆',
  ACTION: '⚙',
  OBSERVATION: '◉',
  CONCLUSION: '✔',
};

/** Referência estável: um array novo a cada seletor faria o `useSyncExternalStore` girar. */
const NO_STEPS: StepEventData[] = [];

/** Converte os passos recebidos ao vivo num fluxograma, sem ida ao servidor. */
function flowFromLiveSteps(task: string, steps: StepEventData[]): ReasoningFlowResponse {
  const nodes: ReasoningFlowNode[] = [
    {
      id: 'task',
      type: 'TASK',
      label: 'Tarefa',
      content: task,
      icon: 'clipboard',
      color: '#64748b',
      column: 0,
      row: 0,
      payload: {},
      meta: {},
    },
  ];
  const edges: ReasoningFlowEdge[] = [];
  let previousId = 'task';
  let row = 0;

  for (const step of steps) {
    if (step.step_type === 'THOUGHT' && nodes.length > 1) row += 1;
    const id = `step-${step.sequence}`;
    nodes.push({
      id,
      type: step.step_type,
      label: `${step.step_type} ${step.sequence}`,
      content: step.content,
      icon: '',
      color: '',
      column: 0,
      row,
      payload: step.payload,
      meta: { sequence: step.sequence, tokens: step.tokens, duration_ms: step.duration_ms },
    });
    edges.push({
      id: `edge-${previousId}-${id}`,
      source: previousId,
      target: id,
      kind: step.step_type === 'THOUGHT' && row > 0 ? 'LOOP' : 'SEQUENCE',
      label: '',
    });
    previousId = id;
  }

  return {
    nodes,
    edges,
    meta: {
      session_id: 'live',
      agent_id: null,
      status: 'RUNNING',
      step_count: steps.length,
      total_tokens: steps.reduce((sum, step) => sum + step.tokens, 0),
      duration_ms: steps.reduce((sum, step) => sum + step.duration_ms, 0),
      conclusion: null,
      error: null,
      columns: [],
      rows: row + 1,
    },
  };
}

/** Aba "Reasoning Flow": fluxograma interativo do ciclo ReAct. */
export function ReasoningFlowTab({
  agent,
  sessionId,
}: {
  agent: GameAgent;
  sessionId?: string;
}): React.JSX.Element {
  const sessionKey = agent.reasoning?.session_id;
  const liveSteps = useGameStore((state) =>
    sessionKey ? (state.liveSteps[sessionKey] ?? NO_STEPS) : NO_STEPS,
  );
  // O resultado carrega a chave do pedido: trocar de agente/sessão invalida o
  // que já está em tela sem precisar de um `setState` dentro do efeito.
  const flowKey = sessionId ?? agent.id;
  const [result, setResult] = useState<{
    key: string;
    flow?: ReasoningFlowResponse;
    error?: string;
  } | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const promise = sessionId ? api.sessionFlow(sessionId) : api.reasoningFlow(agent.id);
    void promise
      .then((flow) => {
        if (!cancelled) setResult({ key: flowKey, flow });
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setResult({
            key: flowKey,
            error: cause instanceof Error ? cause.message : String(cause),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [agent.id, flowKey, sessionId]);

  const current = result?.key === flowKey ? result : null;
  const fetched = current?.flow ?? null;
  const error = current?.error ?? null;

  const flow = useMemo(() => {
    // Enquanto a sessão corre, os passos ao vivo são mais recentes que o GET.
    if (!sessionId && liveSteps.length > (fetched?.nodes.length ?? 1) - 1) {
      return flowFromLiveSteps(agent.reasoning?.task ?? '', liveSteps);
    }
    return fetched;
  }, [agent.reasoning?.task, fetched, liveSteps, sessionId]);

  const copy = useCallback((nodeId: string, content: string) => {
    void navigator.clipboard?.writeText(content).then(() => setCopiedId(nodeId));
  }, []);

  if (error && !flow) {
    return <p className="empty">{error}</p>;
  }
  if (!flow) {
    return <p className="empty">Carregando fluxograma…</p>;
  }

  const edgeByTarget = new Map(flow.edges.map((edge) => [edge.target, edge]));

  return (
    <div className="flow">
      {flow.nodes.map((node, index) => {
        const edge = edgeByTarget.get(node.id);
        return (
          <div key={node.id}>
            {index > 0 && edge ? (
              <div className="flow-edge" data-kind={edge.kind}>
                {edge.kind === 'LOOP' ? '↻ reavalia' : '↓'}
              </div>
            ) : null}
            <details
              className="flow-node"
              data-type={node.type}
              open={index >= flow.nodes.length - 3}
            >
              <summary>
                <span aria-hidden="true">{NODE_ICON[node.type] ?? '•'}</span>
                <span>{node.label}</span>
                <span className="meta">
                  {typeof node.meta.tokens === 'number' ? `${node.meta.tokens} tok` : ''}
                  {typeof node.meta.duration_ms === 'number'
                    ? ` · ${node.meta.duration_ms} ms`
                    : ''}
                </span>
              </summary>
              <pre>{node.content}</pre>
              <div style={{ padding: '0 10px 10px' }}>
                <button type="button" onClick={() => copy(node.id, node.content)}>
                  {copiedId === node.id ? 'Copiado!' : 'Copiar'}
                </button>
              </div>
            </details>
          </div>
        );
      })}
      {flow.meta.conclusion ? (
        <p style={{ fontSize: 13, margin: '12px 0 0' }}>{flow.meta.conclusion}</p>
      ) : null}
    </div>
  );
}
