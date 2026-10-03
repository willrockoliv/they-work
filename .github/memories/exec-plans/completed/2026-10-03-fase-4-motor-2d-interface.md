# Plano de Implementação: Fase 4 - Motor 2D e Interface

**Objetivo:** Criar a visualização interativa 2D top-down do escritório virtual com avatares de agentes, balões de diálogo, painel lateral de raio-X cognitivo e sincronização em tempo real via WebSocket.

**Status:** ✅ Concluído em 2026-10-03

**Bloqueante:** ~~Fase 3 (Transparência e Observabilidade)~~ — concluída

---

## 1. Scaffolding do Frontend

- [x] Criar estrutura de projeto `frontend/`:
  - [x] Setup inicial (React 19 + TypeScript 5.9)
  - [x] Configurar empacotador (Vite 8)
  - [x] Setup de testes (Vitest 5 + Testing Library)
- [x] Configurar ambiente de desenvolvimento:
  - [x] ESLint 10 e Prettier 3
  - [x] Docker compose build para frontend
  - [x] Hot reload durante desenvolvimento (bind mount + polling)
- [x] Criar estrutura de pastas:
  - [x] `components/` - componentes reutilizáveis
  - [x] `engine/` - renderizador 2D (equivalente a `views/` para o canvas)
  - [x] `services/` - chamadas de API e WebSocket
  - [x] `types/` - tipos TypeScript espelhando os schemas do backend
  - [x] `styles/` - tema e CSS

## 2. Motor 2D e Canvas

- [x] Escolher engine 2D adequada (**ADR-008: PixiJS 8**):
  - [x] Opção 1: Babylon.js — descartada (3D completo, peso desproporcional)
  - [x] Opção 2: Phaser 3 — descartada (duplicaria o estado que vive no React/Zustand)
  - [x] Opção 3: PixiJS — **escolhida** (renderizador WebGL fino, sem opinião de arquitetura)
  - [x] Opção 4: Canvas 2D vanilla — descartada (reimplementaria batching e culling)
- [x] Implementar renderizador do mapa:
  - [x] Mapa base estilo pixel-art / 16-bits (sprites procedurais, ADR-009)
  - [x] Grid de posições (40×24 tiles de 32 px)
  - [x] Zoom e pan do mapa (roda, arrasto, teclado)
  - [x] Camadas (piso, mobiliário, agentes, rótulos)
- [x] Otimizações:
  - [x] Renderização apenas do viewport visível (`visibleTileBounds` + `renderable`)
  - [x] Batch rendering: avatares são `Sprite` sobre texturas cacheadas por papel/quadro
  - [x] Throttling: rótulos somem abaixo de 85% de zoom; o tick do servidor é configurável

## 3. Avatares e Animações

- [x] Criar sprites de agentes (procedurais):
  - [x] Avatares dos 5 Chiefs com cor por papel e crachá dourado
  - [x] Template de avatar para subagentes
  - [x] Estados: idle, thinking, working, celebrating, error (blocked)
- [x] Implementar movimento:
  - [x] Pathfinding em L (`routeBetween`) — o salão é aberto, A\* seria excesso
  - [x] Suavização de movimento (`damp` / `stepDistance` independentes de quadro)
  - [x] Animação de caminhada (dois quadros alternados)
- [x] Implementar animações de estado:
  - [x] Balão de pensamento acima da cabeça
  - [x] Ícone de "trabalhando" (glifo girando) e pulsação no "pensando"
  - [x] Indicador de progresso (barra sobre a cabeça durante o ciclo ReAct)
  - [x] Partículas para celebração de conclusão

## 4. Ambientes Virtuais (Escritório)

- [x] Desenhar layout do escritório:
  - [x] Mesas para cada Chief (cadeira cativa por cargo)
  - [x] Estações de trabalho para subagentes (12 postos)
  - [x] Sala de reunião isolada (6 lugares)
  - [x] Área de "bench" (8 lugares) e sala dos servidores
- [x] Implementar pontos de interesse (hotspots):
  - [x] Clicar no nome do cômodo enquadra a câmera nele
  - [x] Visualização de status em local (anel de atividade sob o avatar)
  - [x] Interações contextuais (clique no agente abre o raio-X)

## 5. Balões de Diálogo e Comunicação

- [x] Sistema de chat bubbles:
  - [x] Balões acima de agentes
  - [x] Fila de mensagens (FIFO, limitada a 4)
  - [x] Auto-dismiss após 6 s com desvanecimento
- [x] Diálogos estruturados:
  - [x] Tarefa recebida (`session.started`)
  - [x] Pensamento / ferramenta / observação (`step`)
  - [x] Conclusão de tarefa (`CONCLUSION`) e falha (`session.finished`)
- [x] Log de comunicações:
  - [x] Janela de chat geral (todas as conversas)
  - [x] Filtro por agente
  - [x] Timestamp de cada mensagem

## 6. Painel Lateral do Raio-X Cognitivo

- [x] UI do painel lateral:
  - [x] Cabeçalho com nome do agente selecionado
  - [x] Tabs: Info, Raciocínio, Histórico
- [x] Aba "Info":
  - [x] Nome, função, modelo LLM utilizado
  - [x] Status atual (ocioso, raciocinando, trabalhando, bloqueado)
  - [x] Tokens consumidos
  - [x] Tempo decorrido na tarefa atual
