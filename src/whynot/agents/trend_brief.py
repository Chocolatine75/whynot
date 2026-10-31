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

VISUALS = ("text", "photo", "screen", "mascot", "review")
MOVES = ("punch_in", "slow_zoom", "shake", "slide", "pop", "still")
SFX = ("whoosh", "pop", "ding", "none")  # record scratch and bass drop sounded harsh: removed
FOCUS = ("top", "middle", "bottom", "full")
BEATS = ("trend", "twist", "demo", "proof", "payoff", "cta")  # in this order
MOODS = ("upbeat", "calm", "playful", "inspiring", "dramatic")
SHOT_SECONDS = (0.6, 2.2)
SHOTS = (8, 16)
TOTAL_SECONDS = (10.0, 24.0)
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
    tap: bool = False  # a demo screen: a finger taps the focus region
    review: str | None = None  # a review shot: the review id
    quote: str | None = None  # ... and the words quoted from it, verbatim
    stars: int | None = None  # ... and its star rating


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
    offer: str = ""  # shown on the end card; only an offer the store page supports

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
- move: {moves}; sfx on the cut: {sfx}; beat: trend, twist, demo, proof, payoff, cta (in that order).

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
# Phrases that make no sense in an ad (it has a button, not a bio).
NOT_IN_ADS = ("link in bio", "link in my bio", "check my bio", "follow for more", "comment below")
EMOTION_TAGS = ("[laughs]", "[sighs]", "[gasps]", "[whispers]", "[groans]")


_SHOUT = re.compile(r"\b[A-Z]{2,}\b")


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


DEMO_SHARE = 0.25  # the app in action: at least a quarter of the video
TREND_SHARE_SELLING = 0.4  # the trend still carries the start


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower().replace("’", "'")).split())


def make_validator(ctx: Context, fmt: Format, persona: str, angle: str, n_screens: int, *, has_mascot: bool,
                   selling: Selling | None = None):
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
                raise Invalid(f"{where}: beats must go {' → '.join(BEATS)}, never back")
            last_beat = beat
            sec = s.get("seconds")
            if isinstance(sec, bool) or not isinstance(sec, (int, float)) or not SHOT_SECONDS[0] <= sec <= SHOT_SECONDS[1]:
                raise Invalid(f"{where}: 'seconds' must be between {SHOT_SECONDS[0]} and {SHOT_SECONDS[1]}")
            caption = calm(_words(s.get("caption", ""), 8, f"{where} caption", allow_empty=True))
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
                text = calm(_words(s.get("text"), 8, f"{where} text"))
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
                              prompt, text, tap, review, quote_, stars))
        mine = " ".join(x.text for x in lines if x.speaker == "me")  # what the creator says, in the ad's language
        spoken = " ".join([mine] + [s.caption for s in shots] + [s.text or "" for s in shots]).lower()
        allowed_in_format = f"{fmt.name} {hook}".lower()  # the meme line itself ("tell me you're learning...")
        for w in TEACHER_WORDS:
            if re.search(rf"\b{re.escape(w)}\b", spoken) and not re.search(rf"\b{re.escape(w)}\b", allowed_in_format):
                raise Invalid(f"the voice or captions say {w!r}: that sounds like a course or an ad. Say it like a "
                              "19-24 year-old telling friends what happened")
        everything = " ".join([spoken, voice.lower(), hook.lower(), cta.lower()])
        for phrase in NOT_IN_ADS:
            if phrase in everything:
                raise Invalid(f"{phrase!r} makes no sense in an ad: people tap the button on the end card")
        trend = sum(s.seconds for s in shots if s.beat == "trend")
        body = sum(s.seconds for s in shots)
        if not any(s.beat == "twist" and s.visual == "screen" for s in shots):
            raise Invalid("the twist must show the real app: at least one 'twist' shot with visual 'screen'")
        share = TREND_SHARE_SELLING if selling else 0.5
        if trend < share * body:
            raise Invalid(f"the trend is only {trend:.1f} s of {body:.1f} s; make it at least {share:.0%} of the video")
        offer = ""
        if selling is not None:
            demo = [x for x in shots if x.beat == "demo"]
            if sum(1 for x in demo if x.visual == "screen") < 2 or sum(x.seconds for x in demo) < DEMO_SHARE * body:
                raise Invalid(f"show the app in action: 'demo' shots with at least 2 real screens and at least "
                              f"{DEMO_SHARE:.0%} of the video ({DEMO_SHARE * body:.1f} s); now "
                              f"{sum(x.seconds for x in demo):.1f} s")
            if not any(x.tap for x in demo):
                raise Invalid("at least one demo screen must show the tap (\"tap\": true) on what to use")
            if selling.reviews and not any(x.beat == "proof" and x.visual == "review" for x in shots):
                raise Invalid("add the proof: a 'proof' shot with visual 'review' quoting a verified review")
            if not any(x.beat == "payoff" and x.visual in ("photo", "mascot") for x in shots):
                raise Invalid("add the transformation: a 'payoff' shot (photo or mascot) of the moment it works")
            mine_words = _norm(" ".join(x.text for x in lines if x.speaker == "me"))
            if _norm(selling.brand) not in mine_words:
                raise Invalid(f"the creator must say the app's name ({selling.brand!r}) once, like a friend's tip")
            if selling.offers:
                offer = str(data.get("offer", ""))
                if offer not in selling.offers:
                    raise Invalid(f"'offer' must be one of {list(selling.offers)} (what the store page supports)")
        total = body + END_CARD_SECONDS
        if not TOTAL_SECONDS[0] <= total <= TOTAL_SECONDS[1]:
            raise Invalid(f"the video lasts {total:.1f} s with the end card; make it "
                          f"{TOTAL_SECONDS[0]:.0f}-{TOTAL_SECONDS[1]:.0f} s")
        rules.check(texts, "trend brief")
        return TrendBrief(bid, fmt.id, persona, angle, ctx.language, hook, tuple(shots), voice, cta,
                          str(data["music"]), tuple(lines), offer)

    return validate


