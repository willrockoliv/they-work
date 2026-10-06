import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';

import { Controls } from './Controls';

const CONNECTION_LABEL: Record<string, { text: string; tone: string }> = {
  open: { text: 'ao vivo', tone: 'ok' },
  connecting: { text: 'conectando', tone: 'warn' },
  reconnecting: { text: 'reconectando', tone: 'warn' },
  closed: { text: 'offline', tone: 'crit' },
};

function percent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

function compact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(Math.round(value));
}

/** Monitoramento global: relógio, Natureza, quadro de pessoal e economia. */
export function TopBar(): React.JSX.Element {
  const clock = useGameStore((state) => state.clock);
  const resources = useGameStore((state) => state.resources);
  const economy = useGameStore((state) => state.economy);
  const connection = useGameStore((state) => state.connection);
  const theme = useUiStore((state) => state.theme);
  const toggleTheme = useUiStore((state) => state.toggleTheme);
  const stageView = useUiStore((state) => state.stageView);
  const setStageView = useUiStore((state) => state.setStageView);

  const connectionInfo = CONNECTION_LABEL[connection] ?? CONNECTION_LABEL.closed!;

  return (
    <header className="topbar">
      <div className="brand">
        TheyWork<span>escritório virtual</span>
      </div>

      <div className="stage-switch" role="tablist" aria-label="Visão do palco">
        <button
          type="button"
          role="tab"
          aria-selected={stageView === 'office'}
          onClick={() => setStageView('office')}
        >
          Escritório
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={stageView === 'network'}
          onClick={() => setStageView('network')}
        >
          Rede corporativa
        </button>
      </div>

      <dl className="metric">
        <dt>Expediente</dt>
        <dd>{clock ? `Dia ${clock.day} · ${clock.label}` : '—'}</dd>
      </dl>

      <dl className="metric">
        <dt>RAM</dt>
        <dd>
          {resources
            ? `${compact(resources.ram_used_mb)} / ${compact(resources.ram_limit_mb)} MB`
            : '—'}
        </dd>
        <div className="gauge" data-level={resources?.status ?? 'HEALTHY'}>
          <i style={{ width: percent(resources?.ram_usage_ratio ?? 0) }} />
        </div>
      </dl>

      <dl className="metric">
        <dt>VRAM</dt>
        <dd>
          {!resources
            ? '—'
            : resources.gpu_detected
              ? `${compact(resources.vram_used_mb)} / ${compact(resources.vram_limit_mb)} MB`
              : 'sem GPU'}
        </dd>
        <div className="gauge" data-level={resources?.status ?? 'HEALTHY'}>
          <i style={{ width: percent(resources?.vram_usage_ratio ?? 0) }} />
        </div>
      </dl>

      <dl className="metric">
        <dt>Subagentes</dt>
        <dd>
          {resources
            ? `${resources.active_subagents}/${resources.max_concurrent_subagents} · fila ${resources.queued_hirings}`
            : '—'}
        </dd>
      </dl>

      <dl className="metric">
        <dt>Receita / Custo</dt>
        <dd>
          {economy
            ? `${compact(economy.revenue_tokens)} tok · ${compact(economy.cost_mb_s)} MB·s`
            : '—'}
        </dd>
      </dl>

      <span className="badge" data-tone={resources?.status ?? 'HEALTHY'}>
        Natureza {resources?.status ?? '—'}
      </span>

      <span className="badge" data-tone={connectionInfo.tone} title={`WebSocket ${connection}`}>
        {connectionInfo.text}
      </span>

      <Controls />

      <button
        type="button"
        onClick={toggleTheme}
        aria-label={theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'}
      >
        {theme === 'dark' ? '☀' : '☾'}
      </button>
    </header>
  );
}
