import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApiData } from '../hooks/useApiData';
import { nominationsApi } from '../api/nominations';
import { portsApi } from '../api/ports';
import GlassPanel from '../components/GlassPanel';
import ActionButton from '../components/ActionButton';
import HighlightField from '../components/HighlightField';
import { formatDateTime, STATUS_LABELS, SERVICE_LABELS } from '../utils/format';

function MailEnvelopeIcon() {
  return (
    <div className="absolute -left-3 top-6 w-16 h-16 bg-dockwise-steel rounded-2xl shadow-lg flex items-center justify-center">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8">
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="M3 7l9 6 9-6" />
      </svg>
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [actionLoading, setActionLoading] = useState(null);
  const [actionMessage, setActionMessage] = useState(null);

  // Bierzemy pierwszą nominację czekającą na przegląd - to jest "aktywne
  // zgłoszenie" wyświetlane na panelu głównym, analogicznie do mockupu
  // (jeden konkretny statek na ekranie głównym, resztę widać w Skrzynce).
  const { data: listData, loading: listLoading } = useApiData(
    () => nominationsApi.list({ status: 'parsed_pending_review', limit: 1 }),
    []
  );

  const activeNomination = listData?.items?.[0];

  const { data: detail, loading: detailLoading, reload: reloadDetail } = useApiData(
    () => (activeNomination ? nominationsApi.getDetail(activeNomination.nomination_id) : Promise.resolve(null)),
    [activeNomination?.nomination_id]
  );

  const { data: berthRecommendations } = useApiData(
    () => (activeNomination ? nominationsApi.recommendedBerths(activeNomination.nomination_id) : Promise.resolve(null)),
    [activeNomination?.nomination_id]
  );

  const handleAccept = async () => {
    if (!detail) return;
    setActionLoading('accept');
    setActionMessage(null);
    try {
      const topBerth = berthRecommendations?.recommendations?.[0]?.berth;
      if (topBerth) {
        await nominationsApi.assignBerth(detail.nomination_id, topBerth.berth_id);
      }
      await nominationsApi.changeStatus(detail.nomination_id, 'verified');
      setActionMessage({ tone: 'success', text: 'Zgłoszenie zaakceptowane.' });
      reloadDetail();
    } catch (err) {
      setActionMessage({ tone: 'error', text: err.message });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRedirect = async () => {
    if (!detail) return;
    setActionLoading('redirect');
    setActionMessage(null);
    try {
      await nominationsApi.changeStatus(detail.nomination_id, 'rejected');
      setActionMessage({ tone: 'success', text: 'Zgłoszenie przekierowane - oznaczone jako odrzucone w tym porcie.' });
      reloadDetail();
    } catch (err) {
      setActionMessage({ tone: 'error', text: err.message });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRequestMoreInfo = async () => {
    if (!detail) return;
    setActionLoading('request');
    setActionMessage(null);
    try {
      // Re-uruchamiamy wzbogacenie historią, żeby agent AI spróbował
      // ponownie zaproponować uzupełnienie brakujących pól.
      await nominationsApi.enrichWithHistory(detail.nomination_id);
      setActionMessage({ tone: 'success', text: 'Wysłano prośbę o uzupełnienie danych do agenta AI.' });
      reloadDetail();
    } catch (err) {
      setActionMessage({ tone: 'error', text: err.message });
    } finally {
      setActionLoading(null);
    }
  };

  if (listLoading) {
    return <div className="text-white text-center pt-20">Wczytywanie…</div>;
  }

  if (!activeNomination) {
    return (
      <div className="max-w-xl mx-auto mt-20">
        <GlassPanel title="Brak zgłoszeń do przeglądu">
          <p className="text-dockwise-steel">
            Wszystkie nominacje zostały już przejrzane. Sprawdź zakładkę{' '}
            <button onClick={() => navigate('/skrzynka')} className="underline font-medium">
              Skrzynka
            </button>{' '}
            po nowe maile.
          </p>
        </GlassPanel>
      </div>
    );
  }

  const hasMissingFields = (detail?.fields_missing?.length ?? 0) > 0;
  const vessel = detail?.vessel;
  const specs = detail?.vessel_technical_specs;
  const company = detail?.nominating_company;

  return (
    <div className="h-full flex flex-col min-h-0">
      {actionMessage && (
        <div
          className={`mb-4 px-4 py-2 rounded-lg text-sm font-medium ${
            actionMessage.tone === 'success'
              ? 'bg-dockwise-accentGreen/20 text-[#2F5E38] border border-dockwise-accentGreen/40'
              : 'bg-dockwise-accentRed/20 text-[#7A2E26] border border-dockwise-accentRed/40'
          }`}
        >
          {actionMessage.text}
        </div>
      )}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-0 overflow-hidden">        {/* Panel lewy: Sugestie AI */}
        <div className="relative h-full min-h-0">
          <MailEnvelopeIcon />
          <GlassPanel
            className="h-full ml-6"
            title="Sugestie AI"
            headerRight={
              <label className="flex items-center gap-2 text-sm text-dockwise-steel cursor-pointer select-none">
                <span>{hasMissingFields ? 'ON' : 'OFF'}</span>
                <span
                  className={`relative inline-block w-11 h-6 rounded-full transition-colors ${
                    hasMissingFields ? 'bg-dockwise-accentGreen' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                      hasMissingFields ? 'translate-x-5' : ''
                    }`}
                  />
                </span>
              </label>
            }
          >
            {detailLoading ? (
              <p className="text-dockwise-steel">Wczytywanie danych statku…</p>
            ) : (
              <div className="space-y-5">
                {hasMissingFields && (
                  <p className="text-dockwise-accentRed font-bold text-sm tracking-wide">
                    BRAKUJĄCE INFORMACJE!
                  </p>
                )}

                <div>
                  <h3 className="font-semibold text-dockwise-navy mb-1">Armator:</h3>
                  <p className="text-dockwise-navy/90">
                    {company?.company_name || (
                      <HighlightField tone="pink">brak danych</HighlightField>
                    )}
                  </p>
                  {company?.is_sanctioned && (
                    <p className="text-dockwise-accentRed text-sm mt-1 font-medium">
                      ⚠ Firma oznaczona jako objęta sankcjami
                    </p>
                  )}
                </div>

                <div>
                  <h3 className="font-semibold text-dockwise-navy mb-1">Informacje o statku:</h3>
                  {vessel ? (
                    <ul className="text-dockwise-navy/90 space-y-1">
                      <li>Nazwa: {vessel.current_vessel_name}</li>
                      <li>Numer IMO: {vessel.imo_number}</li>
                      {specs?.length_overall_meters && (
                        <li>
                          Długość statku:{' '}
                          {detail.fields_missing.includes('length_overall_meters') ? (
                            <HighlightField>{specs.length_overall_meters}m</HighlightField>
                          ) : (
                            `${specs.length_overall_meters}m`
                          )}
                        </li>
                      )}
                      {specs?.draft_meters && <li>Zanurzenie: {specs.draft_meters}m</li>}
                      {specs?.deadweight_tonnage && <li>DWT: {specs.deadweight_tonnage}t</li>}
                    </ul>
                  ) : (
                    <p className="text-dockwise-steel italic">Statek nie zidentyfikowany w bazie referencyjnej.</p>
                  )}
                </div>

                {detail?.requested_services?.length > 0 && (
                  <div>
                    <h3 className="font-semibold text-dockwise-navy mb-1">Wymagane usługi:</h3>
                    <ul className="text-dockwise-navy/90 space-y-1">
                      {detail.requested_services.map((s) => (
                        <li key={s.service_order_id}>
                          {SERVICE_LABELS[s.service_type] || s.service_type}
                          {s.notes ? ` — ${s.notes}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div>
                  <h3 className="font-semibold text-dockwise-navy mb-1">Planowane dotarcie do portu:</h3>
                  <p className="text-dockwise-navy/90">
                    {detail?.eta ? formatDateTime(detail.eta) : (
                      <HighlightField>brak danych ETA</HighlightField>
                    )}
                  </p>
                </div>

                <div className="pt-2 text-xs text-dockwise-steel/80 border-t border-dockwise-steel/10">
                  Status: {STATUS_LABELS[detail?.status] || detail?.status}
                  {detail?.confidence_score != null && (
                    <span> · Pewność ekstrakcji AI: {Math.round(detail.confidence_score * 100)}%</span>
                  )}
                </div>
              </div>
            )}
          </GlassPanel>
        </div>

        {/* Panel prawy: Port + pogoda */}
        <GlassPanel className="h-full" title={detail?.destination_port?.port_name || 'Port docelowy'}>
          <div className="space-y-6">
            <div>
              <h3 className="font-semibold text-dockwise-navy mb-1">Aktualna pogoda:</h3>
              <p className="text-dockwise-navy/90">
                Wiatr: <HighlightField>~15 m/s</HighlightField> · Fala: 1.5 m · Temp.: 12°C
              </p>
              <p className="text-dockwise-steel text-sm mt-1 italic">
                Dane orientacyjne - integracja z serwisem pogodowym w przygotowaniu.
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-dockwise-navy mb-1">Dane techniczne:</h3>
              {specs ? (
                <ul className="text-dockwise-navy/90 space-y-1">
                  <li>Tonaż brutto (GT): {specs.gross_tonnage ?? '—'}</li>
                  <li>DWT: {specs.deadweight_tonnage ?? '—'}</li>
                  <li>Pojemność kontenerowa: {specs.container_capacity_teu ?? '—'} TEU</li>
                  <li>Klasa lodowa: {specs.has_ice_class ? specs.ice_class_designation : 'Brak'}</li>
                </ul>
              ) : (
                <p className="text-dockwise-steel italic">Brak danych technicznych w bazie referencyjnej.</p>
              )}
            </div>

            {berthRecommendations?.recommendations?.length > 0 && (
              <div>
                <h3 className="font-semibold text-dockwise-navy mb-1">Rekomendowane nabrzeża:</h3>
                <ul className="space-y-2">
                  {berthRecommendations.recommendations.map((rec) => (
                    <li key={rec.berth.berth_id} className="bg-dockwise-mist rounded-lg px-3 py-2">
                      <span className="font-medium text-dockwise-navy">
                        {rec.berth.berth_name || rec.berth.berth_code}
                      </span>
                      <span className="text-dockwise-steel text-sm"> · wynik {rec.score.toFixed(1)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {berthRecommendations?.warning && (
              <p className="text-dockwise-accentRed text-sm">{berthRecommendations.warning}</p>
            )}
          </div>
        </GlassPanel>
      </div>

      <div className="mt-4 max-w-sm space-y-2.5 flex-shrink-0">
        <ActionButton variant="accept" onClick={handleAccept} loading={actionLoading === 'accept'}>
          Zaakceptuj zgłoszenie
        </ActionButton>
        <ActionButton variant="redirect" onClick={handleRedirect} loading={actionLoading === 'redirect'}>
          Przekieruj do innego portu
        </ActionButton>
        <ActionButton variant="request" onClick={handleRequestMoreInfo} loading={actionLoading === 'request'}>
          Poproś o uzupełnienie danych
        </ActionButton>
      </div>
    </div>
  );
}
