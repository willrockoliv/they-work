---
name: Copilot Agent Instructions
description: Instruções persistentes para LLMs que trabalham neste workspace. Este arquivo é lido automaticamente pelo GitHub Copilot como contexto em toda interação. 
applyTo: "**/*"
---

# Instruções de Onboarding para o Copilot Cloud Agent

## Visão Geral

**Propósito do Repositório:**
TheyWork — simulação corporativa sandbox onde agentes de IA autônomos fundam e operam uma empresa
virtual. Roda 100% offline e conteinerizada. O usuário é observador onisciente. Uma entidade
invisível ("A Natureza") traduz os limites físicos do hardware (16 GB RAM / 4 GB VRAM) em regras
de negócio corporativas.

**Stack & Tamanho:**
Monorepo pequeno. Backend Python 3.14.8 (FastAPI 0.142.2, SQLAlchemy 2.1.3 síncrono, Alembic
1.20.0, Pydantic 2.13.5, structlog). Infra: PostgreSQL 16.11, Redis 8.2.2, Ollama 0.12.11, tudo
via Docker Compose. Frontend 2D (React/Vue) previsto apenas para a Fase 4 — ainda **não existe**.

**Arquivos-chave na raiz:**
- `pyproject.toml` — dependências, ruff, mypy, pytest (configuração única do projeto)
- `docker-compose.yml` — stack principal (+ `.override.yml` dev, `.gpu.yml` NVIDIA)
- `.env.example` — modelo de configuração; copie para `.env`
- `scripts/pull_models.sh` — baixa os 5 modelos Ollama
- `backend/` — código da aplicação, `alembic/` e `tests/`


## Instruções de Build, Execução e Validação

### Configuração de Ambiente
- **Python:** Use Python 3.14.8 (veja `.python-version`).
- **Banco de Dados:** PostgreSQL 16 (provisionado automaticamente pelo Docker Compose).
- **Ambiente:** Copie `.env.example` para `.env` e preencha os segredos necessários.


### Regra Operacional (Agentes)
- **NUNCA rode `npm run ...` diretamente no host.**
- **NUNCA rode `pip install ...` diretamente no host.**
- **NUNCA execute o backend ou frontend diretamente no host.**
- **SEMPRE execute comandos via Docker Compose**
- Se o container não estiver ativo, suba antes com `docker compose up -d`.
- Caso precise rodar comandos Python, sempre use o ambiente virtual do projeto no .python-version ativado.
- Para rodar testes Python, sempre use o ambiente virtual do projeto no .python-version ativado.
- Para subir o serviço backend, sempre use o Docker Compose. Sempre evite rodar o backend diretamente no host para evitar conflitos de dependências.
- Jamais instale dependências globalmente no host. Use ambientes virtuais ou Docker para isolar o ambiente de desenvolvimento.
- Sempre que uma lib for adicionada ou removida, atualize o arquivo de dependências (`requirements.txt`, `pyproject.toml`) e rode os comandos de instalação e migração necessários.
- **JAMAIS** utilize tag latest para nenhuma dependência, seja de Python, Node ou Docker. Sempre fixe a versão para garantir reprodutibilidade, evitar quebras inesperadas e por segurança.
- **NUNCA** delete testes unitários ou de integração sem autorização explícita. Se um teste estiver falhando, investigue a causa raiz e corrija o código ou o teste, mas não remova a cobertura de teste.

### Ambiente e Dependências do Frontend
- Para bootstrap ou rebuild do frontend, prefira `docker compose up --build -d` para manter host e container sincronizados.
- Se precisar refazer o ambiente, remova `node_modules`, `.next` e outros caches no host e no container antes de subir novamente com `docker compose up --build -d`.
- Antes de validar fluxos no frontend, confirme que host e container estão sincronizados.

### Lint
- **Python:** `ruff check .` (config em `pyproject.toml`)
- **JS/TS:** `docker compose exec frontend npm run lint` (apenas a partir da Fase 4)
- **Auto-fix:** `ruff check . --fix`

### Type Checking
- **Python:** `mypy` (modo estrito, configurado em `pyproject.toml`)
- **TypeScript:** `docker compose exec frontend npm run type-check` (apenas a partir da Fase 4)

