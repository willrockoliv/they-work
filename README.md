# TheyWork

Simulação corporativa **sandbox** onde agentes de IA autônomos fundam e operam uma empresa
virtual — do zero ao modelo de negócio em execução. Tudo roda **100% offline**, dentro de
containers isolados, na sua própria máquina.

O usuário é um **observador onisciente**: acompanha as decisões do conselho, inspeciona o
raciocínio de cada agente e vê o escritório funcionando. Nada disso escapa dos limites
físicos do hardware — e é exatamente aí que entra **A Natureza**.

> Documentação completa: [PRD](docs/PRD.md) · [Arquitetura](docs/ARCHITECTURE.md) · [Setup e troubleshooting](docs/SETUP.md) · [Lógica dos Chiefs](docs/CHIEF-LOGIC.md) · [Banco de Talentos](docs/TALENT-BANK.md) · [Fluxo de contratação](docs/HIRING-FLOW.md) · [Frontend 2D](frontend/README.md)

---

## Como funciona

**O conselho (fixo, não demissível)**

| Agente | Papel |
|--------|-------|
| **CEO** | Visão macro, rentabilidade, palavra final em impasses |
| **CTO** | Viabilidade técnica, arquitetura, segurança |
| **CMO** | Mercado, concorrentes, posicionamento |
| **CFO** | Caixa simulado, precificação, monetização |
| **RA** | Único agente que pode instanciar subagentes; cuida do Banco de Talentos |

**Os subagentes** são temporários: nascem para uma sprint, resolvem a tarefa e são
"demitidos" (liberam a RAM), deixando apenas seus relatórios arquivados.

**A Natureza** é a entidade invisível que lê a RAM e a VRAM reais da máquina e traduz
escassez de hardware em regras de negócio. Quando os recursos apertam, ela não mostra um
erro de memória — ela diz:

> *"A infraestrutura da empresa atingiu a capacidade máxima. A contratação do novo
> pesquisador foi bloqueada até que o projeto atual seja finalizado."*

Ela também força **otimização de custos**: se o CTO pediu um especialista rodando
`deepseek-r1:8b` mas só sobram 3 GB, a vaga é preenchida com `gemma3n:e4b`.

---

## Começando

**Pré-requisitos:** Docker 29+, Docker Compose v2+, ~25 GB livres em disco e 16 GB de RAM.

```bash
# 1. Configure o ambiente
cp .env.example .env
# edite .env e defina POSTGRES_PASSWORD

# 2. Suba a stack
docker compose up -d --build

# 3. Baixe os modelos open source (~17 GB, só na primeira vez)
./scripts/pull_models.sh

# 4. Inicialize o conselho administrativo
curl -X POST http://localhost:8000/agents/chiefs/init
```

Pronto. O **escritório virtual** abre em <http://localhost:3000> e a documentação
interativa da API fica em <http://localhost:8000/docs>.

> Tem GPU NVIDIA? Suba com o override para acelerar a inferência:
> `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`

---

## Endpoints

### Fase 1 — Motor base

| Método | Rota | O que faz |
|--------|------|-----------|
| `GET` | `/health` | Saúde do backend, PostgreSQL e Ollama |
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/resources/status` | Leitura de RAM/VRAM/CPU com a narrativa da Natureza |
| `POST` | `/resources/hiring/evaluate` | Submete uma contratação ao veredito da Natureza |
| `POST` | `/agents/chiefs/init` | Inicializa os 5 Chiefs (idempotente) |
| `GET` | `/agents/status` | Quadro de funcionários da empresa |
| `GET` | `/models/available` | Catálogo cruzado com o que está baixado no Ollama |
| `GET` | `/models/select` | Modelo recomendado para uma complexidade de tarefa |

### Fase 2 — Estruturação societária

| Método | Rota | O que faz |
|--------|------|-----------|
| `POST` | `/council/profiles/init` | Materializa os perfis das personas C-Level |
| `GET` | `/council/profiles` | Perfis do conselho, por prioridade |
| `POST` | `/council/deliberate` | Submete uma pauta à deliberação do conselho |
| `GET` | `/council/communications` | Histórico de falas entre os Chiefs |
| `POST` | `/council/profiles/{role}/memory` | Grava um fato na memória de um Chief |
| `POST` | `/hiring/requests` | Abre uma vaga junto ao RA |
| `POST` | `/hiring/requests/{id}/clarify` | Responde aos questionamentos do RA |
| `GET` | `/hiring/requests` | Lista as requisições de contratação |
| `POST` | `/agents/subagents/{id}/dismiss` | Demite um subagente ao fim da sprint |
| `GET` | `/talent/profiles` | Banco de Talentos |
| `GET` | `/talent/profiles/search` | Procura um perfil reaproveitável |
| `GET` | `/talent/profiles/{slug}/versions` | Histórico de versões de um perfil |
| `POST` | `/talent/profiles/{id}/rating` | Avalia o desempenho de um perfil |
| `POST` | `/nature/audit-request` | Auditoria isolada da Natureza |
| `GET` | `/nature/alerts` | Alertas corporativos estruturados |

### Fase 3 — Transparência e observabilidade

| Método | Rota | O que faz |
|--------|------|-----------|
| `POST` | `/agents/{id}/reasoning/run` | Executa uma tarefa capturando todo o ciclo ReAct |
| `GET` | `/agents/{id}/reasoning-flow` | Fluxograma `[Pensamento]→[Ferramenta]→[Observação]→[Conclusão]` |
| `GET` | `/agents/{id}/live-status` | Status ao vivo: progresso, última ação e tempo decorrido |
| `GET` | `/reasoning/sessions` | Histórico de sessões de raciocínio |
| `GET` | `/reasoning/sessions/{id}` | Replay completo de uma sessão |
| `GET` | `/reasoning/sessions/{id}/flow` | Fluxograma de uma sessão específica |
| `GET` | `/reasoning/metrics` | Tokens, tempo, taxa de sucesso, custo em MB·s e ROI |
| `GET` | `/reasoning/export` | Dump JSON das sessões para análise externa |
| `POST` | `/reasoning/retention/purge` | Aplica a política de retenção |
| `WS` | `/ws/agents/{id}/reasoning` | Fluxo cognitivo de um agente (com replay na conexão) |
| `WS` | `/ws/reasoning` | Fluxo cognitivo de todos os agentes |

Contratos detalhados: [`docs/API-REASONING.md`](docs/API-REASONING.md),
[`docs/REASONING-FORMAT.md`](docs/REASONING-FORMAT.md) e
[`docs/FLOWCHART-SCHEMA.md`](docs/FLOWCHART-SCHEMA.md).
```bash
# Ver um agente pensar em voz alta
AGENT=$(curl -s localhost:8000/agents/status | jq -r '.chiefs[0].id')
curl -s -X POST "localhost:8000/agents/$AGENT/reasoning/run" \
  -H 'content-type: application/json' \
  -d '{"task":"Quanta RAM sobra para novos subagentes?"}' | jq '.steps[].content'
