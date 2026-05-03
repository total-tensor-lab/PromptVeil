"""Tests for the YAML config loader."""

import textwrap
from pathlib import Path

import pytest

from promptshield.config.loader import load_config
from promptshield.exceptions import ConfigurationError
from promptshield.policy.models import Action


def write_yaml(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "policy.yaml"
    f.write_text(textwrap.dedent(content))
    return f


class TestLoadConfig:
    def test_valid_config(self, tmp_path):
        path = write_yaml(
            tmp_path,
            """
            version: "1.0"
            default_action: allow
            rules:
              - type: email
                action: mask
              - type: api_key
                action: block
            """,
        )
        config = load_config(path)
        assert config.version == "1.0"
        assert config.default_action == Action.ALLOW
        assert len(config.rules) == 2

    def test_default_action_defaults_to_allow(self, tmp_path):
        path = write_yaml(tmp_path, "rules: []")
        config = load_config(path)
        assert config.default_action == Action.ALLOW

    def test_empty_rules(self, tmp_path):
        path = write_yaml(tmp_path, "rules: []")
        config = load_config(path)
        assert config.rules == []

    def test_file_not_found(self):
        with pytest.raises(ConfigurationError, match="not found"):
            load_config("/nonexistent/path.yaml")

    def test_invalid_action(self, tmp_path):
        path = write_yaml(
            tmp_path,
            """
            rules:
              - type: email
                action: destroy
            """,
        )
        with pytest.raises(ConfigurationError, match="invalid action"):
            load_config(path)

    def test_missing_type_field(self, tmp_path):
        path = write_yaml(
            tmp_path,
            """
            rules:
              - action: mask
            """,
        )
        with pytest.raises(ConfigurationError, match="missing"):
            load_config(path)

    def test_missing_action_field(self, tmp_path):
        path = write_yaml(
            tmp_path,
            """
            rules:
              - type: email
            """,
        )
        with pytest.raises(ConfigurationError, match="missing"):
            load_config(path)

    def test_invalid_yaml(self, tmp_path):
        bad = tmp_path / "policy.yaml"
        bad.write_text(": : invalid : yaml :")
        with pytest.raises(ConfigurationError):
            load_config(bad)
