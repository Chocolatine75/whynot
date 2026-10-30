"""Deconstruct competitor ads: what each one does, in a fixed typed shape, never prose.

For every competitor ad with a captured creative (`ingest/creatives.py`), Muse Spark looks at the image
(or a video's poster frame) and the ad copy and returns: the hook, the visual subject, the text on the
image, the call to action, the emotional pitch, the creative style, the main promise and who it seems to
speak to. The palette is measured from the pixels by code, not asked.

Each answer is validated (closed vocabularies, lengths, text overlays must be short and distinct) and
repaired with feedback (`ask_json`). Results are cached on disk by ad id and prompt version: an ad is
analysed once, then every run and every business reads it for free.
"""

import json
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from whynot.agents.ask import AgentError, ChatClient, Invalid, ask_json
from whynot.create.trends import FORMATS as TREND_FORMATS
from whynot.create.trends import NONE
from whynot.ingest.adlibrary import CompetitorAd
from whynot.models import SPARK, image_data_url

PROMPT_VERSION = "deconstruct-v2"  # v2: trend_format

PITCHES = ("curiosity", "problem_solution", "transformation", "social_proof", "tutorial", "offer", "humor",
           "fear_of_missing_out", "authority", "emotional_story")
STYLES = ("app_screen", "ugc_person", "lifestyle_photo", "illustration", "text_card", "before_after", "mixed")
FORMATS = ("static", "video")

SYSTEM = """You are a senior performance creative strategist. You break down Facebook and Instagram ads into
their parts so a team can learn what the market does. Be literal and specific; never praise."""

PROMPT = """Ad by "{advertiser}" ({format}{video_note}).
Primary text: {body}
Headline: {title}

Look at the image and the copy and return JSON only:
{{
  "hook": "<what grabs attention at first glance, max 15 words>",
  "visual_subject": "<what the image shows, max 20 words>",
  "text_overlays": ["<each piece of text written ON the image, verbatim, max 6>"],
  "cta": "<the call to action on the image or in the copy, or null>",
  "emotional_pitch": "<one of: {pitches}>",
  "creative_style": "<one of: {styles}>",
  "promise": "<the main benefit promised, max 15 words>",
  "audience": "<who this ad seems to speak to, max 15 words>",
  "trend_format": "<the viral format it follows, one of: {formats}; or none>"
}}"""


@dataclass
class Deconstruction:
    ad_id: str
    advertiser: str
    format: str
    hook: str
    visual_subject: str
    text_overlays: list[str]
    cta: str | None
    emotional_pitch: str
    creative_style: str
    promise: str
    audience: str
    trend_format: str = NONE  # a viral format from `create/trends.py`, or "none"
    palette: list[str] = field(default_factory=list)  # measured from the pixels
    prompt_version: str = PROMPT_VERSION

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Deconstruction":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _words(text: str, n: int, name: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise Invalid(f"'{name}' must be a non-empty string")
    text = " ".join(text.split())
    if len(text.split()) > n:
        raise Invalid(f"'{name}' has {len(text.split())} words, max {n}")
    return text


def validate(data: Any) -> dict[str, Any]:
    """The model's answer, checked field by field (the message goes back to the model when wrong)."""
    if not isinstance(data, dict):
        raise Invalid("answer must be a JSON object")
    out: dict[str, Any] = {
        "hook": _words(data.get("hook", ""), 15, "hook"),
        "visual_subject": _words(data.get("visual_subject", ""), 20, "visual_subject"),
        "promise": _words(data.get("promise", ""), 15, "promise"),
        "audience": _words(data.get("audience", ""), 15, "audience"),
    }
    overlays = data.get("text_overlays", [])
    if not isinstance(overlays, list) or len(overlays) > 6 or not all(isinstance(t, str) for t in overlays):
        raise Invalid("'text_overlays' must be a list of at most 6 strings")
    seen, clean = set(), []
    for t in overlays:
        t = " ".join(t.split())
        if t and t.lower() not in seen:
            seen.add(t.lower())
            clean.append(t[:120])
    out["text_overlays"] = clean
    cta = data.get("cta")
    if cta is not None and not isinstance(cta, str):
        raise Invalid("'cta' must be a string or null")
    out["cta"] = " ".join(cta.split())[:40] if cta and cta.strip() else None
    trend = data.get("trend_format", NONE)
    allowed_trends = {f.id for f in TREND_FORMATS} | {NONE}
    if trend not in allowed_trends:
        raise Invalid(f"'trend_format' must be one of {sorted(allowed_trends)}, got {trend!r}")
    out["trend_format"] = trend
    for key, allowed in (("emotional_pitch", PITCHES), ("creative_style", STYLES)):
        value = data.get(key)
        if value not in allowed:
            raise Invalid(f"'{key}' must be one of {list(allowed)}, got {value!r}")
        out[key] = value
    return out


