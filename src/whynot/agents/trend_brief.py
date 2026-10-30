"""Trend briefs: a viral format turned into an ad, as a fast shot list built to hold a thumb.

Shape: the TREND (most of the video, the reason people watch) → the TWIST (the app is the punchline,
shown from its real screens) → the CTA. 8-14 shots of 0.6-2.2 s: a cut every second or so, every shot
moving, a native on-screen caption bubble, a sound effect on the cuts that need one.

Each shot is one of:
- `text`: a bold statement on a flat colour (meme cards, labels like "EXPECTATION");
- `photo`: a generated photo (Muse Image), candid phone-camera style, never a phone/app/logo/text;
- `screen`: the app's REAL interface (cropped from a store screenshot by SAM 3.1), punched into a region;
- `mascot`: the app's own mascot, cut out by SAM 3.1, as a sticker (only when the app has one).

All words go through the same checks as every ad (`director.CopyRules`).
"""

import re
from dataclasses import asdict, dataclass
from typing import Any

from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.agents.director import Context, CopyRules
from whynot.create.trends import BY_ID, Format
from whynot.models import SPARK

VISUALS = ("text", "photo", "screen", "mascot")
MOVES = ("punch_in", "slow_zoom", "shake", "slide", "pop", "still")
SFX = ("whoosh", "pop", "ding", "record_scratch", "bass_drop", "none")
FOCUS = ("top", "middle", "bottom", "full")
BEATS = ("trend", "twist", "cta")
MOODS = ("upbeat", "calm", "playful", "inspiring", "dramatic")
SHOT_SECONDS = (0.6, 2.2)
SHOTS = (8, 14)
TOTAL_SECONDS = (10.0, 20.0)
END_CARD_SECONDS = 1.6
_FORBIDDEN_IN_PHOTO = re.compile(r"\b(phone|smartphone|screen|app|interface|ui|logo|text|words?|letters?|caption|"
                                 r"iphone|android|tablet|laptop|brand|sign|signs)\b", re.IGNORECASE)
_ID = re.compile(r"^[a-z][a-z0-9_]{2,40}$")


@dataclass(frozen=True)
class Shot:
    visual: str
    caption: str
    seconds: float
    move: str
    sfx: str
    beat: str
    screen: int | None = None
    focus: str | None = None
    prompt: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class TrendBrief:
    id: str
    format: str
    persona: str
    angle: str
    language: str
    hook: str  # the first caption, on screen from frame 0
    shots: tuple[Shot, ...]
    voice: str  # what the voice says over the shots ("" = no voice)
    cta: str
    music: str

    @property
    def seconds(self) -> float:
        return sum(s.seconds for s in self.shots) + END_CARD_SECONDS

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "TrendBrief":
        return cls(**{**d, "shots": tuple(Shot(**s) for s in d["shots"])})


PROMPT = """You are the best short-form creative on TikTok and Reels. Make a {low}-{high} second vertical ad that
people watch to the end while doom-scrolling, in {language}.

Use the viral format "{fmt_name}": {beats}
Why it works: {why}
Example of the shape (another wording, do not copy): "{example}"

The ad: 70 % TREND (pure entertainment, relatable, no selling), then the TWIST where {app} is the punchline
(show its real screens), then the CTA. The viewer must feel the twist coming but not see it.

App: {app} — {description}
Persona: {persona}
Angle to land in the twist: {angle}
Verified claims (numbers only from these or the store page): {claims}
Real app screens you can show (kind "screen", by number): {screens}
{mascot_line}

Shots ({min_shots}-{max_shots}), each {s_low}-{s_high} s, a cut every second or so, every shot moving:
- visual: {visuals}. "photo" = a candid phone-camera photo you describe in `prompt` (a scene, people,
  objects; NEVER a phone, screen, app, logo, sign or any text in it). "screen" = real screen number `screen`
  with `focus` (top, middle, bottom, full). "text" = a bold card with `text`.
- caption: the native on-screen caption bubble (max 8 words, can be "" for a pure visual beat)
- move: {moves}; sfx on the cut: {sfx}; beat: trend, twist or cta (in that order).

Return JSON only:
{{"id": "<snake_case>", "hook": "<first caption, max 8 words, the scroll-stopper>",
  "shots": [{{"visual": "photo", "prompt": "...", "caption": "...", "seconds": 1.2, "move": "punch_in",
             "sfx": "whoosh", "beat": "trend"}}, ...],
  "voice": "<optional creator-style voice-over across the video, max 40 words, or empty>",
  "cta": "<end card button, max 4 words>", "music": "<one of {moods}>"}}
No emoji. Short words. Make it funny or tense, never corporate."""


def _words(value: Any, n: int, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value.strip() and not allow_empty):
        raise Invalid(f"'{name}' must be a non-empty string")
    text = " ".join(value.split())
    if len(text.split()) > n:
        raise Invalid(f"'{name}' has {len(text.split())} words, max {n}")
    return text


