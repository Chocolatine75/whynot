"""Static ads get the real screen their concept talks about, cut out of its store poster."""

import json

import pytest
from PIL import Image

from fakes import ScriptedChat
from whynot.assets.screens import Screen, match, pick, prepare

SCREENS = [Screen("s1.png", "ui-s1.png", "main chat list with recent conversations"),
           Screen("s2.png", "ui-s2.png", "group video call with family members"),
           Screen("s3.png", None, "status update with a photo")]


def test_word_matching_and_the_least_used_on_ties():
    assert match("a family video call at bedtime", SCREENS).source == "s2.png"
    used: dict[str, int] = {}
    picked = [match("nothing in common", SCREENS, used).source for _ in range(3)]
    assert picked == ["s1.png", "s2.png", "s3.png"]  # no overlap: spread over the screens
    assert SCREENS[2].asset == "s3.png" and SCREENS[0].asset == "ui-s1.png"
    with pytest.raises(ValueError):
        match("x", [])


def test_the_model_picks_one_screen_per_ad():
    model = ScriptedChat([json.dumps({"picks": {"privacy": 1, "family": 2}})])
    out = pick(model, "App", {"privacy": "only you can read it", "family": "grandma on a call"}, SCREENS)
    assert out == {"privacy": SCREENS[0], "family": SCREENS[1]}
    assert "group video call" in model.prompts()[0] and model.calls[0]["module"] == "screens"


def test_a_wrong_answer_is_repaired_then_word_matching_decides():
    bad = [json.dumps({"picks": {"family": 9}}),  # unknown screen number, missing ad
           json.dumps({"picks": {"family": True, "privacy": 1}})]  # a boolean is not a screen number
    out = pick(ScriptedChat(bad), "App", {"family": "family video call", "privacy": "chat list"}, SCREENS)
    assert out["family"] == SCREENS[1] and out["privacy"] == SCREENS[0]


def test_a_model_that_thinks_without_answering_falls_back_to_words():
    from whynot.models import TruncatedOutput

    class Thinker:
        def chat(self, *a, **kw):
            raise TruncatedOutput("muse-spark-1.3 used all output tokens before answering")

    out = pick(Thinker(), "App", {"family": "family video call", "privacy": "chat list"}, SCREENS)
    assert out == {"family": SCREENS[1], "privacy": SCREENS[0]}


class SamFake:
    """SAM finds a phone in the middle of the probe; counts its calls."""

    def __init__(self, share_box="<|box;x1=100;y1=200;x2=600;y2=1400;w=738;h=1600|>"):
        self.box, self.calls = share_box, 0

    def segment(self, url, concept, *, module):
        from types import SimpleNamespace as NS
        self.calls += 1
        return NS(text=self.box)


def describe(model, app, images):
    from types import SimpleNamespace as NS
    return NS(value=[f"screen {i}" for i in range(1, len(images) + 1)])


def test_prepare_cuts_out_the_interface_once(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    for name, colour in (("a.png", (30, 111, 217)), ("b.png", (217, 111, 30))):  # SAM caches by image
        Image.new("RGB", (1290, 2796), colour).save(assets / name)
    sam = SamFake()
    screens = prepare(sam, assets, "App", ["a.png", "b.png"], sam_cache=tmp_path / "sam", describe=describe)
    assert [s.ui for s in screens] == ["ui-a.png", "ui-b.png"] and sam.calls == 2
    ui = Image.open(assets / "ui-a.png")
    assert ui.size[0] < 1290 and ui.size[1] < 2796  # a crop of the original, never a new picture
    again = prepare(sam, assets, "App", ["a.png", "b.png"], sam_cache=tmp_path / "sam", describe=describe)
    assert again == screens and sam.calls == 2  # cached in screens.json


def test_a_small_phone_is_not_the_screen(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    Image.new("RGB", (1290, 2796)).save(assets / "a.png")
    tiny = SamFake("<|box;x1=10;y1=10;x2=60;y2=60;w=738;h=1600|>")
    screens = prepare(tiny, assets, "App", ["a.png"], sam_cache=tmp_path / "sam", describe=describe)
    assert screens[0].ui is None and screens[0].asset == "a.png"
