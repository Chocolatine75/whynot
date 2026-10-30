"""`whynot video` end to end on a fake world: market → deconstruct → archetypes → briefs → scenes → MP4s."""

import base64
import io
import json
from dataclasses import asdict
from datetime import date, timedelta
from types import SimpleNamespace as NS

import imageio_ffmpeg
from PIL import Image

from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agency import video as agency_video
from whynot.agents.strategist import Sources
from whynot.agents.strategist import make_validator as strategy_validator
from whynot.ingest.adlibrary import CompetitorAd, save_jsonl
from whynot.ingest.creatives import CreativeStore, Media, Snapshot

BUILTIN = agency_video.VideoConfig(renderer="builtin")
STRATEGY = strategy_validator(Sources.build(APP, ADS), COUNTRIES)(strategy_json())
TODAY = date(2026, 10, 30)
PITCHES = ["transformation", "transformation", "curiosity", "curiosity", "social_proof", "social_proof"]


def png(color, size=(400, 700)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


class World:
    """A fake Muse (chat + image) that answers by module and records every call."""

    def __init__(self, broken_brief=False):
        self.calls, self.spent_usd, self.broken_brief = [], 0.0, broken_brief

    def chat(self, messages, *, module, model="m", **kw):
        self.calls.append(module)
        self.spent_usd += 0.01
        content = messages[-1]["content"]
        text = content if isinstance(content, str) else content[0]["text"]
        if module == "deconstruct":
            i = int(text.split("Primary text: copy ")[1].split()[0])
            return NS(text=json.dumps({
                "hook": f"Hook {i}", "visual_subject": "a person smiling", "text_overlays": ["Try it"], "cta": "Learn",
                "emotional_pitch": PITCHES[i], "creative_style": "app_screen", "promise": "Speak faster",
                "audience": "Learners"}), cost=NS(usd=0.01))
        if module == "archetypes":
            keys = [line.split(":")[0].strip("- ") + ":app_screen" for line in text.splitlines()
                    if line.startswith("- ") and ":app_screen" in line]
            picks = [{"archetype": k, "persona": "heritage_learner", "angle": "southern_accent", "audience_fit": 8,
                      "message_fit": 8, "production_fit": 9, "why": "Fits."} for k in keys[:3]]
            return NS(text=json.dumps({"picks": picks}), cost=NS(usd=0.01))
        if "screenshots of the app" in text:
            return NS(text=json.dumps({"screens": ["home", "accent picker"]}), cost=NS(usd=0.01))
        first = messages[0]["content"] if isinstance(messages[0]["content"], str) else ""
        if self.broken_brief and "archetype to follow: curiosity" in first:  # every attempt, repairs included
            return NS(text="{}", cost=NS(usd=0.01))
        return NS(text=json.dumps({
            "id": "southern_voice", "hook": "Hear the Southern accent",
            "scenes": [{"kind": "scene", "prompt": "A sunny family kitchen", "overlay": "Sunday dinner",
                        "motion": "zoom_in", "seconds": 3},
                       {"kind": "screen", "screen": 2, "overlay": "Pick Southern", "motion": "pop", "seconds": 4},
                       {"kind": "text", "text": "Listen first", "overlay": "Then speak", "motion": "still",
                        "seconds": 3}],
            "cta": "Start free", "narration": "Hear it, then say it.", "music": "calm"}), cost=NS(usd=0.01))

    def image(self, prompt, *, module, size="auto", **kw):
        self.calls.append(module)
        self.spent_usd += 0.01
        assert "No text" in prompt and "no phones" in prompt  # the scene style always forbids faking the product
        return NS(images_b64=[base64.b64encode(png((120, 80, 40), (1024, 1536))).decode()], cost=NS(usd=0.01))


class Browser:
    def render(self, url):
        return Snapshot([Media("https://scontent.xx.fbcdn.net/x.jpg", 1080, 1080)])


def make_run(tmp_path):
    run = tmp_path / "run"
    (run / "assets").mkdir(parents=True)
    Image.new("RGB", (512, 512), (255, 90, 80)).save(run / "assets" / "icon.png")
    for i, c in enumerate([(30, 120, 220), (20, 200, 120)], 1):
        Image.new("RGB", (645, 1398), c).save(run / "assets" / f"screen_{i}.png")
    app = {"name": APP.name, "description": APP.description, "rating": 4.6, "rating_count": 300}
    (run / "app.json").write_text(json.dumps(app))
    (run / "brand.json").write_text(json.dumps({"palette": ["#F5FAFF", "#0B1D33", "#1E6FD9", "#E6EEF8"],
                                                "screenshots": ["screen_1.png", "screen_2.png"]}))
    (run / "config.json").write_text(json.dumps({"countries": COUNTRIES, "language": "en"}))
    (run / "strategy.json").write_text(json.dumps(asdict(STRATEGY), default=list))
    ads = [CompetitorAd(f"comp{i}", f"page{i % 3}", f"Brand {i % 3}", [f"copy {i}"], [], TODAY - timedelta(days=90),
                        None, [], 1000 * (i + 1), [], None, snapshot_url=f"https://www.facebook.com/ads/?id={i}")
           for i in range(6)]
    save_jsonl(ads, run / "market_ads.jsonl")
    return run


def test_video_pipeline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_video, "CACHE", tmp_path / "cache")
    monkeypatch.setattr("whynot.ingest.creatives.httpx.Client",
                        lambda **kw: NS(get=lambda url: NS(content=png((10, 10, 10)), raise_for_status=lambda: None)))
    run, world = make_run(tmp_path), World()
    report = agency_video.make_videos(run, world, token="EAAtoken", renderer_factory=Browser, say=lambda s: None,
                                      cfg=BUILTIN)
    assert len(report["videos"]) == 3 and not report["failures"].get("videos")
    assert len({v["file"]["path"] for v in report["videos"]}) == 3  # same brief id, three files
    assert {p["archetype"] for p in report["picks"]} == {f"{p}:app_screen" for p in set(PITCHES)}
    for v in report["videos"]:
        mp4 = run / "videos" / v["file"]["path"]
        n, secs = imageio_ffmpeg.count_frames_and_secs(str(mp4))
        assert n == v["file"]["frames"] and 12 <= secs <= 18
    assert CreativeStore(tmp_path / "cache" / "creatives").has("comp0")
    saved = json.loads((run / "videos" / "videos.json").read_text())
    assert saved["usd"] == report["usd"] > 0 and "EAAtoken" not in (run / "videos" / "videos.json").read_text()

    # a second run reuses captures, deconstructions, screen descriptions and scene images
    again = World()
    agency_video.make_videos(run, again, renderer_factory=Browser, say=lambda s: None, cfg=BUILTIN)
    assert "deconstruct" not in again.calls and "scenes" not in again.calls
    assert again.calls.count("brief") == 3  # only the briefs are written again


def test_one_failed_brief_does_not_lose_the_others(tmp_path, monkeypatch):
    monkeypatch.setattr(agency_video, "CACHE", tmp_path / "cache")
    monkeypatch.setattr("whynot.ingest.creatives.httpx.Client",
                        lambda **kw: NS(get=lambda url: NS(content=png((10, 10, 10)), raise_for_status=lambda: None)))
    report = agency_video.make_videos(make_run(tmp_path), World(broken_brief=True), renderer_factory=Browser,
                                      say=lambda s: None, cfg=BUILTIN)
    assert len(report["videos"]) == 2 and list(report["failures"]["videos"]) == ["curiosity:app_screen"]
