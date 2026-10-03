/**
 * Sprites procedurais (ADR-009).
 *
 * Nada de arte binária no repositório: cada avatar e cada móvel é desenhado com
 * `Graphics` e congelado numa textura reaproveitada por todos os sprites iguais.
 */

import { Graphics, type Renderer, type Texture } from 'pixi.js';

import type { AgentRole } from '@/types/api';

import { PALETTE, ROLE_COLORS } from './palette';

export type AvatarFrame = 0 | 1;

const SKIN = 0xf1c7a0;
const SHOE = 0x1f2937;

function darken(color: number, amount = 0.35): number {
  const r = Math.round(((color >> 16) & 0xff) * (1 - amount));
  const g = Math.round(((color >> 8) & 0xff) * (1 - amount));
  const b = Math.round((color & 0xff) * (1 - amount));
  return (r << 16) | (g << 8) | b;
}

function lighten(color: number, amount = 0.35): number {
  const mix = (channel: number): number => Math.round(channel + (255 - channel) * amount);
  const r = mix((color >> 16) & 0xff);
  const g = mix((color >> 8) & 0xff);
  const b = mix(color & 0xff);
  return (r << 16) | (g << 8) | b;
}

/** Avatar de 24×34, ancorado nos pés. Dois quadros formam a animação de caminhada. */
function drawAvatar(role: AgentRole, frame: AvatarFrame, isChief: boolean): Graphics {
  const body = ROLE_COLORS[role];
  const g = new Graphics();

  // Sombra projetada no chão.
  g.ellipse(12, 33, 9, 3).fill({ color: 0x000000, alpha: 0.35 });

  // Pernas: o quadro 1 afasta os pés para sugerir passada.
  const spread = frame === 1 ? 3 : 1;
  g.rect(9 - spread, 25, 4, 7).fill({ color: darken(body, 0.5) });
  g.rect(11 + spread, 25, 4, 7).fill({ color: darken(body, 0.5) });
  g.rect(8 - spread, 31, 5, 3).fill({ color: SHOE });
  g.rect(11 + spread, 31, 5, 3).fill({ color: SHOE });

  // Tronco.
  g.roundRect(5, 12, 14, 14, 3).fill({ color: body });
  g.roundRect(5, 12, 14, 4, 2).fill({ color: darken(body, 0.2) });

  // Braços.
  const armY = frame === 1 ? 15 : 16;
  g.roundRect(2, armY, 4, 9, 2).fill({ color: darken(body, 0.15) });
  g.roundRect(18, armY, 4, 9, 2).fill({ color: darken(body, 0.15) });

  // Cabeça e cabelo.
  g.circle(12, 7, 6).fill({ color: SKIN });
  g.arc(12, 7, 6, Math.PI, 0).fill({ color: darken(body, 0.55) });
  g.circle(10, 8, 1).fill({ color: 0x1f2937 });
  g.circle(14, 8, 1).fill({ color: 0x1f2937 });

  // Crachá dourado distingue a diretoria à primeira vista.
  if (isChief) {
    g.circle(16, 18, 2).fill({ color: PALETTE.selection });
  }
  return g;
}

/** Mesa vista de cima, com monitor aceso. */
function drawDesk(width: number, height: number): Graphics {
  const g = new Graphics();
  g.roundRect(0, 0, width, height, 4).fill({ color: PALETTE.deskTop });
  g.roundRect(0, 0, width, height, 4).stroke({ width: 2, color: PALETTE.deskEdge });
  g.roundRect(width * 0.25, height * 0.15, width * 0.5, height * 0.35, 2).fill({
    color: PALETTE.monitor,
  });
  g.roundRect(width * 0.3, height * 0.62, width * 0.4, height * 0.18, 2).fill({
    color: PALETTE.chair,
  });
  return g;
}

/** Rack de servidores: a presença física da Natureza no escritório. */
function drawServerRack(width: number, height: number): Graphics {
  const g = new Graphics();
  g.roundRect(0, 0, width, height, 3).fill({ color: 0x111827 });
  g.roundRect(0, 0, width, height, 3).stroke({ width: 2, color: 0x374151 });
  for (let i = 0; i < 4; i += 1) {
    const y = 4 + (i * (height - 8)) / 4;
    g.rect(3, y, width - 6, 3).fill({ color: 0x1f2937 });
    g.circle(width - 6, y + 1.5, 1.2).fill({ color: 0x22c55e });
  }
  return g;
}

/** Cadeira avulsa do bench e da sala de reunião. */
function drawChair(size: number): Graphics {
  const g = new Graphics();
  g.roundRect(size * 0.15, size * 0.3, size * 0.7, size * 0.55, 3).fill({ color: PALETTE.chair });
  g.roundRect(size * 0.2, size * 0.1, size * 0.6, size * 0.25, 3).fill({
    color: darken(PALETTE.chair, 0.25),
  });
  return g;
}

export type FurnitureKind = 'desk' | 'rack' | 'chair';

/**
 * Cache de texturas do processo de render.
 *
 * `generateTexture` é caro; sem o cache, cada avatar custaria um draw call extra
 * por quadro em vez de entrar no batch de sprites.
 */
export class TextureFactory {
  private readonly cache = new Map<string, Texture>();

  constructor(private readonly renderer: Renderer) {}

  avatar(role: AgentRole, frame: AvatarFrame, isChief: boolean): Texture {
    return this.remember(`avatar:${role}:${frame}:${isChief}`, () =>
      drawAvatar(role, frame, isChief),
    );
  }

  furniture(kind: FurnitureKind, width: number, height: number): Texture {
    return this.remember(`furniture:${kind}:${width}x${height}`, () => {
      if (kind === 'desk') return drawDesk(width, height);
      if (kind === 'rack') return drawServerRack(width, height);
      return drawChair(width);
    });
  }

  destroy(): void {
    for (const texture of this.cache.values()) texture.destroy(true);
    this.cache.clear();
  }

  private remember(key: string, build: () => Graphics): Texture {
    const cached = this.cache.get(key);
    if (cached) return cached;
    const graphics = build();
    const texture = this.renderer.generateTexture({ target: graphics, resolution: 2 });
    graphics.destroy();
    this.cache.set(key, texture);
    return texture;
  }
}

export { darken, lighten };
