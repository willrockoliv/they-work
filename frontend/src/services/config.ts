/**
 * Origem da API.
 *
 * Em desenvolvimento o Vite faz proxy de `/api` e `/ws` para o backend, então a
 * base fica vazia e tudo trafega na mesma origem — sem CORS e sem porta fixa.
 */
const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export const API_BASE_URL = RAW_BASE.replace(/\/+$/, '');

/** Prefixo HTTP: usa o proxy do Vite quando não há base explícita. */
export const HTTP_PREFIX = API_BASE_URL === '' ? '/api' : API_BASE_URL;

/** Converte a origem HTTP em origem WebSocket. */
export function websocketUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  if (API_BASE_URL === '') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${normalized}`;
  }
  return `${API_BASE_URL.replace(/^http/, 'ws')}${normalized}`;
}

/** Intervalo máximo entre tentativas de reconexão do WebSocket, em ms. */
export const RECONNECT_MAX_DELAY_MS = 10_000;

/** Sem nenhuma mensagem nesse intervalo, a conexão é considerada morta. */
export const SOCKET_WATCHDOG_MS = 45_000;

/** Quantas mensagens o log de comunicações guarda. */
export const CHAT_LOG_LIMIT = 200;

/** Quantos eventos ficam represados enquanto a simulação está pausada. */
export const PAUSE_BUFFER_LIMIT = 500;
