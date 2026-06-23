-- ============================================================================
-- PORT NOMINATION & VESSEL RISK INTELLIGENCE PLATFORM
-- ============================================================================
-- Hakaton: Hackathon Morski - Kongres Polskie Porty 2030
-- Projekt: Automatyzacja procesu nominacji armatorskich (Redsky AI / MAG)
--
-- Silnik docelowy: PostgreSQL 16+
-- Wymagane rozszerzenia: uuid-ossp, postgis, pg_trgm, btree_gist, pgcrypto
--
-- STANDARDY BRANŻOWE ZASTOSOWANE W TYM SCHEMACIE:
--   - IMO Number              -> unikalny identyfikator statku (7 cyfr, na całe życie statku)
--   - IMO Company Number       -> unikalny identyfikator armatora/operatora
--   - MMSI                      -> Maritime Mobile Service Identity (AIS)
--   - UN/LOCODE                  -> identyfikacja portów (5-znakowy kod UN)
--   - ITU-R M.1371                -> AIS Ship Type Code (kategoria statku)
--   - IHS StatCode5                 -> granularna klasyfikacja typu statku (branżowy standard)
--   - ISO 3166-1 alpha-2/3            -> kody krajów (flaga, narodowość)
--   - ISO 4217                         -> kody walut
--   - Paris MoU / Tokyo MoU             -> Ship Risk Profile (HRS / SRS / LRS) - Port State Control
--   - ISPS Code                          -> bezpieczeństwo portów i statków
--   - IMDG Code                           -> klasy ładunków niebezpiecznych
--   - OFAC SDN / UE Consolidated / UK HMT  -> listy sankcyjne
--
-- ARCHITEKTURA (4 warstwy):
--   1. Rejestr podmiotów (Master Data)    -> vessels, companies, vessel_company_roles
--   2. Dane techniczne i zgodność          -> vessel_technical_specs, vessel_certificates, psc_inspections
--   3. Ryzyko i compliance                  -> vessel_risk_assessments, risk_factor_definitions, sanctions_screening_results
--   4. Operacje portowe                      -> ports, berths, nominations, port_calls, cargo_manifests, service_orders
--
-- ZASADY PROJEKTOWE:
--   - Risk score jest W PEŁNI AUDYTOWALNY: insert-only, każda ocena to nowy wiersz
--   - Schemat jest GENERYCZNY: nie tylko Trójmiasto, dowolny port świata (UN/LOCODE)
--   - Wagi czynników ryzyka są KONFIGUROWALNE per port (risk_factor_definitions),
--     co pozwala na komercjalizację bez zmiany kodu
--   - Dane niesklasyfikowane z maili trafiają do osobnej, przeszukiwalnej tabeli
--     (nomination_unstructured_notes), nic nie jest gubione
--   - Wygenerowane dokumenty PDF są śledzone w bazie (metadane + URL do storage),
--     plik binarny żyje poza bazą (S3/object storage)
--
-- Autor: wygenerowane i przetestowane end-to-end na PostgreSQL 16 + PostGIS 3.4
-- Status: Zweryfikowane - cały plik wykonuje się bezbłędnie na czystej bazie,
--         funkcja calculate_vessel_risk_score() przetestowana na 4 statkach demo
-- ============================================================================



-- ============================================================================
-- PORT NOMINATION & RISK INTELLIGENCE PLATFORM
-- Część 1: Rozszerzenia PostgreSQL oraz typy wyliczeniowe (ENUM)
--
-- Standardy referencyjne zastosowane w tym schemacie:
--   - UN/LOCODE          -> identyfikacja portów (5-znakowy kod UN)
--   - IMO Number          -> unikalny identyfikator statku (7 cyfr, na całe życie statku)
--   - IMO Company Number  -> unikalny identyfikator armatora/operatora
--   - MMSI                -> Maritime Mobile Service Identity (AIS)
--   - ITU-R M.1371        -> AIS Ship Type Code (kategoria statku)
--   - IHS StatCode5        -> granularna klasyfikacja typu statku (branżowy standard)
--   - ISO 3166-1 alpha-2/3 -> kody krajów (flaga, narodowość)
--   - ISO 4217             -> kody walut
--   - Paris MoU / Tokyo MoU -> Ship Risk Profile (HRS / SRS / LRS) - Port State Control
--   - ISPS Code             -> bezpieczeństwo portów i statków
--   - IGC Code / IMSBC Code -> dot. ładunków niebezpiecznych / luzem
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS port_intel;
SET search_path TO port_intel, public;

-- Rozszerzenia
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- generowanie UUID
CREATE EXTENSION IF NOT EXISTS postgis;          -- dane geoprzestrzenne (porty, nabrzeża, trasy)
CREATE EXTENSION IF NOT EXISTS pg_trgm;          -- fuzzy matching tekstu (nazwy statków/armatorów z maili)
CREATE EXTENSION IF NOT EXISTS btree_gist;        -- wymagane do EXCLUDE USING gist na rezerwacjach nabrzeży
CREATE EXTENSION IF NOT EXISTS pgcrypto;          -- funkcje kryptograficzne (hash dokumentów, itp.)

-- ----------------------------------------------------------------------------
-- ENUM: Ogólna klasyfikacja statku (wysoki poziom, biznesowy)
-- ----------------------------------------------------------------------------
CREATE TYPE vessel_domain AS ENUM (
    'commercial',       -- komercyjny (handlowy)
    'military',         -- wojskowy
    'government',        -- rządowy / niewojskowy (np. straż graniczna, hydrografia)
    'civilian_private',   -- cywilny prywatny (jachty, łodzie rekreacyjne)
    'research_scientific',-- statki badawcze
    'fishing',            -- rybackie
    'unknown'             -- nieznany / niezweryfikowany
    );

-- ----------------------------------------------------------------------------
-- ENUM: AIS Ship Type - pierwsza cyfra kategorii (ITU-R M.1371 / SN.1/Circ.227)
-- ----------------------------------------------------------------------------
CREATE TYPE ais_ship_type_category AS ENUM (
    'reserved',           -- 1x
    'wing_in_ground',     -- 2x
    'special_category_a', -- 3x (np. tugi, dredgers, łodzie nurkowe, ratownicze)
    'high_speed_craft',   -- 4x
    'special_category_b', -- 5x (statki pilotowe, antyterrorystyczne, jednostki władz)
    'passenger',          -- 6x
    'cargo',              -- 7x
    'tanker',             -- 8x
    'other'               -- 9x
    );

-- ----------------------------------------------------------------------------
-- ENUM: Granularny typ statku (oparty na IHS StatCode5 / praktyce branżowej)
-- Niewyczerpujący - tabela vessel_type_reference (poniżej) jest źródłem prawdy,
-- ten ENUM służy do szybkiego filtrowania i UI.
-- ----------------------------------------------------------------------------
CREATE TYPE vessel_type_family AS ENUM (
    'container_ship',
    'bulk_carrier',
    'general_cargo',
    'ro_ro_cargo',
    'ro_pax',
    'oil_tanker',
    'chemical_tanker',
    'lng_carrier',
    'lpg_carrier',
    'crude_oil_tanker',
    'passenger_cruise',
    'ferry',
    'fishing_vessel',
    'tug',
    'icebreaker',
    'pilot_vessel',
    'dredger',
    'offshore_supply',
    'research_vessel',
    'naval_combatant',
    'naval_auxiliary',
    'yacht_pleasure_craft',
    'reefer_cargo',          -- chłodniowiec (ważne pod igloporty)
    'heavy_lift_cargo',
    'other_unclassified'
    );

-- ----------------------------------------------------------------------------
-- ENUM: Status nominacji armatorskiej (workflow)
-- ----------------------------------------------------------------------------
CREATE TYPE nomination_status AS ENUM (
    'received',            -- mail wpłynął, jeszcze nieprzetworzony
    'parsing',             -- w trakcie ekstrakcji danych (LLM/agent)
    'parsed_pending_review', -- sparsowane, czeka na weryfikację agenta
    'verified',            -- zweryfikowane przez agenta portowego
    'submitted_to_port',   -- dokumenty wysłane do kapitanatu portu
    'acknowledged',        -- kapitanat potwierdził przyjęcie
    'rejected',            -- kapitanat odrzucił (np. brak dokumentacji)
    'cancelled',           -- nominacja odwołana przez armatora
    'completed'            -- wizyta portowa zakończona
    );

-- ----------------------------------------------------------------------------
-- ENUM: Status wizyty statku w porcie
-- ----------------------------------------------------------------------------
CREATE TYPE port_call_status AS ENUM (
    'scheduled',
    'inbound',           -- statek w drodze / pilot na pokładzie
    'arrived_anchorage',  -- na redzie, czeka na nabrzeże
    'berthed',            -- przy nabrzeżu
    'operations_active',  -- trwają operacje przeładunkowe
    'operations_complete',
    'departed',
    'cancelled'
    );

-- ----------------------------------------------------------------------------
-- ENUM: Poziom ryzyka (zgodny z Paris MoU / Tokyo MoU Ship Risk Profile)
-- ----------------------------------------------------------------------------
CREATE TYPE risk_tier AS ENUM (
    'low_risk',       -- LRS - Low Risk Ship
    'standard_risk',  -- SRS - Standard Risk Ship
    'high_risk',      -- HRS - High Risk Ship
    'critical_risk'   -- rozszerzenie własne: powyżej HRS, np. aktywne sankcje
    );

-- ----------------------------------------------------------------------------
-- ENUM: Kategoria czynnika ryzyka (do tabeli konfigurowalnych wag)
-- ----------------------------------------------------------------------------
CREATE TYPE risk_factor_category AS ENUM (
    'flag_state_performance',   -- wydajność/historia państwa flagi (Paris MoU white/grey/black list)
    'vessel_age',
    'vessel_type',
    'psc_history',               -- historia inspekcji Port State Control
    'detention_history',
    'sanctions_exposure',        -- sankcje OFAC/UE/UK
    'cargo_hazard_class',        -- IMDG/IMSBC/IGC - niebezpieczny ładunek
    'ownership_transparency',    -- nieprzejrzysta struktura własności
    'classification_society',    -- towarzystwo klasyfikacyjne (IACS vs. non-IACS)
    'insurance_p_and_i',         -- pokrycie P&I (Protection & Indemnity)
    'dark_activity',              -- przerwy w transmisji AIS ("dark" periods)
    'port_state_history',         -- historia odwiedzanych portów wysokiego ryzyka
    'crew_nationality_risk',
    'document_completeness',      -- kompletność dokumentacji nominacyjnej
    'other'
    );

-- ----------------------------------------------------------------------------
-- ENUM: Typ podmiotu w relacji do statku (armator rejestrowy vs operator vs manager)
-- ----------------------------------------------------------------------------
CREATE TYPE company_role_type AS ENUM (
    'registered_owner',      -- armator rejestrowy (właściciel formalny)
    'beneficial_owner',      -- właściciel rzeczywisty/beneficjent
    'commercial_operator',    -- operator handlowy / czarterujący
    'technical_manager',      -- manager techniczny (ISM Company)
    'crewing_agent',
    'ship_chandler',
    'classification_society',
    'p_and_i_club',
    'flag_state_authority'
    );

-- ----------------------------------------------------------------------------
-- ENUM: Typ usługi portowej (z notatek: holowniki, prąd, lekarz, barber, etc.)
-- ----------------------------------------------------------------------------
CREATE TYPE port_service_type AS ENUM (
    'pilotage',              -- pilotaż
    'towage',                 -- holowniki
    'mooring_unmooring',       -- cumowanie/odcumowanie
    'shore_power',             -- prąd z lądu
    'fresh_water_supply',
    'bunkering_fuel',          -- dostawa paliwa
    'waste_removal',           -- odbiór odpadów (MARPOL)
    'medical_services',        -- lekarz
    'barber_services',         -- barber (z notatek)
    'provisions_supply',       -- prowiant
    'crew_change',
    'customs_clearance',
    'security_isps',
    'cargo_surveying',
    'ice_breaking_assistance', -- asysta lodołamacza
    'waste_water_pumpout',
    'other'
    );

-- ----------------------------------------------------------------------------
-- ENUM: Status zamówienia usługi portowej
-- ----------------------------------------------------------------------------
CREATE TYPE service_order_status AS ENUM (
    'requested',
    'confirmed',
    'in_progress',
    'completed',
    'cancelled',
    'failed'
    );

