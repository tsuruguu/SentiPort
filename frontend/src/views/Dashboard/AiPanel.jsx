import React, { useState } from 'react';

export default function AiPanel({ nomination, enrichment }) {
  const [aiEnabled, setAiEnabled] = useState(true);

  const hasInconsistencies = enrichment?.inconsistencies_to_clarify?.length > 0;

  const isFieldInvalid = (fieldName) => {
    return enrichment?.inconsistencies_to_clarify?.some(i => i.field_name === fieldName);
  };

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <div className="panel-title">Ekstrakcja AI</div>
        <div className="ai-toggle">
          <div className={`toggle-btn on ${aiEnabled ? 'active' : ''}`} onClick={() => setAiEnabled(true)}>ON</div>
          <div className={`toggle-btn off ${!aiEnabled ? 'active' : ''}`} onClick={() => setAiEnabled(false)}>OFF</div>
        </div>
      </div>

      {aiEnabled && (
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          <div style={{ padding: '0.5rem 1rem', background: '#e0f2fe', color: '#0369a1', borderRadius: '6px', fontWeight: 600 }}>
            Pewność modelu: {(nomination.confidence_score * 100).toFixed(0)}%
          </div>
          {hasInconsistencies && (
            <div style={{ padding: '0.5rem 1rem', background: '#fee2e2', color: '#b91c1c', borderRadius: '6px', fontWeight: 600 }}>
              Wykryto anomalię!
            </div>
          )}
        </div>
      )}

      <div className="data-section">
        <div className="data-label">Armator:</div>
        <div className="data-value">{nomination.nominating_company?.company_name || 'Brak danych'}</div>
      </div>

      <div className="data-section">
        <div className="data-label">Informacje o statku:</div>
        <div className="data-value">
          <p style={{ fontWeight: 600, color: '#1e293b' }}>{nomination.vessel?.current_vessel_name}</p>
          <p>IMO: {nomination.vessel?.imo_number}</p>
          <p className={aiEnabled && isFieldInvalid('length_overall_meters') ? 'highlight-danger' : ''}>
            Długość statku: {nomination.vessel_technical_specs?.length_overall_meters}m
          </p>
        </div>
      </div>

      <div className="data-section">
        <div className="data-label">Ładunek (IMDG Code):</div>
        <div className="data-value">
          {nomination.cargo_items.map((cargo, idx) => (
            <p key={idx} style={{ color: cargo.imdg_hazard_class !== 'none' ? '#d97706' : '#475569', fontWeight: 500 }}>
              {cargo.description} ({cargo.un_number})
            </p>
          ))}
        </div>
      </div>

      {aiEnabled && nomination.fields_missing?.length > 0 && (
        <div className="data-section" style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid #e2e8f0' }}>
          <div className="data-label" style={{ color: '#94a3b8' }}>Braki do uzupełnienia przez agenta:</div>
          <div className="data-value" style={{ fontSize: '0.85rem', color: '#64748b' }}>
            {nomination.fields_missing.join(', ')}
          </div>
        </div>
      )}
    </div>
  );
}