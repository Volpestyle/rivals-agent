"""Regression for the observed probe timeout and cumulative two-attempt cap."""
from decimal import Decimal
import json
from pathlib import Path

import pytest

from cloud.modal_guard.holds import bootstrap
from cloud.modal_guard.common import Refused


ENVELOPE = json.loads(Path(__file__).with_name('envelope.json').read_bytes())
OBSERVED_STARTUP_AND_WORK = 67


def check(envelope):
    assert envelope['work_seconds'] >= 2 * OBSERVED_STARTUP_AND_WORK
    assert envelope['startup_seconds'] >= 2 * 7
    hold = bootstrap(envelope)
    assert Decimal('0.103715') + Decimal(hold['reserved_usd']) <= Decimal('0.80')
    assert envelope['attempt_ids'] == ['idm-expanded-20260928-probe-02']
    return hold


def test_fresh_probe_has_headroom_and_fits_remaining_allowance():
    assert check(ENVELOPE)['reserved_usd'] == '0.394587'


def test_old_function_timeout_is_refused():
    with pytest.raises(AssertionError):
        check({**ENVELOPE, 'work_seconds': 60})


def test_total_probe_budget_includes_spent_attempt():
    with pytest.raises((AssertionError, Refused)):
        check({**ENVELOPE, 'work_seconds': 2000})


def test_historical_attempt_cannot_be_reused():
    with pytest.raises(AssertionError):
        check({**ENVELOPE, 'attempt_ids': ['idm-expanded-20260928-probe-01']})