def palette(path: Path, n: int = 4) -> list[str]:
    """The `n` dominant colours of an image, as hex, most common first (deterministic)."""
    with Image.open(path) as im:
        small = im.convert("RGB").resize((64, 64))
    quant = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = quant.getpalette() or []
    counts: list[tuple[int, int]] = sorted(quant.getcolors() or [], reverse=True)  # type: ignore[arg-type]
    return [f"#{pal[i * 3]:02X}{pal[i * 3 + 1]:02X}{pal[i * 3 + 2]:02X}" for _, i in counts[:n]]


class DeconstructionStore:
    """`folder/<ad id>.json`; an entry from another prompt version is ignored (re-analysed)."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def get(self, ad_id: str) -> Deconstruction | None:
        p = self.folder / f"{ad_id}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        return Deconstruction.from_json(d) if d.get("prompt_version") == PROMPT_VERSION else None

    def put(self, d: Deconstruction) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{d.ad_id}.json").write_text(json.dumps(asdict(d), indent=1, ensure_ascii=False) + "\n")


@dataclass
class DeconstructReport:
    done: dict[str, Deconstruction] = field(default_factory=dict)
    cached: int = 0
    failed: dict[str, str] = field(default_factory=dict)
    usd: float = 0.0


def deconstruct_one(client: ChatClient, ad: CompetitorAd, image: Path, fmt: str, *, model: str = SPARK,
                    reasoning_effort: str | None = "low") -> tuple[Deconstruction, float]:
    if fmt not in FORMATS:
        raise ValueError(f"format must be one of {FORMATS}")
    text = PROMPT.format(advertiser=ad.page_name or "unknown", format=fmt,
                         video_note=": the image is the video's first frame" if fmt == "video" else "",
                         body=(ad.bodies or [""])[0][:600] or "(none)", title=(ad.titles or [""])[0][:120] or "(none)",
                         pitches=", ".join(PITCHES), styles=", ".join(STYLES),
                         formats=", ".join(f"{f.id} ({f.name})" for f in TREND_FORMATS))
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": [{"type": "text", "text": text},
                                             {"type": "image_url", "image_url": {"url": image_data_url(image)}}]}]
    extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
    answer = ask_json(client, messages, validate, module="deconstruct", model=model, repairs=1,
                      max_tokens=3000, **extra)
    return Deconstruction(ad.id, ad.page_name or "", fmt, palette=palette(image), **answer.value), answer.usd


def deconstruct_all(client: ChatClient, ads: Iterable[CompetitorAd], images: dict[str, tuple[Path, str]],
                    store: DeconstructionStore, *, model: str = SPARK, max_workers: int = 6) -> DeconstructReport:
    """Every ad with a captured creative (`images`: ad id -> (jpeg, format)); cached ones cost nothing."""
    report = DeconstructReport()
    todo = []
    for ad in ads:
        if ad.id not in images:
            continue
        hit = store.get(ad.id)
        if hit:
            report.done[ad.id] = hit
            report.cached += 1
        else:
            todo.append(ad)

    def job(ad: CompetitorAd) -> tuple[str, Any]:
        try:
            path, fmt = images[ad.id]
            return ad.id, deconstruct_one(client, ad, path, fmt, model=model)
        except AgentError as exc:
            return ad.id, exc
        except Exception as exc:  # one broken ad must not stop the market analysis
            return ad.id, exc

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for ad_id, res in pool.map(job, todo):
            if isinstance(res, Exception):
                report.failed[ad_id] = f"{type(res).__name__}: {res}"[:300]
                report.usd += getattr(res, "usd", 0.0)
                continue
            d, usd = res
            store.put(d)
            report.done[ad_id] = d
            report.usd += usd
    return report
