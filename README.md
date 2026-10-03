# TheyWork

Simulação corporativa **sandbox** onde agentes de IA autônomos fundam e operam uma empresa
virtual — do zero ao modelo de negócio em execução. Tudo roda **100% offline**, dentro de
containers isolados, na sua própria máquina.

O usuário é um **observador onisciente**: acompanha as decisões do conselho, inspeciona o
raciocínio de cada agente e vê o escritório funcionando. Nada disso escapa dos limites
físicos do hardware — e é exatamente aí que entra **A Natureza**.

> Documentação completa: [PRD](docs/PRD.md) · [Arquitetura](docs/ARCHITECTURE.md) · [Setup e troubleshooting](docs/SETUP.md)

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

Pronto. A documentação interativa da API fica em <http://localhost:8000/docs>.

> Tem GPU NVIDIA? Suba com o override para acelerar a inferência:
> `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`

---

## Endpoints da Fase 1

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

---

## Roadmap

- [x] **Fase 1 — Motor Base e Isolamento:** Docker Compose, PostgreSQL, Ollama, backend
  FastAPI e a Natureza.
- [ ] **Fase 2 — Estruturação Societária:** personas C-Level, framework de decisão,
  Banco de Talentos do RA.
- [ ] **Fase 3 — Transparência:** interceptação do fluxo ReAct de cada agente.
- [ ] **Fase 4 — Motor 2D:** escritório top-down, avatares, raio-X cognitivo via WebSocket.
