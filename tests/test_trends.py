"""Trend ads: the format library, 'trending now' from the Ad Library, trend shot lists, SAM cut-outs, props."""

import json
from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest
from PIL import Image

from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agents.ask import Invalid
from whynot.agents.deconstruct import Deconstruction, validate
from whynot.agents.director import Context
from whynot.agents.strategist import Sources
from whynot.agents.strategist import make_validator as strategy_validator
from whynot.agents.trend_brief import END_CARD_SECONDS, Proof, Selling, TrendBrief, make_validator, selling_from_app
from whynot.assets.cutouts import MIN_MASCOT_SHARE, cutouts, find, ui_crop
from whynot.create.remotion import FPS, Audio
from whynot.create.trend_render import build_props, shot_frames
from whynot.create.trends import BY_ID, FORMATS, trending
from whynot.ingest.adlibrary import CompetitorAd

STRATEGY = strategy_validator(Sources.build(APP, ADS), COUNTRIES)(strategy_json())
CTX = Context(STRATEGY, APP.name, APP.description, ("Rival Lingo",), ("#F5FAFF", "#0B1D33", "#1E6FD9"), "s.png")
TODAY = date(2026, 10, 30)


def test_the_library_is_well_formed():
    assert len(FORMATS) >= 10 and len(BY_ID) == len(FORMATS)
    for f in FORMATS:
        assert f.beats and f.why and set(f.needs) <= {"text", "screen", "mascot", "photo", "voice"}


def test_deconstruction_accepts_only_known_formats():
    base = {"hook": "h", "visual_subject": "v", "text_overlays": [], "cta": None, "emotional_pitch": "humor",
            "creative_style": "mixed", "promise": "p", "audience": "a"}
    assert validate({**base, "trend_format": "pov"})["trend_format"] == "pov"
    assert validate(base)["trend_format"] == "none"
    with pytest.raises(Invalid, match="trend_format"):
        validate({**base, "trend_format": "dance_challenge"})


def ad(i, page, start_days_ago):
    return CompetitorAd(str(i), page, page, ["x"], [], TODAY - timedelta(days=start_days_ago), None, [], None, [], None)


def dec(i, fmt):
    return Deconstruction(str(i), "x", "static", "h", "v", [], None, "humor", "mixed", "p", "a", trend_format=fmt)


def test_trending_counts_what_competitors_started_recently():
    ads = [ad(1, "A", 3), ad(2, "B", 5), ad(3, "A", 40), ad(4, "C", 2), ad(5, "D", 90), ad(6, "E", 1)]
    decons = {"1": dec(1, "pov"), "2": dec(2, "pov"), "3": dec(3, "pov"), "4": dec(4, "rating"),
              "5": dec(5, "starter_pack"), "6": dec(6, "none")}
    sig = trending(decons, ads, as_of=TODAY)
    assert [s.format for s in sig] == ["pov", "rating", "starter_pack"]  # new ads first; "none" ignored
    pov = sig[0]
    assert (pov.ads, pov.new_ads, pov.advertisers) == (3, 2, 2) and pov.share_new == pytest.approx(2 / 3, abs=1e-3)
    assert sig[2].new_ads == 0


def shot(**kw):
    base = {"visual": "text", "text": "Six tones", "caption": "", "seconds": 1.2, "move": "punch_in",
            "sfx": "whoosh", "beat": "trend"}
    return {**base, **kw}


GOOD = {"id": "tell_me_tones", "hook": "Tell me you're learning Vietnamese",
        "shots": [shot(), shot(visual="photo", prompt="A man frowning at a bowl of pho in a busy street",
                               caption="ordering pho", seconds=1.5),
                  shot(text="Ma ma ma ma", seconds=1.0, move="shake", sfx="pop"),
                  shot(visual="photo", prompt="Grandma laughing at a family dinner", caption="grandma laughing"),
                  shot(text="Wrong tone again", seconds=1.4), shot(visual="photo", prompt="Late night study desk",
                                                                   caption="up way too late again", seconds=1.6),
                  shot(visual="screen", screen=2, focus="middle", caption="hear the Southern voice", beat="twist",
                       seconds=1.8, sfx="ding"),
                  shot(visual="screen", screen=1, focus="top", caption="then say it", beat="twist", seconds=1.6),
                  shot(text="Start free", beat="cta", seconds=1.2, sfx="pop")],
        "voice": "Tell me you're learning Vietnamese without telling me.", "cta": "Start free", "music": "playful"}


