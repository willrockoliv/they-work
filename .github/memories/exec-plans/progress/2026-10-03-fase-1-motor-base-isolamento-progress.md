# Progresso: Fase 1 - Motor Base e Isolamento

**Plano Associado:** `completed/2026-10-03-fase-1-motor-base-isolamento.md`

**Data de Início:** 2026-10-03

**Data de Conclusão:** 2026-10-03

**Status Geral:** ✅ Concluído e validado

---

## Resumo de Progresso

| Seção | Status | Progresso | Notas |
|-------|--------|-----------|-------|
| 1. Docker Compose | ✅ Concluído | 100% | 4 serviços + 3 redes isoladas + overrides de dev e GPU |
| 2. Backend Python | ✅ Concluído | 100% | FastAPI em camadas: config/models/schemas/services/routes |
| 3. PostgreSQL | ✅ Concluído | 100% | 4 tabelas, revisão `0001_schema_inicial` aplicada automaticamente |
| 4. Natureza | ✅ Concluído | 100% | RAM+VRAM+CPU, 4 vereditos, fila de contratações, 21 testes |
| 5. Ollama | ✅ Concluído | 100% | Catálogo de 5 modelos, pull script validado, seleção automática |
| 6. API Base | ✅ Concluído | 100% | 8 endpoints, Chiefs idempotentes, auditoria transacional |
| 7. Testes | ✅ Concluído | 100% | 66 testes, 96% de cobertura, E2E validado na stack real |
| 8. Docs | ✅ Concluído | 100% | README, ARCHITECTURE (10 seções, 5 diagramas), SETUP |

---

## Relatório de Testes

**Suíte automatizada** (`pytest`, offline, SQLite em memória):

```
66 passed  —  cobertura total: 96%
```

| Arquivo | Testes | Foco |
|---------|-------:|------|
| `test_nature_manager.py` | 21 | Orçamento, classificação, downgrade, bloqueio, fila FIFO |
| `test_api.py` | 17 | Todos os endpoints + cenários degradados |
| `test_model_catalog.py` | 13 | Integridade do catálogo e seleção por complexidade |
| `test_persistence.py` | 10 | Schema, idempotência de `init_chiefs`, auditoria, memória |
| `test_settings.py` | 5 | Validação de configuração |
| `test_ollama_client.py` | 5 | Parsing e tolerância a falhas |

**Validação end-to-end na stack real** (`docker compose up -d --build`):

| Verificação | Resultado |
|-------------|-----------|
| `docker compose ps` | 4/4 serviços `healthy` |
| Migração automática no boot | `0001_schema_inicial` aplicada pelo `entrypoint.sh` |
| `GET /health` | `ok` — postgres `ok`, ollama `ok` (v0.12.11) |
| `GET /resources/status` | RAM real lida: 15340 MB limite / 7573 em uso / 5719 alocáveis |
| `POST /agents/chiefs/init` | `created=5`; segunda chamada `created=0` (idempotente) |
| `./scripts/pull_models.sh llama3.2:3b` | Download real concluído (2.0 GB) |
| `GET /models/available` | `llama3.2:3b installed=True (1925 MB)`, demais `False` |
| `POST /resources/hiring/evaluate` | `ALLOWED → deepseek-r1:8b` com narrativa corporativa |
| Auditoria no PostgreSQL | 5× `AGENT_CREATED` + 1× `NATURE_DECISION` persistidos |
| `docker compose exec backend alembic current` | `0001_schema_inicial (head)` |

**Qualidade:** `ruff check .` limpo · `mypy --strict` limpo em 30 arquivos.

---

## Aprendizados e Decisões Importantes

### Infraestrutura

- **Tag `# syntax=docker/dockerfile:1.19` removida do Dockerfile.** Ela força o BuildKit a
  baixar o frontend do Docker Hub a cada build; em rede instável isso quebra o build com
  `TLS handshake timeout`. Nenhum recurso avançado era necessário.
- **Healthcheck sem `curl`.** Instalar `curl` exigiria pinar uma versão apt (regra de versões
  fixas), que quebra a cada atualização do Debian. Usamos `python -c "import urllib.request..."`,
  que já está na imagem.
- **`WORKDIR /app/backend`** (e não `/app`): sem isso, `docker compose exec backend alembic ...`
  falha porque o `alembic.ini` não é encontrado a partir do cwd.
- **Isolamento de rede em 3 camadas:** PostgreSQL e Redis em rede `internal: true` (sem rota
  para a internet e sem porta publicada); Ollama numa bridge separada porque precisa de saída
  apenas durante `ollama pull`. Todas as portas publicadas ficam em `127.0.0.1`.
- **`${POSTGRES_PASSWORD:?}`** no compose: falha cedo e com mensagem clara em vez de subir um
  banco com senha vazia.

### Compatibilidade Python 3.14

