/** Avatar de um agente: movimento, animação de estado e balão de fala. */

import { Container, Graphics, Sprite, Text, TextStyle } from 'pixi.js';

import type { Bubble } from '@/store/gameStore';
import type { GameAgent } from '@/types/game';

import { ChatBubble } from './ChatBubble';
import { damp, routeBetween, stepDistance, type Point } from './layoutMath';
import { ACTIVITY_COLORS, ACTIVITY_GLYPHS, PALETTE, THEMES, type ThemeName } from './palette';
import type { TextureFactory } from './textures';

const WALK_TILES_PER_SECOND = 3;
const WALK_FRAME_MS = 180;
const NAME_STYLE = new TextStyle({
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  fontSize: 10,
  fill: THEMES.dark.text,
  align: 'center',
});

export class AgentSprite extends Container {
  readonly agentId: string;

  private readonly body = new Sprite();
  private readonly glyph: Text;
  private readonly nameLabel: Text;
  private readonly statusRing = new Graphics();
  private readonly progress = new Graphics();
  private readonly selection = new Graphics();
  private readonly particles = new Graphics();
  readonly bubble = new ChatBubble();

  private agent: GameAgent;
  private tile: Point;
  private route: Point[] = [];
  private frame: 0 | 1 = 0;
  private frameElapsed = 0;
  private bobElapsed = 0;
  private celebrateMs = 0;
  private shakeMs = 0;
  private lastBubbleAt = 0;

  constructor(
    agent: GameAgent,
    private readonly tileSize: number,
    private readonly textures: TextureFactory,
  ) {
    super();
    this.agentId = agent.id;
    this.agent = agent;
    this.tile = { x: agent.position?.x ?? 0, y: agent.position?.y ?? 0 };

    this.body.anchor.set(0.5, 1);
    this.body.scale.set(tileSize / 32);

    this.glyph = new Text({ text: '', style: { ...NAME_STYLE, fontSize: 14 } });
    this.glyph.anchor.set(0.5, 1);
    this.glyph.position.set(0, -tileSize * 1.15);

    this.nameLabel = new Text({ text: agent.name, style: NAME_STYLE.clone() });
    this.nameLabel.anchor.set(0.5, 0);
    this.nameLabel.position.set(0, 6);

    this.bubble.position.set(0, -tileSize * 1.4);

    this.addChild(
      this.selection,
      this.statusRing,
      this.particles,
      this.body,
      this.glyph,
      this.progress,
      this.nameLabel,
      this.bubble,
    );

    this.eventMode = 'static';
    this.cursor = 'pointer';
    this.apply(agent);
    this.syncPosition(true);
  }

  get tilePosition(): Point {
    return this.tile;
  }

  /** Reaplica os dados do agente; dispara animação quando o estado muda. */
  apply(agent: GameAgent): void {
    const previous = this.agent;
    this.agent = agent;
    this.nameLabel.text = agent.name;

    const isChief = agent.agent_type === 'CHIEF';
    this.body.texture = this.textures.avatar(agent.role, this.frame, isChief);
    this.body.alpha = agent.activity === 'TERMINATED' ? 0.45 : 1;

    if (previous.activity !== agent.activity) {
      if (agent.activity === 'BLOCKED') this.shakeMs = 600;
      if (previous.activity === 'THINKING' && agent.activity === 'IDLE') this.celebrateMs = 900;
    }

    const target = agent.position;
    if (target && (target.target_x !== this.tile.x || target.target_y !== this.tile.y)) {
      this.route = routeBetween(this.tile, { x: target.target_x, y: target.target_y });
    }

    this.drawStatusRing();
    this.drawProgress();
    this.glyph.text = ACTIVITY_GLYPHS[agent.activity];
    this.glyph.style.fill = ACTIVITY_COLORS[agent.activity];
  }

  /** Empurra para o balão a última fala conhecida do agente. */
  applyBubble(bubble: Bubble | undefined): void {
    if (!bubble || bubble.at === this.lastBubbleAt) return;
    this.lastBubbleAt = bubble.at;
    this.bubble.push({ text: bubble.text, kind: bubble.kind });
  }

  setSelected(selected: boolean): void {
    this.selection.clear();
    if (!selected) return;
    this.selection
      .circle(0, -this.tileSize * 0.45, this.tileSize * 0.75)
      .stroke({ width: 2, color: PALETTE.selection, alpha: 0.9 });
    this.selection
      .ellipse(0, 2, this.tileSize * 0.5, this.tileSize * 0.18)
      .stroke({ width: 2, color: PALETTE.selection, alpha: 0.6 });
  }

  /** Em zoom afastado os nomes se sobrepõem e viram ruído: some com eles. */
  setDetailLevel(zoom: number): void {
    this.nameLabel.visible = zoom >= 0.85;
  }

