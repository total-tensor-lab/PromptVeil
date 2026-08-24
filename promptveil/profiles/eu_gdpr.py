"""EU GDPR compliance profile.

Covers the personal data categories most commonly processed in EU-regulated
applications:
  * Email address (mask)
  * Phone number (mask)
  * Credit / debit card numbers (block — PCI-DSS overlap)
  * API keys / bearer tokens (block — not strictly GDPR but frequently
    co-regulated for security compliance)
"""

from ..detector.regex_detector import RegexDetector
from ..policy.models import Action, PolicyConfig, Rule
from .base import Profile

PROFILE = Profile(
    name="eu_gdpr",
    policy=PolicyConfig(
        rules=[
            Rule(type="email",       action=Action.MASK),
            Rule(type="phone",       action=Action.MASK),
            Rule(type="credit_card", action=Action.BLOCK),
            Rule(type="api_key",     action=Action.BLOCK),
        ],
        default_action=Action.ALLOW,
    ),
    detectors=[RegexDetector()],
)
