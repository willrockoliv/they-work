# API de observabilidade cognitiva

Endpoints REST e canais WebSocket da Fase 3. Todos expostos sem prefixo (`API_PREFIX` vazio
por padrão) e documentados automaticamente em `http://127.0.0.1:8000/docs`.

Formatos complementares: [`REASONING-FORMAT.md`](REASONING-FORMAT.md) (contrato dos passos) e
[`FLOWCHART-SCHEMA.md`](FLOWCHART-SCHEMA.md) (grafo).

---

## 1. Execução observável

### `POST /agents/{agent_id}/reasoning/run` → `201`

Executa uma tarefa no agente capturando todo o ciclo ReAct. Síncrono: devolve a sessão já
encerrada, com todos os passos. Os passos são transmitidos pelo WebSocket **enquanto** a
requisição ainda está em curso.

```jsonc
// request
{
  "task": "Avaliar se devemos investir em retenção neste trimestre",
  "complexity": "MODERATE",        // opcional; inferido pelo classificador
  "thread_id": null,               // opcional; correlaciona com uma deliberação
  "max_steps": 4,                  // opcional; default REASONING_MAX_STEPS
  "context": { "origem": "CEO" }   // opcional; injetado no prompt
}
```

```jsonc
// response 201
{
  "id": "1dfa5270-…",
  "agent_id": "10f20d1d-…",
  "task": "…",
  "status": "COMPLETED",
  "complexity": "MODERATE",
  "model_name": "llama3.2:3b",
  "step_count": 5,
  "prompt_tokens": 1204, "completion_tokens": 475, "total_tokens": 1679,
  "duration_ms": 79808,
  "conclusion": "…",
  "error": null,
  "started_at": "…", "finished_at": "…",
  "steps": [ { "id": 1, "sequence": 1, "step_type": "THOUGHT", "content": "…", "payload": {} } ]
}
```

| Código | Quando |
|---|---|
| `201` | execução concluída (mesmo que o status interno seja `FAILED`) |
| `404` | agente inexistente |
| `422` | `task` com menos de 3 caracteres ou `max_steps` fora de `1..32` |

---

## 2. Consulta

### `GET /agents/{agent_id}/reasoning-flow` → `200`

Fluxograma da sessão **em execução** do agente ou, na falta dela, da última encerrada.
Schema em [`FLOWCHART-SCHEMA.md`](FLOWCHART-SCHEMA.md). Responde `404` se o agente nunca
raciocinou.

### `GET /agents/{agent_id}/live-status` → `200`

Estado corrente para a barra de progresso do painel onisciente.

```jsonc
{
  "agent_id": "…", "agent_name": "Analista de Dados #1", "agent_status": "WORKING",
  "model_name": "llama3.2:3b",
  "session_id": "…", "reasoning_status": "RUNNING", "task": "…",
  "step_count": 3,
  "progress": 0.75,              // step_count / REASONING_MAX_STEPS, teto 0.99 enquanto RUNNING
  "last_step_type": "OBSERVATION",
  "last_action": "infraestrutura(capacidade atual)",
  "elapsed_ms": 4120,
  "started_at": "…", "conclusion": null, "error": null
}
```

Agente sem nenhuma sessão devolve `200` com `session_id: null` e `progress: 0.0`.

### `GET /reasoning/sessions` → `200`

| Query | Tipo | Padrão |
|---|---|---|
| `agent_id` | UUID | — |
| `reasoning_status` | `RUNNING`·`COMPLETED`·`FAILED`·`CANCELLED` | — |
| `limit` | int | `50` |

Ordenado por `started_at` decrescente. Devolve `{ total, sessions[] }` sem os passos.

### `GET /reasoning/sessions/{session_id}` → `200`

Replay completo: a sessão com `steps[]` na ordem original. `404` se não existir.

### `GET /reasoning/sessions/{session_id}/flow` → `200`

Fluxograma de uma sessão específica (útil para revisitar decisões históricas).

---

## 3. WebSocket

### `WS /ws/agents/{agent_id}/reasoning`

Fluxo cognitivo de um único agente. Na conexão, envia **primeiro** um evento `replay` com o
histórico já persistido e só depois os eventos ao vivo — isso elimina a janela de corrida
entre conectar e começar a receber.

### `WS /ws/reasoning`

Canal global: recebe os eventos de todos os agentes. Não envia `replay`.

### Envelope dos eventos

```jsonc
{ "event": "<tipo>", "session_id": "<uuid|null>", "data": { … } }
```

