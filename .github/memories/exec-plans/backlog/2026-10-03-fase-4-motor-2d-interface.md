# Plano de Implementação: Fase 4 - Motor 2D e Interface

**Objetivo:** Criar a visualização interativa 2D top-down do escritório virtual com avatares de agentes, balões de diálogo, painel lateral de raio-X cognitivo e sincronização em tempo real via WebSocket.

**Status:** Planejado

**Bloqueante:** Fase 3 (Transparência e Observabilidade) deve estar 100% concluída

**Prazo Estimado:** ~3 semanas

---

## 1. Scaffolding do Frontend

- [ ] Criar estrutura de projeto `frontend/`:
  - [ ] Setup inicial (React/Vue + TypeScript)
  - [ ] Configurar empacotador (Vite)
  - [ ] Setup de testes (Jest/Vitest)
- [ ] Configurar ambiente de desenvolvimento:
  - [ ] ESLint e Prettier
  - [ ] Docker compose build para frontend
  - [ ] Hot reload durante desenvolvimento
- [ ] Criar estrutura de pastas:
  - [ ] `components/` - componentes reutilizáveis
  - [ ] `views/` - páginas principais
  - [ ] `services/` - chamadas de API
  - [ ] `types/` - tipos TypeScript
  - [ ] `styles/` - temas e CSS

## 2. Motor 2D e Canvas

- [ ] Escolher engine 2D adequada:
  - [ ] Opção 1: Babylon.js (mais pesado, 3D completo)
  - [ ] Opção 2: Phaser 3 (game engine, ideal para pixel art)
  - [ ] Opção 3: PixiJS (renderizador WebGL leve)
  - [ ] Opção 4: Canvas 2D vanilla (mais controle, menos abstração)
- [ ] Implementar renderizador do mapa:
  - [ ] Mapa base estilo pixel-art / 16-bits
  - [ ] Grid de posições (para movimento dos agentes)
  - [ ] Zoom e pan do mapa
  - [ ] Camadas (fundo, agentes, UI)
- [ ] Otimizações:
  - [ ] Renderização apenas do viewport visível
  - [ ] Batch rendering de múltiplos agentes
  - [ ] Throttling de atualizações

## 3. Avatares e Animações

- [ ] Criar ou integrar sprites de agentes:
  - [ ] Avatares dos 5 Chiefs (CEO, CTO, CMO, CFO, RA)
  - [ ] Template de avatar para subagentes
  - [ ] Estados: idle, thinking, working, celebrating, error
- [ ] Implementar movimento:
  - [ ] Pathfinding (A* ou simpler straight-line)
  - [ ] Suavização de movimento (lerp/easing)
  - [ ] Animação de caminhada
- [ ] Implementar animações de estado:
  - [ ] Balão de pensamento acima da cabeça
  - [ ] Ícone de "trabalhando" (spinning wheel, piscada, etc.)
  - [ ] Indicador de progresso
  - [ ] Partículas para celebração de conclusão

## 4. Ambientes Virtuais (Escritório)

- [ ] Desenhar layout do escritório:
  - [ ] Mesas para cada Chief
  - [ ] Estações de trabalho para subagentes
  - [ ] Sala de reunião isolada
  - [ ] Área de "bench" (espera por contratação)
- [ ] Implementar pontos de interesse (hotspots):
  - [ ] Cliques levam agentes para locais
  - [ ] Visualização de status em local
  - [ ] Interações contextuais

## 5. Balões de Diálogo e Comunicação

- [ ] Sistema de chat bubbles:
  - [ ] Balões acima de agentes
  - [ ] Fila de mensagens (FIFO)
  - [ ] Auto-dismiss após tempo ou interação
- [ ] Diálogos estruturados:
  - [ ] Requisição de contratação (RA ← Chief)
  - [ ] Decisão de contratação (RA → Chief)
  - [ ] Conclusão de tarefa (Subagente → Chief)
- [ ] Log de comunicações:
  - [ ] Janela de chat geral (todas as conversas)
  - [ ] Filtro por agente
  - [ ] Timestamp de cada mensagem

## 6. Painel Lateral do Raio-X Cognitivo

- [ ] UI do painel lateral:
  - [ ] Aba com nome do agente selecionado
  - [ ] Tabs: Info, Reasoning Flow, History
- [ ] Aba "Info":
  - [ ] Nome, função, modelo LLM utilizado
  - [ ] Status atual (idle, thinking, working)
  - [ ] Tokens consumidos
  - [ ] Tempo decorrido na tarefa atual
