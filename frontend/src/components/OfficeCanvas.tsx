import { useCallback, useEffect, useRef } from 'react';

import { OfficeRenderer, type SyncInput } from '@/engine/OfficeRenderer';
import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';

function buildSyncInput(): SyncInput {
  const game = useGameStore.getState();
  const ui = useUiStore.getState();
  return {
    agents: game.order.flatMap((id) => {
      const agent = game.agents[id];
      return agent ? [agent] : [];
    }),
    bubbles: game.bubbles,
    selectedAgentId: ui.selectedAgentId,
    paused: game.paused,
    speed: game.speed,
    zoom: ui.camera.zoom,
    focus: ui.camera.focus,
    theme: ui.theme,
  };
}

/** Hospeda o canvas do PixiJS e mantém o renderizador em dia com os stores. */
export function OfficeCanvas(): React.JSX.Element {
  const hostRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<OfficeRenderer | null>(null);
  const layout = useGameStore((state) => state.layout);
  const revision = useGameStore((state) => state.revision);

  const push = useCallback(() => {
    const renderer = rendererRef.current;
    if (renderer?.ready) renderer.sync(buildSyncInput());
  }, []);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const renderer = new OfficeRenderer({
      onSelectAgent: (agentId) => useUiStore.getState().selectAgent(agentId),
      onHotspot: (_roomId, center) => useUiStore.getState().focusOn(center.x, center.y, 1.6),
      onPan: (dx, dy) => useUiStore.getState().panBy(dx, dy),
      onZoom: (factor) => useUiStore.getState().zoomBy(factor),
      onZoomArea: (center, zoom) => useUiStore.getState().focusOn(center.x, center.y, zoom),
      onFit: (zoom, center) => useUiStore.getState().applyFit(zoom, center),
    });
    rendererRef.current = renderer;

    let disposed = false;
    void renderer.mount(host).then(() => {
      if (disposed) {
        renderer.destroy();
        return;
      }
      const state = useGameStore.getState();
      if (state.layout) renderer.setLayout(state.layout);
      push();
    });

    return () => {
      disposed = true;
      rendererRef.current = null;
      renderer.destroy();
    };
  }, [push]);

  useEffect(() => {
    if (layout && rendererRef.current?.ready) {
      rendererRef.current.setLayout(layout);
      push();
    }
  }, [layout, push]);

  // `revision` muda a cada evento aplicado: é o gatilho de reconciliação.
  useEffect(push, [revision, push]);

  // A câmera vive no `uiStore`; aqui só espelhamos no renderizador.
  useEffect(() => useUiStore.subscribe(push), [push]);

  return <div className="canvas-host" ref={hostRef} data-testid="office-canvas" />;
}
