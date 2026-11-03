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
        "voice": "Tell me you're learning Vietnamese without telling me.", "cta": "Start free", "music": "playful",
        "cast": "Minh, 23, hoodie and glasses, and his grandma, 75, at a family dinner in a small warm kitchen"}


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


def test_long_shots_become_reframes_never_a_frozen_picture():
    from whynot.create.trend_render import recut, split_frames
    assert split_frames(75, 30) == [25, 25, 25] and split_frames(30, 30) == [30] and sum(split_frames(91, 30)) == 91
    shots = [{"visual": "photo", "durationInFrames": 90, "move": "punch_in", "sfx": "whoosh"},
             {"visual": "screen", "durationInFrames": 60, "ui": "rows", "sfx": "none", "tap": True},
             {"visual": "screen", "durationInFrames": 90, "ui": "grid", "sfx": "pop"},
             {"visual": "review", "durationInFrames": 75, "sfx": "none"}]
    out = recut(shots, max_frames=30)
    photo = [s for s in out if s["visual"] == "photo"]
    assert [s["move"] for s in photo] == ["punch_in", "close", "pan"] and all(s.get("hook") for s in photo)
    assert [s["sfx"] for s in photo] == ["whoosh", "none", "none"]  # one sound per story cut, not per reframe
    app = [s for s in out if s.get("ui") in ("rows", "zoom")]
    assert [s["ui"] for s in app] == ["rows", "zoom"] and "tap" not in app[1]
    assert sum(1 for s in out if s.get("ui") == "grid") == 1 and sum(1 for s in out if s["visual"] == "review") == 1


def test_the_mascot_gets_one_beat_its_time_goes_to_the_next_shot():
    from whynot.create.trend_render import recut
    out = recut([{"visual": "mascot", "durationInFrames": 75, "move": "pop", "sfx": "pop"},
                 {"visual": "screen", "durationInFrames": 30, "ui": "float", "sfx": "none"}], max_frames=30)
    assert [s["visual"] for s in out].count("mascot") == 1 and out[0]["durationInFrames"] == 30
    assert sum(s["durationInFrames"] for s in out) == 105  # no time lost: the app shot got the rest


def test_props_keep_shot_lengths_and_stretch_for_a_long_voice():
    b = check(GOOD)
    imgs = {i: f"shot_{i}.jpg" for i, s in enumerate(b.shots) if s.visual != "text"}
    p = build_props(b, palette=["#FFFFFF", "#111111", "#FF5500", "#EEEEEE"], app_name="X", images=imgs, icon=None,
                    rating=None, rating_count=None, audio=None, sfx={"whoosh": "sfx_whoosh.mp3"})
    # the story keeps its length (a closing cta card hands its extra time to the end card); long shots are cut
    # into reframes of at most MAX_SHOT_SECONDS
    assert (sum(s["durationInFrames"] for s in p["shots"]) + p["endCard"]["durationInFrames"]
            == sum(shot_frames(b)) + round(END_CARD_SECONDS * FPS))
    if b.shots[-1].visual == "text" and b.shots[-1].beat == "cta":
        assert p["shots"][-1]["durationInFrames"] <= round(0.7 * FPS)
    assert max(s["durationInFrames"] for s in p["shots"] if s["visual"] not in ("text", "review")) <= FPS
    assert all(s["sfx"] != "pop" for s in p["shots"])  # "pop" was not generated here: no dangling sound
    assert p["durationInFrames"] == sum(s["durationInFrames"] for s in p["shots"]) + p["endCard"]["durationInFrames"]
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
    b = check({**GOOD, "voice": "so i said cà phê... [laughs] and she just. kept. going. i was SO done"})
    assert "[laughs]" in b.voice  # kept for the voice model; stripped for the copy checks and the guard
    assert check(GOOD).hook.startswith("Tell me you're learning")  # the trend line itself may say "learning"


def verdict(n, why="x", worst="y"):
    """The viewer critic's answer, the same mark for tone, clarity and hook."""
    return json.dumps({"tone": n, "clarity": n, "hook": n, "story": "s", "why": why, "worst": worst})


def _brief_reply(voice):
    return json.dumps({**GOOD, "voice": voice})


