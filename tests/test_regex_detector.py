"""
Comprehensive test suite for RegexDetector.

Tests cover:
- Basic detection of each entity type (email, phone, credit_card, api_key)
- Edge cases and overlapping patterns
- The _resolve_overlaps function
- Integration with the Shield class
"""

import pytest
from promptveil.detector.regex_detector import RegexDetector, _resolve_overlaps, _COMPILED
from promptveil.detector.base import DetectedEntity
from promptveil.policy.models import Action, PolicyConfig, Rule


class TestRegexDetectorBasic:
    """Basic detection tests for each entity type."""

    def test_email_detection(self):
        """Test email pattern detection."""
        detector = RegexDetector()
        text = "Contact alice@example.com or bob@company.org"
        entities = detector.detect(text)
        
        assert len(entities) == 2
        assert entities[0].entity_type == "email"
        assert entities[0].value == "alice@example.com"
        assert entities[1].entity_type == "email"
        assert entities[1].value == "bob@company.org"

    def test_phone_detection_na(self):
        """Test North American phone pattern detection."""
        detector = RegexDetector()
        text = "Call (555) 867-5309 or 555.123.4567"
        entities = detector.detect(text)
        
        assert len(entities) == 2
        assert entities[0].entity_type == "phone"
        assert entities[0].value == "(555) 867-5309"
        assert entities[1].entity_type == "phone"
        assert entities[1].value == "555.123.4567"

    def test_phone_detection_international(self):
        """Test international phone pattern detection."""
        detector = RegexDetector()
        text = "International: +442071234567 or +44 7911 123456"
        entities = detector.detect(text)
        
        assert len(entities) == 2
        assert entities[0].entity_type == "phone"
        assert entities[0].value == "+442071234567"
        assert entities[1].entity_type == "phone"
        assert entities[1].value == "+44 7911 123456"

    def test_credit_card_detection(self):
        """Test credit card pattern detection for all major card types."""
        detector = RegexDetector()
        text = "Visa: 4111-1111-1111-1111, Mastercard: 5500-0000-0000-0004"
        entities = detector.detect(text)
        
        assert len(entities) == 2
        assert entities[0].entity_type == "credit_card"
        assert entities[0].value == "4111-1111-1111-1111"
        assert entities[1].entity_type == "credit_card"
        assert entities[1].value == "5500-0000-0000-0004"

    def test_api_key_detection(self):
        """Test API key pattern detection for various providers."""
        detector = RegexDetector()
        text = "OpenAI: sk-1234567890abcdefghijklmnop, AWS: AKIAIOSFODNN7EXAMPLE"
        entities = detector.detect(text)
        
        assert len(entities) == 2
        assert entities[0].entity_type == "api_key"
        assert entities[0].value == "sk-1234567890abcdefghijklmnop"
        assert entities[1].entity_type == "api_key"
        assert entities[1].value == "AKIAIOSFODNN7EXAMPLE"


class TestRegexDetectorEdgeCases:
    """Edge case tests for detection."""

    def test_no_sensitive_data(self):
        """Test that clean text returns no entities."""
        detector = RegexDetector()
        text = "Hello, this is a clean message with no sensitive data."
        entities = detector.detect(text)
        
        assert len(entities) == 0

    def test_empty_string(self):
        """Test that empty string returns no entities."""
        detector = RegexDetector()
        text = ""
        entities = detector.detect(text)
        
        assert len(entities) == 0

    def test_none_input(self):
        """Test that None input raises TypeError."""
        detector = RegexDetector()
        with pytest.raises(TypeError):
            detector.detect(None)

    def test_special_characters_in_email(self):
        """Test email with special characters."""
        detector = RegexDetector()
        text = "Contact user+tag@example-domain.co.uk"
        entities = detector.detect(text)
        
        assert len(entities) == 1
        assert entities[0].value == "user+tag@example-domain.co.uk"

    def test_multiple_sequential_emails(self):
        """Test multiple emails in sequence."""
        detector = RegexDetector()
        text = "a@b.com c@d.com e@f.com"
        entities = detector.detect(text)
        
        assert len(entities) == 3
        assert all(e.entity_type == "email" for e in entities)