```

> Sem o Ollama no ar (ou sem o modelo baixado), o agente cai num planejador determinístico:
> consulta uma ferramenta de verdade e conclui a partir da observação. A simulação nunca
> deixa de ser observável.

### Fase 4 — Mundo 2D

| Método | Rota | O que faz |
|--------|------|-----------|
| `GET` | `/game/map` | Planta do escritório: cômodos, postos de trabalho e pontos de interesse |
| `GET` | `/game/state` | Estado completo do mundo: lotação, relógio, recursos e economia |
| `GET` | `/agents/{id}/position` | Posição de um agente no grid |
| `POST` | `/agents/{id}/move` | Move um agente para um tile arbitrário |
| `POST` | `/agents/{id}/recall` | Devolve o agente ao posto fixo |
| `WS` | `/ws/game-state` | Canal único do mundo: snapshot, eventos cognitivos e diffs de estado |

A interface consome tudo isso em <http://localhost:3000>:
[`frontend/README.md`](frontend/README.md).

---

## Os cinco modelos

Todos quantizados em **Q4_K_M** para caber no hardware alvo (16 GB RAM / 4 GB VRAM).
A Natureza escolhe automaticamente o mais leve que dê conta do recado.

| Modelo | Vendor | RAM | Melhor para |
|--------|--------|-----|-------------|
| `llama3.2:3b` | Meta | ~2.0 GB | Conversação, sumarização, atas |
| `phi4-mini:3.8b` | Microsoft | ~2.3 GB | Raciocínio lógico e matemático |
| `gemma3n:e4b` | Google DeepMind | ~3.0 GB | Multimodal, documentação extensa |
| `qwen3:8b` | Alibaba | ~4.6 GB | Codificação pesada, alto nível |
| `deepseek-r1:8b` | DeepSeek | ~5.0 GB | Chain-of-thought, decisões vitais |

---

## Desenvolvimento

O ambiente Python local serve apenas para **lint, tipos e testes**. A aplicação sempre roda
em container.

```bash
pyenv activate they-work      # Python 3.14.8 (ver .python-version)
pip install -e ".[dev]"

pytest                        # testes (SQLite em memória, offline)
ruff check . --fix            # lint
mypy                          # type checking estrito
```

Criar uma migração após mudar os modelos ORM:

```bash
docker compose exec backend alembic revision --autogenerate -m "descrição"
docker compose exec backend alembic upgrade head
```

O frontend nunca roda no host — todos os comandos passam pelo container:

```bash
docker compose exec frontend npm run lint
docker compose exec frontend npm run type-check
docker compose exec frontend npm run test
```

---

## Roadmap

- [x] **Fase 1 — Motor Base e Isolamento:** Docker Compose, PostgreSQL, Ollama, backend
  FastAPI e a Natureza.
- [x] **Fase 2 — Estruturação Societária:** personas C-Level com veto e desempate,
  pipeline de contratação do RA, Banco de Talentos versionado e seleção dinâmica de modelos.
- [x] **Fase 3 — Transparência:** interceptação do fluxo ReAct de cada agente, fluxograma
  cognitivo, WebSocket ao vivo, métricas de custo/ROI e política de retenção.
- [x] **Fase 4 — Motor 2D:** escritório top-down em PixiJS, avatares animados com balões de
  fala, painel de raio-X cognitivo e canal `WS /ws/game-state` em tempo real.
