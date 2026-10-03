# Plano de Implementação: Fase 1 - Motor Base e Isolamento

**Objetivo:** Estabelecer a infraestrutura base da aplicação com Docker Compose, banco de dados PostgreSQL, backend Python e o sistema de monitoramento de recursos ("A Natureza").

**Status:** ✅ Concluído em 2026-10-03

**Prazo Estimado:** ~2 semanas

---

## 1. Setup da Infraestrutura Docker Compose

- [x] Criar `docker-compose.yml` com serviços:
  - [x] PostgreSQL 16 (volume persistente) — `postgres:16.11-alpine`
  - [x] Ollama (com modelos otimizados para quantização Q4_K_M) — `ollama/ollama:0.12.11`
  - [x] Backend Python (FastAPI) — build local `theywork-backend:0.1.0`
  - [x] Redis (cache/queue para tasks assíncronas) — `redis:8.2.2-alpine`
- [x] Criar `.env.example` com variáveis de configuração
- [x] Documentar instruções de build e inicialização em `docs/SETUP.md`
- [x] Testar inicialização completa com `docker compose up -d`

> Extras: `docker-compose.override.yml` (hot-reload em dev) e `docker-compose.gpu.yml` (NVIDIA).
> Três redes: `edge` (exposta), `core` (`internal: true`, sem internet) e `inference`.

## 2. Backend Python Base (FastAPI)

- [x] Estruturar projeto Python:
  - [x] Criar pasta `backend/`
  - [x] Configurar `pyproject.toml` com dependências core (FastAPI, SQLAlchemy, Pydantic, psutil, GPUtil)
  - [x] Criar estrutura MVC: `models/`, `services/`, `routes/`, `config/` (+ `schemas/`)
- [x] Implementar configuração de ambiente (`config/settings.py`)
- [x] Criar estrutura base de logging (`config/logging.py` com structlog)
- [x] Implementar health check endpoint `/health` (+ `/health/live`)

## 3. Banco de Dados PostgreSQL

- [x] Criar schema inicial com Alembic (revisão `0001_schema_inicial`):
  - [x] Tabela `agents` (armazenar Chiefs e subagentes)
  - [x] Tabela `talent_bank` (Banco de Talentos do RA)
  - [x] Tabela `audit_logs` (logs de decisões da Natureza)
  - [x] Tabela `corporate_memory` (histórico corporativo de longo prazo)
- [x] Implementar migration base para inicialização (aplicada pelo `entrypoint.sh`)
- [x] Testar conexão do backend com PostgreSQL

## 4. Script da "Natureza" - Monitor de Recursos

- [x] Criar serviço `services/nature_manager.py`:
  - [x] Implementar leitura contínua de RAM (psutil)
  - [x] Implementar leitura de VRAM (GPUtil)
  - [x] Lógica de cálculo de recursos disponíveis vs. limites (16 GB RAM, 4 GB VRAM)
- [x] Criar sistema de alertas:
  - [x] Endpoint que retorna status de recursos para o backend (`GET /resources/status`)
  - [x] Sistema de fila para bloquear requisições de contratação quando em estado crítico
        (`POST /resources/hiring/evaluate` → `ALLOWED` / `DOWNGRADED` / `QUEUED` / `BLOCKED`)
- [x] Testes de carga unitária para validar correto funcionamento (21 testes)
- [x] Documentar limites físicos e mapeamento para narrativa corporativa
      (`docs/ARCHITECTURE.md` §4.1 e `docs/SETUP.md` §5)

## 5. Integração Ollama

- [x] Validar se Ollama roda corretamente no container Docker
- [x] Criar script de download/pull automático dos 5 modelos (`scripts/pull_models.sh`):
  - [x] Llama 3.2 3B (~2GB) — `llama3.2:3b` ✔ validado com pull real
  - [x] Phi-4 Mini 3.8B (~2.3GB) — `phi4-mini:3.8b`
  - [x] Gemma 4 E4B (~3GB) — `gemma3n:e4b`
  - [x] DeepSeek R1 8B (~5GB) — `deepseek-r1:8b`
  - [x] Qwen3 8B (~4.6GB) — `qwen3:8b`
- [x] Implementar endpoint `/models/available` que lista modelos disponíveis
- [x] Criar lógica de seleção automática de modelo por complexidade de tarefa
      (`services/model_catalog.py` + `GET /models/select`)

## 6. API Base para Gerenciamento de Agentes

- [x] Criar rotas iniciais:
  - [x] `POST /agents/chiefs/init` - Inicializa os 5 Chiefs (CEO, CTO, CMO, CFO, RA)
  - [x] `GET /agents/status` - Retorna status de todos os agentes
  - [x] `GET /resources/status` - Retorna status de recursos (Natureza)
- [x] Implementar ORM models para persistência de estado dos agentes
- [x] Criar logging de todas as ações de agentes (auditoria via `services/audit_service.py`)

## 7. Testes de Integração Fase 1

- [x] Testes unitários para `nature_manager.py`
- [x] Testes de conectividade: Docker Compose → PostgreSQL → Backend
- [x] Testes de conectividade: Backend → Ollama
- [x] Teste end-to-end: inicializar sistema e verificar todos os serviços
- [x] Documentar relatório de testes (arquivo de progresso + `docs/ARCHITECTURE.md` §8)

**Resultado:** 66 testes, 96% de cobertura, `ruff` e `mypy --strict` limpos.

## 8. Documentação e Preparação

- [x] Atualizar `README.md` com instruções de execução (foco na leitura por humanos)
- [x] Documentar arquitetura técnica em `docs/ARCHITECTURE.md`
- [x] Criar `docs/SETUP.md` com troubleshooting
- [x] Preparar contexto para Fase 2 (`docs/ARCHITECTURE.md` §9 — pontos de extensão)

---

## Dependências Entre Fases

```
Fase 1 (Motor Base) ← ✅ CONCLUÍDA
├─→ Fase 2 (Estruturação Societária)  ← DESBLOQUEADA
    ├─→ Fase 3 (Transparência e Observabilidade)
        └─→ Fase 4 (Motor 2D e Interface)
```

A Fase 1 está 100% completa e validada; a Fase 2 pode iniciar.
