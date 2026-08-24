"""Compliance profile registry for PromptVeil.

Available built-in profiles
----------------------------
``india_dpdpa``   India Digital Personal Data Protection Act (2023)
``eu_gdpr``       EU General Data Protection Regulation
``us_hipaa``      US Health Insurance Portability and Accountability Act

Usage in YAML policy::

    profile: india_dpdpa
    # optional per-type overrides:
    rules:
      - type: email
        action: allow

Usage in code::

    from promptveil.profiles import load_profile

    profile = load_profile("india_dpdpa")
    shield = Shield(config=profile.policy, detectors=profile.detectors)
"""

from typing import Dict

from ..exceptions import ConfigurationError
from .base import Profile

# Lazy-imported to avoid pulling in all detectors at package import time.
_REGISTRY: Dict[str, Profile] = {}


def _build_registry() -> None:
    from . import eu_gdpr, india_dpdpa, us_hipaa  # noqa: F401

    _REGISTRY["india_dpdpa"] = india_dpdpa.PROFILE
    _REGISTRY["eu_gdpr"] = eu_gdpr.PROFILE
    _REGISTRY["us_hipaa"] = us_hipaa.PROFILE


_build_registry()


def load_profile(name: str) -> Profile:
    """
    Return a built-in :class:`Profile` by name.

    Args:
        name: One of ``"india_dpdpa"``, ``"eu_gdpr"``, ``"us_hipaa"``.

    Returns:
        The corresponding :class:`Profile` instance.

    Raises:
        ConfigurationError: If *name* is not a recognised profile.
    """
    if name not in _REGISTRY:
        raise ConfigurationError(
            f"Unknown profile '{name}'. "
            f"Available profiles: {sorted(_REGISTRY)}."
        )
    return _REGISTRY[name]


def available_profiles() -> list:
    """Return the list of registered profile names."""
    return sorted(_REGISTRY)


__all__ = ["Profile", "load_profile", "available_profiles"]