-- ----------------------------------------------------------------------------
-- ENUM: Klasa niebezpieczeństwa ładunku (IMDG Code - International Maritime
-- Dangerous Goods) - 9 klas + None dla ładunku niesklasyfikowanego jako DG
-- ----------------------------------------------------------------------------
CREATE TYPE imdg_hazard_class AS ENUM (
    'none',
    'class_1_explosives',
    'class_2_gases',
    'class_3_flammable_liquids',
    'class_4_flammable_solids',
    'class_5_oxidizing_substances',
    'class_6_toxic_infectious',
    'class_7_radioactive',
    'class_8_corrosive',
    'class_9_miscellaneous'
    );

-- ----------------------------------------------------------------------------
-- ENUM: Status dokumentu generowanego (PDF do kapitanatu portu)
-- ----------------------------------------------------------------------------
CREATE TYPE document_status AS ENUM (
    'draft',
    'generated',
    'sent',
    'acknowledged_by_port',
    'rejected_by_port',
    'superseded'              -- zastąpiony nowszą wersją
    );

-- ----------------------------------------------------------------------------
-- ENUM: Typ dokumentu generowanego
-- ----------------------------------------------------------------------------
CREATE TYPE document_type AS ENUM (
    'port_entry_notification',  -- zawiadomienie o wejściu do portu
    'pre_arrival_notification',
    'cargo_declaration',
    'dangerous_goods_declaration',
    'isps_security_declaration',
    'crew_list',
    'service_request_summary',
    'departure_notification',
    'other'
    );

-- ----------------------------------------------------------------------------
-- ENUM: Wynik przeglądu sankcyjnego
-- ----------------------------------------------------------------------------
CREATE TYPE sanctions_screening_result AS ENUM (
    'clear',           -- brak trafień
    'potential_match',  -- możliwe trafienie, wymaga weryfikacji manualnej
    'confirmed_match',   -- potwierdzone trafienie na liście sankcyjnej
    'false_positive'     -- zweryfikowane jako fałszywe trafienie
    );

-- ----------------------------------------------------------------------------
-- ENUM: Lista sankcyjna / źródło
-- ----------------------------------------------------------------------------
CREATE TYPE sanctions_list_source AS ENUM (
    'ofac_sdn',          -- USA Treasury OFAC Specially Designated Nationals
    'eu_consolidated',    -- Unia Europejska - lista skonsolidowana
    'uk_hmt',             -- UK HM Treasury
    'un_security_council',
    'other_national'
    );


-- ============================================================================
-- Część 2: Tabele referencyjne / słownikowe
-- Te tabele są "generyczne" i pozwalają na komercjalizację na inne porty
-- bez zmiany struktury - dodaje się tylko nowe wiersze.
-- ============================================================================
SET search_path TO port_intel, public;

