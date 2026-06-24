import GlassPanel from '../components/GlassPanel';
import { SERVICE_LABELS } from '../utils/format';

const SERVICE_TYPES = Object.entries(SERVICE_LABELS);

export default function ProvidersPage() {
  return (
    <div className="max-w-4xl mx-auto h-full">
      <GlassPanel title="Dostawcy usług">
        <div className="bg-dockwise-accentYellow/20 border border-dockwise-accentYellow/50 rounded-lg px-4 py-3 mb-6">
          <p className="text-[#5C4A00] text-sm">
            Baza konkretnych dostawców (kontakty, dane operacyjne) nie jest jeszcze podłączona
            do backendu — to obszar zaplanowany na kolejny etap. Poniżej lista typów usług,
            które system już rozpoznaje i przypisuje do nominacji na podstawie treści maila.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {SERVICE_TYPES.map(([key, label]) => (
            <div key={key} className="bg-dockwise-mist rounded-lg px-3 py-2.5 text-sm text-dockwise-navy font-medium">
              {label}
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
