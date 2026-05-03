"""Tests for IndiaDetector — detection, masking, and Shield integration."""

import pytest

from promptshield import Shield
from promptshield.detector.india_detector import IndiaDetector, _valid_aadhaar
from promptshield.detector.regex_detector import RegexDetector
from promptshield.actions.masker import mask_value
from promptshield.exceptions import SensitiveDataError
from promptshield.policy.models import Action, PolicyConfig, Rule


@pytest.fixture
def detector() -> IndiaDetector:
    return IndiaDetector()


# ---------------------------------------------------------------------------
# Verhoeff checksum validator
# ---------------------------------------------------------------------------

class TestVerhoeff:
    def test_valid_aadhaar_plain(self):
        # Computed valid: 234567890124
        assert _valid_aadhaar("234567890124") is True

    def test_valid_aadhaar_spaces(self):
        assert _valid_aadhaar("2345 6789 0124") is True

    def test_valid_aadhaar_hyphens(self):
        assert _valid_aadhaar("2345-6789-0124") is True

    def test_invalid_checksum(self):
        # Last digit off by one
        assert _valid_aadhaar("234567890123") is False

    def test_too_short(self):
        assert _valid_aadhaar("23456789012") is False

    def test_non_digits(self):
        assert _valid_aadhaar("ABCD EFGH IJKL") is False

    def test_second_valid_number(self):
        assert _valid_aadhaar("498765432102") is True


# ---------------------------------------------------------------------------
# Aadhaar detection
# ---------------------------------------------------------------------------

class TestAadhaarDetection:
    def test_valid_aadhaar_detected(self, detector):
        entities = detector.detect("Aadhaar: 2345 6789 0124")
        aadhaar = [e for e in entities if e.entity_type == "in_aadhaar"]
        assert len(aadhaar) == 1
        assert "2345" in aadhaar[0].value

    def test_invalid_checksum_not_detected(self, detector):
        # 234567890123 has wrong checksum — should be filtered out
        entities = detector.detect("ID: 2345 6789 0123")
        assert not any(e.entity_type == "in_aadhaar" for e in entities)

    def test_aadhaar_with_hyphens(self, detector):
        entities = detector.detect("UID: 2345-6789-0124")
        aadhaar = [e for e in entities if e.entity_type == "in_aadhaar"]
        assert len(aadhaar) == 1

    def test_aadhaar_plain_digits(self, detector):
        entities = detector.detect("234567890124")
        aadhaar = [e for e in entities if e.entity_type == "in_aadhaar"]
        assert len(aadhaar) == 1

    def test_no_aadhaar_in_clean_text(self, detector):
        entities = detector.detect("Hello, no sensitive data here.")
        assert not any(e.entity_type == "in_aadhaar" for e in entities)


# ---------------------------------------------------------------------------
# PAN detection
# ---------------------------------------------------------------------------

class TestPANDetection:
    def test_individual_pan(self, detector):
        entities = detector.detect("PAN: ABCPE1234F")
        pan = [e for e in entities if e.entity_type == "in_pan"]
        assert len(pan) == 1
        assert pan[0].value == "ABCPE1234F"

    def test_company_pan(self, detector):
        entities = detector.detect("Company PAN XYZCP1234Q")
        pan = [e for e in entities if e.entity_type == "in_pan"]
        assert len(pan) == 1

    def test_lowercase_not_matched(self, detector):
        entities = detector.detect("abcde1234f")
        assert not any(e.entity_type == "in_pan" for e in entities)

    def test_invalid_length_not_matched(self, detector):
        entities = detector.detect("ABCD1234F")  # 9 chars, not 10
        assert not any(e.entity_type == "in_pan" for e in entities)


# ---------------------------------------------------------------------------
# Indian phone detection
# ---------------------------------------------------------------------------

class TestIndiaPhoneDetection:
    def test_plus91_format(self, detector):
        entities = detector.detect("Call me on +91 98765 43210")
        phones = [e for e in entities if e.entity_type == "in_phone"]
        assert len(phones) >= 1

    def test_plus91_no_space(self, detector):
        entities = detector.detect("+919876543210")
        phones = [e for e in entities if e.entity_type == "in_phone"]
        assert len(phones) >= 1

    def test_zero_prefix(self, detector):
        entities = detector.detect("STD: 09876543210")
        phones = [e for e in entities if e.entity_type == "in_phone"]
        assert len(phones) >= 1

    def test_no_phone_in_clean_text(self, detector):
        entities = detector.detect("The answer is 42.")
        assert not any(e.entity_type == "in_phone" for e in entities)


# ---------------------------------------------------------------------------
# Passport detection
# ---------------------------------------------------------------------------

class TestPassportDetection:
    def test_valid_passport(self, detector):
        entities = detector.detect("Passport no. A1234567")
        passports = [e for e in entities if e.entity_type == "in_passport"]
        assert len(passports) >= 1
        assert any("A1234567" in e.value for e in passports)

    def test_lowercase_not_matched(self, detector):
        entities = detector.detect("ref a1234567")
        assert not any(e.entity_type == "in_passport" for e in entities)


# ---------------------------------------------------------------------------
# Voter ID detection
# ---------------------------------------------------------------------------

class TestVoterIdDetection:
    def test_valid_voter_id(self, detector):
        entities = detector.detect("Voter ID: ABC1234567")
        voter = [e for e in entities if e.entity_type == "in_voter_id"]
        assert len(voter) >= 1

    def test_no_voter_id(self, detector):
        entities = detector.detect("Order no. 123")
        assert not any(e.entity_type == "in_voter_id" for e in entities)


