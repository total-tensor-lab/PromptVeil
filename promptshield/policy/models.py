"""Data models for the policy engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Action(str, Enum):
    """The action to apply when a policy rule matches a detected entity."""

    MASK = "mask"
    BLOCK = "block"
    ALLOW = "allow"


@dataclass
class Rule:
    """
    A single policy rule that maps an entity type to an action.

    Attributes:
        type: The entity type to match, e.g. ``"email"``.
        action: The :class:`Action` to take when this type is detected.
        min_confidence: Only apply this rule when the detected entity's
            ``confidence`` is at or above this threshold (0.0–1.0).  Entities
            below the threshold fall back to :attr:`PolicyConfig.default_action`.
    """

    type: str
    action: Action
    min_confidence: float = 0.0


@dataclass
class PolicyConfig:
    """
    The complete policy configuration.

    Attributes:
        rules: Ordered list of :class:`Rule` objects.
        default_action: Fallback action when no rule matches a detected type.
        version: Optional config schema version string.
    """

    rules: List[Rule]
    default_action: Action = Action.ALLOW
    version: str = "1.0"
