import React from 'react';
import { mockWeatherData } from '../../api/mockData';

export default function PortPanel({ nomination }) {
  return (
    <div className="glass-panel">
      <div className="panel-header">
        <div className="panel-title">Port XYZ</div>
      </div>

      <div className="data-section">
        <div className="data-label">Aktualna pogoda:</div>
        <div className="data-value">
          <p>{mockWeatherData.description}</p>
          {/* Prędkość wiatru dodana w drugiej fazie PDF */}
          <p>Prędkość wiatru: <strong>{mockWeatherData.wind_speed_ms} m/s</strong></p>
        </div>
      </div>

      <div className="data-section">
        <div className="data-label">Dane techniczne:</div>
        <div className="data-value">
          <p>Zanurzenie: {nomination.vessel_technical_specs?.draft_meters}m</p>
          <p>Szerokość (Beam): {nomination.vessel_technical_specs?.beam_meters}m</p>
          <p style={{ marginTop: '1rem', fontStyle: 'italic', color: '#94a3b8' }}>
            {nomination.source_email_body_raw}
          </p>
        </div>
      </div>
    </div>
  );
}