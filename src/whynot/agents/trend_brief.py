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
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from whynot.agency.ideas import MAX_TEXT_OVERLAP, overlap
from whynot.agents.ask import AgentError, Answer, ChatClient, Invalid, ask_json
from whynot.agents.director import Context, CopyRules
from whynot.audio.voices import GENDERS, LANGUAGE_NAMES, NATIVE
from whynot.create.trends import BY_ID, Format
from whynot.models import SPARK

VISUALS = ("text", "photo", "screen", "mascot", "review")
MOVES = ("punch_in", "slow_zoom", "shake", "slide", "pop", "still")
SFX = ("whoosh", "pop", "ding", "none")  # record scratch and bass drop sounded harsh: removed
FOCUS = ("top", "middle", "bottom", "full")
BEATS = ("trend", "twist", "demo", "proof", "payoff", "cta")  # in this order
MOODS = ("upbeat", "calm", "playful", "inspiring", "dramatic")
SHOT_SECONDS = (0.6, 2.2)
SHOTS = (8, 16)
TOTAL_SECONDS = (10.0, 22.0)  # 24-27 s videos lost the product until 10 s in (WhatsApp, Nov 2)
UI_MOTIONS = ("rows", "grid", "zoom", "scroll", "float")  # how a real screen comes alive (video/AppShot.tsx)
# Words a brand line must not say: an absolute it cannot prove ("calls stay private always").
ABSOLUTE_CLAIMS = re.compile(r"\b(always|never fails|100\s?%|guaranteed?|forever|every time|nothing can)\b", re.I)
END_CARD_SECONDS = 1.6
# A phone in someone's hand is real life; a phone SCREEN would be a generated interface. Allowed when the prompt
# keeps its screen out of view.
_PHONE = re.compile(r"\b(phone|smartphone|iphone|android)\b", re.I)
_SCREEN_HIDDEN = re.compile(r"((?:(?:its|the|her|his|their)\s+)?screen\s+)?facing away|back of the phone|from behind "
                            r"the phone|(?:(?:its|the|her|his|their)\s+)?screen (?:is )?(?:dark|off|not visible|hidden)|"
                            r"dark screen", re.I)


def photo_problem(prompt: str) -> str | None:
    """Why a photo prompt is refused, or None: never an interface, text or logo; a phone only with its screen away."""
    hidden = bool(_SCREEN_HIDDEN.search(prompt))
    for m in _FORBIDDEN_IN_PHOTO.finditer(_SCREEN_HIDDEN.sub(" ", prompt)):  # "screen facing away" is no screen
        if _PHONE.fullmatch(m.group(0)) and hidden:
            continue
        return m.group(0)
    return None


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
    tap: bool = False  # a demo screen: a finger taps the focus region
    review: str | None = None  # a review shot: the review id
    quote: str | None = None  # ... and the words quoted from it, verbatim
    stars: int | None = None  # ... and its star rating
    ui: str | None = None  # screen: how the real interface comes alive (UI_MOTIONS)
    grid: tuple[int, int] | None = None  # screen with ui "grid": columns, rows


@dataclass(frozen=True)
class Line:
    """One spoken line: "me" (the creator, in the ad's language) or "them" (someone else, maybe in their own
    language, then spoken by a native voice with the accent asked)."""

    speaker: str  # me (the creator) | them (someone in the story) | narrator (the brand, from the twist on)
    text: str
    language: str  # ISO 639-1
    gender: str = "female"  # for "them"
    accent: str | None = None  # for native lines, e.g. "south"
    shots: tuple[int, ...] = ()  # the shots (1-based, in a row) this line is spoken over: image and voice agree


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
    offer: str = ""  # shown on the end card; only an offer the store page supports
    cast: str = ""  # who and where, the same in every generated photo (the same grandma from shot to shot)

    @property
    def seconds(self) -> float:
        return sum(s.seconds for s in self.shots) + END_CARD_SECONDS

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "TrendBrief":
        return cls(**{**d, "shots": tuple(Shot(**{**s, "grid": tuple(s["grid"]) if s.get("grid") else None})
                                         for s in d["shots"]),
                      "lines": tuple(Line(**{**x, "shots": tuple(x.get("shots", ()))}) for x in d.get("lines", ()))})


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
- visual: {visuals}. "photo" = a candid phone-camera photo you describe in `prompt` (people, objects, the
  place; NEVER a screen, app, logo, sign or any text in it). When the story is about a call, a message or typing,
  the phone is IN the scene, held, with its screen facing away ("holding her phone, screen facing away").
  "screen" = real screen number `screen` with `focus` (top, middle, bottom, full) and `ui`, how it comes alive
  inside a phone on the brand's background: "rows" (messages or chats arriving one by one), "grid" (a call
  filling with faces, tile by tile; add "grid": [columns, rows]), "zoom" (push into the part that matters),
  "scroll", "float". Pick the motion that shows what the line says. "text" = a bold card with `text`.
- caption: the native on-screen caption bubble (max 8 words, can be "" for a pure visual beat)
- move: {moves}; sfx on the cut: {sfx}; beat: trend, twist, demo, proof, payoff, cta (in that order).

STORYBOARD — the picture and the voice tell ONE story, beat by beat:
- Write the story first as spoken lines, then give each line the 1-3 shots that SHOW exactly what it says, in
  the same order ("shots": [3, 4] = the line is spoken over shots 3 and 4). Every shot before the cta has its
  line. When a line says "grandma's still on the line", its shots show grandma on the line.
