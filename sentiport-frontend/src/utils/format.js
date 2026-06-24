export function formatDateTime(isoString) {
  if (!isoString) return null;
  const date = new Date(isoString);
  return date.toLocaleString('pl-PL', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export function formatNumber(value, unit = '') {
  if (value === null || value === undefined) return null;
  return `${value}${unit}`;
}

export const STATUS_LABELS = {
  received: 'Odebrana',
  parsing: 'W trakcie przetwarzania',
  parsed_pending_review: 'Czeka na przegląd',
  verified: 'Zweryfikowana',
  submitted_to_port: 'Złożona do portu',
  acknowledged: 'Potwierdzona przez port',
  rejected: 'Odrzucona',
  cancelled: 'Anulowana',
  completed: 'Zakończona',
};

export const SERVICE_LABELS = {
  pilotage: 'Pilotaż',
  towage: 'Holowanie',
  mooring_unmooring: 'Cumowanie/odcumowanie',
  shore_power: 'Prąd z lądu',
  fresh_water_supply: 'Dostawa wody pitnej',
  bunkering_fuel: 'Bunkrowanie paliwa',
  waste_removal: 'Odbiór odpadów',
  medical_services: 'Usługi medyczne',
  barber_services: 'Usługi fryzjerskie',
  provisions_supply: 'Dostawa prowiantu',
  crew_change: 'Zmiana załogi',
  customs_clearance: 'Odprawa celna',
  security_isps: 'Bezpieczeństwo / ISPS',
  cargo_surveying: 'Inspekcja ładunku',
  ice_breaking_assistance: 'Asysta lodołamacza',
  waste_water_pumpout: 'Odbiór wód zaolejonych',
  other: 'Inne',
};
