import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApiData } from '../hooks/useApiData';
import { nominationsApi } from '../api/nominations';
import GlassPanel from '../components/GlassPanel';
import { formatDateTime, STATUS_LABELS } from '../utils/format';

export default function InboxPage() {
  const navigate = useNavigate();
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);

  const { data, loading, error, reload } = useApiData(
    () => nominationsApi.list({ limit: 50 }),
    []
  );

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await nominationsApi.syncInbox();
      setSyncResult(`Zaimportowano ${result.imported_count} nowych maili.`);
      reload();
    } catch (err) {
      setSyncResult(`Błąd importu: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-full">
      <GlassPanel
        className="h-full"
        title="Wiadomości"
        headerRight={
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing}
            className="text-sm bg-dockwise-steel text-white px-4 py-1.5 rounded-lg hover:bg-dockwise-navy transition-colors disabled:opacity-50"
          >
            {syncing ? 'Importowanie…' : 'Sprawdź nową pocztę'}
          </button>
        }
      >
        {syncResult && (
          <p className="mb-4 text-sm text-dockwise-steel bg-dockwise-mist rounded-lg px-3 py-2">
            {syncResult}
          </p>
        )}

        {loading && <p className="text-dockwise-steel">Wczytywanie wiadomości…</p>}
        {error && <p className="text-dockwise-accentRed">Błąd wczytywania: {error.message}</p>}

        {data?.items?.length === 0 && (
          <p className="text-dockwise-steel italic">
            Brak wiadomości. Kliknij "Sprawdź nową pocztę", żeby zaimportować maile ze skrzynki.
          </p>
        )}

        <ul className="divide-y divide-dockwise-mist">
          {data?.items?.map((item) => (
            <li key={item.nomination_id}>
              <button
                type="button"
                onClick={() => navigate(`/panel/${item.nomination_id}`)}
                className="w-full text-left py-4 hover:bg-dockwise-mist/60 transition-colors rounded-lg px-2 -mx-2"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-dockwise-navy">
                    Armator: {item.nominating_company?.company_name || 'nieznany'}
                    {item.vessel ? ` — ${item.vessel.current_vessel_name}` : ''}
                  </span>
                  {item.requires_human_review && (
                    <span className="text-xs bg-dockwise-accentRed/15 text-dockwise-accentRed font-medium px-2 py-0.5 rounded-full">
                      Do weryfikacji
                    </span>
                  )}
                </div>
                <p className="text-dockwise-steel text-sm truncate mt-0.5">
                  {item.source_email_subject || 'Brak tematu'}
                </p>
                <p className="text-dockwise-steel/70 text-xs mt-1">
                  {STATUS_LABELS[item.status] || item.status}
                  {item.source_email_received_at && ` · ${formatDateTime(item.source_email_received_at)}`}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </GlassPanel>
    </div>
  );
}