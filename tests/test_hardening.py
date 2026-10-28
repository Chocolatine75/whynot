"""Regression tests for bugs found in the 2026-10-28 review, one per bug, plus edge cases.

Each test names the failure it prevents. No network.
"""

from pathlib import Path
from types import SimpleNamespace as NS

import httpx
import pytest

from fakes import FakeOpenAI, make_settings
from whynot.assets.sam import SamParseError, parse
from whynot.config import load_settings
from whynot.costs import UnknownModelPrice, check_priced, image_cost, segment_cost, token_cost
from whynot.create.composer import Brand, ComposeError, compose, hex_to_rgb
from whynot.create.templates import Template, TemplateError
from whynot.ingest.adlibrary import AdLibraryClient, AdLibraryError
from whynot.models import ModelClient
from whynot.sim.feed import FeedItem, build_candidate_feeds, build_market_feeds
from whynot.sim.personas import Persona
from whynot.sim.scores import score_ads
from whynot.sim.viewer import Reaction, Viewer, ViewerParseError, parse_reactions, run_simulation
from whynot.validate.stats import auc, bootstrap_ci, wilson_interval

TOKEN = "EAAtestSECRET123"


# --- costs and model client -------------------------------------------------------

def test_unpriced_model_fails_before_the_call_is_made(tmp_path):
    """Bug: the price was looked up after the call, so a billed call could go unlogged."""
    fake = FakeOpenAI()
    client = ModelClient(make_settings(tmp_path), meta=fake)
    with pytest.raises(UnknownModelPrice):
        client.chat([{"role": "user", "content": "hi"}], module="t", model="muse-spark-9.9")
    assert fake.chat.calls == []


def test_check_priced_knows_every_model_family():
    for model in ("muse-spark-1.3", "muse-image-1.0", "sam-3.1", "muse-voice-transcribe-1.0",
                  "meta-models/muse-spark-open"):
        check_priced(model)
    with pytest.raises(UnknownModelPrice):
        check_priced("gpt-x")


@pytest.mark.parametrize("call", [
    lambda: token_cost("muse-spark-1.3", -1, 0, 0),
    lambda: image_cost("muse-image-1.0", -1),
    lambda: segment_cost("sam-3.1", images=-1),
])
def test_negative_counts_are_rejected(call):
    with pytest.raises(ValueError):
        call()


def test_empty_choices_raise_but_cost_is_logged(tmp_path):
    fake = FakeOpenAI()
    fake.chat._resp.choices = []
    client = ModelClient(make_settings(tmp_path), meta=fake)
    with pytest.raises(RuntimeError, match="no choices"):
        client.chat([{"role": "user", "content": "hi"}], module="t")
    assert len(client.ledger.events()) == 1


def test_sam_cost_is_logged_even_if_the_stream_breaks(tmp_path):
    """Bug: a broken stream skipped the ledger although the request is billed."""
    fake = FakeOpenAI()

    def broken(**kw):
        yield NS(type="response.output_text.delta", delta="<|box;")
        raise httpx.ReadError("connection reset")

    fake.responses = NS(create=broken)
    client = ModelClient(make_settings(tmp_path), meta=fake)
    with pytest.raises(httpx.ReadError):
        client.segment("data:image/png;base64,AA", "phone", module="t")
    (event,) = client.ledger.events()
    assert event.model == "sam-3.1" and event.ok is False and event.usd > 0


# --- SAM parsing -------------------------------------------------------------------

def test_sam_payload_may_contain_the_closing_marker():
    """Bug: base85 (RFC 1924) includes '|' and '>', so '|>' inside data cut the payload."""
    text = "<0f>0<|mask;x=0;y=0;data=4,4,~ab|>cd|><|box;x1=0;y1=0;x2=2;y2=2;w=4;h=4|>"
    boxes, masks = parse(text)
    assert masks[0].payload == "ab|>cd" and len(boxes) == 1


