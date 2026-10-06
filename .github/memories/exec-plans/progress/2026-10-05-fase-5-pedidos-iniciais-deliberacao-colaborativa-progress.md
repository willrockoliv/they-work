# Progresso: Fase 5 — Rede Corporativa e Grafo de Comunicações

**Plano:** [2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa.md](../completed/2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa.md)
**Status:** ✅ Concluído
**Início:** 2026-10-05 · **Conclusão:** 2026-10-05

---

## 1. O que foi entregue

### Backend

| Camada | Entrega |
|---|---|
| `models/enums.py` | `InitialRequestStatus`, `CommunicationType` (10 rótulos), `CommunicationStatus`, `TaskStatus`, `ChiefDecision`, `SUPERVISING_ROLES` e 8 novos `AuditEventType` |
| `models/network.py` | `InitialRequest`, `AgentTask` (com `parent_task_id` para subtarefas) e `CommunicationEdge` |
| `alembic/0004_fase_5_rede_corporativa` | 3 tabelas, 5 tipos enum novos, 8 rótulos acrescentados a `audit_event_type` |
| `services/report_analysis.py` | Avaliação determinística: qualidade, cobertura vs. objetivo, riscos, custo/benefício, próximos passos, capacidade do agente e o veredito |
| `services/reasoning_tools.py` | +7 ferramentas de revisão no catálogo ReAct; `ToolContext` ganhou `task_id` |
| `services/communication_service.py` | Pedido → deliberação → pedido ao RA → delegação → execução → report; arestas, grafo e invariantes de hierarquia |
| `services/agent_decision_engine.py` | Revisão do Chief (APPROVE/REJECT/MODIFY/CONSULT_PEERS/ESCALATE), reconvocação, subtarefa, consulta a pares e desempate do CEO |
| `services/network_orchestrator.py` | Turno automático: 3 frentes (CTO/CMO/CFO) montam time, delegam, executam e revisam |
| `routes/network.py` | 13 endpoints REST |
| `services/react_engine.py` | `run_task(..., task_id=...)` liga o ciclo ReAct à tarefa sob revisão |

**Eventos novos no barramento (Fase 3 reaproveitado):** `network.edge`, `network.task`, `network.request` — saem pelo `WS /ws/game-state` já existente.

### Frontend

- `types/network.ts` — espelho tipado dos schemas da Fase 5
- `engine/graphLayout.ts` — organograma determinístico em camadas (observador → CEO → chiefs → subagentes), com curvatura de arestas paralelas
- `components/NetworkGraph.tsx` — grafo em SVG puro, legenda e detalhe de aresta clicável
- `components/RequestsPanel.tsx` — formulário de pedido, lista, grafo e lista de tarefas com veredito
- `store/gameStore.ts` — `networkEdges`, `networkTasks`, `networkRequests`, `networkRevision`
- `store/uiStore.ts` + `TopBar` — alternância "Escritório" ↔ "Rede corporativa"

### Testes

| Suíte | Antes | Depois |
|---|---|---|
| Backend (`pytest`) | 286 | **341** (+21 `test_report_analysis`, +20 `test_communication_graph`, +13 `test_api_fase5`, +1 `test_network_redelegation`) |
| Frontend (`vitest`) | 69 | **89** (+9 `graphLayout`, +4 `networkStore`, +4 `RequestsPanel`, +3 `NetworkGraph`) |

`ruff check` · `mypy` (estrito, 66 arquivos) · `tsc --noEmit` · `eslint` — todos limpos.

---

## 2. Decisões de projeto

### ADR-012 — `reports_to_id` é o `reporting_chief_id`
O plano pedia uma coluna `agents.reporting_chief_id`. A tabela `agents` **já tinha**
`reports_to_id` com exatamente essa semântica desde a Fase 2. Criar uma segunda FK com o
mesmo significado abriria espaço para divergência entre as duas. A coluna existente foi
reaproveitada e `communication_service.request_agent()` passou a reatribuí-la ao Chief
solicitante logo depois que o RA instancia o agente.

### ADR-013 — Veredito determinístico como piso, não como fallback de emergência
O Chief roda um ciclo ReAct completo com as 7 ferramentas (é isso que fica auditável no
raio-X cognitivo), mas a decisão só é aceita quando o parser reconhece um rótulo na
conclusão. Caso contrário vale `report_analysis.assess()`. Como os modelos dos Chiefs não
estão baixados na máquina (ver memória do repo), o caminho determinístico é o **normal**,
não a exceção — e ele nunca deixa a tarefa sem veredito.

