import '@testing-library/jest-dom/vitest';

import { afterEach, vi } from 'vitest';

import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';

// jsdom não implementa nenhuma destas APIs; o canvas e o clipboard são dublês.
if (!('ResizeObserver' in globalThis)) {
  globalThis.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  } as unknown as typeof ResizeObserver;
}

if (typeof window.matchMedia !== 'function') {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

Object.defineProperty(navigator, 'clipboard', {
  configurable: true,
  value: { writeText: vi.fn().mockResolvedValue(undefined) },
});

const initialUi = useUiStore.getState();

afterEach(() => {
  useGameStore.getState().reset();
  useUiStore.setState(initialUi, true);
  vi.clearAllMocks();
});
