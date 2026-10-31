"""Video renderer: deterministic, right length and size, real product pixels, honest end card."""

import hashlib

import imageio_ffmpeg
import pytest
from PIL import Image

from whynot.agents.brief import END_CARD_SECONDS, Scene, VideoBrief
from whynot.create.composer import prepare_product
from whynot.create.video import CARD_W, FPS, Assets, EndCard, H, Look, W, frames, render, screen_layer


def screenshot(color=(30, 120, 220)):
    im = Image.new("RGB", (1290, 2796), color)
    for y in range(0, 2796, 97):  # stripes, so a moved or redrawn pixel would show
        im.paste((250, 250, 250), (0, y, 1290, y + 9))
    return im


LOOK = Look.from_palette(["#FDFAF9", "#261412", "#FF7A6B", "#F7E5E3"], "VietBuddy",
                         icon=Image.new("RGB", (512, 512), (255, 90, 80)), rating=4.8, rating_count=120)


def brief(*scenes, cta="Start free"):
    return VideoBrief("t", "a:b", "p", "a", "English", "Your grandma speaks Southern", tuple(scenes), cta,
                      "She speaks Southern.", "calm", "why")


SCREEN = Scene("screen", "Pick the Southern voice", "zoom_in", 2.0, screen=1)
TEXT = Scene("text", "Listen first", "pop", 2.0, text="Understand her, finally")
PHOTO = Scene("scene", "Family dinner", "pan", 2.0, prompt="kitchen")


def test_every_frame_has_the_right_size_and_the_video_the_right_length():
    b = brief(SCREEN, TEXT, PHOTO)
    assets = Assets([screenshot()], {2: Image.new("RGB", (1024, 1536), (90, 60, 40))})
    out = list(frames(b, LOOK, assets))
    assert len(out) == round((6 + END_CARD_SECONDS) * FPS)
    assert all(f.size == (W, H) and f.mode == "RGB" for f in out[::40])


def test_rendering_is_deterministic():
    b = brief(SCREEN, TEXT, PHOTO)
    assets = Assets([screenshot()], {2: Image.new("RGB", (1024, 1536), (90, 60, 40))})
    a = [hashlib.sha256(f.tobytes()).hexdigest() for f in list(frames(b, LOOK, assets))[::25]]
    b2 = [hashlib.sha256(f.tobytes()).hexdigest() for f in list(frames(b, LOOK, assets))[::25]]
    assert a == b2


def test_the_screen_card_holds_the_real_pixels_only_resized():
    shot = screenshot()
    layer = screen_layer(shot)
    expected = prepare_product(shot, (CARD_W, round(shot.height * CARD_W / shot.width)), radius=44)
    if expected.height > 1260:  # the card fits the height for tall screenshots
        w = round(shot.width * 1260 / shot.height)
        expected = prepare_product(shot, (w, 1260), radius=44)
    crop = layer.crop((80, 80, 80 + expected.width, 80 + expected.height))
    inner = (60, 60, expected.width - 60, expected.height - 60)  # away from the rounded corners
    assert crop.crop(inner).convert("RGB").tobytes() == expected.crop(inner).convert("RGB").tobytes()


def test_a_weak_rating_is_not_advertised():
    good = EndCard(brief(SCREEN), LOOK)
    weak = EndCard(brief(SCREEN), Look.from_palette(["#FFFFFF", "#000000", "#FF0000", "#EEEEEE"], "X", rating=3.9,
                                                    rating_count=500))
    few = EndCard(brief(SCREEN), Look.from_palette(["#FFFFFF", "#000000", "#FF0000", "#EEEEEE"], "X", rating=5.0,
                                                   rating_count=3))
    assert good.rating.width > weak.rating.width  # "Rated 4.8 on the App Store" vs "On the App Store"
    assert weak.rating.tobytes() == few.rating.tobytes()


def test_missing_assets_are_refused_before_rendering():
    with pytest.raises(ValueError, match="screenshot 2"):
        list(frames(brief(Scene("screen", "x", "still", 2.0, screen=2)), LOOK, Assets([screenshot()])))
    with pytest.raises(ValueError, match="generated background"):
        list(frames(brief(SCREEN, PHOTO), LOOK, Assets([screenshot()])))


def test_render_writes_a_playable_mp4_and_a_poster(tmp_path):
    info = render(brief(SCREEN, TEXT), LOOK, Assets([screenshot()]), tmp_path / "ad.mp4")
    n, secs = imageio_ffmpeg.count_frames_and_secs(str(tmp_path / "ad.mp4"))
    assert n == info["frames"] == round((4 + END_CARD_SECONDS) * FPS) and abs(secs - info["seconds"]) < 0.1
    assert Image.open(tmp_path / "ad.poster.jpg").size == (W, H)
