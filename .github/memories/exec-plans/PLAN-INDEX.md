# Index dos Planos de Execução

Use este arquivo para localizar rapidamente os planos de execução ativos, completos, arquivados e o progresso das implementações.

## .github/memories/exec-plans/backlog/ - planos para futuras implementações

### [2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa.md](backlog/2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa.md)
**Objetivo:** Implementar UI para submeter pedidos aos chiefs e fluxo onde chiefs deliberam coletivamente, conversam entre si e delegam tarefas para outros agentes  
**Status:** 📋 Planejado  
**Conceito:** Grafo dinâmico de comunicações (DAG) — não é linear, é rede corporativa com feedback loops  
**Estimativa:** 52–64 horas (backend + frontend + testes)  

**📚 Documentação Complementar em `docs/fase-5/` (LEIA NESTA ORDEM):**
1. [docs/fase-5/README-FASE-5.md](../../docs/fase-5/README-FASE-5.md) — **COMECE AQUI** — Resumo executivo + TL;DR
2. [docs/fase-5/ARQUITETURA-FASE-5.md](../../docs/fase-5/ARQUITETURA-FASE-5.md) — Diagramas Mermaid da arquitetura (frontend → backend → db)
3. [docs/fase-5/GRAFO-EXEMPLO.md](../../docs/fase-5/GRAFO-EXEMPLO.md) — Exemplo prático passo a passo: "Fundar startup" (14 estados)
4. [docs/fase-5/FLUXO-DECISAO-CHIEF.md](../../docs/fase-5/FLUXO-DECISAO-CHIEF.md) — Diagramas do ciclo de análise de reports (REJECT/MODIFY/CONSULT/APPROVE)
5. [docs/fase-5/FERRAMENTAS-CHIEF-ANALYSIS.md](../../docs/fase-5/FERRAMENTAS-CHIEF-ANALYSIS.md) — 7 ferramentas novas para análise

**Próximas ações:** Promover para `active/` quando pronto para implementar


## .github/memories/exec-plans/active/ - planos em andamento

*Nenhum plano em andamento.*


## .github/memories/exec-plans/completed/ - planos completados

### [2026-10-03-fase-1-motor-base-isolamento.md](completed/2026-10-03-fase-1-motor-base-isolamento.md)
**Objetivo:** Estabelecer infraestrutura base (Docker, PostgreSQL, Ollama, backend FastAPI, monitor de recursos "Natureza")  
**Status:** ✅ Concluído em 2026-10-03  
**Entregas:** 4 serviços conteinerizados em redes isoladas · schema inicial com Alembic · `NatureManager` (RAM/VRAM/CPU → vereditos corporativos) · catálogo dos 5 modelos Ollama com seleção automática · 8 endpoints HTTP · 66 testes / 96% de cobertura  
**Progresso:** [2026-10-03-fase-1-motor-base-isolamento-progress.md](progress/2026-10-03-fase-1-motor-base-isolamento-progress.md)

### [2026-10-03-fase-2-estruturacao-societaria.md](completed/2026-10-03-fase-2-estruturacao-societaria.md)
**Objetivo:** Implementar personas C-Level (CEO, CTO, CMO, CFO), Recursos Agênticos (RA), Banco de Talentos e seleção dinâmica de modelos  
**Status:** ✅ Concluído em 2026-10-03  
**Entregas:** `ChiefAgent` + 5 personas com veto do CTO e desempate do CEO · pipeline completo do RA (triagem → Natureza → talento → contratação → demissão) · Banco de Talentos versionado com rating · classificador de complexidade · teto de contratação por regime da infraestrutura · 15 endpoints novos · migração `0002_fase_2_sociedade` · 168 testes / 98% de cobertura  
**Progresso:** [2026-10-03-fase-2-estruturacao-societaria-progress.md](progress/2026-10-03-fase-2-estruturacao-societaria-progress.md)

### [2026-10-03-fase-3-transparencia-observabilidade.md](completed/2026-10-03-fase-3-transparencia-observabilidade.md)
**Objetivo:** Interceptar e visualizar o fluxo cognitivo ReAct de cada agente em tempo real, transformando pensamentos brutos em fluxogramas para o frontend  
**Status:** ✅ Concluído em 2026-10-03  
**Entregas:** motor ReAct próprio sobre o streaming do Ollama (sem LangGraph/CrewAI — ADR-004) · `reasoning_sessions` + `reasoning_steps` com discriminador (ADR-005) · `ReasoningTracer` com os 4 callbacks e contabilidade de tokens · broker pub/sub in-process com backpressure (ADR-006) · 5 ferramentas offline com captura integral de entrada/saída · fluxograma com layout hints e aresta de ciclo · 9 endpoints REST + 2 canais WebSocket com replay · métricas de custo (MB·s) e ROI, retenção e export · fallback determinístico offline · migração `0003_fase_3_observabilidade` · 255 testes / 98% de cobertura  
**Progresso:** [2026-10-03-fase-3-transparencia-observabilidade-progress.md](progress/2026-10-03-fase-3-transparencia-observabilidade-progress.md)

