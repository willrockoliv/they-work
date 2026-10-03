import type { GameEvent } from '@/types/events';
import { isGameEvent } from '@/types/events';

import { RECONNECT_MAX_DELAY_MS, SOCKET_WATCHDOG_MS } from './config';

export type ConnectionState = 'connecting' | 'open' | 'reconnecting' | 'closed';

/** Subconjunto do `WebSocket` do browser que o cliente realmente usa. */
export interface WebSocketLike {
  close(): void;
  onopen: ((event: unknown) => void) | null;
  onclose: ((event: unknown) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
}

export interface GameSocketOptions {
  url: string;
  onEvent: (event: GameEvent) => void;
  onStateChange?: (state: ConnectionState) => void;
  /** Injetável nos testes; por padrão usa o `WebSocket` nativo. */
  factory?: (url: string) => WebSocketLike;
  /** Base do backoff exponencial, em ms. */
  baseDelayMs?: number;
  /** Sem mensagem nesse intervalo, a conexão é dada como morta. */
  watchdogMs?: number;
}

const INITIAL_DELAY_MS = 500;

/**
 * Cliente do canal `/ws/game-state`.
 *
 * O servidor emite `game.tick`/`heartbeat` a cada poucos segundos: o silêncio
 * prolongado é o único sinal confiável de queda em redes que não fecham o socket.
 */
export class GameSocket {
  private socket: WebSocketLike | null = null;
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private watchdogTimer: ReturnType<typeof setTimeout> | null = null;
  private disposed = false;
  private state: ConnectionState = 'closed';

  private readonly factory: (url: string) => WebSocketLike;
  private readonly baseDelayMs: number;
  private readonly watchdogMs: number;

  constructor(private readonly options: GameSocketOptions) {
    this.factory = options.factory ?? ((url) => new WebSocket(url) as unknown as WebSocketLike);
    this.baseDelayMs = options.baseDelayMs ?? INITIAL_DELAY_MS;
    this.watchdogMs = options.watchdogMs ?? SOCKET_WATCHDOG_MS;
  }

  get connectionState(): ConnectionState {
    return this.state;
  }

  /** Quantas reconexões consecutivas falharam. Zera a cada `open`. */
  get retries(): number {
    return this.attempt;
  }

  connect(): void {
    if (this.disposed || this.socket) return;
    this.setState(this.attempt === 0 ? 'connecting' : 'reconnecting');

    const socket = this.factory(this.options.url);
    this.socket = socket;

    socket.onopen = () => {
      this.attempt = 0;
      this.setState('open');
      this.armWatchdog();
    };
    socket.onmessage = (event) => {
      this.armWatchdog();
      this.handleMessage(event.data);
    };
    socket.onerror = () => this.scheduleReconnect();
    socket.onclose = () => this.scheduleReconnect();
  }

  /** Encerra em definitivo: nenhuma reconexão é tentada depois disto. */
  dispose(): void {
    this.disposed = true;
    this.clearTimers();
    this.detach();
    this.setState('closed');
  }

  private handleMessage(raw: unknown): void {
    if (typeof raw !== 'string') return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    if (isGameEvent(parsed)) this.options.onEvent(parsed);
  }

  private scheduleReconnect(): void {
    if (this.disposed || this.reconnectTimer) return;
    this.detach();
    this.setState('reconnecting');

    const delay = this.nextDelay();
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  /** Backoff exponencial com teto; o jitter evita reconexões em manada. */
  private nextDelay(): number {
    const exponential = this.baseDelayMs * 2 ** Math.min(this.attempt, 6);
    const capped = Math.min(exponential, RECONNECT_MAX_DELAY_MS);
    return Math.round(capped * (0.7 + Math.random() * 0.3));
  }

  private armWatchdog(): void {
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    this.watchdogTimer = setTimeout(() => {
      this.watchdogTimer = null;
      this.scheduleReconnect();
    }, this.watchdogMs);
  }

  private detach(): void {
    const socket = this.socket;
    this.socket = null;
    if (!socket) return;
    socket.onopen = null;
    socket.onclose = null;
    socket.onerror = null;
    socket.onmessage = null;
    try {
      socket.close();
    } catch {
      // O socket já pode estar fechando; nada a fazer.
    }
  }

  private clearTimers(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    this.reconnectTimer = null;
    this.watchdogTimer = null;
  }

  private setState(state: ConnectionState): void {
    if (this.state === state) return;
    this.state = state;
    this.options.onStateChange?.(state);
  }
}
