import { useGameStore, type SimulationSpeed } from '@/store/gameStore';
import { MAX_ZOOM, MIN_ZOOM, useUiStore } from '@/store/uiStore';

const SPEEDS: SimulationSpeed[] = [1, 2, 4];

/** Play/pause, velocidade, zoom e reset da visualização. */
export function Controls(): React.JSX.Element {
  const paused = useGameStore((state) => state.paused);
  const speed = useGameStore((state) => state.speed);
  const togglePaused = useGameStore((state) => state.togglePaused);
  const setSpeed = useGameStore((state) => state.setSpeed);
  const reset = useGameStore((state) => state.reset);
  const zoom = useUiStore((state) => state.camera.zoom);
  const zoomBy = useUiStore((state) => state.zoomBy);
  const resetCamera = useUiStore((state) => state.resetCamera);

  return (
    <div className="controls">
      <button
        type="button"
        onClick={togglePaused}
        aria-pressed={paused}
        title="Espaço alterna play/pause"
      >
        {paused ? '▶ Retomar' : '⏸ Pausar'}
      </button>

      <div className="group" role="group" aria-label="Velocidade da simulação">
        {SPEEDS.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={speed === option}
            onClick={() => setSpeed(option)}
          >
            {option}x
          </button>
        ))}
      </div>

      <div className="group" role="group" aria-label="Zoom do mapa">
        <button
          type="button"
          onClick={() => zoomBy(1 / 1.15)}
          disabled={zoom <= MIN_ZOOM}
          aria-label="Afastar"
        >
          −
        </button>
        <button type="button" onClick={resetCamera} aria-label="Enquadrar o escritório">
          {Math.round(zoom * 100)}%
        </button>
        <button
          type="button"
          onClick={() => zoomBy(1.15)}
          disabled={zoom >= MAX_ZOOM}
          aria-label="Aproximar"
        >
          +
        </button>
      </div>

      <button type="button" onClick={reset} title="Descarta o estado local e aguarda novo snapshot">
        ⟲ Reset
      </button>
    </div>
  );
}
