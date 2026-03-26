import { Suspense } from 'react';
import AppShell from './components/layout/AppShell';
import { useWebSocket } from './hooks/useWebSocket';

function AppContent() {
  useWebSocket();
  return <AppShell />;
}

export default function App() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center">Loading...</div>}>
      <AppContent />
    </Suspense>
  );
}
