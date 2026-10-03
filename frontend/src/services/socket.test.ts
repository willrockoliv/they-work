import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { GameEvent } from '@/types/events';

import { GameSocket, type WebSocketLike } from './socket';

class FakeSocket implements WebSocketLike {
  static instances: FakeSocket[] = [];
  closed = false;

  onopen: ((event: unknown) => void) | null = null;
  onclose: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  close(): void {
    this.closed = true;
  }

  open(): void {
    this.onopen?.({});
  }

  emit(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  emitRaw(data: unknown): void {
    this.onmessage?.({ data });
  }

  drop(): void {
    this.onclose?.({});
  }
}

function build(onEvent: (event: GameEvent) => void = () => {}) {
  return new GameSocket({
    url: 'ws://test/ws/game-state',
    onEvent,
    factory: (url) => new FakeSocket(url),
    baseDelayMs: 100,
    watchdogMs: 1_000,
  });
}

describe('GameSocket', () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('entrega eventos já desserializados', () => {
    const received: GameEvent[] = [];
    const socket = build((event) => received.push(event));
    socket.connect();
    FakeSocket.instances[0]!.open();
    FakeSocket.instances[0]!.emit({ event: 'heartbeat' });

    expect(socket.connectionState).toBe('open');
    expect(received).toEqual([{ event: 'heartbeat' }]);
    socket.dispose();
  });

  it('descarta payload que não é um evento conhecido', () => {
    const received: GameEvent[] = [];
    const socket = build((event) => received.push(event));
    socket.connect();
    FakeSocket.instances[0]!.open();
    FakeSocket.instances[0]!.emitRaw('{ json quebrado');
    FakeSocket.instances[0]!.emit({ sem: 'evento' });
    FakeSocket.instances[0]!.emitRaw(42);

    expect(received).toEqual([]);
    socket.dispose();
  });

  it('reconecta com backoff exponencial depois de cair', () => {
    const socket = build();
    socket.connect();
    FakeSocket.instances[0]!.open();

    FakeSocket.instances[0]!.drop();
    expect(socket.connectionState).toBe('reconnecting');

    vi.advanceTimersByTime(100);
    expect(FakeSocket.instances).toHaveLength(2);

    FakeSocket.instances[1]!.drop();
    vi.advanceTimersByTime(150);
    expect(FakeSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(100);
    expect(FakeSocket.instances).toHaveLength(3);

    socket.dispose();
  });

  it('zera o backoff quando a conexão volta a abrir', () => {
    const socket = build();
    socket.connect();
    FakeSocket.instances[0]!.drop();
    vi.advanceTimersByTime(200);
    expect(socket.retries).toBe(1);

    FakeSocket.instances[1]!.open();
    expect(socket.retries).toBe(0);
    socket.dispose();
  });

  it('o watchdog reconecta quando o servidor emudece', () => {
    const socket = build();
    socket.connect();
    FakeSocket.instances[0]!.open();

    vi.advanceTimersByTime(1_001);
    expect(socket.connectionState).toBe('reconnecting');
    expect(FakeSocket.instances[0]!.closed).toBe(true);

    vi.advanceTimersByTime(200);
    expect(FakeSocket.instances).toHaveLength(2);
    socket.dispose();
  });

  it('dispose impede qualquer reconexão posterior', () => {
    const socket = build();
    socket.connect();
    FakeSocket.instances[0]!.open();
    socket.dispose();

    vi.advanceTimersByTime(10_000);
    expect(FakeSocket.instances).toHaveLength(1);
    expect(socket.connectionState).toBe('closed');
  });
});
