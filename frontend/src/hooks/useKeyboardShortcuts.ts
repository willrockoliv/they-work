import { useEffect } from 'react';

import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';

const PAN_STEP_TILES = 2;

/** Atalhos globais do observador onisciente. */
export function useKeyboardShortcuts(): void {
  useEffect(() => {
    const handler = (event: KeyboardEvent): void => {
      const target = event.target as HTMLElement | null;
      // Digitar num campo não deve pilotar a câmera.
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;

      const ui = useUiStore.getState();
      const game = useGameStore.getState();

      switch (event.key) {
        case 'Escape':
          ui.closePanel();
          break;
        case ' ':
          event.preventDefault();
          game.togglePaused();
          break;
        case 'ArrowLeft':
          ui.panBy(-PAN_STEP_TILES, 0);
          break;
        case 'ArrowRight':
          ui.panBy(PAN_STEP_TILES, 0);
          break;
        case 'ArrowUp':
          ui.panBy(0, -PAN_STEP_TILES);
          break;
        case 'ArrowDown':
          ui.panBy(0, PAN_STEP_TILES);
          break;
        case '+':
        case '=':
          ui.zoomBy(1.15);
          break;
        case '-':
        case '_':
          ui.zoomBy(1 / 1.15);
          break;
        case '0':
          ui.resetCamera();
          break;
        case 'c':
        case 'C':
          ui.toggleChat();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
