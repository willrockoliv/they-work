import { useEffect, useRef } from 'react';

import { MESSAGE_PREFIX, useGameStore } from '@/store/gameStore';
import { type ChatSize, useUiStore } from '@/store/uiStore';

interface ResizeStart {
  x: number;
  y: number;
  width: number;
  height: number;
}

function sizeStyle(size: ChatSize): React.CSSProperties {
  return {
    width: size.width,
    height: size.height,
    maxWidth: 'calc(100% - 24px)',
    maxHeight: 'calc(100% - 24px)',
  };
}

/** Janela de chat geral: todas as falas, com filtro por agente. */
export function ChatLog(): React.JSX.Element | null {
  const messages = useGameStore((state) => state.messages);
  const agents = useGameStore((state) => state.agents);
  const order = useGameStore((state) => state.order);
  const clearMessages = useGameStore((state) => state.clearMessages);
  const visible = useUiStore((state) => state.chatVisible);
  const toggleChat = useUiStore((state) => state.toggleChat);
  const filter = useUiStore((state) => state.chatFilterAgentId);
  const setChatFilter = useUiStore((state) => state.setChatFilter);
  const chatSize = useUiStore((state) => state.chatSize);
  const setChatSize = useUiStore((state) => state.setChatSize);
  const listRef = useRef<HTMLOListElement>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const resizeRef = useRef<ResizeStart | null>(null);

  const filtered = filter ? messages.filter((message) => message.agentId === filter) : messages;

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [filtered.length]);

  function startResize(event: React.PointerEvent<HTMLDivElement>): void {
    const box = sectionRef.current?.getBoundingClientRect();
    if (!box) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    resizeRef.current = { x: event.clientX, y: event.clientY, width: box.width, height: box.height };
  }

  function resize(event: React.PointerEvent<HTMLDivElement>): void {
    const start = resizeRef.current;
    if (!start) return;
    // A alça fica no canto superior direito: arrastar para cima e para a direita aumenta o log.
    setChatSize(start.width + (event.clientX - start.x), start.height + (start.y - event.clientY));
  }

  function endResize(): void {
    resizeRef.current = null;
  }

  if (!visible) {
    return (
      <div className="chat-log" style={{ maxHeight: 'none' }}>
        <header>
          <strong>Comunicações</strong>
          <button type="button" style={{ marginLeft: 'auto' }} onClick={toggleChat}>
            Abrir (C)
          </button>
        </header>
      </div>
    );
  }

  return (
    <section
      ref={sectionRef}
      className="chat-log"
      aria-label="Log de comunicações"
      style={chatSize ? sizeStyle(chatSize) : undefined}
    >
      <header>
        <strong>Comunicações</strong>
        <select
          value={filter ?? ''}
          aria-label="Filtrar por agente"
          onChange={(event) => setChatFilter(event.target.value || null)}
        >
          <option value="">Todos</option>
          {order.map((id) => (
            <option key={id} value={id}>
              {agents[id]?.name ?? id}
            </option>
          ))}
        </select>
        <button type="button" onClick={clearMessages} aria-label="Limpar log">
          ␡
        </button>
        <button type="button" onClick={toggleChat} aria-label="Recolher log">
          −
        </button>
      </header>

      <ol ref={listRef}>
        {filtered.length === 0 ? (
          <li>
            <span className="who">—</span>
            <span className="what">Nenhuma comunicação registrada ainda.</span>
          </li>
        ) : null}
        {filtered.map((message) => (
          <li key={message.id} data-kind={message.kind}>
            <span className="who">
              {new Date(message.at).toLocaleTimeString('pt-BR')} · {message.agentName}
            </span>
            <span className="what">
              <em>{MESSAGE_PREFIX[message.kind]}:</em> {message.text}
            </span>
          </li>
        ))}
      </ol>
      <div
        className="chat-log-resize"
        title="Arraste para redimensionar"
        onPointerDown={startResize}
        onPointerMove={resize}
        onPointerUp={endResize}
        onPointerCancel={endResize}
      />
    </section>
  );
}
