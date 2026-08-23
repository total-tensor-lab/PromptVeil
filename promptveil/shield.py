"""
PromptVeil — core Shield class.

This module exposes the primary public API.  Import and use it as::

    from promptveil import Shield

    shield = Shield(config_path="policy.yaml")
    safe_prompt = shield.scan(prompt)
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .actions.blocker import block
from .actions.masker import apply_masks, mask_value
from .config.loader import load_config_with_profile
from .detector.base import BaseDetector, DetectedEntity
from .detector.regex_detector import RegexDetector
from .exceptions import ConfigurationError, SensitiveDataError
from .logger.audit_logger import AuditLogger
from .policy.engine import PolicyEngine
from .policy.models import Action, PolicyConfig
from .results import EntityResult, ScanResult, _compute_risk_score, _risk_level
from .vault import PseudonymVault


class Shield:
    """
    Central orchestrator for PromptVeil.

    Wires together detection, policy evaluation, action execution, and audit
    logging into a single :meth:`scan` call.

    Example::

        from promptveil import Shield

        shield = Shield(config_path="policy.yaml")

        # Masks emails, blocks API keys, passes everything else through.
        safe = shield.scan("Email me at bob@example.com")
        # → "Email me at b***@example.com"

    You can also construct a :class:`Shield` programmatically without a YAML
    file::

        from promptveil.policy.models import Action, PolicyConfig, Rule

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
        Initialise PromptVeil.

        Exactly one of *config_path* or *config* must be provided.

        Args:
            config_path: Path to a YAML policy file.
            config: A pre-built :class:`~promptveil.policy.models.PolicyConfig`.
                Useful for programmatic configuration without a YAML file.
            detectors: Ordered list of :class:`~promptveil.detector.base.BaseDetector`
                instances. Defaults to ``[RegexDetector()]``.  Add custom
                detectors here or via :meth:`add_detector`.
            logger: Custom :class:`~promptveil.logger.audit_logger.AuditLogger`.
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

        if config_path is not None:
            policy_config, profile_detectors = load_config_with_profile(config_path)  # type: ignore[arg-type]
        else:
            policy_config = config  # type: ignore[assignment]
            profile_detectors = None

        self._policy = PolicyEngine(policy_config)
        # Explicit detectors always win; then profile defaults; then built-in.
        if detectors is not None:
            self._detectors: List[BaseDetector] = detectors
        elif profile_detectors is not None:
            self._detectors = profile_detectors
        else:
            self._detectors = [RegexDetector()]
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
           and raise :class:`~promptveil.exceptions.SensitiveDataError`
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
                :class:`~promptveil.detector.base.BaseDetector`.
        """
        self._detectors.append(detector)

    # ------------------------------------------------------------------
    # Rich scan — returns ScanResult with risk scoring
    # ------------------------------------------------------------------

    def scan_detailed(self, prompt: str) -> ScanResult:
        """
        Scan a prompt and return a rich :class:`~promptveil.results.ScanResult`.

        Identical policy semantics to :meth:`scan` (block still raises), but
        instead of returning a plain string this method returns a structured
        object that includes every detected entity, the action taken, a
        composite risk score, and a risk level label.

        Args:
            prompt: The raw input text to evaluate.

        Returns:
            :class:`~promptveil.results.ScanResult` with ``safe_text``,
            ``entities``, ``risk_score``, ``risk_level``, and ``was_mutated``.

        Raises:
            SensitiveDataError: Same conditions as :meth:`scan`.
            TypeError: If *prompt* is not a ``str``.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"prompt must be a str, got {type(prompt).__name__!r}."
            )

        # 1. Detect
        all_entities: List[DetectedEntity] = []
        for detector in self._detectors:
            all_entities.extend(detector.detect(prompt))

        if not all_entities:
            return ScanResult(
                safe_text=prompt,
                entities=[],
                risk_score=0.0,
                risk_level="NONE",
                was_mutated=False,
            )

        # 2. Evaluate
        evaluated: Dict[DetectedEntity, Action] = self._policy.evaluate(all_entities)

        # 3. Block (fail-fast)
        for entity, action in evaluated.items():
            if action == Action.BLOCK:
                self._logger.log_blocked(entity)
                block(entity)

        # 4. Build per-entity results and collect masks
        to_mask: List[DetectedEntity] = []
        entity_results: List[EntityResult] = []

        for entity, action in evaluated.items():
            if action == Action.MASK:
                mv = mask_value(entity.value, entity.entity_type)
                to_mask.append(entity)
                entity_results.append(
                    EntityResult(
                        entity_type=entity.entity_type,
                        action="mask",
                        start=entity.start,
                        end=entity.end,
                        masked_value=mv,
                        confidence=entity.confidence,
                    )
                )
            else:  # ALLOW
                entity_results.append(
                    EntityResult(
                        entity_type=entity.entity_type,
                        action="allow",
                        start=entity.start,
                        end=entity.end,
                        masked_value=entity.value,
                        confidence=entity.confidence,
                    )
                )

        # 5. Audit log
        if to_mask:
            log_records = [
                (e, Action.MASK, mask_value(e.value, e.entity_type))
                for e in to_mask
            ]
            self._logger.log_scan_result(log_records, len(prompt))

        safe_text = apply_masks(prompt, to_mask) if to_mask else prompt
        risk_score = _compute_risk_score(entity_results)

        return ScanResult(
            safe_text=safe_text,
            entities=entity_results,
            risk_score=risk_score,
            risk_level=_risk_level(risk_score),
            was_mutated=bool(to_mask),
        )

    # ------------------------------------------------------------------
    # Vault-based pseudonymization
    # ------------------------------------------------------------------

    def scan_with_vault(
        self,
        prompt: str,
        vault: Optional[PseudonymVault] = None,
    ) -> Tuple[str, PseudonymVault]:
        """
        Scan a prompt and replace masked entities with reversible pseudonym
        tokens instead of irreversible masks.

        Tokens follow the pattern ``<ENTITY_TYPE_N>`` (e.g. ``<EMAIL_1>``).
        The same original value always receives the same token within a vault
        instance.  After the LLM processes the pseudonymized text, call
        :meth:`~promptveil.vault.PseudonymVault.restore` on the response to
        reinstate original values.

        Example::

            pseudonymized, vault = shield.scan_with_vault(
                "Email john@acme.com or call +1-555-867-5309."
            )
            # → "Email <EMAIL_1> or call <PHONE_1>."

            llm_response = call_llm(pseudonymized)
            restored = vault.restore(llm_response)

        Args:
            prompt: The raw input text to evaluate.
            vault:  An existing :class:`~promptveil.vault.PseudonymVault`
                    to reuse (for multi-turn consistency).  A new vault is
                    created when ``None``.

        Returns:
            A 2-tuple ``(pseudonymized_text, vault)``.

        Raises:
            SensitiveDataError: Same conditions as :meth:`scan`.
            TypeError: If *prompt* is not a ``str``.
        """
        if not isinstance(prompt, str):
            raise TypeError(
                f"prompt must be a str, got {type(prompt).__name__!r}."
            )

        if vault is None:
            vault = PseudonymVault()

        # 1. Detect
        all_entities: List[DetectedEntity] = []
        for detector in self._detectors:
            all_entities.extend(detector.detect(prompt))

        if not all_entities:
            return prompt, vault

        # 2. Evaluate
        evaluated: Dict[DetectedEntity, Action] = self._policy.evaluate(all_entities)

        # 3. Block (fail-fast)
        for entity, action in evaluated.items():
            if action == Action.BLOCK:
                self._logger.log_blocked(entity)
                block(entity)

        # 4. Pseudonymize entities that would be masked
        to_pseudonymize = [e for e, a in evaluated.items() if a == Action.MASK]

        if not to_pseudonymize:
            return prompt, vault

        pseudonymized = vault.pseudonymize(prompt, to_pseudonymize)

        # 5. Audit log — log the assigned token as the "masked" value
        log_records = [
            (entity, Action.MASK, vault.get_token(entity.value) or "***")
            for entity in to_pseudonymize
        ]
        self._logger.log_scan_result(log_records, len(prompt))

        return pseudonymized, vault
