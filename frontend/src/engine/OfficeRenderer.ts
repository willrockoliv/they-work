/**
 * Renderizador do escritório.
 *
 * O React é dono do estado; o Pixi só desenha (ADR-008). `sync()` recebe um
 * snapshot imutável e reconcilia os sprites — nenhum dado de domínio mora aqui.
 */

import { Application, Container, Graphics, Sprite, Text, TextStyle } from 'pixi.js';

import type { Bubble, SimulationSpeed } from '@/store/gameStore';
import type { GameAgent, OfficeLayout } from '@/types/game';

import { AgentSprite } from './AgentSprite';
import {
  clampFocus,
  fitZoom,
  zoomForRect,
  isWithin,
  layoutCenter,
  pixelToTile,
  visibleTileBounds,
  type Point,
} from './layoutMath';
import { ROOM_COLORS, THEMES, type ThemeName } from './palette';
import { darken, lighten, TextureFactory } from './textures';

export interface RendererCallbacks {
  onSelectAgent: (agentId: string | null) => void;
  onHotspot: (roomId: string, center: Point) => void;
  onPan: (deltaTilesX: number, deltaTilesY: number) => void;
  onZoom: (factor: number) => void;
  /** Arrastar com o botão esquerdo: centro (em tiles) e zoom que enquadram a área escolhida. */
  onZoomArea: (center: Point, zoom: number) => void;
  /** Enquadramento calculado pelo renderizador quando a câmera está em modo automático. */
  onFit: (zoom: number, center: Point) => void;
}

export interface SyncInput {
  agents: GameAgent[];
  bubbles: Record<string, Bubble>;
  selectedAgentId: string | null;
  paused: boolean;
  speed: SimulationSpeed;
  zoom: number;
  focus: Point | null;
  theme: ThemeName;
}

/** Deslocamento mínimo, em pixels, para o gesto deixar de ser clique. */
const DRAG_THRESHOLD_PX = 5;
/** Menor lado da área selecionada para zoom; áreas menores são descartadas. */
const MIN_SELECTION_PX = 8;

const ROOM_LABEL_STYLE = new TextStyle({
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  fontSize: 12,
  fill: THEMES.dark.textMuted,
  letterSpacing: 1.5,
});

export class OfficeRenderer {
  private app: Application | null = null;
  private textures: TextureFactory | null = null;
  private layout: OfficeLayout | null = null;

  private readonly world = new Container();
  private readonly floorLayer = new Graphics();
  private readonly furnitureLayer = new Container();
  private readonly agentLayer = new Container();
  private readonly labelLayer = new Container();

  private readonly sprites = new Map<string, AgentSprite>();
  private paused = false;
  private speed: SimulationSpeed = 1;
  private theme: ThemeName = 'dark';
  private zoom = 1;
  private focus: Point = { x: 0, y: 0 };
  /** Botão do ponteiro em uso: 0 seleciona área para zoom, 1 (meio) arrasta o mapa. */
  private dragButton: number | null = null;
  private dragStart: Point | null = null;
  private dragLast: Point | null = null;
  /** Passa a `true` quando o gesto ultrapassa o limiar; suprime os `pointertap` do gesto. */
  private dragMoved = false;
  private readonly selection = new Graphics();
  private detachInput: (() => void) | null = null;

  constructor(private readonly callbacks: RendererCallbacks) {
    this.agentLayer.sortableChildren = true;
    this.world.addChild(this.floorLayer, this.furnitureLayer, this.agentLayer, this.labelLayer);
  }

  get ready(): boolean {
    return this.app !== null;
  }

  async mount(element: HTMLElement): Promise<void> {
    if (this.app) return;
    const app = new Application();
    await app.init({
      background: THEMES[this.theme].background,
      antialias: true,
      resizeTo: element,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      preference: 'webgl',
    });
    element.appendChild(app.canvas);
    app.canvas.setAttribute('aria-label', 'Mapa do escritório virtual');
    app.canvas.setAttribute('role', 'img');

    app.stage.addChild(this.world);
    app.stage.eventMode = 'static';
    app.stage.hitArea = app.screen;

    this.app = app;
    this.textures = new TextureFactory(app.renderer);
    this.attachInput(app);
    app.ticker.add((ticker) => this.tick(ticker.deltaMS));
  }

