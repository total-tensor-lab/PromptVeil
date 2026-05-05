"""Tests for the regex-based PII detector."""

import pytest

from promptshield.detector.regex_detector import RegexDetector


@pytest.fixture
def detector() -> RegexDetector:
    return RegexDetector()


# ── Email ─────────────────────────────────────────────────────────────────

class TestEmailDetection:
    def test_simple_email(self, detector):
        entities = detector.detect("Contact alice@example.com for info.")
        emails = [e for e in entities if e.entity_type == "email"]
        assert len(emails) == 1
        assert emails[0].value == "alice@example.com"

    def test_email_with_plus(self, detector):
        entities = detector.detect("Send to user+tag@domain.co.uk")
        emails = [e for e in entities if e.entity_type == "email"]
        assert len(emails) == 1

    def test_multiple_emails(self, detector):
        entities = detector.detect("From a@x.com to b@y.org")
        emails = [e for e in entities if e.entity_type == "email"]
        assert len(emails) == 2

    def test_no_email(self, detector):
        entities = detector.detect("No email address here.")
        assert not any(e.entity_type == "email" for e in entities)


# ── Phone ─────────────────────────────────────────────────────────────────

class TestPhoneDetection:
    def test_us_dashes(self, detector):
        entities = detector.detect("Call 555-867-5309 now.")
        phones = [e for e in entities if e.entity_type == "phone"]
        assert len(phones) >= 1

    def test_us_parentheses(self, detector):
        entities = detector.detect("Reach me at (555) 867-5309.")
        phones = [e for e in entities if e.entity_type == "phone"]
        assert len(phones) >= 1

    def test_international_e164(self, detector):
        entities = detector.detect("My number is +442071234567.")
        phones = [e for e in entities if e.entity_type == "phone"]
        assert len(phones) >= 1

    def test_no_phone(self, detector):
        entities = detector.detect("Today is the 5th of May, 2025.")
        assert not any(e.entity_type == "phone" for e in entities)


# ── Credit card ──────────────────────────────────────────────────────────

class TestCreditCardDetection:
    def test_visa_dashes(self, detector):
        entities = detector.detect("Card: 4111-1111-1111-1111")
        cards = [e for e in entities if e.entity_type == "credit_card"]
        assert len(cards) == 1
        assert "4111" in cards[0].value

    def test_visa_spaces(self, detector):
        entities = detector.detect("4111 1111 1111 1111")
        cards = [e for e in entities if e.entity_type == "credit_card"]
        assert len(cards) == 1

    def test_mastercard(self, detector):
        entities = detector.detect("5500-0000-0000-0004")
        cards = [e for e in entities if e.entity_type == "credit_card"]
        assert len(cards) == 1

    def test_no_card(self, detector):
        entities = detector.detect("Order #1234 placed successfully.")
        assert not any(e.entity_type == "credit_card" for e in entities)


# ── API key ──────────────────────────────────────────────────────────────

class TestApiKeyDetection:
    def test_openai_key(self, detector):
        entities = detector.detect("key=sk-abcdefABCDEF12345678901234")
        keys = [e for e in entities if e.entity_type == "api_key"]
        assert len(keys) == 1

    def test_github_pat(self, detector):
        entities = detector.detect(
            "token: ghp_AbCdEfGhIjKlMnOpQrStUvWxYz123456"
        )
        keys = [e for e in entities if e.entity_type == "api_key"]
        assert len(keys) == 1

    def test_aws_key(self, detector):
        entities = detector.detect("AKIAIOSFODNN7EXAMPLE is the access key")
        keys = [e for e in entities if e.entity_type == "api_key"]
        assert len(keys) == 1

    def test_no_key(self, detector):
        entities = detector.detect("Hello world, nothing secret here.")
        assert not any(e.entity_type == "api_key" for e in entities)

    def test_stripe_live_key(self, detector):
        entities = detector.detect("key=sk_live_abcdefABCDEF12345678901234")
        keys = [e for e in entities if e.entity_type == "api_key"]
        assert len(keys) == 1
        assert keys[0].value == "sk_live_abcdefABCDEF12345678901234"

    def test_stripe_test_key(self, detector):
        entities = detector.detect("STRIPE_KEY=sk_test_abcdefABCDEF12345678901234")
        keys = [e for e in entities if e.entity_type == "api_key"]
        assert len(keys) == 1
        assert keys[0].value == "sk_test_abcdefABCDEF12345678901234"

    def test_anthropic_key(self, detector):
        entities = detector.detect(
            "ANTHROPIC_API_KEY=sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz1234567890AbCd"
        )
        keys = [e for e in entities if e.entity_type == "api_key"]
        assert len(keys) == 1
        assert keys[0].value.startswith("sk-ant-")

    def test_bearer_token(self, detector):
        entities = detector.detect(
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        )
        keys = [e for e in entities if e.entity_type == "api_key"]
        assert len(keys) >= 1
        assert any("Bearer" in k.value for k in keys)


# ── Overlap resolution ────────────────────────────────────────────────────

class TestOverlapResolution:
    def test_no_duplicate_entities(self, detector):
        # Both email patterns should not produce duplicate entries.
        entities = detector.detect("a@b.com")
        emails = [e for e in entities if e.entity_type == "email"]
        assert len(emails) == 1

    def test_mixed_entities_no_overlap(self, detector):
        text = "Email a@b.com and call 555-123-4567."
        entities = detector.detect(text)
        types = [e.entity_type for e in entities]
        assert "email" in types
        assert "phone" in types
        # Verify no overlapping ranges.
        sorted_ents = sorted(entities, key=lambda e: e.start)
        for i in range(len(sorted_ents) - 1):
            assert sorted_ents[i].end <= sorted_ents[i + 1].start
