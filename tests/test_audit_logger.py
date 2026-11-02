"""Tests for audit log metadata."""

import io
import json
import logging
import uuid

import pytest

from promptveil import Shield
from promptveil.exceptions import SensitiveDataError
from promptveil.logger.audit_logger import AuditLogger
from promptveil.policy.models import Action, PolicyConfig, Rule


@pytest.fixture
def shield_and_stream():
    stream = io.StringIO()
    name = f"promptveil.audit.test.{uuid.uuid4().hex}"
    config = PolicyConfig(
        rules=[
            Rule(type="email", action=Action.MASK),
            Rule(type="api_key", action=Action.BLOCK),
        ],
        default_action=Action.ALLOW,
    )
    shield = Shield(config=config, logger=AuditLogger(name=name, stream=stream))
    yield shield, stream
    logging.getLogger(name).handlers.clear()


def _events(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_scan_event_has_metadata(shield_and_stream):
    shield, stream = shield_and_stream
    shield.scan("mail a@example.com")
    (event,) = _events(stream)
    assert event["event"] == "prompt_scan"
    assert event["method"] == "scan"
    assert len(event["scan_id"]) == 32
    assert 0.0 < event["risk_score"] <= 1.0
    assert event["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert event["entities"][0]["confidence"] == 1.0
    assert "a@example.com" not in stream.getvalue()


def test_method_distinguishes_entry_points(shield_and_stream):
    shield, stream = shield_and_stream
    shield.scan_response("mail a@example.com")
    shield.scan_detailed("mail a@example.com")
    shield.scan_with_vault("mail a@example.com")
    events = _events(stream)
    assert [e["method"] for e in events] == [
        "scan_response", "scan_detailed", "scan_with_vault",
    ]
    assert len({e["scan_id"] for e in events}) == 3


def test_blocked_event_has_metadata(shield_and_stream):
    shield, stream = shield_and_stream
    prompt = "Key: sk-abcdefABCDEF12345678901234"
    with pytest.raises(SensitiveDataError):
        shield.scan(prompt)
    (event,) = _events(stream)
    assert event["event"] == "prompt_blocked"
    assert event["method"] == "scan"
    assert event["prompt_length"] == len(prompt)
    assert event["position"] == {"start": 5, "end": len(prompt)}
    assert event["confidence"] == 1.0
    assert "sk-abcdef" not in stream.getvalue()


def test_logger_without_metadata_keeps_lean_schema():
    stream = io.StringIO()
    name = f"promptveil.audit.test.{uuid.uuid4().hex}"
    logger = AuditLogger(name=name, stream=stream)
    from promptveil.detector.base import DetectedEntity
    entity = DetectedEntity("email", "a@b.com", 0, 7)
    logger.log_scan_result([(entity, Action.MASK, "a***@b.com")], 7)
    logger.log_blocked(entity)
    scan, blocked = _events(stream)
    for key in ("scan_id", "method", "risk_score", "risk_level"):
        assert key not in scan
    assert "prompt_length" not in blocked
    logging.getLogger(name).handlers.clear()
