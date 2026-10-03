# Progresso: Fase 3 - Transparência e Observabilidade

**Plano:** [2026-10-03-fase-3-transparencia-observabilidade.md](../completed/2026-10-03-fase-3-transparencia-observabilidade.md)
**Status:** ✅ Concluído
**Início:** 2026-10-03 · **Conclusão:** 2026-10-03

---

## 1. O que foi entregue

| Camada | Arquivos | Entrega |
|--------|----------|---------|
| Modelos | `models/reasoning.py`, `models/enums.py` | `ReasoningSession` + `ReasoningStep`, enums `ReasoningStepType`/`ReasoningStatus` e 4 novos `AuditEventType` |
| Migração | `alembic/versions/0003_fase_3_observabilidade.py` | 2 tabelas, 2 tipos enum novos, 4 valores em `audit_event_type`, 4 índices |
| Interceptação | `services/reasoning_tracer.py` | Callbacks `on_thought/on_action/on_observation/on_conclusion`, contabilidade de tokens, auditoria e publicação |
| Streaming | `services/ollama_client.py` | `generate()` sobre `POST /api/generate` com `stream=true`, callback por token e `OllamaCompletion` |
| Barramento | `services/reasoning_broker.py` | Pub/sub in-process, canal por agente + global, backpressure por descarte do mais antigo |
| Motor | `services/react_engine.py` | Loop ReAct, parser tolerante, teto de passos, fallback determinístico offline |
| Ferramentas | `services/reasoning_tools.py` | 5 ferramentas offline com captura integral de entrada/saída |
| Fluxograma | `services/reasoning_flow.py` | Grafo `{nodes, edges, meta}` com layout hints e aresta de ciclo |
| Métricas | `services/reasoning_metrics.py`, `services/reasoning_service.py` | Agregações, custo em MB·s, ROI, retenção e export |
| API | `routes/reasoning.py`, `routes/ws.py`, `schemas/reasoning.py` | 9 endpoints REST + 2 canais WebSocket |
| Testes | 4 arquivos novos + extensões | 255 testes no total (87 novos), 98% de cobertura |
| Docs | `REASONING-FORMAT.md`, `API-REASONING.md`, `FLOWCHART-SCHEMA.md` | + `ARCHITECTURE.md` §4.8 e `README.md` |

---

## 2. Decisões importantes

### ADR-004 — Wrapper próprio em vez de LangGraph/CrewAI

O PRD sugeria LangGraph ou CrewAI. Ambos foram descartados:

- arrastam dezenas de dependências transitivas **sem pin**, o que colide frontalmente com a
  regra do projeto de fixar todas as versões;
- assumem rede disponível (telemetria, downloads de tokenizers) num sistema que roda 100%
  offline;
- escondem o prompt real atrás de abstrações, justamente o que a Fase 3 precisa expor.

A interceptação acabou sendo trivial sobre o streaming nativo do Ollama. O loop completo
tem ~180 linhas, zero dependências novas e controle total do que entra na trilha.

### ADR-005 — Uma tabela em vez de quatro

O plano original previa `reasoning_logs`, `action_logs`, `observation_logs` e
`conclusion_logs`. As quatro teriam colunas idênticas e exigiriam quatro JOINs (mais uma
ordenação por timestamp entre tabelas) para reconstruir o fluxograma. Substituídas por
`reasoning_steps` com discriminador `step_type` + `sequence` monotônico + `payload` JSONB.

### ADR-006 — Broker in-process, não Redis

O backend roda num único worker. O Redis entra como transporte na Fase 4; `ReasoningBroker`
já é a única superfície que as rotas enxergam, então a troca não toca na API.

### ADR-007 — Captura síncrona

O passo é persistido e publicado no mesmo ponto do código. Sem fila intermediária não existe
cenário de passo perdido ou fora de ordem.

### Offline-first como requisito, não como fallback de emergência

Durante o desenvolvimento ficou claro que **só `llama3.2:3b` estava baixado** na máquina de
testes, enquanto os Chiefs usam modelos maiores. Em vez de falhar, o motor cai num planejador
determinístico que escolhe a ferramenta por heurística lexical, executa a consulta de verdade
e conclui a partir da observação obtida. A sessão continua integralmente capturada e
transmitida; muda apenas `total_tokens = 0`. Isso também tornou toda a suíte de testes
executável sem nenhum mock de LLM nos casos de fallback.

---

## 3. Aprendizados e armadilhas

### Manter o backend síncrono

As rotas das Fases 1 e 2 são todas `def` (threadpool do FastAPI) com `Session` síncrona. Para
não introduzir um modelo misto, `react_engine.run_task` também é síncrono e chama o cliente
async do Ollama por uma ponte (`_await`): `asyncio.run` quando não há loop; `ThreadPoolExecutor`
dedicado quando há. Custo irrelevante diante da latência de um LLM local.

### `publish` tem que funcionar de qualquer thread

O tracer é chamado do threadpool do FastAPI, mas os assinantes WebSocket vivem no event loop
principal. `asyncio.Queue.put_nowait` chamado de outra thread é **inseguro**. Solução: cada
`Subscription` guarda o loop em que foi criada (`asyncio.get_running_loop()` no `subscribe`) e
`publish` entrega via `loop.call_soon_threadsafe`.

### `dependency_overrides` também vale para WebSocket