- The creator ("me") and the people of the story ("them") speak over the trend and the twist. From the twist on,
  the NARRATOR (the brand, speaker "narrator") speaks over the app's screens and says what the screen shows,
  only what the store page says the app does (never "I", never a promise).
- One specific story, not a list of features: one person, one situation, ONE mechanism (the thing that goes
  wrong), ONE payoff, and the app as the punchline. ONE hero feature, the angle's, shown working on screen; never
  a list of features. Concrete details (a name, a place, a time of day) beat general claims.
- The hook and the lines share one point of view: if the hook says "POV you're stuck on the call", the creator is
  the one stuck on it, not someone watching.
- The real app appears early: the twist's first screen before 6 seconds.
- The narrator says ONE thing about the app (this angle's feature) in plain spoken words, never the store's
  sentences, then the call to action over the cta shot ("free to download"). Max {narrator_words} words in all.
- The cta shot is a moment of the story or a screen, never a card repeating the app name and offer: the end card
  that follows already shows them.
- "cast": who is in the photos and where, described once (age, look, clothes, place, light). Every photo prompt
  shows these same people in this same place, so the story looks like one video, not stock photos.

Return JSON only:
{{"id": "<snake_case>", "hook": "<first caption, max 8 words, the scroll-stopper>",
  "cast": "<who and where, 10-45 words>",
  "shots": [{{"visual": "photo", "prompt": "<what happens in this shot, with the cast>", "caption": "...",
             "seconds": 1.2, "move": "punch_in", "sfx": "whoosh", "beat": "trend"}}, ...],
  "lines": [{{"speaker": "me", "text": "<the creator, in {language}>", "shots": [1, 2]}},
            {{"speaker": "them", "text": "<what the other person says>", "gender": "female|male",
              "shots": [3]}}{native_example},
            {{"speaker": "narrator", "text": "<what the screen shows, brand voice>", "shots": [7, 8]}}, ...],
  "cta": "<end card button, max 4 words>", "music": "<one of {moods}>"}}
{tone}"""

TONE = """TONE — non-negotiable. You are not a brand and not a teacher: you are a 19-24 year-old creator talking
into your phone, telling your friends what happened to you.
- First person, story energy, run-on and fragments. Roast yourself, exaggerate, react. The examples in this
  brief show the ENERGY only: never reuse their words (refused: {cliches}); find this story's own words.
{accents_rule}- Casual words used naturally, max two per video: lowkey, ngl, literally, bro, cooked, it's giving, fr.
- HONESTY, the law for ads: the creator is a character in a skit, NOT a customer. They live the situation
  (the struggle, the joke) and never mention the app: they never name it, never say they used, tried,
  downloaded or paid for it, never claim a result ("now grandma understands me", "it changed my life"). The app
  arrives ON SCREEN and in the narrator's voice, in the brand's own words (captions, text cards and narrator
  lines: "{brand_hint} keeps the whole family on one call"), saying only what the store page says it does.
- Captions read like texts: lowercase, short, no full stops.
- The audio is a short DIALOGUE ("lines", max 8, max {max_words} words in all): "me" is the creator; "them" is
  the other person in the story; "narrator" is the brand over the app's screens. {natives_rule}
- Lines may use up to 3 emotion tags in all: [laughs], [sighs], [gasps], [whispers], [groans].
- Never sound like a lesson or a commercial: never use {banned}.
No emoji in captions."""
# Words that make a video sound like a language course or an ad, refused in the voice and the captions.
TEACHER_WORDS = ("learn", "learning", "lesson", "lessons", "practise", "practice", "practicing", "practising",
                 "improve", "skills", "master", "fluent", "fluently", "effortlessly", "unlock", "journey",
                 "discover", "boost", "enhance", "perfect your", "start your", "download now", "language skills")
# Phrases that make no sense in an ad (it has a button, not a bio).
NOT_IN_ADS = ("link in bio", "link in my bio", "check my bio", "follow for more", "comment below", "link up top",
              "link above", "link in comments")
BRAND_BEATS = ("demo", "proof", "payoff", "cta")  # from the demo on, the screen speaks for the brand, not the creator
_FIRST_PERSON = re.compile(r"\b(?:i|i'm|im|i'd|i've|me|my|mine|myself)\b")
EMOTION_TAGS = ("[laughs]", "[sighs]", "[gasps]", "[whispers]", "[groans]")
# Lines the old prompt gave as examples: all four VietBuddy videos of Nov 1 reused them. Refused in the creator's
# lines and captions.
CLICHES = ("kept talking", "so cooked", "just nodded", "no because why")
PHRASE_WORDS = 4  # a run of this many words already used in an earlier ad is a repeated line


def _phrases(text: str, n: int = PHRASE_WORDS) -> set[str]:
    words = re.findall(r"[a-zà-ỹ0-9']+", re.sub(r"\[[^\]]*\]", " ", text.lower()))
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


_SHOUT = re.compile(r"\b[A-Z]{2,}\b")

# Honesty: an invented person must never vouch for the product (FTC endorsement guides, EU unfair-practices rules,
# Meta's deceptive-practices policy). The creator is a skit character: these are refused in their lines, and the
# result claims also in captions and cards.
_SUBJECT = (r"(?:she|he|they|grandma|grandpa|mom|my mom|dad|my dad|my \w+|bà|má|mẹ|ba|bố|cô|chú|bác)")
TESTIMONIAL = (
    re.compile(r"\b(?:i|we)(?:'ve| have)?\s+(?:(?:just|finally|literally|actually|been|now|started)\s+)*"
               r"(?:us(?:e|ed|ing)|download(?:ed|ing)?|subscrib(?:e|ed|ing)|signed up|pa(?:id|y) for|bought|switched to)\b"),
    re.compile(r"\b(?:yearly plan|premium|free trial|changed my life|game ?changer|can'?t go back|before and after|"
               r"works for me|it actually works|only reason|thanks to (?:it|this|that))\b"),
    re.compile(rf"\bnow {_SUBJECT}\b[^.?!]{{0,40}}?\b(?:understands?|gets?|thinks?|loves?|says?|calls?)\b"),
)
APP_WORDS = re.compile(r"\b(?:app|apps|application)\b")


def testimonial(text: str) -> str | None:
    """The first words in `text` that make it sound like someone vouching for the product, else None."""
    low = text.lower()
    for rx in TESTIMONIAL:
        if m := rx.search(low):
            return m.group(0)
    return None


def calm(text: str) -> str:
    """Captions and cards read like texts: words in capitals are lowercased (Meta's policy flags shouting, and
    a model asked three times kept writing "THIS or THAT"). The voice keeps its capitals: they are emphasis."""
    return _SHOUT.sub(lambda m: m.group(0).lower(), text)


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


# Vietnamese words that English captions kept without their accents (seen: "ca phe sua"). Multi-word phrases
# or words that are not English, so a plain English word never matches. Extend when a run shows a new one.
VI_UNACCENTED = {
    "ca phe": "cà phê", "sua da": "sữa đá", "sua": "sữa", "cam on": "cảm ơn", "xin chao": "xin chào",
    "bao nhieu": "bao nhiêu", "khong": "không", "troi oi": "trời ơi", "ngon qua": "ngon quá",
    "ba noi": "bà nội", "ba ngoai": "bà ngoại", "chao ba": "chào bà", "an com": "ăn cơm", "mang ve": "mang về",
    "o day": "ở đây", "di dau": "đi đâu", "dep qua": "đẹp quá", "nuoc mia": "nước mía", "banh xeo": "bánh xèo",
}
_VI_UNACCENTED_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, VI_UNACCENTED), key=len, reverse=True))
                               + r")\b", re.IGNORECASE)


def unaccented_vietnamese(text: str) -> list[tuple[str, str]]:
    """(as written, with its accents) for Vietnamese words written without accents inside another language."""
    return [(m.group(0), VI_UNACCENTED[m.group(0).lower()]) for m in _VI_UNACCENTED_RE.finditer(text)]


def _check_vietnamese_words(text: str, where: str) -> None:
    found = unaccented_vietnamese(text)
    if found:
        fixes = ", ".join(f"'{fix}' not '{bad}'" for bad, fix in found)
        raise Invalid(f"{where}: Vietnamese words keep their accents even in an English line: {fixes}")


SPEAKERS = ("me", "them", "narrator")
MAX_SPOKEN_WORDS = 55


def other_languages(ctx: Context, ad_code: str) -> list[str]:
    """Languages a line may be spoken in besides the ad's: only those the app itself is about (named in its
    name or store page) and that have a native voice. A messaging app gets none: everyone speaks the ad's
    language (seen on WhatsApp, Nov 2: a US ad where the family spoke Vietnamese because VietBuddy's examples
    leaked into every app)."""
    about = f"{ctx.app_name} {ctx.store_text}".lower()
    return [code for code in NATIVE if code != ad_code and LANGUAGE_NAMES.get(code, code).lower() in about]


def _lines(data: dict[str, Any], ad_code: str, allowed: list[str] | None = None) -> list[Line]:
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
        if not isinstance(x, dict) or x.get("speaker") not in SPEAKERS:
            raise Invalid(f"{where}: 'speaker' must be one of {list(SPEAKERS)}")
        text = _words(x.get("text"), 25, f"{where} text")
        total += len(text.split())
        lang = str(x.get("language") or ad_code)
        others = NATIVE if allowed is None else allowed
        if lang != ad_code and lang not in others:
            raise Invalid(f"{where}: this ad is spoken in {ad_code} only" + (f" (or {sorted(others)})" if others else "")
                          + f"; write the line in {ad_code}")
        if x["speaker"] == "narrator" and lang != ad_code:
            raise Invalid(f"{where}: the narrator is the brand and speaks the ad's language ({ad_code})")
        span = x.get("shots", [])
        if (not isinstance(span, list) or any(isinstance(n, bool) or not isinstance(n, int) for n in span)):
            raise Invalid(f"{where}: 'shots' must be the list of shot numbers this line is spoken over")
        gender = x.get("gender", "female")
        if gender not in GENDERS:
            raise Invalid(f"{where}: 'gender' must be one of {list(GENDERS)}")
        accent = x.get("accent")
        if lang in NATIVE and accent is not None and accent not in NATIVE[lang]:
            raise Invalid(f"{where}: accent must be one of {sorted(NATIVE[lang])}")
        if lang != "vi":
            _check_vietnamese_words(text, where)
        if lang == "vi" and not _has_marks(text):
            raise Invalid(f"{where}: Vietnamese without its accents and tone marks; write it correctly "
                          "(cà phê sữa đá, not ca phe sua da)")
        out.append(Line(x["speaker"], text, lang, gender, accent if lang in NATIVE else None, tuple(span)))
    if total > MAX_SPOKEN_WORDS:
        raise Invalid(f"the lines have {total} words in all, max {MAX_SPOKEN_WORDS}")
    return out


@dataclass(frozen=True)
class Proof:
    id: str
    rating: int
    text: str


@dataclass(frozen=True)
class Selling:
    """What a trend ad needs to sell, all verified by code: the name the creator must say, reviews that may be
    quoted (≥ 4 stars, verbatim only), and the offers the store page supports."""

    brand: str
    reviews: tuple[Proof, ...] = ()
    offers: tuple[str, ...] = ()


MAX_NARRATOR_WORDS = 22  # one hero feature, said like a person: a list of claims read out sounded like a manual
CREATOR_BEATS = ("trend", "twist")  # the creator and the people of the story speak over the story
NARRATOR_BEATS = ("twist", "demo", "proof", "payoff", "cta")  # the brand speaks over the app and says the CTA


def storyboard_problems(lines: list[Line], shots: list[Shot]) -> list[str]:
    """Image and voice tell ONE story: every line is spoken over the shots that show what it says.

    Each line covers a run of shots, lines follow the shots in order without overlapping, and every shot
    before the call to action has its line. The creator speaks over the story, the narrator (the brand) over
    the app. Seen on WhatsApp (Nov 2): the creator talked about grandma while the chat list scrolled by."""
    if not lines:
        return []
    problems, covered, last = [], set(), 0
    n = len(shots)
    for i, x in enumerate(lines, 1):
        span = list(x.shots)
        if not span:
            problems.append(f"line {i} needs 'shots': the shot numbers it is spoken over (the shots that SHOW it)")
            continue
        if span != list(range(span[0], span[0] + len(span))) or not 1 <= span[0] <= span[-1] <= n:
            problems.append(f"line {i}: 'shots' {span} must be shot numbers in a row, between 1 and {n}")
            continue
        if span[0] <= last:
            problems.append(f"line {i} starts on shot {span[0]}, but shot {last} already has a line: one line per "
                            "shot, in the order of the shots")
        last = max(last, span[-1])
        covered |= set(span)
        beats = {shots[k - 1].beat for k in span}
        allowed = NARRATOR_BEATS if x.speaker == "narrator" else CREATOR_BEATS
        if not beats <= set(allowed):
            who = "the narrator (the brand)" if x.speaker == "narrator" else "the creator and the people of the story"
            problems.append(f"line {i} ({x.speaker}) is spoken over {sorted(beats)} shots; {who} speaks over "
                            f"{list(allowed)} shots only")
    missing = [k for k in range(1, n + 1) if k not in covered]
    if missing:
        problems.append(f"shots {missing} have no line: every shot is spoken over by the line that says what it shows, "
                        "the cta too (the narrator says the call to action; a silent ending loses people)")
    return problems


DEMO_SHARE = 0.25  # the app in action: at least a quarter of the video
TREND_SHARE_SELLING = 0.3  # the trend still carries the start, and the product comes in before 6 s


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower().replace("’", "'")).split())


def make_validator(ctx: Context, fmt: Format, persona: str, angle: str, n_screens: int, *, has_mascot: bool,
                   selling: Selling | None = None, avoid: list[tuple[str, str]] | None = None):
    rules = CopyRules(ctx)
    ad_code = next((c for c, n in LANGUAGE_NAMES.items() if n == ctx.language), "en")

    def validate(data: Any) -> TrendBrief:
        if not isinstance(data, dict):
            raise Invalid("answer must be a JSON object")
        bid = str(data.get("id", ""))
        if not _ID.match(bid):
            raise Invalid("'id' must be snake_case, 3-41 characters")
        hook = calm(_words(data.get("hook"), 8, "hook"))
        cta = _words(data.get("cta"), 4, "cta")
        lines = _lines(data, ad_code, other_languages(ctx, ad_code))
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
                raise Invalid(f"{where}: beats must go {' → '.join(BEATS)}, never back")
            last_beat = beat
            sec = s.get("seconds")
            if isinstance(sec, bool) or not isinstance(sec, (int, float)) or not SHOT_SECONDS[0] <= sec <= SHOT_SECONDS[1]:
                raise Invalid(f"{where}: 'seconds' must be between {SHOT_SECONDS[0]} and {SHOT_SECONDS[1]}")
            caption = calm(_words(s.get("caption", ""), 8, f"{where} caption", allow_empty=True))
            if caption:
                texts[f"proof.shot{i}"] = caption
            screen = focus = prompt = text = ui = None
            grid: tuple[int, int] | None = None
            if s["visual"] == "screen":
                screen = s.get("screen")
                if isinstance(screen, bool) or not isinstance(screen, int) or not 1 <= screen <= n_screens:
                    raise Invalid(f"{where}: 'screen' must be a screen number from 1 to {n_screens}")
                focus = s.get("focus", "full")
                if focus not in FOCUS:
                    raise Invalid(f"{where}: 'focus' must be one of {list(FOCUS)}")
                ui = s.get("ui", "float")
                if ui not in UI_MOTIONS:
                    raise Invalid(f"{where}: 'ui' must be one of {list(UI_MOTIONS)}")
                if ui == "grid":
                    g = s.get("grid", [2, 3])
                    if (not isinstance(g, list) or len(g) != 2 or any(isinstance(v, bool) or not isinstance(v, int)
                                                                      for v in g) or not (1 <= g[0] <= 3 and 1 <= g[1] <= 4)):
                        raise Invalid(f"{where}: 'grid' must be [columns 1-3, rows 1-4] of the call's tiles")
                    grid = (g[0], g[1])
            elif s["visual"] == "photo":
                prompt = _words(s.get("prompt"), 40, f"{where} prompt")
                if refused := photo_problem(prompt):
                    raise Invalid(f"{where}: the photo prompt mentions {refused!r}; generated photos never show a screen, "
                                  "app, logo, sign or text. A phone in a hand is fine with its screen facing away "
                                  "(the real app is shown with visual 'screen')")
            elif s["visual"] == "text":
                text = calm(_words(s.get("text"), 8, f"{where} text"))
                _check_vietnamese_words(text, f"{where} text")
                texts[f"proof.card{i}"] = text
            elif s["visual"] == "review":
                if selling is None or not selling.reviews:
                    raise Invalid(f"{where}: no verified review to quote; use another visual")
                by_id = {r.id: r for r in selling.reviews}
                rid = str(s.get("review", ""))
                if rid not in by_id:
                    raise Invalid(f"{where}: 'review' must be one of the verified review ids {sorted(by_id)}")
                quote = _words(s.get("quote"), 18, f"{where} quote")
                if _norm(quote) not in _norm(by_id[rid].text):
                    raise Invalid(f"{where}: the quote must be copied word for word from review {rid}")
            elif not has_mascot:
                raise Invalid(f"{where}: this app has no mascot; use text, photo or screen")
            tap = bool(s.get("tap", False)) and s["visual"] == "screen"
            review = quote_ = stars = None
            if s["visual"] == "review" and selling is not None:
                review, quote_ = str(s["review"]), " ".join(str(s["quote"]).split())
                stars = next(r.rating for r in selling.reviews if r.id == review)
            shots.append(Shot(s["visual"], caption, float(sec), s["move"], s["sfx"], s["beat"], screen, focus,
                              prompt, text, tap, review, quote_, stars, ui, grid))
        # From here on every problem is collected and sent back at once: fixing one per attempt used up the
        # repairs (seen on VietBuddy, Nov 1: 3 of 4 ideas failed, each on a different rule).
        # a plain "voice" (the first scripts' single voice-over) is re-rendered as it was; new scripts use "lines"
        problems: list[str] = storyboard_problems(lines, shots) if "lines" in data else []
        cast = " ".join(str(data.get("cast") or "").split())
        if any(x.visual == "photo" for x in shots) and not 3 <= len(cast.split()) <= 45:
            problems.append("'cast' (3-45 words) must describe who and where, once, so every photo shows the same "
                            "people in the same place (\"Rosa, 70, grey bun, cardigan; her grandson Leo, 22; a small "
                            "warm kitchen at night\")")
        if refused := photo_problem(cast):
            problems.append(f"'cast' mentions {refused!r}: generated photos never show a screen or text")
        narrator_words = sum(len(x.text.split()) for x in lines if x.speaker == "narrator")
        if narrator_words > MAX_NARRATOR_WORDS:
            problems.append(f"the narrator says {narrator_words} words; max {MAX_NARRATOR_WORDS}: ONE feature (this "
                            "angle's), said in plain spoken words, then the call to action. Never read the claims out")
        for claim in ctx.strategy.claims:  # a claim copied word for word reads like the store page, not a voice
            if any(overlap(x.text, claim.text) > 0.8 for x in lines
                   if x.speaker == "narrator" and len(x.text.split()) >= 5):
                problems.append(f"a narrator line reads the claim \"{claim.text}\" word for word; say it the way a "
                                "person would, shorter")
                break
        for i, x in enumerate(lines, 1):
            if x.speaker == "narrator" and (m := _FIRST_PERSON.search(x.text.lower())):
                problems.append(f"line {i}: the narrator is the brand and never says {m.group(0)!r}")
        mine = " ".join(x.text for x in lines if x.speaker == "me")  # what the creator says, in the ad's language
        spoken = " ".join([mine] + [s.caption for s in shots] + [s.text or "" for s in shots]).lower()
        allowed_in_format = f"{fmt.name} {hook}".lower()  # the meme line itself ("tell me you're learning...")
        for w in TEACHER_WORDS:
            if re.search(rf"\b{re.escape(w)}\b", spoken) and not re.search(rf"\b{re.escape(w)}\b", allowed_in_format):
                problems.append(f"the voice or captions say {w!r}: that sounds like a course or an ad. Say it like a "
                                "19-24 year-old telling friends what happened")
        for old_hook, old_voice in avoid or []:  # a new idea must not come back with an old ad's words
            if overlap(hook, old_hook) > MAX_TEXT_OVERLAP or (old_voice and overlap(voice, old_voice) > MAX_TEXT_OVERLAP):
                problems.append(f"this repeats an ad already made (\"{old_hook}\"); write a new hook and new lines")
        creator = " ".join([mine, hook] + [s.caption for s in shots] + [s.text or "" for s in shots]).lower()
        creator = re.sub(r"[^\w\s']", " ", creator)
        if used := [c for c in CLICHES if re.search(rf"\b{re.escape(c)}\b", " ".join(creator.split()))]:
            problems.append(f"the lines reuse the prompt's examples {used}: they show the energy only; say this "
                            "story's moment in its own words")
        mine_phrases = _phrases(" ".join([mine, hook] + [s.caption for s in shots]))
        for old_hook, old_voice in avoid or []:
            if again := sorted(mine_phrases & _phrases(f"{old_hook} {old_voice}"))[:3]:
                problems.append(f"these words were already said in the ad \"{old_hook}\": {again}; write new lines")
                break
        brand = selling.brand if selling else ctx.app_name.split(":")[0].split(" - ")[0].strip()
        for x in lines:
            if x.speaker != "me":
                continue
            if (_norm(brand) and _norm(brand) in _norm(x.text)) or APP_WORDS.search(x.text.lower()):
                problems.append(f"the creator says {x.text!r}: they are a skit character, not a customer, and never "
                                f"mention the app or {brand!r}; name it on screen (captions, cards) in the brand's "
                                "voice")
        for where, text in [*((f"line {i}", x.text) for i, x in enumerate(lines, 1) if x.speaker == "me"),
                            ("hook", hook), *((f"shot {i} caption", s.caption) for i, s in enumerate(shots, 1)),
                            *((f"shot {i} text", s.text or "") for i, s in enumerate(shots, 1))]:
            if words := testimonial(text):
                problems.append(f"{where} says {words!r}: that is a testimonial from an invented person (not "
                                "allowed in ads). The creator only lives the situation; the screen says what the app "
                                "does")
        everything = " ".join([spoken, voice.lower(), hook.lower(), cta.lower()])
        for phrase in NOT_IN_ADS:
            if phrase in everything:
                problems.append(f"{phrase!r} makes no sense in an ad: people tap the button on the end card")
                break
        else:  # any other "link ..." the model invents ("link right here btw", seen Nov 1)
            if m := re.search(r"\blinks?\b[^.!?]{0,20}", everything):
                problems.append(f"{m.group(0).strip()!r} makes no sense in an ad: people tap the button on the end "
                                "card")

        # the timeline: trend ≥ share, demo ≥ DEMO_SHARE, total within TOTAL_SECONDS, computed together so one
        # fix does not break another
        secs = {b: sum(x.seconds for x in shots if x.beat == b) for b in BEATS}
        body = sum(secs.values())
        trend = secs["trend"]
        timeline = ", ".join(f"{b} {v:.1f} s" for b, v in secs.items() if v) + f"; total {body + END_CARD_SECONDS:.1f} s"
        if not any(s.beat == "twist" and s.visual == "screen" for s in shots):
            problems.append("the twist must show the real app: make one 'twist' shot "
                            '{"visual": "screen", "screen": 1, "focus": "full", "beat": "twist", ...}')
        share = TREND_SHARE_SELLING if selling else 0.5
        if trend < share * body:
            others = body - trend
            need = share * others / (1 - share) - trend  # trend seconds to add, keeping the other shots as they are
            problems.append(f"the trend is only {trend:.1f} s of {body:.1f} s; it must be at least {share:.0%}. Add "
                            f"{need:.1f} s of 'trend' shots at the start (e.g. {max(1, math.ceil(need / 1.6))} more "
                            "trend shot(s) of about 1.6 s: the setup, the awkward moment, the reaction)")
        offer = ""
        if selling is not None:
            demo = [x for x in shots if x.beat == "demo"]
            n_screens_demo = sum(1 for x in demo if x.visual == "screen")
            if n_screens_demo < 2 or secs["demo"] < DEMO_SHARE * body:
                # adding demo seconds also grows the video: solve for the demo time that reaches the share
                need = max(0.0, (DEMO_SHARE * (body - secs["demo"]) / (1 - DEMO_SHARE)) - secs["demo"])
                problems.append(f"show the app in action: 'demo' shots need at least 2 real screens (now "
                                f"{n_screens_demo}) and {DEMO_SHARE:.0%} of the video (now {secs['demo']:.1f} s of "
                                f"{body:.1f} s): add {max(need, 0.1):.1f} s of demo, e.g. lengthen demo screens to "
                                f"2.0-2.2 s or add one demo screen")
            if not any(x.tap for x in demo):
                problems.append("at least one demo screen must show the tap (\"tap\": true) on what to use")
            if selling.reviews and not any(x.beat == "proof" and x.visual == "review" for x in shots):
                problems.append("add the proof: a 'proof' shot with visual 'review' quoting a verified review")
            if not any(x.beat == "payoff" and x.visual in ("photo", "mascot") for x in shots):
                problems.append("add the payoff (the transformation moment the app is for): a 'payoff' shot, photo "
                                "or mascot, with a brand caption")
            on_screen = _norm(" ".join([s.caption for s in shots if s.beat != "trend"]
                                       + [s.text or "" for s in shots if s.beat != "trend"]))
            if _norm(selling.brand) not in on_screen:
                problems.append(f"name the app ({selling.brand!r}) once ON SCREEN, in a caption or text card after "
                                "the trend (the brand's voice), never in the creator's lines")
            if selling.offers:
                offer = str(data.get("offer", ""))
                if offer not in selling.offers:
                    problems.append(f"'offer' must be one of {list(selling.offers)} (what the store page supports)")
        total = body + END_CARD_SECONDS
        if not TOTAL_SECONDS[0] <= total <= TOTAL_SECONDS[1]:
            problems.append(f"the video lasts {total:.1f} s with the end card; make it "
                            f"{TOTAL_SECONDS[0]:.0f}-{TOTAL_SECONDS[1]:.0f} s")
        try:
            rules.check(texts, "trend brief", promises=False)  # the creator's own words are a story, not a promise
        except Invalid as exc:
            problems.append(str(exc))
        for i, s in enumerate(shots, 1):
            words = f"{s.caption} {s.text or ''}".lower()
            if s.beat in BRAND_BEATS and (m := _FIRST_PERSON.search(words)):
                problems.append(f"shot {i} ({s.beat}) says {m.group(0)!r}: from the demo on, captions speak for the "
                                f"brand, not the creator (\"{brand} lets you pick a southern voice\"), never \"I\" or "
                                "\"my\"")
        brand_text = {f"shot {i}": f"{s.caption} {s.text or ''}" for i, s in enumerate(shots, 1) if s.beat != "trend"}
        narrated = {f"line {i}": x.text for i, x in enumerate(lines, 1) if x.speaker == "narrator"}
        for where, text in {**brand_text, **narrated}.items():
            if m := ABSOLUTE_CLAIMS.search(text):
                problems.append(f"{where} says {m.group(0)!r}: an absolute the brand cannot prove; say what the app "
                                "does, plainly")
        for where, text in {**brand_text, **narrated, "cta": cta}.items():
            if promised := rules.unbacked_promises(text):
                problems.append(f"{where} promises {promised}, which neither the store page nor a verified claim says: "
                                "say only what the app is shown to do")
        if len(problems) == 1:
            raise Invalid(problems[0])
        if problems:
            raise Invalid(f"{len(problems)} problems, fix them all in one go (timeline now: {timeline}): "
                          + " | ".join(f"{i}) {x}" for i, x in enumerate(problems, 1)))
        return TrendBrief(bid, fmt.id, persona, angle, ctx.language, hook, tuple(shots), voice, cta,
                          str(data["music"]), tuple(lines), offer, cast)

    return validate


SELLING = """
IT MUST SELL. After the trend and the twist, in this order:
- DEMO ({demo_share} of the video at least, ≥ 2 real screens, beat "demo"): the app in action on its real screens,
  punched into the part that matters, with "tap": true on the screen where the finger taps. From here on the
  CAPTIONS and the narrator speak for the brand (what the screen shows), never "I" or "my", and name {brand}
  once on screen. The creator's lines never name it.
