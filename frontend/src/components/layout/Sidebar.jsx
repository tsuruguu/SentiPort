import React from 'react';
import { mockMailbox } from '../../api/mockData';

export default function Sidebar({ currentView, setCurrentView }) {
  const menuItems = [
    { id: 'dashboard', label: 'Panel główny' },
    // Etykieta to teraz "Skrzynka", a licznik dynamicznie czyta długość tablicy z mockData
    { id: 'inbox', label: 'Skrzynka', count: mockMailbox.items.length },
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
            <span>{item.label}</span>
            {item.count > 0 && <span className="nav-count">{item.count}</span>}
          </div>
        ))}
      </nav>
    </aside>
  );
}