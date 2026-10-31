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

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.agents.director import Context, CopyRules
from whynot.audio.voices import GENDERS, LANGUAGE_NAMES, NATIVE
from whynot.create.trends import BY_ID, Format
from whynot.models import SPARK

VISUALS = ("text", "photo", "screen", "mascot")
MOVES = ("punch_in", "slow_zoom", "shake", "slide", "pop", "still")
SFX = ("whoosh", "pop", "ding", "none")  # record scratch and bass drop sounded harsh: removed
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
class Line:
    """One spoken line: "me" (the creator, in the ad's language) or "them" (someone else, maybe in their own
    language, then spoken by a native voice with the accent asked)."""

    speaker: str
    text: str
    language: str  # ISO 639-1
    gender: str = "female"  # for "them"
    accent: str | None = None  # for native lines, e.g. "south"


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
    lines: tuple[Line, ...] = ()

    @property
    def seconds(self) -> float:
        return sum(s.seconds for s in self.shots) + END_CARD_SECONDS

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "TrendBrief":
        return cls(**{**d, "shots": tuple(Shot(**s) for s in d["shots"]),
                      "lines": tuple(Line(**x) for x in d.get("lines", ()))})


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
  "lines": [{{"speaker": "me", "text": "<the creator, in {language}>"}},
            {{"speaker": "them", "language": "<code>", "gender": "female|male", "accent": "<accent>",
              "text": "<what the other person says>"}}, ...],
  "cta": "<end card button, max 4 words>", "music": "<one of {moods}>"}}
{tone}"""

TONE = """TONE — non-negotiable. You are not a brand and not a teacher: you are a 19-24 year-old creator talking
into your phone, telling your friends what happened to you.
- First person, story energy, run-on and fragments: "so i said ca phe... and she just. kept. talking."
- Roast yourself, exaggerate, react: "i was SO cooked", "the way i just nodded", "no because why".
- Casual words used naturally, max two per video: lowkey, ngl, literally, bro, cooked, it's giving, fr.
- The app comes in like a friend's tip, never like an ad: "anyway this app has a southern voice and it's
  actually the only reason grandma understands me now".
- Captions read like texts: lowercase, short, no full stops.
- The audio is a short DIALOGUE ("lines", max 8, max 55 words in all): "me" is the creator; "them" is the
  other person in the story (the barista, the grandma, the mother-in-law). When they speak another language,
  write their line in that real language with every accent and tone mark (it is spoken by a native voice):
  {natives}. The joke is often the creator not understanding them.
- Never put words of another language inside an English line: when the creator TRIES to say something in
  the other language, give it its own "me" line with that language code and the correct accents (the creator's
  voice says it, like a learner would).
