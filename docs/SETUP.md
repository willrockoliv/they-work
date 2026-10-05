# Setup, Operação e Troubleshooting

Guia operacional do TheyWork. Para entender *o que* o sistema faz, veja o
[README](../README.md); para entender *como* ele é construído, veja a
[Arquitetura](ARCHITECTURE.md).

---

## 1. Pré-requisitos

| Item | Mínimo | Observação |
|------|--------|------------|
| Docker Engine | 29.x | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |
| RAM | 16 GB | É o limite assumido pela Natureza |
| Disco livre | ~25 GB | ~17 GB de modelos + imagens + volumes |
| GPU (opcional) | NVIDIA com 4 GB VRAM | Requer NVIDIA Container Toolkit |
| Python local (opcional) | 3.14.8 via pyenv | Só para lint/tipos/testes — ver `.python-version` |

> **Regra operacional:** a aplicação **nunca** roda diretamente no host. Backend, banco,
> cache e inferência sempre sobem via Docker Compose.

---

## 2. Primeira execução

```bash
# 1. Arquivo de ambiente
cp .env.example .env
```

Abra o `.env` e, no mínimo, defina `POSTGRES_PASSWORD`. Se alterar o usuário ou o banco,
ajuste também `DATABASE_URL` de forma coerente.

```bash
# 2. Build + subida da stack
docker compose up -d --build

# 3. Verificação
docker compose ps
curl http://localhost:8000/health
```

O backend aplica as migrações Alembic automaticamente no `entrypoint.sh` — não há passo
manual de criação de schema.

```bash
# 4. Modelos open source (~17 GB; só na primeira vez)
./scripts/pull_models.sh

# ou apenas os que você for usar agora
./scripts/pull_models.sh llama3.2:3b phi4-mini:3.8b

# 5. Conselho administrativo
curl -X POST http://localhost:8000/agents/chiefs/init
curl http://localhost:8000/agents/status
```

### Com GPU NVIDIA

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Esse override dá acesso à GPU para o `ollama` (inferência) e para o `backend` (para que o
`nvidia-smi` consiga ler a VRAM). Sem ele, `/resources/status` retorna `gpu_detected: false`
e a Natureza decide apenas com base na RAM.

---

## 3. Comandos do dia a dia

```bash
docker compose up -d                 # subir
docker compose down                  # parar (volumes preservados)
docker compose down -v               # parar e APAGAR banco e modelos
docker compose logs -f backend       # acompanhar logs
docker compose restart backend       # reiniciar só o backend
docker compose up -d --build backend # rebuild após mudar dependências
```

### Banco de dados

O PostgreSQL vive numa rede `internal` e **não publica porta no host** (decisão de
isolamento). O acesso é feito por dentro do container:

```bash
docker compose exec postgres psql -U theywork -d theywork

# atalhos úteis
docker compose exec postgres psql -U theywork -d theywork -c "\dt"
docker compose exec postgres psql -U theywork -d theywork \
  -c "SELECT event_type, actor, decision, summary FROM audit_logs ORDER BY id DESC LIMIT 10;"
```

### Migrações

```bash
docker compose exec backend alembic current
docker compose exec backend alembic history
docker compose exec backend alembic revision --autogenerate -m "descrição"
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
```

> Sempre revise o arquivo gerado pelo `--autogenerate` antes de commitar.

### Ollama

```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama rm deepseek-r1:8b
```

---

## 4. Ambiente local (lint, tipos, testes)

O virtualenv local existe **apenas** para ferramentas de qualidade. Nenhum serviço roda nele.

```bash
pyenv activate they-work        # ou: source ~/.pyenv/versions/they-work/bin/activate
pip install -e ".[dev]"

pytest                          # 66 testes, offline
pytest --cov                    # com cobertura
ruff check . --fix              # lint + autofix
mypy                            # type checking estrito
```

Os testes usam SQLite em memória e dublês de HTTP/hardware: **não** exigem a stack Docker
no ar e não acessam a rede.

---

## 5. Configuração

Todas as chaves do `.env.example` mapeiam 1:1 para campos de
[`Settings`](../backend/app/config/settings.py). Precedência: variável de ambiente >
`.env` > valor padrão.

### Os parâmetros da Natureza

