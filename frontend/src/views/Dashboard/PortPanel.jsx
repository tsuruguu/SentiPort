import React from 'react';
import { mockWeatherData, mockRiskData } from '../../api/mockData';

export default function PortPanel({ nomination }) {
  return (
    <div className="glass-panel">
      <div className="panel-header">
        <div className="panel-title">Ocena Operacyjna</div>
      </div>

      <div className="data-section">
        <div className="data-label">Profil Ryzyka Statku (Risk Tier):</div>
        <div className="data-value" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '0.5rem' }}>
          <div style={{ background: '#fff', padding: '1rem', borderRadius: '6px', borderLeft: '4px solid #f59e0b', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Status Paris MoU</div>
            <div style={{ fontWeight: 600, color: '#1e293b' }}>Szara Lista (Grey)</div>
          </div>
          <div style={{ background: '#fff', padding: '1rem', borderRadius: '6px', borderLeft: mockRiskData.sanctions_clear ? '4px solid #10b981' : '4px solid #ef4444', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Screening Sankcyjny</div>
            <div style={{ fontWeight: 600, color: '#1e293b' }}>{mockRiskData.sanctions_clear ? 'Czysty (Clear)' : 'Wykryto ryzyko'}</div>
          </div>
        </div>
        {mockRiskData.psc_detentions > 0 && (
          <p style={{ marginTop: '0.5rem', color: '#ef4444', fontSize: '0.9rem', fontWeight: 600 }}>
            ⚠ Historia PSC: Zatrzymano statek {mockRiskData.psc_detentions} raz.
          </p>
        )}
      </div>

      <div className="data-section" style={{ marginTop: '2rem' }}>
        <div className="data-label">Parametry Infrastruktury:</div>
        <div className="data-value">
          <p>Wymagane zanurzenie: <strong>{nomination.vessel_technical_specs?.draft_meters}m</strong></p>
          <p>Szerokość (Beam): <strong>{nomination.vessel_technical_specs?.beam_meters}m</strong></p>
        </div>
      </div>

      <div className="data-section" style={{ marginTop: '2rem' }}>
        <div className="data-label">Warunki Pogodowe:</div>
        <div className="data-value">
          <p>{mockWeatherData.description}</p>
          <p>Prędkość wiatru: <strong>{mockWeatherData.wind_speed_ms} m/s</strong></p>
        </div>
      </div>
    </div>
  );
}