"""The app's real interface and its mascot, found in store screenshots by SAM 3.1.

Store screenshots are posters: a headline, a phone, sometimes a mascot. A trend ad needs the bare
interface (full screen, punched into) and the mascot as a character. SAM 3.1 finds both ("phone screen",
"cartoon mascot"); we crop the ORIGINAL screenshot at the box SAM returns, so the pixels shown are the
app's own, only cropped and scaled. Boxes are cached by screenshot hash: SAM runs once per screenshot.

The mascot is cut out with its SAM mask (decoded by Meta's `meta-sam-parser`): a transparent PNG of the
character only. The interface is a plain crop (a rectangle needs no mask).
"""

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from whynot.assets.sam import decode_mask, parse
from whynot.models import image_data_url

PROBE_SIDE = 1600  # SAM sees a downscaled copy; boxes are mapped back to the original
UI_INSET = 0.035  # trim the phone's rounded corners and bezel
MIN_MASCOT_SHARE = 0.03  # a "mascot" smaller than 3 % of the screenshot is an icon in the UI, not a character


MASCOT_CONCEPTS = ("cartoon mascot", "cartoon character", "cartoon animal")


@dataclass(frozen=True)
class Found:
    box: tuple[int, int, int, int]  # in the original screenshot's pixels
    area_share: float
    mask: Path | None = None  # the object's mask (white = object), at its own resolution


def _probe(img: Image.Image) -> tuple[bytes, float]:
    small = img.convert("RGB")
    k = min(1.0, PROBE_SIDE / max(small.size))
    if k < 1:
        small = small.resize((round(small.width * k), round(small.height * k)))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=90)
    return buf.getvalue(), k


def find(model: Any, img: Image.Image, concept: str, cache: Path) -> list[Found]:
    """Boxes of `concept` in `img` (original pixels), biggest first; cached by image + concept."""
    raw = img.convert("RGB").tobytes()
    key = hashlib.sha256(raw + img.size.__repr__().encode() + concept.encode()).hexdigest()[:24]
    path = Path(cache) / f"{key}.json"
    if path.exists():
        boxes = json.loads(path.read_text())
    else:
        jpeg, k = _probe(img)
        result = model.segment(image_data_url(jpeg, "image/jpeg"), concept, module="cutouts")
        found, masks = parse(result.text)
        boxes = [[round(b.x1 / k), round(b.y1 / k), round(b.x2 / k), round(b.y2 / k)] for b in found]
        path.parent.mkdir(parents=True, exist_ok=True)
        for i, m in enumerate(masks[:len(boxes)]):  # one mask per box, in the same order
            try:
                raster = decode_mask(m)
            except Exception:  # a mask we can't read leaves the box usable
                continue
            Image.frombytes("L", (m.width, m.height), bytes(v * 255 for v in raster)).save(
                path.with_name(f"{key}-{i}.png"))
        path.write_text(json.dumps(boxes))
    area = img.width * img.height
    out = []
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        if x2 > x1 and y2 > y1:
            mask = path.with_name(f"{key}-{i}.png")
            out.append(Found((x1, y1, x2, y2), (x2 - x1) * (y2 - y1) / area, mask if mask.exists() else None))
    return sorted(out, key=lambda f: -f.area_share)


def cut_out(img: Image.Image, found: Found) -> Image.Image:
    """The object alone on transparency (its mask resized to its box), or the box crop without a mask."""
    crop = img.convert("RGBA").crop(found.box)
    if found.mask is not None:
        with Image.open(found.mask) as m:
            crop.putalpha(m.convert("L").resize(crop.size, Image.Resampling.BILINEAR))
        bbox = crop.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if bbox:
            crop = crop.crop(bbox)
    return crop


def ui_crop(img: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """The interface inside the phone: the box, trimmed of the bezel and rounded corners."""
    x1, y1, x2, y2 = box
    dx, dy = round((x2 - x1) * UI_INSET), round((y2 - y1) * UI_INSET * 0.6)
    return img.convert("RGB").crop((x1 + dx, y1 + dy, x2 - dx, y2 - dy))


@dataclass
class AppCutouts:
    screens: list[Image.Image]  # the bare interface of each screenshot (or the screenshot if none found)
    mascot: Image.Image | None


def cutouts(model: Any, screenshots: list[Image.Image], cache: Path) -> AppCutouts:
    screens, best = [], None
    for img in screenshots:
        phones = find(model, img, "phone screen", cache)
        screens.append(ui_crop(img, phones[0].box) if phones else img.convert("RGB"))
    for concept in MASCOT_CONCEPTS:  # SAM needs the right words: try a few, keep the biggest character
        for img in screenshots:
            for m in find(model, img, concept, cache):
                if m.area_share >= MIN_MASCOT_SHARE and (best is None or m.area_share > best[0].area_share):
                    best = (m, img)
        if best:
            break
    mascot = cut_out(best[1], best[0]) if best else None
    return AppCutouts(screens, mascot)
