import { useEffect } from 'react';

import { useGameStore } from '@/store/gameStore';

const AUTO_DISMISS_MS = 12_000;

/** Alertas da Natureza, contratações bloqueadas e marcos concluídos. */
export function Notifications(): React.JSX.Element {
  const notifications = useGameStore((state) => state.notifications);
  const dismiss = useGameStore((state) => state.dismissNotification);

  useEffect(() => {
    // Alertas críticos exigem ação do observador e não somem sozinhos.
    const timers = notifications
      .filter((notification) => notification.severity !== 'critical')
      .map((notification) => setTimeout(() => dismiss(notification.id), AUTO_DISMISS_MS));
    return () => timers.forEach(clearTimeout);
  }, [notifications, dismiss]);

  return (
    <div className="notifications" role="status" aria-live="polite">
      {notifications.map((notification) => (
        <article
          key={notification.id}
          className="notification"
          data-severity={notification.severity}
        >
          <strong>{notification.title}</strong>
          <p>{notification.body}</p>
          <button
            type="button"
            onClick={() => dismiss(notification.id)}
            aria-label={`Dispensar: ${notification.title}`}
          >
            ✕
          </button>
        </article>
      ))}
    </div>
  );
}
