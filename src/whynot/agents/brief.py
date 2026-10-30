"""Video briefs: one storyboard per picked archetype, ready for the deterministic renderer.

A brief is a 12-18 s vertical video: 3-4 scenes, then an end card. Each scene is one of
- `screen`: one of the app's REAL screenshots in a phone (never generated: product pixels stay true);
- `scene`: a background made by Muse Image from a prompt (no phone, no app, no logo, no text in it);
- `text`: a full-screen text card in the brand colours,
with a short overlay and a motion. The brief also has the hook (shown big over the first scene), the end
card button, a voice-over script and a music mood.

Every word goes through the same checks as our static ads (`director.CopyRules`): lengths, numbers only
from verified claims or the store page, no competitor names, Meta policy rules, characters the font can
draw, accents in accented languages. The model must show the real app at least once and may not ask Muse
Image for anything that would fake the product.
"""

import re
from dataclasses import asdict, dataclass
from typing import Any

from whynot.agents.archetypes import Archetype, Pick
from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.agents.director import Context, CopyRules
from whynot.models import SPARK

KINDS = ("screen", "scene", "text")
MOTIONS = ("zoom_in", "zoom_out", "scroll", "pan", "pop", "still")
MOODS = ("upbeat", "calm", "playful", "inspiring", "dramatic")
SCENE_SECONDS = (2.0, 4.5)
END_CARD_SECONDS = 2.5
TOTAL_SECONDS = (12.0, 18.0)
WORDS = {"hook": 8, "overlay": 9, "cta": 4, "narration": 45}
# A generated scene must not fake the product or carry text (text is drawn by code, in the brand font).
_FORBIDDEN_IN_SCENE = re.compile(r"\b(phone|smartphone|screen|app|interface|ui|logo|text|words?|letters?|"
                                 r"caption|iphone|android|tablet|laptop|brand)\b", re.IGNORECASE)
_ID = re.compile(r"^[a-z][a-z0-9_]{2,40}$")


@dataclass(frozen=True)
class Scene:
    kind: str
    overlay: str
    motion: str
    seconds: float
    screen: int | None = None  # 1-based index into the app's screenshots
    prompt: str | None = None  # Muse Image prompt for kind "scene"
    text: str | None = None  # the card's text for kind "text"


@dataclass(frozen=True)
class VideoBrief:
    id: str
    archetype: str
    persona: str
    angle: str
    language: str
    hook: str
    scenes: tuple[Scene, ...]
    cta: str
    narration: str
    music: str
    why: str

    @property
    def seconds(self) -> float:
        return sum(s.seconds for s in self.scenes) + END_CARD_SECONDS

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "VideoBrief":
        return cls(**{**d, "scenes": tuple(Scene(**s) for s in d["scenes"])})


PROMPT = """Write the storyboard of a {low}-{high} second vertical video ad (9:16) for Instagram Reels and
Facebook, in {language}.

App: {app}
What it is: {description}
Persona: {persona}
Angle (the idea to get across): {angle}
Market archetype to follow: {archetype} — what works for competitors:
{examples}
Verified claims you may use (numbers only from these or the store page): {claims}
The app has {n_screens} real screenshots, numbered 1 to {n_screens}:
{screens}

Scenes ({min_scenes}-{max_scenes}), each {s_low}-{s_high} seconds, then an end card (logo + button) is added.
- kind "screen": show real screenshot number `screen` in a phone. Show the real app at least once.
- kind "scene": a background generated from `prompt` (a place, an object, a mood). Never a phone, screen,
  app, logo, or any text in the prompt.
- kind "text": a full-screen card with `text` (max {w_overlay} words).
Every scene has an `overlay` (max {w_overlay} words, on screen) and a `motion` ({motions}).

Return JSON only:
{{"id": "<snake_case>", "hook": "<max {w_hook} words, shown big over the first scene>",
  "scenes": [{{"kind": "screen", "screen": 1, "overlay": "...", "motion": "zoom_in", "seconds": 3}}, ...],
  "cta": "<end card button, max {w_cta} words>", "narration": "<voice-over, max {w_narration} words>",
  "music": "<one of {moods}>"}}
No emoji. Words only. Speak to the persona, like the best ads of the archetype."""


