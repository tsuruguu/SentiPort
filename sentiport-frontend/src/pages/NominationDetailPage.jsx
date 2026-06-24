import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useApiData } from '../hooks/useApiData';
import { nominationsApi } from '../api/nominations';
import { documentsApi } from '../api/documents';
import GlassPanel from '../components/GlassPanel';
import ActionButton from '../components/ActionButton';
import { formatDateTime, STATUS_LABELS, SERVICE_LABELS } from '../utils/format';

export default function NominationDetailPage() {
  const { nominationId } = useParams();
  const navigate = useNavigate();
  const [actionLoading, setActionLoading] = useState(null);
  const [message, setMessage] = useState(null);

  const { data: detail, loading, reload } = useApiData(
    () => nominationsApi.getDetail(nominationId),
    [nominationId]
  );

  const runAction = async (key, fn, successText) => {
    setActionLoading(key);
    setMessage(null);
    try {
      await fn();
      setMessage({ tone: 'success', text: successText });
      reload();
    } catch (err) {
      setMessage({ tone: 'error', text: err.message });
    } finally {
      setActionLoading(null);
    }
  };

  const handleGeneratePdf = async () => {
    setActionLoading('pdf');
    setMessage(null);
    try {
      const doc = await documentsApi.generate(nominationId);
      window.open(documentsApi.downloadUrl(doc.document_id), '_blank');
      setMessage({ tone: 'success', text: 'Pakiet PDF wygenerowany.' });
    } catch (err) {
      setMessage({ tone: 'error', text: err.message });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <div className="text-white text-center pt-20">Wczytywanie…</div>;
  if (!detail) return <div className="text-white text-center pt-20">Nominacja nie znaleziona.</div>;

  return (
    <div className="max-w-3xl mx-auto h-full overflow-y-auto">
      <button onClick={() => navigate('/skrzynka')} className="text-white/80 hover:text-white mb-4 text-sm">
        ← Wróć do skrzynki
      </button>

      {message && (
        <div
          className={`mb-4 px-4 py-2 rounded-lg text-sm font-medium ${
            message.tone === 'success'
              ? 'bg-dockwise-accentGreen/20 text-[#2F5E38]'
              : 'bg-dockwise-accentRed/20 text-[#7A2E26]'
          }`}
        >
          {message.text}
        </div>
      )}

      <GlassPanel title={detail.source_email_subject || 'Nominacja'}>
        <div className="space-y-5">
          <div className="flex flex-wrap gap-3">
            <ActionButton
              variant="redirect"
              onClick={() => runAction('extract', () => nominationsApi.extract(nominationId), 'Dane statku wyciągnięte z maila.')}
              loading={actionLoading === 'extract'}
            >
              Wyciągnij dane z maila (Agent AI)
            </ActionButton>
            <ActionButton
              variant="request"
              onClick={() => runAction('enrich', () => nominationsApi.enrichWithHistory(nominationId), 'Historia statku porównana.')}
              loading={actionLoading === 'enrich'}
            >
              Porównaj z historią statku
            </ActionButton>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <Field label="Status" value={STATUS_LABELS[detail.status] || detail.status} />
            <Field label="Statek" value={detail.vessel?.current_vessel_name} />
            <Field label="Numer IMO" value={detail.vessel?.imo_number} />
            <Field label="Firma" value={detail.nominating_company?.company_name} />
            <Field label="Port docelowy" value={detail.destination_port?.port_name} />
            <Field label="ETA" value={detail.eta ? formatDateTime(detail.eta) : null} />
            <Field label="ETD" value={detail.etd ? formatDateTime(detail.etd) : null} />
            <Field label="Nabrzeże żądane" value={detail.requested_berth?.berth_name} />
            <Field label="Nabrzeże przydzielone" value={detail.assigned_berth?.berth_name} />
          </div>

          {detail.cargo_items?.length > 0 && (
            <div>
              <h3 className="font-semibold text-dockwise-navy mb-2">Ładunek</h3>
              <ul className="space-y-1 text-sm">
                {detail.cargo_items.map((c) => (
                  <li key={c.cargo_id} className="bg-dockwise-mist rounded px-3 py-1.5">
                    {c.cargo_description} {c.cargo_quantity ? `· ${c.cargo_quantity} ${c.cargo_unit || ''}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {detail.requested_services?.length > 0 && (
            <div>
              <h3 className="font-semibold text-dockwise-navy mb-2">Usługi portowe</h3>
              <ul className="space-y-1 text-sm">
                {detail.requested_services.map((s) => (
                  <li key={s.service_order_id} className="bg-dockwise-mist rounded px-3 py-1.5">
                    {SERVICE_LABELS[s.service_type] || s.service_type}
                    {s.notes ? ` — ${s.notes}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {detail.fields_missing?.length > 0 && (
            <div className="bg-dockwise-accentYellow/20 border border-dockwise-accentYellow/50 rounded-lg px-4 py-3">
              <p className="font-semibold text-[#5C4A00] text-sm mb-1">Pola brakujące w mailu:</p>
              <p className="text-[#5C4A00] text-sm">{detail.fields_missing.join(', ')}</p>
            </div>
          )}

          <div className="pt-4 border-t border-dockwise-mist">
            <ActionButton variant="accept" onClick={handleGeneratePdf} loading={actionLoading === 'pdf'}>
              Wygeneruj pakiet PDF dla kapitanatu
            </ActionButton>
          </div>
        </div>
      </GlassPanel>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <dt className="text-dockwise-steel text-xs uppercase tracking-wide">{label}</dt>
      <dd className="text-dockwise-navy font-medium">{value || '—'}</dd>
    </div>
  );
}
