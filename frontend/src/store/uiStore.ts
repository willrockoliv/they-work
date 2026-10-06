import { create } from 'zustand';

export type PanelTab = 'info' | 'flow' | 'history';
export type StageView = 'office' | 'network';
export type Theme = 'dark' | 'light';

export interface Camera {
  zoom: number;
  /** Centro da câmera em tiles. `null` = deixa o renderizador enquadrar o mapa. */
  focus: { x: number; y: number } | null;
}

export const MIN_ZOOM = 0.4;
export const MAX_ZOOM = 3;

export interface UiStoreState {
  selectedAgentId: string | null;
  panelTab: PanelTab;
  panelExpanded: boolean;
  /** Painel recolhido para a direita, deixando só a aba de reabrir. */
  panelCollapsed: boolean;
  chatVisible: boolean;
  chatFilterAgentId: string | null;
  theme: Theme;
  camera: Camera;
  stageView: StageView;
  selectedRequestId: string | null;

  selectAgent: (agentId: string | null) => void;
  setPanelTab: (tab: PanelTab) => void;
  setStageView: (view: StageView) => void;
  selectRequest: (requestId: string | null) => void;
  togglePanelCollapsed: () => void;
  togglePanelExpanded: () => void;
  closePanel: () => void;
  toggleChat: () => void;
  setChatFilter: (agentId: string | null) => void;
  toggleTheme: () => void;
  setZoom: (zoom: number) => void;
  zoomBy: (factor: number) => void;
  panBy: (dx: number, dy: number) => void;
  focusOn: (x: number, y: number, zoom?: number) => void;
  /** Enquadramento proposto pelo renderizador; só vale enquanto a câmera é automática. */
  applyFit: (zoom: number, center: { x: number; y: number }) => void;
  resetCamera: () => void;
}

const DEFAULT_CAMERA: Camera = { zoom: 1, focus: null };

function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(zoom.toFixed(3))));
}

export const useUiStore = create<UiStoreState>()((set, get) => ({
  selectedAgentId: null,
  panelTab: 'info',
  panelExpanded: false,
  panelCollapsed: false,
  chatVisible: true,
  chatFilterAgentId: null,
  theme: 'dark',
  camera: DEFAULT_CAMERA,
  stageView: 'office',
  selectedRequestId: null,

  selectAgent: (agentId) =>
    set((state) => ({
      selectedAgentId: agentId,
      panelExpanded: agentId === null ? false : state.panelExpanded,
      // Escolher um agente é pedir para ver o raio-X dele: reabre o painel.
      panelCollapsed: agentId === null ? state.panelCollapsed : false,
    })),

  togglePanelCollapsed: () => set((state) => ({ panelCollapsed: !state.panelCollapsed })),

  setPanelTab: (panelTab) => set({ panelTab }),

  setStageView: (stageView) => set({ stageView }),

  selectRequest: (selectedRequestId) => set({ selectedRequestId }),

  togglePanelExpanded: () => set((state) => ({ panelExpanded: !state.panelExpanded })),

  closePanel: () => set({ selectedAgentId: null, panelExpanded: false }),

  toggleChat: () => set((state) => ({ chatVisible: !state.chatVisible })),

  setChatFilter: (chatFilterAgentId) => set({ chatFilterAgentId }),

  toggleTheme: () => {
    const theme: Theme = get().theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    set({ theme });
  },

  setZoom: (zoom) => set((state) => ({ camera: { ...state.camera, zoom: clampZoom(zoom) } })),

  zoomBy: (factor) =>
    set((state) => ({ camera: { ...state.camera, zoom: clampZoom(state.camera.zoom * factor) } })),

  panBy: (dx, dy) =>
    set((state) => {
      const focus = state.camera.focus ?? { x: 0, y: 0 };
      return { camera: { ...state.camera, focus: { x: focus.x + dx, y: focus.y + dy } } };
    }),

  focusOn: (x, y, zoom) =>
    set((state) => ({
      camera: { zoom: zoom === undefined ? state.camera.zoom : clampZoom(zoom), focus: { x, y } },
    })),

  applyFit: (zoom, center) =>
    set((state) =>
      state.camera.focus ? state : { camera: { zoom: clampZoom(zoom), focus: center } },
    ),

  resetCamera: () => set({ camera: DEFAULT_CAMERA }),
}));
