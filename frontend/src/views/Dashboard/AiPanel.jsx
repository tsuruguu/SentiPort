import React, { useState } from 'react';

export default function AiPanel({ nomination, enrichment }) {
  const [aiEnabled, setAiEnabled] = useState(true);

  // Sprawdzamy, czy AI znalazło braki z backendu (lista z vessel_enrichment.py)
  const hasInconsistencies = enrichment?.inconsistencies_to_clarify?.length > 0;

  // Funkcja sprawdzająca czy konkretne pole jest oflagowane błędem
  const isFieldInvalid = (fieldName) => {
    return enrichment?.inconsistencies_to_clarify?.some(i => i.field_name === fieldName);
  };

  return (
    <div className="glass-panel">
      <div className="panel-header">
        <div className="panel-title">Sugestie Ai</div>
        <div className="ai-toggle">
          <div className={`toggle-btn on ${aiEnabled ? 'active' : ''}`} onClick={() => setAiEnabled(true)}>ON</div>
          <div className={`toggle-btn off ${!aiEnabled ? 'active' : ''}`} onClick={() => setAiEnabled(false)}>OFF</div>
        </div>
      </div>

      {aiEnabled && hasInconsistencies && (
        <div className="error-text">BRAKUJĄCE INFORMACJE!</div>
      )}

      <div className="data-section">
        <div className="data-label">Armator:</div>
        <div className="data-value">{nomination.nominating_company?.company_name || 'Brak danych'}</div>
      </div>

      <div className="data-section">
        <div className="data-label">Informacje o statku:</div>
        <div className="data-value">
          <p>{nomination.vessel?.current_vessel_name}</p>
          <p>IMO: {nomination.vessel?.imo_number}</p>

          {/* Jeśli wymiary są zagnieżdżone w błędach - renderuj je na czerwono zgodnie z designem */}
          <p className={aiEnabled && isFieldInvalid('length_overall_meters') ? 'highlight-danger' : ''}>
            Długość statku: {nomination.vessel_technical_specs?.length_overall_meters}m
          </p>

          {/* Surowy tekst maila (hababab...) pokazany z obiektu NominationDetailResponse */}
          <p style={{ marginTop: '1rem', fontStyle: 'italic', color: '#94a3b8' }}>
            {nomination.source_email_body_raw}
          </p>
        </div>
      </div>

      <div className="data-section">
        <div className="data-label">Planowane dotarcie do portu:</div>
        <div className="data-value">
          {new Date(nomination.eta).toLocaleString('pl-PL')}
        </div>
      </div>
    </div>
  );
}