# Progresso: Fase 2 - Estruturação Societária e Recursos Agênticos

**Plano Associado:** `completed/2026-10-03-fase-2-estruturacao-societaria.md`

**Data de Início:** 2026-10-03

**Data de Conclusão:** 2026-10-03

**Status Geral:** ✅ Concluído e validado

---

## Resumo de Progresso

| Seção | Status | Progresso | Notas |
|-------|--------|-----------|-------|
| 1. Framework de Personas C-Level | ✅ Concluído | 100% | `ChiefAgent` abstrato + 5 personas, 2 tabelas novas |
| 2. Recursos Agênticos (RA) | ✅ Concluído | 100% | Triagem com questionamento + fábrica de metaprompts |
| 3. Banco de Talentos | ✅ Concluído | 100% | Busca por slug/Jaccard, versionamento, rating, histórico |
| 4. Seleção Dinâmica de Modelos | ✅ Concluído | 100% | Classificador lexical + piso por cargo + fallback |
| 5. Fluxo de Contratação | ✅ Concluído | 100% | Pipeline completo, incluindo demissão com limpeza de memória |
| 6. Integração com "A Natureza" | ✅ Concluído | 100% | `/nature/audit-request` + 5 códigos de alerta estruturado |
| 7. Testes e Validação | ✅ Concluído | 100% | 168 testes, 98% de cobertura, E2E na stack real |
| 8. Documentação | ✅ Concluído | 100% | 3 docs novos + ARCHITECTURE e README atualizados |

---

## Entregas

### Modelos e migração

| Artefato | Conteúdo |
|----------|----------|
| `models/council.py` | `ChiefProfile` (perfil cognitivo) e `ChiefCommunication` (falas do conselho) |
| `models/hiring.py` | `SubagentRequest` — rastro completo do pedido até a contratação |
| `models/talent.py` | `TalentProfile` expandido: `version`, `is_active`, `supersedes_id`, `keywords`, `rating_sum/count`, `task_history` |
| `models/enums.py` | `CommunicationKind`, `RequestStatus`, `CouncilStance`, `CouncilOutcome` + 7 novos `AuditEventType` |
| `alembic/versions/0002_fase_2_sociedade.py` | 3 tabelas novas, 7 colunas em `talent_bank`, 3 tipos enum novos |

### Serviços

| Serviço | Responsabilidade |
|---------|------------------|
| `council_service.py` | `ChiefAgent` abstrato, 5 personas, deliberação e desempate do CEO |
| `ra_service.py` | Pipeline: triagem → classificação → Natureza → talento → instanciação → demissão |
| `talent_bank.py` | Slug, palavras-chave, busca, versionamento, uso e avaliação |
| `complexity_classifier.py` | Heurística lexical determinística com piso por cargo |
| `prompt_factory.py` | Metaprompt em 7 seções com restrições base invariantes |
| `nature_manager.py` | `NatureAlert` + `alerts()` com 5 códigos estruturados; teto de contratação por regime |

### API — 15 endpoints novos

`/council/profiles/init` · `/council/profiles` · `/council/deliberate` ·
`/council/communications` · `/council/profiles/{role}/memory` · `/hiring/requests` (POST/GET) ·
`/hiring/requests/{id}` · `/hiring/requests/{id}/clarify` · `/agents/subagents/{id}/dismiss` ·
`/talent/profiles` · `/talent/profiles/search` · `/talent/profiles/{slug}/versions` ·
`/talent/profiles/{id}/rating` · `/nature/audit-request` · `/nature/alerts`

---

## Relatório de Testes

**Suíte automatizada** (`pytest`, offline, SQLite em memória):

```
168 passed  —  cobertura total: 98%
```

