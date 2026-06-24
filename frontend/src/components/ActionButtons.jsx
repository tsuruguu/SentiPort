import React from 'react';

export default function ActionButtons({ nominationId }) {
  const handleAction = async (actionType) => {
    console.log(`Wykonuję akcję: ${actionType} dla zgłoszenia ${nominationId}`);
    // Docelowo: axios.post(`/api/v1/nominations/${nominationId}/status`, { status: actionType })
  };

  return (
    <div className="action-buttons">
      {/* status: verified wg enums.py */}
      <button className="btn-action btn-green" onClick={() => handleAction('verified')}>
        Zaakceptuj zgłoszenie
      </button>

      {/* status: rejected wg enums.py */}
      <button className="btn-action btn-blue" onClick={() => handleAction('rejected')}>
        Przekieruj do innego portu
      </button>

      {/* status: parsed_pending_review lub trigger do agenta mailowego */}
      <button className="btn-action btn-blue" onClick={() => handleAction('parsed_pending_review')}>
        Poproś o uzupełnienie danych
      </button>
    </div>
  );
}