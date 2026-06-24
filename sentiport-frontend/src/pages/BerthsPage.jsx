import { useState, useEffect } from 'react';
import { useApiData } from '../hooks/useApiData';
import { portsApi } from '../api/ports';
import GlassPanel from '../components/GlassPanel';

export default function BerthsPage() {
  const [selectedPortId, setSelectedPortId] = useState(null);

  const { data: ports, loading: portsLoading } = useApiData(() => portsApi.list(), []);

  // Gdy lista portów się wczyta, domyślnie wybieramy pierwszy port -
  // ale jako PRAWDZIWĄ zmianę stanu (setSelectedPortId), nie jako
  // osobno liczoną wartość pomocniczą. Inaczej fetch nabrzeży (zależny
  // od selectedPortId) i podświetlenie w UI (które liczyło activePortId
  // niezależnie) rozjeżdżały się o jeden klik - to było źródło "migania"
  // (klikasz port X, ale fetch wciąż dotyczy poprzednio wybranego portu).
  useEffect(() => {
    if (!selectedPortId && ports && ports.length > 0) {
      setSelectedPortId(ports[0].port_id);
    }
  }, [ports, selectedPortId]);

  const { data: berths, loading: berthsLoading } = useApiData(
    () => (selectedPortId ? portsApi.berths(selectedPortId) : Promise.resolve([])),
    [selectedPortId]
  );

  return (
    <div className="max-w-5xl mx-auto h-full grid grid-cols-1 md:grid-cols-3 gap-6">
      <GlassPanel title="Porty" className="md:col-span-1">
        {portsLoading && <p className="text-dockwise-steel">Wczytywanie…</p>}
        <ul className="space-y-2">
          {ports?.map((port) => (
            <li key={port.port_id}>
              <button
                type="button"
                onClick={() => setSelectedPortId(port.port_id)}
                className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                  selectedPortId === port.port_id
                    ? 'bg-dockwise-steel text-white'
                    : 'hover:bg-dockwise-mist text-dockwise-navy'
                }`}
              >
                {port.port_name}
                <span className="text-xs opacity-70 ml-2">{port.un_locode}</span>
              </button>
            </li>
          ))}
        </ul>
      </GlassPanel>

      <GlassPanel title="Nabrzeża" className="md:col-span-2">
        {!selectedPortId && <p className="text-dockwise-steel">Wybierz port z listy.</p>}
        {berthsLoading && <p className="text-dockwise-steel">Wczytywanie nabrzeży…</p>}

        {berths && berths.length === 0 && !berthsLoading && (
          <p className="text-dockwise-steel italic">Brak zarejestrowanych nabrzeży dla tego portu.</p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {berths?.map((berth) => (
            <div key={berth.berth_id} className="bg-dockwise-mist rounded-xl p-4">
              <h3 className="font-semibold text-dockwise-navy">{berth.berth_name || berth.berth_code}</h3>
              <dl className="text-sm text-dockwise-steel mt-2 space-y-0.5">
                <div>Max zanurzenie: {berth.max_draft_meters ?? '—'} m</div>
                <div>Max LOA: {berth.max_loa_meters ?? '—'} m</div>
                <div>Max DWT: {berth.max_dwt_tonnes ?? '—'} t</div>
              </dl>
              <div className="flex flex-wrap gap-1.5 mt-3">
                {berth.supports_dangerous_goods && <Tag>Towary niebezpieczne</Tag>}
                {berth.supports_reefer_containers && <Tag>Kontenery reefer</Tag>}
                {berth.supports_ro_ro && <Tag>Ro-Ro</Tag>}
                {berth.has_shore_power && <Tag>Prąd z lądu</Tag>}
              </div>
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}

function Tag({ children }) {
  return (
    <span className="text-[11px] bg-dockwise-steel/15 text-dockwise-steel font-medium px-2 py-0.5 rounded-full">
      {children}
    </span>
  );
}