### ADR-014 — Grafo em SVG, sem D3 nem Cytoscape
O plano sugeria D3.js ou Cytoscape.js. Ambos custam ~80–250 kB e trazem simulação de
forças, que faz o desenho "pular" a cada aresta nova chegando pelo WebSocket. Como a
hierarquia da empresa é conhecida e fixa (4 camadas), um layout determinístico em
`engine/graphLayout.ts` + SVG nativo resolve com zero dependência nova e leitura estável.

### ADR-015 — Barramento da Fase 3 reaproveitado
O plano listava "Pub/Sub robusto (threading safe)" como dependência nova. O
`reasoning_broker` da Fase 3 já é thread-safe (entrega via `loop.call_soon_threadsafe`) e o
`WS /ws/game-state` já repassa qualquer evento do canal global. As mutações do grafo entram
por ali, sem Redis e sem canal novo.

---

## 3. Armadilhas encontradas (e a correção)

### 3.1 O enunciado da tarefa envenenava o parser de veredito
O planejador determinístico do `react_engine` ecoa o texto da tarefa dentro da conclusão.
O enunciado original da revisão era *"...decidir entre APPROVE, REJECT, MODIFY,
CONSULT_PEERS ou ESCALATE"* — então **todo** veredito saía `ESCALATE`, porque o parser
encontrava o rótulo ecoado antes de qualquer decisão real.

**Correção:** o cardápio de vereditos saiu do enunciado e foi para o `context` do
`TaskRequest` (que o modelo vê no prompt, mas que o fallback não ecoa). Constante
`agent_decision_engine.DECISION_MENU`.

> **Regra geral:** nada que o parser de saída procure pode aparecer no texto de entrada.

### 3.2 Marcador de risco casando no meio de palavra
`"senha" in texto_normalizado` dava verdadeiro para **de-senha-r**. Um report impecável
era classificado com risco `SECURITY` alto e escalado ao CEO. O marcador `custo` tinha o
mesmo problema: qualquer menção legítima a custo virava risco `FINANCE` alto.

**Correção:** `_mentions()` usa `\b{marcador}\b`, e o catálogo financeiro passou a listar
só sinais de fato negativos (`prejuizo`, `margem negativa`, `caixa negativo`).

### 3.3 Cobertura do objetivo quebrava com flexão verbal
Comparação por token exato marcava "mapear" como lacuna quando o report dizia "mapeei" e
"mapa". Toda entrega boa virava `MODIFY`.

**Correção:** `compare_vs_objective` compara radicais de 4 caracteres
(`report_analysis.STEM_CHARS`). Não é um stemmer de verdade, mas é determinístico,
offline e suficiente para o português do domínio.

### 3.4 O CEO virava supervisor ao desempatar
`ceo_final_decision` → `_apply` → `_redelegate` redelegava com o CEO como `chief`, e a
invariante "um Chief só delega para o próprio time" estourava, porque o agente reportava ao
CTO. **Correção:** `_redelegate` usa sempre `task.assigned_by_chief_id` — o CEO decide, mas
não assume o time de outra diretoria.

### 3.5 Container do frontend não espelha o host
`docker compose exec frontend npm run lint` passou sem enxergar nenhum arquivo novo: a
imagem copia o `src`, não o monta. `type-check` e `lint` deram verde contra o código
**antigo**. Só `docker compose up --build -d frontend` sincroniza.

> Sempre rebuildar antes de confiar em lint/type-check/test do frontend.

### 3.6 `react-hooks/set-state-in-effect` (ESLint 10)
`RequestsPanel` chamava `void refreshList()` e `setDetail(null)` no corpo do efeito.
**Correção:** o efeito só dispara o I/O (todo `setState` vai para o `.then`), e o detalhe
obsoleto é **derivado** (`detail.request.id === selectedRequestId`) em vez de sincronizado.

### 3.7 Prefixo da API em `/`
`settings.api_prefix` é vazio: as rotas são `/council/...`, não `/api/v1/council/...`.

### 3.8 Todo o C-Level virava um "C" no grafo (só visível no navegador)
`initials("CTO")` pegava a primeira letra de cada palavra — com uma palavra só, sobrava `C`.
CEO, CTO, CMO e CFO ficavam indistinguíveis. **Correção:** siglas de até 4 caracteres entram
inteiras; nomes compostos viram iniciais ignorando sufixos não alfabéticos (`#1`).

### 3.9 Arestas recíprocas se cobrindo (só visível no navegador)
O parecer `CTO→CEO` e a coordenação `CEO→CTO` ocupam exatamente a mesma reta. A curvatura
era indexada por `origem->destino`, então as duas recebiam desvio zero e uma tapava a outra
— a de baixo ficava **inclicável**.

