import { useEffect, useRef } from 'react';

import { MESSAGE_PREFIX, useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';

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
  const listRef = useRef<HTMLOListElement>(null);

  const filtered = filter ? messages.filter((message) => message.agentId === filter) : messages;

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [filtered.length]);

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
    <section className="chat-log" aria-label="Log de comunicações">
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
    </section>
  );
}
