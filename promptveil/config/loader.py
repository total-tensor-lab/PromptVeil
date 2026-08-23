"""YAML policy configuration loader and validator."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
        List of validated :class:`~promptveil.policy.models.Rule` objects.

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

        min_confidence = float(item.get("min_confidence", 0.0))
        if not (0.0 <= min_confidence <= 1.0):
            raise ConfigurationError(
                f"Rule #{i}: 'min_confidence' must be between 0.0 and 1.0, "
                f"got {min_confidence}."
            )

        rules.append(
            Rule(
                type=str(item["type"]),
                action=Action(action_str),
                min_confidence=min_confidence,
            )
        )

    return rules


def _read_raw_yaml(config_path: Union[str, Path]) -> Dict[str, Any]:
    """Read and parse YAML, raising ConfigurationError on any failure."""
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
    return raw


def load_config(config_path: Union[str, Path]) -> PolicyConfig:
    """
    Load and validate a :class:`~promptveil.policy.models.PolicyConfig`
    from a YAML file.  Backward-compatible; ignores ``profile:`` detector
    side-effects (use :func:`load_config_with_profile` from ``Shield``).

    Expected YAML structure::

        version: "1.0"
        default_action: allow   # mask | block | allow
        rules:
          - type: email
            action: mask
            min_confidence: 0.8   # optional threshold
          - type: api_key
            action: block

    You may also specify a built-in compliance profile::

        profile: india_dpdpa    # india_dpdpa | eu_gdpr | us_hipaa
        rules:                  # optional per-type overrides
          - type: email
            action: allow

    Args:
        config_path: Path to the ``.yaml`` policy file.

    Returns:
        A validated :class:`~promptveil.policy.models.PolicyConfig`.

    Raises:
        ConfigurationError: If the file is missing, cannot be parsed as YAML,
            or contains invalid values.
    """
    policy, _ = load_config_with_profile(config_path)
    return policy


def load_config_with_profile(
    config_path: Union[str, Path],
) -> Tuple[PolicyConfig, Optional[List[Any]]]:
    """
    Load a policy config from YAML, resolving any ``profile:`` key.

    Returns:
        A 2-tuple ``(PolicyConfig, detectors_or_None)``.  When a ``profile:``
        key is present the second element is the profile's default detector
        list; otherwise it is ``None`` (caller should use its own defaults).
    """
    raw = _read_raw_yaml(config_path)

    profile_name: Optional[str] = raw.get("profile")

    if profile_name:
        # Late import to avoid circular dependency: profiles → detector → …
        from ..profiles import load_profile  # type: ignore[import]

        profile = load_profile(str(profile_name))

        # Profile rules are the base; YAML rules act as per-type overrides.
        merged: Dict[str, Rule] = {r.type: r for r in profile.policy.rules}
        for override in _parse_rules(raw.get("rules", [])):
            merged[override.type] = override

        default_str = str(
            raw.get("default_action", profile.policy.default_action.value)
        ).lower()
        if default_str not in _VALID_ACTIONS:
            raise ConfigurationError(
                f"Invalid default_action '{default_str}'. "
                f"Must be one of: {sorted(_VALID_ACTIONS)}."
            )

        policy = PolicyConfig(
            rules=list(merged.values()),
            default_action=Action(default_str),
            version=str(raw.get("version", "1.0")),
        )
        return policy, profile.detectors

    # ── Plain config (no profile) ─────────────────────────────────────────
    rules = _parse_rules(raw.get("rules", []))
    default_str = str(raw.get("default_action", "allow")).lower()
    if default_str not in _VALID_ACTIONS:
        raise ConfigurationError(
            f"Invalid default_action '{default_str}'. "
            f"Must be one of: {sorted(_VALID_ACTIONS)}."
        )

    return (
        PolicyConfig(
            rules=rules,
            default_action=Action(default_str),
            version=str(raw.get("version", "1.0")),
        ),
        None,
    )
