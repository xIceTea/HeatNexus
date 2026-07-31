"""Wertparsing: fehlende Werte dürfen niemals als 0 durchgehen."""

from __future__ import annotations

import pytest


def test_decimals_survive(helpers):
    assert helpers.parse_value("45.7", float) == pytest.approx(45.7)


def test_int_parsing_truncates_float_strings(helpers):
    assert helpers.parse_value("45.7", int) == 45


def test_missing_value_is_none(helpers):
    assert helpers.parse_value(None, float) is None


@pytest.mark.parametrize("raw", ["-.-", "-", "", "kaputt"])
def test_invalid_values_are_none(helpers, raw):
    assert helpers.parse_value(raw, float) is None


class _Coordinator:
    def __init__(self, oids):
        self.data = {"oids": oids}


def test_get_oid_value_uses_prefix(helpers):
    coordinator = _Coordinator({"/1/15/0/1/1/0": "21.5"})
    assert helpers.get_oid_value(coordinator, "/1/1/0", "/1/15/0") == pytest.approx(21.5)


def test_get_oid_value_missing_returns_none_not_zero(helpers):
    coordinator = _Coordinator({})
    assert helpers.get_oid_value(coordinator, "/1/1/0", "/1/15/0") is None
