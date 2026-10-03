# Progresso: Fase 4 - Motor 2D e Interface

**Plano:** [2026-10-03-fase-4-motor-2d-interface.md](../completed/2026-10-03-fase-4-motor-2d-interface.md)
**Status:** ✅ Concluído
**Início:** 2026-10-03 · **Conclusão:** 2026-10-03

---

## Entregas

### Backend (sem migração nova)

| Módulo | O que faz |
|--------|-----------|
| `services/office_map.py` | Planta de 40×24 tiles (5 cômodos, 31 postos), lotação determinística em memória, relógio corporativo |
| `services/game_service.py` | Projeção de leitura do mundo + `diff()` entre snapshots |
| `schemas/game.py` | 11 schemas do mundo 2D |
| `routes/game.py` | `GET /game/map`, `GET /game/state`, `GET /agents/{id}/position`, `POST /agents/{id}/move`, `POST /agents/{id}/recall` |
| `routes/ws.py` | Novo canal `WS /ws/game-state` |
| `config/settings.py` | `cors_allow_origins`, `game_tick_seconds`, `game_walk_tiles_per_second` |

### Frontend (`frontend/`, 31 arquivos)

- Vite 8 + React 19 + TypeScript 5.9 + PixiJS 8 + Zustand 5, tudo com versão fixada.
- `engine/` — `OfficeRenderer` (camadas, câmera, culling, input), `AgentSprite`
  (caminhada, respiração, giro, shake, confetes, barra de progresso), `ChatBubble`
  (fila FIFO com auto-dismiss), `textures.ts` (sprites procedurais), `layoutMath.ts`.
- `store/` — `gameStore` (reducer de todos os eventos do canal, pausa com represamento,
  notificações) e `uiStore` (seleção, abas, câmera, tema).
- `services/` — cliente HTTP tipado com `ApiError` e `GameSocket` com backoff + watchdog.
- `components/` — `TopBar`, `Controls`, `OfficeCanvas`, `SidePanel` (3 abas), `ChatLog`,
  `Notifications`.
- Container próprio em `docker-compose.yml`, só na rede `edge`, com proxy de `/api` e `/ws`.

### Testes

| Suíte | Resultado |
|-------|-----------|
| Backend (`pytest`) | **286 passando** (+31 da Fase 4: `test_office_map.py`, `test_api_fase4.py`) |
| Backend (`ruff`, `mypy --strict`) | limpos |
| Frontend (`vitest`) | **69 passando** em 11 arquivos — 85% de cobertura |
| Frontend (`tsc --noEmit`, `eslint`, `prettier --check`) | limpos |
| Frontend (`vite build`) | 3 chunks, sem avisos |

### Validação E2E no navegador

1. Stack completa no ar (`docker compose up --build -d`): 5 containers saudáveis.
2. `POST /agents/chiefs/init` → os 5 Chiefs aparecem nas mesas da diretoria.
3. Dois `POST /hiring/requests` → 4 subagentes lotados em `station-0..3` ao vivo,
   via evento `agent.joined`.
4. `POST /agents/{id}/reasoning/run` com o motor ReAct real → balão de fala sobre o
   avatar, 6 linhas no log de comunicações e notificação "Entrega concluída".
5. Clique no CEO → painel lateral com modelo, RAM, posto e tarefa atual.
6. Aba "Raciocínio" → fluxograma completo `Tarefa → Pensamento → Ferramenta →
   Observação →(↻ reavalia)→ Pensamento → Conclusão`, com botão de copiar por nó.
7. `POST /agents/{id}/move` → avatar caminha até a sala de reunião em tempo real.

---

## Decisões de arquitetura

### ADR-008 — PixiJS como motor 2D (em vez de Babylon.js / Phaser 3 / Canvas puro)

**Contexto:** o plano listava 4 opções. O escritório é um mapa top-down pequeno
(40×24 tiles), com poucas dezenas de sprites e nenhuma física.