def test_a_teacher_tone_is_sent_back_once_and_the_better_take_is_kept():
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    scores = iter([4, 8])

    def reply(messages, module):
        if module == "tone_critic":
            return verdict(next(scores), "sounds like class", "ok so this happened")
        return _brief_reply("ok so this happened" if len(messages) == 1 else "bro i was SO done [laughs]")

    model = ScriptedChat(reply)
    answer = write(model, CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
                   screens=["a", "b", "c"], has_mascot=False)
    assert "SO done" in answer.value.voice and "4/10 → 8/10" in answer.errors[-1]
    rewrite_prompt = [c for c in model.calls if c["module"] == "trend_brief"][-1]["messages"][-1]["content"]
    assert "tone 4/10, story clarity 4/10" in rewrite_prompt and "ok so this happened" in rewrite_prompt


def test_a_worse_rewrite_is_not_kept():
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    scores = iter([6, 3])
    model = ScriptedChat(lambda m, mod: verdict(next(scores), "x", "y")
                         if mod == "tone_critic" else _brief_reply("first take" if len(m) == 1 else "second take"))
    answer = write(model, CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
                   screens=["a", "b", "c"], has_mascot=False)
    assert answer.value.voice == "first take" and "kept 6/10" in answer.errors[-1]


def test_an_invalid_rewrite_keeps_the_valid_first_take():
    """Seen on VietBuddy (Nov 2): the first brief was valid, the tone rewrite broke a rule 3 times, and the whole
    idea was thrown away."""
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    def reply(m, mod):
        if mod == "tone_critic":
            return verdict(4, "x", "y")
        return _brief_reply("first take") if len(m) == 1 else json.dumps({**GOOD, "music": "jazz"})

    answer = write(ScriptedChat(reply), CTX, BY_ID["tell_me_without"], persona="heritage_learner",
                   angle="southern_accent", screens=["a", "b", "c"], has_mascot=False)
    assert answer.value.voice == "first take" and "first take kept" in answer.errors[-1]


def test_a_good_tone_is_not_rewritten():
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    model = ScriptedChat(lambda m, mod: verdict(9, "x", "y") if mod == "tone_critic"
                         else _brief_reply("why did she keep going like that"))
    write(model, CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
          screens=["a", "b", "c"], has_mascot=False)
    assert [c["module"] for c in model.calls] == ["trend_brief", "tone_critic"]


DIALOGUE = [{"speaker": "me", "text": "so i walk up and go... cà phê sữa đá?", "shots": [1, 2, 3]},
            {"speaker": "them", "language": "vi", "gender": "female", "accent": "south",
             "text": "Dạ, em uống ở đây hay mang về?", "shots": [4, 5, 6]},
            {"speaker": "me", "text": "[laughs] bro i was SO done", "shots": [7, 8]},
            {"speaker": "narrator", "text": "start free", "shots": [9]}]  # the spoken call to action


