"""
PromptShield — core Shield class.

This module exposes the primary public API.  Import and use it as::

    from promptshield import Shield

    shield = Shield(config_path="policy.yaml")
    safe_prompt = shield.scan(prompt)
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from .actions.blocker import block
from .actions.masker import apply_masks, mask_value
from .config.loader import load_config
from .detector.base import BaseDetector, DetectedEntity
from .detector.regex_detector import RegexDetector
from .exceptions import ConfigurationError, SensitiveDataError
from .logger.audit_logger import AuditLogger
from .policy.engine import PolicyEngine
from .policy.models import Action, PolicyConfig


class Shield:
    """
    Central orchestrator for PromptShield.

    Wires together detection, policy evaluation, action execution, and audit
    logging into a single :meth:`scan` call.

    Example::

        from promptshield import Shield

        shield = Shield(config_path="policy.yaml")

        # Masks emails, blocks API keys, passes everything else through.
        safe = shield.scan("Email me at bob@example.com")
        # → "Email me at b***@example.com"

    You can also construct a :class:`Shield` programmatically without a YAML
    file::

        from promptshield.policy.models import Action, PolicyConfig, Rule

        config = PolicyConfig(
            rules=[Rule(type="email", action=Action.MASK)],
            default_action=Action.ALLOW,
        )
        shield = Shield(config=config)
    """

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        config: Optional[PolicyConfig] = None,
        detectors: Optional[List[BaseDetector]] = None,
        logger: Optional[AuditLogger] = None,
    ) -> None:
        """
        Initialise PromptShield.

        Exactly one of *config_path* or *config* must be provided.

        Args:
            config_path: Path to a YAML policy file.
            config: A pre-built :class:`~promptshield.policy.models.PolicyConfig`.
                Useful for programmatic configuration without a YAML file.
            detectors: Ordered list of :class:`~promptshield.detector.base.BaseDetector`
                instances. Defaults to ``[RegexDetector()]``.  Add custom
                detectors here or via :meth:`add_detector`.
            logger: Custom :class:`~promptshield.logger.audit_logger.AuditLogger`.
                Defaults to a logger that writes JSON lines to ``stdout``.

        Raises:
            ConfigurationError: If neither or both of *config_path* / *config*
                are provided, or if the YAML file is invalid.
        """
        if config_path is not None and config is not None:
            raise ConfigurationError(
                "Provide either 'config_path' or 'config', not both."
            )
        if config_path is None and config is None:
            raise ConfigurationError(
                "A policy is required. Provide 'config_path' (YAML file path) "
                "or 'config' (a PolicyConfig instance)."
            )

        policy_config = (
            config if config is not None else load_config(config_path)  # type: ignore[arg-type]
        )

        self._policy = PolicyEngine(policy_config)
        self._detectors: List[BaseDetector] = (
            detectors if detectors is not None else [RegexDetector()]
        )
        self._logger = logger if logger is not None else AuditLogger()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, prompt: str) -> str:
        """
        Scan a prompt for sensitive data and apply configured policy rules.

        Processing order:

        1. Run every registered detector against the prompt.
        2. Evaluate each detected entity against policy rules.
        3. **Block** — if any entity matches a ``block`` rule, log the event
           and raise :class:`~promptshield.exceptions.SensitiveDataError`
           immediately (before any masking).
        4. **Mask** — replace all entities matching ``mask`` rules with
           redacted placeholders.
        5. **Allow** — entities matching ``allow`` rules (or the default
           action) pass through unchanged.
        6. Log all mask actions for audit.

        Args:
            prompt: The raw input text to evaluate.

        Returns:
            A sanitised copy of *prompt* with sensitive values masked.
            If no sensitive data is detected the original string is returned
            unchanged.

        Raises:
            SensitiveDataError: When a detected entity type maps to the
                ``block`` action in the active policy.
            TypeError: If *prompt* is not a ``str``.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"prompt must be a str, got {type(prompt).__name__!r}."
            )

        # --- 1. Detect --------------------------------------------------
        all_entities: List[DetectedEntity] = []
        for detector in self._detectors:
            all_entities.extend(detector.detect(prompt))

        if not all_entities:
            return prompt

        # --- 2. Evaluate ------------------------------------------------
        evaluated: Dict[DetectedEntity, Action] = self._policy.evaluate(all_entities)

        # --- 3. Block (fail-fast) ----------------------------------------
        for entity, action in evaluated.items():
            if action == Action.BLOCK:
                self._logger.log_blocked(entity)
                block(entity)  # always raises SensitiveDataError

        # --- 4 & 5. Collect masks / allows --------------------------------
        to_mask = [e for e, a in evaluated.items() if a == Action.MASK]

        # --- 6. Audit log -------------------------------------------------
        if to_mask:
            log_records = [
                (entity, Action.MASK, mask_value(entity.value, entity.entity_type))
                for entity in to_mask
            ]
            self._logger.log_scan_result(log_records, len(prompt))

        # --- Apply masking ------------------------------------------------
        if to_mask:
            return apply_masks(prompt, to_mask)

        return prompt

    def scan_response(self, response: str) -> str:
        """
        Scan an LLM *response* for sensitive data (same logic as :meth:`scan`).

        Useful when you also want to sanitise the model's output before
        returning it to the end user.

        Args:
            response: The LLM response text to scan.

        Returns:
            Sanitised response string.

        Raises:
            SensitiveDataError: Same conditions as :meth:`scan`.
        """
        return self.scan(response)

    def add_detector(self, detector: BaseDetector) -> None:
        """
        Register an additional detector at runtime.

        Detectors are run in the order they were added.

        Args:
            detector: Any object that implements
                :class:`~promptshield.detector.base.BaseDetector`.
        """
        self._detectors.append(detector)
