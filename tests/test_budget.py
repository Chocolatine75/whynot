"""The per-command model budget: refused before running, hard stop during the run."""

import math
import threading

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fakes import FakeOpenAI, make_settings
from whynot.budget import Budget, BudgetExceeded, CallEstimate, estimate_usd
from whynot.models import ModelClient


def test_refuses_to_start_above_the_cap():
    with pytest.raises(BudgetExceeded, match=r"above the \$1.00 cap"):
        Budget(1.0).require(1.01)
    Budget(1.0).require(1.0)
    Budget(None).require(1e9)  # no cap: never refuses


@pytest.mark.parametrize("bad", [-0.01, math.nan])
def test_bad_numbers_are_refused(bad):
    with pytest.raises(ValueError):
        Budget(bad)
    with pytest.raises(ValueError):
        Budget(1.0).require(bad)


def test_estimate_uses_the_price_table():
    one = CallEstimate("muse-spark-1.3", input_tokens=1_000_000, output_tokens=1_000_000)
    assert one.usd == pytest.approx(1.25 + 4.25)
    assert estimate_usd(one, CallEstimate("muse-spark-1.3", 0, 1_000_000, calls=2)) == pytest.approx(5.5 + 8.5)


@given(cap=st.floats(0, 1), costs=st.lists(st.floats(0, 0.2), max_size=60))
def test_spend_never_exceeds_the_cap_plus_one_call(cap, costs):
    budget = Budget(cap)
    for usd in costs:
        try:
            budget.check()
        except BudgetExceeded:
            break
        budget.add(usd)
    assert budget.spent <= cap + max(costs, default=0) + 1e-12
    assert budget.remaining >= 0


def test_parallel_spend_is_counted_exactly():
    budget = Budget(None)

    def spend():
        for _ in range(1000):
            budget.add(0.001)

    threads = [threading.Thread(target=spend) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert budget.spent == pytest.approx(8.0)


def test_client_stops_calling_once_the_budget_is_spent(tmp_path):
    fake = FakeOpenAI()
    client = ModelClient(make_settings(tmp_path), meta=fake, budget_usd=0.002)
    calls = 0
    with pytest.raises(BudgetExceeded):
        for _ in range(100):
            client.chat([{"role": "user", "content": "hi"}], module="t")
            calls += 1
    one = client.ledger.events()[0].usd
    assert client.spent_usd <= 0.002 + one
    assert len(fake.chat.calls) == calls  # the refused call never reached the API
