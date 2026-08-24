"""Tests for jurisdiction/compliance profile packs."""

import pytest

from promptveil import Shield
from promptveil.exceptions import ConfigurationError, SensitiveDataError
from promptveil.profiles import available_profiles, load_profile


# ── Profile registry ──────────────────────────────────────────────────────

class TestProfileRegistry:
    def test_all_three_profiles_available(self):
        names = available_profiles()
        assert "india_dpdpa" in names
        assert "eu_gdpr" in names
        assert "us_hipaa" in names

    def test_unknown_profile_raises(self):
        with pytest.raises(ConfigurationError, match="Unknown profile"):
            load_profile("nonexistent_profile")


# ── Profile structure ─────────────────────────────────────────────────────

class TestProfileStructure:
    def test_india_dpdpa_has_detectors(self):
        profile = load_profile("india_dpdpa")
        assert len(profile.detectors) >= 2
        detector_types = {type(d).__name__ for d in profile.detectors}
        assert "RegexDetector" in detector_types
        assert "IndiaDetector" in detector_types

    def test_eu_gdpr_has_regex_detector(self):
        profile = load_profile("eu_gdpr")
        detector_types = {type(d).__name__ for d in profile.detectors}
        assert "RegexDetector" in detector_types

    def test_us_hipaa_has_us_detector(self):
        profile = load_profile("us_hipaa")
        detector_types = {type(d).__name__ for d in profile.detectors}
        assert "RegexDetector" in detector_types
        assert "USDetector" in detector_types

    def test_india_dpdpa_blocks_aadhaar(self):
        profile = load_profile("india_dpdpa")
        rule_map = {r.type: r for r in profile.policy.rules}
        assert rule_map["in_aadhaar"].action.value == "block"

    def test_india_dpdpa_blocks_pan(self):
        profile = load_profile("india_dpdpa")
        rule_map = {r.type: r for r in profile.policy.rules}
        assert rule_map["in_pan"].action.value == "block"

    def test_us_hipaa_blocks_ssn(self):
        profile = load_profile("us_hipaa")
        rule_map = {r.type: r for r in profile.policy.rules}
        assert rule_map["ssn"].action.value == "block"

    def test_eu_gdpr_blocks_credit_card(self):
        profile = load_profile("eu_gdpr")
        rule_map = {r.type: r for r in profile.policy.rules}
        assert rule_map["credit_card"].action.value == "block"


# ── Profile via YAML ──────────────────────────────────────────────────────

class TestProfileViaYAML:
    def test_profile_key_loads_detectors(self, tmp_path):
        yaml_text = "profile: india_dpdpa\n"
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml_text)

        shield = Shield(config_path=str(policy_file))
        detector_types = {type(d).__name__ for d in shield._detectors}
        assert "IndiaDetector" in detector_types

    def test_yaml_rules_override_profile(self, tmp_path):
        # Override: allow email instead of mask
        yaml_text = """\
profile: eu_gdpr
rules:
  - type: email
    action: allow
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml_text)

        shield = Shield(config_path=str(policy_file))
        result = shield.scan("email alice@example.com for info")
        # email is allowed → unchanged
        assert "alice@example.com" in result

    def test_profile_credit_card_still_blocked(self, tmp_path):
        yaml_text = "profile: eu_gdpr\n"
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml_text)

        shield = Shield(config_path=str(policy_file))
        with pytest.raises(SensitiveDataError):
            shield.scan("Pay 4111-1111-1111-1111 now")

    def test_unknown_profile_in_yaml_raises(self, tmp_path):
        yaml_text = "profile: fake_profile\n"
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml_text)

        with pytest.raises(ConfigurationError, match="Unknown profile"):
            Shield(config_path=str(policy_file))


# ── India DPDPA end-to-end ────────────────────────────────────────────────

class TestIndiaDPDPAEndToEnd:
    @pytest.fixture
    def shield(self):
        profile = load_profile("india_dpdpa")
        return Shield(config=profile.policy, detectors=profile.detectors)

    def test_aadhaar_blocked(self, shield):
        with pytest.raises(SensitiveDataError):
            shield.scan("UID: 2345 6789 0124")

    def test_email_masked(self, shield):
        result = shield.scan("Contact admin@example.com")
        assert "admin@example.com" not in result
        assert "@" in result  # domain preserved

    def test_clean_text_unchanged(self, shield):
        text = "Please process the request."
        assert shield.scan(text) == text


# ── US HIPAA end-to-end ───────────────────────────────────────────────────

class TestUSHIPAAEndToEnd:
    @pytest.fixture
    def shield(self):
        profile = load_profile("us_hipaa")
        return Shield(config=profile.policy, detectors=profile.detectors)

    def test_ssn_blocked(self, shield):
        with pytest.raises(SensitiveDataError):
            shield.scan("SSN: 123-45-6789")

    def test_email_masked(self, shield):
        result = shield.scan("Reach patient@hospital.org")
        assert "patient@hospital.org" not in result


# ── EU GDPR end-to-end ────────────────────────────────────────────────────

class TestEUGDPREndToEnd:
    @pytest.fixture
    def shield(self):
        profile = load_profile("eu_gdpr")
        return Shield(config=profile.policy, detectors=profile.detectors)

    def test_email_masked(self, shield):
        result = shield.scan("user@domain.eu signed up")
        assert "user@domain.eu" not in result

    def test_phone_masked(self, shield):
        result = shield.scan("Call +442071234567 now")
        assert "+442071234567" not in result