def _words(value: Any, n: int, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Invalid(f"'{name}' must be a non-empty string")
    text = " ".join(value.split())
    if len(text.split()) > n:
        raise Invalid(f"'{name}' has {len(text.split())} words, max {n}")
    return text


def make_validator(ctx: Context, pick: Pick, n_screens: int, *, scenes: tuple[int, int] = (3, 4)):
    rules = CopyRules(ctx)

    def validate(data: Any) -> VideoBrief:
        if not isinstance(data, dict):
            raise Invalid("answer must be a JSON object")
        bid = str(data.get("id", ""))
        if not _ID.match(bid):
            raise Invalid("'id' must be snake_case, 3-41 characters")
        hook = _words(data.get("hook"), WORDS["hook"], "hook")
        cta = _words(data.get("cta"), WORDS["cta"], "cta")
        narration = _words(data.get("narration"), WORDS["narration"], "narration")
        music = data.get("music")
        if music not in MOODS:
            raise Invalid(f"'music' must be one of {list(MOODS)}")
        raw = data.get("scenes")
        if not isinstance(raw, list) or not scenes[0] <= len(raw) <= scenes[1]:
            raise Invalid(f"'scenes' must be a list of {scenes[0]} to {scenes[1]} scenes")
        out, texts = [], {"hook.main": hook, "cta.button": cta, "body.narration": narration}
        for i, s in enumerate(raw, 1):
            where = f"scene {i}"
            if not isinstance(s, dict) or s.get("kind") not in KINDS:
                raise Invalid(f"{where}: 'kind' must be one of {list(KINDS)}")
            if s.get("motion") not in MOTIONS:
                raise Invalid(f"{where}: 'motion' must be one of {list(MOTIONS)}")
            sec = s.get("seconds")
            if isinstance(sec, bool) or not isinstance(sec, (int, float)) or not (
                    SCENE_SECONDS[0] <= sec <= SCENE_SECONDS[1]):
                raise Invalid(f"{where}: 'seconds' must be between {SCENE_SECONDS[0]} and {SCENE_SECONDS[1]}")
            overlay = _words(s.get("overlay"), WORDS["overlay"], f"{where} overlay")
            texts[f"proof.scene{i}"] = overlay
            kind, screen, prompt, text = s["kind"], None, None, None
            if kind == "screen":
                screen = s.get("screen")
                if isinstance(screen, bool) or not isinstance(screen, int) or not 1 <= screen <= n_screens:
                    raise Invalid(f"{where}: 'screen' must be a screenshot number from 1 to {n_screens}")
            elif kind == "scene":
                prompt = _words(s.get("prompt"), 40, f"{where} prompt")
                if m := _FORBIDDEN_IN_SCENE.search(prompt):
                    raise Invalid(f"{where}: the scene prompt mentions {m.group(0)!r}; generated scenes never show a "
                                  "phone, screen, app, logo or text (the real app is shown with kind 'screen')")
            else:
                text = _words(s.get("text"), WORDS["overlay"], f"{where} text")
                texts[f"proof.card{i}"] = text
            out.append(Scene(kind, overlay, s["motion"], float(sec), screen, prompt, text))
        if not any(s.kind == "screen" for s in out):
            raise Invalid("show the real app at least once: one scene must have kind 'screen'")
        total = sum(s.seconds for s in out) + END_CARD_SECONDS
        if not TOTAL_SECONDS[0] <= total <= TOTAL_SECONDS[1]:
            raise Invalid(f"the video lasts {total:.1f} s with the {END_CARD_SECONDS} s end card; "
                          f"make it {TOTAL_SECONDS[0]:.0f}-{TOTAL_SECONDS[1]:.0f} s")
        rules.check(texts, "brief")
        return VideoBrief(bid, pick.archetype, pick.persona, pick.angle, ctx.language, hook, tuple(out), cta,
                          narration, music, pick.why)

    return validate


def write_brief(client: ChatClient, ctx: Context, pick: Pick, archetype: Archetype, screens: list[str], *,
                model: str = SPARK) -> Answer[VideoBrief]:
    """`screens`: one short description per real screenshot, in order (what each shows)."""
    s = ctx.strategy
    persona = s.persona(pick.persona)
    angle = next(a for a in s.angles if a.id == pick.angle)
    examples = "\n".join(f'- hook "{e["hook"]}", promise "{e["promise"]}", visual: {e["visual"]}, '
                         f'on-image text: {e["overlays"]}' for e in archetype.examples)
    prompt = PROMPT.format(
        low=int(TOTAL_SECONDS[0]), high=int(TOTAL_SECONDS[1]), language=ctx.language, app=ctx.app_name,
        description=" ".join(ctx.store_text.split())[:700], persona=f"{persona.name}: {persona.description}",
        angle=angle.idea, archetype=archetype.key, examples=examples or "(none)",
        claims="; ".join(c.text for c in s.claims) or "(none)", n_screens=len(screens),
        screens="\n".join(f"{i}. {d}" for i, d in enumerate(screens, 1)), min_scenes=3, max_scenes=4,
        s_low=SCENE_SECONDS[0], s_high=SCENE_SECONDS[1], w_overlay=WORDS["overlay"], w_hook=WORDS["hook"],
        w_cta=WORDS["cta"], w_narration=WORDS["narration"], motions=", ".join(MOTIONS), moods=", ".join(MOODS))
    return ask_json(client, [{"role": "user", "content": prompt}], make_validator(ctx, pick, len(screens)),
                    module="brief", model=model, repairs=3, max_tokens=5000, reasoning_effort="low")


SCREENS_PROMPT = """These are the {n} App Store screenshots of the app "{app}", in order. For each, say in at most
15 words what it shows (the feature, not the colours). Return JSON only: {{"screens": ["...", ...]}}"""


def describe_screens(client: ChatClient, app_name: str, images: list[str], *, model: str = SPARK) -> Answer[list[str]]:
    """One short description per real screenshot (`images`: data URLs), so briefs can pick the right one."""
    n = len(images)

    def validate(data: Any) -> list[str]:
        items = data.get("screens") if isinstance(data, dict) else None
        if not isinstance(items, list) or len(items) != n:
            raise Invalid(f"'screens' must be a list of exactly {n} descriptions, one per screenshot")
        return [_words(x, 15, f"screen {i}") for i, x in enumerate(items, 1)]

    content: list[dict[str, Any]] = [{"type": "text", "text": SCREENS_PROMPT.format(n=n, app=app_name)}]
    for i, url in enumerate(images, 1):
        content += [{"type": "text", "text": f"Screenshot {i}:"}, {"type": "image_url", "image_url": {"url": url}}]
    return ask_json(client, [{"role": "user", "content": content}], validate, module="brief", model=model,
                    repairs=1, max_tokens=3000, reasoning_effort="low")