- Todas as dependências do stack têm wheels cp314 (fastapi 0.142.2, sqlalchemy 2.1.3,
  pydantic 2.13.5, psycopg 3.3.6, psutil 7.2.2). `gputil 1.4.0` compila a partir do sdist sem
  problemas (é Python puro, chama `nvidia-smi` por subprocess).
- `types-psutil` não tem releases com numeração alinhada ao psutil: foi preciso consultar as
  versões disponíveis no PyPI antes de pinar (`7.2.2.20260906`).

### Portabilidade PostgreSQL ↔ SQLite (testes)

- `BigInteger` **não autoincrementa no SQLite** — só `INTEGER` o faz. Solução adotada em
  `audit_logs.id`: `BigInteger().with_variant(Integer(), "sqlite")`.
- JSONB idem: `JSON().with_variant(JSONB(), "postgresql")`.
- `sa.Uuid(as_uuid=True)` funciona nos dois dialetos sem variante.
- `MetaData(naming_convention=...)` é essencial para que o autogenerate do Alembic produza
  diffs estáveis em vez de renomear índices a cada execução.

### FastAPI

- **`dependency_overrides` não aceita funções com parâmetros.** `overrides[dep] = make_ollama`
  fez o FastAPI interpretar o parâmetro `handler` como query param e levantar
  `FastAPIError: Invalid args for response field`. Correto: `overrides[dep] = lambda: make_ollama()`.
- `Settings` é cacheado com `@lru_cache` por processo ⇒ o `conftest.py` precisa definir as
  variáveis de ambiente **antes** de qualquer `import app.*` (daí o bloco de imports separado).

### Design da Natureza

- Sondas (`ram_probe`, `vram_probe`, `cpu_probe`) injetáveis no `dataclass` tornaram possível
  testar todos os regimes (saudável/alerta/crítico) sem manipular o hardware real.
- Separar `preferred_for(complexity)` de `best_fit_within(ceiling, budget)` deixou o conceito
  de *downgrade* explícito: é simplesmente `granted.tier < preferred.tier`.
- Quando o RA pede um modelo específico, ele vira **teto**, não decisão final — a Natureza
  ainda pode rebaixar.
- Toda decisão carrega uma `narrative` em linguagem corporativa, pronta para ser injetada no
  contexto dos agentes (Fase 2) e exibida na UI (Fase 4).

### Modelos Ollama

- O PRD menciona "Gemma 4 E4B", que não existe como tag. O equivalente real é
  **`gemma3n:e4b`** (Gemma 3n, variante E4B) — foi o adotado.
- Tags confirmadas: `llama3.2:3b`, `phi4-mini:3.8b`, `gemma3n:e4b`, `qwen3:8b`, `deepseek-r1:8b`.
- `OLLAMA_MAX_LOADED_MODELS=1` e `OLLAMA_NUM_PARALLEL=1` no compose: com 16 GB de RAM, dois
  modelos residentes simultâneos estouram o orçamento da Natureza.

---

## Débitos Técnicos

| # | Débito | Impacto | Encaminhamento |
|---|--------|---------|----------------|
| 1 | `NatureManager` é singleton em memória; a fila de contratações não sobrevive a restart | Baixo na Fase 1 | Migrar a fila para Redis (já provisionado) na Fase 2 |
| 2 | GPUtil não enxerga a GPU sem o override `docker-compose.gpu.yml` | `gpu_detected: false` no setup padrão | Documentado em SETUP §6; override criado |
| 3 | `psutil` lê a RAM do host, não do cgroup do container | Divergência em hosts com cgroup limitado | `NATURE_RAM_LIMIT_MB` permite fixar o teto manualmente |
| 4 | SQLAlchemy síncrono em rotas `async` (roda no threadpool) | Nenhum na escala local | Reavaliar só se houver gargalo medido |
| 5 | Sem monitoramento contínuo em background (a Natureza amostra sob demanda) | Alertas são *pull*, não *push* | Task periódica + WebSocket na Fase 3/4 (`NATURE_POLL_INTERVAL_SECONDS` já existe) |
| 6 | `scripts/pull_models.sh` validado apenas com `llama3.2:3b` | Baixo | Os outros 4 seguem o mesmo caminho de código |

---

## Bloqueadores

*Nenhum. A Fase 2 está desbloqueada.*

---

## Próximas Ações (Fase 2)

1. `services/ra_service.py` — gestão do Banco de Talentos (`TalentProfile` já tem tabela e schema).
2. `services/council_service.py` — framework de decisão C-Level e resolução de impasses pelo CEO.
3. Instanciação real de subagentes: `POST /agents/subagents` consumindo
   `/resources/hiring/evaluate` antes de criar o `Agent`.
4. Integração de inferência: `OllamaClient.generate()` / `chat()` usando o modelo concedido
   pela Natureza.
5. Migrar a fila de contratações para Redis (débito #1).