  setLayout(layout: OfficeLayout): void {
    if (!this.app || !this.textures) return;
    this.layout = layout;
    this.drawFloor(layout);
    this.drawFurniture(layout);
    this.drawLabels(layout);
    this.focus = layoutCenter(layout);
    this.zoom = fitZoom(layout, this.app.screen);
  }

  sync(input: SyncInput): void {
    this.paused = input.paused;
    this.speed = input.speed;

    const layout = this.layout;
    if (!layout || !this.textures) return;

    if (input.theme !== this.theme) {
      this.theme = input.theme;
      this.applyTheme();
    }

    if (input.focus) {
      this.zoom = input.zoom;
      this.focus = input.focus;
    } else if (this.app) {
      // Sem foco definido, o escritório inteiro é enquadrado e o valor sobe para a UI.
      const zoom = fitZoom(layout, this.app.screen);
      const center = layoutCenter(layout);
      this.zoom = zoom;
      this.focus = center;
      this.callbacks.onFit(zoom, center);
    }

    const seen = new Set<string>();
    for (const agent of input.agents) {
      seen.add(agent.id);
      let sprite = this.sprites.get(agent.id);
      if (!sprite) {
        sprite = new AgentSprite(agent, layout.tile_size, this.textures);
        sprite.on('pointertap', (event) => {
          event.stopPropagation();
          if (this.dragMoved) return;
          this.callbacks.onSelectAgent(agent.id);
        });
        this.sprites.set(agent.id, sprite);
        this.agentLayer.addChild(sprite);
      } else {
        sprite.apply(agent);
      }
      sprite.applyBubble(input.bubbles[agent.id]);
      sprite.setSelected(agent.id === input.selectedAgentId);
      sprite.setTheme(this.theme);
    }

    for (const [id, sprite] of this.sprites) {
      if (seen.has(id)) continue;
      sprite.destroy();
      this.sprites.delete(id);
    }
  }

  /** Enquadra a câmera num ponto do mundo. */
  focusOn(point: Point): void {
    this.focus = point;
  }

  destroy(): void {
    this.detachInput?.();
    this.detachInput = null;
    for (const sprite of this.sprites.values()) sprite.destroy();
    this.sprites.clear();
    this.textures?.destroy();
    this.textures = null;
    this.app?.destroy(true, { children: true });
    this.app = null;
  }

  // --- Loop ---------------------------------------------------------------

  private tick(deltaMs: number): void {
    const app = this.app;
    const layout = this.layout;
    if (!app || !layout) return;

    const focus = clampFocus(this.focus, layout, app.screen, this.zoom);
    this.world.scale.set(this.zoom);
    this.world.pivot.set(focus.x * layout.tile_size, focus.y * layout.tile_size);
    this.world.position.set(app.screen.width / 2, app.screen.height / 2);

    const bounds = visibleTileBounds(focus, layout, app.screen, this.zoom);
    for (const sprite of this.sprites.values()) {
      // Culling: fora do viewport o sprite nem entra na fila de render.
      sprite.renderable = isWithin(sprite.tilePosition, bounds);
      sprite.setDetailLevel(this.zoom);
      if (!this.paused) sprite.update(deltaMs, this.speed);
    }
  }

  // --- Camadas estáticas --------------------------------------------------

  private drawFloor(layout: OfficeLayout): void {
    const tile = layout.tile_size;
    const surface = THEMES[this.theme];
    const g = this.floorLayer;
    g.clear();
    g.rect(0, 0, layout.columns * tile, layout.rows * tile).fill({ color: surface.floor });

    // Xadrez discreto: dá escala ao piso sem poluir.
    for (let row = 0; row < layout.rows; row += 1) {
      for (let column = 0; column < layout.columns; column += 1) {
        if ((row + column) % 2 === 0) continue;
        g.rect(column * tile, row * tile, tile, tile).fill({
          color: surface.floorAlt,
          alpha: 0.5,
        });
      }
    }

    for (const room of layout.rooms) {
      const accent = ROOM_COLORS[room.kind].accent;
      const box = [room.x * tile, room.y * tile, room.width * tile, room.height * tile, 8] as const;
      g.roundRect(...box).fill({ color: surface.roomFill });
      // O acento do cômodo tinge o piso dele em vez de ter uma cor fixa por tema.
      g.roundRect(...box).fill({ color: accent, alpha: surface.roomTint });
      g.roundRect(...box).stroke({ width: 3, color: accent, alpha: 0.85 });
    }

    g.rect(0, 0, layout.columns * tile, layout.rows * tile).stroke({
      width: 4,
      color: surface.wall,
    });
  }

