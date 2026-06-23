import enum

class NominationStatus(str, enum.Enum):
    received = 'received'
    parsing = 'parsing'
    parsed_pending_review = 'parsed_pending_review'
    verified = 'verified'
    submitted_to_port = 'submitted_to_port'
    acknowledged = 'acknowledged'
    rejected = 'rejected'
    cancelled = 'cancelled'
    completed = 'completed'

class RiskTier(str, enum.Enum):
    low_risk = 'low_risk'
    standard_risk = 'standard_risk'
    high_risk = 'high_risk'
    critical_risk = 'critical_risk'

class ImdgHazardClass(str, enum.Enum):
    none = 'none'
    class_1_explosives = 'class_1_explosives'
    class_2_gases = 'class_2_gases'
    class_3_flammable_liquids = 'class_3_flammable_liquids'
    class_7_radioactive = 'class_7_radioactive'
    class_8_corrosive = 'class_8_corrosive'
    class_9_miscellaneous = 'class_9_miscellaneous'

class VesselDomain(str, enum.Enum):
    commercial = 'commercial'
    military = 'military'
    government = 'government'
    civilian_private = 'civilian_private'
    research_scientific = 'research_scientific'
    fishing = 'fishing'
    unknown = 'unknown'

class PortServiceType(str, enum.Enum):
    pilotage = 'pilotage'
    towage = 'towage'
    mooring_unmooring = 'mooring_unmooring'
    shore_power = 'shore_power'
    fresh_water_supply = 'fresh_water_supply'
    bunkering_fuel = 'bunkering_fuel'
    waste_removal = 'waste_removal'
    medical_services = 'medical_services'
    barber_services = 'barber_services'
    provisions_supply = 'provisions_supply'
    crew_change = 'crew_change'
    customs_clearance = 'customs_clearance'
    security_isps = 'security_isps'
    cargo_surveying = 'cargo_surveying'
    ice_breaking_assistance = 'ice_breaking_assistance'
    waste_water_pumpout = 'waste_water_pumpout'
    other = 'other'

class ServiceOrderStatus(str, enum.Enum):
    requested = 'requested'
    confirmed = 'confirmed'
    in_progress = 'in_progress'
    completed = 'completed'
    cancelled = 'cancelled'
    failed = 'failed'