import { ChatLog } from '@/components/ChatLog';
import { Notifications } from '@/components/Notifications';
import { OfficeCanvas } from '@/components/OfficeCanvas';
import { RequestsPanel } from '@/components/RequestsPanel';
import { SidePanel } from '@/components/SidePanel';
import { TopBar } from '@/components/TopBar';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { useUiStore } from '@/store/uiStore';

export function App(): React.JSX.Element {
  useGameSocket();
  useKeyboardShortcuts();
  const panelExpanded = useUiStore((state) => state.panelExpanded);
  const panelCollapsed = useUiStore((state) => state.panelCollapsed);
  const stageView = useUiStore((state) => state.stageView);

  const shellClass = [
    'app',
    panelExpanded && !panelCollapsed ? 'panel-expanded' : '',
    panelCollapsed ? 'panel-collapsed' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={shellClass}>
      <TopBar />
      <main className="stage">
        {stageView === 'office' ? (
          <>
            <OfficeCanvas />
            <Notifications />
            <ChatLog />
          </>
        ) : (
          <>
            <RequestsPanel />
            <Notifications />
          </>
        )}
      </main>
      <SidePanel />
    </div>
  );
}
