/** Balão de fala/pensamento acima do avatar, com fila FIFO e auto-dismiss. */

import { Container, Graphics, Text, TextStyle } from 'pixi.js';

import type { MessageKind } from '@/store/gameStore';

import { STEP_COLORS, THEMES, type ThemeName } from './palette';

/** Quanto tempo um balão permanece visível antes de ceder lugar ao próximo. */
export const BUBBLE_TTL_MS = 6_000;
const MAX_WIDTH = 190;
const MAX_CHARS = 110;

const TEXT_STYLE = new TextStyle({
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  fontSize: 11,
  fill: THEMES.dark.text,
  wordWrap: true,
  wordWrapWidth: MAX_WIDTH - 16,
  lineHeight: 14,
});

export interface BubbleContent {
  text: string;
  kind: MessageKind;
}

export class ChatBubble extends Container {
  private readonly background = new Graphics();
  private readonly content: Text;
  private readonly queue: BubbleContent[] = [];
  private current: BubbleContent | null = null;
  private remainingMs = 0;
  private theme: ThemeName = 'dark';

  constructor() {
    super();
    this.content = new Text({ text: '', style: TEXT_STYLE.clone() });
    this.content.position.set(8, 6);
    this.addChild(this.background, this.content);
    this.visible = false;
    this.eventMode = 'none';
  }

  setTheme(theme: ThemeName): void {
    if (this.theme === theme) return;
    this.theme = theme;
    this.content.style.fill = THEMES[theme].text;
    if (this.current) this.render(this.current);
  }

  /** Enfileira uma fala; a fila é FIFO e limitada para não acumular atraso. */
  push(content: BubbleContent): void {
    this.queue.push(content);
    if (this.queue.length > 4) this.queue.shift();
    if (!this.current) this.advance();
  }

  update(deltaMs: number): void {
    if (!this.current) return;
    this.remainingMs -= deltaMs;
    if (this.remainingMs <= 0) {
      this.advance();
      return;
    }
    // Desvanece no último meio segundo.
    this.alpha = Math.min(1, this.remainingMs / 500);
  }

  clear(): void {
    this.queue.length = 0;
    this.current = null;
    this.visible = false;
  }

  private advance(): void {
    const next = this.queue.shift();
    this.current = next ?? null;
    if (!next) {
      this.visible = false;
      return;
    }
    this.remainingMs = BUBBLE_TTL_MS;
    this.alpha = 1;
    this.visible = true;
    this.render(next);
  }

  private render(content: BubbleContent): void {
    const text =
      content.text.length > MAX_CHARS ? `${content.text.slice(0, MAX_CHARS)}…` : content.text;
    this.content.text = text;

    const width = Math.min(MAX_WIDTH, Math.max(60, this.content.width + 16));
    const height = this.content.height + 12;
    const accent = STEP_COLORS[content.kind] ?? THEMES[this.theme].textMuted;
    const surface = THEMES[this.theme].bubble;

    this.background.clear();
    this.background.roundRect(0, 0, width, height, 6).fill({ color: surface, alpha: 0.94 });
    this.background.roundRect(0, 0, width, height, 6).stroke({ width: 1.5, color: accent });
    this.background.moveTo(width / 2 - 5, height);
    this.background.lineTo(width / 2 + 5, height);
    this.background.lineTo(width / 2, height + 7);
    this.background.fill({ color: surface, alpha: 0.94 });

    this.pivot.set(width / 2, height + 7);
  }
}
