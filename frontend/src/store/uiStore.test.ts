import { describe, expect, it } from 'vitest';

import { MAX_ZOOM, MIN_ZOOM, useUiStore } from './uiStore';

function ui() {
  return useUiStore.getState();
}

describe('uiStore', () => {
  it('selecionar um agente não expande o painel sozinho', () => {
    ui().togglePanelExpanded();
    ui().selectAgent('agent-1');
    expect(ui().selectedAgentId).toBe('agent-1');
    expect(ui().panelExpanded).toBe(true);
  });

  it('limpar a seleção recolhe o painel', () => {
    ui().selectAgent('agent-1');
    ui().togglePanelExpanded();
    ui().selectAgent(null);
    expect(ui().selectedAgentId).toBeNull();
    expect(ui().panelExpanded).toBe(false);
  });

  it('fechar o painel limpa seleção e expansão', () => {
    ui().selectAgent('agent-1');
    ui().setPanelTab('history');
    ui().closePanel();
    expect(ui().selectedAgentId).toBeNull();
    // A aba escolhida sobrevive: reabrir volta onde o observador estava.
    expect(ui().panelTab).toBe('history');
  });

  it('o zoom respeita os limites', () => {
    ui().setZoom(99);
    expect(ui().camera.zoom).toBe(MAX_ZOOM);
    ui().setZoom(0.001);
    expect(ui().camera.zoom).toBe(MIN_ZOOM);
  });

  it('zoomBy multiplica dentro dos limites', () => {
    ui().setZoom(1);
    ui().zoomBy(2);
    expect(ui().camera.zoom).toBe(2);
    ui().zoomBy(100);
    expect(ui().camera.zoom).toBe(MAX_ZOOM);
  });

  it('panBy parte do centro quando a câmera é automática', () => {
    ui().panBy(3, -2);
    expect(ui().camera.focus).toEqual({ x: 3, y: -2 });
    ui().panBy(1, 1);
    expect(ui().camera.focus).toEqual({ x: 4, y: -1 });
  });

  it('focusOn fixa o foco e opcionalmente o zoom', () => {
    ui().focusOn(10, 5);
    expect(ui().camera).toEqual({ zoom: 1, focus: { x: 10, y: 5 } });
    ui().focusOn(1, 2, 1.6);
    expect(ui().camera).toEqual({ zoom: 1.6, focus: { x: 1, y: 2 } });
  });

  it('applyFit só vale enquanto a câmera é automática', () => {
    ui().applyFit(0.76, { x: 20, y: 12 });
    expect(ui().camera).toEqual({ zoom: 0.76, focus: { x: 20, y: 12 } });

    // Com foco já definido, o enquadramento proposto é ignorado.
    ui().applyFit(2, { x: 0, y: 0 });
    expect(ui().camera).toEqual({ zoom: 0.76, focus: { x: 20, y: 12 } });
  });

  it('resetCamera devolve a câmera ao modo automático', () => {
    ui().focusOn(10, 5, 2);
    ui().resetCamera();
    expect(ui().camera.focus).toBeNull();
  });

  it('o tema alterna e marca o documento', () => {
    ui().toggleTheme();
    expect(ui().theme).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    ui().toggleTheme();
    expect(ui().theme).toBe('dark');
  });

  it('o log de comunicações liga e desliga com filtro independente', () => {
    ui().setChatFilter('agent-2');
    ui().toggleChat();
    expect(ui().chatVisible).toBe(false);
    expect(ui().chatFilterAgentId).toBe('agent-2');
  });
});