-- ----------------------------------------------------------------------------
-- countries: kraje (ISO 3166-1) - używane jako flaga statku, narodowość armatora
-- ----------------------------------------------------------------------------
CREATE TABLE countries (
                           country_id          SMALLINT PRIMARY KEY,
                           iso_alpha2          CHAR(2) NOT NULL UNIQUE,
                           iso_alpha3          CHAR(3) NOT NULL UNIQUE,
                           country_name        VARCHAR(150) NOT NULL,
    -- Klasyfikacja Paris MoU dla państwa flagi: white/grey/black list
    -- (wpływa bezpośrednio na risk score statku pod tą flagą)
                           paris_mou_flag_tier  VARCHAR(15) CHECK (paris_mou_flag_tier IN ('white', 'grey', 'black', 'not_assessed')),
                           is_eu_member         BOOLEAN NOT NULL DEFAULT FALSE,
                           is_sanctioned_jurisdiction BOOLEAN NOT NULL DEFAULT FALSE,
                           created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
                           updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE countries IS 'Słownik krajów ISO 3166-1, rozszerzony o klasyfikację Paris MoU dla oceny ryzyka flagi statku.';

-- ----------------------------------------------------------------------------
-- currencies: ISO 4217 - waluty (do rozliczeń usług portowych)
-- ----------------------------------------------------------------------------
CREATE TABLE currencies (
                            currency_code  CHAR(3) PRIMARY KEY,
                            currency_name  VARCHAR(50) NOT NULL,
                            minor_unit      SMALLINT NOT NULL DEFAULT 2
);

-- ----------------------------------------------------------------------------
-- ports: porty świata, identyfikowane przez UN/LOCODE (generyczne, nie tylko Trójmiasto)
-- ----------------------------------------------------------------------------
CREATE TABLE ports (
                       port_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                       un_locode           VARCHAR(5) NOT NULL UNIQUE,
                       port_name           VARCHAR(200) NOT NULL,
                       country_id           SMALLINT NOT NULL REFERENCES countries(country_id),
                       location             GEOGRAPHY(POINT, 4326),
                       timezone              VARCHAR(64) NOT NULL DEFAULT 'UTC',
                       max_draft_meters       NUMERIC(5,2),
                       max_loa_meters          NUMERIC(6,2),
                       max_beam_meters         NUMERIC(5,2),
                       has_icebreaker_support   BOOLEAN NOT NULL DEFAULT FALSE,
                       has_cold_storage_facility BOOLEAN NOT NULL DEFAULT FALSE,
                       is_isps_compliant         BOOLEAN NOT NULL DEFAULT TRUE,
                       port_authority_name        VARCHAR(200),
                       port_authority_contact_email VARCHAR(200),
                       port_authority_contact_phone VARCHAR(50),
                       notes                  TEXT,
                       is_active               BOOLEAN NOT NULL DEFAULT TRUE,
                       created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
                       updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ports_country ON ports(country_id);
CREATE INDEX idx_ports_location ON ports USING GIST(location);
COMMENT ON TABLE ports IS 'Generyczny rejestr portów świata (UN/LOCODE). Dane Trójmiasta + przykładowe porty UE jako seed.';

-- ----------------------------------------------------------------------------
-- berths: nabrzeża wewnątrz portu - kluczowe dla doboru odpowiedniego miejsca
-- ----------------------------------------------------------------------------
CREATE TABLE berths (
                        berth_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                        port_id                UUID NOT NULL REFERENCES ports(port_id) ON DELETE CASCADE,
                        berth_code              VARCHAR(50) NOT NULL,
                        berth_name               VARCHAR(200),
                        location                  GEOGRAPHY(POINT, 4326),
                        max_draft_meters           NUMERIC(5,2),
                        max_loa_meters               NUMERIC(6,2),
                        max_dwt_tonnes                NUMERIC(10,2),
                        supports_dangerous_goods       BOOLEAN NOT NULL DEFAULT FALSE,
                        supports_reefer_containers      BOOLEAN NOT NULL DEFAULT FALSE,
                        supports_ro_ro                   BOOLEAN NOT NULL DEFAULT FALSE,
                        has_shore_power                   BOOLEAN NOT NULL DEFAULT FALSE,
                        crane_capacity_tonnes               NUMERIC(8,2),
                        is_active                            BOOLEAN NOT NULL DEFAULT TRUE,
                        notes                                  TEXT,
                        created_at                              TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at                               TIMESTAMPTZ NOT NULL DEFAULT now(),
                        UNIQUE (port_id, berth_code)
);
CREATE INDEX idx_berths_port ON berths(port_id);
COMMENT ON TABLE berths IS 'Nabrzeża/terminale w ramach portu, z parametrami technicznymi determinującymi które statki mogą być obsłużone.';

-- ----------------------------------------------------------------------------
-- berth_occupancy: zajętość nabrzeży w czasie (rezerwacje), z wykluczeniem nakładania
-- ----------------------------------------------------------------------------
CREATE TABLE berth_occupancy (
                                 occupancy_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                 berth_id          UUID NOT NULL REFERENCES berths(berth_id) ON DELETE CASCADE,
                                 port_call_id        UUID,  -- FK dodany w części 5 (port_calls) przez ALTER TABLE
                                 occupied_from         TIMESTAMPTZ NOT NULL,
                                 occupied_until          TIMESTAMPTZ NOT NULL,
                                 CONSTRAINT chk_occupancy_period CHECK (occupied_until > occupied_from),
                                 EXCLUDE USING gist (berth_id WITH =, tstzrange(occupied_from, occupied_until) WITH &&)
);
COMMENT ON TABLE berth_occupancy IS 'Harmonogram zajętości nabrzeży - zapobiega podwójnym rezerwacjom dzięki EXCLUDE constraint.';

-- ----------------------------------------------------------------------------
-- port_weather_history: historyczne dane pogodowe portu (z notatek - StormGlass.io)
-- ----------------------------------------------------------------------------
CREATE TABLE port_weather_history (
                                      weather_record_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                      port_id              UUID NOT NULL REFERENCES ports(port_id) ON DELETE CASCADE,
                                      recorded_at            TIMESTAMPTZ NOT NULL,
                                      wind_speed_knots         NUMERIC(5,2),
                                      wind_direction_degrees     SMALLINT,
                                      wave_height_meters           NUMERIC(4,2),
                                      air_temperature_celsius        NUMERIC(4,1),
                                      water_temperature_celsius       NUMERIC(4,1),
                                      visibility_meters                 INTEGER,
                                      ice_present                         BOOLEAN NOT NULL DEFAULT FALSE,
                                      ice_thickness_cm                      NUMERIC(5,2),
                                      data_source                            VARCHAR(100) DEFAULT 'stormglass.io',
                                      raw_payload                              JSONB,
                                      created_at                                 TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_weather_port_time ON port_weather_history(port_id, recorded_at DESC);
COMMENT ON TABLE port_weather_history IS 'Historyczne i bieżące dane pogodowe per port, zasilane np. z StormGlass.io API.';

-- ----------------------------------------------------------------------------
-- vessel_type_reference: granularna klasyfikacja typu statku (StatCode5-like)
-- ----------------------------------------------------------------------------
CREATE TABLE vessel_type_reference (
                                       vessel_type_id        SMALLSERIAL PRIMARY KEY,
                                       type_family             vessel_type_family NOT NULL,
                                       ais_category              ais_ship_type_category NOT NULL,
                                       ais_numeric_code            SMALLINT,
                                       statcode5_label               VARCHAR(150),
                                       type_description                TEXT,
                                       typical_risk_baseline               NUMERIC(4,1) CHECK (typical_risk_baseline BETWEEN 0 AND 100),
                                       requires_icebreaker_priority           BOOLEAN NOT NULL DEFAULT FALSE,
                                       created_at                               TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE vessel_type_reference IS 'Granularny słownik typów statków (zgodny z duchem IHS StatCode5), z bazowym poziomem ryzyka per typ.';

-- ----------------------------------------------------------------------------
-- classification_societies: towarzystwa klasyfikacyjne (IACS members + inne)
-- ----------------------------------------------------------------------------
CREATE TABLE classification_societies (
                                          society_id        SMALLSERIAL PRIMARY KEY,
                                          society_name         VARCHAR(150) NOT NULL UNIQUE,
                                          is_iacs_member          BOOLEAN NOT NULL DEFAULT TRUE,
                                          country_id                SMALLINT REFERENCES countries(country_id),
                                          created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE classification_societies IS 'Towarzystwa klasyfikacyjne statków. Non-IACS towarzystwa zwiększają risk score (red flag w branży).';


-- ============================================================================
-- Część 3: STATKI i ARMATORZY (Master Data)
-- Klucz: IMO Number jako unikalny, niemienny identyfikator statku przez całe
-- jego życie (nazwa statku ZMIENIA SIĘ, IMO Number NIE - dlatego to jest PK biznesowy)
-- ============================================================================
SET search_path TO port_intel, public;

-- ----------------------------------------------------------------------------
-- companies: armatorzy / operatorzy / managerowie techniczni / inne podmioty
-- Jedna tabela dla wszystkich typów podmiotów firmowych w ekosystemie -
-- rola względem konkretnego statku jest w tabeli łączącej vessel_company_roles
-- ----------------------------------------------------------------------------
CREATE TABLE companies (
                           company_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                           imo_company_number         VARCHAR(7) UNIQUE,  -- IMO Unique Company Identifier, jeśli znany
                           company_name                 VARCHAR(250) NOT NULL,
                           country_id                     SMALLINT REFERENCES countries(country_id),
                           registered_address               TEXT,
                           primary_contact_name               VARCHAR(150),
                           primary_contact_email                VARCHAR(200),
                           primary_contact_phone                 VARCHAR(50),
    -- Czy struktura własności jest przejrzysta - wpływa na risk score
                           ownership_transparency_flag             BOOLEAN NOT NULL DEFAULT TRUE,
                           is_sanctioned                             BOOLEAN NOT NULL DEFAULT FALSE,  -- cache wyniku screeningu, źródło prawdy: sanctions_screening_results
                           notes                                       TEXT,
                           created_at                                   TIMESTAMPTZ NOT NULL DEFAULT now(),
                           updated_at                                     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_companies_name_trgm ON companies USING gin (company_name gin_trgm_ops);
COMMENT ON TABLE companies IS 'Wszystkie podmioty firmowe: armatorzy, operatorzy, managerowie techniczni, agenci crewingowi, P&I Clubs, itd. Rola określona w vessel_company_roles.';

-- ----------------------------------------------------------------------------
-- company_contacts: osoby kontaktowe per firma (imię, nazwisko, rola)
-- Z notatek: "Agent musi precyzyjnie wykorzystać kluczowe informacje
-- nominacyjne" - imiona/nazwiska osób kontaktowych armatora
-- ----------------------------------------------------------------------------
CREATE TABLE company_contacts (
                                  contact_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                  company_id          UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
                                  first_name             VARCHAR(100) NOT NULL,
                                  last_name                VARCHAR(100) NOT NULL,
                                  job_title                  VARCHAR(150),
                                  email                         VARCHAR(200),
                                  phone                           VARCHAR(50),
                                  is_primary_for_nominations       BOOLEAN NOT NULL DEFAULT FALSE,
                                  notes                               TEXT,
                                  created_at                           TIMESTAMPTZ NOT NULL DEFAULT now(),
                                  updated_at                             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_company_contacts_company ON company_contacts(company_id);
COMMENT ON TABLE company_contacts IS 'Osoby kontaktowe w firmach armatorskich/operatorskich - imiona, nazwiska, e-maile pozyskane z korespondencji.';

-- ----------------------------------------------------------------------------
-- vessels: GŁÓWNA tabela statków. IMO Number = klucz biznesowy.
-- ----------------------------------------------------------------------------
CREATE TABLE vessels (
                         vessel_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                         imo_number                VARCHAR(7) NOT NULL UNIQUE
                             CHECK (imo_number ~ '^[0-9]{7}$'),
                         mmsi                         VARCHAR(9)
                             CHECK (mmsi IS NULL OR mmsi ~ '^[0-9]{9}$'),
                         call_sign                       VARCHAR(15),
                         current_vessel_name                VARCHAR(200) NOT NULL,  -- aktualna nazwa (może się zmieniać - historia w vessel_name_history)
                         domain                                 vessel_domain NOT NULL DEFAULT 'unknown',
                         vessel_type_id                            SMALLINT REFERENCES vessel_type_reference(vessel_type_id),
                         flag_country_id                              SMALLINT REFERENCES countries(country_id),
                         year_built                                      SMALLINT CHECK (year_built BETWEEN 1900 AND 2100),
                         classification_society_id                          SMALLINT REFERENCES classification_societies(society_id),
                         is_active                                             BOOLEAN NOT NULL DEFAULT TRUE,  -- FALSE = wycofany/zezłomowany
                         scrapped_date                                            DATE,
                         notes                                                       TEXT,
                         created_at                                                    TIMESTAMPTZ NOT NULL DEFAULT now(),
                         updated_at                                                      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vessels_name_trgm ON vessels USING gin (current_vessel_name gin_trgm_ops);
CREATE INDEX idx_vessels_mmsi ON vessels(mmsi);
CREATE INDEX idx_vessels_flag ON vessels(flag_country_id);
CREATE INDEX idx_vessels_type ON vessels(vessel_type_id);
COMMENT ON TABLE vessels IS 'Centralny rejestr statków. imo_number to niezmienny identyfikator biznesowy (statek może zmienić nazwę/flagę, IMO Number nigdy).';

-- ----------------------------------------------------------------------------
-- vessel_name_history: historia nazw statku (statki zmieniają nazwę przy
-- zmianie właściciela - to częste i ważne dla śledzenia historii ryzyka)
-- ----------------------------------------------------------------------------
CREATE TABLE vessel_name_history (
                                     name_history_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                     vessel_id             UUID NOT NULL REFERENCES vessels(vessel_id) ON DELETE CASCADE,
                                     vessel_name              VARCHAR(200) NOT NULL,
                                     flag_country_id             SMALLINT REFERENCES countries(country_id),
                                     effective_from                 DATE NOT NULL,
                                     effective_until                   DATE,
                                     source                               VARCHAR(100),  -- np. 'IMO GISIS', 'manual_entry'
                                     created_at                             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_name_history_vessel ON vessel_name_history(vessel_id);
COMMENT ON TABLE vessel_name_history IS 'Historia nazw i flag statku - statki często zmieniają nazwę/flagę po zmianie właściciela, co bywa sygnałem ryzyka (flag hopping).';

-- ----------------------------------------------------------------------------
-- vessel_technical_specs: dane techniczne statku, WERSJONOWANE w czasie
-- (np. po przebudowie statku zmienia się tonaż) - jedna tabela, ważność dat
-- ----------------------------------------------------------------------------
CREATE TABLE vessel_technical_specs (
                                        spec_id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                        vessel_id                  UUID NOT NULL REFERENCES vessels(vessel_id) ON DELETE CASCADE,
                                        length_overall_meters         NUMERIC(6,2),   -- LOA
                                        beam_meters                      NUMERIC(5,2),   -- szerokość
                                        draft_meters                        NUMERIC(5,2),   -- zanurzenie
                                        air_draft_meters                       NUMERIC(5,2),   -- wysokość nad linią wodną (mosty!)
                                        gross_tonnage                             NUMERIC(10,2),  -- GT
                                        net_tonnage                                  NUMERIC(10,2),  -- NT
                                        deadweight_tonnage                              NUMERIC(10,2),  -- DWT
                                        main_engine_power_kw                               NUMERIC(10,2),
                                        max_speed_knots                                       NUMERIC(4,1),
                                        has_ice_class                                           BOOLEAN NOT NULL DEFAULT FALSE,
                                        ice_class_designation                                      VARCHAR(50),  -- np. 'PC6', '1A Super' (Finnish-Swedish Ice Class)
                                        container_capacity_teu                                        INTEGER,    -- jeśli kontenerowiec
                                        has_reefer_plugs                                                 BOOLEAN NOT NULL DEFAULT FALSE,
                                        reefer_plug_count                                                   INTEGER,
                                        effective_from                                                         DATE NOT NULL DEFAULT CURRENT_DATE,
                                        effective_until                                                           DATE,
                                        data_source                                                                  VARCHAR(150),  -- np. 'VesselFinder', 'MarineTraffic', 'manual'
                                        created_at                                                                       TIMESTAMPTZ NOT NULL DEFAULT now(),
                                        CONSTRAINT chk_spec_period CHECK (effective_until IS NULL OR effective_until > effective_from)
);
CREATE INDEX idx_tech_specs_vessel ON vessel_technical_specs(vessel_id, effective_from DESC);
COMMENT ON TABLE vessel_technical_specs IS 'Wersjonowane dane techniczne statku (wymiary, tonaż, klasa lodowa). Pozwala śledzić zmiany po przebudowach.';

-- ----------------------------------------------------------------------------
-- vessel_company_roles: relacja statek <-> firma, z określoną rolą i okresem
-- (armator rejestrowy MOŻE SIĘ RÓŻNIĆ od operatora handlowego)
-- ----------------------------------------------------------------------------
CREATE TABLE vessel_company_roles (
                                      role_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                      vessel_id             UUID NOT NULL REFERENCES vessels(vessel_id) ON DELETE CASCADE,
                                      company_id              UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
                                      role_type                  company_role_type NOT NULL,
                                      effective_from                DATE NOT NULL DEFAULT CURRENT_DATE,
                                      effective_until                  DATE,
                                      is_current                          BOOLEAN NOT NULL DEFAULT TRUE,
                                      created_at                             TIMESTAMPTZ NOT NULL DEFAULT now(),
                                      CONSTRAINT chk_role_period CHECK (effective_until IS NULL OR effective_until > effective_from)
);
CREATE INDEX idx_vessel_roles_vessel ON vessel_company_roles(vessel_id);
CREATE INDEX idx_vessel_roles_company ON vessel_company_roles(company_id);
CREATE UNIQUE INDEX idx_vessel_roles_current_unique
    ON vessel_company_roles(vessel_id, role_type)
    WHERE is_current = TRUE;
COMMENT ON TABLE vessel_company_roles IS 'Relacje statek-firma z rolą (armator rejestrowy, operator, manager techniczny, P&I club itd.), wersjonowane w czasie.';

-- ----------------------------------------------------------------------------
-- vessel_certificates: certyfikaty statku (ISM, ISPS, klasa, itp.)
-- ----------------------------------------------------------------------------
CREATE TABLE vessel_certificates (
                                     certificate_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                     vessel_id             UUID NOT NULL REFERENCES vessels(vessel_id) ON DELETE CASCADE,
                                     certificate_type        VARCHAR(100) NOT NULL,  -- np. 'ISM Safety Management Certificate', 'ISSC (ISPS)'
                                     certificate_number          VARCHAR(100),
                                     issuing_authority              VARCHAR(200),
                                     issue_date                       DATE,
                                     expiry_date                         DATE,
                                     document_file_url                         TEXT,  -- link do skanu certyfikatu w object storage
                                     created_at                                   TIMESTAMPTZ NOT NULL DEFAULT now(),
                                     updated_at                                      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_certificates_vessel ON vessel_certificates(vessel_id);
CREATE INDEX idx_certificates_expiry ON vessel_certificates(expiry_date);
COMMENT ON TABLE vessel_certificates IS 'Certyfikaty statku - ISM, ISPS (ISSC), klasa, i inne wymagane dokumenty zgodności.';

-- Widok z dynamicznie liczoną walidnością certyfikatu (CURRENT_DATE nie jest
-- IMMUTABLE, więc nie może być generowaną kolumną - liczymy to w widoku)
CREATE OR REPLACE VIEW v_vessel_certificates_status AS
SELECT
    certificate_id,
    vessel_id,
    certificate_type,
    certificate_number,
    issuing_authority,
    issue_date,
    expiry_date,
    (expiry_date IS NULL OR expiry_date >= CURRENT_DATE) AS is_valid,
    document_file_url
FROM vessel_certificates;
COMMENT ON VIEW v_vessel_certificates_status IS 'Certyfikaty statku ze statusem walidności liczonym na bieżąco względem CURRENT_DATE.';


-- ============================================================================
-- Część 4: RYZYKO, SANKCJE, PORT STATE CONTROL
-- To jest serce systemu compliance/ryzyka, oparte na realnych frameworkach:
--   - Paris MoU / Tokyo MoU Ship Risk Profile (HRS/SRS/LRS)
--   - OFAC SDN / UE Consolidated List / UK HMT - sankcje
-- Risk score jest w PEŁNI AUDYTOWALNY: każda ocena to nowy wiersz (insert-only),
-- nigdy nie nadpisujemy poprzedniej oceny.
-- ============================================================================
SET search_path TO port_intel, public;

-- ----------------------------------------------------------------------------
-- psc_inspections: historia inspekcji Port State Control (realne źródło danych
-- do scoringu, nie zgadywanie - zgodnie z modelem Paris/Tokyo MoU)
-- ----------------------------------------------------------------------------
CREATE TABLE psc_inspections (
                                 inspection_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                 vessel_id                 UUID NOT NULL REFERENCES vessels(vessel_id) ON DELETE CASCADE,
                                 inspecting_port_id            UUID REFERENCES ports(port_id),
                                 inspecting_authority             VARCHAR(200),  -- np. 'Paris MoU', 'Tokyo MoU', 'US Coast Guard'
                                 inspection_date                     DATE NOT NULL,
                                 deficiency_count                       INTEGER NOT NULL DEFAULT 0 CHECK (deficiency_count >= 0),
                                 was_detained                              BOOLEAN NOT NULL DEFAULT FALSE,
                                 detention_days                               INTEGER CHECK (detention_days IS NULL OR detention_days >= 0),
                                 inspection_report_url                           TEXT,
                                 notes                                              TEXT,
                                 created_at                                            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_psc_vessel ON psc_inspections(vessel_id, inspection_date DESC);
COMMENT ON TABLE psc_inspections IS 'Historia inspekcji Port State Control - liczba usterek i zatrzymań to kluczowe, empirycznie zweryfikowane predyktory ryzyka (Paris/Tokyo MoU).';

-- ----------------------------------------------------------------------------
-- psc_deficiencies: szczegółowe usterki znalezione przy inspekcji (kody PSC)
-- ----------------------------------------------------------------------------
CREATE TABLE psc_deficiencies (
                                  deficiency_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                  inspection_id            UUID NOT NULL REFERENCES psc_inspections(inspection_id) ON DELETE CASCADE,
                                  deficiency_code              VARCHAR(20),  -- harmonizowany kod deficiency (Paris MoU code list)
                                  deficiency_description           TEXT NOT NULL,
                                  severity                            VARCHAR(20) CHECK (severity IN ('low', 'medium', 'high', 'detainable')),
                                  action_taken                           VARCHAR(100),  -- np. 'rectified before departure'
                                  created_at                                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_deficiencies_inspection ON psc_deficiencies(inspection_id);
COMMENT ON TABLE psc_deficiencies IS 'Pojedyncze usterki znalezione przy inspekcji PSC, z harmonizowanym kodem i ważnością.';

-- ----------------------------------------------------------------------------
-- sanctions_screening_results: wyniki przeglądu sankcyjnego per podmiot
-- Polimorficzne odniesienie: może dotyczyć statku ALBO firmy (sankcje bywają
-- nałożone na statek, na armatora, albo na oba)
-- ----------------------------------------------------------------------------
CREATE TABLE sanctions_screening_results (
                                             screening_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                             vessel_id                UUID REFERENCES vessels(vessel_id) ON DELETE CASCADE,
                                             company_id                  UUID REFERENCES companies(company_id) ON DELETE CASCADE,
                                             list_source                    sanctions_list_source NOT NULL,
                                             screening_result                  sanctions_screening_result NOT NULL,
                                             matched_entry_name                   VARCHAR(250),  -- nazwa na liście, którą system dopasował
                                             match_confidence_pct                    NUMERIC(5,2) CHECK (match_confidence_pct BETWEEN 0 AND 100),
                                             screened_at                                TIMESTAMPTZ NOT NULL DEFAULT now(),
                                             reviewed_by_user                              VARCHAR(150),  -- kto zweryfikował manualnie (jeśli potencjalne trafienie)
                                             review_notes                                     TEXT,
                                             CONSTRAINT chk_screening_target CHECK (vessel_id IS NOT NULL OR company_id IS NOT NULL)
);
CREATE INDEX idx_sanctions_vessel ON sanctions_screening_results(vessel_id);
CREATE INDEX idx_sanctions_company ON sanctions_screening_results(company_id);
CREATE INDEX idx_sanctions_result ON sanctions_screening_results(screening_result);
COMMENT ON TABLE sanctions_screening_results IS 'Wyniki przeglądu sankcyjnego (OFAC/UE/UK) per statek lub firma. Insert-only - każdy przegląd to nowy wiersz, dla audytu.';

-- ----------------------------------------------------------------------------
-- risk_factor_definitions: KONFIGUROWALNE definicje czynników ryzyka i ich wag.
-- To jest klucz do komercjalizacji - każdy port może mieć własną politykę
-- ryzyka bez zmiany kodu, tylko zmieniając wagi w tej tabeli.
-- ----------------------------------------------------------------------------
CREATE TABLE risk_factor_definitions (
                                         factor_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                         factor_category            risk_factor_category NOT NULL,
                                         factor_code                   VARCHAR(80) NOT NULL UNIQUE,  -- np. 'FLAG_BLACKLIST', 'CARGO_CLASS_7'
                                         factor_label                     VARCHAR(200) NOT NULL,
                                         description                         TEXT,
                                         weight                                 NUMERIC(5,2) NOT NULL DEFAULT 1.0,  -- waga w modelu scoringowym
                                         max_score_contribution                    NUMERIC(5,2) NOT NULL DEFAULT 10.0,
                                         is_active                                    BOOLEAN NOT NULL DEFAULT TRUE,
                                         applicable_port_id                              UUID REFERENCES ports(port_id),  -- NULL = globalna polityka, wartość = polityka specyficzna dla portu
                                         created_at                                         TIMESTAMPTZ NOT NULL DEFAULT now(),
                                         updated_at                                            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_risk_factors_port ON risk_factor_definitions(applicable_port_id);
COMMENT ON TABLE risk_factor_definitions IS 'Konfigurowalny katalog czynników ryzyka z wagami. applicable_port_id=NULL oznacza politykę globalną; różne porty mogą nadpisać wagi lokalnie.';

-- ----------------------------------------------------------------------------
-- vessel_risk_assessments: GŁÓWNA tabela wyniku oceny ryzyka.
-- PEŁNA HISTORIA - każda ocena to nowy wiersz (insert-only, nigdy UPDATE wyniku).
-- ----------------------------------------------------------------------------
CREATE TABLE vessel_risk_assessments (
                                         assessment_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                         vessel_id                  UUID NOT NULL REFERENCES vessels(vessel_id) ON DELETE CASCADE,
    -- Kontekst oceny - opcjonalnie powiązana z konkretną nominacją/wizytą portową
                                         nomination_id                 UUID,  -- FK dodany w części 5 (ALTER TABLE), bo nominations zdefiniowane później
                                         port_call_id                     UUID,  -- FK dodany w części 5
                                         assessed_at                         TIMESTAMPTZ NOT NULL DEFAULT now(),
                                         overall_risk_score                     NUMERIC(5,2) NOT NULL CHECK (overall_risk_score BETWEEN 0 AND 100),
                                         risk_tier                                 risk_tier NOT NULL,
                                         model_version                                VARCHAR(50) NOT NULL DEFAULT 'v1.0',  -- wersjonowanie samego algorytmu
                                         assessment_trigger                              VARCHAR(100),  -- np. 'new_nomination', 'scheduled_recheck', 'manual_review', 'psc_update'
                                         assessed_by                                        VARCHAR(150),  -- 'system_auto' albo imię agenta przy manualnym review
                                         is_current                                            BOOLEAN NOT NULL DEFAULT TRUE,  -- czy to najnowsza ocena dla statku
                                         notes                                                    TEXT,
                                         created_at                                                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_risk_assessments_vessel_time ON vessel_risk_assessments(vessel_id, assessed_at DESC);
CREATE INDEX idx_risk_assessments_tier ON vessel_risk_assessments(risk_tier);
-- Tylko jedna "aktualna" ocena per statek na raz
CREATE UNIQUE INDEX idx_risk_assessments_current_unique
    ON vessel_risk_assessments(vessel_id)
    WHERE is_current = TRUE;
COMMENT ON TABLE vessel_risk_assessments IS 'Pełna, audytowalna historia ocen ryzyka statku. INSERT-ONLY: nowa ocena = nowy wiersz, is_current flaguje najnowszą. Nigdy nie nadpisujemy starych ocen.';

-- ----------------------------------------------------------------------------
-- vessel_risk_assessment_factors: rozbicie konkretnej oceny na czynniki
-- składowe (audytowalność na poziomie "dlaczego ten statek ma taki wynik")
-- ----------------------------------------------------------------------------
CREATE TABLE vessel_risk_assessment_factors (
                                                assessment_factor_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                                assessment_id               UUID NOT NULL REFERENCES vessel_risk_assessments(assessment_id) ON DELETE CASCADE,
                                                factor_id                      UUID NOT NULL REFERENCES risk_factor_definitions(factor_id),
                                                factor_value_observed              TEXT,    -- np. 'flag=RUS', 'cargo_class=2 (gas)', 'psc_deficiencies=7'
                                                score_contribution                    NUMERIC(5,2) NOT NULL,
                                                created_at                               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_assessment_factors_assessment ON vessel_risk_assessment_factors(assessment_id);
COMMENT ON TABLE vessel_risk_assessment_factors IS 'Rozbicie oceny ryzyka na pojedyncze czynniki i ich wkład w wynik - pełna wyjaśnialność (explainability) scoringu.';


-- ============================================================================
-- Część 5: NOMINACJE ARMATORSKIE, WIZYTY PORTOWE, ŁADUNKI
-- To jest warstwa operacyjna - to, co faktycznie przychodzi mailem od armatora
-- i co dzieje się podczas wizyty statku w porcie.
-- ============================================================================
SET search_path TO port_intel, public;

-- ----------------------------------------------------------------------------
-- nominations: nominacja armatorska - GŁÓWNY dokument wejściowy procesu
-- ----------------------------------------------------------------------------
CREATE TABLE nominations (
                             nomination_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                             vessel_id                  UUID NOT NULL REFERENCES vessels(vessel_id),
                             nominating_company_id         UUID NOT NULL REFERENCES companies(company_id),  -- armator zgłaszający (z notatek: "Firma zgłaszająca")
                             nominating_contact_id            UUID REFERENCES company_contacts(contact_id),
                             destination_port_id                 UUID NOT NULL REFERENCES ports(port_id),
                             status                                  nomination_status NOT NULL DEFAULT 'received',
                             eta                                        TIMESTAMPTZ,  -- Estimated Time of Arrival
                             etd                                           TIMESTAMPTZ,  -- Estimated Time of Departure
                             requested_berth_id                               UUID REFERENCES berths(berth_id),
                             assigned_berth_id                                   UUID REFERENCES berths(berth_id),
    -- Surowa treść maila - zachowana w całości dla audytu i ponownego parsowania
                             source_email_subject                                   VARCHAR(500),
                             source_email_body_raw                                     TEXT,
                             source_email_received_at                                     TIMESTAMPTZ,
                             source_email_sender_address                                     VARCHAR(200),
    -- Pole na ekstrakcję LLM - jeśli parser nie złapał czegoś w sztywne kolumny,
    -- ZGODNIE z ustaleniami: LLM działa poza bazą, ale "resztki" trafiają tutaj
                             llm_extraction_metadata                                            JSONB,  -- np. {"model": "claude-sonnet-4-6", "confidence": 0.92, "fields_extracted": [...]}
                             assigned_agent_name                                                   VARCHAR(150),  -- np. 'Michał Samaruk' (z dokumentu hakatonowego)
                             mentor_contact_note                                                      TEXT,  -- z notatek: "kontakt do mentora przez RedSky"
                             created_at                                                                 TIMESTAMPTZ NOT NULL DEFAULT now(),
                             updated_at                                                                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_nominations_vessel ON nominations(vessel_id);
CREATE INDEX idx_nominations_company ON nominations(nominating_company_id);
CREATE INDEX idx_nominations_port ON nominations(destination_port_id);
CREATE INDEX idx_nominations_status ON nominations(status);
CREATE INDEX idx_nominations_eta ON nominations(eta);
COMMENT ON TABLE nominations IS 'Nominacja armatorska - dokument wejściowy z maila armatora, zawierający dane statku, ładunku i ETA do portu docelowego.';

-- Teraz możemy dodać odłożone FK z części 4
ALTER TABLE vessel_risk_assessments
    ADD CONSTRAINT fk_risk_assessment_nomination
        FOREIGN KEY (nomination_id) REFERENCES nominations(nomination_id) ON DELETE SET NULL;

-- ----------------------------------------------------------------------------
-- nomination_unstructured_notes: dane niesklasyfikowane z maila nominacyjnego
-- (zgodnie z ustaleniami: osobna tabela, wiele wierszy per nominacja,
-- przeszukiwalna - np. "armator prosi o cumowanie rufą do nabrzeża" itp.)
-- ----------------------------------------------------------------------------
CREATE TABLE nomination_unstructured_notes (
                                               note_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                               nomination_id           UUID NOT NULL REFERENCES nominations(nomination_id) ON DELETE CASCADE,
                                               note_text                  TEXT NOT NULL,
                                               extracted_by                  VARCHAR(50) NOT NULL DEFAULT 'llm',  -- 'llm' / 'manual_agent_entry'
                                               confidence_score                 NUMERIC(4,2) CHECK (confidence_score BETWEEN 0 AND 1),
                                               requires_human_review               BOOLEAN NOT NULL DEFAULT TRUE,
                                               reviewed_at                            TIMESTAMPTZ,
                                               reviewed_by                               VARCHAR(150),
                                               created_at                                   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_unstructured_notes_nomination ON nomination_unstructured_notes(nomination_id);
CREATE INDEX idx_unstructured_notes_text_trgm ON nomination_unstructured_notes USING gin (note_text gin_trgm_ops);
COMMENT ON TABLE nomination_unstructured_notes IS 'Niesklasyfikowane fragmenty treści maila nominacyjnego, które nie pasują do sztywnych kolumn - przeszukiwalne pełnotekstowo (pg_trgm), z flagą wymagającą przeglądu człowieka.';

-- ----------------------------------------------------------------------------
-- port_calls: konkretna wizyta statku w porcie (1 nominacja zwykle -> 1 wizyta)
-- ----------------------------------------------------------------------------
CREATE TABLE port_calls (
                            port_call_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                            vessel_id                  UUID NOT NULL REFERENCES vessels(vessel_id),
                            port_id                       UUID NOT NULL REFERENCES ports(port_id),
                            nomination_id                    UUID REFERENCES nominations(nomination_id),
                            berth_id                            UUID REFERENCES berths(berth_id),
                            status                                 port_call_status NOT NULL DEFAULT 'scheduled',
                            eta                                       TIMESTAMPTZ,
                            actual_arrival_time                         TIMESTAMPTZ,
                            actual_berthing_time                           TIMESTAMPTZ,
                            actual_departure_time                             TIMESTAMPTZ,
                            draft_on_arrival_meters                              NUMERIC(5,2),
                            purpose_of_call                                         VARCHAR(200),  -- np. 'cargo_discharge', 'bunkering', 'crew_change'
                            created_at                                                  TIMESTAMPTZ NOT NULL DEFAULT now(),
                            updated_at                                                     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_port_calls_vessel ON port_calls(vessel_id, actual_arrival_time DESC);
CREATE INDEX idx_port_calls_port ON port_calls(port_id);
CREATE INDEX idx_port_calls_status ON port_calls(status);
COMMENT ON TABLE port_calls IS 'Konkretna wizyta statku w porcie - historia wejść/wyjść, kluczowa dla budowania "track record" statku w danym porcie.';

-- Dopinamy odłożone FK z części 2 i 4
ALTER TABLE berth_occupancy
    ADD CONSTRAINT fk_berth_occupancy_port_call
        FOREIGN KEY (port_call_id) REFERENCES port_calls(port_call_id) ON DELETE CASCADE;

ALTER TABLE vessel_risk_assessments
    ADD CONSTRAINT fk_risk_assessment_port_call
        FOREIGN KEY (port_call_id) REFERENCES port_calls(port_call_id) ON DELETE SET NULL;

-- ----------------------------------------------------------------------------
-- cargo_manifests: ładunek deklarowany per nominacja/wizyta
-- ----------------------------------------------------------------------------
CREATE TABLE cargo_manifests (
                                 cargo_id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                 nomination_id              UUID REFERENCES nominations(nomination_id) ON DELETE CASCADE,
                                 port_call_id                  UUID REFERENCES port_calls(port_call_id) ON DELETE CASCADE,
                                 cargo_description                VARCHAR(300) NOT NULL,
                                 cargo_quantity                      NUMERIC(12,2),
                                 cargo_unit                             VARCHAR(20),  -- np. 'TEU', 'tonnes', 'm3', 'units'
                                 imdg_hazard_class                         imdg_hazard_class NOT NULL DEFAULT 'none',
                                 un_number                                    VARCHAR(10),  -- UN number dla towarów niebezpiecznych (np. UN1203)
                                 requires_refrigeration                          BOOLEAN NOT NULL DEFAULT FALSE,  -- pod igloporty
                                 target_temperature_celsius                         NUMERIC(5,2),
                                 is_perishable                                          BOOLEAN NOT NULL DEFAULT FALSE,
                                 origin_country_id                                         SMALLINT REFERENCES countries(country_id),
                                 destination_country_id                                       SMALLINT REFERENCES countries(country_id),
                                 created_at                                                       TIMESTAMPTZ NOT NULL DEFAULT now(),
                                 CONSTRAINT chk_cargo_parent CHECK (nomination_id IS NOT NULL OR port_call_id IS NOT NULL)
);
CREATE INDEX idx_cargo_nomination ON cargo_manifests(nomination_id);
CREATE INDEX idx_cargo_port_call ON cargo_manifests(port_call_id);
CREATE INDEX idx_cargo_hazard ON cargo_manifests(imdg_hazard_class) WHERE imdg_hazard_class != 'none';
COMMENT ON TABLE cargo_manifests IS 'Ładunek statku - deklarowany przy nominacji i/lub potwierdzony przy wizycie. Klasa IMDG wpływa na risk score i wybór nabrzeża.';

-- ----------------------------------------------------------------------------
-- port_service_orders: zamówienia usług portowych (holowniki, prąd, lekarz, barber)
-- ----------------------------------------------------------------------------
CREATE TABLE port_service_orders (
                                     service_order_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                     port_call_id                UUID NOT NULL REFERENCES port_calls(port_call_id) ON DELETE CASCADE,
                                     service_type                   port_service_type NOT NULL,
                                     provider_company_id               UUID REFERENCES companies(company_id),  -- np. firma holownicza, dostawca prowiantu
                                     status                               service_order_status NOT NULL DEFAULT 'requested',
                                     requested_at                            TIMESTAMPTZ NOT NULL DEFAULT now(),
                                     scheduled_for                              TIMESTAMPTZ,
                                     completed_at                                  TIMESTAMPTZ,
                                     cost_amount                                      NUMERIC(12,2),
                                     cost_currency                                       CHAR(3) REFERENCES currencies(currency_code),
                                     notes                                                  TEXT,
                                     created_at                                                TIMESTAMPTZ NOT NULL DEFAULT now(),
                                     updated_at                                                   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_service_orders_port_call ON port_service_orders(port_call_id);
CREATE INDEX idx_service_orders_type ON port_service_orders(service_type);
CREATE INDEX idx_service_orders_status ON port_service_orders(status);
COMMENT ON TABLE port_service_orders IS 'Zamówienia usług portowych per wizyta: pilotaż, holowniki, prąd z lądu, lekarz, barber, bunkrowanie, itd.';

-- ----------------------------------------------------------------------------
-- generated_documents: śledzenie dokumentów PDF generowanych dla kapitanatu
-- portu (metadane + link do pliku w object storage, NIE sam plik binarny)
-- ----------------------------------------------------------------------------
CREATE TABLE generated_documents (
                                     document_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                     nomination_id              UUID REFERENCES nominations(nomination_id) ON DELETE CASCADE,
                                     port_call_id                  UUID REFERENCES port_calls(port_call_id) ON DELETE CASCADE,
                                     document_type                    document_type NOT NULL,
                                     status                               document_status NOT NULL DEFAULT 'draft',
                                     version_number                         INTEGER NOT NULL DEFAULT 1,
                                     file_url                                  TEXT,           -- link do S3/storage
                                     file_hash_sha256                             VARCHAR(64),    -- integralność pliku
                                     generated_by                                    VARCHAR(150),   -- 'system_auto' / nazwa agenta
                                     generated_at                                       TIMESTAMPTZ NOT NULL DEFAULT now(),
                                     sent_at                                               TIMESTAMPTZ,
                                     sent_to_email                                            VARCHAR(200),
                                     acknowledged_at                                             TIMESTAMPTZ,
                                     acknowledged_by                                                VARCHAR(150),
                                     rejection_reason                                                  TEXT,
                                     supersedes_document_id                                               UUID REFERENCES generated_documents(document_id),
                                     created_at                                                              TIMESTAMPTZ NOT NULL DEFAULT now(),
                                     CONSTRAINT chk_document_parent CHECK (nomination_id IS NOT NULL OR port_call_id IS NOT NULL)
);
CREATE INDEX idx_documents_nomination ON generated_documents(nomination_id);
CREATE INDEX idx_documents_port_call ON generated_documents(port_call_id);
CREATE INDEX idx_documents_status ON generated_documents(status);
COMMENT ON TABLE generated_documents IS 'Metadane dokumentów PDF generowanych do kapitanatu portu - status, wersjonowanie, kto/kiedy wysłał, czy port potwierdził. Plik binarny żyje w object storage, baza trzyma tylko file_url.';


-- ============================================================================
-- Część 6: DANE SEED (przykładowe dane startowe)
-- Kraje (subset istotny dla Bałtyku/UE), porty Trójmiasta + przykładowe porty UE,
-- typy statków, towarzystwa klasyfikacyjne.
-- ============================================================================
SET search_path TO port_intel, public;

-- ----------------------------------------------------------------------------
-- countries (subset - kraje istotne dla ruchu bałtyckiego i demo)
-- Paris MoU flag tier na podstawie publicznie znanych klasyfikacji (przykładowo;
-- w produkcji aktualizować z oficjalnej listy Paris MoU rocznie)
-- ----------------------------------------------------------------------------
INSERT INTO countries (country_id, iso_alpha2, iso_alpha3, country_name, paris_mou_flag_tier, is_eu_member, is_sanctioned_jurisdiction) VALUES
                                                                                                                                            (1,  'PL', 'POL', 'Polska',             'white', TRUE,  FALSE),
                                                                                                                                            (2,  'DE', 'DEU', 'Niemcy',             'white', TRUE,  FALSE),
                                                                                                                                            (3,  'NL', 'NLD', 'Holandia',           'white', TRUE,  FALSE),
                                                                                                                                            (4,  'DK', 'DNK', 'Dania',              'white', TRUE,  FALSE),
                                                                                                                                            (5,  'SE', 'SWE', 'Szwecja',            'white', TRUE,  FALSE),
                                                                                                                                            (6,  'FI', 'FIN', 'Finlandia',          'white', TRUE,  FALSE),
                                                                                                                                            (7,  'LT', 'LTU', 'Litwa',              'white', TRUE,  FALSE),
                                                                                                                                            (8,  'LV', 'LVA', 'Łotwa',              'white', TRUE,  FALSE),
                                                                                                                                            (9,  'EE', 'EST', 'Estonia',            'white', TRUE,  FALSE),
                                                                                                                                            (10, 'NO', 'NOR', 'Norwegia',           'white', FALSE, FALSE),
                                                                                                                                            (11, 'GB', 'GBR', 'Wielka Brytania',    'white', FALSE, FALSE),
                                                                                                                                            (12, 'PA', 'PAN', 'Panama',             'grey',  FALSE, FALSE),
                                                                                                                                            (13, 'LR', 'LBR', 'Liberia',            'white', FALSE, FALSE),
                                                                                                                                            (14, 'MH', 'MHL', 'Wyspy Marshalla',    'white', FALSE, FALSE),
                                                                                                                                            (15, 'MT', 'MLT', 'Malta',              'white', TRUE,  FALSE),
                                                                                                                                            (16, 'CY', 'CYP', 'Cypr',               'white', TRUE,  FALSE),
                                                                                                                                            (17, 'RU', 'RUS', 'Rosja',              'black', FALSE, TRUE),
                                                                                                                                            (18, 'BY', 'BLR', 'Białoruś',           'not_assessed', FALSE, TRUE),
                                                                                                                                            (19, 'CN', 'CHN', 'Chiny',              'grey',  FALSE, FALSE),
                                                                                                                                            (20, 'KR', 'KOR', 'Korea Południowa',   'white', FALSE, FALSE),
                                                                                                                                            (21, 'IR', 'IRN', 'Iran',               'black', FALSE, TRUE),
                                                                                                                                            (22, 'KP', 'PRK', 'Korea Północna',     'black', FALSE, TRUE),
                                                                                                                                            (23, 'SY', 'SYR', 'Syria',              'not_assessed', FALSE, TRUE),
                                                                                                                                            (24, 'BE', 'BEL', 'Belgia',             'white', TRUE,  FALSE),
                                                                                                                                            (25, 'FR', 'FRA', 'Francja',            'white', TRUE,  FALSE),
                                                                                                                                            (26, 'ES', 'ESP', 'Hiszpania',          'white', TRUE,  FALSE),
                                                                                                                                            (27, 'IT', 'ITA', 'Włochy',             'white', TRUE,  FALSE),
                                                                                                                                            (28, 'GR', 'GRC', 'Grecja',             'grey',  TRUE,  FALSE),
                                                                                                                                            (29, 'TR', 'TUR', 'Turcja',             'grey',  FALSE, FALSE),
                                                                                                                                            (30, 'SG', 'SGP', 'Singapur',           'white', FALSE, FALSE);

-- ----------------------------------------------------------------------------
-- currencies
-- ----------------------------------------------------------------------------
INSERT INTO currencies (currency_code, currency_name, minor_unit) VALUES
                                                                      ('EUR', 'Euro', 2),
                                                                      ('USD', 'Dolar amerykański', 2),
                                                                      ('PLN', 'Złoty polski', 2),
                                                                      ('GBP', 'Funt brytyjski', 2);

-- ----------------------------------------------------------------------------
-- classification_societies (główni członkowie IACS + przykład non-IACS)
-- ----------------------------------------------------------------------------
INSERT INTO classification_societies (society_name, is_iacs_member, country_id) VALUES
                                                                                    ('DNV',                        TRUE,  10),
                                                                                    ('Lloyd''s Register',          TRUE,  11),
                                                                                    ('American Bureau of Shipping (ABS)', TRUE, NULL),
                                                                                    ('Bureau Veritas',             TRUE,  25),
                                                                                    ('RINA',                       TRUE,  27),
                                                                                    ('Polski Rejestr Statków (PRS)', TRUE, 1),
                                                                                    ('Russian Maritime Register of Shipping (RS)', TRUE, 17),
                                                                                    ('Unrecognized Local Class Society', FALSE, NULL);

-- ----------------------------------------------------------------------------
-- vessel_type_reference (granularna klasyfikacja, baseline ryzyka per typ)
-- ----------------------------------------------------------------------------
INSERT INTO vessel_type_reference (type_family, ais_category, ais_numeric_code, statcode5_label, type_description, typical_risk_baseline, requires_icebreaker_priority) VALUES
                                                                                                                                                                            ('container_ship',       'cargo',               70, 'Container Ship',                'Statek do przewozu kontenerów',                          15.0, FALSE),
                                                                                                                                                                            ('bulk_carrier',         'cargo',               70, 'Bulk Carrier',                   'Masowiec - ładunki sypkie',                              20.0, FALSE),
                                                                                                                                                                            ('general_cargo',        'cargo',               70, 'General Cargo Ship',             'Drobnicowiec',                                           15.0, FALSE),
                                                                                                                                                                            ('ro_ro_cargo',           'cargo',               70, 'Ro-Ro Cargo Ship',                'Statek typu roll-on/roll-off',                           15.0, FALSE),
                                                                                                                                                                            ('ro_pax',                 'passenger',           60, 'Ro-Pax Ship',                      'Statek pasażersko-towarowy (promy)',                     20.0, FALSE),
                                                                                                                                                                            ('oil_tanker',              'tanker',              80, 'Oil Tanker',                        'Tankowiec do przewozu ropy/produktów ropopochodnych',    55.0, FALSE),
                                                                                                                                                                            ('chemical_tanker',          'tanker',              80, 'Chemical Tanker',                    'Chemikaliowiec',                                          60.0, FALSE),
                                                                                                                                                                            ('lng_carrier',                'tanker',              80, 'LNG Carrier',                         'Gazowiec LNG',                                            65.0, FALSE),
                                                                                                                                                                            ('lpg_carrier',                  'tanker',              80, 'LPG Carrier',                          'Gazowiec LPG',                                            60.0, FALSE),
                                                                                                                                                                            ('crude_oil_tanker',               'tanker',              80, 'Crude Oil Tanker',                      'Tankowiec do ropy surowej',                               70.0, FALSE),
                                                                                                                                                                            ('passenger_cruise',                 'passenger',           60, 'Cruise Ship',                            'Statek wycieczkowy',                                       25.0, FALSE),
                                                                                                                                                                            ('ferry',                              'passenger',           60, 'Ferry',                                   'Prom pasażerski',                                          15.0, FALSE),
                                                                                                                                                                            ('fishing_vessel',                       'other',               30, 'Fishing Vessel',                          'Statek rybacki',                                            10.0, FALSE),
                                                                                                                                                                            ('tug',                                    'special_category_a', 52, 'Tug',                                      'Holownik',                                                     5.0, FALSE),
                                                                                                                                                                            ('icebreaker',                               'special_category_a', 53, 'Icebreaker',                              'Lodołamacz',                                                   5.0, FALSE),
                                                                                                                                                                            ('pilot_vessel',                               'special_category_a', 50, 'Pilot Vessel',                            'Statek pilotowy',                                              5.0, FALSE),
                                                                                                                                                                            ('dredger',                                      'special_category_a', 33, 'Dredger',                                  'Pogłębiarka',                                                  10.0, FALSE),
                                                                                                                                                                            ('offshore_supply',                               'cargo',               70, 'Offshore Supply Vessel',                    'Statek zaopatrzenia offshore',                                 20.0, FALSE),
                                                                                                                                                                            ('research_vessel',                                 'other',               58, 'Research Vessel',                            'Statek badawczy',                                              10.0, FALSE),
                                                                                                                                                                            ('naval_combatant',                                   'other',               35, 'Naval Combatant',                              'Okręt wojenny',                                                40.0, FALSE),
                                                                                                                                                                            ('naval_auxiliary',                                     'other',               35, 'Naval Auxiliary',                                'Okręt pomocniczy',                                             30.0, FALSE),
                                                                                                                                                                            ('yacht_pleasure_craft',                                  'other',               37, 'Pleasure Craft',                                  'Jacht rekreacyjny',                                             8.0, FALSE),
                                                                                                                                                                            ('reefer_cargo',                                            'cargo',               70, 'Refrigerated Cargo Ship',                          'Chłodniowiec',                                                  15.0, TRUE),
                                                                                                                                                                            ('heavy_lift_cargo',                                          'cargo',               70, 'Heavy Lift Cargo Ship',                             'Statek do ładunków ciężkich/ponadgabarytowych',                 20.0, FALSE),
                                                                                                                                                                            ('other_unclassified',                                          'other',               90, 'Other / Unclassified',                              'Inny / niesklasyfikowany',                                       25.0, FALSE);

-- ----------------------------------------------------------------------------
-- ports: Trójmiasto (główny fokus) + przykładowe porty UE (dla generyczności)
-- ----------------------------------------------------------------------------
INSERT INTO ports (un_locode, port_name, country_id, location, timezone, max_draft_meters, max_loa_meters, has_icebreaker_support, has_cold_storage_facility, port_authority_name) VALUES
                                                                                                                                                                                       ('PLGDY', 'Gdynia',        1, ST_GeogFromText('POINT(18.5463 54.5189)'), 'Europe/Warsaw', 13.0, 290.0, TRUE,  TRUE,  'Zarząd Morskiego Portu Gdynia S.A.'),
                                                                                                                                                                                       ('PLGDN', 'Gdańsk',        1, ST_GeogFromText('POINT(18.6466 54.3520)'), 'Europe/Warsaw', 17.0, 400.0, TRUE,  TRUE,  'Port Gdańsk Authority'),
                                                                                                                                                                                       ('PLSOP', 'Sopot',         1, ST_GeogFromText('POINT(18.5601 54.4419)'), 'Europe/Warsaw', 4.0,  60.0,  FALSE, FALSE, 'Molo Sopot - przystań'),
                                                                                                                                                                                       ('NLRTM', 'Rotterdam',     3, ST_GeogFromText('POINT(4.4777 51.9244)'),  'Europe/Amsterdam', 24.0, 400.0, FALSE, TRUE, 'Port of Rotterdam Authority'),
                                                                                                                                                                                       ('DEHAM', 'Hamburg',       2, ST_GeogFromText('POINT(9.9937 53.5459)'),  'Europe/Berlin', 15.1, 400.0, TRUE,  TRUE,  'Hamburg Port Authority'),
                                                                                                                                                                                       ('DKCPH', 'Kopenhaga',     4, ST_GeogFromText('POINT(12.6035 55.6886)'), 'Europe/Copenhagen', 16.0, 300.0, TRUE, TRUE, 'Copenhagen Malmö Port'),
                                                                                                                                                                                       ('SEGOT', 'Göteborg',      5, ST_GeogFromText('POINT(11.9667 57.7000)'), 'Europe/Stockholm', 13.5, 300.0, TRUE, TRUE, 'Göteborgs Hamn AB'),
                                                                                                                                                                                       ('FIHEL', 'Helsinki',      6, ST_GeogFromText('POINT(24.9384 60.1699)'), 'Europe/Helsinki', 11.0, 250.0, TRUE,  TRUE, 'Port of Helsinki');

-- ----------------------------------------------------------------------------
-- berths: przykładowe nabrzeża dla Gdyni i Gdańska (z notatek: igloporty itd.)
-- ----------------------------------------------------------------------------
INSERT INTO berths (port_id, berth_code, berth_name, max_draft_meters, max_loa_meters, max_dwt_tonnes, supports_dangerous_goods, supports_reefer_containers, supports_ro_ro, has_shore_power, crane_capacity_tonnes)
SELECT p.port_id, b.berth_code, b.berth_name, b.max_draft, b.max_loa, b.max_dwt, b.dg, b.reefer, b.roro, b.shore_power, b.crane
FROM ports p
         JOIN (VALUES
                   ('PLGDY', 'NAB-HOL',   'Nabrzeże Holenderskie',           10.0, 200.0, 60000,  FALSE, TRUE,  FALSE, TRUE,  40.0),
                   ('PLGDY', 'NAB-FRA',   'Nabrzeże Francuskie',              12.5, 290.0, 100000, TRUE,  FALSE, FALSE, TRUE,  60.0),
                   ('PLGDY', 'NAB-CHL',   'Nabrzeże Chłodnicze (Igloport)',    9.0, 180.0, 40000,  FALSE, TRUE,  FALSE, TRUE,  25.0),
                   ('PLGDN', 'DCT-T1',    'DCT Terminal Kontenerowy T1',      17.0, 400.0, 200000, FALSE, TRUE,  FALSE, TRUE,  80.0),
                   ('PLGDN', 'NAB-PALIW', 'Nabrzeże Paliwowe',                 15.0, 250.0, 150000, TRUE,  FALSE, FALSE, FALSE, 0.0)
) AS b(loc, berth_code, berth_name, max_draft, max_loa, max_dwt, dg, reefer, roro, shore_power, crane)
              ON p.un_locode = b.loc;

-- ----------------------------------------------------------------------------
-- risk_factor_definitions: domyślne (globalne) wagi czynników ryzyka
-- ----------------------------------------------------------------------------
INSERT INTO risk_factor_definitions (factor_category, factor_code, factor_label, description, weight, max_score_contribution) VALUES
                                                                                                                                  ('flag_state_performance',  'FLAG_BLACKLIST',        'Flaga na czarnej liście Paris MoU',          'Statek pływa pod flagą sklasyfikowaną jako black list',    3.0, 25.0),
                                                                                                                                  ('flag_state_performance',  'FLAG_GREYLIST',         'Flaga na szarej liście Paris MoU',            'Statek pływa pod flagą sklasyfikowaną jako grey list',     1.5, 12.0),
                                                                                                                                  ('vessel_age',              'AGE_OVER_20Y',          'Statek starszy niż 20 lat',                    'Wiek statku > 20 lat zwiększa ryzyko usterek',             1.0, 10.0),
                                                                                                                                  ('vessel_type',             'TYPE_TANKER_HAZARDOUS', 'Tankowiec/gazowiec',                            'Statki przewożące ładunki niebezpieczne luzem',            2.0, 20.0),
                                                                                                                                  ('psc_history',             'PSC_DEFICIENCIES_HIGH', 'Wysoka liczba usterek PSC',                      '5 lub więcej usterek w ostatniej inspekcji PSC',           2.5, 20.0),
                                                                                                                                  ('detention_history',       'DETENTION_LAST_36M',    'Zatrzymanie w ciągu ostatnich 36 miesięcy',       'Statek zatrzymany przez PSC w ciągu ostatnich 3 lat',      3.0, 25.0),
                                                                                                                                  ('sanctions_exposure',      'SANCTIONS_CONFIRMED',   'Potwierdzone trafienie sankcyjne',                  'Statek lub armator na liście sankcyjnej (OFAC/UE/UK)',     5.0, 50.0),
                                                                                                                                  ('sanctions_exposure',      'SANCTIONS_POTENTIAL',   'Potencjalne trafienie sankcyjne',                    'Wymaga manualnej weryfikacji - możliwe trafienie',         2.0, 15.0),
                                                                                                                                  ('cargo_hazard_class',      'CARGO_IMDG_HIGH',       'Ładunek wysokiego ryzyka (IMDG klasa 1/2/7)',         'Materiały wybuchowe, gazy lub radioaktywne',               3.0, 20.0),
                                                                                                                                  ('ownership_transparency',  'OWNERSHIP_OPAQUE',      'Nieprzejrzysta struktura własności',                   'Brak jasno zidentyfikowanego beneficjenta rzeczywistego',  2.0, 15.0),
                                                                                                                                  ('classification_society',  'CLASS_NON_IACS',        'Towarzystwo klasyfikacyjne non-IACS',                   'Klasa nie jest członkiem IACS - niższe zaufanie',          1.5, 10.0),
                                                                                                                                  ('dark_activity',           'AIS_DARK_PERIODS',      'Przerwy w transmisji AIS',                               'Wykryte okresy wyłączenia/zaniku sygnału AIS',            2.5, 18.0),
                                                                                                                                  ('document_completeness',   'DOCS_INCOMPLETE',       'Niekompletna dokumentacja nominacyjna',                   'Brak wymaganych danych w nominacji armatorskiej',         1.0, 8.0);


-- ============================================================================
-- Część 7: FUNKCJA OBLICZAJĄCA RISK SCORE + WIDOKI POMOCNICZE
-- To jest mechanizm, który realizuje: "rosyjski kontenerowiec z gazem = wysokie
-- ryzyko, stateczek ze zwierskiem = niskie ryzyko" w sposób w pełni
-- konfigurowalny (wagi z risk_factor_definitions, nie hardkodowane w kodzie).
-- ============================================================================
SET search_path TO port_intel, public;

-- ----------------------------------------------------------------------------
-- FUNKCJA: calculate_vessel_risk_score
-- Liczy wynik ryzyka dla statku na podstawie aktualnych danych i zapisuje
-- nową ocenę (INSERT-ONLY) w vessel_risk_assessments + rozbicie na czynniki.
-- Zwraca assessment_id nowo utworzonej oceny.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION calculate_vessel_risk_score(
    p_vessel_id UUID,
    p_nomination_id UUID DEFAULT NULL,
    p_port_call_id UUID DEFAULT NULL,
    p_trigger VARCHAR DEFAULT 'manual_review',
    p_assessed_by VARCHAR DEFAULT 'system_auto'
) RETURNS UUID AS $$
DECLARE
    v_assessment_id UUID;
    v_total_score NUMERIC(5,2) := 0;
    v_tier risk_tier;
    v_vessel RECORD;
    v_factor RECORD;
    v_contribution NUMERIC(5,2);
    v_recent_deficiencies INTEGER;
    v_recent_detention BOOLEAN;
    v_has_hazardous_cargo BOOLEAN;
    v_is_non_iacs BOOLEAN;
    v_ownership_opaque BOOLEAN;
    v_sanctions_confirmed BOOLEAN;
    v_sanctions_potential BOOLEAN;
BEGIN
    -- Pobierz podstawowe dane statku wraz z flagą i typem
    SELECT v.vessel_id, v.flag_country_id, v.year_built, v.vessel_type_id,
           v.classification_society_id, c.paris_mou_flag_tier,
           vt.typical_risk_baseline, vt.type_family,
           cs.is_iacs_member
    INTO v_vessel
    FROM vessels v
             LEFT JOIN countries c ON c.country_id = v.flag_country_id
             LEFT JOIN vessel_type_reference vt ON vt.vessel_type_id = v.vessel_type_id
             LEFT JOIN classification_societies cs ON cs.society_id = v.classification_society_id
    WHERE v.vessel_id = p_vessel_id;

    IF v_vessel IS NULL THEN
        RAISE EXCEPTION 'Vessel % not found', p_vessel_id;
    END IF;

    -- Baseline ryzyka z typu statku
    v_total_score := COALESCE(v_vessel.typical_risk_baseline, 10.0);

    -- Utwórz wpis oceny (najpierw szkic, wypełnimy score na końcu)
    -- Odznacz poprzednią ocenę jako nieaktualną
    UPDATE vessel_risk_assessments SET is_current = FALSE
    WHERE vessel_id = p_vessel_id AND is_current = TRUE;

    INSERT INTO vessel_risk_assessments (
        vessel_id, nomination_id, port_call_id, overall_risk_score,
        risk_tier, assessment_trigger, assessed_by, is_current
    ) VALUES (
                 p_vessel_id, p_nomination_id, p_port_call_id, 0, 'low_risk',
                 p_trigger, p_assessed_by, TRUE
             ) RETURNING assessment_id INTO v_assessment_id;

    -- ---- Czynnik: flaga na czarnej/szarej liście Paris MoU ----
    IF v_vessel.paris_mou_flag_tier = 'black' THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'FLAG_BLACKLIST' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'flag_tier=black', v_contribution);
        END IF;
    ELSIF v_vessel.paris_mou_flag_tier = 'grey' THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'FLAG_GREYLIST' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'flag_tier=grey', v_contribution);
        END IF;
    END IF;

    -- ---- Czynnik: wiek statku > 20 lat ----
    IF v_vessel.year_built IS NOT NULL AND (EXTRACT(YEAR FROM CURRENT_DATE) - v_vessel.year_built) > 20 THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'AGE_OVER_20Y' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'age_years=' || (EXTRACT(YEAR FROM CURRENT_DATE) - v_vessel.year_built), v_contribution);
        END IF;
    END IF;

    -- ---- Czynnik: typ statku - tankowiec/gazowiec (hazardowy z definicji) ----
    IF v_vessel.type_family IN ('oil_tanker','chemical_tanker','lng_carrier','lpg_carrier','crude_oil_tanker') THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'TYPE_TANKER_HAZARDOUS' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'type_family=' || v_vessel.type_family, v_contribution);
        END IF;
    END IF;

    -- ---- Czynnik: usterki PSC w ostatniej inspekcji ----
    SELECT deficiency_count INTO v_recent_deficiencies
    FROM psc_inspections
    WHERE vessel_id = p_vessel_id
    ORDER BY inspection_date DESC LIMIT 1;

    IF v_recent_deficiencies IS NOT NULL AND v_recent_deficiencies >= 5 THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'PSC_DEFICIENCIES_HIGH' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'deficiency_count=' || v_recent_deficiencies, v_contribution);
        END IF;
    END IF;

    -- ---- Czynnik: zatrzymanie w ciągu ostatnich 36 miesięcy ----
    SELECT EXISTS (
        SELECT 1 FROM psc_inspections
        WHERE vessel_id = p_vessel_id
          AND was_detained = TRUE
          AND inspection_date >= (CURRENT_DATE - INTERVAL '36 months')
    ) INTO v_recent_detention;

    IF v_recent_detention THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'DETENTION_LAST_36M' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'detained_last_36m=true', v_contribution);
        END IF;
    END IF;

    -- ---- Czynnik: sankcje - potwierdzone i potencjalne (statek lub armator) ----
    SELECT EXISTS (
        SELECT 1 FROM sanctions_screening_results ssr
        WHERE (ssr.vessel_id = p_vessel_id
            OR ssr.company_id IN (
                SELECT company_id FROM vessel_company_roles
                WHERE vessel_id = p_vessel_id AND is_current = TRUE
            ))
          AND ssr.screening_result = 'confirmed_match'
    ) INTO v_sanctions_confirmed;

    IF v_sanctions_confirmed THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'SANCTIONS_CONFIRMED' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'sanctions=confirmed_match', v_contribution);
        END IF;
    ELSE
        SELECT EXISTS (
            SELECT 1 FROM sanctions_screening_results ssr
            WHERE (ssr.vessel_id = p_vessel_id
                OR ssr.company_id IN (
                    SELECT company_id FROM vessel_company_roles
                    WHERE vessel_id = p_vessel_id AND is_current = TRUE
                ))
              AND ssr.screening_result = 'potential_match'
        ) INTO v_sanctions_potential;

        IF v_sanctions_potential THEN
            SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'SANCTIONS_POTENTIAL' AND is_active;
            IF FOUND THEN
                v_contribution := v_factor.max_score_contribution;
                v_total_score := v_total_score + v_contribution;
                INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
                VALUES (v_assessment_id, v_factor.factor_id, 'sanctions=potential_match', v_contribution);
            END IF;
        END IF;
    END IF;

    -- ---- Czynnik: ładunek wysokiego ryzyka (jeśli oceniamy w kontekście nominacji) ----
    IF p_nomination_id IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1 FROM cargo_manifests
            WHERE nomination_id = p_nomination_id
              AND imdg_hazard_class IN ('class_1_explosives','class_2_gases','class_7_radioactive')
        ) INTO v_has_hazardous_cargo;

        IF v_has_hazardous_cargo THEN
            SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'CARGO_IMDG_HIGH' AND is_active;
            IF FOUND THEN
                v_contribution := v_factor.max_score_contribution;
                v_total_score := v_total_score + v_contribution;
                INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
                VALUES (v_assessment_id, v_factor.factor_id, 'imdg_class=high_risk', v_contribution);
            END IF;
        END IF;
    END IF;

    -- ---- Czynnik: towarzystwo klasyfikacyjne non-IACS ----
    v_is_non_iacs := (v_vessel.classification_society_id IS NOT NULL AND v_vessel.is_iacs_member = FALSE);
    IF v_is_non_iacs THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'CLASS_NON_IACS' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'classification_society=non_iacs', v_contribution);
        END IF;
    END IF;

    -- ---- Czynnik: nieprzejrzysta struktura własności ----
    SELECT EXISTS (
        SELECT 1 FROM vessel_company_roles vcr
                          JOIN companies c ON c.company_id = vcr.company_id
        WHERE vcr.vessel_id = p_vessel_id
          AND vcr.is_current = TRUE
          AND c.ownership_transparency_flag = FALSE
    ) INTO v_ownership_opaque;

    IF v_ownership_opaque THEN
        SELECT * INTO v_factor FROM risk_factor_definitions WHERE factor_code = 'OWNERSHIP_OPAQUE' AND is_active;
        IF FOUND THEN
            v_contribution := v_factor.max_score_contribution;
            v_total_score := v_total_score + v_contribution;
            INSERT INTO vessel_risk_assessment_factors (assessment_id, factor_id, factor_value_observed, score_contribution)
            VALUES (v_assessment_id, v_factor.factor_id, 'ownership_transparency=opaque', v_contribution);
        END IF;
    END IF;

    -- Ogranicz wynik do zakresu 0-100
    v_total_score := LEAST(v_total_score, 100.0);

    -- Ustal tier ryzyka na podstawie wyniku końcowego
    v_tier := CASE
                  WHEN v_sanctions_confirmed THEN 'critical_risk'
                  WHEN v_total_score >= 60 THEN 'high_risk'
                  WHEN v_total_score >= 30 THEN 'standard_risk'
                  ELSE 'low_risk'
        END;

    -- Zapisz finalny wynik w już utworzonym wierszu oceny
    UPDATE vessel_risk_assessments
    SET overall_risk_score = v_total_score,
        risk_tier = v_tier
    WHERE assessment_id = v_assessment_id;

    RETURN v_assessment_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_vessel_risk_score IS 'Liczy i zapisuje (insert-only) nową ocenę ryzyka statku na podstawie konfigurowalnych wag z risk_factor_definitions. Zwraca assessment_id. Przykład: SELECT calculate_vessel_risk_score(''<vessel_uuid>'');';

-- ============================================================================
-- WIDOKI POMOCNICZE (do szybkiego demo / dashboardu na hakaton)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- v_vessel_current_risk: aktualny risk score + tier dla każdego statku
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_vessel_current_risk AS
SELECT
    v.vessel_id,
    v.imo_number,
    v.current_vessel_name,
    v.domain,
    vt.type_family,
    co.country_name AS flag_country,
    co.paris_mou_flag_tier,
    ra.overall_risk_score,
    ra.risk_tier,
    ra.assessed_at,
    ra.assessment_trigger
FROM vessels v
         LEFT JOIN vessel_type_reference vt ON vt.vessel_type_id = v.vessel_type_id
         LEFT JOIN countries co ON co.country_id = v.flag_country_id
         LEFT JOIN vessel_risk_assessments ra ON ra.vessel_id = v.vessel_id AND ra.is_current = TRUE;
COMMENT ON VIEW v_vessel_current_risk IS 'Szybki przegląd: aktualny risk score i tier dla każdego statku w rejestrze.';

-- ----------------------------------------------------------------------------
-- v_nomination_summary: pełny obraz nominacji wraz z ryzykiem i armatorem
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_nomination_summary AS
SELECT
    n.nomination_id,
    n.status,
    v.imo_number,
    v.current_vessel_name,
    c.company_name AS nominating_company,
    p.port_name AS destination_port,
    n.eta,
    n.etd,
    b.berth_name AS assigned_berth,
    ra.overall_risk_score,
    ra.risk_tier,
    n.created_at
FROM nominations n
         JOIN vessels v ON v.vessel_id = n.vessel_id
         JOIN companies c ON c.company_id = n.nominating_company_id
         JOIN ports p ON p.port_id = n.destination_port_id
         LEFT JOIN berths b ON b.berth_id = n.assigned_berth_id
         LEFT JOIN vessel_risk_assessments ra ON ra.vessel_id = v.vessel_id AND ra.is_current = TRUE;
COMMENT ON VIEW v_nomination_summary IS 'Widok roboczy agenta portowego: wszystkie aktywne nominacje z kontekstem ryzyka, gotowe do filtrowania na dashboardzie.';

-- ----------------------------------------------------------------------------
-- v_berth_availability: szybkie sprawdzenie dostępności nabrzeży
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_berth_availability AS
SELECT
    b.berth_id,
    p.port_name,
    b.berth_code,
    b.berth_name,
    b.max_draft_meters,
    b.max_loa_meters,
    b.supports_dangerous_goods,
    b.supports_reefer_containers,
    bo.occupied_from,
    bo.occupied_until,
    CASE WHEN bo.occupancy_id IS NULL THEN TRUE ELSE FALSE END AS currently_free
FROM berths b
         JOIN ports p ON p.port_id = b.port_id
         LEFT JOIN berth_occupancy bo
                   ON bo.berth_id = b.berth_id
                       AND tstzrange(bo.occupied_from, bo.occupied_until) @> now()
WHERE b.is_active = TRUE;
COMMENT ON VIEW v_berth_availability IS 'Bieżąca dostępność nabrzeży - czy zajęte teraz, i przez jaki przedział czasu.';


-- ============================================================================
-- Część 8: DANE DEMO (przykładowe statki ilustrujące model ryzyka)
-- Specjalnie wybrane, by zademonstrować rozpiętość: od rybackiej łódki
-- (niskie ryzyko) do tankowca pod sankcjonowaną flagą z gazem (wysokie ryzyko).
-- ============================================================================
SET search_path TO port_intel, public;

-- ----------------------------------------------------------------------------
-- Firmy (armatorzy/operatorzy)
-- ----------------------------------------------------------------------------
INSERT INTO companies (company_id, imo_company_number, company_name, country_id, ownership_transparency_flag, is_sanctioned) VALUES
                                                                                                                                 ('a0000000-0000-0000-0000-000000000001', '5432109', 'Baltic Fishing Co-op',           1,  TRUE,  FALSE),
                                                                                                                                 ('a0000000-0000-0000-0000-000000000002', '5432110', 'Nordic Container Lines AS',       5,  TRUE,  FALSE),
                                                                                                                                 ('a0000000-0000-0000-0000-000000000003', '5432111', 'Severnaya Gas Shipping LLC',       17, FALSE, FALSE),
                                                                                                                                 ('a0000000-0000-0000-0000-000000000004', '5432112', 'Hanseatic Ferry Group GmbH',         2,  TRUE,  FALSE);

INSERT INTO company_contacts (company_id, first_name, last_name, job_title, email, is_primary_for_nominations) VALUES
                                                                                                                   ('a0000000-0000-0000-0000-000000000001', 'Jan',    'Kowalski',  'Operations Manager', 'j.kowalski@balticfishing.example', TRUE),
                                                                                                                   ('a0000000-0000-0000-0000-000000000002', 'Lars',   'Andersen',  'Fleet Coordinator',   'l.andersen@nordiccontainer.example', TRUE),
                                                                                                                   ('a0000000-0000-0000-0000-000000000003', 'Igor',   'Volkov',    'Chartering Agent',     'i.volkov@severnayagas.example', TRUE),
                                                                                                                   ('a0000000-0000-0000-0000-000000000004', 'Greta',  'Hoffmann',  'Port Liaison',           'g.hoffmann@hanseaticferry.example', TRUE);

-- ----------------------------------------------------------------------------
-- Statki: 4 przykłady o rosnącym ryzyku
-- ----------------------------------------------------------------------------
INSERT INTO vessels (vessel_id, imo_number, mmsi, call_sign, current_vessel_name, domain, vessel_type_id, flag_country_id, year_built, classification_society_id) VALUES
                                                                                                                                                                      -- 1. Mały kuter rybacki, polska flaga -> NISKIE RYZYKO
                                                                                                                                                                      ('b0000000-0000-0000-0000-000000000001', '8814422', '261001234', 'SPM1234', 'Mewa Bałtycka',
                                                                                                                                                                       'commercial', (SELECT vessel_type_id FROM vessel_type_reference WHERE type_family='fishing_vessel'),
                                                                                                                                                                       1, 2015, (SELECT society_id FROM classification_societies WHERE society_name LIKE 'Polski%')),
                                                                                                                                                                      -- 2. Kontenerowiec norweski, nowy, dobra flaga -> NISKIE/STANDARDOWE RYZYKO
                                                                                                                                                                      ('b0000000-0000-0000-0000-000000000002', '9456789', '257123456', 'LADW7',   'Nordic Voyager',
                                                                                                                                                                       'commercial', (SELECT vessel_type_id FROM vessel_type_reference WHERE type_family='container_ship'),
                                                                                                                                                                       5, 2019, (SELECT society_id FROM classification_societies WHERE society_name = 'DNV')),
                                                                                                                                                                      -- 3. Prom pasażerski, niemiecki -> NISKIE RYZYKO
                                                                                                                                                                      ('b0000000-0000-0000-0000-000000000003', '9234567', '211987654', 'DABC3',   'Hanse Star',
                                                                                                                                                                       'commercial', (SELECT vessel_type_id FROM vessel_type_reference WHERE type_family='ferry'),
                                                                                                                                                                       2, 2017, (SELECT society_id FROM classification_societies WHERE society_name = 'Bureau Veritas')),
                                                                                                                                                                      -- 4. Rosyjski gazowiec LNG, stary, flaga czarnej listy, non-IACS class -> WYSOKIE RYZYKO
                                                                                                                                                                      ('b0000000-0000-0000-0000-000000000004', '9112233', '273445566', 'UCEF8',   'Sibirskaya Zvezda',
                                                                                                                                                                       'commercial', (SELECT vessel_type_id FROM vessel_type_reference WHERE type_family='lng_carrier'),
                                                                                                                                                                       17, 1998, (SELECT society_id FROM classification_societies WHERE society_name = 'Unrecognized Local Class Society'));

-- Role firmowe (armator rejestrowy) dla statków
INSERT INTO vessel_company_roles (vessel_id, company_id, role_type, is_current) VALUES
                                                                                    ('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'registered_owner', TRUE),
                                                                                    ('b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000002', 'registered_owner', TRUE),
                                                                                    ('b0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000004', 'registered_owner', TRUE),
                                                                                    ('b0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000003', 'registered_owner', TRUE);

-- Oznacz statek #4 jako mający nieprzejrzystą strukturę własności (typowy red flag)
UPDATE companies SET ownership_transparency_flag = FALSE WHERE company_id = 'a0000000-0000-0000-0000-000000000003';

-- Dane techniczne statków
INSERT INTO vessel_technical_specs (vessel_id, length_overall_meters, beam_meters, draft_meters, gross_tonnage, deadweight_tonnage, container_capacity_teu, has_reefer_plugs, reefer_plug_count, data_source) VALUES
                                                                                                                                                                                                                  ('b0000000-0000-0000-0000-000000000001', 24.5,  6.2,  3.1,  180,   220,    NULL, FALSE, NULL, 'manual'),
                                                                                                                                                                                                                  ('b0000000-0000-0000-0000-000000000002', 294.0, 32.3, 13.5, 95000, 110000, 8500, TRUE,  600,  'VesselFinder'),
                                                                                                                                                                                                                  ('b0000000-0000-0000-0000-000000000003', 188.0, 25.0, 6.2,  28000, 6500,   NULL, FALSE, NULL, 'MarineTraffic'),
                                                                                                                                                                                                                  ('b0000000-0000-0000-0000-000000000004', 285.0, 44.0, 11.5, 98000, 75000,  NULL, FALSE, NULL, 'manual');

-- Przykładowa historia PSC: statek #4 ma usterki i zatrzymanie (realistyczny red flag)
INSERT INTO psc_inspections (vessel_id, inspecting_port_id, inspecting_authority, inspection_date, deficiency_count, was_detained, detention_days) VALUES
                                                                                                                                                       ('b0000000-0000-0000-0000-000000000004', (SELECT port_id FROM ports WHERE un_locode='PLGDN'), 'Paris MoU', CURRENT_DATE - INTERVAL '8 months', 7, TRUE, 4),
                                                                                                                                                       ('b0000000-0000-0000-0000-000000000002', (SELECT port_id FROM ports WHERE un_locode='NLRTM'), 'Paris MoU', CURRENT_DATE - INTERVAL '14 months', 1, FALSE, NULL);

-- Przykładowy wynik przeglądu sankcyjnego dla statku #4 (potencjalne trafienie -> wymaga weryfikacji)
INSERT INTO sanctions_screening_results (vessel_id, list_source, screening_result, matched_entry_name, match_confidence_pct) VALUES
    ('b0000000-0000-0000-0000-000000000004', 'eu_consolidated', 'potential_match', 'SIBIRSKAYA ZVEZDA SHIPPING', 78.5);

-- ----------------------------------------------------------------------------
-- Przykładowa nominacja armatorska (statek #2, kontenerowiec, do Gdyni)
-- ----------------------------------------------------------------------------
INSERT INTO nominations (
    nomination_id, vessel_id, nominating_company_id, nominating_contact_id,
    destination_port_id, status, eta, etd,
    source_email_subject, source_email_body_raw, source_email_received_at, source_email_sender_address,
    assigned_agent_name
) VALUES (
             'c0000000-0000-0000-0000-000000000001',
             'b0000000-0000-0000-0000-000000000002',
             'a0000000-0000-0000-0000-000000000002',
             (SELECT contact_id FROM company_contacts WHERE email = 'l.andersen@nordiccontainer.example'),
             (SELECT port_id FROM ports WHERE un_locode = 'PLGDY'),
             'parsed_pending_review',
             now() + INTERVAL '3 days',
             now() + INTERVAL '4 days',
             'Vessel Nomination - MV Nordic Voyager - ETA Gdynia',
             'Dear Agent, please find nomination details for MV Nordic Voyager, IMO 9456789, ETA Gdynia 3 days, laden with 6200 TEU containers, requesting berth with reefer plugs. Regards, Lars',
             now() - INTERVAL '2 hours',
             'l.andersen@nordiccontainer.example',
             'Michał Samaruk'
         );

INSERT INTO nomination_unstructured_notes (nomination_id, note_text, extracted_by, confidence_score, requires_human_review) VALUES
    ('c0000000-0000-0000-0000-000000000001', 'Armator wspomina o możliwym opóźnieniu 6h ze względu na warunki pogodowe na Bałtyku - do potwierdzenia bliżej ETA.', 'llm', 0.81, TRUE);

INSERT INTO cargo_manifests (nomination_id, cargo_description, cargo_quantity, cargo_unit, imdg_hazard_class, requires_refrigeration, is_perishable) VALUES
    ('c0000000-0000-0000-0000-000000000001', 'Kontenery mieszane, w tym reefer', 6200, 'TEU', 'none', TRUE, TRUE);

-- ============================================================================
-- Wygeneruj oceny ryzyka dla wszystkich 4 statków demo
-- ============================================================================
SELECT calculate_vessel_risk_score('b0000000-0000-0000-0000-000000000001', NULL, NULL, 'initial_seed', 'system_auto');
SELECT calculate_vessel_risk_score('b0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000001', NULL, 'new_nomination', 'system_auto');
SELECT calculate_vessel_risk_score('b0000000-0000-0000-0000-000000000003', NULL, NULL, 'initial_seed', 'system_auto');
SELECT calculate_vessel_risk_score('b0000000-0000-0000-0000-000000000004', NULL, NULL, 'initial_seed', 'system_auto');