  private drawFurniture(layout: OfficeLayout): void {
    const factory = this.textures;
    if (!factory) return;
    this.furnitureLayer.removeChildren().forEach((child) => child.destroy());

    const tile = layout.tile_size;
    for (const seat of layout.seats) {
      const kind = seat.kind === 'CHIEF' || seat.kind === 'WORKSTATION' ? 'desk' : 'chair';
      const width = kind === 'desk' ? tile * 2 : tile;
      const height = kind === 'desk' ? tile * 1.2 : tile;
      const sprite = new Sprite(factory.furniture(kind, width, height));
      sprite.anchor.set(0.5, 0.5);
      sprite.position.set((seat.x + 0.5) * tile, (seat.y + 1.1) * tile);
      sprite.alpha = 0.95;
      this.furnitureLayer.addChild(sprite);
    }

    const serverRoom = layout.rooms.find((room) => room.kind === 'SERVER');
    if (serverRoom) {
      for (let i = 0; i < 3; i += 1) {
        const rack = new Sprite(factory.furniture('rack', tile * 1.2, tile * 2.4));
        rack.anchor.set(0.5, 0.5);
        rack.position.set((serverRoom.x + 2 + i * 2.5) * tile, (serverRoom.y + 3) * tile);
        this.furnitureLayer.addChild(rack);
      }
    }
  }

  private drawLabels(layout: OfficeLayout): void {
    this.labelLayer.removeChildren().forEach((child) => child.destroy());
    const tile = layout.tile_size;

    for (const hotspot of layout.hotspots) {
      const room = layout.rooms.find((candidate) => candidate.id === hotspot.room_id);
      const label = new Text({
        text: hotspot.label.toUpperCase(),
        style: ROOM_LABEL_STYLE.clone(),
      });
      label.anchor.set(0.5, 0.5);
      label.position.set(hotspot.x * tile, (room ? room.y + 0.6 : hotspot.y) * tile);
      label.eventMode = 'static';
      label.cursor = 'zoom-in';
      label.on('pointertap', (event) => {
        event.stopPropagation();
        if (this.dragMoved) return;
        this.callbacks.onHotspot(hotspot.room_id, { x: hotspot.x, y: hotspot.y });
      });
      if (room) {
        const accent = ROOM_COLORS[room.kind].accent;
        label.style.fill = this.theme === 'dark' ? lighten(accent, 0.45) : darken(accent, 0.3);
      }
      this.labelLayer.addChild(label);
    }
  }

  /** Repinta o que depende do tema; o mobiliário e os avatares mantêm suas cores. */
  private applyTheme(): void {
    const layout = this.layout;
    if (!layout || !this.app) return;
    this.app.renderer.background.color = THEMES[this.theme].background;
    this.drawFloor(layout);
    this.drawLabels(layout);
  }

  // --- Entrada ------------------------------------------------------------