def check(data, mascot=False):
    return make_validator(CTX, BY_ID["tell_me_without"], "heritage_learner", "southern_accent", 3,
                          has_mascot=mascot)(data)


def test_a_good_trend_brief():
    b = check(GOOD)
    assert isinstance(b, TrendBrief) and len(b.shots) == 9 and b.format == "tell_me_without"
    assert b.seconds == pytest.approx(sum(s["seconds"] for s in GOOD["shots"]) + END_CARD_SECONDS)
    assert TrendBrief.from_json(json.loads(json.dumps(b.to_json()))) == b


def with_shot(i, **kw):
    d = json.loads(json.dumps(GOOD))
    for j in (i if isinstance(i, tuple) else (i,)):
        d["shots"][j].update(kw)
    return d


@pytest.mark.parametrize("data, error", [
    (with_shot(1, prompt="A man holding a phone with the app"), "phone"),
    (with_shot(1, prompt="A street with a big neon sign"), "sign"),
    (with_shot((6, 7), visual="text", text="Our app"), "twist must show the real app"),
    (with_shot((6, 7), beat="trend"), "twist must show"),
    (with_shot(8, beat="trend"), "never back"),
    (with_shot(0, seconds=3.0), "seconds"),
    (with_shot(0, visual="mascot"), "no mascot"),
    (with_shot(6, screen=9), "screen number"),
    ({**GOOD, "shots": GOOD["shots"][:5]}, "8 to 16"),
    ({**GOOD, "hook": "Speak Vietnamese in 10 minutes", "voice": "ok so this happened"}, "number"),
    ({**GOOD, "voice": "Rival Lingo can't do this."}, "competitor"),
    ({**GOOD, "voice": "Improve your skills with daily lessons."}, "course or an ad"),
    (with_shot(1, caption="master the tones"), "course or an ad"),
    ({**GOOD, "voice": "so i said cà phê [screams] and she kept going"}, "unknown tags"),
    ({**GOOD, "voice": "[laughs] no [sighs] why [gasps] bro [groans]"}, "more than 3"),
])
def test_bad_trend_briefs_are_refused(data, error):
    with pytest.raises(Invalid, match=error):
        check(data)


def test_the_trend_must_be_most_of_the_video():
    d = json.loads(json.dumps(GOOD))
    for s in d["shots"][3:6]:
        s["beat"] = "twist"
    with pytest.raises(Invalid, match="trend is only"):
        check(d)


def test_mascot_shots_are_allowed_when_the_app_has_one():
    assert check(with_shot(0, visual="mascot"), mascot=True).shots[0].visual == "mascot"


def test_props_keep_shot_lengths_and_stretch_for_a_long_voice():
    b = check(GOOD)
    imgs = {i: f"shot_{i}.jpg" for i, s in enumerate(b.shots) if s.visual != "text"}
    p = build_props(b, palette=["#FFFFFF", "#111111", "#FF5500", "#EEEEEE"], app_name="X", images=imgs, icon=None,
                    rating=None, rating_count=None, audio=None, sfx={"whoosh": "sfx_whoosh.mp3"})
    assert [s["durationInFrames"] for s in p["shots"]] == [round(s.seconds * FPS) for s in b.shots]
    assert p["shots"][2]["sfx"] == "none"  # "pop" was not generated here: no dangling sound
    assert p["durationInFrames"] == sum(s["durationInFrames"] for s in p["shots"]) + round(END_CARD_SECONDS * FPS)
    from whynot.audio.captions import Word
    long = Audio(voice_mp3=__file__, words=[Word("w", 0, 20.0)])
    assert sum(shot_frames(b, 20.0)) >= (20.0 + 0.5) * FPS
    p2 = build_props(b, palette=["#FFFFFF", "#111111", "#FF5500", "#EEEEEE"], app_name="X", images=imgs, icon=None,
                     rating=None, rating_count=None, audio=long, sfx={})
    assert p2["voice"]["src"] == "voice.mp3"
    with pytest.raises(ValueError, match="shot 2"):
        build_props(b, palette=["#FFFFFF", "#111111", "#FF5500", "#EEEEEE"], app_name="X", images={}, icon=None,
                    rating=None, rating_count=None, audio=None, sfx={})