| `event` | `data` | Quando |
|---|---|---|
| `replay` | sessão + `steps[]` completos (ou `null`) | apenas no canal por agente, na conexão |
| `session.started` | resumo da sessão com `status: "RUNNING"` | início da execução |
| `step` | passo serializado (`sequence`, `step_type`, `content`, `payload`, `tokens`, `duration_ms`) | a cada nó do ciclo ReAct |
| `session.finished` | resumo com status final, `conclusion` e `error` | encerramento |
| `heartbeat` | *(sem `data`)* | 20 s sem atividade |

Exemplo de sessão real no canal global:

```text
session.started   | RUNNING
step              | THOUGHT     | "A capacidade total de RAM disponível…"
step              | ACTION      | "infraestrutura(capacidade atual)"
step              | OBSERVATION | "A infraestrutura da empresa opera com folga…"
step              | CONCLUSION  | "…"
session.finished  | COMPLETED
```

### Backpressure

Cada assinante tem uma fila de `REASONING_STREAM_BUFFER` eventos (padrão 256). Se o cliente
não consumir a tempo, o evento **mais antigo** é descartado — o painel sempre mostra o estado
mais recente, nunca trava o backend.

---

## 4. Métricas, export e retenção

### `GET /reasoning/metrics` → `200`

| Query | Tipo | Efeito |
|---|---|---|
| `since` | datetime ISO | considera apenas sessões iniciadas depois |

```jsonc
{
  "total_sessions": 2, "completed": 2, "failed": 0, "running": 0,
  "success_rate": 1.0,
  "total_tokens": 1679, "prompt_tokens": 1204, "completion_tokens": 475,
  "avg_duration_ms": 39951.0, "avg_steps": 6.0,
  "cost_mb_s": 163928.06,
  "by_model":     [ { "model": "llama3.2:3b", "sessions": 1, "total_tokens": 1679, "avg_duration_ms": 79808.0 } ],
  "by_agent":     [ { "agent_id": "…", "name": "…", "role": "SUBAGENT", "sessions": 1, "completed": 1,
                      "total_tokens": 1679, "avg_duration_ms": 79808.0, "cost_mb_s": 163928.06, "roi": 0.000006 } ],
  "by_step_type": [ { "step_type": "THOUGHT", "count": 4, "total_tokens": 1679, "avg_duration_ms": 1200.0 } ]
}
```

- `success_rate` = `completed / (completed + failed)`; sessões `RUNNING` não contam.
- `cost_mb_s` = Σ `estimated_ram_mb × duration_ms / 1000` — a única moeda do sandbox.
- `roi` = conclusões entregues por MB·s consumido.
- `by_step_type` sempre lista os quatro tipos, inclusive com `count: 0`.

### `GET /reasoning/export` → `200`

| Query | Tipo | Padrão |
|---|---|---|
| `agent_id` | UUID | — |
| `since` | datetime ISO | — |
| `limit` | int | `100` |

Devolve `{ total, sessions[] }` com cada sessão acompanhada de `steps[]` e `cost_mb_s` —
dump completo para análise fora do sandbox.

### `POST /reasoning/retention/purge` → `200`

```jsonc
// request — `before` opcional; default = agora - REASONING_RETENTION_DAYS
{ "before": "2026-09-03T00:00:00Z" }

// response
{ "removed": 12, "retention_days": 30 }
```

Sessões com status `RUNNING` **nunca** são removidas. A operação deixa um evento
`REASONING_PURGED` na trilha de auditoria.

---

## 5. Auditoria correlata

Toda sessão alimenta `audit_logs` e aparece em `GET /nature/audit`:

| `event_type` | Momento |
|---|---|
| `REASONING_STARTED` | abertura da sessão |
| `REASONING_COMPLETED` | encerramento com sucesso |
| `REASONING_FAILED` | encerramento em erro |
| `REASONING_PURGED` | execução da política de retenção |

---

## 6. Exemplo ponta a ponta

```bash
# 1. Agente qualquer (um Chief recém-inicializado serve)
AGENT=$(curl -s localhost:8000/agents/status | jq -r '.chiefs[0].id')

# 2. Execução com captura
curl -s -X POST "localhost:8000/agents/$AGENT/reasoning/run" \
  -H 'content-type: application/json' \
  -d '{"task":"Quanta RAM sobra para novos subagentes?","max_steps":2}' | jq '.status, .step_count'

# 3. Fluxograma e status
curl -s "localhost:8000/agents/$AGENT/reasoning-flow" | jq '.meta'
curl -s "localhost:8000/agents/$AGENT/live-status"    | jq '.progress, .last_action'

# 4. Painel de métricas
curl -s localhost:8000/reasoning/metrics | jq '.success_rate, .by_model'
```