def test_dialogue_lines_are_typed_with_language_and_accent():
    b = check({**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": DIALOGUE})
    assert [(x.speaker, x.language, x.accent) for x in b.lines] == [("me", "en", None), ("them", "vi", "south"),
                                                                     ("me", "en", None), ("narrator", "en", None)]
    assert "mang về" in b.voice
    assert TrendBrief.from_json(json.loads(json.dumps(b.to_json()))).lines == b.lines
    legacy = check(GOOD)  # a plain "voice" is one line by the creator
    assert legacy.lines[0].speaker == "me" and legacy.lines[0].text == GOOD["voice"]


@pytest.mark.parametrize("patch, error", [
    ({"text": "Da, em uong o day hay mang ve?"}, "accents and tone marks"),
    ({"language": "ja"}, "spoken in en only"),  # the app is about Vietnamese, not Japanese
    ({"accent": "central"}, "accent must be"),
    ({"gender": "robot"}, "gender"),
    ({"speaker": "robot"}, "speaker"),
    ({"speaker": "narrator"}, "the narrator is the brand"),  # a Vietnamese line can't be the brand's
])
def test_bad_dialogue_lines_are_refused(patch, error):
    lines = json.loads(json.dumps(DIALOGUE))
    lines[1].update(patch)
    with pytest.raises(Invalid, match=error):
        check({**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": lines})


def test_the_creator_may_try_the_other_language_in_its_own_line_with_accents():
    lines = json.loads(json.dumps(DIALOGUE))
    lines[0] = {"speaker": "me", "language": "vi", "text": "cà phê sữa đá?", "shots": [1, 2, 3]}
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
    d["lines"][2]["text"] = "and i just stood there [laughs]"
    d["shots"] = [
        shot(seconds=1.8), shot(text="Ma ma ma", seconds=1.4),
        shot(visual="photo", prompt="A busy cafe counter", caption="me at the counter", seconds=1.6),
        shot(text="six tones bro", seconds=1.4),
        shot(visual="screen", screen=1, beat="twist", caption="wait", seconds=1.2),
        shot(visual="screen", screen=2, focus="middle", tap=True, beat="demo", caption="linguaapp has a southern voice",
             seconds=1.8),
        shot(visual="screen", screen=3, focus="top", beat="demo", caption="hear it first", seconds=2.0),
        shot(visual="review", review="r1", quote="I especially like how you can choose southern Vietnamese",
             beat="proof", caption="", seconds=1.6),
        shot(visual="photo", prompt="Grandma laughing at the dinner table", beat="payoff", caption="she laughed",
             seconds=1.4),
        shot(text="Start free", beat="cta", seconds=1.0)]
    d["offer"] = "Free to download"
    # the storyboard: the creator over the story, the people of the story over theirs, the narrator over the app
    for line, span in zip(d["lines"][:3], ([1, 2], [3, 4], [5]), strict=True):
        line["shots"] = span
    d["lines"][3] = {"speaker": "narrator", "text": "linguaapp has a southern voice, free to download",
                     "shots": [6, 7, 8, 9, 10]}
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
    (sell_patch(lambda d: d["shots"][5].update(caption="pick southern")), "ON SCREEN"),
    (sell_patch(lambda d: d.update(offer="50% off today")), "offer"),
    (sell_patch(lambda d: d["shots"][8].update(beat="demo")), "never back"),
])
def test_briefs_that_dont_sell_are_refused(data, error):
    with pytest.raises(Invalid, match=error):
        check_selling(data)


def test_selling_facts_come_from_the_store_page_only():
    app = {"price": 0.0, "description": "Learn. Start your free trial today.",
           "reviews": [{"id": "a", "rating": 5, "text": "Love  it, my whole family uses it every single week"},
                       {"id": "b", "rating": 2, "text": "bad"}, {"id": "c", "rating": 4, "text": ""},
                       {"id": "d", "rating": 5, "text": "Very good encrypted"}]}  # too short to prove anything
    s = selling_from_app(app, "X")
    assert [r.id for r in s.reviews] == ["a"]  # ≥ 4 stars and a real sentence only
    assert s.reviews[0].text == "Love it, my whole family uses it every single week"
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


# --- honesty: no testimonial from an invented person ------------------------------------------


@pytest.mark.parametrize("line", [
    # seen on the first real `whynot agency` run (VietBuddy, Oct 31)
    "my buffalo kept yelling so i tapped it slow in LinguaApp till i heard it",
    "cousin sent me LinguaApp so i could hear her way first",
    # the old prompt's own example
    "anyway this app has a southern voice and it's actually the only reason grandma understands me now",
    "i've been using it every morning",
    "i finally downloaded it",
    "i got the yearly plan",
    "it lowkey changed my life",
    "now she thinks i am cute or whatever",
    "now my mom says i sound southern",
])
def test_the_creator_never_vouches_for_the_app(line):
    d = selling_brief()
    d["lines"][2]["text"] = line
    with pytest.raises(Invalid, match=r"skit character|testimonial"):
        check_selling(d)


@pytest.mark.parametrize("caption", ["now grandma understands me", "i've been using it daily", "thanks to it"])
def test_result_claims_are_refused_on_screen_too(caption):
    with pytest.raises(Invalid, match="testimonial"):
        check_selling(sell_patch(lambda d: d["shots"][8].update(caption=caption)))


@pytest.mark.parametrize("line", ["so i said cà phê and she just kept going", "i was so done",
                                  "i got roasted by my own mom", "she called me out at dinner",
                                  "my cousin uses slang i don't get"])
def test_the_skit_itself_is_free(line):
    d = selling_brief()
    d["lines"][2]["text"] = line
    assert check_selling(d).lines[2].text == line


def test_the_prompt_asks_for_a_skit_and_the_brand_on_screen():
    from whynot.agents.trend_brief import SELLING, TONE

    assert "skit" in TONE and "NOT a customer" in TONE and "only reason grandma" not in TONE
    assert "once on screen" in SELLING and "never as a result" in SELLING


def test_a_short_trend_gets_a_repair_saying_how_much_to_add():
    """Seen on VietBuddy: two briefs failed 4 times on 'the trend is only 4.3 s of 13.5 s'."""
    d = selling_brief()
    for s in d["shots"]:
        if s["beat"] == "trend":
            s["seconds"] = 0.6  # 2.4 s of trend in 11.4 s
    with pytest.raises(Invalid, match=r"Add \d+\.\d s of 'trend' shots at the start .*more trend shot"):
        check_selling(d)


def test_every_rule_problem_comes_back_in_one_message():
    """Seen on VietBuddy (Nov 1): 3 of 4 ideas failed after 4 attempts, each fixing one rule and hitting the next."""
    d = selling_brief()
    d["shots"][4]["visual"] = "photo"  # no screen in the twist
    d["shots"][4]["prompt"] = "A cafe table"
    d["shots"][9]["text"] = "3 tones free"  # an unverified number
    d["offer"] = "50% off"  # an offer the store does not support
    with pytest.raises(Invalid) as exc:
        check_selling(d)
    msg = str(exc.value)
    assert msg.startswith("3 problems, fix them all in one go (timeline now: trend")
    assert "twist must show the real app" in msg and "'3'" in msg and "'offer' must be one of" in msg
    assert '"visual": "screen"' in msg  # says how to fix it, not only what is wrong


def test_a_short_demo_says_how_many_seconds_to_add():
    d = selling_brief()
    d["shots"][5]["seconds"] = 0.6
    d["shots"][6]["seconds"] = 0.6
    with pytest.raises(Invalid, match=r"add \d+\.\d s of demo"):
        check_selling(d)


@pytest.mark.parametrize("line", ["and she just. kept. talking.", "i was SO cooked", "the way i just nodded",
                                  "no because why"])
def test_the_prompts_own_examples_are_refused(line):
    """All four VietBuddy videos of Nov 1 reused the prompt's examples word for word."""
    d = selling_brief()
    d["lines"][2]["text"] = line
    with pytest.raises(Invalid, match="reuse the prompt's examples"):
        check_selling(d)


def test_a_line_said_in_an_earlier_ad_is_refused():
    d = selling_brief()
    d["lines"][2]["text"] = "and i stood there like a statue"
    old = ("pov airport chaos", "so i landed and stood there like a statue for an hour")
    with pytest.raises(Invalid, match="already said in the ad"):
        make_validator(CTX, BY_ID["tell_me_without"], "heritage_learner", "southern_accent", 3, has_mascot=False,
                       selling=SELL, avoid=[old])(d)
    assert check_selling(d).lines[2].text == "and i stood there like a statue"  # fine without that earlier ad


@pytest.mark.parametrize("caption", ["get told instantly", "perfect accent in a week", "be fluent by summer"])
def test_unbacked_promises_on_screen_are_refused(caption):
    """Seen on VietBuddy: a caption promised instant feedback; the store page doesn't (reviews say it is slow)."""
    with pytest.raises(Invalid, match="neither the store page nor a verified claim"):
        check_selling(sell_patch(lambda d: d["shots"][6].update(caption=caption)))


def test_the_creator_may_use_promise_words_in_the_story():
    d = selling_brief()
    d["lines"][2]["text"] = "i froze instantly lol"
    assert check_selling(d).lines[2].text == "i froze instantly lol"


@pytest.mark.parametrize("beat_index, field, words", [(6, "caption", "southern voice so i actually get it"),
                                                       (8, "caption", "for next time im not frozen"),
                                                       (9, "text", "my turn now")])
def test_captions_from_the_demo_on_speak_for_the_brand(beat_index, field, words):
    """Seen on VietBuddy (Nov 1): testimonials moved from the voice to the captions ("so i actually get it")."""
    with pytest.raises(Invalid, match="speak for the brand"):
        check_selling(sell_patch(lambda d: d["shots"][beat_index].update({field: words})))


@pytest.mark.parametrize("caption", ["link up top if u need it", "link right here btw", "links below"])
def test_any_link_line_makes_no_sense_in_an_ad(caption):
    with pytest.raises(Invalid, match="makes no sense in an ad"):
        check_selling(sell_patch(lambda d: d["shots"][6].update(caption=caption)))


def test_a_sticker_inside_the_screen_is_not_the_mascot(tmp_path):
    # WhatsApp (Nov 2): a bear sticker in a chat was taken for the app's mascot and starred in every video
    shot_img = Image.new("RGB", (1600, 3200), (200, 50, 50))
    sam = Sam({"phone screen": [(100, 300, 700, 1500)], "cartoon mascot": [(300, 800, 500, 1000)],
               "cartoon character": [], "cartoon animal": []})
    assert cutouts(sam, [shot_img], tmp_path).mascot is None


def test_a_video_nobody_understands_is_rewritten_even_if_funny():
    """The weakest of tone, clarity and hook decides (Nov 2: "grandma said five mins", nobody got the story)."""
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    confused = json.dumps({"tone": 9, "clarity": 3, "hook": 8, "story": "something about grandma?",
                           "why": "I could not tell what happens", "worst": "grandma said five mins"})
    replies = iter([confused, verdict(8)])
    model = ScriptedChat(lambda m, mod: next(replies) if mod == "tone_critic"
                         else _brief_reply("first take" if len(m) == 1 else "second take"))
    write(model, CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
          screens=["a", "b", "c"], has_mascot=False)
    rewrite = model.calls[2]["messages"][-1]["content"]
    assert "story clarity 3/10" in rewrite and "something about grandma?" in rewrite


def test_tones_are_known():
    from fakes import ScriptedChat
    from whynot.agents.trend_brief import write

    with pytest.raises(ValueError, match="tone"):
        write(ScriptedChat([]), CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
              screens=["a"], has_mascot=False, tone="dramatic")


def test_a_preview_can_never_spend():
    import pytest as _pytest

    from whynot.agency.trend_video import NoModel, offline_voice
    with _pytest.raises(RuntimeError, match="no model call"):
        NoModel().image("a photo")
    with _pytest.raises(RuntimeError, match="no model call"):
        NoModel().transcribe(b"")
    assert NoModel().spent_usd == 0.0
    import tempfile
    from pathlib import Path as _P

    from whynot.agency import trend_video
    with tempfile.TemporaryDirectory() as d:
        old = trend_video.CACHE
        trend_video.CACHE = _P(d)
        try:
            v = offline_voice(_P(d) / "audio")
            with _pytest.raises(Exception, match="not in the audio cache"):
                v.sfx("whoosh")  # not cached: refused, never generated
        finally:
            trend_video.CACHE = old


def test_every_photo_after_the_first_is_made_from_it_and_at_most_three_are_made():
    from whynot.agency.trend_video import MAX_PHOTOS, story_photos
    b = check(GOOD)
    shots = [replace(s, visual="photo", prompt=f"moment {i}") if i < 6 else s for i, s in enumerate(b.shots)]
    b = replace(b, shots=tuple(shots))
    calls = []

    def photo(prompt, reference=None):
        calls.append((prompt, reference))
        return Image.new("RGB", (10, 10), (len(calls) * 30, 0, 0))

    imgs = story_photos(b, photo)
    assert len(calls) == MAX_PHOTOS == 3 and calls[0][1] is None
    assert all(ref is imgs[0] for _, ref in calls[1:])  # the same people: every later photo from the first
    assert imgs[3] is imgs[4] is imgs[5] is imgs[2]  # past the limit, the last photo again (reframed)


def test_a_photo_with_a_reference_is_an_edit_cached_apart(tmp_path):
    from whynot.agency.video import scene_image

    class Model:
        def __init__(self):
            self.made, self.edits = 0, []

        def _png(self):
            import base64
            buf = __import__("io").BytesIO()
            Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, "PNG")
            return NS(images_b64=[base64.b64encode(buf.getvalue()).decode()])

        def image(self, prompt, *, module, size):
            self.made += 1
            return self._png()

        def edit_image(self, prompt, refs, *, module, size):
            self.edits.append((prompt, len(refs)))
            return self._png()

    m = Model()
    first = scene_image(m, "she panics in the taxi", tmp_path)
    scene_image(m, "she laughs in the taxi", tmp_path, reference=first)
    scene_image(m, "she laughs in the taxi", tmp_path, reference=first)  # cached: no second edit
    assert m.made == 1 and len(m.edits) == 1 and "same people" in m.edits[0][0] and m.edits[0][1] == 1


def test_an_eight_word_text_card_is_not_held_to_a_static_proof_line_length():
    data = json.loads(json.dumps(GOOD))
    card = next(s for s in data["shots"] if s["visual"] == "text")
    card["text"] = "Southern voices sounding exactly like your whole family"  # 8 words, 50+ characters
    assert len(card["text"]) > 50
    b = check(data)
    assert any(s.text == card["text"] for s in b.shots)