- PROOF (beat "proof", visual "review"): quote a verified review word for word ("review": id, "quote": max 18
  words copied exactly). Verified reviews:
{reviews}
- PAYOFF (beat "payoff", photo or mascot): the moment the app is for, back in the story's own situation with
  the same cast, with a brand caption written for THIS story, never as a result the creator claims.
- CTA (beat "cta") and the end card. "offer": one of {offers}.
"""


MIN_REVIEW_WORDS = 8


def selling_from_app(app: dict[str, Any], brand: str) -> Selling:
    """Reviews that may be quoted (≥ 4 stars) and offers the store page supports, from the App Store data."""
    # a proof people can read: ≥ 4 stars and a real sentence ("Very good encrypted" made a weak card, Nov 2)
    candidates = [Proof(str(r["id"]), int(r["rating"]), " ".join(str(r.get("text", "")).split()))
                  for r in app.get("reviews", []) if int(r.get("rating", 0)) >= 4 and r.get("text")]
    reviews = tuple(sorted((r for r in candidates if len(r.text.split()) >= MIN_REVIEW_WORDS),
                           key=lambda r: (-r.rating, -min(len(r.text.split()), 40)))[:6])
    desc = str(app.get("description", "")).lower()
    offers = []
    if float(app.get("price") or 0) == 0:
        offers.append("Free to download")
    if "free trial" in desc:
        offers.append("Free trial")
    return Selling(brand, reviews, tuple(offers))


def write(client: ChatClient, ctx: Context, fmt: Format, *, persona: str, angle: str, screens: list[str],
          has_mascot: bool, selling: Selling | None = None, avoid: list[tuple[str, str]] | None = None,
          model: str = SPARK) -> Answer[TrendBrief]:
    s = ctx.strategy
    p = s.persona(persona)
    a = next(x for x in s.angles if x.id == angle)
    ad_code = next((c for c, n in LANGUAGE_NAMES.items() if n == ctx.language), "en")
    others = other_languages(ctx, ad_code)
    if others:
        natives_rule = ("When someone in the story speaks another language the app is about, write their line in "
                        "that real language with every accent and tone mark, with its \"language\" code (spoken by a "
                        "native voice): " + "; ".join(f"{LANGUAGE_NAMES.get(c, c)} (code {c}, accents "
                                                      f"{', '.join(NATIVE[c])})" for c in others)
                        + ". When the creator TRIES to say something in it, give that its own \"me\" line with the "
                        "language code.")
        native_example = (',\n            {"speaker": "them", "language": "<code>", "accent": "<accent>", '
                          '"text": "<in their language>", "shots": [4]}')
        accents_rule = ("- Words of another language keep their accents, even inside an English line: write them as "
                        "the language writes them, never stripped.\n")
    else:
        natives_rule = f"Everyone speaks {ctx.language}: no other language anywhere in this ad."
        native_example, accents_rule = "", ""
    prompt = PROMPT.format(native_example=native_example, narrator_words=MAX_NARRATOR_WORDS,
        low=int(TOTAL_SECONDS[0]), high=int(TOTAL_SECONDS[1]), language=ctx.language, fmt_name=fmt.name,
        beats=" → ".join(fmt.beats), why=fmt.why, example=fmt.example, app=ctx.app_name,
        description=" ".join(ctx.store_text.split())[:600], persona=f"{p.name}: {p.description}", angle=a.idea,
        claims="; ".join(c.text for c in s.claims) or "(none)",
        screens="; ".join(f"{i}. {d}" for i, d in enumerate(screens, 1)),
        tone=TONE.format(banned=", ".join(f'"{w}"' for w in TEACHER_WORDS),
                         cliches=", ".join(f'"{c}"' for c in CLICHES),
                         brand_hint=selling.brand if selling else ctx.app_name.split(":")[0].strip(),
                         natives_rule=natives_rule, accents_rule=accents_rule, max_words=MAX_SPOKEN_WORDS),
        mascot_line=("The app has a mascot (visual 'mascot'): use it as a character." if has_mascot
                     else "The app has no mascot: never use visual 'mascot'."),
        min_shots=SHOTS[0], max_shots=SHOTS[1], s_low=SHOT_SECONDS[0], s_high=SHOT_SECONDS[1],
        visuals=", ".join(VISUALS), moves=", ".join(MOVES), sfx=", ".join(SFX), moods=", ".join(MOODS))
    if selling is not None:
        prompt += SELLING.format(
            demo_share=f"{DEMO_SHARE:.0%}", brand=selling.brand, offers=list(selling.offers) or ["(none)"],
            reviews="\n".join(f'  - id {r.id} ({r.rating} stars): "{r.text[:300]}"' for r in selling.reviews)
            or "  (none: skip the proof)")
        prompt += ('\nAdd to the JSON: "offer": "<one of the offers>"; review shots: {"visual": "review", '
                   '"review": "<id>", "quote": "<exact words>", "beat": "proof", ...}; demo screens may have '
                   '"tap": true.')
    if avoid:
        prompt += ("\nAds already made for this app (never reuse their hook or their lines, find a new story):\n"
                   + "\n".join(f'- "{h}"' for h, _ in avoid[-12:]))
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    validator = make_validator(ctx, fmt, persona, angle, len(screens), has_mascot=has_mascot, selling=selling,
                               avoid=avoid)
    first = ask_json(client, messages, validator, module="trend_brief", model=model, repairs=4, max_tokens=6000,
                     reasoning_effort="low")
    verdict = critique(client, first.value, model=model)
    if verdict.value["score"] >= MIN_TONE_SCORE:
        return Answer(first.value, first.usd + verdict.usd, first.attempts, first.raw,
                      [*first.errors, f"tone {verdict.value['score']}/10"])
    retry = [*messages, {"role": "assistant", "content": json.dumps(first.raw, ensure_ascii=False)},
             {"role": "user", "content": f"A 20-year-old TikTok creator rated the tone {verdict.value['score']}/10: "
                                         f"{verdict.value['why']} Worst line: \"{verdict.value['worst']}\". "
                                         "Rewrite the whole brief so it sounds like them. Same JSON schema."}]
    try:
        second = ask_json(client, retry, validator, module="trend_brief", model=model, repairs=2, max_tokens=6000,
                          reasoning_effort="low")
    except AgentError as exc:  # the rewrite broke a rule: the first take was valid, keep it (seen on VietBuddy)
        return Answer(first.value, first.usd + verdict.usd + exc.usd, first.attempts, first.raw,
                      [*first.errors, *exc.errors, f"tone {verdict.value['score']}/10, rewrite invalid: first take "
                                                   "kept"])
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
language course or a brand trying too hard? Be harsh. A line that is not correct, natural {language} ("text is not
enough personal", "fam call up to 32") scores 4 at most and is the worst line.

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
    prompt = CRITIC.format(voice=dialogue, captions=captions, language=brief.language)
    return ask_json(client, [{"role": "user", "content": prompt}], validate, module="tone_critic", model=model,
                    repairs=1, max_tokens=2000, reasoning_effort="low")


def retime(brief: TrendBrief, line_seconds: list[float]) -> TrendBrief:
    """Shots lasting exactly as long as the line spoken over them (`line_seconds`: measured audio, gap included).

    A line's time is shared between its shots in proportion to the seconds the brief asked for, so a shot meant
    to be longer stays longer. Shots without a line (the cta) keep their time. The voice is then never ahead of
    or behind its picture."""
    if not brief.lines or len(line_seconds) != len(brief.lines) or any(not x.shots for x in brief.lines):
        return brief
    seconds = [s.seconds for s in brief.shots]
    for x, total in zip(brief.lines, line_seconds, strict=True):
        asked = sum(brief.shots[k - 1].seconds for k in x.shots)
        for k in x.shots:
            seconds[k - 1] = round(total * brief.shots[k - 1].seconds / asked, 3)
    shots = tuple(Shot(**{**asdict(s), "seconds": sec}) for s, sec in zip(brief.shots, seconds, strict=True))
    return TrendBrief(**{**asdict(brief), "shots": shots, "lines": brief.lines})


def get_format(fid: str) -> Format:
    if fid not in BY_ID:
        raise ValueError(f"unknown format {fid!r}")
    return BY_ID[fid]
