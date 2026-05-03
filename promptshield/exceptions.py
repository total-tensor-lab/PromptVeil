"""Custom exceptions for PromptShield."""


class PromptShieldError(Exception):
    """Base exception for all PromptShield errors."""


class SensitiveDataError(PromptShieldError):
    """
    Raised when sensitive data is detected and the policy action is 'block'.

    Attributes:
        entity_type: The type of sensitive entity that triggered the block.
    """

    def __init__(self, message: str, entity_type: str = "") -> None:
        super().__init__(message)
        self.entity_type = entity_type


class ConfigurationError(PromptShieldError):
    """Raised when the policy configuration is invalid or cannot be loaded."""
