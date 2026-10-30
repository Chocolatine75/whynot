"""Competitor ad deconstruction: strict typed answers, repairs, cache by ad id, failures counted."""

import json

import pytest
from PIL import Image

from fakes import ScriptedChat
from test_longevity import ad
from whynot.agents.ask import Invalid
from whynot.agents.deconstruct import (
    PROMPT_VERSION,
    Deconstruction,
    DeconstructionStore,
    deconstruct_all,
    palette,
    validate,
)

GOOD = {"hook": "Speak Vietnamese with your grandma in 10 minutes a day",
        "visual_subject": "Phone showing a chat with a cartoon buffalo tutor",
        "text_overlays": ["Have real conversations", "have REAL conversations", "Learn More"],
        "cta": "Learn More", "emotional_pitch": "transformation", "creative_style": "app_screen",
        "promise": "Real conversations, not phrase lists", "audience": "Heritage learners in the US"}


def image(tmp_path, name="a.jpg", colours=((230, 30, 30), (250, 250, 250))):
    im = Image.new("RGB", (100, 100), colours[0])
    im.paste(colours[1], (0, 0, 100, 30))
    p = tmp_path / name
    im.save(p)
    return p


def test_validate_normalises_and_dedupes_overlays():
    out = validate(GOOD)
    assert out["text_overlays"] == ["Have real conversations", "Learn More"]
    assert out["emotional_pitch"] == "transformation"


@pytest.mark.parametrize("patch, error", [
    ({"emotional_pitch": "nostalgia"}, "emotional_pitch"),
    ({"creative_style": "3d"}, "creative_style"),
    ({"hook": " ".join(["word"] * 16)}, "hook"),
    ({"hook": ""}, "hook"),
    ({"text_overlays": "Learn more"}, "text_overlays"),
    ({"text_overlays": ["a"] * 7}, "text_overlays"),
    ({"cta": 3}, "cta"),
])
def test_validate_refuses_answers_outside_the_schema(patch, error):
    with pytest.raises(Invalid, match=error):
        validate({**GOOD, **patch})


def test_palette_is_measured_from_pixels_most_common_first(tmp_path):
    p = image(tmp_path)
    assert palette(p, 2) == palette(p, 2)  # deterministic
    r, g, b = (int(palette(p, 2)[0][i:i + 2], 16) for i in (1, 3, 5))
    assert r > 200 and g < 60 and b < 60  # red covers 70 % of the image (JPEG shifts it slightly)


def test_deconstruct_all_repairs_caches_and_counts_failed_spend(tmp_path):
    ads = [ad(1, page="Ling"), ad(2, page="Falou"), ad(3, page="Babbel"), ad(4, page="NoImage")]
    images = {"1": (image(tmp_path, "1.jpg"), "static"), "2": (image(tmp_path, "2.jpg"), "video"),
              "3": (image(tmp_path, "3.jpg"), "static")}

    def reply(messages, module):
        text = messages[1]["content"][0]["text"]
        if "Babbel" in text:
            return "not json"
        if "Falou" in text and len(messages) == 2:
            return json.dumps({**GOOD, "creative_style": "anime"})  # repaired on the second try
        return json.dumps(GOOD)

    model = ScriptedChat(reply)
    store = DeconstructionStore(tmp_path / "kb")
    report = deconstruct_all(model, ads, images, store, max_workers=2)
    assert set(report.done) == {"1", "2"} and set(report.failed) == {"3"}
    assert report.done["2"].format == "video" and report.done["1"].palette
    assert report.usd == pytest.approx(0.01 * (1 + 2 + 2))  # failed attempts are still paid for
    assert all(m == "deconstruct" for m in (c["module"] for c in model.calls))
    falou = next(c for c in model.calls if "Falou" in c["messages"][1]["content"][0]["text"])
    assert "first frame" in falou["messages"][1]["content"][0]["text"]  # the model knows it sees a video frame

    again = deconstruct_all(ScriptedChat(lambda m, mod: json.dumps(GOOD)), ads, images, store)
    assert again.cached == 2 and again.usd == pytest.approx(0.01)  # only the failed one is asked again


def test_store_ignores_entries_from_another_prompt_version(tmp_path):
    store = DeconstructionStore(tmp_path)
    d = Deconstruction("9", "X", "static", **validate(GOOD))
    store.put(d)
    assert store.get("9") == d and store.get("9").prompt_version == PROMPT_VERSION
    raw = json.loads((tmp_path / "9.json").read_text())
    raw["prompt_version"] = "deconstruct-v0"
    (tmp_path / "9.json").write_text(json.dumps(raw))
    assert store.get("9") is None
