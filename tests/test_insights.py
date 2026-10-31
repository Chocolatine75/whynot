"""Results per ad and day: the Insights API (on a fake Graph) and the simulated account."""

import json
from datetime import date, timedelta

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whynot.run.insights import CONVERSIONS, MetaInsights, SimulatedAccount, parse_rows
from whynot.run.meta import Account, MarketingClient

TOKEN = "EAAinsightsSECRET42"


def row(ad, day, spend="3.10", imp="400", clicks="5", installs=None, links=None):
    actions = []
    if installs is not None:
        actions.append({"action_type": "mobile_app_install", "value": str(installs)})
    if links is not None:
        actions.append({"action_type": "link_click", "value": str(links)})
    return {"ad_id": ad, "date_start": day, "date_stop": day, "spend": spend, "impressions": imp, "clicks": clicks,
            "actions": actions}


def test_rows_become_metrics_per_ad_and_day():
    rows = [row("a", "2026-11-02", installs=2, links=4), row("a", "2026-11-01", installs=1),
            row("b", "2026-11-01", spend="0", imp="0", clicks="0"), row("a", "2026-11-02", spend="1.00", imp="10",
                                                                         clicks="1", installs=1)]
    m = parse_rows(rows, CONVERSIONS["app_promotion"])
    assert [d.day for d in m["a"]] == ["2026-11-01", "2026-11-02"]  # in order
    assert m["a"][1].spend_eur == 4.10 and m["a"][1].conversions == 3  # duplicate rows of a day are summed
    assert m["b"][0].conversions == 0
    assert parse_rows([row("a", "2026-11-01", links=7)], CONVERSIONS["traffic"])["a"][0].conversions == 7


@pytest.mark.parametrize("junk", ["NaN", "-5", "abc", None, "inf"])
def test_junk_numbers_count_as_zero(junk):
    m = parse_rows([row("a", "2026-11-01", spend=junk, imp=junk, clicks=junk)], ("x",))
    assert m["a"][0].spend_eur == 0 and m["a"][0].impressions == 0


@settings(max_examples=50, deadline=None)
@given(st.lists(st.tuples(st.sampled_from("abc"), st.integers(1, 5), st.integers(0, 900), st.integers(0, 9)),
                max_size=30))
def test_totals_per_day_match_the_rows(spec):
    rows = [row(ad, f"2026-11-0{d}", spend=f"{c / 100:.2f}", installs=i) for ad, d, c, i in spec]
    m = parse_rows(rows, CONVERSIONS["app_promotion"])
    assert sum(x.conversions for days in m.values() for x in days) == sum(i for *_, i in spec)
    total = round(sum(x.spend_eur for days in m.values() for x in days), 2)
    assert total == round(sum(c for *_, c, _ in spec) / 100, 2)


def graph(pages, seen):
    def handler(request):
        seen.append(request)
        params = dict(request.url.params)
        assert params["access_token"] == TOKEN and params["level"] == "ad" and params["time_increment"] == "1"
        page = pages[1] if params.get("after") == "cur1" else pages[0]
        return httpx.Response(200, json=page)
    return MarketingClient(Account("123", TOKEN), http=httpx.Client(transport=httpx.MockTransport(handler)),
                           sleep=lambda s: None)


def test_meta_insights_follow_cursors_not_the_token_url():
    pages = [{"data": [row("a", "2026-11-01", links=3)],
              "paging": {"cursors": {"after": "cur1"}, "next": f"https://graph.facebook.com/x?access_token={TOKEN}"}},
             {"data": [row("a", "2026-11-02", links=1)], "paging": {"cursors": {"after": "cur2"}}}]
    seen = []
    m = MetaInsights(graph(pages, seen)).fetch(["a"], date(2026, 11, 1), date(2026, 11, 2))
    assert [d.conversions for d in m["a"]] == [3, 1] and len(seen) == 2
    assert json.loads(dict(seen[0].url.params)["filtering"])[0]["value"] == ["a"]
    assert MetaInsights(graph(pages, [])).fetch([], date(2026, 11, 1), date(2026, 11, 2)) == {}
    with pytest.raises(ValueError):
        MetaInsights(graph(pages, []), objective="likes")


def test_recent_days_are_provisional():
    ins = MetaInsights(graph([{"data": []}], []), settle_days=1)
    today = date(2026, 11, 3)
    assert ins.provisional(date(2026, 11, 2), today) and not ins.provisional(date(2026, 11, 1), today)


def test_the_simulated_account_is_deterministic_tires_and_keeps_its_truths():
    acc = SimulatedAccount(seed=3)
    d0 = date(2026, 11, 1)
    a = acc.fetch(["good", "bad"], d0, d0 + timedelta(days=9), launched={"good": d0, "bad": d0 + timedelta(days=5)})
    assert a == acc.fetch(["good", "bad"], d0, d0 + timedelta(days=9),
                          launched={"good": d0, "bad": d0 + timedelta(days=5)})
    assert len(a["good"]) == 10 and len(a["bad"]) == 5  # an ad has results only after its launch
    assert acc.simulated is True
    assert all(0.3 <= acc.quality(x) <= 1.7 for x in ("good", "bad", "x", "y"))
    many = [acc.day("q", d0 + timedelta(days=i), i) for i in range(30)]
    early, late = sum(m.clicks for m in many[:7]), sum(m.clicks for m in many[-7:])
    assert late < early  # ads tire