- [x] Aba "Reasoning Flow":
  - [x] Fluxograma interativo do ReAct
  - [x] Nodes: [Pensamento], [Ferramenta], [Observação], [Conclusão]
  - [x] Expandir/colapsar nodes (`<details>`)
  - [x] Copiar conteúdo de cada node
  - [x] Timeline vertical com aresta de ciclo (`↻ reavalia`)
- [x] Aba "History":
  - [x] Últimas 10 tarefas do agente
  - [x] Duração, status, modelo
  - [x] Clique para ver reasoning histórico

## 7. Sincronização em Tempo Real (WebSocket)

- [x] Implementar cliente WebSocket:
  - [x] Conexão para `/ws/game-state`
  - [x] Reconexão automática com backoff exponencial e jitter
  - [x] Watchdog de silêncio (o servidor emite `game.tick`/`heartbeat`)
- [x] Tipos de eventos sincronizados:
  - [x] Movimento de agente → atualiza posição (`agent.moved`)
  - [x] Novo agente → adiciona ao canvas (`agent.joined`)
  - [x] Agente saiu → remove do canvas (`agent.left`)
  - [x] Nova mensagem → mostra chat bubble (`step`)
  - [x] Novo reasoning step → atualiza painel lateral
  - [x] Status do agente mudou → atualiza visual (`agent.status`)
- [x] Gerenciador de estado cliente:
  - [x] Zustand (`gameStore` para o mundo, `uiStore` para a interface)
  - [x] Sincronizar estado do backend (snapshot + diffs)
  - [x] Atualizações otimistas de câmera e seleção

## 8. Interatividade e Controles

- [x] Clique em agente:
  - [x] Seleciona agente
  - [x] Abre painel lateral
  - [x] Destaca agente no mapa
- [x] Ações no painel:
  - [x] Centraliza a câmera no agente
  - [x] Expande o painel lateral em tela cheia
- [x] Botões de controle:
  - [x] Play/Pause da simulação (eventos ficam represados, não se perdem)
  - [x] Speed control (1x, 2x, 4x)
  - [x] Reset de estado
  - [x] Dark/Light mode
- [x] Atalhos de teclado:
  - [x] ESC: fecha painel lateral
  - [x] Space: play/pause
  - [x] Arrow keys: pan mapa
  - [x] +/-: zoom · `0`: reenquadra · `C`: log de comunicações

## 9. Painel de Monitoramento Global

- [x] Barra superior com informações:
  - [x] Hora corporativa simulada (1 s real = 1 min de expediente)
  - [x] Recursos disponíveis (RAM/VRAM) via "Natureza"
  - [x] Número de subagentes ativos e fila de contratação
  - [x] Receita/Custo corporativo (tokens entregues × MB·s)
- [x] Notificações:
  - [x] Alerta quando recurso crítico (não some sozinho)
  - [x] Aviso de agente bloqueado
  - [x] Celebração de milestone (entrega concluída)
- [x] Controles de visualização:
  - [x] Zoom e reenquadramento
  - [x] Tema claro/escuro

## 10. Validação Visual

- [x] Teste no navegador integrado do VS Code (Chromium)
- [x] Responsividade (grid colapsa para empilhado abaixo de 820 px)
- [x] Performance:
  - [x] Ticker do Pixi a 60 FPS com culling por viewport
  - [x] Latência do WebSocket limitada ao tick do servidor (2 s por padrão)
  - [x] Texturas cacheadas suportam dezenas de avatares sem novo draw call
- [x] Acessibilidade básica:
  - [x] Contraste adequado nos dois temas
  - [x] Navegação por teclado e `:focus-visible` explícito
  - [x] Labels descritivos (`aria-label`, `role`, `aria-live`)

## 11. Integração com Backend

- [x] Endpoints necessários:
  - [x] `GET /game/state` - estado inicial completo
  - [x] `GET /game/map` - planta estática do escritório
  - [x] `GET /agents/status` - lista de agentes (já existia)
  - [x] `GET /agents/{id}/position` - posição
  - [x] `POST /agents/{id}/move` e `POST /agents/{id}/recall`
  - [x] WebSocket `/ws/game-state` - eventos em tempo real
- [x] Tratamento de erros:
  - [x] Desconexão de WebSocket (badge de estado + reconexão)
  - [x] Falha em chamadas HTTP (`ApiError` com status e detalhe)
  - [x] Estados inconsistentes (eventos de agente desconhecido são ignorados)

## 12. Testes e Validação

- [x] Testes unitários:
  - [x] Componentes React (barra, painel, fluxograma, log)
  - [x] Lógica de movimento e câmera (`layoutMath`)
  - [x] Parsing de eventos WebSocket (`gameStore`, `socket`)
- [x] Testes de integração:
  - [x] Backend: `test_api_fase4.py` cobre REST e o canal `/ws/game-state`
  - [x] Sincronizar estado completo (snapshot + diff de contratação)
  - [x] Validar todos os eventos do canal
- [x] Validação E2E manual no navegador:
  - [x] Contratação de subagentes reflete no mapa
  - [x] Ciclo ReAct real gera balões, log e notificação
  - [x] `POST /move` move o avatar ao vivo

## 13. Documentação e Polish

- [x] Capturas de tela durante a validação
- [x] Guia de uso para usuário final (`frontend/README.md`)
- [x] Comentários no código-chave (apenas o que o código não mostra)
- [x] README do frontend
- [x] Atualizar `ARCHITECTURE.md` com a seção 4.9 e os ADRs 008–011

---

## Dependências

```
← Fase 3 (Observabilidade) [CONCLUÍDA]
Fase 4 (Interface 2D) [CONCLUÍDA]
= PRODUTO FINAL PRONTO =
```