| Arquivo | Testes | Foco |
|---------|-------:|------|
| `test_nature_manager.py` | 27 | Orçamento, teto por regime, bloqueio, fila FIFO, alertas |
| `test_api_fase2.py` | 27 | Conselho, RA, talentos, Natureza e fluxo ponta a ponta |
| `test_ra_service.py` | 23 | Triagem, esclarecimento, contratação, demissão, carga e concorrência |
| `test_talent_bank.py` | 16 | Slug, busca, versionamento, uso e avaliação |
| `test_council_service.py` | 16 | Personas, veto do CTO, desempate do CEO, comunicações |
| `test_model_catalog.py` | 15 | Integridade do catálogo, seleção por complexidade e `tier_below` |
| `test_api.py` | 15 | Endpoints da Fase 1 e cenários degradados |
| `test_persistence.py` | 11 | Schema, idempotência, auditoria, memória |
| `test_complexity_classifier.py` | 8 | Heurística, escopo, piso por cargo |
| `test_settings.py` | 5 | Validação de configuração |
| `test_ollama_client.py` | 5 | Parsing e tolerância a falhas |

**Validação end-to-end na stack real** (`docker compose up -d --build`):

| Verificação | Resultado |
|-------------|-----------|
| `alembic upgrade head` | `0002_fase_2_sociedade` aplicada |
| `alembic check` | `No new upgrade operations detected` — schema ≡ modelos |
| `POST /council/profiles/init` | 5 perfis criados; segunda chamada idempotente |
| `POST /council/deliberate` | `APPROVED` por unanimidade, 4 pareceres com justificativa |
| `POST /hiring/requests` (vago) | `NEEDS_CLARIFICATION` com 3 perguntas do RA |
| `POST /hiring/requests` (completo) | `FULFILLED`, `MODERATE` → `phi4-mini:3.8b`, `ALLOWED` |
| Recontratação do mesmo cargo | `reused_profile: true`, perfil com `usage_count=2` |
| `POST /nature/audit-request` | `DOWNGRADED`: DeepSeek R1 8B → Qwen3 8B com narrativa |
| `GET /nature/alerts` | `HEALTHY`, nenhum alerta ativo |
| `POST /agents/subagents/{id}/dismiss` | `TERMINATED`, `estimated_ram_mb=0` |
| Auditoria no PostgreSQL | 10 tipos de evento persistidos; 5 comunicações, 3 requisições, 1 relatório |

**Qualidade:** `ruff check .` limpo · `mypy --strict` limpo em 44 arquivos.

---

## Aprendizados e Decisões Importantes

### Deliberação determinística, não inferencial

A decisão mais estruturante da fase: **nenhum Chief consulta o Ollama para deliberar**.
O raciocínio é lexical (palavras-chave normalizadas sem acento). Motivos:

- A deliberação precisa ser **auditável e reproduzível** — o usuário é observador onisciente
  e deve conseguir entender por que o CTO vetou.
- Decidir *qual modelo usar* não pode custar uma rodada de LLM.
- Permite testar todos os regimes de decisão sem rede.

O custo é a fragilidade a sinônimos fora das listas — registrado como débito #3.

### Veto técnico como regra de primeira ordem

`_resolve()` avalia o veto do CTO **antes** de qualquer contagem de votos. Isso traduz a
restrição física do projeto (16 GB / 4 GB) em regra de governança: nenhuma maioria de
negócio aprova algo que não roda no hardware.

### Enum do PostgreSQL em migrações: `create_type=False`

`alembic revision --autogenerate` falhou com `PermissionError` ao escrever no volume
montado (o usuário do container não tem permissão de escrita em `alembic/versions/`).
A migração foi escrita à mão — o que acabou sendo necessário de qualquer forma:

- `op.create_table` com `sa.Enum(..., name='agent_role')` tenta **recriar** o tipo
  (`_on_table_create` usa `checkfirst=False` quando a tabela não está ligada a um
  `MetaData`). Em tipos já criados pela 0001 isso aborta a migração.
- Solução: declarar os tipos reaproveitados como
  `postgresql.ENUM(..., name='agent_role', create_type=False)` e criar explicitamente
  apenas os novos (`communication_kind`, `request_status`, `nature_decision`).
- Novos rótulos em enum existente: `ALTER TYPE ... ADD VALUE IF NOT EXISTS`. Funciona
  dentro de transação no PG 16 desde que o valor não seja **usado** na mesma transação.