**Decisão:** **PixiJS 8**.

- Babylon.js — motor 3D completo; peso e API desproporcionais ao problema.
- Phaser 3 — traz loop de jogo, física, cenas e input próprios; duplicaria o
  gerenciamento de estado que já vive no React/Zustand.
- Canvas 2D puro — exigiria reimplementar batching, culling e transform stack.
- **PixiJS** — renderizador WebGL fino: `Container`/`Graphics`/`Sprite`, sem opinião
  sobre arquitetura de jogo. O React continua dono do estado; o Pixi só desenha.

**Consequências:** o loop de render é um `ticker` do Pixi que lê um snapshot
imutável vindo do Zustand. Nenhum estado de domínio vive dentro do canvas — o que
também torna a lógica testável sem WebGL (`engine/layoutMath.ts`).

### ADR-009 — Sprites procedurais em vez de assets binários

**Contexto:** o repositório roda 100% offline e não deve carregar binários de arte.

**Decisão:** todos os avatares, móveis e ícones são desenhados com `Graphics` em
tempo de execução a partir de uma paleta de 16 bits (`engine/palette.ts`) e
cacheados como texturas (`engine/textures.ts`).

**Consequências:** nenhum download, nenhum `.png` versionado, trocar de tema é
apenas trocar a paleta — `THEMES.dark`/`THEMES.light` repintam piso, cômodos,
rótulos e balões sem recriar sprite nenhum. O custo é que a arte é geométrica
("16-bit minimalista"), não pixel-art desenhada à mão.

### ADR-010 — Posições do escritório ficam em memória, não no banco

**Contexto:** o plano pedia `GET /agents/{id}/position` e `POST /agents/{id}/move`,
mas nenhum modelo ORM tem coordenadas (verificado nas Fases 1–3).

**Decisão:** `services/office_map.py` mantém um registro em memória, por processo,
com a mesma disciplina do `reasoning_broker` (lock + instância via `lru_cache`).
A atribuição de posto é **determinística**: o Chief sempre senta na mesa do seu
cargo; o subagente recebe a estação livre de menor índice, ordenado por `created_at`.

**Consequências:** nenhuma migração nova na Fase 4. Reiniciar o backend recoloca
todo mundo no lugar canônico — aceitável para um sandbox e desejável para testes
determinísticos. Movimentos manuais (`POST /move`) são efêmeros e marcados com
`manual: true`, para que o recálculo de lotação não os arraste de volta.

### ADR-011 — `/ws/game-state` reaproveita o barramento da Fase 3

**Contexto:** o frontend precisa de um canal único com tudo que acontece.

**Decisão:** o canal reusa o `ReasoningBroker` global. Eventos cognitivos
(`session.started` / `step` / `session.finished`) passam adiante sem tradução, e
os eventos de mundo (`agent.moved`) são publicados no mesmo barramento.
Mudanças que **não** passam por evento (contratação, demissão, pressão da
Natureza) são detectadas por *diff* de snapshot a cada tick do servidor.

**Consequências:** nenhum serviço da Fase 2/3 precisou ser alterado para emitir
eventos. O preço é a latência de um tick (`GAME_TICK_SECONDS`, padrão 2 s) para
`agent.joined` / `agent.left` / `agent.status` / `nature.status`.

---

## Aprendizados

### Ecossistema Node

- `typescript-eslint@8.71.0` declara peer `typescript >=4.8.4 <6.1.0`. O `latest`
  do TypeScript é `7.0.2`, que **quebraria** o `npm install`. O projeto fixa
  `typescript@5.9.3` — a última linha coberta pelo linter.
- `@vitejs/plugin-react@6.1.1` lista `oxc-transform-react`, `@rolldown/plugin-babel`
  e `babel-plugin-react-compiler` como peers **opcionais**; não precisam ser instalados.
- Vite 8 usa rolldown: `build.rollupOptions.output.manualChunks` não existe mais.
  O equivalente é `build.rolldownOptions.output.codeSplitting.groups`
  (`advancedChunks` já está deprecado).
