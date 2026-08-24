"""India DPDPA (Digital Personal Data Protection Act, 2023) compliance profile.

Covers all personal data categories recognised under the DPDPA:
  * Aadhaar UID (biometric-adjacent — block)
  * PAN card (financial identifier — block)
  * Passport number (sensitive ID — block)
  * Voter ID / EPIC (sensitive ID — mask)
  * Indian mobile number (mask)
  * GSTIN (business ID — mask)
  * IFSC code (financial — mask)
  * Generic email and phone via RegexDetector (mask)
  * Credit card / API keys (block)
"""

from ..detector.india_detector import IndiaDetector
from ..detector.regex_detector import RegexDetector
from ..policy.models import Action, PolicyConfig, Rule
from .base import Profile

PROFILE = Profile(
    name="india_dpdpa",
    policy=PolicyConfig(
        rules=[
            Rule(type="in_aadhaar",  action=Action.BLOCK),
            Rule(type="in_pan",      action=Action.BLOCK),
            Rule(type="in_passport", action=Action.BLOCK),
            Rule(type="in_voter_id", action=Action.MASK),
            Rule(type="in_phone",    action=Action.MASK),
            Rule(type="in_gstin",    action=Action.MASK),
            Rule(type="in_ifsc",     action=Action.MASK),
            Rule(type="email",       action=Action.MASK),
            Rule(type="phone",       action=Action.MASK),
            Rule(type="credit_card", action=Action.BLOCK),
            Rule(type="api_key",     action=Action.BLOCK),
        ],
        default_action=Action.ALLOW,
    ),
    detectors=[RegexDetector(), IndiaDetector()],
)
