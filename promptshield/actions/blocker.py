"""Blocking action — raises SensitiveDataError for blocked entities."""

from ..detector.base import DetectedEntity
from ..exceptions import SensitiveDataError


def block(entity: DetectedEntity) -> None:
    """
    Raise a :class:`~promptshield.exceptions.SensitiveDataError` for a blocked entity.

    This function always raises; it never returns normally.

    Args:
        entity: The entity that triggered the block policy rule.

    Raises:
        SensitiveDataError: Always, carrying the entity type for downstream
            error handling.
    """
    raise SensitiveDataError(
        f"Sensitive data of type '{entity.entity_type}' was detected and "
        "blocked by the active policy. Remove or redact the value before "
        "sending this prompt.",
        entity_type=entity.entity_type,
    )
