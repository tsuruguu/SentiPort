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