import { useEffect, useRef } from 'react';

import { api } from '@/services/api';
import { websocketUrl } from '@/services/config';
import { GameSocket } from '@/services/socket';
import { useGameStore } from '@/store/gameStore';

/**
 * Liga o store ao backend: snapshot inicial por HTTP, atualizações por WebSocket.
 *
 * O snapshot por HTTP não é redundante — ele popula a tela antes do handshake do
 * socket, que também reenvia `game.snapshot` ao conectar e ao reconectar.
 */
export function useGameSocket(): void {
  const applyEvent = useGameStore((state) => state.applyEvent);
  const hydrate = useGameStore((state) => state.hydrate);
  const setConnection = useGameStore((state) => state.setConnection);
  const socketRef = useRef<GameSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    void api
      .gameState()
      .then((state) => {
        if (!cancelled) hydrate(state);
      })
      .catch((error: unknown) => {
        console.error('Falha ao carregar o estado inicial do mundo', error);
      });

    const socket = new GameSocket({
      url: websocketUrl('/ws/game-state'),
      onEvent: applyEvent,
      onStateChange: setConnection,
    });
    socketRef.current = socket;
    socket.connect();

    return () => {
      cancelled = true;
      controller.abort();
      socket.dispose();
      socketRef.current = null;
    };
  }, [applyEvent, hydrate, setConnection]);
}
