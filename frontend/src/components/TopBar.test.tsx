import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { useGameStore } from '@/store/gameStore';
import { makeGameState } from '@/test/fixtures';

import { TopBar } from './TopBar';

describe('TopBar', () => {
  it('mostra placeholders enquanto o snapshot não chega', () => {
    render(<TopBar />);
    expect(screen.getByText('offline')).toBeInTheDocument();
  });

  it('exibe relógio, recursos e economia do snapshot', () => {
    useGameStore.getState().hydrate(makeGameState());
    useGameStore.getState().setConnection('open');
    render(<TopBar />);

    expect(screen.getByText('Dia 1 · 09:30')).toBeInTheDocument();
    expect(screen.getByText('4.0k / 16.4k MB')).toBeInTheDocument();
    expect(screen.getByText('1/4 · fila 0')).toBeInTheDocument();
    expect(screen.getByText('Natureza HEALTHY')).toBeInTheDocument();
    expect(screen.getByText('ao vivo')).toBeInTheDocument();
  });

  it('o botão de pausa alterna o estado da simulação', async () => {
    const user = userEvent.setup();
    useGameStore.getState().hydrate(makeGameState());
    render(<TopBar />);

    await user.click(screen.getByRole('button', { name: /pausar/i }));
    expect(useGameStore.getState().paused).toBe(true);

    await user.click(screen.getByRole('button', { name: /retomar/i }));
    expect(useGameStore.getState().paused).toBe(false);
  });

  it('a velocidade selecionada fica marcada', async () => {
    const user = userEvent.setup();
    render(<TopBar />);

    await user.click(screen.getByRole('button', { name: '4x' }));
    expect(useGameStore.getState().speed).toBe(4);
    expect(screen.getByRole('button', { name: '4x' })).toHaveAttribute('aria-pressed', 'true');
  });
});
