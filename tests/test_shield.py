"""End-to-end tests for the Shield class."""

import pytest

from promptveil import Shield
from promptveil.exceptions import ConfigurationError, SensitiveDataError
from promptveil.policy.models import Action, PolicyConfig, Rule


def make_shield(rules=None, default_action=Action.ALLOW) -> Shield:
    """Helper: build a Shield from a programmatic config."""
    config = PolicyConfig(
        rules=rules or [],
        default_action=default_action,
    )
    return Shield(config=config)


# ── Constructor validation ────────────────────────────────────────────────

class TestShieldInit:
    def test_requires_config(self):
        with pytest.raises(ConfigurationError):
            Shield()

    def test_config_path_and_config_mutual_exclusive(self):
        config = PolicyConfig(rules=[])
        with pytest.raises(ConfigurationError):
            Shield(config_path="policy.yaml", config=config)

    def test_programmatic_config(self):
        shield = make_shield()
        assert shield is not None

    def test_missing_yaml_file(self):
        with pytest.raises(ConfigurationError):
            Shield(config_path="/nonexistent/policy.yaml")

    def test_type_error_on_non_string_prompt(self):
        shield = make_shield()
        with pytest.raises(TypeError):
            shield.scan(42)  # type: ignore[arg-type]


# ── Allow (pass-through) ─────────────────────────────────────────────────

class TestShieldAllow:
    def test_no_pii_returns_unchanged(self):
        shield = make_shield()
        prompt = "Hello, world! No sensitive data."
        assert shield.scan(prompt) == prompt

    def test_allow_by_default(self):
        shield = make_shield(rules=[], default_action=Action.ALLOW)
        prompt = "My email is bob@example.com"
        assert shield.scan(prompt) == prompt


# ── Masking ──────────────────────────────────────────────────────────────

class TestShieldMask:
    def test_masks_email(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        result = shield.scan("Contact alice@example.com for details.")
        assert "alice@example.com" not in result
        assert "@example.com" in result  # domain still visible

    def test_masks_phone(self):
        shield = make_shield(rules=[Rule(type="phone", action=Action.MASK)])
        result = shield.scan("Call me at 555-867-5309 anytime.")
        assert "555-867-5309" not in result
        assert "5309" in result  # last 4 visible

    def test_masks_credit_card(self):
        shield = make_shield(rules=[Rule(type="credit_card", action=Action.MASK)])
        result = shield.scan("Card: 4111-1111-1111-1111")
        assert "4111-1111-1111-1111" not in result
        assert "1111" in result

    def test_masks_multiple_entities(self):
        shield = make_shield(
            rules=[
                Rule(type="email", action=Action.MASK),
                Rule(type="phone", action=Action.MASK),
            ]
        )
        result = shield.scan("Email a@b.com or call 555-123-4567.")
        assert "a@b.com" not in result
        assert "555-123-4567" not in result


# ── Blocking ─────────────────────────────────────────────────────────────

class TestShieldBlock:
    def test_blocks_api_key(self):
        shield = make_shield(rules=[Rule(type="api_key", action=Action.BLOCK)])
        with pytest.raises(SensitiveDataError) as exc_info:
            shield.scan("Key: sk-abcdefABCDEF12345678901234")
        assert exc_info.value.entity_type == "api_key"

    def test_block_raises_before_masking(self):
        """If block + mask rules both fire, block wins (fail fast)."""
        shield = make_shield(
            rules=[
                Rule(type="email", action=Action.MASK),
                Rule(type="api_key", action=Action.BLOCK),
            ]
        )
        prompt = "Email a@b.com, key sk-abcABC12345678901234567890"
        with pytest.raises(SensitiveDataError):
            shield.scan(prompt)

    def test_sensitive_data_error_has_entity_type(self):
        shield = make_shield(rules=[Rule(type="api_key", action=Action.BLOCK)])
        with pytest.raises(SensitiveDataError) as exc_info:
            shield.scan("sk-abcdefABCDEF12345678901234")
        assert exc_info.value.entity_type == "api_key"


# ── scan_response ─────────────────────────────────────────────────────────

class TestScanResponse:
    def test_scan_response_masks(self):
        shield = make_shield(rules=[Rule(type="email", action=Action.MASK)])
        response = "You can reach us at support@company.com."
        result = shield.scan_response(response)
        assert "support@company.com" not in result

    def test_scan_response_blocks(self):
        shield = make_shield(rules=[Rule(type="api_key", action=Action.BLOCK)])
        with pytest.raises(SensitiveDataError):
            shield.scan_response("Here is your token: sk-abcABC12345678901234")


# ── YAML config ───────────────────────────────────────────────────────────

class TestYamlConfig:
    def test_load_from_yaml(self):
        shield = Shield(config_path="policy.yaml")
        # Emails should be masked per the default policy.yaml
        result = shield.scan("Contact test@example.com")
        assert "test@example.com" not in result

    def test_yaml_blocks_api_key(self):
        shield = Shield(config_path="policy.yaml")
        with pytest.raises(SensitiveDataError):
            shield.scan("key sk-abcdefABCDEF12345678901234")


# ── Overlapping detections from multiple detectors ────────────────────────

class TestOverlappingDetectors:
    """Two detectors reporting the same span must not corrupt the output."""

    TEXT = "call +91 98765 43210 now"

    @staticmethod
    def make_multi_detector_shield() -> Shield:
        from promptveil.detector.india_detector import IndiaDetector
        from promptveil.detector.regex_detector import RegexDetector

        config = PolicyConfig(
            rules=[
                Rule(type="phone", action=Action.MASK),
                Rule(type="in_phone", action=Action.MASK),
            ],
            default_action=Action.ALLOW,
        )
        return Shield(config=config, detectors=[RegexDetector(), IndiaDetector()])

    def test_scan_with_vault_round_trips(self):
        shield = self.make_multi_detector_shield()
        pseudonymized, vault = shield.scan_with_vault(self.TEXT)
        assert "98765" not in pseudonymized
        assert vault.restore(pseudonymized) == self.TEXT

    def test_scan_masks_span_once(self):
        shield = self.make_multi_detector_shield()
        masked = shield.scan(self.TEXT)
        assert "98765" not in masked
        assert masked.startswith("call ") and masked.endswith(" now")

    def test_scan_detailed_reports_span_once(self):
        shield = self.make_multi_detector_shield()
        result = shield.scan_detailed(self.TEXT)
        assert len(result.entities) == 1

    def test_block_rule_still_applies_to_overlapped_span(self):
        from promptveil.detector.india_detector import IndiaDetector
        from promptveil.detector.regex_detector import RegexDetector

        config = PolicyConfig(
            rules=[
                Rule(type="phone", action=Action.MASK),
                Rule(type="in_phone", action=Action.BLOCK),
            ],
            default_action=Action.ALLOW,
        )
        # RegexDetector is first, so phone wins the overlap; in_phone must still block.
        shield = Shield(config=config, detectors=[RegexDetector(), IndiaDetector()])
        with pytest.raises(SensitiveDataError):
            shield.scan(self.TEXT)
        with pytest.raises(SensitiveDataError):
            shield.scan_with_vault(self.TEXT)
