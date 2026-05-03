"""
PromptShield — example usage script.

Run from the project root::

    pip install -e .
    python example_usage.py
"""

import re

from promptshield import Shield
from promptshield.detector.base import BaseDetector, DetectedEntity
from promptshield.exceptions import SensitiveDataError
from promptshield.policy.models import Action, PolicyConfig, Rule


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


# ── Example 1: Load policy from YAML ──────────────────────────────────────
separator("1 · Load policy from policy.yaml")

shield = Shield(config_path="policy.yaml")

examples = [
    "Hello, my name is Alice — no sensitive data here.",
    "Please reach out to me at alice@example.com.",
    "You can also call me at 555-867-5309.",
    "My international number is +44 7911 123456.",
]

for prompt in examples:
    result = shield.scan(prompt)
    print(f"  IN : {prompt}")
    print(f"  OUT: {result}\n")


# ── Example 2: Block on API key ────────────────────────────────────────────
separator("2 · Block when an API key is detected")

try:
    prompt = "My OpenAI key is sk-abcdefABCDEF12345678901234"
    shield.scan(prompt)
except SensitiveDataError as exc:
    print(f"  Blocked! ({exc.entity_type}): {exc}")


# ── Example 3: Block on credit card ───────────────────────────────────────
separator("3 · Block when a credit card number is detected")

try:
    prompt = "Charge card 4111-1111-1111-1111 for $99."
    shield.scan(prompt)
except SensitiveDataError as exc:
    print(f"  Blocked! ({exc.entity_type}): {exc}")


# ── Example 4: Programmatic config (no YAML file) ─────────────────────────
separator("4 · Programmatic config — mask email, block credit card")

config = PolicyConfig(
    rules=[
        Rule(type="email", action=Action.MASK),
        Rule(type="credit_card", action=Action.BLOCK),
    ],
    default_action=Action.ALLOW,
)
inline_shield = Shield(config=config)

try:
    prompt = "Invoice for customer@company.org — card 4111-1111-1111-1111"
    result = inline_shield.scan(prompt)
    print(f"  OUT: {result}")
except SensitiveDataError as exc:
    print(f"  Blocked! ({exc.entity_type}): {exc}")


# ── Example 5: Custom plug-in detector ────────────────────────────────────
separator("5 · Custom detector — US Social Security Numbers")


class SSNDetector(BaseDetector):
    """Detect US Social Security Numbers (XXX-XX-XXXX)."""

    _PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    def detect(self, text: str) -> list[DetectedEntity]:
        return [
            DetectedEntity("ssn", m.group(), m.start(), m.end())
            for m in self._PATTERN.finditer(text)
        ]

    @property
    def supported_types(self) -> list[str]:
        return ["ssn"]


custom_config = PolicyConfig(
    rules=[Rule(type="ssn", action=Action.MASK)],
    default_action=Action.ALLOW,
)
custom_shield = Shield(config=custom_config, detectors=[SSNDetector()])

prompt = "Patient SSN: 123-45-6789 was admitted on Monday."
result = custom_shield.scan(prompt)
print(f"  IN : {prompt}")
print(f"  OUT: {result}")


# ── Example 6: scan_response — sanitise LLM output ────────────────────────
separator("6 · scan_response — sanitise LLM output before returning")

response_shield = Shield(
    config=PolicyConfig(
        rules=[Rule(type="email", action=Action.MASK)],
        default_action=Action.ALLOW,
    )
)
llm_response = "Sure! You can reach support at support@internal.corp anytime."
safe = response_shield.scan_response(llm_response)
print(f"  LLM : {llm_response}")
print(f"  Safe: {safe}")

print("\nDone.\n")
