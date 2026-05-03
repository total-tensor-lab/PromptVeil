"""YAML policy configuration loader and validator."""

from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from ..exceptions import ConfigurationError
from ..policy.models import Action, PolicyConfig, Rule

_VALID_ACTIONS = frozenset(a.value for a in Action)


def _parse_rules(raw_rules: Any) -> List[Rule]:
    """
    Parse and validate the ``rules`` list from raw YAML data.

    Args:
        raw_rules: The value of the ``rules`` key from the YAML document.

    Returns:
        List of validated :class:`~promptshield.policy.models.Rule` objects.

    Raises:
        ConfigurationError: If any rule is malformed or contains an
            unrecognised action.
    """
    if not isinstance(raw_rules, list):
        raise ConfigurationError(
            f"'rules' must be a YAML list, got {type(raw_rules).__name__}."
        )

    rules: List[Rule] = []
    for i, item in enumerate(raw_rules, start=1):
        if not isinstance(item, dict):
            raise ConfigurationError(
                f"Rule #{i} must be a YAML mapping, got {type(item).__name__}."
            )
        missing = [f for f in ("type", "action") if f not in item]
        if missing:
            raise ConfigurationError(
                f"Rule #{i} is missing required field(s): {missing}."
            )

        action_str = str(item["action"]).lower()
        if action_str not in _VALID_ACTIONS:
            raise ConfigurationError(
                f"Rule #{i}: invalid action '{action_str}'. "
                f"Must be one of: {sorted(_VALID_ACTIONS)}."
            )

        rules.append(Rule(type=str(item["type"]), action=Action(action_str)))

    return rules


def load_config(config_path: Union[str, Path]) -> PolicyConfig:
    """
    Load and validate a :class:`~promptshield.policy.models.PolicyConfig`
    from a YAML file.

    Expected YAML structure::

        version: "1.0"
        default_action: allow   # mask | block | allow
        rules:
          - type: email
            action: mask
          - type: api_key
            action: block

    Args:
        config_path: Path to the ``.yaml`` policy file.

    Returns:
        A validated :class:`~promptshield.policy.models.PolicyConfig`.

    Raises:
        ConfigurationError: If the file is missing, cannot be parsed as YAML,
            or contains invalid values.
    """
    path = Path(config_path)
    if not path.exists():
        raise ConfigurationError(
            f"Policy config file not found: '{path}'. "
            "Check that the path is correct or provide a PolicyConfig directly."
        )

    try:
        with path.open("r", encoding="utf-8") as fh:
            raw: Dict[str, Any] = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Failed to parse YAML from '{path}': {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise ConfigurationError(
            "Policy config must be a YAML mapping at the top level."
        )

    rules = _parse_rules(raw.get("rules", []))

    default_str = str(raw.get("default_action", "allow")).lower()
    if default_str not in _VALID_ACTIONS:
        raise ConfigurationError(
            f"Invalid default_action '{default_str}'. "
            f"Must be one of: {sorted(_VALID_ACTIONS)}."
        )

    return PolicyConfig(
        rules=rules,
        default_action=Action(default_str),
        version=str(raw.get("version", "1.0")),
    )