SELLING = """
IT MUST SELL. After the trend and the twist, in this order:
- DEMO ({demo_share} of the video at least, ≥ 2 real screens, beat "demo"): the app in action on its real screens,
  punched into the part that matters, with "tap": true on the screen where the finger taps. The voice says what
  it does, in the creator's words, and names {brand} once.
- PROOF (beat "proof", visual "review"): quote a verified review word for word ("review": id, "quote": max 18
  words copied exactly). Verified reviews:
{reviews}
- PAYOFF (beat "payoff", photo or mascot): the transformation, the moment it works (grandma smiling, the order
  understood).
- CTA (beat "cta") and the end card. "offer": one of {offers}.
"""


def selling_from_app(app: dict[str, Any], brand: str) -> Selling:
    """Reviews that may be quoted (≥ 4 stars) and offers the store page supports, from the App Store data."""
    reviews = tuple(Proof(str(r["id"]), int(r["rating"]), " ".join(str(r.get("text", "")).split()))
                    for r in app.get("reviews", []) if int(r.get("rating", 0)) >= 4 and r.get("text"))
    desc = str(app.get("description", "")).lower()
    offers = []
    if float(app.get("price") or 0) == 0:
        offers.append("Free to download")
    if "free trial" in desc:
        offers.append("Free trial")
    return Selling(brand, reviews, tuple(offers))


def write(client: ChatClient, ctx: Context, fmt: Format, *, persona: str, angle: str, screens: list[str],
          has_mascot: bool, selling: Selling | None = None, model: str = SPARK) -> Answer[TrendBrief]:
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
    if selling is not None:
        prompt += SELLING.format(
            demo_share=f"{DEMO_SHARE:.0%}", brand=selling.brand, offers=list(selling.offers) or ["(none)"],
            reviews="\n".join(f'  - id {r.id} ({r.rating} stars): "{r.text[:300]}"' for r in selling.reviews)
            or "  (none: skip the proof)")
        prompt += ('\nAdd to the JSON: "offer": "<one of the offers>"; review shots: {"visual": "review", '
                   '"review": "<id>", "quote": "<exact words>", "beat": "proof", ...}; demo screens may have '
                   '"tap": true.')
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    validator = make_validator(ctx, fmt, persona, angle, len(screens), has_mascot=has_mascot, selling=selling)
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
