import React from 'react';

// Dane symulujące odpowiedź z endpointu usług (RequestedServiceResponse)
const mockServices = [
  { id: 1, type: 'Holowanie (Towage)', provider: 'Fairplay Towage Polska', status: 'Potwierdzone', time: '15.07.2026, 13:30', color: '#10b981' },
  { id: 2, type: 'Pilotaż (Pilotage)', provider: 'Pilot Station', status: 'Oczekujące', time: '15.07.2026, 14:00', color: '#f59e0b' },
  { id: 3, type: 'Bunkrowanie (Bunkering)', provider: 'Orlen Paliwa', status: 'W trakcie', time: '16.07.2026, 08:00', color: '#3b82f6' },
  { id: 4, type: 'Odbiór odpadów (Waste Removal)', provider: 'Port Service', status: 'Anulowane', time: '16.07.2026, 12:00', color: '#ef4444' }
];

export default function Providers() {
  return (
    <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <div className="panel-title">Dostawcy usług (Harmonogram dla Valdemar Construction)</div>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
        {mockServices.map(svc => (
          <div key={svc.id} style={{
            background: 'white',
            padding: '1.5rem',
            borderRadius: '8px',
            minWidth: '280px',
            flex: '1 1 calc(50% - 1.5rem)', // 2 kolumny
            boxShadow: '0 4px 6px rgba(0,0,0,0.05)',
            borderTop: `4px solid ${svc.color}`
          }}>
            <div style={{ fontWeight: 'bold', marginBottom: '0.5rem', fontSize: '1.1rem', color: '#1e293b' }}>
              {svc.type}
            </div>
            <div style={{ color: '#475569', marginBottom: '1.5rem', fontSize: '0.95rem' }}>
              Wykonawca: {svc.provider}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.9rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ fontSize: '1.2rem' }}>🕒</span> {svc.time}
              </span>
              <span style={{
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '0.85rem',
                fontWeight: 600,
                background: `${svc.color}15`,
                color: svc.color
              }}>
                {svc.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}