@pytest.mark.parametrize("bad", [
    "<|box;x1=0;y1=0;x2=2;y2=2;w=4;h=4",           # unterminated
    "<|box;x1=0;y1=0;x2=9;y2=2;w=4;h=4|>",         # outside the frame
    "<|box;x1=a;y1=0;x2=2;y2=2;w=4;h=4|>",         # not a number
    "<|box;x1=0;y1=0;w=4;h=4|>",                   # missing corner
    "<|mask;x=0;y=0;data=4,4,|>",                  # no payload
    "<|mask;x=0;y=0;data=4|>",                     # no size
])
def test_sam_malformed_records_raise_a_clear_error(bad):
    with pytest.raises(SamParseError):
        parse(bad)


# --- Ad Library --------------------------------------------------------------------

def client_with(responses, sleeps):
    calls = []

    def handler(request):
        calls.append(request)
        r = responses[len(calls) - 1]
        if isinstance(r, Exception):
            raise r
        return r

    c = AdLibraryClient(TOKEN, http=httpx.Client(transport=httpx.MockTransport(handler)),
                        retries=2, backoff_s=1.0, sleep=sleeps.append)
    return c, calls


def ok_page():
    return httpx.Response(200, json={"data": [{"id": "1"}], "paging": {}})


def test_rate_limit_is_retried_with_backoff():
    sleeps = []
    c, calls = client_with([httpx.Response(400, json={"error": {"code": 613, "message": "slow down"}}),
                            httpx.Response(500, text="oops"), ok_page()], sleeps)
    assert [a.id for a in c.search(countries=["FR"], page_ids=["1"])] == ["1"]
    assert len(calls) == 3 and sleeps == [1.0, 2.0]


def test_token_errors_are_not_retried():
    sleeps = []
    c, calls = client_with([httpx.Response(400, json={"error": {"code": 190, "message": "expired"}})], sleeps)
    with pytest.raises(AdLibraryError, match="190"):
        list(c.search(countries=["FR"], page_ids=["1"]))
    assert len(calls) == 1 and sleeps == []


def test_network_errors_give_up_without_leaking_the_token():
    sleeps = []
    err = httpx.ConnectError(f"cannot reach https://graph.facebook.com/?access_token={TOKEN}")
    c, calls = client_with([err, err, err], sleeps)
    with pytest.raises(AdLibraryError) as exc:
        list(c.search(countries=["FR"], page_ids=["1"]))
    assert TOKEN not in str(exc.value) and len(calls) == 3


def test_search_needs_countries():
    c, _ = client_with([], [])
    with pytest.raises(ValueError, match="country"):
        list(c.search(countries=[], page_ids=["1"]))


# --- config ------------------------------------------------------------------------

