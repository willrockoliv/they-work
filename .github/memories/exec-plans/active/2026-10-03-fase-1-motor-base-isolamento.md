# Plano de Implementação: Fase 1 - Motor Base e Isolamento

**Objetivo:** Estabelecer a infraestrutura base da aplicação com Docker Compose, banco de dados PostgreSQL, backend Python e o sistema de monitoramento de recursos ("A Natureza").

**Status:** Iniciando

**Prazo Estimado:** ~2 semanas

---

## 1. Setup da Infraestrutura Docker Compose

- [ ] Criar `docker-compose.yml` com serviços:
  - [ ] PostgreSQL 16 (volume persistente)
  - [ ] Ollama (com modelos otimizados para quantização Q4_K_M)
  - [ ] Backend Python (FastAPI)
  - [ ] Redis (cache/queue para tasks assíncronas)
- [ ] Criar `.env.example` com variáveis de configuração
- [ ] Documentar instruções de build e inicialização em `docs/SETUP.md`
- [ ] Testar inicialização completa com `docker compose up -d`

## 2. Backend Python Base (FastAPI)

- [ ] Estruturar projeto Python:
  - [ ] Criar pasta `backend/`
  - [ ] Configurar `pyproject.toml` com dependências core (FastAPI, SQLAlchemy, Pydantic, psutil, GPUtil)
  - [ ] Criar estrutura MVC: `models/`, `services/`, `routes/`, `config/`
- [ ] Implementar configuração de ambiente (`config/settings.py`)
- [ ] Criar estrutura base de logging
- [ ] Implementar health check endpoint `/health`

## 3. Banco de Dados PostgreSQL

- [ ] Criar schema inicial com Alembic:
  - [ ] Tabela `agents` (armazenar Chiefs e subagentes)
  - [ ] Tabela `talent_bank` (Banco de Talentos do RA)
  - [ ] Tabela `audit_logs` (logs de decisões da Natureza)
  - [ ] Tabela `corporate_memory` (histórico corporativo de longo prazo)
- [ ] Implementar migration base para inicialização
- [ ] Testar conexão do backend com PostgreSQL

## 4. Script da "Natureza" - Monitor de Recursos

- [ ] Criar serviço `services/nature_manager.py`:
  - [ ] Implementar leitura contínua de RAM (psutil)
  - [ ] Implementar leitura de VRAM (GPUtil)
  - [ ] Lógica de cálculo de recursos disponíveis vs. limites (16 GB RAM, 4 GB VRAM)
- [ ] Criar sistema de alertas:
  - [ ] Endpoint que retorna status de recursos para o backend
  - [ ] Sistema de fila para bloquear requisições de contratação quando em estado crítico
- [ ] Testes de carga unitária para validar correto funcionamento
- [ ] Documentar limites físicos e mapeamento para narrativa corporativa

## 5. Integração Ollama

- [ ] Validar se Ollama roda corretamente no container Docker
- [ ] Criar script de download/pull automático dos 5 modelos:
  - [ ] Llama 3.2 3B (~2GB)
  - [ ] Phi-4 Mini 3.8B (~2.3GB)
  - [ ] Gemma 4 E4B (~3GB)
  - [ ] DeepSeek R1 8B (~5GB)
  - [ ] Qwen3 8B (~4.6GB)
- [ ] Implementar endpoint `/models/available` que lista modelos disponíveis
- [ ] Criar lógica de seleção automática de modelo por complexidade de tarefa

## 6. API Base para Gerenciamento de Agentes

- [ ] Criar rotas iniciais:
  - [ ] `POST /agents/chiefs/init` - Inicializa os 5 Chiefs (CEO, CTO, CMO, CFO, RA)
  - [ ] `GET /agents/status` - Retorna status de todos os agentes
  - [ ] `GET /resources/status` - Retorna status de recursos (Natureza)
- [ ] Implementar ORM models para persistência de estado dos agentes
- [ ] Criar logging de todas as ações de agentes (auditoria)

## 7. Testes de Integração Fase 1

- [ ] Testes unitários para `nature_manager.py`
- [ ] Testes de conectividade: Docker Compose → PostgreSQL → Backend
- [ ] Testes de conectividade: Backend → Ollama
- [ ] Teste end-to-end: inicializar sistema e verificar todos os serviços
- [ ] Documentar relatório de testes

## 8. Documentação e Preparação

- [ ] Atualizar `README.md` com instruções de execução (foco na leitura por humanos)
- [ ] Documentar arquitetura técnica em `docs/ARCHITECTURE.md` (utilizar a skill .github/skills/architecture-blueprint-generator/SKILL.md)
- [ ] Criar `docs/SETUP.md` com troubleshooting
- [ ] Preparar contexto para Fase 2 (estrutura C-Level)

---

## Dependências Entre Fases

```
Fase 1 (Motor Base) ← BLOQUEANTE CRÍTICA
├─→ Fase 2 (Estruturação Societária)
    ├─→ Fase 3 (Transparência e Observabilidade)
        └─→ Fase 4 (Motor 2D e Interface)
```

Nenhuma outra fase pode iniciar até que Fase 1 esteja 100% completa e validada.
