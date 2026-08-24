"""US HIPAA compliance profile.

Covers the 18 PHI (Protected Health Information) identifier categories
from the HIPAA Safe Harbor method, as detectable via regex:
  * SSN (block — 45 CFR 164.514(b)(2)(i))
  * Email address (mask)
  * Phone / fax number (mask)
  * Credit / debit card (block — financial identifier)
  * API keys (block — security)
  * US passport numbers (mask)
  * EIN (mask — for provider identification)

Non-regex PHI categories (names, geographic data, dates, URLs, device
identifiers, etc.) require NER / ML detectors and are not covered here.
"""

from ..detector.regex_detector import RegexDetector
from ..detector.us_detector import USDetector
from ..policy.models import Action, PolicyConfig, Rule
from .base import Profile

PROFILE = Profile(
    name="us_hipaa",
    policy=PolicyConfig(
        rules=[
            Rule(type="ssn",         action=Action.BLOCK),
            Rule(type="email",       action=Action.MASK),
            Rule(type="phone",       action=Action.MASK),
            Rule(type="credit_card", action=Action.BLOCK),
            Rule(type="api_key",     action=Action.BLOCK),
            Rule(type="us_passport", action=Action.MASK),
            Rule(type="us_ein",      action=Action.MASK),
        ],
        default_action=Action.ALLOW,
    ),
    detectors=[RegexDetector(), USDetector()],
)
