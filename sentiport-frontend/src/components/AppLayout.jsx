import { Outlet } from 'react-router-dom';
import OceanBackground from './OceanBackground';
import TopNav from './TopNav';

export default function AppLayout({ inboxCount }) {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <OceanBackground />
      <TopNav inboxCount={inboxCount} />
      <main className="flex-1 px-6 py-6 min-h-0 flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
