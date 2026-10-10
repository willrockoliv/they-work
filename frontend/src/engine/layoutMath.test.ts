import { describe, expect, it } from 'vitest';

import { layout } from '@/test/fixtures';

import {
  clampFocus,
  damp,
  easeInOut,
  fitZoom,
  isWithin,
  layoutCenter,
  pixelToTile,
  routeBetween,
  stepDistance,
  tileToPixel,
  visibleTileBounds,
  zoomForRect,
} from './layoutMath';

describe('conversão de coordenadas', () => {
  it('leva o tile ao centro em pixels e volta', () => {
    const pixel = tileToPixel({ x: 3, y: 4 }, 32);
    expect(pixel).toEqual({ x: 112, y: 144 });
    expect(pixelToTile(pixel, 32)).toEqual({ x: 3, y: 4 });
  });
});

describe('zoomForRect', () => {
  it('amplia o zoom para que a área escolhida preencha o viewport no eixo mais restrito', () => {
    // Área 400x200 num viewport 800x600: o eixo X limita, então o zoom dobra.
    const zoom = zoomForRect(1, { x: 0, y: 0, width: 400, height: 200 }, { width: 800, height: 600 });
    expect(zoom).toBeCloseTo(2);
  });

  it('reduz o zoom quando a área escolhida é maior que o viewport', () => {
    const zoom = zoomForRect(2, { x: 0, y: 0, width: 1600, height: 600 }, { width: 800, height: 600 });
    expect(zoom).toBeCloseTo(1);
  });

  it('mantém o zoom atual para uma área degenerada', () => {
    const zoom = zoomForRect(1.5, { x: 0, y: 0, width: 0, height: 10 }, { width: 800, height: 600 });
    expect(zoom).toBe(1.5);
  });
});

describe('câmera', () => {
  it('o zoom de enquadramento faz o mapa inteiro caber', () => {
    const zoom = fitZoom(layout, { width: 1280, height: 720 });
    expect(zoom * layout.columns * layout.tile_size).toBeLessThanOrEqual(1280);
    expect(zoom * layout.rows * layout.tile_size).toBeLessThanOrEqual(720);
  });

  it('o centro do mapa é o meio do grid', () => {
    expect(layoutCenter(layout)).toEqual({ x: 20, y: 12 });
  });

  it('o foco nunca escapa dos limites do escritório', () => {
    const viewport = { width: 640, height: 360 };
    const focus = clampFocus({ x: -50, y: 999 }, layout, viewport, 1);
    expect(focus.x).toBeGreaterThanOrEqual(0);
    expect(focus.y).toBeLessThanOrEqual(layout.rows);
  });

  it('quando o mundo cabe na tela, o foco trava no centro', () => {
    const focus = clampFocus({ x: 0, y: 0 }, layout, { width: 4000, height: 3000 }, 1);
    expect(focus).toEqual({ x: 20, y: 12 });
  });

  it('o retângulo visível acompanha o zoom', () => {
    const viewport = { width: 640, height: 320 };
    const aberto = visibleTileBounds({ x: 20, y: 12 }, layout, viewport, 1, 0);
    const fechado = visibleTileBounds({ x: 20, y: 12 }, layout, viewport, 2, 0);
    expect(aberto.width).toBeCloseTo(20);
    expect(fechado.width).toBeCloseTo(10);
  });

  it('o culling reconhece o que está dentro e fora', () => {
    const rect = { x: 0, y: 0, width: 10, height: 10 };
    expect(isWithin({ x: 5, y: 5 }, rect)).toBe(true);
    expect(isWithin({ x: 11, y: 5 }, rect)).toBe(false);
  });
});

describe('movimento', () => {
  it('o caminho em L desvia num único canto', () => {
    expect(routeBetween({ x: 0, y: 0 }, { x: 4, y: 3 })).toEqual([
      { x: 4, y: 0 },
      { x: 4, y: 3 },
    ]);
  });

  it('eixos alinhados vão direto ao destino', () => {
    expect(routeBetween({ x: 0, y: 2 }, { x: 7, y: 2 })).toEqual([{ x: 7, y: 2 }]);
  });

  it('a distância percorrida escala com a velocidade', () => {
    expect(stepDistance(3, 1_000, 1)).toBe(3);
    expect(stepDistance(3, 1_000, 4)).toBe(12);
  });

  it('a interpolação aproxima do alvo sem ultrapassá-lo', () => {
    const meio = damp(0, 10, 5, 100);
    expect(meio).toBeGreaterThan(0);
    expect(meio).toBeLessThan(10);
    expect(damp(10, 10, 5, 100)).toBe(10);
  });

  it('o easing é simétrico nas pontas', () => {
    expect(easeInOut(0)).toBe(0);
    expect(easeInOut(1)).toBe(1);
    expect(easeInOut(0.5)).toBeCloseTo(0.5);
  });
});