A primeira versão de `routes/ws.py` abria a própria sessão de banco (via um `session_scope` que
nem existia). Usar `DbSession` como dependência do handler WebSocket funciona normalmente no
FastAPI e permite que o `conftest` substitua o banco nos testes — sem isso o replay seria
intestável.

### Replay antes do stream elimina a corrida

Se o cliente conectar enquanto o agente já está raciocinando, os passos anteriores se perdem.
O handler envia o histórico persistido **antes** de entrar no laço de consumo do broker.

### Parser precisa ser tolerante

Modelos pequenos quebram o formato com frequência: acentuação ausente, `**Ação**` em negrito,
`Ferramenta:` em vez de `Ação:`, nome da ferramenta capitalizado (`Infraestrutura()`). O parser
normaliza acentos/caixa e `reasoning_tools.get_tool` faz lookup normalizado. Se nada casar, a
resposta crua vira pensamento + conclusão — a execução nunca trava por desvio de formato.

### `calculadora` sem `eval`

A ferramenta avalia a expressão por `ast.parse(mode="eval")` + walk explícito com uma whitelist
de operadores. `__import__('os').system('ls')` resulta em erro controlado, não em execução.

### Custo e ROI precisam de uma moeda

Não há dinheiro real no sandbox. A unidade adotada é **MB·s** (`estimated_ram_mb × duration_ms
/ 1000`), e o ROI é "conclusões entregues por MB·s consumido". É a tradução direta da premissa
do projeto: o hardware é a economia.

---

## 4. Validação

### Automatizada

```
ruff check .   → All checks passed!
mypy           → Success: no issues found in 55 source files
pytest         → 255 passed
cobertura      → 98% (serviços da Fase 3 em 100%, exceto reasoning_metrics em 99%)
```

### Migração

```
alembic current → 0003_fase_3_observabilidade (head)
alembic check   → No new upgrade operations detected.
```

Schema conferido no PostgreSQL: `reasoning_steps` com `bigint` autoincrement, `jsonb`, FK
`ON DELETE CASCADE` e os dois índices esperados.

### E2E no stack real

| Cenário | Resultado |
|---|---|
| Chief com modelo não baixado (`deepseek-r1:8b`) | Fallback determinístico, `COMPLETED`, 5 passos, 94 ms |
| Subagente com modelo instalado (`llama3.2:3b`) | Streaming real, `COMPLETED`, 7 passos, 1679 tokens, 79,8 s |
| `GET /reasoning-flow` | 8 nós, 7 arestas, 1 aresta `LOOP`, 2 linhas |
| `GET /live-status` | `IDLE` / `COMPLETED` / `progress: 1.0` |
| `GET /reasoning/metrics` | 2 sessões, `success_rate: 1.0`, agrupamento por modelo correto |
| `WS /ws/reasoning` | `session.started → step(THOUGHT) → step(CONCLUSION) → session.finished` ao vivo |

Observação do teste real: o modelo chamou `Infraestrutura()` com entrada vazia e capitalizado —
o lookup normalizado resolveu corretamente, confirmando a necessidade da tolerância do parser.

---

## 5. Débitos técnicos

| # | Débito | Impacto | Encaminhamento |
|---|--------|---------|----------------|
| 1 | `POST /reasoning/run` é síncrono | Tarefa com modelo grande segura a conexão HTTP por dezenas de segundos (medido: 79,8 s) | Execução em background + `202 Accepted` na Fase 4; os passos já chegam ao vivo pelo WebSocket |
| 2 | `ReasoningBroker` vive no processo | Com mais de um worker Uvicorn, o cliente só recebe eventos do worker a que se conectou | Trocar o transporte por Redis pub/sub (ADR-006) |
| 3 | Sem cancelamento via API | `tracer.cancel()` existe, mas nenhuma rota o expõe | `POST /reasoning/sessions/{id}/cancel` quando houver execução assíncrona |
| 4 | Retenção é manual | `purge_sessions` só roda sob demanda | Agendador (APScheduler ou job do compose) na Fase 4 |
| 5 | Ferramentas não têm timeout | Uma ferramenta lenta trava o loop | Hoje todas são consultas locais limitadas a 200 linhas; revisar se surgir ferramenta de I/O |
| 6 | `payload.raw` guarda a resposta integral do modelo | Pode inflar o JSONB em sessões longas | `REASONING_MAX_CONTENT_CHARS` trunca o `content`, mas não o `raw`; avaliar truncar também |
| 7 | Overhead da captura medido de forma grosseira | O teste compara ordens de grandeza, não um percentual | Benchmark dedicado se a captura virar gargalo |
| 8 | Downgrade da `0003` não remove valores de enum | `audit_event_type` mantém `REASONING_*` após rollback | Limitação do PostgreSQL; documentado na própria migração |

---

## 6. Impacto nas fases seguintes

A Fase 4 (motor 2D) recebe tudo pronto do backend:

- `GET /agents/{id}/reasoning-flow` → painel de raio-X cognitivo
- `GET /agents/{id}/live-status` → barra de progresso e balão do avatar
- `WS /ws/reasoning` → atualização sem polling, com replay na conexão
- `GET /reasoning/metrics` → dashboard corporativo

Falta apenas o canal de **coordenadas no mapa**, que é específico da interface e não tem
contrapartida no domínio atual.
