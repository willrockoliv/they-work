import type { GraphEdge, GraphNode } from '@/types/network';

/** Camada vertical de cada papel no organograma desenhado. */
const LAYER_BY_ROLE: Record<string, number> = {
  OBSERVER: 0,
  CEO: 1,
  CTO: 2,
  CMO: 2,
  CFO: 2,
  RA: 2,
  SUBAGENT: 3,
};

export const LAYER_COUNT = 4;

/** Distância entre arestas que ligam o mesmo par de nós. */
export const EDGE_SPACING = 64;
export const NODE_RADIUS = 22;

export interface PositionedNode extends GraphNode {
  x: number;
  y: number;
  layer: number;
}

export interface PositionedEdge extends GraphEdge {
  /** Caminho SVG já curvado para separar arestas paralelas. */
  path: string;
  midX: number;
  midY: number;
  labelX: number;
  labelY: number;
  /** Quantas arestas do mesmo par precedem esta — define a curvatura. */
  parallelIndex: number;
}

export interface GraphLayout {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  width: number;
  height: number;
}

export interface LayoutOptions {
  width?: number;
  height?: number;
}

function layerOf(node: GraphNode): number {
  return LAYER_BY_ROLE[node.role] ?? LAYER_BY_ROLE.SUBAGENT!;
}

/**
 * Organograma determinístico: camadas fixas por papel, ordem estável dentro da
 * camada. Nada de simulação de forças — o mesmo grafo rende sempre o mesmo
 * desenho, o que mantém a leitura estável enquanto novas arestas chegam ao vivo.
 */
export function layoutGraph(
  nodes: GraphNode[],
  edges: GraphEdge[],
  options: LayoutOptions = {},
): GraphLayout {
  const width = options.width ?? 960;
  const height = options.height ?? 540;

  const layers = new Map<number, GraphNode[]>();
  for (const node of nodes) {
    const layer = layerOf(node);
    const bucket = layers.get(layer);
    if (bucket) bucket.push(node);
    else layers.set(layer, [node]);
  }

  // Subagentes ficam sob o chefe a quem reportam, preservando a leitura hierárquica.
  const chiefOrder = new Map<string, number>();
  (layers.get(2) ?? []).forEach((chief, index) => chiefOrder.set(chief.id, index));
  const subagents = layers.get(3);
  if (subagents) {
    subagents.sort((a, b) => {
      const left = chiefOrder.get(a.reports_to ?? '') ?? Number.MAX_SAFE_INTEGER;
      const right = chiefOrder.get(b.reports_to ?? '') ?? Number.MAX_SAFE_INTEGER;
      return left === right ? a.name.localeCompare(b.name) : left - right;
    });
  }

  const positioned = new Map<string, PositionedNode>();
  const rowHeight = height / LAYER_COUNT;

  for (const [layer, bucket] of layers) {
    const step = width / (bucket.length + 1);
    bucket.forEach((node, index) => {
      positioned.set(node.id, {
        ...node,
        layer,
        x: step * (index + 1),
        y: rowHeight * layer + rowHeight / 2,
      });
    });
  }

  // Chave sem direção: um parecer CTO→CEO e uma coordenação CEO→CTO ocupam a mesma
  // reta, então precisam entrar no mesmo grupo de curvatura — senão uma cobre a outra
  // e fica impossível clicar na de baixo.
  const pairKey = (a: string, b: string): string => [a, b].sort().join('|');

  // 1ª passada: conta quantas arestas existem em cada par.
  const total = new Map<string, number>();
  const drawable: { edge: GraphEdge; source: PositionedNode; target: PositionedNode }[] = [];

  for (const edge of edges) {
    const source = positioned.get(edge.sender_agent_id ?? 'observer');
    const target = positioned.get(edge.recipient_agent_id ?? '');
    if (!source || !target) continue;
    const key = pairKey(source.id, target.id);
    total.set(key, (total.get(key) ?? 0) + 1);
    drawable.push({ edge, source, target });
  }

  // 2ª passada: distribui as arestas do par simetricamente em torno da reta central.
  const seen = new Map<string, number>();
  const laidOutEdges: PositionedEdge[] = [];

  for (const { edge, source, target } of drawable) {
    const key = pairKey(source.id, target.id);
    const parallelIndex = seen.get(key) ?? 0;
    seen.set(key, parallelIndex + 1);

    const count = total.get(key) ?? 1;
    const spread = (parallelIndex - (count - 1) / 2) * EDGE_SPACING;

    // A normal sai de uma direção canônica (par ordenado por id), não da direção da
    // aresta: numa aresta recíproca o vetor se inverte e cancelaria o sinal do
    // `spread`, jogando as duas para o mesmo lado da reta.
    const [from, to] = source.id < target.id ? [source, target] : [target, source];
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy) || 1;
    const midX = (source.x + target.x) / 2 + (-dy / length) * spread;
    const midY = (source.y + target.y) / 2 + (dx / length) * spread;
    const sourceDx = midX - source.x;
    const sourceDy = midY - source.y;
    const sourceLength = Math.hypot(sourceDx, sourceDy) || 1;
    const targetDx = midX - target.x;
    const targetDy = midY - target.y;
    const targetLength = Math.hypot(targetDx, targetDy) || 1;
    const startX = source.x + (sourceDx / sourceLength) * NODE_RADIUS;
    const startY = source.y + (sourceDy / sourceLength) * NODE_RADIUS;
    const endX = target.x + (targetDx / targetLength) * NODE_RADIUS;
    const endY = target.y + (targetDy / targetLength) * NODE_RADIUS;

    laidOutEdges.push({
      ...edge,
      parallelIndex,
      midX,
      midY,
      labelX: startX * 0.25 + midX * 0.5 + endX * 0.25,
      labelY: startY * 0.25 + midY * 0.5 + endY * 0.25,
      path: `M ${startX} ${startY} Q ${midX} ${midY} ${endX} ${endY}`,
    });
  }

  return { nodes: [...positioned.values()], edges: laidOutEdges, width, height };
}
