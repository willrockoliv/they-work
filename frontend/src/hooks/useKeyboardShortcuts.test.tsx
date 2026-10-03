import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { useGameStore } from '@/store/gameStore';
import { useUiStore } from '@/store/uiStore';

import { useKeyboardShortcuts } from './useKeyboardShortcuts';

function Harness(): React.JSX.Element {
  useKeyboardShortcuts();
  return <input aria-label="campo" />;
}

describe('useKeyboardShortcuts', () => {
  it('espaço pausa e retoma a simulação', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.keyboard('[Space]');
    expect(useGameStore.getState().paused).toBe(true);

    await user.keyboard('[Space]');
    expect(useGameStore.getState().paused).toBe(false);
  });

  it('ESC fecha o painel lateral', async () => {
    const user = userEvent.setup();
    useUiStore.getState().selectAgent('agent-1');
    render(<Harness />);

    await user.keyboard('{Escape}');
    expect(useUiStore.getState().selectedAgentId).toBeNull();
  });

  it('as setas movem a câmera', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.keyboard('{ArrowRight}{ArrowDown}');
    expect(useUiStore.getState().camera.focus).toEqual({ x: 2, y: 2 });

    await user.keyboard('{ArrowLeft}{ArrowUp}');
    expect(useUiStore.getState().camera.focus).toEqual({ x: 0, y: 0 });
  });

  it('+ e - dão zoom e 0 reenquadra', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.keyboard('+');
    expect(useUiStore.getState().camera.zoom).toBeGreaterThan(1);

    await user.keyboard('-');
    expect(useUiStore.getState().camera.zoom).toBeCloseTo(1, 2);

    useUiStore.getState().focusOn(5, 5);
    await user.keyboard('0');
    expect(useUiStore.getState().camera.focus).toBeNull();
  });

  it('C alterna o log de comunicações', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.keyboard('c');
    expect(useUiStore.getState().chatVisible).toBe(false);
  });

  it('digitar num campo não pilota a câmera', async () => {
    const user = userEvent.setup();
    const { getByLabelText } = render(<Harness />);

    await user.click(getByLabelText('campo'));
    await user.keyboard('c 0');

    expect(useUiStore.getState().chatVisible).toBe(true);
    expect(useGameStore.getState().paused).toBe(false);
  });
});
