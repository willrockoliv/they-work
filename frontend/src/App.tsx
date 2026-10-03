import { ChatLog } from '@/components/ChatLog';
import { Notifications } from '@/components/Notifications';
import { OfficeCanvas } from '@/components/OfficeCanvas';
import { SidePanel } from '@/components/SidePanel';
import { TopBar } from '@/components/TopBar';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { useUiStore } from '@/store/uiStore';

export function App(): React.JSX.Element {
  useGameSocket();
  useKeyboardShortcuts();
  const panelExpanded = useUiStore((state) => state.panelExpanded);

  return (
    <div className={panelExpanded ? 'app panel-expanded' : 'app'}>
      <TopBar />
      <main className="stage">
        <OfficeCanvas />
        <Notifications />
        <ChatLog />
      </main>
      <SidePanel />
    </div>
  );
}