- Lines may use up to 3 emotion tags in all: [laughs], [sighs], [gasps], [whispers], [groans].
- Never sound like a lesson or a commercial: never use {banned}.
No emoji in captions."""
# Words that make a video sound like a language course or an ad, refused in the voice and the captions.
TEACHER_WORDS = ("learn", "learning", "lesson", "lessons", "practise", "practice", "practicing", "practising",
                 "improve", "skills", "master", "fluent", "fluently", "effortlessly", "unlock", "journey",
                 "discover", "boost", "enhance", "perfect your", "start your", "download now", "language skills")
EMOTION_TAGS = ("[laughs]", "[sighs]", "[gasps]", "[whispers]", "[groans]")


def _words(value: Any, n: int, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value.strip() and not allow_empty):
        raise Invalid(f"'{name}' must be a non-empty string")
    text = " ".join(value.split())
    if len(text.split()) > n:
        raise Invalid(f"'{name}' has {len(text.split())} words, max {n}")
    return text


_VIETNAMESE_MARKS = set("ăâđêôơưĂÂĐÊÔƠƯ")


def _has_marks(text: str) -> bool:
    """Accents or tone marks are present (any combining mark after decomposition, or đ/ơ/ư...)."""
    return any(ch in _VIETNAMESE_MARKS for ch in text) or any(unicodedata.combining(c)
                                                             for c in unicodedata.normalize("NFD", text))


def _lines(data: dict[str, Any], ad_code: str) -> list[Line]:
    raw = data.get("lines")
    if raw is None and isinstance(data.get("voice"), str):  # a plain voice-over: one line by the creator
        raw = [{"speaker": "me", "text": data["voice"]}] if data["voice"].strip() else []
    if raw is None:
        raw = []
    if not isinstance(raw, list) or len(raw) > 8:
        raise Invalid("'lines' must be a list of at most 8 lines")
    out, total = [], 0
    for i, x in enumerate(raw, 1):
        where = f"line {i}"
        if not isinstance(x, dict) or x.get("speaker") not in ("me", "them"):
            raise Invalid(f"{where}: 'speaker' must be 'me' or 'them'")
        text = _words(x.get("text"), 25, f"{where} text")
        total += len(text.split())
        lang = str(x.get("language") or ad_code)
        if lang != ad_code and lang not in NATIVE:
            raise Invalid(f"{where}: no native voice for language {lang!r}; use one of {sorted(NATIVE)} or "
                          f"{ad_code}")
        gender = x.get("gender", "female")
        if gender not in GENDERS:
            raise Invalid(f"{where}: 'gender' must be one of {list(GENDERS)}")
        accent = x.get("accent")
        if lang in NATIVE and accent is not None and accent not in NATIVE[lang]:
            raise Invalid(f"{where}: accent must be one of {sorted(NATIVE[lang])}")
        if lang == "vi" and not _has_marks(text):
            raise Invalid(f"{where}: Vietnamese without its accents and tone marks; write it correctly "
                          "(cà phê sữa đá, not ca phe sua da)")
        out.append(Line(x["speaker"], text, lang, gender, accent if lang in NATIVE else None))
    if total > 55:
        raise Invalid(f"the lines have {total} words in all, max 55")
    return out


def make_validator(ctx: Context, fmt: Format, persona: str, angle: str, n_screens: int, *, has_mascot: bool):
    rules = CopyRules(ctx)
    ad_code = next((c for c, n in LANGUAGE_NAMES.items() if n == ctx.language), "en")

    def validate(data: Any) -> TrendBrief:
        if not isinstance(data, dict):
            raise Invalid("answer must be a JSON object")
        bid = str(data.get("id", ""))
        if not _ID.match(bid):
            raise Invalid("'id' must be snake_case, 3-41 characters")
        hook = _words(data.get("hook"), 8, "hook")
        cta = _words(data.get("cta"), 4, "cta")
        lines = _lines(data, ad_code)
        voice = " ".join(x.text for x in lines)
        if data.get("music") not in MOODS:
            raise Invalid(f"'music' must be one of {list(MOODS)}")
        raw = data.get("shots")
        if not isinstance(raw, list) or not SHOTS[0] <= len(raw) <= SHOTS[1]:
            raise Invalid(f"'shots' must be a list of {SHOTS[0]} to {SHOTS[1]} shots")
        texts = {"hook.main": hook, "cta.button": cta}
        tags = re.findall(r"\[[^\]]*\]", voice)
        if bad := [t for t in tags if t not in EMOTION_TAGS]:
            raise Invalid(f"the lines have unknown tags {bad}; allowed: {list(EMOTION_TAGS)}")
        if len(tags) > 3:
            raise Invalid("the lines have more than 3 emotion tags")
        for i, x in enumerate(lines, 1):
            texts[f"body.line{i}"] = re.sub(r"\s*\[[^\]]*\]\s*", " ", x.text).strip()
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
        mine = " ".join(x.text for x in lines if x.speaker == "me")  # what the creator says, in the ad's language
        spoken = " ".join([mine] + [s.caption for s in shots] + [s.text or "" for s in shots]).lower()
        allowed_in_format = f"{fmt.name} {hook}".lower()  # the meme line itself ("tell me you're learning...")
        for w in TEACHER_WORDS:
            if re.search(rf"\b{re.escape(w)}\b", spoken) and not re.search(rf"\b{re.escape(w)}\b", allowed_in_format):
                raise Invalid(f"the voice or captions say {w!r}: that sounds like a course or an ad. Say it like a "
                              "19-24 year-old telling friends what happened")
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
                          str(data["music"]), tuple(lines))

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
        tone=TONE.format(banned=", ".join(f'"{w}"' for w in TEACHER_WORDS),
                         natives="; ".join(f"{LANGUAGE_NAMES.get(code, code)} (code {code}, accents "
                                           f"{', '.join(acc)})" for code, acc in NATIVE.items())),
        mascot_line=("The app has a mascot (visual 'mascot'): use it as a character." if has_mascot
                     else "The app has no mascot: never use visual 'mascot'."),
        min_shots=SHOTS[0], max_shots=SHOTS[1], s_low=SHOT_SECONDS[0], s_high=SHOT_SECONDS[1],
        visuals=", ".join(VISUALS), moves=", ".join(MOVES), sfx=", ".join(SFX), moods=", ".join(MOODS))
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    validator = make_validator(ctx, fmt, persona, angle, len(screens), has_mascot=has_mascot)
    first = ask_json(client, messages, validator, module="trend_brief", model=model, repairs=3, max_tokens=6000,
                     reasoning_effort="low")
    verdict = critique(client, first.value, model=model)
    if verdict.value["score"] >= MIN_TONE_SCORE:
        return Answer(first.value, first.usd + verdict.usd, first.attempts, first.raw,
                      [*first.errors, f"tone {verdict.value['score']}/10"])
    retry = [*messages, {"role": "assistant", "content": json.dumps(first.raw, ensure_ascii=False)},
             {"role": "user", "content": f"A 20-year-old TikTok creator rated the tone {verdict.value['score']}/10: "
                                         f"{verdict.value['why']} Worst line: \"{verdict.value['worst']}\". "
                                         "Rewrite the whole brief so it sounds like them. Same JSON schema."}]
    second = ask_json(client, retry, validator, module="trend_brief", model=model, repairs=2, max_tokens=6000,
                      reasoning_effort="low")
    again = critique(client, second.value, model=model)
    best, best_score = ((second, again.value["score"]) if again.value["score"] >= verdict.value["score"]
                        else (first, verdict.value["score"]))
    usd = first.usd + verdict.usd + second.usd + again.usd
    return Answer(best.value, usd, first.attempts + second.attempts, best.raw,
                  first.errors + second.errors + [f"tone {verdict.value['score']}/10 → {again.value['score']}/10, "
                                                  f"kept {best_score}/10"])


MIN_TONE_SCORE = 7
CRITIC = """You are a 20-year-old who spends hours a day on TikTok and Reels. Read this video's voice-over and
on-screen captions. Would someone your age actually say this in a video, or does it sound like a teacher, a
language course or a brand trying too hard? Be harsh.

