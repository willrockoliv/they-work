import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, request } from './http';

function mockFetch(response: Response): ReturnType<typeof vi.fn> {
  const spy = vi.fn().mockResolvedValue(response);
  vi.stubGlobal('fetch', spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('request', () => {
  it('chama o proxy do Vite e devolve o JSON tipado', async () => {
    const spy = mockFetch(new Response(JSON.stringify({ total: 2 }), { status: 200 }));
    const body = await request<{ total: number }>('/game/state');

    expect(body).toEqual({ total: 2 });
    expect(spy.mock.calls[0]?.[0]).toBe('/api/game/state');
    expect(spy.mock.calls[0]?.[1]).toMatchObject({ method: 'GET' });
  });

  it('monta a query string ignorando valores indefinidos', async () => {
    const spy = mockFetch(new Response('{}', { status: 200 }));
    await request('/reasoning/sessions', {
      query: { agent_id: 'a1', limit: 10, since: undefined },
    });

    expect(spy.mock.calls[0]?.[0]).toBe('/api/reasoning/sessions?agent_id=a1&limit=10');
  });

  it('serializa o corpo e declara o content-type no POST', async () => {
    const spy = mockFetch(new Response('{}', { status: 200 }));
    await request('/agents/a1/move', { method: 'POST', body: { x: 1, y: 2 } });

    expect(spy.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: '{"x":1,"y":2}',
      headers: { 'Content-Type': 'application/json' },
    });
  });

  it('transforma resposta de erro em ApiError com o detalhe da API', async () => {
    mockFetch(new Response(JSON.stringify({ detail: 'Agente não encontrado.' }), { status: 404 }));

    const erro = await request('/agents/x/position').catch((cause: unknown) => cause);
    expect(erro).toBeInstanceOf(ApiError);
    expect((erro as ApiError).status).toBe(404);
    expect((erro as ApiError).detail).toBe('Agente não encontrado.');
  });

  it('tolera corpo de erro que não é JSON', async () => {
    mockFetch(new Response('<html>502</html>', { status: 502, statusText: 'Bad Gateway' }));

    const erro = (await request('/game/state').catch((cause: unknown) => cause)) as ApiError;
    expect(erro.detail).toBe('Bad Gateway');
  });

  it('204 não tenta desserializar corpo', async () => {
    mockFetch(new Response(null, { status: 204 }));
    await expect(request('/game/state')).resolves.toBeUndefined();
  });
});