def test_env_inline_comments_and_bad_numbers(monkeypatch):
    monkeypatch.setattr("whynot.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("AUTONOMY_LEVEL", "propose   # comment")
    monkeypatch.setenv("MAX_DAILY_AD_SPEND_EUR", "12.5 # cap")
    s = load_settings()
    assert (s.autonomy_level, s.max_daily_ad_spend_eur) == ("propose", 12.5)
    monkeypatch.setenv("MAX_DAILY_AD_SPEND_EUR", "ten")
    with pytest.raises(ValueError, match="MAX_DAILY_AD_SPEND_EUR"):
        load_settings()


# --- templates and composer --------------------------------------------------------

BASE = {"id": "t", "concept": "C", "persona": "p", "objection": "o",
        "genes": {"format": ["static_1080"], "hook": ["q"], "cta": ["Go"]}}


@pytest.mark.parametrize("data, msg", [
    (None, "mapping"),
    (["a"], "mapping"),
    ({**BASE, "guards": ["text_legible", "text_legible"]}, "duplicate guards"),
    ({**BASE, "genes": {**BASE["genes"], "hook": [" "]}}, "empty option"),
    ({**BASE, "copy": ["x"]}, "'copy' must be a mapping"),
    ({**BASE, "copy": {"hook": "text"}}, "must map options"),
])
def test_template_validation_edge_cases(data, msg):
    with pytest.raises(TemplateError, match=msg):
        Template.from_dict(data)


def test_invalid_yaml_file_is_a_template_error(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text("id: [unclosed")
    with pytest.raises(TemplateError, match="invalid YAML"):
        Template.load(p)


@pytest.mark.parametrize("palette, msg", [
    (["#FFFFFF", "#000000"], "at least 3"),
    (["#FFFFFF", "#000000", "#FFFFFF"], "duplicate"),
    (["#FFFFFF", "#000000", "#GGGGGG"], "bad colour"),
    (["#FFFFFF", "#000000", "#FFF"], "bad colour"),
])
def test_bad_palettes(palette, msg):
    with pytest.raises(ComposeError, match=msg):
        Brand.from_fixed({"brand": {"palette": palette}})


def test_hex_to_rgb():
    assert hex_to_rgb("#E4572E") == (228, 87, 46) and hex_to_rgb("000000") == (0, 0, 0)


def test_empty_headline_is_refused():
    from PIL import Image
    t = Template.from_dict({**BASE, "copy": {"hook": {"q": "   "}},
                            "fixed": {"brand": {"palette": ["#FFFFFF", "#111111", "#2255AA"]}}})
    with pytest.raises(ComposeError, match="empty headline"):
        compose(t, next(t.genomes()), Image.new("RGBA", (10, 10), (0, 0, 0, 255)))


# --- simulator ---------------------------------------------------------------------

def item(i):
    return FeedItem(str(i), f"B{i}", "", f"body {i}")


def test_feeds_reject_duplicate_ids_and_bad_sizes():
    with pytest.raises(ValueError, match="unique"):
        build_market_feeds([item(1), item(1), item(2)], feed_size=2, appearances=1)
    with pytest.raises(ValueError, match="appearances"):
        build_market_feeds([item(1), item(2)], feed_size=2, appearances=0)
    feeds = build_candidate_feeds(item(0), [item(1), item(1), item(2)], feed_size=3, n_feeds=4)
    assert all(len({i.ad_id for i in f}) == 3 for f in feeds)  # duplicates collapsed


class NeverCalled:
    def viewer_chat(self, *a, **k):
        raise AssertionError("should not be called")


def test_more_viewers_than_personas_is_refused():
    """Bug: the same persona saw a feed twice, which doubled its feed size in the score."""
    personas = [Persona("p0", "FR", "25-34", "male")]
    feeds = [[item(1), item(2)]]
    with pytest.raises(ValueError, match="personas"):
        run_simulation(Viewer(NeverCalled()), personas, feeds, viewers_per_feed=2)
    with pytest.raises(ValueError, match="unique"):
        run_simulation(Viewer(NeverCalled()), personas * 2, feeds, viewers_per_feed=1)


@pytest.mark.parametrize("answer", [
    '{"reactions": ["A1"], "preferred": "A1"}',                       # reaction is not an object
    '[1, 2]',                                                          # not an object at all
    '{"reactions": [{"ad": "A1", "stopped": true, "understood": true, "believed": true,'
    ' "intent_score": 1e999}], "preferred": "A1"}',                    # infinite score
])
def test_malformed_answers_are_parse_errors_not_crashes(answer):
    """Bug: these raised AttributeError/OverflowError, which skipped the retry."""
    with pytest.raises(ViewerParseError):
        parse_reactions(answer, {"A1": "x"}, feed_id="F", persona_id="p")


def test_top_why_not_is_the_most_frequent_objection():
    def r(why):
        return Reaction("F", "p", "ad", 0, False, True, False, why, "", 2, False)
    rs = [r("too expensive"), r("not for me"), r("too expensive"), r(""), r("too expensive"), r("not for me")]
    assert score_ads(rs, max_reasons=2)["ad"].top_why_not == ["too expensive", "not for me"]


# --- statistics --------------------------------------------------------------------

def test_stats_input_validation():
    with pytest.raises(ValueError):
        wilson_interval(5, 3)
    with pytest.raises(ValueError):
        bootstrap_ci(lambda idx: 0.0, 0)
    with pytest.raises(ValueError):
        bootstrap_ci(lambda idx: 0.0, 5, level=1.5)
    with pytest.raises(ValueError):
        auc([1.0, 2.0], [True])
