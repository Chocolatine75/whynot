"""Rule-based ad-policy checks (v0), modelled on Meta's Advertising Standards.

Catches the mistakes that get small advertisers' ads rejected most often:
- personal attributes: asserting or implying the viewer has a sensitive trait
  ("Are you depressed?", "your debt"), Meta's most common text rejection;
- unverifiable absolutes: "guaranteed", "100%", "#1", "number one";
- engagement bait: "like/share/comment/tag a friend";
- shouting: several all-caps words, "!!!".

Errors block an ad; warnings are reported. This is a first line of defence,
not a substitute for Meta's review or a model-based check (planned).
"""

import re
from dataclasses import dataclass

SENSITIVE = (
    r"depress\w*|anxi\w*|lonely|loneliness|overweight|obes\w*|fat|diabet\w*|cancer|disab\w*|illness|sick|"
    r"pregnan\w*|infertil\w*|addict\w*|alcoholi\w*|debt|bankrupt\w*|broke|poor|unemployed|divorc\w*|single|"
    r"gay|lesbian|bisexual|transgender|religio\w*|christian|muslim|jewish|hindu|atheist|race|ethnic\w*|"
    r"immigra\w*|criminal|arrest\w*|bald\w*|acne|wrinkl\w*|insomnia|adhd|autis\w*|bipolar|ptsd|trauma\w*"
)
_ATTRIBUTE_PATTERNS = [
    re.compile(rf"\b(are you|aren't you|you're|you are|r u)\b[^.?!]{{0,30}}\b({SENSITIVE})\b", re.I),
    re.compile(rf"\byour\s+({SENSITIVE})\b", re.I),
    re.compile(rf"\b(other|fellow|meet)\s+({SENSITIVE})\s+(people|singles|men|women|users)\b", re.I),
]
_ABSOLUTES = re.compile(
    r"(\bguarantee[ds]?\b|\b100\s?%|#\s?1\b|\bnumber one\b|\bno\.?\s?1\b|\brisk[- ]free\b|\bmiracle\b)", re.I)
_BAIT = re.compile(r"\b(like|share|comment|tag)\b[^.?!]{0,20}\b(this|a friend|below|if you|someone)\b", re.I)
_SUPERLATIVE = re.compile(r"\b(best|fastest|easiest|cheapest)\b", re.I)


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str  # error | warning
    field: str
    message: str


def check_text(text: str, field: str) -> list[Issue]:
    issues: list[Issue] = []
    for pat in _ATTRIBUTE_PATTERNS:
        m = pat.search(text)
        if m:
            message = f"implies a personal attribute ({m.group(0)!r}); talk about the product, not the viewer"
            issues.append(Issue("personal_attributes", "error", field, message))
            break
    m = _ABSOLUTES.search(text)
    if m:
        issues.append(Issue("absolute_claim", "error", field, f"unverifiable absolute claim {m.group(0)!r}"))
    m = _BAIT.search(text)
    if m:
        issues.append(Issue("engagement_bait", "error", field, f"engagement bait {m.group(0)!r}"))
    caps = [w for w in re.findall(r"\b[A-Z]{4,}\b", text) if w not in {"FAQ", "HTML", "IELTS", "TOEFL"}]
    if len(caps) >= 2:
        issues.append(Issue("shouting", "error", field, f"too many all-caps words: {caps[:4]}"))
    if re.search(r"[!?]{3,}", text):
        issues.append(Issue("shouting", "error", field, "repeated punctuation"))
    m = _SUPERLATIVE.search(text)
    if m:
        issues.append(Issue("superlative", "warning", field, f"superlative {m.group(0)!r} needs proof"))
    return issues


def check_ad(texts: dict[str, str]) -> list[Issue]:
    """Every text field of one ad (headline, body, title, proof, cta...)."""
    return [i for name, text in texts.items() if text for i in check_text(text, name)]


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]
