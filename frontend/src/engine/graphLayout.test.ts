import { describe, expect, it } from 'vitest';

import { LAYER_COUNT, layoutGraph } from '@/engine/graphLayout';
import type { GraphEdge, GraphNode } from '@/types/network';

const NODES: GraphNode[] = [
  { id: 'observer', name: 'OBSERVER', role: 'OBSERVER', agent_type: 'OBSERVER', status: 'IDLE', reports_to: null },
  { id: 'ceo', name: 'CEO', role: 'CEO', agent_type: 'CHIEF', status: 'IDLE', reports_to: null },
  { id: 'cto', name: 'CTO', role: 'CTO', agent_type: 'CHIEF', status: 'IDLE', reports_to: 'ceo' },
  { id: 'cmo', name: 'CMO', role: 'CMO', agent_type: 'CHIEF', status: 'IDLE', reports_to: 'ceo' },
  { id: 'ra', name: 'RA', role: 'RA', agent_type: 'CHIEF', status: 'IDLE', reports_to: 'ceo' },
  { id: 'dev', name: 'Dev #1', role: 'SUBAGENT', agent_type: 'SUBAGENT', status: 'IDLE', reports_to: 'cto' },
  { id: 'ana', name: 'Analista #1', role: 'SUBAGENT', agent_type: 'SUBAGENT', status: 'IDLE', reports_to: 'cmo' },
];

function edge(id: string, from: string | null, to: string): GraphEdge {
  return {
    id,
    request_id: 'req',
    task_id: null,
    sender_agent_id: from,
    recipient_agent_id: to,
    communication_type: 'DELEGATION',
    status: 'PENDING',
    summary: id,
    content: {},
    reasoning_session_id: null,
    created_at: null,
  };
}

describe('layoutGraph', () => {
  it('posiciona cada papel na sua camada hierárquica', () => {
    const layout = layoutGraph(NODES, []);
    const byId = new Map(layout.nodes.map((node) => [node.id, node]));

    expect(byId.get('observer')?.layer).toBe(0);
    expect(byId.get('ceo')?.layer).toBe(1);
    expect(byId.get('cto')?.layer).toBe(2);
    expect(byId.get('ra')?.layer).toBe(2);
    expect(byId.get('dev')?.layer).toBe(3);
  });

  it('mantém todos os nós dentro do viewport', () => {
    const layout = layoutGraph(NODES, [], { width: 800, height: 400 });
    for (const node of layout.nodes) {
      expect(node.x).toBeGreaterThan(0);
      expect(node.x).toBeLessThan(800);
      expect(node.y).toBeGreaterThan(0);
      expect(node.y).toBeLessThan(400);
    }
    expect(LAYER_COUNT).toBe(4);
  });

  it('agrupa subagentes sob o chefe a quem reportam', () => {
    const layout = layoutGraph(NODES, []);
    const chiefs = layout.nodes.filter((node) => node.layer === 2).sort((a, b) => a.x - b.x);
    const subagents = layout.nodes.filter((node) => node.layer === 3).sort((a, b) => a.x - b.x);

    const chiefRank = chiefs.map((node) => node.id);
    const expected = subagents.map((node) => chiefRank.indexOf(node.reports_to ?? ''));
    expect(expected).toEqual([...expected].sort((a, b) => a - b));
  });

  it('trata emissor nulo como o observador', () => {
    const layout = layoutGraph(NODES, [edge('e1', null, 'ceo')]);
    expect(layout.edges).toHaveLength(1);
    expect(layout.edges[0]?.path).toMatch(/^M /);
  });

  it('descarta arestas que apontam para nós ausentes', () => {
    const layout = layoutGraph(NODES, [edge('e1', 'cto', 'fantasma')]);
    expect(layout.edges).toHaveLength(0);
  });

  it('curva arestas paralelas para que não se sobreponham', () => {
    const layout = layoutGraph(NODES, [
      edge('e1', 'cto', 'dev'),
      edge('e2', 'cto', 'dev'),
      edge('e3', 'cto', 'dev'),
    ]);

    expect(layout.edges.map((item) => item.parallelIndex)).toEqual([0, 1, 2]);
    const mids = new Set(layout.edges.map((item) => `${item.midX},${item.midY}`));
    expect(mids.size).toBe(3);
  });

  it('uma aresta sozinha fica reta', () => {
    const layout = layoutGraph(NODES, [edge('e1', 'cto', 'dev')]);
    const only = layout.edges[0]!;
    const source = layout.nodes.find((node) => node.id === 'cto')!;
    const target = layout.nodes.find((node) => node.id === 'dev')!;

    expect(only.midX).toBeCloseTo((source.x + target.x) / 2);
    expect(only.midY).toBeCloseTo((source.y + target.y) / 2);
  });

  it('separa arestas recíprocas para os dois lados da reta', () => {
    // CTO→CEO e CEO→CTO ocupam a mesma reta: sem separação uma fica inclicável.
    const layout = layoutGraph(NODES, [edge('e1', 'cto', 'ceo'), edge('e2', 'ceo', 'cto')]);
    const [first, second] = layout.edges;

    expect(layout.edges.map((item) => item.parallelIndex)).toEqual([0, 1]);

    const source = layout.nodes.find((node) => node.id === 'cto')!;
    const target = layout.nodes.find((node) => node.id === 'ceo')!;
    const centerX = (source.x + target.x) / 2;
    const centerY = (source.y + target.y) / 2;

    // Uma de cada lado, e ambas longe o bastante da reta central para serem clicáveis.
    const offset = (item: { midX: number; midY: number }) =>
      Math.hypot(item.midX - centerX, item.midY - centerY);
    expect(offset(first!)).toBeGreaterThan(20);
    expect(offset(second!)).toBeGreaterThan(20);
    expect(Math.sign(first!.midX - centerX)).not.toBe(Math.sign(second!.midX - centerX));
  });

  it('devolve um grafo vazio sem explodir', () => {
    const layout = layoutGraph([], []);
    expect(layout.nodes).toEqual([]);
    expect(layout.edges).toEqual([]);
  });
});