**Correção**, em `engine/graphLayout.ts`:
1. a chave do grupo ignora a direção (par ordenado por id);
2. duas passadas — conta as arestas do par e distribui simetricamente
   (`(i - (n-1)/2) * EDGE_SPACING`), de modo que uma aresta sozinha fica reta;
3. o deslocamento é **perpendicular** à reta (funciona para arestas verticais e horizontais);
4. a normal sai de uma direção **canônica**, não da direção da aresta — senão, numa aresta
   recíproca, o vetor se inverte, cancela o sinal do deslocamento e joga as duas para o
   mesmo lado (foi exatamente o que aconteceu na primeira tentativa de correção).

> As duas só apareceram na validação com o navegador. Teste unitário de layout não pega
> "ficou ilegível" nem "ficou inclicável" se as asserções não foram escritas pensando nisso.

---

## 4. Validação E2E (stack real)

```
docker compose up --build -d
POST /agents/chiefs/init              → 201
POST /council/profiles/init           → 201
POST /council/request-action          → 201
  request  8a3fb204… DELIBERATING
  arestas  REQUEST, OPINION ×3, COORDINATION ×3
alembic current                        → 0004_fase_5_rede_corporativa (head)
alembic check                          → No new upgrade operations detected
```

### Turno automático contra PostgreSQL real

Após dois `run-cycle` e três `ceo/final-decision`, o grafo persistido ficou:

| Aresta | Qtd. |
|---|---|
| DELEGATION | 9 |
| DECISION | 9 |
| REPORT | 6 |
| ESCALATION | 3 |
| AGENT_REQUEST / AGENT_CREATED / COORDINATION / OPINION | 3 cada |
| REQUEST | 1 |

O loop de feedback se comportou exatamente como projetado:

1. **Turno 1** — RA cria 3 agentes (um por diretoria), cada Chief delega à sua frente,
   os agentes executam e reportam → 3 vereditos `REJECT` → 3 tarefas tentativa 2.
2. **Turno 2** — tentativa 2 executa e reporta → 3 `ESCALATE` (regra de 2ª falha com
   histórico ruim do agente).
3. **Desempate do CEO** — 3 `REJECT`, gerando tentativa 3 e mantendo o pedido
   `IN_EXECUTION` (ainda há tarefa aberta). Correto.

Todo agente reportou ao Chief que o solicitou; o RA não aparece em nenhuma aresta de
report ou delegação.

### Inferência real

Com os 5 modelos baixados, o `run-cycle` encadeia 6 sessões ReAct e leva **mais de 15
minutos** em CPU (`docker stats` mostrou o Ollama em ~400% de CPU e 5,7 GB o tempo todo —
estava inferindo, não travado). A validação completa do grafo foi feita pelo caminho
determinístico offline, que é o mesmo código sem a latência do LLM.

### Navegador (Integrated Browser)

- Aba **Rede corporativa** alterna com a do escritório pela TopBar.
- Pedido submetido pelo formulário → `201` → deliberação → grafo desenhado com as 4 camadas
  (observador → CEO → CTO/RA/CMO/CFO → 3 subagentes agrupados sob seus chefes).
- Botão de submissão travado enquanto o formulário está incompleto.
- Clique/Enter numa aresta abre o detalhe com o raciocínio que a gerou (verificado:
  *"Parecer — CTO: APPROVE — Escopo compatível com a infraestrutura local"*).
- Lista de tarefas mostra status, tentativa, qualidade e a justificativa do veredito.

---

## 5. Débitos técnicos

1. **`run-cycle` é síncrono e longo.** Com inferência real o turno leva minutos e segura a
   conexão HTTP. Precisa virar tarefa em segundo plano com acompanhamento pelo WebSocket.
2. **`CONSULT_PEERS` não coleta resposta.** As arestas `CONSULTATION` são criadas, mas os
   pares não raciocinam sobre a consulta; a tarefa fica em `AWAITING_REVIEW` até o CEO.
3. **Sem timeout/retry por tarefa.** Agente que trava deixa a tarefa aberta para sempre.
4. **Sem modo MANUAL.** Só o automático foi implementado; falta a confirmação do veredito
   pelo observador antes de aplicar.
5. **Radical de 4 letras gera falso positivo.** "custo"/"custear"/"customizar" colidem.
   Um stemmer RSLP resolveria, ao custo de uma dependência.
6. **Grafo sem virtualização.** Acima de ~80 nós o SVG fica ilegível; falta zoom/pan e
   agrupamento por diretoria.
7. **`run_cycle` fixa 3 frentes.** As `FRONTS` são estáticas; o CEO deveria derivá-las do
   teor do pedido.
8. **Subagentes nunca são demitidos.** A rede acumula agentes ociosos; falta amarrar o
   encerramento do pedido à demissão via `ra_service.dismiss_subagent`.
