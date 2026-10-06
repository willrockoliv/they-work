import { useState } from 'react';

import { useGameStore } from '@/store/gameStore';
import { useUiStore, type PanelTab } from '@/store/uiStore';

import { HistoryTab } from './HistoryTab';
import { InfoTab } from './InfoTab';
import { ReasoningFlowTab } from './ReasoningFlowTab';

const TABS: { id: PanelTab; label: string }[] = [
  { id: 'info', label: 'Info' },
  { id: 'flow', label: 'Raciocínio' },
  { id: 'history', label: 'Histórico' },
];

/** Raio-X cognitivo do agente selecionado. */
export function SidePanel(): React.JSX.Element {
  const selectedAgentId = useUiStore((state) => state.selectedAgentId);
  const panelTab = useUiStore((state) => state.panelTab);
  const panelExpanded = useUiStore((state) => state.panelExpanded);
  const panelCollapsed = useUiStore((state) => state.panelCollapsed);
  const setPanelTab = useUiStore((state) => state.setPanelTab);
  const togglePanelExpanded = useUiStore((state) => state.togglePanelExpanded);
  const togglePanelCollapsed = useUiStore((state) => state.togglePanelCollapsed);
  const closePanel = useUiStore((state) => state.closePanel);
  const agent = useGameStore((state) => (selectedAgentId ? state.agents[selectedAgentId] : null));

  const [historySessionId, setHistorySessionId] = useState<string | undefined>(undefined);

  if (panelCollapsed) {
    return (
      <aside className="side-panel collapsed" aria-label="Raio-X cognitivo recolhido">
        <button
          type="button"
          onClick={togglePanelCollapsed}
          aria-expanded={false}
          aria-label="Reabrir o raio-X cognitivo"
          title="Reabrir o raio-X cognitivo"
        >
          ‹
        </button>
      </aside>
    );
  }

  if (!agent) {
    return (
      <aside className="side-panel" aria-label="Raio-X cognitivo">
        <div className="panel-toolbar">
          <button
            type="button"
            onClick={togglePanelCollapsed}
            aria-expanded
            aria-label="Recolher o raio-X cognitivo"
            title="Recolher o raio-X cognitivo"
          >
            ›
          </button>
        </div>
        <p className="empty">
          Clique num agente do escritório para abrir o raio-X do raciocínio dele.
        </p>
      </aside>
    );
  }

  return (
    <aside className="side-panel" aria-label={`Raio-X cognitivo de ${agent.name}`}>
      <header>
        <div className="header-row">
          <div>
            <h2>{agent.name}</h2>
            <p>
              {agent.job_title ?? agent.role} · {agent.model_name ?? 'sem modelo'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              type="button"
              onClick={togglePanelExpanded}
              aria-pressed={panelExpanded}
              aria-label={panelExpanded ? 'Recolher painel' : 'Expandir painel'}
            >
              {panelExpanded ? '⤡' : '⤢'}
            </button>
            <button
              type="button"
              onClick={togglePanelCollapsed}
              aria-expanded
              aria-label="Recolher o raio-X cognitivo"
              title="Recolher o raio-X cognitivo"
            >
              ›
            </button>
            <button type="button" onClick={closePanel} aria-label="Fechar painel (ESC)">
              ✕
            </button>
          </div>
        </div>
      </header>

      <div className="tabs" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={panelTab === tab.id}
            aria-pressed={panelTab === tab.id}
            onClick={() => {
              setPanelTab(tab.id);
              if (tab.id !== 'flow') setHistorySessionId(undefined);
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="panel-body" role="tabpanel">
        {panelTab === 'info' ? <InfoTab agent={agent} /> : null}
        {panelTab === 'flow' ? (
          <ReasoningFlowTab agent={agent} sessionId={historySessionId} />
        ) : null}
        {panelTab === 'history' ? (
          <HistoryTab
            agent={agent}
            onOpenSession={(sessionId) => {
              setHistorySessionId(sessionId);
              setPanelTab('flow');
            }}
          />
        ) : null}
      </div>
    </aside>
  );
}
