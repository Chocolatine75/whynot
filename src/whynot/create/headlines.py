"""Rules for the headline on a static ad (E5-1): what stops a thumb, from what lasts on Meta.

A headline is read in a second, on a phone, next to real ads. Measured on long-running competitor ads (their
link headlines, `tests/data/headlines.json`) and on the weak headlines our own runs produced:
- at most 7 words (the long-running ads we saw: 2 to 8 words, most 4-6; the roadmap's 6 was tighter than they are);
- an action: a verb ("Stop memorizing. Start speaking."), a question that names a moment ("Busy day?"), or a
  number (verified elsewhere by the copy rules);
- no filler words that say nothing concrete ("journey", "solution", "experience", "seamless", "unlock"...);
- not the AI-copy templates that fill our weak headlines: "Less X, more Y", "From X to Y", "X, not just Y".
English only for the word lists (the ads in other languages get the length rule).
"""

import re

MAX_WORDS = 7

FILLER = ("journey", "solution", "solutions", "experience", "seamless", "seamlessly", "unlock", "unlocks", "elevate",
          "empower", "empowers", "transform", "transforms", "transformative", "revolutionary", "revolutionize",
          "game-changer", "game changer", "next-level", "next level", "cutting-edge", "innovative", "ecosystem",
          "holistic", "synergy", "effortless", "effortlessly", "loop", "unleash", "discover the power",
          "take it to the next", "world of", "living street scene", "lived moments")

TEMPLATES = (
    (re.compile(r"^\s*less\b.+,\s*more\b", re.I), "\"Less X, more Y\""),
    (re.compile(r"^\s*from\b.+\bto\b", re.I), "\"From X to Y\""),
    (re.compile(r"\bnot just\b", re.I), "\"not just\""),
)

# common verbs of ad headlines, auxiliaries and modals (base forms; -s/-ed/-ing forms are matched too)
_VERB_WORDS = """
train fit fits pick picks
be is are was were am been being do does did done have has had get gets got can could will would should may
might must need needs let lets make makes made take takes took give gives gave go goes went come comes came keep
keeps kept say says said tell tells told ask asks asked hear hears heard listen listens speak speaks spoke talk
talks learn learns learned learnt practice practise try tries tried start starts stop stops turn turns use uses
know knows knew understand understands remember remembers forget forgets order orders call calls meet meets find
finds found see sees saw look looks watch watches play plays win wins beat beats pick picks choose chooses chose
switch improve improves handle handles join joins open opens close closes repeat repeats replay replays decode
decodes guess guesses read reads write writes sound sounds feel feels think thinks want wants miss misses love
loves hate hates freeze freezes blank blanks laugh laughs answer answers reply replies follow follows show shows
sleep track tracks save saves spend spends pay pays download downloads install installs book books travel
travels move moves build builds grow grows stick sticks drive drives cook cooks order fix fixes skip skips catch
catches nail nails teach bring adapt happen approve hand wait await help reach lead check plan earn count matter
work run sing dance smile cry shout walk swim fly ride bake shop sell buy share send text post scroll swipe tap
click sign log rest relax breathe focus study review master unlock improve grow lose keep fall rise wake shine
hit land own care lift trust prove test solve clean fill finish begin end hold leave stay return visit explore
enjoy celebrate greet thank forgive change pause slow speed stretch notice imagine wonder deserve belong race
hatch clear untangle rewind calm cheer compare swap
"""
VERBS = frozenset(_VERB_WORDS.split())
_IRREGULAR_ING = {"nothing", "something", "everything", "anything", "morning", "evening", "thing", "things", "king",
                  "ring", "string", "spring", "wing", "building", "ceiling", "pudding", "wedding"}
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def has_action(text: str) -> bool:
    ws = [w.lower().replace("’", "'") for w in words(text)]
    if re.search(r"\d", text) or ("?" in text and len(ws) >= 2):
        return True
    for w in ws:
        base = w.split("'")[0]
        if base in VERBS or w in ("you're", "it's", "don't", "can't", "won't", "isn't", "aren't", "i'm", "let's"):
            return True
        for suffix in ("ing", "ed", "es", "s", "d"):
            if base.endswith(suffix) and base[:-len(suffix)] in VERBS:
                return True
        if base.endswith("ing") and len(base) > 5 and base not in _IRREGULAR_ING:
            return True
    return False


def problems(text: str, language: str = "en") -> list[str]:
    """What is wrong with a static ad's headline (empty: it passes)."""
    out = []
    n = len(words(text))
    if n > MAX_WORDS:
        out.append(f"{n} words, max {MAX_WORDS}: cut it to the moment or the action")
    if language != "en":
        return out
    if not has_action(text):
        out.append("no action: use a verb (\"Order coffee by ear\"), a question that names the moment "
                   "(\"Frozen at the coffee counter?\") or a verified number")
    low = text.lower()
    filler = [f for f in FILLER if re.search(rf"\b{re.escape(f)}\b", low)]
    if filler:
        out.append(f"filler words {filler}: say the concrete thing instead")
    for rx, name in TEMPLATES:
        if rx.search(text):
            out.append(f"the {name} template: write the specific situation instead")
    return out
