import React, { useState, useEffect } from 'react';
import AiPanel from './AiPanel';
import PortPanel from './PortPanel';
import { mockNominationDetail, mockEnrichmentData } from '../../api/mockData';

export default function Dashboard({ nominationId }) {
  const [nomination, setNomination] = useState(null);
  const [enrichment, setEnrichment] = useState(null);

  useEffect(() => {
    // Symulacja pobrania danych z: GET /api/v1/nominations/{id}
    // oraz POST /api/v1/nominations/{id}/enrich-with-history
    setNomination(mockNominationDetail);
    setEnrichment(mockEnrichmentData);
  }, [nominationId]);

  if (!nomination) return <div>Ładowanie danych...</div>;

  return (
    <div className="dashboard-grid">
      <AiPanel nomination={nomination} enrichment={enrichment} />
      <PortPanel nomination={nomination} />
    </div>
  );
}