# ---------------------------------------------------------------------------
# IFSC detection
# ---------------------------------------------------------------------------

class TestIFSCDetection:
    def test_sbi_ifsc(self, detector):
        entities = detector.detect("Transfer via SBIN0001234")
        ifsc = [e for e in entities if e.entity_type == "in_ifsc"]
        assert len(ifsc) == 1
        assert ifsc[0].value == "SBIN0001234"

    def test_hdfc_ifsc(self, detector):
        entities = detector.detect("IFSC: HDFC0000123")
        ifsc = [e for e in entities if e.entity_type == "in_ifsc"]
        assert len(ifsc) == 1

    def test_invalid_fifth_char_not_zero(self, detector):
        # Fifth character must be '0'
        entities = detector.detect("SBIN1001234")
        assert not any(e.entity_type == "in_ifsc" for e in entities)


# ---------------------------------------------------------------------------
# GSTIN detection
# ---------------------------------------------------------------------------

class TestGSTINDetection:
    def test_valid_gstin(self, detector):
        entities = detector.detect("GSTIN: 27ABCPE1234F1Z5")
        gstin = [e for e in entities if e.entity_type == "in_gstin"]
        assert len(gstin) == 1
        assert gstin[0].value == "27ABCPE1234F1Z5"

    def test_no_gstin_in_clean_text(self, detector):
        entities = detector.detect("Invoice total: Rs. 5000")
        assert not any(e.entity_type == "in_gstin" for e in entities)


# ---------------------------------------------------------------------------
# supported_types
# ---------------------------------------------------------------------------

class TestSupportedTypes:
    def test_all_types_listed(self, detector):
        types = detector.supported_types
        for t in ("in_aadhaar", "in_pan", "in_phone", "in_passport",
                  "in_voter_id", "in_ifsc", "in_gstin"):
            assert t in types


# ---------------------------------------------------------------------------
# Masking
# ---------------------------------------------------------------------------

class TestIndiaMasking:
    def test_aadhaar_mask(self):
        result = mask_value("2345 6789 0124", "in_aadhaar")
        assert result == "XXXX-XXXX-0124"

    def test_aadhaar_mask_plain(self):
        result = mask_value("234567890124", "in_aadhaar")
        assert result.endswith("0124")
        assert result.startswith("XXXX")

    def test_pan_mask(self):
        result = mask_value("ABCDE1234F", "in_pan")
        assert result.startswith("AB")
        assert result.endswith("F")
        assert "*" in result

    def test_in_phone_mask(self):
        result = mask_value("+91 98765 43210", "in_phone")
        assert result.startswith("+91")
        assert "3210" in result
        assert "***" in result

    def test_passport_mask(self):
        result = mask_value("A1234567", "in_passport")
        assert result == "A*******"

    def test_voter_id_mask(self):
        result = mask_value("ABC1234567", "in_voter_id")
        assert result.startswith("ABC")
        assert "*" in result

    def test_ifsc_mask(self):
        result = mask_value("SBIN0001234", "in_ifsc")
        assert result.startswith("SBIN0")
        assert "*" in result

    def test_gstin_mask(self):
        result = mask_value("27ABCPE1234F1Z5", "in_gstin")
        assert result.startswith("27")
        assert "*" in result
        assert len(result) == 15


# ---------------------------------------------------------------------------
# Shield integration
# ---------------------------------------------------------------------------

class TestShieldIntegration:
    def test_shield_masks_aadhaar(self):
        shield = Shield(
            config=PolicyConfig(
                rules=[Rule(type="in_aadhaar", action=Action.MASK)],
                default_action=Action.ALLOW,
            ),
            detectors=[IndiaDetector()],
        )
        result = shield.scan("My Aadhaar is 2345 6789 0124.")
        assert "2345 6789 0124" not in result
        assert "0124" in result

    def test_shield_blocks_pan(self):
        shield = Shield(
            config=PolicyConfig(
                rules=[Rule(type="in_pan", action=Action.BLOCK)],
                default_action=Action.ALLOW,
            ),
            detectors=[IndiaDetector()],
        )
        with pytest.raises(SensitiveDataError) as exc_info:
            shield.scan("PAN: ABCPE1234F")
        assert exc_info.value.entity_type == "in_pan"

    def test_combined_detectors_global_and_india(self):
        shield = Shield(
            config=PolicyConfig(
                rules=[
                    Rule(type="email", action=Action.MASK),
                    Rule(type="in_aadhaar", action=Action.MASK),
                ],
                default_action=Action.ALLOW,
            ),
            detectors=[RegexDetector(), IndiaDetector()],
        )
        prompt = "Email alice@example.com, Aadhaar 2345 6789 0124"
        result = shield.scan(prompt)
        assert "alice@example.com" not in result
        assert "2345 6789 0124" not in result
        assert "@example.com" in result   # domain preserved
        assert "0124" in result           # last 4 preserved

    def test_invalid_aadhaar_not_masked(self):
        """A 12-digit number with bad checksum passes through unchanged."""
        shield = Shield(
            config=PolicyConfig(
                rules=[Rule(type="in_aadhaar", action=Action.MASK)],
                default_action=Action.ALLOW,
            ),
            detectors=[IndiaDetector()],
        )
        # 234567890123 fails Verhoeff — should not be detected
        result = shield.scan("ID: 234567890123")
        assert result == "ID: 234567890123"