### Testes
- **Backend:** `pytest` (offline; SQLite in-memory + dublês de HTTP/hardware)

### Problemas Comuns & Workarounds
- Se o backend reiniciar em loop, confira se `POSTGRES_PASSWORD` e `DATABASE_URL` no `.env`
  são coerentes entre si.
- Migrações são aplicadas automaticamente pelo `backend/entrypoint.sh` no boot; para rodar
  manualmente: `docker compose exec backend alembic upgrade head`.
- PostgreSQL não publica porta no host (isolamento). Use `docker compose exec postgres psql`.
- `gpu_detected: false` é esperado sem o override `docker-compose.gpu.yml`.
- Troubleshooting completo: `docs/SETUP.md` §6.

### Validação de Frontend (Obrigatória para Agentes)
- **Use o Integrated Browser do VS Code** para validar visual e comportamento das páginas localmente.
- **Após qualquer alteração de frontend, navegue por TODAS as telas alteradas** (incluindo rotas públicas e autenticadas impactadas).
- **Quando a tarefa envolver código em `frontend/` ou integração frontend-backend**, siga o padrão de pastas do projeto, valide endpoints alterados e atualize componentes e páginas conforme especificações do projeto.

## Estrutura & Arquitetura do Projeto

```text
backend/app/
├── main.py      # create_app(), middleware, lifespan
├── config/      # settings (pydantic-settings), logging (structlog), database (engine/sessão)
├── models/      # ORM SQLAlchemy + enums de domínio (models/enums.py)
├── schemas/     # contratos Pydantic da API
├── services/    # regras de negócio: nature_manager, model_catalog, agent_service, audit_service, ollama_client
└── routes/      # camada HTTP fina (health, resources, agents, models) + deps.py
```

**Regra de dependência (unidirecional):** `routes/ → services/ → models/ → config/`.
`models/` nunca importa de `services/`; `services/` nunca importa de `routes/`.

**Pontos de atenção ao editar:**
- Tipos de coluna precisam funcionar em PostgreSQL **e** SQLite (testes). Use variantes de
  dialeto — ver `models/base.py` e `audit.py`.
- `Settings` é cacheado com `@lru_cache`; em testes, defina env vars **antes** de importar `app.*`.
- `dependency_overrides` do FastAPI só aceita callables sem parâmetros (use `lambda: factory()`).
- Nenhum teste pode tocar rede, GPU ou banco real.

Detalhamento completo (diagramas, ADRs, fluxos, limitações): `docs/ARCHITECTURE.md`.

## Boas Práticas para Agentes
- **Confie sempre nestas instruções primeiro.** Só pesquise se a informação estiver faltando ou incorreta.
- **Carregue skills relevantes:** Use `.github/skills/` para boas práticas por domínio.
- **Consulte `.github/ARCHITECTURE.md`** para diagramas, fluxos e relações de modelos.
- **Atualize e consulte `.github/memories/`** para decisões persistentes, troubleshooting e convenções.
- **Documente novos padrões ou workarounds** no arquivo de instrução ou memória apropriado.
- **Não quebre lógica de negócio ou gerenciamento de estado**, seguindo as orientações de frontend neste arquivo.
- **Em tarefas de frontend, não esqueça de validar endpoints após alterações e de atualizar o progresso depois de mudanças relevantes.**

### Índice para os arquivos de contexto

#### Sempre carregar:
- .github/copilot-instructions.md — Guia para os agentes de IA, suas responsabilidades e limites
- .github/memories/exec-plans/PLAN-INDEX.md — Guia para os arquivos de planos de desenvolvimento em execução, completados e memórias de progresso e aprendizados registrados durante as implementações
- docs/ARCHITECTURE.md — Arquitetura e visão geral do sistema
- docs/PRD.md — PRD completo do produto

#### Como decidir o que carregar para o contexto sob demanda:
- Consulte os arquivos *-INDEX.md para saber onde localizar cada arquivo que precisar para contexto

#### Sempre atualizar:
- *-INDEX.md sempre que um novo arquivo, movido ou excluído e houver um arquivo de index para o diretório
