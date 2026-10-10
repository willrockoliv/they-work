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

/** Dimensões do log de comunicações em pixels. */
export interface ChatSize {
  width: number;
  height: number;
}

export const CHAT_MIN_WIDTH = 280;
export const CHAT_MIN_HEIGHT = 160;
export const CHAT_MAX_WIDTH = 1600;
export const CHAT_MAX_HEIGHT = 1200;
const CHAT_SIZE_KEY = 'theywork.chatSize';

export interface UiStoreState {
  selectedAgentId: string | null;
  panelTab: PanelTab;
  panelExpanded: boolean;
  /** Painel recolhido para a direita, deixando só a aba de reabrir. */
  panelCollapsed: boolean;
  chatVisible: boolean;
  chatFilterAgentId: string | null;
  /** `null` = tamanho padrão do CSS. */
  chatSize: ChatSize | null;
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
  setChatSize: (width: number, height: number) => void;
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

function clampChatSize(width: number, height: number): ChatSize {
  return {
    width: Math.round(Math.min(CHAT_MAX_WIDTH, Math.max(CHAT_MIN_WIDTH, width))),
    height: Math.round(Math.min(CHAT_MAX_HEIGHT, Math.max(CHAT_MIN_HEIGHT, height))),
  };
}

/** Tamanho escolhido pelo usuário, lembrado entre recarregamentos. */
function readChatSize(): ChatSize | null {
  try {
    const raw = window.localStorage.getItem(CHAT_SIZE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ChatSize>;
    if (typeof parsed.width !== 'number' || typeof parsed.height !== 'number') return null;
    return clampChatSize(parsed.width, parsed.height);
  } catch {
    return null;
  }
}

function writeChatSize(size: ChatSize): void {
  try {
    window.localStorage.setItem(CHAT_SIZE_KEY, JSON.stringify(size));
  } catch {
    // Armazenamento indisponível: o tamanho vale apenas para esta sessão.
  }
}

export const useUiStore = create<UiStoreState>()((set, get) => ({
  selectedAgentId: null,
  panelTab: 'info',
  panelExpanded: false,
  panelCollapsed: false,
  chatVisible: true,
  chatFilterAgentId: null,
  chatSize: readChatSize(),
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

  setChatSize: (width, height) => {
    const size = clampChatSize(width, height);
    writeChatSize(size);
    set({ chatSize: size });
  },

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
