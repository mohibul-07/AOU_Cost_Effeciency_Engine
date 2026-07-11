"""Tests for the IPython magic integration."""

from unittest.mock import MagicMock, patch

import pytest
from IPython.terminal.interactiveshell import TerminalInteractiveShell

from aou_cost_engine.magic import AouCostMagics


@pytest.fixture
def magic():
    shell = TerminalInteractiveShell.instance()
    m = AouCostMagics(shell)
    return m


class TestAouCostConfig:
    def test_enable_ai(self, magic):
        magic.aou_cost_config("--ai on")
        assert magic._ai_enabled is True

    def test_disable_ai(self, magic):
        magic._ai_enabled = True
        magic.aou_cost_config("--ai off")
        assert magic._ai_enabled is False

    def test_set_threshold(self, magic):
        magic.aou_cost_config("--threshold 0.05")
        assert magic._cost_threshold == 0.05

    def test_auto_cap(self, magic):
        magic.aou_cost_config("--auto-cap on")
        assert magic._auto_cap is True


class TestGetBqClient:
    def test_finds_client_in_namespace(self, magic):
        mock_client = MagicMock()
        mock_client.query = MagicMock()
        magic.shell.user_ns["client"] = mock_client
        result = magic._get_bq_client()
        assert result is mock_client
        del magic.shell.user_ns["client"]

    def test_finds_bq_client_in_namespace(self, magic):
        mock_client = MagicMock()
        mock_client.query = MagicMock()
        magic.shell.user_ns["bq_client"] = mock_client
        result = magic._get_bq_client()
        assert result is mock_client
        del magic.shell.user_ns["bq_client"]

    def test_no_client_falls_back(self, magic):
        with patch("google.cloud.bigquery.Client") as mock_cls:
            mock_cls.side_effect = Exception("No credentials")
            result = magic._get_bq_client()
            assert result is None