  setTheme(theme: ThemeName): void {
    this.nameLabel.style.fill = THEMES[theme].text;
    this.bubble.setTheme(theme);
  }

  update(deltaMs: number, speed: number): void {
    this.advanceRoute(deltaMs, speed);
    this.animate(deltaMs, speed);
    this.bubble.update(deltaMs * speed);
    this.syncPosition(false);
  }

  override destroy(): void {
    this.bubble.clear();
    super.destroy({ children: true });
  }

  private advanceRoute(deltaMs: number, speed: number): void {
    const next = this.route[0];
    if (!next) return;
    const budget = stepDistance(WALK_TILES_PER_SECOND, deltaMs, speed);
    const dx = next.x - this.tile.x;
    const dy = next.y - this.tile.y;
    const distance = Math.hypot(dx, dy);
    if (distance <= budget) {
      this.tile = { ...next };
      this.route.shift();
      return;
    }
    this.tile = {
      x: this.tile.x + (dx / distance) * budget,
      y: this.tile.y + (dy / distance) * budget,
    };
  }

  private animate(deltaMs: number, speed: number): void {
    const walking = this.route.length > 0;
    const activity = this.agent.activity;

    if (walking) {
      this.frameElapsed += deltaMs * speed;
      if (this.frameElapsed >= WALK_FRAME_MS) {
        this.frameElapsed = 0;
        this.frame = this.frame === 0 ? 1 : 0;
        this.body.texture = this.textures.avatar(
          this.agent.role,
          this.frame,
          this.agent.agent_type === 'CHIEF',
        );
      }
    }

    // Respiração: amplitude maior quando o agente está raciocinando.
    this.bobElapsed += deltaMs * speed;
    const amplitude = activity === 'THINKING' ? 2.4 : activity === 'WORKING' ? 1.6 : 0.8;
    this.body.y = Math.sin(this.bobElapsed / 320) * amplitude;

    if (activity === 'THINKING' || activity === 'WORKING') {
      this.glyph.alpha = 0.55 + 0.45 * Math.abs(Math.sin(this.bobElapsed / 260));
      if (activity === 'WORKING') this.glyph.rotation += (deltaMs * speed) / 400;
    } else {
      this.glyph.alpha = 1;
      this.glyph.rotation = 0;
    }

    if (this.shakeMs > 0) {
      this.shakeMs -= deltaMs;
      this.body.x = Math.sin(this.shakeMs / 25) * 2;
    } else {
      this.body.x = damp(this.body.x, 0, 12, deltaMs);
    }

    this.updateParticles(deltaMs);
  }

  /** Confetes geométricos na conclusão de uma entrega. */
  private updateParticles(deltaMs: number): void {
    if (this.celebrateMs <= 0) {
      if (this.particles.visible) {
        this.particles.clear();
        this.particles.visible = false;
      }
      return;
    }
    this.celebrateMs -= deltaMs;
    const progress = 1 - this.celebrateMs / 900;
    this.particles.visible = true;
    this.particles.clear();
    for (let i = 0; i < 8; i += 1) {
      const angle = (i / 8) * Math.PI * 2;
      const radius = this.tileSize * 0.4 + progress * this.tileSize * 0.9;
      this.particles
        .rect(Math.cos(angle) * radius, -this.tileSize * 0.6 + Math.sin(angle) * radius, 3, 3)
        .fill({ color: 0x22c55e, alpha: Math.max(0, 1 - progress) });
    }
  }

  private drawStatusRing(): void {
    this.statusRing.clear();
    this.statusRing
      .ellipse(0, 2, this.tileSize * 0.42, this.tileSize * 0.15)
      .fill({ color: ACTIVITY_COLORS[this.agent.activity], alpha: 0.28 });
  }

  private drawProgress(): void {
    this.progress.clear();
    const reasoning = this.agent.reasoning;
    if (!reasoning || reasoning.status !== 'RUNNING') return;
    const width = this.tileSize * 0.9;
    const y = -this.tileSize * 1.05;
    this.progress.roundRect(-width / 2, y, width, 4, 2).fill({ color: 0x0f172a, alpha: 0.85 });
    this.progress
      .roundRect(-width / 2, y, Math.max(2, width * reasoning.progress), 4, 2)
      .fill({ color: ACTIVITY_COLORS.THINKING });
  }

  private syncPosition(immediate: boolean): void {
    const x = (this.tile.x + 0.5) * this.tileSize;
    const y = (this.tile.y + 0.9) * this.tileSize;
    if (immediate) {
      this.position.set(x, y);
      return;
    }
    this.position.set(x, y);
    this.zIndex = this.tile.y;
  }
}
