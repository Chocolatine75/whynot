"""Viewer answer cache: a view is never paid twice, only valid answers are kept, order matters."""

import json

import pytest

from fakes import FakeChat, FakeOpenAI, make_settings
from test_viewer import PERSONAS, ScriptedClient, item
from whynot.costs import CostLedger
from whynot.models import ModelClient
from whynot.sim.feed import build_market_feeds
from whynot.sim.viewer import Viewer, ViewerCache, ViewerParseError, run_simulation

ITEMS = [item(i, f"ad {i} GOOD" if i % 3 == 0 else f"ad {i}") for i in range(8)]
FEEDS = build_market_feeds(ITEMS, feed_size=4, appearances=2, seed=1)


def simulate(client, cache, draw=0):
    return run_simulation(Viewer(client, cache=cache, draw=draw), PERSONAS, FEEDS, viewers_per_feed=2)


def test_a_second_identical_simulation_costs_nothing(tmp_path):
    cache = ViewerCache(tmp_path / "cache")
    client = ScriptedClient()
    first = simulate(client, cache)
    calls = client.calls
    second = simulate(client, cache)
    assert first.usd > 0 and second.usd == 0
    assert client.calls == calls  # no new model call
    assert first.reactions == second.reactions
    assert cache.hits == calls and cache.size()[0] == calls


def test_a_different_order_or_draw_is_a_different_view(tmp_path):
    cache = ViewerCache(tmp_path / "cache")
    client = ScriptedClient()
    viewer = Viewer(client, cache=cache)
    feed = FEEDS[0]
    viewer.react(PERSONAS[0], feed, feed_id="F0")
    viewer.react(PERSONAS[0], feed, feed_id="F0")
    assert client.calls == 1
    viewer.react(PERSONAS[0], list(reversed(feed)), feed_id="other")  # another order on screen
    assert client.calls == 2
    Viewer(client, cache=cache, draw=1).react(PERSONAS[0], feed, feed_id="F0")  # a fresh, independent answer
    assert client.calls == 3


def test_invalid_answers_are_never_cached(tmp_path):
    cache = ViewerCache(tmp_path / "cache")
    with pytest.raises(ViewerParseError):
        Viewer(ScriptedClient(broken_first=2), cache=cache).react(PERSONAS[0], FEEDS[0], feed_id="F0")
    assert cache.size() == (0, 0)


def test_a_damaged_entry_is_asked_again_and_replaced(tmp_path):
    cache = ViewerCache(tmp_path / "cache")
    client = ScriptedClient()
    Viewer(client, cache=cache).react(PERSONAS[0], FEEDS[0], feed_id="F0")
    entry = next((tmp_path / "cache").glob("*.txt"))
    entry.write_text("{truncated")
    reactions, usd = Viewer(client, cache=cache).react(PERSONAS[0], FEEDS[0], feed_id="F0")
    assert client.calls == 2 and usd > 0 and len(reactions) == 4
    assert json.loads(entry.read_text().strip("`json\n"))["reactions"]


def test_hits_are_logged_at_zero_and_the_model_is_part_of_the_key(tmp_path):
    from dataclasses import replace

    settings = replace(make_settings(tmp_path), viewer_cache_dir=tmp_path / "cache")
    answer = json.dumps({"reactions": [{"ad": f"A{i}", "stopped": True, "understood": True, "believed": True,
                                        "why_not": "", "intent": "yes", "intent_score": 4} for i in range(1, 5)],
                         "preferred": "A1"})
    fake = FakeOpenAI()
    fake.chat = FakeChat(text=answer)
    ledger = CostLedger(tmp_path / "costs.jsonl")
    on_spark = ModelClient(settings, ledger, meta=fake)
    viewer = Viewer(on_spark)  # cache folder taken from the settings
    viewer.react(PERSONAS[0], FEEDS[0], feed_id="F0")
    viewer.react(PERSONAS[0], FEEDS[0], feed_id="F0")
    assert [e.source for e in ledger.events()] == ["api", "cache"] and ledger.events()[1].usd == 0
    on_open = ModelClient(replace(settings, viewer_backend="baseten"), ledger, meta=fake, baseten=fake)
    Viewer(on_open).react(PERSONAS[0], FEEDS[0], feed_id="F0")
    assert len(fake.chat.calls) == 2  # Muse Spark Open's answer is not Muse Spark's


def test_no_cache_folder_means_no_cache(tmp_path):
    client = ScriptedClient()
    assert Viewer(client).cache is None  # the scripted client has no settings
    assert Viewer(ModelClient(make_settings(tmp_path), meta=FakeOpenAI())).cache is None


def test_settings_read_the_cache_and_cassette_variables(monkeypatch, tmp_path):
    from whynot.config import REPO_ROOT, load_settings

    monkeypatch.setenv("WHYNOT_VIEWER_CACHE", "off")
    monkeypatch.setenv("WHYNOT_CASSETTE", "replay  # comment")
    monkeypatch.setenv("WHYNOT_CASSETTE_DIR", str(tmp_path))
    s = load_settings()
    assert s.viewer_cache_dir is None and s.cassette_mode == "replay" and s.cassette_dir == tmp_path
    monkeypatch.setenv("WHYNOT_VIEWER_CACHE", "")
    assert load_settings().viewer_cache_dir == REPO_ROOT / "data" / "cache" / "viewers"
