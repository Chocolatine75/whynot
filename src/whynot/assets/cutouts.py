"""The app's real interface and its mascot, found in store screenshots by SAM 3.1.

Store screenshots are posters: a headline, a phone, sometimes a mascot. A trend ad needs the bare
interface (full screen, punched into) and the mascot as a character. SAM 3.1 finds both ("phone screen",
"cartoon mascot"); we crop the ORIGINAL screenshot at the box SAM returns, so the pixels shown are the
app's own, only cropped and scaled. Boxes are cached by screenshot hash: SAM runs once per screenshot.

Masks (for a clean mascot cut-out) are not decoded here yet: the mascot is shown as a sticker cropped at
its box.
"""

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from whynot.assets.sam import parse
from whynot.models import image_data_url

PROBE_SIDE = 1600  # SAM sees a downscaled copy; boxes are mapped back to the original
UI_INSET = 0.035  # trim the phone's rounded corners and bezel
MIN_MASCOT_SHARE = 0.03  # a "mascot" smaller than 3 % of the screenshot is an icon in the UI, not a character


@dataclass(frozen=True)
class Found:
    box: tuple[int, int, int, int]  # in the original screenshot's pixels
    area_share: float


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
        found, _ = parse(result.text)
        boxes = [[round(b.x1 / k), round(b.y1 / k), round(b.x2 / k), round(b.y2 / k)] for b in found]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(boxes))
    area = img.width * img.height
    out = [Found((x1, y1, x2, y2), (x2 - x1) * (y2 - y1) / area) for x1, y1, x2, y2 in boxes if x2 > x1 and y2 > y1]
    return sorted(out, key=lambda f: -f.area_share)


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
        for m in find(model, img, "cartoon mascot", cache):
            if m.area_share >= MIN_MASCOT_SHARE and (best is None or m.area_share > best[0].area_share):
                best = (m, img)
    mascot = best[1].convert("RGB").crop(best[0].box) if best else None
    return AppCutouts(screens, mascot)
