import React from 'react';

export default function Sidebar({ currentView, setCurrentView }) {
  const menuItems = [
    { id: 'dashboard', label: 'Panel główny' },
    { id: 'inbox', label: 'Skrzynka 13', count: 13 },
    { id: 'providers', label: 'Dostawcy usług' },
    { id: 'berths', label: 'Nadbrzeża' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">DOCK WISE</div>
      <nav>
        {menuItems.map(item => (
          <div
            key={item.id}
            className={`nav-item ${currentView === item.id ? 'active' : ''}`}
            onClick={() => setCurrentView(item.id)}
          >
            {/* Tutaj mogłyby być ikony z lucide-react */}
            <span>{item.label}</span>
            {item.count && <span className="nav-count">{item.count}</span>}
          </div>
        ))}
      </nav>
    </aside>
  );
}