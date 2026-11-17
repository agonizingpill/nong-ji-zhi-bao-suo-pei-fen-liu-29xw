ROLES = ('admin','assessor','viewer')
CLAIM_STATES = ('submitted','queued','assessed','out_of_warranty','paid','denied','failed')
PARTS = ('hydraulic','engine','transmission')

RETURN_STATES=('dispatched','received','verified')
SETTLEMENT_STATES=('draft','approved','booked')

REPAIR_STATES=('reserved','running','completed')
ISSUE_STATES=('issued','returned','consumed')
FOLLOWUP_STATES=('review','rework','closed')

SAMPLING_PLAN_STATES=('draft','confirmed')
SAMPLING_SLOT_STATES=('selected','withdrawn','started')
SAMPLING_SELECTIONS=('random_low','risk_priority')
