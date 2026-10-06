import { useMemo, useState } from 'react';

import { layoutGraph, type PositionedEdge } from '@/engine/graphLayout';
import type { CommunicationType, GraphEdge, RequestGraphResponse } from '@/types/network';

const EDGE_COLOR: Record<CommunicationType, string> = {
  REQUEST: '#facc15',
  OPINION: '#38bdf8',
  COORDINATION: '#6366f1',
  AGENT_REQUEST: '#f59e0b',
  AGENT_CREATED: '#a855f7',
  DELEGATION: '#14b8a6',
  REPORT: '#22c55e',
  CONSULTATION: '#0ea5e9',
  ESCALATION: '#fb7185',
  DECISION: '#e879f9',
};

const EDGE_LABEL: Record<CommunicationType, string> = {
  REQUEST: 'Pedido',
  OPINION: 'Parecer',
  COORDINATION: 'Coordenação',
  AGENT_REQUEST: 'Pedido ao RA',
  AGENT_CREATED: 'Agente criado',
  DELEGATION: 'Delegação',
  REPORT: 'Report',
  CONSULTATION: 'Consulta',
  ESCALATION: 'Escalação',
  DECISION: 'Decisão',
};

const NODE_RADIUS = 22;
const VIEW_WIDTH = 960;
const VIEW_HEIGHT = 560;

function nodeFill(role: string): string {
  if (role === 'OBSERVER') return '#64748b';
  if (role === 'CEO') return '#4a90d9';
  if (role === 'RA') return '#eab308';
  if (role === 'SUBAGENT') return '#94a3b8';
  return '#34d399';
}

/**
 * Rótulo curto do nó.
 *
 * Siglas (CEO, CTO, RA…) entram inteiras: reduzi-las a iniciais faria todos os
 * C-Level virarem um "C" indistinguível. Nomes compostos viram iniciais, ignorando
 * sufixos não alfabéticos como "#1".
 */
function initials(name: string): string {
  const clean = name.trim();
  if (clean.length <= 4 && !clean.includes(' ')) return clean.toUpperCase();

  const words = clean.split(/\s+/).filter((word) => /^[A-Za-zÀ-ÿ]/.test(word));
  if (words.length === 0) return clean.slice(0, 2).toUpperCase();
  const first = words[0]?.[0] ?? '';
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? '') : '';
  return `${first}${last}`.toUpperCase();
}

export interface NetworkGraphProps {
  graph: RequestGraphResponse | null;
  onSelectEdge?: (edge: GraphEdge | null) => void;
}

/**
 * Organograma vivo do pedido, em SVG puro.
 *
 * O layout é determinístico (ver `engine/graphLayout`): o mesmo grafo rende
 * sempre o mesmo desenho, então a leitura não "pula" quando chegam arestas novas.
 */
export function NetworkGraph({ graph, onSelectEdge }: NetworkGraphProps): React.JSX.Element {
  const [activeEdgeId, setActiveEdgeId] = useState<string | null>(null);

  const layout = useMemo(
    () =>
      graph
        ? layoutGraph(graph.nodes, graph.edges, { width: VIEW_WIDTH, height: VIEW_HEIGHT })
        : null,
    [graph],
  );

  if (!layout || layout.nodes.length === 0) {
    return (
      <div className="network-graph empty">
        <p className="empty">Submeta um pedido para ver a rede corporativa se formar.</p>
      </div>
    );
  }

  const activeEdge = layout.edges.find((edge) => edge.id === activeEdgeId) ?? null;

  function toggle(edge: PositionedEdge): void {
    const next = edge.id === activeEdgeId ? null : edge.id;
    setActiveEdgeId(next);
    onSelectEdge?.(next === null ? null : edge);
  }

  return (
    <div className="network-graph">
      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        role="img"
        aria-label={`Grafo de comunicações de ${graph?.topic ?? 'pedido'}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="18"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
          </marker>
        </defs>

        <g className="edges">
          {layout.edges.map((edge) => (
            <g key={edge.id} style={{ color: EDGE_COLOR[edge.communication_type] }}>
              <path
                d={edge.path}
                fill="none"
                stroke="currentColor"
                strokeWidth={edge.id === activeEdgeId ? 3 : 1.6}
                strokeOpacity={edge.id === activeEdgeId ? 1 : 0.65}
                markerEnd="url(#arrow)"
              />
              <path
                d={edge.path}
                fill="none"
                stroke="transparent"
                strokeWidth={14}
                role="button"
                tabIndex={0}
                aria-label={`${EDGE_LABEL[edge.communication_type]}: ${edge.summary}`}
                aria-pressed={edge.id === activeEdgeId}
                style={{ cursor: 'pointer' }}
                onClick={() => toggle(edge)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    toggle(edge);
                  }
                }}
              >
                <title>{`${EDGE_LABEL[edge.communication_type]}: ${edge.summary}`}</title>
              </path>
            </g>
          ))}
        </g>

        <g className="nodes">
          {layout.nodes.map((node) => (
            <g key={node.id} transform={`translate(${node.x} ${node.y})`}>
              <circle r={NODE_RADIUS} fill={nodeFill(node.role)} stroke="#0f172a" strokeWidth={2} />
              <text textAnchor="middle" dy="0.35em" fontSize={11} fill="#0f172a" fontWeight={700}>
                {initials(node.name)}
              </text>
              <text textAnchor="middle" y={NODE_RADIUS + 14} fontSize={11} fill="currentColor">
                {node.role === 'SUBAGENT' ? node.name : node.role}
              </text>
              <title>{`${node.name} · ${node.role} · ${node.status}`}</title>
            </g>
          ))}
        </g>
      </svg>

      {activeEdge ? (
        <aside className="edge-detail" aria-label="Detalhe da comunicação">
          <h4>{EDGE_LABEL[activeEdge.communication_type]}</h4>
          <p>{activeEdge.summary}</p>
          {typeof activeEdge.content.rationale === 'string' ? (
            <p className="muted">{activeEdge.content.rationale}</p>
          ) : null}
          {typeof activeEdge.content.conclusion === 'string' ? (
            <p className="muted">{activeEdge.content.conclusion}</p>
          ) : null}
        </aside>
      ) : (
        <ul className="legend" aria-label="Legenda do grafo">
          {Object.entries(EDGE_LABEL).map(([kind, label]) => (
            <li key={kind}>
              <i style={{ background: EDGE_COLOR[kind as CommunicationType] }} />
              {label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