### [2026-10-03-fase-4-motor-2d-interface.md](completed/2026-10-03-fase-4-motor-2d-interface.md)
**Objetivo:** Criar a interface 2D top-down do escritório virtual com avatares, balões de diálogo, painel de raio-X cognitivo e WebSocket em tempo real  
**Status:** ✅ Concluído em 2026-10-03  
**Entregas:** planta de 40×24 tiles com lotação determinística em memória (ADR-010) · `game_service` como projeção de leitura + `diff()` de snapshots · 5 endpoints REST novos · canal único `WS /ws/game-state` reaproveitando o barramento da Fase 3 (ADR-011) · frontend Vite 8 + React 19 + PixiJS 8 + Zustand 5 com sprites procedurais (ADR-008/009) · avatares animados, balões FIFO, painel de raio-X com 3 abas, log de comunicações filtrável, notificações e atalhos de teclado · container próprio isolado na rede `edge` · 286 testes no backend + 69 no frontend  
**Progresso:** [2026-10-03-fase-4-motor-2d-interface-progress.md](progress/2026-10-03-fase-4-motor-2d-interface-progress.md)


## .github/memories/exec-plans/archived/ - planos arquivados

*Nenhum plano arquivado.*


## .github/memories/exec-plans/progress/ - progresso das implementaçoes com aprendizados e anotações importantes

### [2026-10-03-fase-1-motor-base-isolamento-progress.md](progress/2026-10-03-fase-1-motor-base-isolamento-progress.md)
**Plano:** Fase 1 - Motor Base e Isolamento  
**Status:** ✅ Concluído  
**Início:** 2026-10-03 · **Conclusão:** 2026-10-03  
**Contém:** relatório de testes (automatizados + E2E), decisões de infraestrutura, armadilhas de Python 3.14 / SQLite↔PostgreSQL / FastAPI, e 6 débitos técnicos mapeados

### [2026-10-03-fase-2-estruturacao-societaria-progress.md](progress/2026-10-03-fase-2-estruturacao-societaria-progress.md)
**Plano:** Fase 2 - Estruturação Societária e Recursos Agênticos  
**Status:** ✅ Concluído  
**Início:** 2026-10-03 · **Conclusão:** 2026-10-03  
**Contém:** relatório de testes (automatizados + E2E), decisão por deliberação determinística, armadilhas de enum do PostgreSQL em migrações, calibração reserva × limiares da Natureza e 9 débitos técnicos mapeados

### [2026-10-03-fase-3-transparencia-observabilidade-progress.md](progress/2026-10-03-fase-3-transparencia-observabilidade-progress.md)
**Plano:** Fase 3 - Transparência e Observabilidade  
**Status:** ✅ Concluído  
**Início:** 2026-10-03 · **Conclusão:** 2026-10-03  
**Contém:** ADRs 004–007 (wrapper próprio vs. LangGraph/CrewAI, tabela única com discriminador, broker in-process, captura síncrona), armadilhas de thread-safety no pub/sub, `dependency_overrides` em WebSocket, tolerância do parser ReAct, definição de custo em MB·s e ROI, validação E2E com streaming real e 8 débitos técnicos mapeados

### [2026-10-03-fase-4-motor-2d-interface-progress.md](progress/2026-10-03-fase-4-motor-2d-interface-progress.md)
**Plano:** Fase 4 - Motor 2D e Interface  
**Status:** ✅ Concluído  
**Início:** 2026-10-03 · **Conclusão:** 2026-10-03  
**Contém:** ADRs 008–011 (PixiJS vs. Babylon/Phaser/Canvas, sprites procedurais, posições em memória, reuso do barramento), armadilhas do ecossistema Node (peer deps do typescript-eslint, rolldown no Vite 8, `vi.mock` içado), seletor instável no Zustand que estoura o `useSyncExternalStore`, a regra `set-state-in-effect` do ESLint 10, colisão de `name`/`label` com `Container` do Pixi, ponte de enquadramento entre renderizador e store, relatório de validação E2E no navegador e 8 débitos técnicos mapeados

