# Index dos Planos de Execução

Use este arquivo para localizar rapidamente os planos de execução ativos, completos, arquivados e o progresso das implementações.

## .github/memories/exec-plans/backlog/ - planos para futuras implementações

*Nenhum plano no backlog.*


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

### [2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa.md](completed/2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa.md)
**Objetivo:** Permitir que o observador submeta pedidos ao conselho e implementar o grafo dirigido (DAG) de comunicações onde os Chiefs deliberam, pedem agentes ao RA, delegam ao próprio time, recebem reports e decidem o próximo passo  
**Status:** ✅ Concluído em 2026-10-05  
**Entregas:** ADRs 012–015 (reuso de `reports_to_id` como vínculo de supervisão, veredito determinístico como piso, grafo em SVG sem D3/Cytoscape, reuso do barramento da Fase 3) · `InitialRequest` + `AgentTask` + `CommunicationEdge` com 10 tipos de aresta · `report_analysis` determinístico alimentando as 7 ferramentas de revisão do Chief · `agent_decision_engine` com APPROVE/REJECT/MODIFY/CONSULT_PEERS/ESCALATE, reconvocação, subtarefa e desempate do CEO · invariante de hierarquia inviolável (o RA cria agentes mas nunca supervisiona) · `network_orchestrator` com turno automático de 3 frentes · 13 endpoints REST + 3 eventos novos no `WS /ws/game-state` · migração `0004_fase_5_rede_corporativa` · aba "Rede corporativa" com grafo SVG de layout determinístico · 340 testes no backend + 84 no frontend  
**Documentação:** [docs/COMMUNICATION-GRAPH.md](../../docs/COMMUNICATION-GRAPH.md)  
**Progresso:** [2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa-progress.md](progress/2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa-progress.md)


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

### [2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa-progress.md](progress/2026-10-05-fase-5-pedidos-iniciais-deliberacao-colaborativa-progress.md)
**Plano:** Fase 5 - Rede Corporativa e Grafo de Comunicações  
**Status:** ✅ Concluído  
**Início:** 2026-10-05 · **Conclusão:** 2026-10-05  
**Contém:** ADRs 012–015, e 7 armadilhas com a correspondente correção — o enunciado da tarefa envenenando o parser de veredito (o planejador determinístico ecoa o enunciado na conclusão), marcador de risco casando no meio de palavra (`senha` dentro de `desenhar`), cobertura de objetivo quebrando com flexão verbal, o CEO virando supervisor ao desempatar, o container do frontend não espelhando o host (lint/type-check passando contra código antigo), `react-hooks/set-state-in-effect` e o prefixo vazio da API — além de 8 débitos técnicos mapeados

