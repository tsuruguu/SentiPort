import React, { useState } from 'react';
import Sidebar from './components/layout/Sidebar';
import TopRightAvatar from './components/layout/TopRightAvatar';
import ActionButtons from './components/ActionButtons';
import Dashboard from './views/Dashboard/Dashboard';
import Inbox from './views/Inbox/Inbox';
import Providers from './views/Providers'; // Nowy import
import Berths from './views/Berths';       // Nowy import

function App() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [selectedNominationId, setSelectedNominationId] = useState("123e4567");

  return (
    <div className="app-container">
      <Sidebar currentView={currentView} setCurrentView={setCurrentView} />

      <main className="main-content">
        {/* Renderowanie warunkowe w zależności od klikniętej zakładki */}
        {currentView === 'dashboard' && <Dashboard nominationId={selectedNominationId} />}
        {currentView === 'inbox' && <Inbox />}
        {currentView === 'providers' && <Providers />}
        {currentView === 'berths' && <Berths />}

        {/* Przyciski na dole pokazujemy tylko w panelu głównym */}
        {currentView === 'dashboard' && (
          <ActionButtons nominationId={selectedNominationId} />
        )}

        <TopRightAvatar name="Jakub Szprot" />
      </main>
    </div>
  );
}

export default App;