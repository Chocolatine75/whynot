"""Remotion props: timings, the voice always ends before the end card, honest rating; a real render if Node is here."""

import imageio_ffmpeg
import pytest
from PIL import Image

from whynot.agents.brief import Scene, VideoBrief
from whynot.audio.captions import Word
from whynot.create import remotion
from whynot.create.remotion import FPS, TRANSITION_FRAMES, Audio, build_props, rating_text, scene_frames

PALETTE = ["#FDFAF9", "#261412", "#FF7A6B", "#F7E5E3"]
BRIEF = VideoBrief("t", "a:b", "p", "a", "English", "Your grandma speaks Southern",
                   (Scene("scene", "Sunday dinner", "zoom_in", 3.0, prompt="kitchen"),
                    Scene("screen", "Pick Southern", "pop", 4.0, screen=2),
                    Scene("text", "Then speak", "pop", 3.0, text="Listen first")),
                   "Start free", "She speaks Southern. Your app should too.", "calm", "why")


def props(audio=None, **kw):
    return build_props(BRIEF, palette=PALETTE, app_name="VietBuddy", screens=["s1.png", "s2.png"],
                       scenes={0: "scene_0.jpg"}, icon="icon.png", rating=kw.get("rating", 4.8),
                       rating_count=kw.get("count", 200), audio=audio)


def test_props_follow_the_brief():
    p = props()
    assert [s["durationInFrames"] for s in p["scenes"]] == [90, 120, 90]
    assert p["scenes"][1]["src"] == "s2.png" and p["scenes"][0]["src"] == "scene_0.jpg"
    assert p["durationInFrames"] == 300 + 75 - 3 * TRANSITION_FRAMES
    assert p["voice"] is None and p["music"] is None and p["hook"] == BRIEF.hook
    assert p["endCard"]["rating"] == "Rated 4.8 on the App Store"


def test_a_long_voice_stretches_the_scenes_so_it_ends_before_the_end_card():
    long_voice = [Word("w", i * 0.5, i * 0.5 + 0.4) for i in range(30)]  # ends at 14.9 s
    p = props(Audio(voice_mp3=__file__, words=long_voice, music_mp3=__file__))
    end_card_starts = (p["durationInFrames"] - p["endCard"]["durationInFrames"]) / FPS
    assert end_card_starts >= 14.9 + remotion.VOICE_TAIL_SECONDS - 0.05
    assert p["voice"]["words"][0] == {"text": "w", "start": 0.0, "end": 0.4} and p["music"]["volume"] > 0
    short = scene_frames(BRIEF, 2.0)
    assert short == [90, 120, 90]  # a short voice changes nothing


@pytest.mark.parametrize("rating, count, text", [
    (4.8, 200, "Rated 4.8 on the App Store"), (4.29, 900, "On the App Store"), (5.0, 3, "On the App Store"),
    (None, None, "On the App Store")])
def test_rating_is_shown_only_when_it_helps(rating, count, text):
    assert rating_text(rating, count) == text


def test_a_scene_without_its_image_is_refused():
    with pytest.raises(ValueError, match="scene 1"):
        build_props(BRIEF, palette=PALETTE, app_name="X", screens=["a", "b"], scenes={}, icon=None, rating=None,
                    rating_count=None, audio=None)


@pytest.mark.skipif(not remotion.available(), reason="Remotion not installed (cd video && npm install)")
def test_a_real_remotion_render(tmp_path):
    shot = Image.new("RGB", (645, 1398), (30, 120, 220))
    b = VideoBrief("t", "a:b", "p", "a", "English", "Hook", (Scene("screen", "Pick", "pop", 2.0, screen=1),
                                                             Scene("text", "Go", "pop", 2.0, text="Listen")),
                   "Start", "x", "calm", "why")
    info = remotion.render(b, tmp_path / "ad.mp4", palette=PALETTE, app_name="X", screens=[shot], scenes={},
                           icon=Image.new("RGB", (100, 100), (255, 0, 0)), rating=None, rating_count=None)
    frames, _ = imageio_ffmpeg.count_frames_and_secs(str(tmp_path / "ad.mp4"))
    assert frames == info["frames"] == 4 * FPS + 75 - 2 * TRANSITION_FRAMES
    assert (tmp_path / "ad.poster.jpg").exists() and not list(tmp_path.glob(".public-*"))  # temp files cleaned