Voice-over: {voice}
Captions: {captions}

Return JSON only: {{"score": <1-10, 10 = sounds exactly like a real creator your age>, "why": "<one sentence>",
"worst": "<the single worst line, verbatim>"}}"""


def critique(client: ChatClient, brief: TrendBrief, *, model: str = SPARK) -> Answer[dict[str, Any]]:
    """The tone critic: does it sound like a young creator (score 1-10), and the worst line."""
    def validate(data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise Invalid("answer must be a JSON object")
        score = data.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 10:
            raise Invalid("'score' must be an integer 1-10")
        return {"score": score, "why": " ".join(str(data.get("why", "")).split())[:300],
                "worst": " ".join(str(data.get("worst", "")).split())[:200]}

    captions = " / ".join([brief.hook] + [s.caption for s in brief.shots if s.caption])
    dialogue = " / ".join(f"{x.speaker}: {x.text}" for x in brief.lines) or brief.voice or "(none)"
    prompt = CRITIC.format(voice=dialogue, captions=captions)
    return ask_json(client, [{"role": "user", "content": prompt}], validate, module="tone_critic", model=model,
                    repairs=1, max_tokens=2000, reasoning_effort="low")


def get_format(fid: str) -> Format:
    if fid not in BY_ID:
        raise ValueError(f"unknown format {fid!r}")
    return BY_ID[fid]
