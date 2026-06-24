import React, { useState, useEffect } from 'react';
import { mockMailbox } from '../../api/mockData';

export default function Inbox() {
  const [emails, setEmails] = useState([]);

  useEffect(() => {
    // Symulacja GET /api/v1/nominations?status=received
    setEmails(mockMailbox.items);
  }, []);

  return (
    <div className="glass-panel" style={{ flex: 1, maxWidth: '800px' }}>
      <div className="panel-header">
        <div className="panel-title">Wiadomości</div>
      </div>

      <div className="inbox-list">
        {emails.map((email, idx) => (
          <div key={idx} className="message-card">
            <div className="message-sender">
              Armator: {email.nominating_company?.company_name}
            </div>
            <div className="message-snippet">
              {email.source_email_subject}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}