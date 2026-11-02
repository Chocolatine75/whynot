"""The right real screen for each static ad, cut out of its store poster.

Seen on a WhatsApp run (Nov 1): ads about calls showed the chat list or the Status screen, because templates
took the store screenshots in turn; and every screen kept the store poster's own headline ("Simple. Reliable.
Private.") above the phone, so two headlines competed in one ad. So, once per run:

1. SAM 3.1 finds the phone screen in each store screenshot; the bare interface (`cutouts.ui_crop`, a crop of
   the original pixels, nothing generated) is saved as `assets/ui-<screenshot>.png`. A screenshot where SAM
   finds no phone, or only a small one, is used whole;
2. one vision call describes each screen in a few words (`brief.describe_screens`);
3. each template gets the screen whose description shares the most content words with its concept and copy;
   ties go to the screen used least, so a run still shows several screens.

Cached in `screens.json` in the run folder (SAM boxes are cached by image hash as well).
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from whynot.assets.cutouts import find, ui_crop
from whynot.models import image_data_url
from whynot.sim.relevance import topic_words

MIN_PHONE_SHARE = 0.2  # a "phone screen" smaller than this share of the poster is a detail, not the screen


@dataclass(frozen=True)
class Screen:
    source: str  # the store screenshot (file name in assets/)
    ui: str | None  # the bare interface cut out of it (file name in assets/), or None
    description: str

    @property
    def asset(self) -> str:
        return self.ui or self.source


def prepare(model: Any, assets: Path, app_name: str, screenshots: list[str], *, sam_cache: Path,
            describe: Any = None) -> list[Screen]:
    """Cut out and describe every screenshot once (cached in `<assets>/../screens.json`)."""
    cache = Path(assets).parent / "screens.json"
    if cache.exists():
        known = [Screen(**s) for s in json.loads(cache.read_text())]
        if [s.source for s in known] == list(screenshots):
            return known
    if describe is None:
        from whynot.agents.brief import describe_screens as describe
    descriptions = describe(model, app_name, [image_data_url(Path(assets) / s) for s in screenshots]).value
    screens = []
    for name, text in zip(screenshots, descriptions, strict=True):
        with Image.open(Path(assets) / name) as img:
            phones = [p for p in find(model, img, "phone screen", sam_cache) if p.area_share >= MIN_PHONE_SHARE]
            ui = None
            if phones:
                ui = f"ui-{Path(name).stem}.png"
                ui_crop(img, phones[0].box).save(Path(assets) / ui)
        screens.append(Screen(name, ui, text))
    cache.write_text(json.dumps([asdict(s) for s in screens], indent=1, ensure_ascii=False))
    return screens


def match(text: str, screens: list[Screen], used: dict[str, int] | None = None) -> Screen:
    """The screen whose description best fits `text`; ties go to the least used, then the first."""
    if not screens:
        raise ValueError("no screen to choose from")
    words = topic_words(text)
    used = used if used is not None else {}

    def score(i: int) -> tuple[int, int, int]:
        s = screens[i]
        return (-len(words & topic_words(s.description)), used.get(s.source, 0), i)

    best = screens[min(range(len(screens)), key=score)]
    used[best.source] = used.get(best.source, 0) + 1
    return best


PICK_PROMPT = """You place the real app screen in each ad of "{app}". The screen must SHOW what the ad talks about
(an ad about video calls shows the call screen; an ad about privacy shows the screen that mentions encryption).

Screens:
{screens}

Ads:
{ads}

Return JSON only: {{"picks": {{"<ad id>": <screen number>, ...}}}} with every ad id exactly once."""


def pick(model: Any, app_name: str, concepts: dict[str, str], screens: list[Screen], *,
         model_id: str = "muse-spark-1.3") -> dict[str, Screen]:
    """The screen for each concept (ad id → concept), chosen by Muse Spark from the screen descriptions.

    One small call, any language. If the model gives no valid answer, word matching (`match`) decides."""
    from whynot.agents.ask import AgentError, Invalid, ask_json

    ids = list(concepts)

    def validate(data: Any) -> dict[str, Screen]:
        picks = data.get("picks") if isinstance(data, dict) else None
        if not isinstance(picks, dict) or set(picks) != set(ids):
            raise Invalid(f"'picks' must map exactly these ad ids: {ids}")
        out = {}
        for k, v in picks.items():
            if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= len(screens):
                raise Invalid(f"{k}: the screen must be a number from 1 to {len(screens)}")
            out[k] = screens[v - 1]
        return out

    prompt = PICK_PROMPT.format(app=app_name,
                                screens="\n".join(f"{i}. {s.description}" for i, s in enumerate(screens, 1)),
                                ads="\n".join(f"- {k}: {v}" for k, v in concepts.items()))
    try:
        return ask_json(model, [{"role": "user", "content": prompt}], validate, module="screens", model=model_id,
                        repairs=1, max_tokens=2000, reasoning_effort="low").value
    except AgentError:
        used: dict[str, int] = {}
        return {k: match(v, screens, used) for k, v in concepts.items()}
