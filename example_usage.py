"""
PromptVeil — example usage script.

Run from the project root::

    pip install -e .
    python example_usage.py
"""

import re

from promptveil import Shield
from promptveil.detector.base import BaseDetector, DetectedEntity
from promptveil.detector.india_detector import IndiaDetector
from promptveil.detector.regex_detector import RegexDetector
from promptveil.exceptions import SensitiveDataError
from promptveil.policy.models import Action, PolicyConfig, Rule


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


# ── Example 7: India PII — mask Aadhaar and phone ─────────────────────────
separator("7 · India PII — mask Aadhaar and phone numbers")

india_mask_config = PolicyConfig(
    rules=[
        Rule(type="in_aadhaar", action=Action.MASK),
        Rule(type="in_phone",   action=Action.MASK),
    ],
    default_action=Action.ALLOW,
)
india_shield = Shield(config=india_mask_config, detectors=[IndiaDetector()])

india_prompts = [
    "My Aadhaar is 2345 6789 0124 and I live in Pune.",
    "Reach me on +91 98765 43210 or at home 09876543210.",
    "Aadhaar: 2345-6789-0124, mobile +91-98765-43210.",
]
for prompt in india_prompts:
    result = india_shield.scan(prompt)
    print(f"  IN : {prompt}")
    print(f"  OUT: {result}\n")


# ── Example 8: India PII — block PAN card ─────────────────────────────────
separator("8 · India PII — block PAN card numbers")

pan_config = PolicyConfig(
    rules=[Rule(type="in_pan", action=Action.BLOCK)],
    default_action=Action.ALLOW,
)
pan_shield = Shield(config=pan_config, detectors=[IndiaDetector()])

try:
    pan_shield.scan("Please process refund for PAN ABCPE1234F.")
except SensitiveDataError as exc:
    print(f"  Blocked! ({exc.entity_type}): {exc}")


# ── Example 9: India PII — mask passport, voter ID, IFSC, GSTIN ───────────
separator("9 · India PII — mask passport, voter ID, IFSC, GSTIN")

doc_config = PolicyConfig(
    rules=[
        Rule(type="in_passport", action=Action.MASK),
        Rule(type="in_voter_id", action=Action.MASK),
        Rule(type="in_ifsc",     action=Action.MASK),
        Rule(type="in_gstin",    action=Action.MASK),
    ],
    default_action=Action.ALLOW,
)
doc_shield = Shield(config=doc_config, detectors=[IndiaDetector()])

doc_prompts = [
    "Passport no. A1234567 was issued in Delhi.",
    "Voter ID: ABC1234567 belongs to Ravi Kumar.",
    "Please transfer to IFSC SBIN0001234.",
    "Invoice raised under GSTIN 27ABCPE1234F1Z5.",
]
for prompt in doc_prompts:
    result = doc_shield.scan(prompt)
    print(f"  IN : {prompt}")
    print(f"  OUT: {result}\n")


# ── Example 10: Combined global + India detectors ─────────────────────────
separator("10 · Combined RegexDetector + IndiaDetector")

combined_config = PolicyConfig(
    rules=[
        Rule(type="email",      action=Action.MASK),
        Rule(type="in_aadhaar", action=Action.MASK),
        Rule(type="in_pan",     action=Action.BLOCK),
    ],
    default_action=Action.ALLOW,
)
combined_shield = Shield(
    config=combined_config,
    detectors=[RegexDetector(), IndiaDetector()],
)

mixed_prompts = [
    "Contact: ravi@example.in, Aadhaar 2345 6789 0124.",
    "Email me at ops@corp.com — no other PII here.",
]
for prompt in mixed_prompts:
    try:
        result = combined_shield.scan(prompt)
        print(f"  IN : {prompt}")
        print(f"  OUT: {result}\n")
    except SensitiveDataError as exc:
        print(f"  IN : {prompt}")
        print(f"  BLOCKED ({exc.entity_type}): {exc}\n")

print("\nDone.\n")
