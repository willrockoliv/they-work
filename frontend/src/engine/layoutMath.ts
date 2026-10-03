/** Conversões de coordenadas, enquadramento de câmera e interpolação de movimento. */

import type { OfficeLayout } from '@/types/game';

export interface Point {
  x: number;
  y: number;
}

export interface Viewport {
  width: number;
  height: number;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Centro do tile, em pixels. */
export function tileToPixel(tile: Point, tileSize: number): Point {
  return { x: (tile.x + 0.5) * tileSize, y: (tile.y + 0.5) * tileSize };
}

/** Tile que contém um ponto em pixels do mundo. */
export function pixelToTile(pixel: Point, tileSize: number): Point {
  return { x: Math.floor(pixel.x / tileSize), y: Math.floor(pixel.y / tileSize) };
}

/** Zoom que faz o escritório inteiro caber no viewport, com uma folga. */
export function fitZoom(layout: OfficeLayout, viewport: Viewport, padding = 24): number {
  const worldWidth = layout.columns * layout.tile_size;
  const worldHeight = layout.rows * layout.tile_size;
  if (worldWidth <= 0 || worldHeight <= 0) return 1;
  const usableWidth = Math.max(viewport.width - padding * 2, 1);
  const usableHeight = Math.max(viewport.height - padding * 2, 1);
  return Math.min(usableWidth / worldWidth, usableHeight / worldHeight);
}

/** Centro do mapa, em tiles. */
export function layoutCenter(layout: OfficeLayout): Point {
  return { x: layout.columns / 2, y: layout.rows / 2 };
}

/**
 * Mantém o foco da câmera dentro do mapa.
 *
 * Quando o mundo é menor que o viewport em algum eixo, o foco nesse eixo trava
 * no centro — do contrário a cena "escaparia" da tela ao arrastar.
 */
export function clampFocus(
  focus: Point,
  layout: OfficeLayout,
  viewport: Viewport,
  zoom: number,
): Point {
  const halfWidthTiles = viewport.width / (2 * zoom * layout.tile_size);
  const halfHeightTiles = viewport.height / (2 * zoom * layout.tile_size);

  const clampAxis = (value: number, half: number, total: number): number => {
    if (half * 2 >= total) return total / 2;
    return Math.min(total - half, Math.max(half, value));
  };

  return {
    x: clampAxis(focus.x, halfWidthTiles, layout.columns),
    y: clampAxis(focus.y, halfHeightTiles, layout.rows),
  };
}

/** Retângulo do mundo visível, em tiles, já com margem para culling. */
export function visibleTileBounds(
  focus: Point,
  layout: OfficeLayout,
  viewport: Viewport,
  zoom: number,
  margin = 2,
): Rect {
  const halfWidth = viewport.width / (2 * zoom * layout.tile_size) + margin;
  const halfHeight = viewport.height / (2 * zoom * layout.tile_size) + margin;
  return {
    x: focus.x - halfWidth,
    y: focus.y - halfHeight,
    width: halfWidth * 2,
    height: halfHeight * 2,
  };
}

export function isWithin(point: Point, rect: Rect): boolean {
  return (
    point.x >= rect.x &&
    point.x <= rect.x + rect.width &&
    point.y >= rect.y &&
    point.y <= rect.y + rect.height
  );
}

/** Interpolação quadro-independente: `rate` é a fração recuperada por segundo. */
export function damp(current: number, target: number, rate: number, deltaMs: number): number {
  if (Math.abs(target - current) < 0.001) return target;
  const factor = 1 - Math.exp((-rate * deltaMs) / 1000);
  return current + (target - current) * factor;
}

export function easeInOut(t: number): number {
  const clamped = Math.min(1, Math.max(0, t));
  return clamped < 0.5 ? 2 * clamped * clamped : 1 - (-2 * clamped + 2) ** 2 / 2;
}

/**
 * Caminho em L entre dois tiles.
 *
 * O escritório é um salão aberto: um desvio ortogonal já basta para o avatar
 * contornar as mesas sem o custo de um A\* completo.
 */
export function routeBetween(from: Point, to: Point): Point[] {
  if (from.x === to.x || from.y === to.y) return [to];
  return [{ x: to.x, y: from.y }, to];
}

/** Distância em tiles percorrida no intervalo, dada a velocidade e o multiplicador. */
export function stepDistance(tilesPerSecond: number, deltaMs: number, speed: number): number {
  return (tilesPerSecond * speed * deltaMs) / 1000;
}
