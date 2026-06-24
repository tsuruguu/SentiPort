export const mockNominationDetail = {
  nomination_id: "123e4567-e89b-12d3-a456-426614174000",
  status: "parsed_pending_review",
  vessel: {
    imo_number: "9432652",
    current_vessel_name: "Valdemar Construction"
  },
  vessel_technical_specs: {
    length_overall_meters: 450, // Celowo błąd logiczny dla statku, by AI to wyłapało
    beam_meters: 40,
    draft_meters: 14.5
  },
  nominating_company: {
    company_name: "Maersk Line A/S"
  },
  eta: "2026-07-15T14:00:00Z",
  source_email_body_raw: "Hababababahababababba\nhabababba\nhababababab"
};

// Wynik z agenta elevenLabs do walidacji danych (z vessel_enrichment.py)
export const mockEnrichmentData = {
  inconsistencies_to_clarify: [
    {
      field_name: "length_overall_meters",
      description: "Podana długość statku (450m) przekracza limity konstrukcyjne dla tej klasy. Weryfikacja rejestru wskazuje na 399m.",
      severity: "high"
    }
  ]
};

export const mockMailbox = {
  items: [
    {
      nomination_id: "1",
      nominating_company: { company_name: "qdad...." },
      source_email_subject: "wiadomość oryginalna fdjkfvawkfpkwafawgv......."
    },
    {
      nomination_id: "2",
      nominating_company: { company_name: "qdad...." },
      source_email_subject: "wiadomość oryginalna fdjkfvawkfpkwafawgv......."
    }
  ]
};

export const mockWeatherData = {
  wind_speed_ms: 12.5,
  description: "Częściowe zachmurzenie, możliwe przelotne opady."
};