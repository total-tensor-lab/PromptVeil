"""Structured JSON audit logger for PromptVeil scan events."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import IO, Any, Dict, List, Optional, Tuple

from ..detector.base import DetectedEntity
from ..policy.models import Action


def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _build_entity_record(
    entity: DetectedEntity,
    action: Action,
    masked_value: Optional[str],
) -> Dict[str, Any]:
    """
    Build a structured log record for a single entity detection event.

    The original value is *never* stored; only the already-masked form is
    included so audit logs do not inadvertently persist sensitive data.

    Args:
        entity: The detected entity.
        action: The policy action that was applied.
        masked_value: The masked representation of the entity value, or
            ``None`` when masking was not applicable (e.g. allow).

    Returns:
        A JSON-serialisable ``dict``.
    """
    return {
        "entity_type": entity.entity_type,
        "action": action.value,
        "value_preview": masked_value or "[redacted]",
        "confidence": entity.confidence,
        "position": {"start": entity.start, "end": entity.end},
    }


def _optional(**fields: Any) -> Dict[str, Any]:
    """Drop fields that were not supplied so custom callers keep a lean schema."""
    return {k: v for k, v in fields.items() if v is not None}


class AuditLogger:
    """
    Structured JSON audit logger.

    Each log line is a self-contained JSON object written to *stream*
    (defaults to ``sys.stdout``).  Raw sensitive values are **never** logged;
    only masked previews are included.

    Example log output::

        {"event": "prompt_scan", "timestamp": "…", "prompt_length": 42,
         "detections": 1, "entities": [{"entity_type": "email", …}]}
    """

    def __init__(
        self,
        name: str = "promptveil.audit",
        stream: Optional[IO[str]] = None,
    ) -> None:
        """
        Args:
            name: Python logger name. Defaults to ``"promptveil.audit"``.
            stream: Output stream for log lines. Defaults to ``sys.stdout``.
        """
        self._logger = logging.getLogger(name)
        # Only add a handler if the logger has no handlers yet, preventing
        # duplicate output when the caller configures root logging themselves.
        if not self._logger.handlers:
            handler = logging.StreamHandler(stream or sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
            self._logger.propagate = False

    def log_scan_result(
        self,
        entity_records: List[Tuple[DetectedEntity, Action, Optional[str]]],
        prompt_length: int,
        *,
        scan_id: Optional[str] = None,
        method: Optional[str] = None,
        risk_score: Optional[float] = None,
        risk_level: Optional[str] = None,
    ) -> None:
        """
        Emit a structured log event summarising the result of a prompt scan.

        Args:
            entity_records: List of ``(entity, action, masked_value)`` tuples
                for every entity that had a non-allow action.
            prompt_length: Character length of the original prompt.
            scan_id: ID shared by every event from the same scan call.
            method: The ``Shield`` method that produced the scan.
            risk_score: Composite risk score (0.0–1.0), as in ``ScanResult``.
            risk_level: Risk label matching *risk_score*.
        """
        if not entity_records:
            return

        entities_log = [
            _build_entity_record(entity, action, masked_value)
            for entity, action, masked_value in entity_records
        ]

        event: Dict[str, Any] = {
            "event": "prompt_scan",
            "timestamp": _utc_now(),
            "prompt_length": prompt_length,
            "detections": len(entities_log),
            "entities": entities_log,
        }
        event.update(
            _optional(
                scan_id=scan_id,
                method=method,
                risk_score=risk_score,
                risk_level=risk_level,
            )
        )
        self._logger.info(json.dumps(event))

    def log_blocked(
        self,
        entity: DetectedEntity,
        *,
        scan_id: Optional[str] = None,
        method: Optional[str] = None,
        prompt_length: Optional[int] = None,
    ) -> None:
        """
        Emit a warning-level log event for a blocked entity.

        Called immediately before raising
        :class:`~promptveil.exceptions.SensitiveDataError`.

        Args:
            entity: The entity whose type matched a ``block`` rule.
            scan_id: ID shared by every event from the same scan call.
            method: The ``Shield`` method that produced the scan.
            prompt_length: Character length of the original prompt.
        """
        event: Dict[str, Any] = {
            "event": "prompt_blocked",
            "timestamp": _utc_now(),
            "entity_type": entity.entity_type,
            "action": "block",
            "confidence": entity.confidence,
            "position": {"start": entity.start, "end": entity.end},
        }
        event.update(
            _optional(scan_id=scan_id, method=method, prompt_length=prompt_length)
        )
        self._logger.warning(json.dumps(event))