  private attachInput(app: Application): void {
    const canvas = app.canvas;
    app.stage.addChild(this.selection);

    const canvasPoint = (event: PointerEvent): Point => {
      const box = canvas.getBoundingClientRect();
      return { x: event.clientX - box.left, y: event.clientY - box.top };
    };

    const onWheel = (event: WheelEvent): void => {
      event.preventDefault();
      this.callbacks.onZoom(event.deltaY < 0 ? 1.12 : 1 / 1.12);
    };

    const onPointerDown = (event: PointerEvent): void => {
      if (event.button !== 0 && event.button !== 1) return;
      // Evita o auto-scroll do navegador ao clicar com o botão do meio.
      if (event.button === 1) event.preventDefault();
      const point = canvasPoint(event);
      this.dragButton = event.button;
      this.dragStart = point;
      this.dragLast = point;
      this.dragMoved = false;
      canvas.setPointerCapture(event.pointerId);
    };

    const onPointerMove = (event: PointerEvent): void => {
      if (this.dragButton === null || !this.dragStart || !this.dragLast) return;
      const point = canvasPoint(event);

      if (this.dragButton === 1) {
        this.dragMoved = true;
        this.panBy(this.dragLast, point);
        this.dragLast = point;
        return;
      }

      if (!this.dragMoved) {
        const travelled = Math.hypot(point.x - this.dragStart.x, point.y - this.dragStart.y);
        if (travelled < DRAG_THRESHOLD_PX) return;
        this.dragMoved = true;
      }
      this.drawSelection(this.dragStart, point);
    };

    const endGesture = (event: PointerEvent, commit: boolean): void => {
      const start = this.dragStart;
      const button = this.dragButton;
      const moved = this.dragMoved;
      this.dragButton = null;
      this.dragStart = null;
      this.dragLast = null;
      this.selection.clear();
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      if (commit && button === 0 && moved && start) this.zoomToArea(start, canvasPoint(event));
    };

    const onPointerUp = (event: PointerEvent): void => endGesture(event, true);
    const onPointerCancel = (event: PointerEvent): void => endGesture(event, false);

    // Clique no vazio limpa a seleção; clique no agente é tratado pelo sprite.
    // Um arrasto nunca conta como clique.
    const onStageTap = (): void => {
      if (this.dragMoved) return;
      this.callbacks.onSelectAgent(null);
    };

    canvas.addEventListener('wheel', onWheel, { passive: false });
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerCancel);
    app.stage.on('pointertap', onStageTap);

    this.detachInput = () => {
      canvas.removeEventListener('wheel', onWheel);
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerCancel);
      app.stage.off('pointertap', onStageTap);
    };
  }

  /** Pan do mapa pelo deslocamento de tela entre dois pontos. */
  private panBy(from: Point, to: Point): void {
    if (!this.layout) return;
    const scale = this.zoom * this.layout.tile_size;
    const dx = (from.x - to.x) / scale;
    const dy = (from.y - to.y) / scale;
    if (dx !== 0 || dy !== 0) this.callbacks.onPan(dx, dy);
  }

  /** Retângulo de seleção desenhado em coordenadas de tela, sobre o mapa. */
  private drawSelection(from: Point, to: Point): void {
    const g = this.selection;
    g.clear();
    const x = Math.min(from.x, to.x);
    const y = Math.min(from.y, to.y);
    const width = Math.abs(to.x - from.x);
    const height = Math.abs(to.y - from.y);
    const color = THEMES[this.theme].textMuted;
    g.rect(x, y, width, height).fill({ color, alpha: 0.12 });
    g.rect(x, y, width, height).stroke({ width: 2, color, alpha: 0.9 });
  }

  /** Zoom e centro para a área arrastada; áreas pequenas são ignoradas. */
  private zoomToArea(from: Point, to: Point): void {
    const app = this.app;
    const layout = this.layout;
    if (!app || !layout) return;
    const width = Math.abs(to.x - from.x);
    const height = Math.abs(to.y - from.y);
    if (width < MIN_SELECTION_PX || height < MIN_SELECTION_PX) return;

    const rect = {
      x: Math.min(from.x, to.x),
      y: Math.min(from.y, to.y),
      width,
      height,
    };
    const zoom = zoomForRect(this.zoom, rect, app.screen);
    // Centro da área em coordenadas do mundo (antes da mudança de zoom), em tiles fracionários.
    const world = this.world.toLocal({
      x: rect.x + rect.width / 2,
      y: rect.y + rect.height / 2,
    });
    this.callbacks.onZoomArea(
      { x: world.x / layout.tile_size, y: world.y / layout.tile_size },
      zoom,
    );
  }

  /** Converte um ponto da tela em tile do mundo (usado por testes e atalhos). */
  screenToTile(screen: Point): Point | null {
    const layout = this.layout;
    const app = this.app;
    if (!layout || !app) return null;
    const world = this.world.toLocal({ x: screen.x, y: screen.y });
    return pixelToTile(world, layout.tile_size);
  }
}
