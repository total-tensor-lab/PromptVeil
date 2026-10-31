"""Shared benchmark fixtures and benchmark-specific pytest hooks."""

from __future__ import annotations

from typing import Callable

import pytest

from promptveil import PseudonymVault, Shield
from promptveil.detector.india_detector import IndiaDetector
from promptveil.detector.regex_detector import RegexDetector
from promptveil.detector.us_detector import USDetector
from promptveil.policy.models import Action, PolicyConfig, Rule

from benchmarks.fixtures.corpus import ALL_POLICY_TYPES
from benchmarks.utils.recording import compact_results


@pytest.hookimpl(optionalhook=True)
def pytest_benchmark_generate_machine_info():
    return {}


@pytest.hookimpl(optionalhook=True)
def pytest_benchmark_generate_commit_info():
    return {}


@pytest.hookimpl(optionalhook=True)
def pytest_benchmark_update_json(output_json):
    compact_results(output_json)


class NullAuditLogger:
    """No-op logger so benchmark timings exclude stdout I/O."""

    def log_scan_result(self, entity_records, prompt_length: int) -> None:
        del entity_records, prompt_length

    def log_blocked(self, entity) -> None:
        del entity


def _mask_all_config() -> PolicyConfig:
    return PolicyConfig(
        rules=[Rule(type=entity_type, action=Action.MASK) for entity_type in ALL_POLICY_TYPES],
        default_action=Action.ALLOW,
    )


def _build_shield(detectors) -> Shield:
    return Shield(
        config=_mask_all_config(),
        detectors=list(detectors),
        logger=NullAuditLogger(),
    )


def pytest_collection_modifyitems(config, items) -> None:
    del config
    for item in items:
        if "/benchmarks/" in str(item.fspath):
            item.add_marker(pytest.mark.benchmark_suite)


@pytest.fixture(scope="session")
def shield_factory() -> Callable[[], Shield]:
    def factory() -> Shield:
        return _build_shield([RegexDetector(), IndiaDetector(), USDetector()])

    return factory


@pytest.fixture(scope="session")
def regex_detector() -> RegexDetector:
    return RegexDetector()


@pytest.fixture(scope="session")
def india_detector() -> IndiaDetector:
    return IndiaDetector()


@pytest.fixture(scope="session")
def us_detector() -> USDetector:
    return USDetector()


@pytest.fixture(scope="session")
def regex_shield() -> Shield:
    return _build_shield([RegexDetector()])


@pytest.fixture(scope="session")
def india_shield() -> Shield:
    return _build_shield([IndiaDetector()])


@pytest.fixture(scope="session")
def us_shield() -> Shield:
    return _build_shield([USDetector()])


@pytest.fixture(scope="session")
def full_stack_shield(shield_factory: Callable[[], Shield]) -> Shield:
    return shield_factory()


@pytest.fixture()
def vault() -> PseudonymVault:
    return PseudonymVault()