class Sam:
    """Fake SAM: answers with boxes in the probe frame, counts calls."""

    def __init__(self, boxes):
        self.boxes, self.calls = boxes, 0

    def segment(self, url, concept, *, module):
        self.calls += 1
        return NS(text="".join(f"<|box;x1={a};y1={b};x2={c};y2={d};w=800;h=1600|>" for a, b, c, d in
                               self.boxes.get(concept, [])))


def test_cutouts_map_sam_boxes_back_to_original_pixels_and_cache_them(tmp_path):
    shot_img = Image.new("RGB", (1600, 3200), (200, 50, 50))  # probed at 800x1600: boxes are doubled back
    sam = Sam({"phone screen": [(100, 300, 700, 1500)], "cartoon mascot": [(0, 1000, 300, 1400), (10, 10, 20, 20)]})
    found = find(sam, shot_img, "phone screen", tmp_path)
    assert found[0].box == (200, 600, 1400, 3000)
    find(sam, shot_img, "phone screen", tmp_path)
    assert sam.calls == 1  # cached
    cut = cutouts(sam, [shot_img], tmp_path)
    assert cut.mascot is not None and cut.mascot.size == (600, 800)  # the big one; the tiny icon is ignored
    assert cut.screens[0].size == ui_crop(shot_img, (200, 600, 1400, 3000)).size
    assert MIN_MASCOT_SHARE > (20 * 20) / (800 * 1600)


def test_ui_crop_keeps_the_app_pixels():
    img = Image.new("RGB", (100, 200))
    for x in range(100):
        for y in range(200):
            img.putpixel((x, y), (x, y % 256, 7))
    crop = ui_crop(img, (10, 20, 90, 180))
    x0, y0 = 10 + round(80 * 0.035), 20 + round(160 * 0.035 * 0.6)
    assert crop.getpixel((0, 0)) == img.getpixel((x0, y0)) and crop.getpixel((5, 9)) == img.getpixel((x0 + 5, y0 + 9))


def test_no_mascot_when_sam_finds_none(tmp_path):
    cut = cutouts(Sam({"phone screen": [(0, 0, 800, 1600)]}), [Image.new("RGB", (800, 1600))], tmp_path)
    assert cut.mascot is None and cut.screens[0].size[0] < 800


def test_trend_dataclass_roundtrip_keeps_optional_fields():
    b = check(GOOD)
    s = replace(b.shots[6], focus="bottom")
    assert s.focus == "bottom" and s.screen == 2


def test_a_masked_mascot_is_cut_out_on_transparency(tmp_path):
    from whynot.assets.cutouts import Found, cut_out
    img = Image.new("RGB", (400, 400), (0, 200, 0))
    mask = Image.new("L", (100, 100), 0)
    mask.paste(255, (25, 25, 75, 75))  # the character is the middle half of its box
    mask.save(tmp_path / "m.png")
    out = cut_out(img, Found((100, 100, 300, 300), 0.25, tmp_path / "m.png"))
    assert out.mode == "RGBA" and all(abs(n - 100) <= 2 for n in out.size)  # trimmed to the character (±edge blur)
    assert out.getpixel((50, 50))[3] == 255
    plain = cut_out(img, Found((100, 100, 300, 300), 0.25, None))
    assert plain.size == (200, 200) and plain.getpixel((0, 0))[3] == 255  # no mask: the box


