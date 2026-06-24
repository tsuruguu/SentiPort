export const mockNominationDetail = {
  nomination_id: "123e4567-e89b-12d3-a456-426614174000",
  status: "parsed_pending_review",
  vessel: {
    imo_number: "9432652",
    current_vessel_name: "Valdemar Construction"
  },
  vessel_technical_specs: {
    length_overall_meters: 450,
    beam_meters: 40,
    draft_meters: 14.5
  },
  nominating_company: {
    company_name: "Maersk Line A/S"
  },
  eta: "2026-07-15T14:00:00Z",
  cargo_items: [
    { description: "Chemikalia przemysłowe", imdg_hazard_class: "class_3_flammable_liquids", un_number: "UN 1203" }
  ],
  confidence_score: 0.85,
  fields_missing: ["has_reefer_plugs", "ice_class_designation"]
};

export const mockEnrichmentData = {
  confidence_score: 0.92,
  inconsistencies_to_clarify: [
    {
      field_name: "length_overall_meters",
      description: "Podana długość statku (450m) przekracza limity rejestrowe.",
      severity: "high"
    }
  ],
  proposed_configuration: [
    { field_name: "draft_meters", proposed_value: "14.5", is_inferred: true, confidence: 0.88, source_note: "Historia wizyt" }
  ]
};

export const mockRiskData = {
  overall_risk_score: 75.5,
  risk_tier: "high_risk",
  paris_mou_tier: "grey",
  sanctions_clear: true,
  psc_detentions: 1
};

export const mockMailbox = {
  items: [
    { nomination_id: "1", nominating_company: { company_name: "Maersk Line A/S" }, source_email_subject: "Awizacja statku Valdemar Construction" },
    { nomination_id: "2", nominating_company: { company_name: "MSC" }, source_email_subject: "Zgłoszenie ładunku - MSC Zoe" },
    { nomination_id: "3", nominating_company: { company_name: "Hapag-Lloyd" }, source_email_subject: "Zmiana ETA - Berlin Express" }
  ]
};

export const mockWeatherData = {
  wind_speed_ms: 12.5,
  description: "Częściowe zachmurzenie, możliwe przelotne opady."
};