- [ ] Aba "Reasoning Flow":
  - [ ] Fluxograma interativo do ReAct
  - [ ] Nodes: [Pensamento], [Ferramenta], [Observação], [Conclusão]
  - [ ] Expandir/colapsar nodes
  - [ ] Copiar conteúdo de cada node
  - [ ] Timeline horizontal ou vertical
- [ ] Aba "History":
  - [ ] Últimas 10 tarefas do agente
  - [ ] Duração, status, modelo
  - [ ] Clique para ver reasoning histórico

## 7. Sincronização em Tempo Real (WebSocket)

- [ ] Implementar cliente WebSocket:
  - [ ] Conexão para `/ws/game-state`
  - [ ] Reconexão automática com backoff
  - [ ] Heartbeat para manter conexão viva
- [ ] Tipos de eventos sincronizados:
  - [ ] Movimento de agente → atualiza posição
  - [ ] Novo agente → adiciona ao canvas
  - [ ] Agente saiu → remove do canvas
  - [ ] Nova mensagem → mostra chat bubble
  - [ ] Novo reasoning step → atualiza painel lateral
  - [ ] Status do agente mudou → atualiza visual
- [ ] Gerenciador de estado cliente:
  - [ ] Redux, Pinia, ou Context API
  - [ ] Sincronizar estado do backend
  - [ ] Otimista updates quando possível

## 8. Interatividade e Controles

- [ ] Clique em agente:
  - [ ] Seleciona agente
  - [ ] Abre painel lateral
  - [ ] Destaca agente no mapa
- [ ] Duplo clique em agente:
  - [ ] Foca câmera no agente
  - [ ] Expande painel lateral em tela inteira
- [ ] Botões de controle:
  - [ ] Play/Pause da simulação
  - [ ] Speed control (1x, 2x, 4x)
  - [ ] Reset de estado
  - [ ] Dark/Light mode
- [ ] Atalhos de teclado:
  - [ ] ESC: fecha painel lateral
  - [ ] Space: play/pause
  - [ ] Arrow keys: pan mapa
  - [ ] +/-: zoom

## 9. Painel de Monitoramento Global

- [ ] Barra superior com informações:
  - [ ] Hora corporativa simulada
  - [ ] Recursos disponíveis (RAM/VRAM) via "Natureza"
  - [ ] Número de subagentes ativos
  - [ ] Receita/Custo corporativo
- [ ] Notificações:
  - [ ] Alerta quando recurso crítico
  - [ ] Aviso de contratação bloqueada
  - [ ] Celebração de milestone (projeto concluído)
- [ ] Botão de configurações:
  - [ ] Zoom padrão
  - [ ] Volume de som (opcional)
  - [ ] Preferências de tema

## 10. Validação Visual

- [ ] Teste em navegador (Chrome, Firefox)
- [ ] Responsividade (desktop, tablet, mobile)
- [ ] Performance:
  - [ ] 60 FPS mínimo
  - [ ] Latência de WebSocket < 100ms
  - [ ] Suporta 50+ agentes simultâneos
- [ ] Acessibilidade básica:
  - [ ] Contraste adequado
  - [ ] Navegação por teclado
  - [ ] Labels descritivos

## 11. Integração com Backend

- [ ] Endpoints necessários:
  - [ ] `GET /game/state` - estado inicial completo
  - [ ] `GET /agents` - lista de agentes
  - [ ] `GET /agents/{id}/position` - posição
  - [ ] `POST /agents/{id}/move` - mover agente
  - [ ] WebSocket `/ws/game-state` - eventos em tempo real
- [ ] Tratamento de erros:
  - [ ] Desconexão de WebSocket
  - [ ] Falha em chamadas HTTP
  - [ ] Estados inconsistentes

## 12. Testes e Validação

- [ ] Testes unitários:
  - [ ] Componentes React/Vue
  - [ ] Lógica de movimento
  - [ ] Parsing de eventos WebSocket
- [ ] Testes de integração:
  - [ ] Conectar a backend real
  - [ ] Sincronizar estado completo
  - [ ] Validar todos os eventos
- [ ] Testes de performance:
  - [ ] 50+ agentes simultâneos
  - [ ] 1000+ mensagens em chat
  - [ ] Histórico de 100+ reasoning flows

## 13. Documentação e Polish

- [ ] Screenshots e demos
- [ ] Guia de uso para usuário final
- [ ] Comentários no código-chave
- [ ] README do frontend
- [ ] Atualizar `ARCHITECTURE.md` com diagrama da UI

---

## Dependências

```
← Fase 3 (Observabilidade) [BLOQUEANTE]
Fase 4 (Interface 2D)
= PRODUTO FINAL PRONTO =
```