def test_creator_voice_with_emotion_tags_is_accepted_and_the_meme_line_is_exempt():
    b = check({**GOOD, "voice": "so i said cà phê... [laughs] and she just. kept. talking. i was SO cooked"})
    assert "[laughs]" in b.voice  # kept for the voice model; stripped for the copy checks and the guard
    assert check(GOOD).hook.startswith("Tell me you're learning")  # the trend line itself may say "learning"


def _brief_reply(voice):
    return json.dumps({**GOOD, "voice": voice})


def test_a_teacher_tone_is_sent_back_once_and_the_better_take_is_kept():
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    scores = iter([4, 8])

    def reply(messages, module):
        if module == "tone_critic":
            return json.dumps({"score": next(scores), "why": "sounds like class", "worst": "ok so this happened"})
        return _brief_reply("ok so this happened" if len(messages) == 1 else "bro i was SO cooked [laughs]")

    model = ScriptedChat(reply)
    answer = write(model, CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
                   screens=["a", "b", "c"], has_mascot=False)
    assert "cooked" in answer.value.voice and "4/10 → 8/10" in answer.errors[-1]
    rewrite_prompt = [c for c in model.calls if c["module"] == "trend_brief"][-1]["messages"][-1]["content"]
    assert "rated the tone 4/10" in rewrite_prompt and "ok so this happened" in rewrite_prompt


def test_a_worse_rewrite_is_not_kept():
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    scores = iter([6, 3])
    model = ScriptedChat(lambda m, mod: json.dumps({"score": next(scores), "why": "x", "worst": "y"})
                         if mod == "tone_critic" else _brief_reply("first take" if len(m) == 1 else "second take"))
    answer = write(model, CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
                   screens=["a", "b", "c"], has_mascot=False)
    assert answer.value.voice == "first take" and "kept 6/10" in answer.errors[-1]


def test_a_good_tone_is_not_rewritten():
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    model = ScriptedChat(lambda m, mod: json.dumps({"score": 9, "why": "x", "worst": "y"}) if mod == "tone_critic"
                         else _brief_reply("no because why did she keep talking"))
    write(model, CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
          screens=["a", "b", "c"], has_mascot=False)
    assert [c["module"] for c in model.calls] == ["trend_brief", "tone_critic"]


DIALOGUE = [{"speaker": "me", "text": "so i walk up and go... cà phê sữa đá?"},
            {"speaker": "them", "language": "vi", "gender": "female", "accent": "south",
             "text": "Dạ, em uống ở đây hay mang về?"},
            {"speaker": "me", "text": "[laughs] bro i was SO cooked"}]


