import { NavLink } from 'react-router-dom';

const TABS = [
  { to: '/', label: 'Panel główny' },
  { to: '/skrzynka', label: 'Skrzynka' },
  { to: '/dostawcy', label: 'Dostawcy usług' },
  { to: '/nadbrzeza', label: 'Nadbrzeża' },
];

export default function TopNav({ inboxCount = 0, userName = 'Agent Portowy' }) {
  return (
    <header className="relative z-10 flex items-center justify-between px-6 py-3 bg-white/10 backdrop-blur-md border-b border-white/15">
      <div className="bg-white rounded-full px-5 py-2 shadow-sm">
        <span className="font-display font-semibold text-lg text-dockwise-navy tracking-wide">
          DockWise
        </span>
      </div>

      <nav className="flex items-center gap-8">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `relative font-display text-[17px] text-white transition-opacity hover:opacity-100 ${
                isActive ? 'opacity-100' : 'opacity-75'
              }`
            }
          >
            {({ isActive }) => (
              <span className="relative inline-block">
                {tab.label}
                {tab.to === '/skrzynka' && inboxCount > 0 && (
                  <span className="absolute -top-2 -right-4 bg-dockwise-accentRed text-white text-[10px] font-body font-semibold rounded-full w-5 h-5 flex items-center justify-center">
                    {inboxCount}
                  </span>
                )}
                {isActive && (
                  <span className="absolute -bottom-1 left-0 right-0 h-[2px] bg-white rounded-full" />
                )}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="flex items-center gap-4">
        <button
          type="button"
          aria-label="Ustawienia"
          className="text-white/85 hover:text-white transition-colors"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
        <div className="flex items-center gap-2">
          <div className="relative">
            <div className="w-9 h-9 rounded-full bg-dockwise-mist flex items-center justify-center text-dockwise-navy font-semibold text-sm overflow-hidden">
              {userName.split(' ').map((p) => p[0]).join('').slice(0, 2)}
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-dockwise-accentGreen rounded-full border-2 border-dockwise-navy" />
          </div>
          <span className="text-white text-sm font-body hidden sm:inline">{userName}</span>
        </div>
      </div>
    </header>
  );
}
