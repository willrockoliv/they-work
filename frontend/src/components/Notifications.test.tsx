import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useGameStore } from '@/store/gameStore';
import { makeGameState, resources } from '@/test/fixtures';

import { Notifications } from './Notifications';

afterEach(() => {
  vi.useRealTimers();
});

describe('Notifications', () => {
  it('não renderiza nada quando não há alertas', () => {
    render(<Notifications />);
    expect(screen.getByRole('status')).toBeEmptyDOMElement();
  });

  it('mostra o alerta da Natureza e permite dispensá-lo', async () => {
    const user = userEvent.setup();
    useGameStore.getState().hydrate(makeGameState());
    useGameStore.getState().applyEvent({
      event: 'nature.status',
      agent_id: null,
      data: { ...resources, status: 'CRITICAL' },
    });
    render(<Notifications />);

    expect(screen.getByText('A Natureza está CRITICAL')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /dispensar/i }));
    expect(screen.queryByText('A Natureza está CRITICAL')).not.toBeInTheDocument();
  });

  it('alerta não-crítico some sozinho; crítico permanece', () => {
    vi.useFakeTimers();
    useGameStore.getState().hydrate(makeGameState());
    useGameStore.getState().applyEvent({
      event: 'nature.status',
      agent_id: null,
      data: { ...resources, status: 'WARNING' },
    });
    useGameStore.getState().applyEvent({
      event: 'nature.status',
      agent_id: null,
      data: { ...resources, status: 'CRITICAL' },
    });
    render(<Notifications />);

    act(() => {
      vi.advanceTimersByTime(13_000);
    });

    expect(screen.queryByText('A Natureza está WARNING')).not.toBeInTheDocument();
    expect(screen.getByText('A Natureza está CRITICAL')).toBeInTheDocument();
  });
});