| Variável | Padrão | O que significa |
|----------|--------|-----------------|
| `NATURE_RAM_LIMIT_MB` | `16384` | Teto de RAM que a empresa pode enxergar |
| `NATURE_VRAM_LIMIT_MB` | `4096` | Teto de VRAM |
| `NATURE_RESERVED_RAM_MB` | `2048` | Reserva para SO/IDE — nunca vai para agentes |
| `NATURE_RESERVED_VRAM_MB` | `512` | Reserva de VRAM |
| `NATURE_WARNING_THRESHOLD` | `0.75` | Uso a partir do qual contratações são avaliadas |
| `NATURE_CRITICAL_THRESHOLD` | `0.90` | Uso a partir do qual há congelamento/downgrade forçado |
| `NATURE_MAX_CONCURRENT_SUBAGENTS` | `4` | "Estações de trabalho" disponíveis |
| `NATURE_MAX_QUEUE_SIZE` | `32` | Tamanho da fila de contratações represadas |

**Ajustando para outro hardware:** com 32 GB de RAM, suba `NATURE_RAM_LIMIT_MB=32768` e
`NATURE_MAX_CONCURRENT_SUBAGENTS=8`. Com 8 GB, reduza para `8192` e `2`.

---

## 6. Troubleshooting

### `backend` reinicia em loop

```bash
docker compose logs backend --tail 50
```

| Sintoma no log | Causa | Correção |
|----------------|-------|----------|
| `PostgreSQL indisponível` após 60s | Banco não subiu ou credenciais divergem | Confira `POSTGRES_PASSWORD` e `DATABASE_URL` no `.env` — os dois precisam bater |
| `Target database is not up to date` | Migração pendente manualmente criada | `docker compose exec backend alembic upgrade head` |
| `ModuleNotFoundError: app` | Build desatualizado | `docker compose up -d --build backend` |

### `POSTGRES_PASSWORD` não definido

```text
error: defina POSTGRES_PASSWORD no .env
```

O compose usa `${POSTGRES_PASSWORD:?}` de propósito: falhar cedo é melhor que subir um banco
com senha vazia. Crie o `.env` a partir do `.env.example`.

### Alterei a senha do Postgres e o backend não conecta

O volume `theywork_postgres_data` mantém a senha do **primeiro** `initdb`. Para resetar:

```bash
docker compose down -v          # ATENÇÃO: apaga o banco e os modelos
docker compose up -d --build
```

### `/health` retorna `degraded` com `ollama: down`

```bash
docker compose ps ollama
docker compose logs ollama --tail 30
docker compose exec ollama ollama list
```

O container do Ollama leva até ~30s para ficar `healthy` na primeira subida.

### `ollama pull` falha com timeout

O serviço `ollama` está na rede `inference`, que tem saída para a internet. Se houver proxy
corporativo, configure-o no Docker daemon. Para retomar um download interrompido, basta rodar
o `pull` novamente — o Ollama é incremental.

### `gpu_detected: false` mesmo com GPU NVIDIA

Esperado sem o override de GPU. Verifique, nesta ordem:

```bash
nvidia-smi                                            # driver no host
docker run --rm --gpus all ubuntu nvidia-smi          # NVIDIA Container Toolkit
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
docker compose exec backend python -c "import GPUtil; print(GPUtil.getGPUs())"
```

A Natureza continua funcionando sem GPU — ela apenas decide com base em RAM, que é o recurso
mais restritivo no hardware alvo.

### Contratações sempre voltam `QUEUED` / `BLOCKED`

Consulte o orçamento real:

```bash
curl -s http://localhost:8000/resources/status | python -m json.tool
```

Se `ram_allocatable_mb` estiver baixo, ou há processos pesados no host, ou
`NATURE_RESERVED_RAM_MB` está alto demais para a sua máquina. Esse comportamento é
**intencional** — é a Natureza fazendo o trabalho dela.

### Porta 8000 já em uso

```bash
ss -tulpn | grep 8000
```

Mude `API_PORT` no `.env` e rode `docker compose up -d`.

### Testes falham com `IntegrityError` em SQLite

Indica um tipo de coluna incompatível entre PostgreSQL e SQLite. Use variantes de dialeto nos
modelos (ex.: `BigInteger().with_variant(Integer(), "sqlite")`), conforme o padrão já adotado
em [`models/base.py`](../backend/app/models/base.py).

---

## 7. Reset completo

```bash
docker compose down -v
docker system prune -f
rm -rf .pytest_cache .mypy_cache .ruff_cache
docker compose up -d --build
./scripts/pull_models.sh
curl -X POST http://localhost:8000/agents/chiefs/init
```
