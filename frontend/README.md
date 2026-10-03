# Frontend 2D — TheyWork

Interface top-down do escritório virtual: avatares dos agentes, balões de fala,
raio-X cognitivo e sincronização em tempo real com o backend.

## Stack

| Peça   | Escolha                    | Por quê                                                     |
| ------ | -------------------------- | ----------------------------------------------------------- |
| Build  | Vite 8                     | dev server com HMR e build por rolldown                     |
| UI     | React 19 + TypeScript 5.9  | o estado do mundo vive em componentes, não no canvas        |
| Canvas | PixiJS 8                   | renderizador WebGL fino, sem loop de jogo próprio (ADR-008) |
| Estado | Zustand 5                  | duas lojas: mundo (`gameStore`) e interface (`uiStore`)     |
| Testes | Vitest 5 + Testing Library | jsdom; nenhum teste abre WebGL nem rede                     |

Nenhum asset binário é versionado: avatares e móveis são desenhados com
`Graphics` e cacheados como texturas (ADR-009, `src/engine/textures.ts`). O tema
claro/escuro troca a paleta do canvas junto com a do HTML (`src/engine/palette.ts`).

## Execução

O frontend **sempre** roda em container:

```bash
docker compose up --build -d          # sobe toda a stack
docker compose logs -f frontend       # acompanha o dev server
```

A UI fica em <http://127.0.0.1:3000>. O dev server do Vite faz proxy de `/api` e
`/ws` para o backend, então navegador e API compartilham a origem — sem CORS e
sem porta fixa no código.

## Comandos

```bash
docker compose exec frontend npm run type-check   # tsc --noEmit
docker compose exec frontend npm run lint         # ESLint 10
docker compose exec frontend npm run format       # Prettier
docker compose exec frontend npm run test         # Vitest
docker compose exec frontend npm run build        # tsc + vite build
```

## Estrutura

```text
src/
├── components/   # TopBar, OfficeCanvas, SidePanel (+ abas), ChatLog, Notifications, Controls
├── engine/       # PixiJS: OfficeRenderer, AgentSprite, ChatBubble, texturas, paleta, matemática
├── hooks/        # useGameSocket (HTTP + WS), useKeyboardShortcuts
├── services/     # config de origem, cliente HTTP tipado, cliente WebSocket com backoff
├── store/        # gameStore (mundo) e uiStore (seleção, câmera, tema)
├── types/        # espelho tipado de backend/app/schemas
└── test/         # setup do jsdom e fixtures
```

## Fluxo de dados

```text
GET /game/state ──┐
                  ├──> gameStore ──> OfficeCanvas ──> OfficeRenderer ──> PixiJS
WS /ws-game-state ┘                └──> TopBar · SidePanel · ChatLog · Notifications
```

`gameStore.applyEvent` é a única porta de entrada: todo evento do canal
(`game.snapshot`, `game.tick`, `agent.*`, `session.*`, `step`, `nature.status`)
passa por ela. `revision` incrementa a cada evento aplicado e é o gatilho de
reconciliação do canvas.

## Atalhos de teclado

| Tecla     | Ação                                                        |
| --------- | ----------------------------------------------------------- |
| `Espaço`  | pausa / retoma (eventos ficam represados, não são perdidos) |
| `Esc`     | fecha o painel lateral                                      |
| `← ↑ → ↓` | move a câmera                                               |
| `+` / `-` | zoom                                                        |
| `0`       | reenquadra o escritório                                     |
| `C`       | mostra / esconde o log de comunicações                      |

Mouse: roda do mouse dá zoom, arrastar faz pan, clique num agente abre o
raio-X, clique no nome de um cômodo enquadra a câmera nele.