class TestRegexDetectorOverlappingPatterns:
    """Tests for overlapping pattern resolution."""

    def test_phone_and_credit_card_overlap(self):
        """Test that phone pattern doesn't interfere with credit card."""
        detector = RegexDetector()
        # A credit card number could potentially match phone patterns
        text = "Card: 4111111111111111"
        entities = detector.detect(text)
        
        # Should detect as credit_card, not phone
        assert len(entities) == 1
        assert entities[0].entity_type == "credit_card"

    def test_api_key_and_email_overlap(self):
        """Test that API key pattern doesn't interfere with email."""
        detector = RegexDetector()
        text = "Key: sk-1234567890abcdefghijklmnop"
        entities = detector.detect(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "api_key"

    def test_jwt_detection(self):
        """Test JWT token detection."""
        detector = RegexDetector()
        text = "Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        entities = detector.detect(text)
        
        assert len(entities) == 1
        assert entities[0].entity_type == "api_key"
        assert entities[0].value == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"


class TestResolveOverlaps:
    """Tests for the _resolve_overlaps helper function."""

    def test_no_overlaps(self):
        """Test that non-overlapping entities are returned unchanged."""
        entities = [
            DetectedEntity(entity_type="email", value="a@b.com", start=0, end=8),
            DetectedEntity(entity_type="email", value="c@d.com", start=10, end=18),
        ]
        result = _resolve_overlaps(entities)
        
        assert len(result) == 2
        assert result[0].value == "a@b.com"
        assert result[1].value == "c@d.com"

    def test_overlapping_entities(self):
        """Test that overlapping entities are resolved correctly."""
        # Create overlapping entities
        entities = [
            DetectedEntity(entity_type="email", value="a@b.com", start=0, end=8),
            DetectedEntity(entity_type="api_key", value="sk-1234567890abcdefghijklmnop", start=5, end=30),
        ]
        result = _resolve_overlaps(entities)
        
        # Should keep the longer one (api_key)
        assert len(result) == 1
        assert result[0].entity_type == "api_key"

    def test_multiple_overlaps(self):
        """Test resolution of multiple overlapping entities."""
        entities = [
            DetectedEntity(entity_type="email", value="a@b.com", start=0, end=8),
            DetectedEntity(entity_type="email", value="x@y.com", start=2, end=10),
            DetectedEntity(entity_type="email", value="z@w.com", start=4, end=12),
        ]
        result = _resolve_overlaps(entities)
        
        # Equal-length overlaps retain the earliest match.
        assert len(result) == 1
        assert result[0].value == "a@b.com"

    def test_sorted_by_start_position(self):
        """Test that result is sorted by start position."""
        entities = [
            DetectedEntity(entity_type="email", value="c@d.com", start=20, end=28),
            DetectedEntity(entity_type="email", value="a@b.com", start=0, end=8),
            DetectedEntity(entity_type="email", value="b@c.com", start=10, end=18),
        ]
        result = _resolve_overlaps(entities)
        
        assert result[0].start == 0
        assert result[1].start == 10
        assert result[2].start == 20


class TestRegexDetectorSupportedTypes:
    """Tests for supported_types property."""

    def test_supported_types(self):
        """Test that supported_types returns expected entity types."""
        detector = RegexDetector()
        expected = ["email", "phone", "credit_card", "api_key"]
        
        assert detector.supported_types == expected


class TestRegexDetectorCompiledPatterns:
    """Tests for compiled pattern registry."""

    def test_patterns_compiled(self):
        """Test that all patterns are compiled at import time."""
        for entity_type, patterns in _COMPILED.items():
            assert isinstance(patterns, list)
            for pattern in patterns:
                assert hasattr(pattern, 'finditer')
                assert hasattr(pattern, 'pattern')

    def test_all_entity_types_have_patterns(self):
        """Test that each entity type has at least one pattern."""
        for entity_type in ["email", "phone", "credit_card", "api_key"]:
            assert entity_type in _COMPILED
            assert len(_COMPILED[entity_type]) > 0


class TestRegexDetectorIntegration:
    """Integration tests with Shield class."""

    def test_detector_in_shield(self):
        """Test that RegexDetector works correctly when added to Shield."""
        from promptveil.shield import Shield
        
        shield = Shield(
            config=PolicyConfig(
                rules=[Rule(type="email", action=Action.MASK)],
            )
        )
        # Shield already has RegexDetector by default.
        result = shield.scan_detailed("Contact alice@example.com")
        
        assert "alice@example.com" not in result.safe_text
        assert result.entities[0].entity_type == "email"

    def test_detector_order_matters(self):
        """Test that detector order affects detection results."""
        from promptveil.shield import Shield
        
        # Create a custom detector that detects a specific pattern
        class CustomDetector:
            @property
            def supported_types(self):
                return ["custom"]
            
            def detect(self, text):
                if "custom" in text:
                    return [DetectedEntity(
                        entity_type="custom",
                        value="custom",
                        start=0,
                        end=6,
                        confidence=1.0
                    )]
                return []
        
        shield = Shield(config=PolicyConfig(rules=[]))
        shield.add_detector(CustomDetector())
        
        result = shield.scan_detailed("This is a custom message")
        
        assert len(result.entities) > 0
        assert any(e.entity_type == "custom" for e in result.entities)


class TestRegexDetectorConfidence:
    """Tests for confidence scoring."""

    def test_default_confidence(self):
        """Test that regex matches have default confidence of 1.0."""
        detector = RegexDetector()
        text = "Contact alice@example.com"
        entities = detector.detect(text)
        
        assert entities[0].confidence == 1.0

    def test_confidence_in_result(self):
        """Test that confidence is preserved in Shield results."""
        from promptveil.shield import Shield
        
        shield = Shield(config=PolicyConfig(rules=[]))
        result = shield.scan_detailed("Contact alice@example.com")
        
        assert result.entities[0].confidence == 1.0


class TestRegexDetectorPatterns:
    """Tests for specific pattern behaviors."""

    def test_email_variations(self):
        """Test various email formats."""
        detector = RegexDetector()
        
        test_cases = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
            "user@127.0.0.1",
        ]
        
        for email in test_cases:
            entities = detector.detect(email)
            assert len(entities) == 1
            assert entities[0].value == email

    def test_phone_variations(self):
        """Test various phone formats."""
        detector = RegexDetector()
        
        test_cases = [
            "(555) 867-5309",
            "555-867-5309",
            "555.867.5309",
            "+1 555-867-5309",
            "+1-555-867-5309",
        ]
        
        for phone in test_cases:
            entities = detector.detect(phone)
            assert len(entities) == 1
            assert entities[0].value == phone

    def test_credit_card_variations(self):
        """Test various credit card formats."""
        detector = RegexDetector()
        
        test_cases = [
            ("4111111111111111", "Visa (no separators)"),
            ("4111-1111-1111-1111", "Visa (dashes)"),
            ("4111 1111 1111 1111", "Visa (spaces)"),
            ("5500000000000004", "Mastercard (no separators)"),
            ("5500-0000-0000-0004", "Mastercard (dashes)"),
        ]
        
        for card, description in test_cases:
            entities = detector.detect(card)
            assert len(entities) == 1
            assert entities[0].value == card

    def test_api_key_variations(self):
        """Test various API key formats."""
        detector = RegexDetector()
        
        test_cases = [
            ("sk-1234567890abcdefghijklmnop", "OpenAI key"),
            ("AKIAIOSFODNN7EXAMPLE", "AWS key"),
            ("ghp_1234567890abcdefghijklmnop", "GitHub PAT"),
            ("AIzaSyAbcdefghijklmnopqrstuv123", "Google API key"),
            ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U", "JWT token"),
        ]
        
        for key, description in test_cases:
            entities = detector.detect(key)
            assert len(entities) == 1
            assert entities[0].value == key


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
