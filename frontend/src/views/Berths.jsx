import React from 'react';

// Dane symulujące endpoint GET /ports/{port_id}/berths (oparte na port.py)
const mockBerths = [
  { id: 'BCTC-1', name: 'BCT Terminal - Nabrzeże Helskie I', maxDraft: 13.5, dangerousGoods: true, status: 'Zajęte', ship: 'MSC Zoe', color: '#ef4444' },
  { id: 'BCTC-2', name: 'BCT Terminal - Nabrzeże Helskie II', maxDraft: 13.5, dangerousGoods: true, status: 'Wolne', ship: '-', color: '#10b981' },
  { id: 'GCT-1', name: 'GCT - Nabrzeże Bułgarskie', maxDraft: 11.0, dangerousGoods: false, status: 'Wolne', ship: '-', color: '#10b981' },
  { id: 'GCT-2', name: 'GCT - Nabrzeże Rumuńskie', maxDraft: 13.5, dangerousGoods: true, status: 'Oczekuje', ship: 'Valdemar Construction (ETA: 15.07)', color: '#f59e0b' }
];

export default function Berths() {
  return (
    <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <div className="panel-title">Infrastruktura - Dostępne Nadbrzeża</div>
      </div>

      <div style={{ background: 'white', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569', fontSize: '0.95rem' }}>
            <tr>
              <th style={{ padding: '1.2rem 1rem' }}>Kod / Nazwa Terminala</th>
              <th style={{ padding: '1.2rem 1rem' }}>Max Zanurzenie</th>
              <th style={{ padding: '1.2rem 1rem' }}>Ładunki Niebezpieczne</th>
              <th style={{ padding: '1.2rem 1rem' }}>Status</th>
              <th style={{ padding: '1.2rem 1rem' }}>Aktualny / Oczekujący Statek</th>
            </tr>
          </thead>
          <tbody>
            {mockBerths.map((berth, i) => (
              <tr key={berth.id} style={{ borderBottom: i !== mockBerths.length - 1 ? '1px solid #e2e8f0' : 'none', transition: 'background 0.2s' }}>
                <td style={{ padding: '1.2rem 1rem' }}>
                  <div style={{ fontWeight: 600, color: '#1e293b' }}>{berth.id}</div>
                  <div style={{ fontSize: '0.85rem', color: '#64748b' }}>{berth.name}</div>
                </td>
                <td style={{ padding: '1.2rem 1rem', color: '#334155', fontWeight: 500 }}>{berth.maxDraft} m</td>
                <td style={{ padding: '1.2rem 1rem' }}>
                  {berth.dangerousGoods
                    ? <span style={{ color: '#ef4444', fontWeight: 600 }}>⚠ Tak</span>
                    : <span style={{ color: '#94a3b8' }}>Nie</span>}
                </td>
                <td style={{ padding: '1.2rem 1rem' }}>
                  <span style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    background: `${berth.color}15`,
                    color: berth.color
                  }}>
                    {berth.status}
                  </span>
                </td>
                <td style={{ padding: '1.2rem 1rem', color: '#475569', fontWeight: berth.ship !== '-' ? 500 : 400 }}>
                  {berth.ship}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}