- `alembic check` confirmou a paridade schema ↔ modelos ao final.

### Autoflush desligado exige `flush()` após auditoria

O `conftest` cria a sessão com `autoflush=False`. Eventos de auditoria registrados *depois*
do último `session.flush()` de um serviço ficavam invisíveis para `audit_service.list_events()`
nos testes. Regra adotada: **todo caminho de saída de um serviço termina com `flush()`**,
depois de registrar a auditoria.

### Downgrade por RAM crítica é inalcançável com os defaults

Tentando testar o caminho `status is CRITICAL → lightest_model`, descobrimos que com
`nature_ram_limit_mb=16384` e `nature_reserved_ram_mb=2048` as condições são mutuamente
exclusivas:

- `CRITICAL` exige `ram_used >= 0.90 × 16384 = 14746`
- orçamento para o modelo mais leve exige `ram_used <= 16384 − 2048 − 2048 = 12288`

Ou seja, antes de ficar crítico o orçamento já zerou e a vaga vai para a fila. O caminho de
downgrade realmente exercitado no hardware alvo é o de **orçamento apertado** (status
`HEALTHY`/`WARNING` com `best_fit_within` rebaixando o tier). O teste foi reescrito para
refletir o comportamento real em vez de forçar um cenário impossível.

### Refinamento da Natureza: o regime rebaixa o teto (pós-conclusão)

O item acima foi tratado de forma definitiva depois da conclusão inicial do plano. O ramo
especial de `CRITICAL` em `evaluate_hiring` foi removido; o regime da infraestrutura passou
a **rebaixar o teto** antes da única regra de seleção (`best_fit_within`):

| Regime | Teto |
|--------|------|
| `HEALTHY` | modelo preferido |
| `WARNING` | um tier abaixo (`model_catalog.tier_below`) |
| `CRITICAL` | modelo mais leve |

Três descobertas no caminho:

1. **O teto por regime não é redundante — é o canal da GPU.** Para RAM, `ram_used` e
   `ram_allocatable` são leituras da mesma variável, então o orçamento sempre domina os
   limiares. Mas o orçamento **não enxerga VRAM**: com a GPU saturada e RAM sobrando, só o
   teto impede que o DeepSeek R1 seja concedido. Coberto por
   `test_vram_saturada_rebaixa_o_modelo_mesmo_sobrando_ram`.
2. **`NATURE_RAM_LIMIT_MB` é o knob errado para folga do host.** Ele também é o denominador
   do percentual de saúde; abaixo da RAM física o ratio se distorce (`used` é do host e pode
   superar o teto → `CRITICAL` permanente com orçamento zero). A folga correta é
   `NATURE_RESERVED_RAM_MB`. Documentado no `.env.example` e em `ARCHITECTURE.md`.
3. **Relação de calibração explícita:**
   `reserva + 2048 ≤ (1 − warning_threshold) × ram_limit`. Quando não vale, a reserva domina
   os limiares. Fixado em `test_reserva_domina_os_limiares_na_configuracao_do_projeto`.

### Auditoria de encerramento

Uma varredura item-a-item do plano contra o código apontou uma lacuna real: o teste de carga
era **sequencial**, enquanto o plano pedia "múltiplos Chiefs solicitando simultaneamente".
Adicionado `test_chiefs_concorrentes_nao_corrompem_a_fila`, que exercita
`evaluate_hiring()` em `ThreadPoolExecutor` e verifica que nenhuma posição de fila é
duplicada ou perdida. A escrita no banco permanece sequencial de propósito: a `Session` do
SQLAlchemy não é thread-safe, e o estado mutável compartilhado de verdade é a Natureza.

### Versionamento do Banco de Talentos não herda métricas

Uma nova versão do metaprompt zera `rating_sum`, `rating_count` e `task_history`: a nota
antiga avaliava um prompt diferente. A unicidade passou de `slug` para `(slug, version)` e a
busca filtra por `is_active`.

### Separação triagem × orçamento