def test_dialogue_lines_are_typed_with_language_and_accent():
    b = check({**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": DIALOGUE})
    assert [(x.speaker, x.language, x.accent) for x in b.lines] == [("me", "en", None), ("them", "vi", "south"),
                                                                     ("me", "en", None)]
    assert "mang về" in b.voice
    assert TrendBrief.from_json(json.loads(json.dumps(b.to_json()))).lines == b.lines
    legacy = check(GOOD)  # a plain "voice" is one line by the creator
    assert legacy.lines[0].speaker == "me" and legacy.lines[0].text == GOOD["voice"]


@pytest.mark.parametrize("patch, error", [
    ({"text": "Da, em uong o day hay mang ve?"}, "accents and tone marks"),
    ({"language": "ja"}, "no native voice"),
    ({"accent": "central"}, "accent must be"),
    ({"gender": "robot"}, "gender"),
    ({"speaker": "narrator"}, "speaker"),
])
def test_bad_dialogue_lines_are_refused(patch, error):
    lines = json.loads(json.dumps(DIALOGUE))
    lines[1].update(patch)
    with pytest.raises(Invalid, match=error):
        check({**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": lines})


def test_the_creator_may_try_the_other_language_in_its_own_line_with_accents():
    lines = json.loads(json.dumps(DIALOGUE))
    lines[0] = {"speaker": "me", "language": "vi", "text": "cà phê sữa đá?"}
    b = check({**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": lines})
    assert (b.lines[0].speaker, b.lines[0].language) == ("me", "vi")
    lines[0]["text"] = "ca phe sua da?"
    with pytest.raises(Invalid, match="accents and tone marks"):
        check({**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": lines})


def test_teacher_words_are_checked_only_in_the_creator_lines():
    lines = json.loads(json.dumps(DIALOGUE))
    lines[2]["text"] = "time to practise again"
    with pytest.raises(Invalid, match="course or an ad"):
        check({**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": lines})


def test_casting_picks_native_voices_by_language_accent_and_gender():
    from whynot.audio.voices import CREATOR, NATIVE, cast
    assert cast("me", "en", "en").voice_id == CREATOR["male"]
    assert cast("them", "vi", "en", gender="female", accent="south").voice_id == NATIVE["vi"]["south"]["female"]
    assert cast("them", "vi", "en", gender="male", accent="north").native is True
    assert cast("them", "vi", "en", accent="moon").voice_id in {v for a in NATIVE["vi"].values() for v in a.values()}
    assert cast("them", "en", "en", gender="male").voice_id == CREATOR["female"]  # never the creator's own voice
    with pytest.raises(ValueError, match="no native voice"):
        cast("them", "ja", "en")


def test_harsh_sound_effects_are_not_offered():
    from whynot.agents.trend_brief import SFX
    from whynot.audio.elevenlabs import SFX_PROMPTS
    assert "record_scratch" not in SFX and "bass_drop" not in SFX
    assert set(SFX) - {"none"} == set(SFX_PROMPTS)  # every effect a brief can ask for can be generated
    with pytest.raises(Invalid, match="sfx"):
        check(with_shot(2, sfx="record_scratch"))


def test_a_failed_run_never_overwrites_the_last_good_scripts(tmp_path):
    """Regression: a re-render that failed wrote an empty trends.json over the scripts Matteo had just watched."""
    from whynot.agency.trend_video import save_report
    good = {"videos": [{"brief": {"id": "a"}}]}
    save_report(tmp_path, good)
    assert save_report(tmp_path, {"videos": []}).name == "trends-failed.json"
    assert json.loads((tmp_path / "trends.json").read_text()) == good
    newer = {"videos": [{"brief": {"id": "b"}}]}
    save_report(tmp_path, newer)
    archived = [p for p in tmp_path.glob("trends-*.json") if p.name != "trends-failed.json"]
    assert json.loads((tmp_path / "trends.json").read_text()) == newer
    assert len(archived) == 1 and json.loads(archived[0].read_text()) == good


# --- E14-8: it must sell (demo, proof, payoff, offer, the app named) ---------------------------


REVIEW = Proof("r1", 5, "I think this app is very promising and I especially like how you can choose "
                        "southern Vietnamese.")
SELL = Selling("LinguaApp", (REVIEW,), ("Free to download",))


def selling_brief():
    d = json.loads(json.dumps({**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": DIALOGUE}))
    d["lines"][2]["text"] = "anyway linguaapp has a southern voice [laughs]"
    d["shots"] = [
        shot(seconds=1.8), shot(text="Ma ma ma", seconds=1.4),
        shot(visual="photo", prompt="A busy cafe counter", caption="me at the counter", seconds=1.6),
        shot(text="six tones bro", seconds=1.4),
        shot(visual="screen", screen=1, beat="twist", caption="wait", seconds=1.2),
        shot(visual="screen", screen=2, focus="middle", tap=True, beat="demo", caption="pick southern", seconds=1.8),
        shot(visual="screen", screen=3, focus="top", beat="demo", caption="hear it first", seconds=2.0),
        shot(visual="review", review="r1", quote="I especially like how you can choose southern Vietnamese",
             beat="proof", caption="", seconds=1.6),
        shot(visual="photo", prompt="Grandma laughing at the dinner table", beat="payoff", caption="she laughed",
             seconds=1.4),
        shot(text="Start free", beat="cta", seconds=1.0)]
    d["offer"] = "Free to download"
    return d


def check_selling(data):
    return make_validator(CTX, BY_ID["tell_me_without"], "heritage_learner", "southern_accent", 3,
                          has_mascot=False, selling=SELL)(data)


def test_a_brief_that_sells():
    b = check_selling(selling_brief())
    assert b.offer == "Free to download"
    proof = next(s for s in b.shots if s.visual == "review")
    assert proof.stars == 5 and proof.quote.startswith("I especially like")
    assert any(s.tap for s in b.shots if s.beat == "demo")


def sell_patch(fn):
    d = selling_brief()
    fn(d)
    return d


@pytest.mark.parametrize("data, error", [
    (sell_patch(lambda d: d["shots"][7].update(quote="the best Vietnamese app ever made")), "word for word"),
    (sell_patch(lambda d: d["shots"][7].update(review="r9")), "verified review ids"),
    (sell_patch(lambda d: d["shots"].pop(6)), "app in action"),
    (sell_patch(lambda d: d["shots"][5].update(tap=False)), "tap"),
    (sell_patch(lambda d: d["shots"].pop(7)), "proof"),
    (sell_patch(lambda d: d["shots"][8].update(beat="proof")), "transformation"),
    (sell_patch(lambda d: d["lines"][2].update(text="anyway this app has a southern voice")), "app's name"),
    (sell_patch(lambda d: d.update(offer="50% off today")), "offer"),
    (sell_patch(lambda d: d["shots"][8].update(beat="demo")), "never back"),
])
def test_briefs_that_dont_sell_are_refused(data, error):
    with pytest.raises(Invalid, match=error):
        check_selling(data)


def test_selling_facts_come_from_the_store_page_only():
    app = {"price": 0.0, "description": "Learn. Start your free trial today.",
           "reviews": [{"id": "a", "rating": 5, "text": "Love  it"}, {"id": "b", "rating": 2, "text": "bad"},
                       {"id": "c", "rating": 4, "text": ""}]}
    s = selling_from_app(app, "X")
    assert [r.id for r in s.reviews] == ["a"] and s.reviews[0].text == "Love it"  # ≥ 4 stars with text only
    assert s.offers == ("Free to download", "Free trial")
    assert selling_from_app({"price": 4.99, "description": "", "reviews": []}, "X").offers == ()


def test_shouting_in_captions_and_cards_is_calmed_not_refused():
    """Regression: a brief failed 4 times because the model kept writing 'THIS or THAT' on cards."""
    d = with_shot(0, text="THIS or THAT", caption="SOUTHERN or NORTHERN")
    b = check({**d, "hook": "Tell me you're learning Vietnamese FR"})
    assert b.shots[0].text == "this or that" and b.shots[0].caption == "southern or northern"
    assert b.hook.endswith("fr")


@pytest.mark.parametrize("patch", [lambda d: d["shots"][9].update(caption="link in bio lol"),
                                   lambda d: d.update(cta="follow for more")])
def test_creator_habits_that_make_no_sense_in_an_ad_are_refused(patch):
    with pytest.raises(Invalid, match="makes no sense in an ad"):
        check_selling(sell_patch(patch))


@pytest.mark.parametrize("text", ["so i said ca phe sua da and she laughed", "khong. just khong.",
                                  "Xin Chao grandma"])
def test_vietnamese_words_without_accents_are_refused_in_english_lines(text):
    # Seen on a real run: English captions showed "ca phe sua" (the prompt's own example had no accents).
    with pytest.raises(Invalid, match="keep their accents"):
        check({**GOOD, "voice": text})


def test_the_refusal_names_the_correct_spelling():
    with pytest.raises(Invalid, match="'cà phê' not 'ca phe'"):
        check({**GOOD, "voice": "so i said ca phe and she laughed"})


@pytest.mark.parametrize("text", ["so i said cà phê sữa đá and she laughed", "the barista said something",
                                  "i was in a cafe", "a phone call", "she said no"])
def test_accented_vietnamese_and_plain_english_pass(text):
    check({**GOOD, "voice": text})


def test_unaccented_vietnamese_finds_every_phrase():
    from whynot.agents.trend_brief import unaccented_vietnamese

    assert unaccented_vietnamese("Ca Phe and bao nhieu?") == [("Ca Phe", "cà phê"), ("bao nhieu", "bao nhiêu")]
    assert unaccented_vietnamese("cà phê, bao nhiêu?") == []