def make_validator(ctx: Context, fmt: Format, persona: str, angle: str, n_screens: int, *, has_mascot: bool):
    rules = CopyRules(ctx)

    def validate(data: Any) -> TrendBrief:
        if not isinstance(data, dict):
            raise Invalid("answer must be a JSON object")
        bid = str(data.get("id", ""))
        if not _ID.match(bid):
            raise Invalid("'id' must be snake_case, 3-41 characters")
        hook = _words(data.get("hook"), 8, "hook")
        cta = _words(data.get("cta"), 4, "cta")
        voice = _words(data.get("voice", ""), 40, "voice", allow_empty=True)
        if data.get("music") not in MOODS:
            raise Invalid(f"'music' must be one of {list(MOODS)}")
        raw = data.get("shots")
        if not isinstance(raw, list) or not SHOTS[0] <= len(raw) <= SHOTS[1]:
            raise Invalid(f"'shots' must be a list of {SHOTS[0]} to {SHOTS[1]} shots")
        texts = {"hook.main": hook, "cta.button": cta}
        if voice:
            texts["body.voice"] = voice
        shots, last_beat = [], 0
        for i, s in enumerate(raw, 1):
            where = f"shot {i}"
            if not isinstance(s, dict):
                raise Invalid(f"{where} must be an object")
            for key, allowed in (("visual", VISUALS), ("move", MOVES), ("sfx", SFX), ("beat", BEATS)):
                if s.get(key) not in allowed:
                    raise Invalid(f"{where}: '{key}' must be one of {list(allowed)}")
            beat = BEATS.index(s["beat"])
            if beat < last_beat:
                raise Invalid(f"{where}: beats must go trend → twist → cta, never back")
            last_beat = beat
            sec = s.get("seconds")
            if isinstance(sec, bool) or not isinstance(sec, (int, float)) or not SHOT_SECONDS[0] <= sec <= SHOT_SECONDS[1]:
                raise Invalid(f"{where}: 'seconds' must be between {SHOT_SECONDS[0]} and {SHOT_SECONDS[1]}")
            caption = _words(s.get("caption", ""), 8, f"{where} caption", allow_empty=True)
            if caption:
                texts[f"proof.shot{i}"] = caption
            screen = focus = prompt = text = None
            if s["visual"] == "screen":
                screen = s.get("screen")
                if isinstance(screen, bool) or not isinstance(screen, int) or not 1 <= screen <= n_screens:
                    raise Invalid(f"{where}: 'screen' must be a screen number from 1 to {n_screens}")
                focus = s.get("focus", "full")
                if focus not in FOCUS:
                    raise Invalid(f"{where}: 'focus' must be one of {list(FOCUS)}")
            elif s["visual"] == "photo":
                prompt = _words(s.get("prompt"), 40, f"{where} prompt")
                if m := _FORBIDDEN_IN_PHOTO.search(prompt):
                    raise Invalid(f"{where}: the photo prompt mentions {m.group(0)!r}; generated photos never show a "
                                  "phone, screen, app, logo, sign or text (show the real app with visual 'screen')")
            elif s["visual"] == "text":
                text = _words(s.get("text"), 8, f"{where} text")
                texts[f"proof.card{i}"] = text
            elif not has_mascot:
                raise Invalid(f"{where}: this app has no mascot; use text, photo or screen")
            shots.append(Shot(s["visual"], caption, float(sec), s["move"], s["sfx"], s["beat"], screen, focus,
                              prompt, text))
        trend = sum(s.seconds for s in shots if s.beat == "trend")
        body = sum(s.seconds for s in shots)
        if not any(s.beat == "twist" and s.visual == "screen" for s in shots):
            raise Invalid("the twist must show the real app: at least one 'twist' shot with visual 'screen'")
        if trend < 0.5 * body:
            raise Invalid(f"the trend is only {trend:.1f} s of {body:.1f} s; make it most of the video (≥ 50 %)")
        total = body + END_CARD_SECONDS
        if not TOTAL_SECONDS[0] <= total <= TOTAL_SECONDS[1]:
            raise Invalid(f"the video lasts {total:.1f} s with the end card; make it "
                          f"{TOTAL_SECONDS[0]:.0f}-{TOTAL_SECONDS[1]:.0f} s")
        rules.check(texts, "trend brief")
        return TrendBrief(bid, fmt.id, persona, angle, ctx.language, hook, tuple(shots), voice, cta,
                          str(data["music"]))

    return validate


def write(client: ChatClient, ctx: Context, fmt: Format, *, persona: str, angle: str, screens: list[str],
          has_mascot: bool, model: str = SPARK) -> Answer[TrendBrief]:
    s = ctx.strategy
    p = s.persona(persona)
    a = next(x for x in s.angles if x.id == angle)
    prompt = PROMPT.format(
        low=int(TOTAL_SECONDS[0]), high=int(TOTAL_SECONDS[1]), language=ctx.language, fmt_name=fmt.name,
        beats=" → ".join(fmt.beats), why=fmt.why, example=fmt.example, app=ctx.app_name,
        description=" ".join(ctx.store_text.split())[:600], persona=f"{p.name}: {p.description}", angle=a.idea,
        claims="; ".join(c.text for c in s.claims) or "(none)",
        screens="; ".join(f"{i}. {d}" for i, d in enumerate(screens, 1)),
        mascot_line=("The app has a mascot (visual 'mascot'): use it as a character." if has_mascot
                     else "The app has no mascot: never use visual 'mascot'."),
        min_shots=SHOTS[0], max_shots=SHOTS[1], s_low=SHOT_SECONDS[0], s_high=SHOT_SECONDS[1],
        visuals=", ".join(VISUALS), moves=", ".join(MOVES), sfx=", ".join(SFX), moods=", ".join(MOODS))
    return ask_json(client, [{"role": "user", "content": prompt}],
                    make_validator(ctx, fmt, persona, angle, len(screens), has_mascot=has_mascot),
                    module="trend_brief", model=model, repairs=3, max_tokens=6000, reasoning_effort="low")


def get_format(fid: str) -> Format:
    if fid not in BY_ID:
        raise ValueError(f"unknown format {fid!r}")
    return BY_ID[fid]