- `defineConfig` precisa vir de `vitest/config`, não de `vite`, para que a chave
  `test` seja tipada.
- Resolver versões pelo registro **dentro de um container** (`docker run node npm view`)
  mantém a regra de nunca rodar npm no host.

### React / Zustand

- Seletor que devolve literal novo (`state.liveSteps[id] ?? []`) estoura o
  `useSyncExternalStore` com *"Maximum update depth exceeded"*. A correção é uma
  referência estável no escopo do módulo (`const NO_STEPS = []`). Há teste de
  regressão em `components/ReasoningFlowTab.test.tsx`.
- A regra `react-hooks/set-state-in-effect` do ESLint 10 proíbe `setState` síncrono
  no corpo de um efeito. O padrão que resolve: guardar o resultado **com a chave do
  pedido** (`{ key, data, error }`) e derivar "carregando" de `result.key !== key`.
- `vi.mock` é içado para o topo do arquivo — a fábrica não pode fechar sobre
  variáveis do módulo, senão dá `Cannot access 'X' before initialization`.
- Propriedades `name` e `label` colidem com `Container` do Pixi ao estender a classe;
  renomear para `nameLabel` / `content` evita o `TS2416` e o `TS4114`.

### Câmera e canvas

- Quem calcula o enquadramento inicial é o renderizador (só ele conhece o tamanho do
  viewport), mas quem é dono da câmera é o store. A ponte é um callback `onFit` que
  **só** aplica enquanto `camera.focus === null` — do contrário o zoom do usuário
  seria sobrescrito a cada quadro.
- `clampFocus` precisa travar o foco no centro quando o mundo cabe na tela; sem isso
  a cena "escapa" ao arrastar.

### Backend

- `ReasoningTracer` expõe `complete()` / `fail()` / `cancel()`, não `finish()`.
- A sessão do SQLAlchemy vive enquanto o WebSocket viver. `session.expire_all()` a
  cada tick é o que faz o próximo `SELECT` enxergar o que outras requisições
  commitaram — `rollback()` descartaria dados em testes que não commitam.
- A Natureza reporta `vram_limit_mb: 0` quando não há GPU, mesmo com
  `NATURE_VRAM_LIMIT_MB=4096`. A UI precisa tratar isso ("sem GPU") em vez de
  mostrar `0 / 0 MB`.

---

## Débitos técnicos

| # | Débito | Impacto | Mitigação futura |
|---|--------|---------|------------------|
| 1 | Posições não persistem entre reinícios do backend | Baixo — layout é determinístico | Coluna `seat_id`/`x`/`y` em `agents` se a persistência passar a importar |
| 2 | `agent.joined`/`agent.left` chegam com atraso de até 1 tick | Baixo | Publicar evento direto de `ra_service` |
| 3 | Pathfinding é linha reta com desvio em L, não A\* | Baixo — o escritório é aberto | Só vale implementar se houver obstáculos reais |
| 4 | `/ws/game-state` roda consultas SQLAlchemy síncronas no event loop | Médio | Mesmo padrão já usado em `/ws/agents/{id}/reasoning`; mover o snapshot para `asyncio.to_thread` |
| 5 | O chunk do Pixi tem 546 kB (156 kB gzip) | Baixo | `import()` dinâmico do `OfficeRenderer` se o tempo de primeira pintura virar problema |
| 6 | Em `StrictMode`, o duplo-mount do efeito gera um aviso de "WebSocket closed before established" | Nenhum em produção | Inerente ao `StrictMode`; o socket reconecta sozinho |
| 7 | A velocidade (1x/2x/4x) só acelera a animação local, não a simulação do backend | Médio | Expor `GAME_TICK_SECONDS` por conexão WebSocket |
| 8 | Sem testes de carga com 50+ agentes simultâneos | Médio | O culling e o cache de texturas estão prontos; falta medir |
