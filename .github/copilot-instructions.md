---
name: Copilot Agent Instructions
description: Instruções persistentes para LLMs que trabalham neste workspace. Este arquivo é lido automaticamente pelo GitHub Copilot como contexto em toda interação. 
applyTo: "**/*"
---

# Instruções de Onboarding para o Copilot Cloud Agent

## Visão Geral

**Propósito do Repositório:**


**Stack & Tamanho:**


**Arquivos-chave na raiz:**


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
- **Python:** `ruff check .` ou `flake8 .` (se configurado)
- **JS/TS:** `docker compose exec frontend npm run lint` (usa ESLint, config em `frontend/eslint.config.mjs`)
- **Auto-fix:** `ruff check . --fix` ou `docker compose exec frontend npm run lint -- --fix`

### Type Checking
- **Python:** `mypy .` (se configurado)
- **TypeScript:** `docker compose exec frontend npm run type-check` ou `docker compose exec frontend npx tsc --noEmit`

### Testes
- **Backend:** `pytest` (unitário/integrado, usa SQLite in-memory para integração)

### Problemas Comuns & Workarounds
- Sempre rode `npm install` antes de buildar o frontend.
- Se ocorrerem erros de banco, garanta que as migrações estão atualizadas (`alembic upgrade head`).

### Validação de Frontend (Obrigatória para Agentes)
- **Use o Integrated Browser do VS Code** para validar visual e comportamento das páginas localmente.
- **Após qualquer alteração de frontend, navegue por TODAS as telas alteradas** (incluindo rotas públicas e autenticadas impactadas).
- **Quando a tarefa envolver código em `frontend/` ou integração frontend-backend**, siga o padrão de pastas do projeto, valide endpoints alterados e atualize componentes e páginas conforme especificações do projeto.

## Estrutura & Arquitetura do Projeto


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