O RA faz a triagem (`screen`) **antes** de consultar a Natureza. Um pedido vago não consome
nenhum recurso de infraestrutura — só gera perguntas. Isso mantém a fila de contratações
limpa e reflete a regra do PRD ("se o pedido for vago, ele questiona o gestor antes de
prosseguir").

### Suíte de testes não era hermética (defeito corrigido)

A suíte passou a falhar em massa (42 de 162) sem nenhuma mudança de código. Causa: o
`.env` da máquina define `NATURE_RAM_LIMIT_MB=5120`, e **pydantic-settings lê o arquivo
`.env` mesmo durante os testes**. Com o teto a 5120 MB e 2048 MB reservados, o orçamento
alocável ficava em 0 e toda contratação ia para a fila.

Correção: o `conftest.py` passou a fixar todas as variáveis `NATURE_*` via
`os.environ.setdefault` — variáveis de ambiente têm precedência sobre o arquivo `.env`. O
bug era latente desde a Fase 1; só apareceu quando os testes passaram a depender do
orçamento de RAM. **Regra:** todo setting novo que influencie comportamento precisa ser
pinado no `conftest`.

### Detalhes menores que custaram tempo

- `DbSession` é um `Annotated[..., Depends(...)]`: usá-lo como anotação de um helper comum
  faz o FastAPI/mypy tratarem o parâmetro como injeção. Helpers usam `Session` puro.
- `status.HTTP_422_UNPROCESSABLE_ENTITY` está deprecado no Starlette atual; usamos o
  literal `422` para não pinar um nome em transição.
- `app/services/__init__.py` precisa importar os módulos em ordem de dependência para que
  `from app.services import X` dentro de `ra_service` resolva durante a inicialização.

---

## Débitos Técnicos

| # | Débito | Impacto | Encaminhamento |
|---|--------|---------|----------------|
| 1 | Fila de contratações da Natureza continua em memória (herdado da Fase 1) | Não sobrevive a restart; vagas represadas se perdem | Migrar para Redis (já provisionado) na Fase 3 |
| 2 | Requisições `QUEUED` nunca são reprocessadas automaticamente | O Chief precisa reabrir a vaga manualmente | Worker de drenagem da fila quando a Natureza voltar a `HEALTHY` |
| 3 | Raciocínio dos Chiefs é lexical | Sinônimos fora das listas levam a classificação errada | Complementar com inferência real na Fase 3, mantendo a heurística como fallback auditável |
| 4 | Subagentes não executam tarefas | O metaprompt é gerado e persistido, mas nenhuma inferência roda | `OllamaClient.generate()/chat()` na Fase 3 |
| 5 | `alembic revision --autogenerate` falha por permissão no volume | Migrações precisam ser escritas à mão | Ajustar `user:` no compose de dev ou gerar fora do container |
| 6 | `chief_profiles.context_memory` trunca em 25 fatos sem critério de relevância | Fatos importantes podem ser descartados por fatos recentes | Ordenar o descarte por `importance` ao atingir o teto |
| 7 | Débitos #2, #3 e #4 da Fase 1 permanecem | GPU em container, cgroup, SQLAlchemy síncrono | Inalterados; ver progresso da Fase 1 |
| 8 | Só os settings `NATURE_*` estão pinados no `conftest` | Outros settings do `.env` ainda podem vazar para os testes | Avaliar `env_file=None` quando `APP_ENV=test` |
| 9 | Concorrência é testada só na Natureza, não no caminho de banco | Uma corrida real entre dois RAs gravando no PostgreSQL não está coberta | Exige sessões independentes por thread; reavaliar quando houver workers de verdade (Fase 3) |

---

## Bloqueadores

*Nenhum. A Fase 3 está desbloqueada.*

---

## Próximas Ações (Fase 3)

1. Interceptar o fluxo ReAct real: `OllamaClient.generate()/chat()` + callbacks por token.
2. Nova tabela `thought_traces` (ou `corporate_memory` com `memory_type` dedicado) para os
   passos Thought/Action/Observation.
3. Drenagem automática da fila de contratações (débito #2) + migração para Redis (débito #1).
4. Streaming dos traços cognitivos — base do painel de raio-X da Fase 4.
