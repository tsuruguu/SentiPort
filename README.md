# Port Nomination & Vessel Risk Intelligence Platform — Database Documentation

A database supporting the automation of shipowner nomination processes, vessel risk assessment, and port operations. Built on PostgreSQL 16 with the PostGIS, pg_trgm, btree_gist, and pgcrypto extensions.

Schema: `port_intel`

## Table of Contents

- [Industry Standards](#industry-standards)
- [Architecture — 4 Layers](#architecture--4-layers)
- [Reference / Lookup Tables](#reference--lookup-tables)
- [Vessels and Owners (Master Data)](#vessels-and-owners-master-data)
- [Risk, Sanctions, Port State Control](#risk-sanctions-port-state-control)
- [Nominations, Port Calls, Cargo](#nominations-port-calls-cargo)
- [Views](#views)
- [Functions](#functions)
- [Relationship Diagram](#relationship-diagram)

---

## Industry Standards

The schema doesn't invent its own classifications from scratch — it's built on real maritime standards, which makes integration with external systems (AIS, PCS, PSC) easier and supports commercialization across different ports:

| Standard | Application in the database |
|---|---|
| **IMO Number** | Unique, immutable vessel identifier (`vessels.imo_number`) — a vessel can change its name and flag, but never its IMO Number |
| **IMO Company Number** | Owner/operator identifier (`companies.imo_company_number`) |
| **MMSI** | Maritime Mobile Service Identity, AIS identifier (`vessels.mmsi`) |
| **UN/LOCODE** | Port identification, 5-character code (`ports.un_locode`) |
| **ITU-R M.1371** | AIS vessel type category (`vessel_type_reference.ais_category`) |
| **IHS StatCode5** | Granular vessel type classification (`vessel_type_reference.statcode5_label`) |
| **ISO 3166-1** | Country codes (`countries.iso_alpha2/iso_alpha3`) |
| **ISO 4217** | Currency codes (`currencies.currency_code`) |
| **Paris MoU / Tokyo MoU** | Ship Risk Profile — flag state classification (white/grey/black list) and a PSC-inspection-based risk model |
| **ISPS Code** | Port and vessel security compliance (`ports.is_isps_compliant`, document types like `isps_security_declaration`) |
| **IMDG Code** | Dangerous goods cargo classes (`cargo_manifests.imdg_hazard_class`) |
| **OFAC SDN / EU Consolidated List / UK HMT** | Sanctions lists (`sanctions_screening_results.list_source`) |

---

## Architecture — 4 Layers

```
1. ENTITY REGISTRY (Master Data)
   vessels, companies, company_contacts, vessel_company_roles, vessel_name_history

2. TECHNICAL DATA AND COMPLIANCE
   vessel_technical_specs, vessel_certificates, psc_inspections, psc_deficiencies

3. RISK AND COMPLIANCE
   vessel_risk_assessments, vessel_risk_assessment_factors,
   risk_factor_definitions, sanctions_screening_results

4. PORT OPERATIONS
   ports, berths, berth_occupancy, port_weather_history,
   nominations, nomination_unstructured_notes, port_calls,
   cargo_manifests, port_service_orders, generated_documents
```

Guiding principle: **risk is insert-only and fully auditable** — every risk assessment is a new row, never an overwrite of a previous one. Risk factor weights are configurable per port (`risk_factor_definitions`), which supports commercialization without any code changes.

---

## Reference / Lookup Tables

Generic, port-independent tables — these let the system scale to any port worldwide without structural changes.

### `countries`
Country lookup table (ISO 3166-1), extended with the Paris MoU classification used to assess flag-state risk.

| Column | Description |
|---|---|
| `country_id` | PK, smallint |
| `iso_alpha2` / `iso_alpha3` | ISO 3166-1 codes |
| `country_name` | Country name |
| `paris_mou_flag_tier` | `white` / `grey` / `black` / `not_assessed` — flag risk classification |
| `is_eu_member` | Whether the country is an EU member |
| `is_sanctioned_jurisdiction` | Quick filter for state-level embargoes |

Used by: `ports`, `vessels`, `companies`, `classification_societies`, `vessel_name_history`, `cargo_manifests` (cargo origin/destination country).

### `currencies`
Currency lookup table (ISO 4217) for port service billing. Columns: `currency_code` (PK, e.g. `EUR`), `currency_name`, `minor_unit`.

### `ports`
Generic worldwide port registry, identified by UN/LOCODE — not limited to the Tri-City area (Gdynia/Gdańsk/Sopot).

| Column | Description |
|---|---|
| `port_id` | PK, UUID |
| `un_locode` | Unique port code (e.g. `PLGDY` = Gdynia) |
| `location` | `GEOGRAPHY(POINT, 4326)` — coordinates (PostGIS) |
| `max_draft_meters` / `max_loa_meters` / `max_beam_meters` | Port entry limits |
| `has_icebreaker_support` | Whether the port has icebreaker support |
| `has_cold_storage_facility` | Cold storage / "igloport" facilities |
| `is_isps_compliant` | ISPS Code compliance |

### `berths`
Berths/terminals within a port — key for matching a vessel to the right location.

| Column | Description |
|---|---|
| `berth_id` | PK, UUID |
| `port_id` | FK → `ports` |
| `max_draft_meters` / `max_loa_meters` / `max_dwt_tonnes` | Berth technical limits |
| `supports_dangerous_goods` | Whether the berth can handle dangerous goods |
| `supports_reefer_containers` | Reefer container plug points |
| `crane_capacity_tonnes` | Maximum crane lifting capacity |

### `berth_occupancy`
Berth occupancy schedule. Prevents double-booking via `EXCLUDE USING gist` on the `tstzrange(occupied_from, occupied_until)` time range.

### `port_weather_history`
Historical and current weather data per port (e.g. fed from the StormGlass.io API). Includes `raw_payload JSONB` to store the full API response for audit/reprocessing purposes. Fields: wind speed/direction, wave height, air/water temperature, visibility, ice presence and thickness.

### `vessel_type_reference`
Granular vessel type lookup (in the spirit of IHS StatCode5), with a baseline risk level per type.

| Column | Description |
|---|---|
| `vessel_type_id` | PK, smallserial |
| `type_family` | ENUM: `container_ship`, `bulk_carrier`, `oil_tanker`, `lng_carrier`, `reefer_cargo`, `icebreaker`, `naval_combatant`, etc. (25 values) |
| `ais_category` | AIS category per ITU-R M.1371 |
| `typical_risk_baseline` | Baseline risk score 0–100 for this type (e.g. crude oil tanker = 70, fishing boat = 10) |
| `requires_icebreaker_priority` | Whether the type requires priority icebreaker access (e.g. reefer cargo ships) |

### `classification_societies`
Vessel classification societies (DNV, Lloyd's Register, ABS, Bureau Veritas, etc.). The `is_iacs_member` flag — societies that are **not** IACS members increase a vessel's risk score (a well-known red flag in the industry).

---

## Vessels and Owners (Master Data)

### `vessels`
**The central vessel table.** `imo_number` is the immutable business identifier — a vessel can change its name and flag, but never its IMO Number.

| Column | Description |
|---|---|
| `vessel_id` | PK, UUID |
| `imo_number` | UNIQUE, validated against the regex `^[0-9]{7}$` |
| `mmsi` | Validated against the regex `^[0-9]{9}$` |
| `current_vessel_name` | Current name (history tracked in `vessel_name_history`) |
| `domain` | ENUM: `commercial`, `military`, `government`, `civilian_private`, `research_scientific`, `fishing`, `unknown` |
| `vessel_type_id` | FK → `vessel_type_reference` |
| `flag_country_id` | FK → `countries` |
| `classification_society_id` | FK → `classification_societies` |
| `is_active` | FALSE = retired/scrapped |

### `vessel_name_history`
History of vessel names and flags. Vessels frequently change name/flag after a change of ownership ("flag hopping") — this can itself be a risk signal, which is why the history is tracked rather than overwritten.

### `vessel_technical_specs`
Vessel technical data, **versioned over time** (`effective_from` / `effective_until`) — allows tracking changes after refits.

| Column | Description |
|---|---|
| `length_overall_meters`, `beam_meters`, `draft_meters`, `air_draft_meters` | Vessel dimensions (LOA, beam, draft, air draft above the waterline) |
| `gross_tonnage`, `net_tonnage`, `deadweight_tonnage` | GT, NT, DWT |
| `has_ice_class`, `ice_class_designation` | Ice class (e.g. `PC6`, `1A Super`) |
| `container_capacity_teu` | TEU capacity (if a container ship) |
| `has_reefer_plugs`, `reefer_plug_count` | Reefer container plug points |

### `companies`
All corporate entities in the ecosystem: shipowners, operators, technical managers, crewing agents, P&I Clubs. A single table for all entity types — the specific **role** relative to a vessel is defined in `vessel_company_roles`.

| Column | Description |
|---|---|
| `imo_company_number` | IMO Unique Company Identifier (if known) |
| `ownership_transparency_flag` | FALSE = opaque ownership structure (a risk factor) |
| `is_sanctioned` | Cached screening result — source of truth is `sanctions_screening_results` |

### `company_contacts`
Contact persons at companies (first name, last name, email, phone), sourced from email correspondence. The `is_primary_for_nominations` flag marks the main contact for shipowner nominations.

### `vessel_company_roles`
Vessel ↔ company relationship with a defined role and validity period. The registered owner **may differ** from the commercial operator or technical manager.

| Column | Description |
|---|---|
| `role_type` | ENUM: `registered_owner`, `beneficial_owner`, `commercial_operator`, `technical_manager`, `crewing_agent`, `ship_chandler`, `classification_society`, `p_and_i_club`, `flag_state_authority` |
| `is_current` | A partial unique index guarantees a single current role of each type per vessel |

### `vessel_certificates`
Vessel certificates — ISM Safety Management Certificate, ISSC (ISPS), class certificates, and other compliance documents. Validity is computed dynamically in the `v_vessel_certificates_status` view (not as a generated column, since `CURRENT_DATE` is not IMMUTABLE in PostgreSQL).

---

## Risk, Sanctions, Port State Control

The heart of the compliance system — built on real Paris MoU / Tokyo MoU frameworks and OFAC/EU/UK sanctions lists.

### `psc_inspections`
Port State Control inspection history. Deficiency and detention counts are empirically validated risk predictors under the Paris/Tokyo MoU framework.

| Column | Description |
|---|---|
| `deficiency_count` | Number of deficiencies found during the inspection |
| `was_detained` | Whether the vessel was detained |
| `detention_days` | Number of days detained |

### `psc_deficiencies`
Detailed deficiencies found during an inspection, with a harmonized code (Paris MoU code list) and a severity level (`low` / `medium` / `high` / `detainable`).

### `sanctions_screening_results`
Sanctions screening results. **Polymorphic reference** — can relate to a vessel OR a company (a constraint enforces that at least one must be set). Insert-only: every screening run is a new row, for full audit purposes.

| Column | Description |
|---|---|
| `list_source` | ENUM: `ofac_sdn`, `eu_consolidated`, `uk_hmt`, `un_security_council`, `other_national` |
| `screening_result` | ENUM: `clear`, `potential_match`, `confirmed_match`, `false_positive` |
| `match_confidence_pct` | Match confidence, 0–100% |

### `risk_factor_definitions`
**Configurable catalog of risk factors with weights.** This is the key to commercialization — every port can have its own risk policy without any code changes, just by adjusting the weights in this table.

| Column | Description |
|---|---|
| `factor_category` | ENUM: `flag_state_performance`, `vessel_age`, `vessel_type`, `psc_history`, `detention_history`, `sanctions_exposure`, `cargo_hazard_class`, `ownership_transparency`, `classification_society`, `dark_activity`, and others (15 categories) |
| `factor_code` | Unique code, e.g. `FLAG_BLACKLIST`, `SANCTIONS_CONFIRMED` |
| `weight` / `max_score_contribution` | Weight and maximum contribution of the factor to the final score |
| `applicable_port_id` | `NULL` = global policy; a value = port-specific policy |

### `vessel_risk_assessments`
**The main risk assessment results table — a complete, auditable history.** INSERT-ONLY: a new assessment is a new row, never an update of an existing result. The `is_current` flag (backed by a partial unique index) marks the latest assessment per vessel.

| Column | Description |
|---|---|
| `overall_risk_score` | Score, 0–100 |
| `risk_tier` | ENUM: `low_risk`, `standard_risk`, `high_risk`, `critical_risk` |
| `model_version` | Versioning of the scoring algorithm itself |
| `assessment_trigger` | What triggered the assessment: `new_nomination`, `scheduled_recheck`, `manual_review`, `psc_update` |

### `vessel_risk_assessment_factors`
Breakdown of a specific assessment into its component factors — full **explainability** of the scoring. Answers the question "why does this vessel have this score" down to the exact points contributed by a specific factor (e.g. `flag_tier=black` → +25 pts).

---

## Nominations, Port Calls, Cargo

The operational layer — what actually arrives by email from the shipowner, and what happens during a vessel's port call.

### `nominations`
**The main input document of the process** — the shipowner nomination email.

| Column | Description |
|---|---|
| `status` | ENUM: `received`, `parsing`, `parsed_pending_review`, `verified`, `submitted_to_port`, `acknowledged`, `rejected`, `cancelled`, `completed` |
| `eta` / `etd` | Estimated time of arrival/departure |
| `source_email_body_raw` | Full, unmodified email body — kept for audit and re-parsing |
| `llm_extraction_metadata` | `JSONB` with LLM extraction metadata (model, confidence, extracted fields) |

### `nomination_unstructured_notes`
Fragments of the nomination email content that **don't fit any fixed column** — full-text searchable (`pg_trgm` index). Every row has a `requires_human_review` flag, since data extracted by an LLM may need manual verification.

### `port_calls`
A specific vessel's port call — arrival/departure history, building a vessel's "track record" at a given port.

| Column | Description |
|---|---|
| `status` | ENUM: `scheduled`, `inbound`, `arrived_anchorage`, `berthed`, `operations_active`, `operations_complete`, `departed`, `cancelled` |
| `purpose_of_call` | e.g. `cargo_discharge`, `bunkering`, `crew_change` |

### `cargo_manifests`
Cargo declared at nomination and/or confirmed at the port call. A constraint enforces a link to either `nomination_id` or `port_call_id` (at least one).

| Column | Description |
|---|---|
| `imdg_hazard_class` | ENUM matching the IMDG Code: `none` through `class_1_explosives` to `class_9_miscellaneous` |
| `requires_refrigeration`, `target_temperature_celsius` | For cold-storage ports — cargo requiring refrigeration |
| `is_perishable` | Perishable goods |

### `port_service_orders`
Port service orders per port call.

| Column | Description |
|---|---|
| `service_type` | ENUM (17 values): `pilotage`, `towage`, `mooring_unmooring`, `shore_power`, `bunkering_fuel`, `medical_services`, `barber_services`, `ice_breaking_assistance`, and others |
| `status` | ENUM: `requested`, `confirmed`, `in_progress`, `completed`, `cancelled`, `failed` |
| `provider_company_id` | FK → `companies` (e.g. a towage company, a provisions supplier) |

### `generated_documents`
Metadata for PDF documents generated for the port authority. **The binary file lives outside the database** (S3/object storage) — the database only stores `file_url` and `file_hash_sha256`.

| Column | Description |
|---|---|
| `document_type` | ENUM: `port_entry_notification`, `pre_arrival_notification`, `cargo_declaration`, `dangerous_goods_declaration`, `isps_security_declaration`, `crew_list`, and others |
| `status` | ENUM: `draft`, `generated`, `sent`, `acknowledged_by_port`, `rejected_by_port`, `superseded` |
| `supersedes_document_id` | Self-referencing FK — tracks the document's version chain |

---

## Views

Views don't have their own Foreign Key constraints (their join logic is embedded in the `SELECT` definition), so they don't appear as connected nodes in the relationship diagram — that's expected PostgreSQL behavior, not a bug.

### `v_vessel_current_risk`
Quick overview: current risk score and tier for every vessel in the registry (joins `vessels`, `vessel_type_reference`, `countries`, `vessel_risk_assessments` filtered to `is_current = TRUE`).

### `v_nomination_summary`
The port agent's working view: all nominations with risk context, ready to filter on a dashboard.

### `v_berth_availability`
Current berth availability — whether occupied right now, and for what time window (based on `berth_occupancy` and the current `now()`).

### `v_vessel_certificates_status`
Vessel certificates with validity status computed dynamically against `CURRENT_DATE`.

---

## Functions

### `calculate_vessel_risk_score(p_vessel_id, p_nomination_id, p_port_call_id, p_trigger, p_assessed_by)`

Calculates and stores (insert-only) a new vessel risk assessment based on the configurable weights in `risk_factor_definitions`. Marks the previous assessment as outdated (`is_current = FALSE`) and inserts a new one, along with a full factor breakdown in `vessel_risk_assessment_factors`. Returns the `assessment_id` of the newly created assessment.

Evaluates, among other things: flag status on the Paris MoU list, vessel age, vessel type (tanker/gas carrier), PSC deficiency and detention history, sanctions screening results, cargo IMDG class, classification society IACS status, and ownership structure transparency.

```sql
SELECT calculate_vessel_risk_score('<vessel_uuid>');
```
