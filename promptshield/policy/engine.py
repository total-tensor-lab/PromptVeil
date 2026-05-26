"""Policy rule engine — maps detected entities to actions."""

from typing import Dict, List

from .models import Action, PolicyConfig, Rule
from ..detector.base import DetectedEntity


class PolicyEngine:
    """
    Evaluates detected entities against a :class:`~promptshield.policy.models.PolicyConfig`
    and resolves the action to take for each entity.

    Rules are stored in a dictionary keyed by entity type for O(1) lookup.
    When no rule matches an entity type, :attr:`PolicyConfig.default_action`
    is returned.

    If a rule carries a ``min_confidence`` threshold and the detected entity's
    ``confidence`` is below that threshold, the rule is skipped and the default
    action is returned instead.
    """

    def __init__(self, config: PolicyConfig) -> None:
        """
        Args:
            config: The validated policy configuration.
        """
        self._config = config
        # Store full Rule objects so we can read min_confidence.
        self._rule_map: Dict[str, Rule] = {
            rule.type: rule for rule in config.rules
        }

    def get_action(self, entity: DetectedEntity) -> Action:
        """
        Return the :class:`~promptshield.policy.models.Action` for a single entity.

        If the entity's ``confidence`` is below the matched rule's
        ``min_confidence``, the rule is skipped and the default action is used.

        Args:
            entity: A detected sensitive entity.

        Returns:
            The matched action, or :attr:`PolicyConfig.default_action` if no
            rule covers this entity type or the confidence threshold is not met.
        """
        rule = self._rule_map.get(entity.entity_type)
        if rule is None:
            return self._config.default_action
        if entity.confidence < rule.min_confidence:
            return self._config.default_action
        return rule.action

    def evaluate(self, entities: List[DetectedEntity]) -> Dict[DetectedEntity, Action]:
        """
        Evaluate a list of entities and return a mapping of entity → action.

        Args:
            entities: Detected entities to evaluate.

        Returns:
            ``dict`` mapping each :class:`~promptshield.detector.base.DetectedEntity`
            to its resolved :class:`~promptshield.policy.models.Action`.
        """
        return {entity: self.get_action(entity) for entity in entities}
