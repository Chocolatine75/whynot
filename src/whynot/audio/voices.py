"""Voice casting: who speaks each line of an ad, in which language, with which accent.

An English creator saying "cà phê sữa đá" sounds wrong. Ads are written as dialogue: "me" (the creator,
in the ad's language) and "them" (someone answering: a barista, a grandma), each line in its own
language. Lines in another language are spoken by a NATIVE voice of that language, with the accent the
brief asks for (the Southern accent is VietBuddy's whole point).

Voices are ElevenLabs premade voices (creator) and public Voice Library voices (natives), used by id:
nothing is added to the account.
"""

from dataclasses import dataclass

CREATOR = {"male": "TX3LPaxmHKxFdv7VOQHJ", "female": "cgSgspJ2msm6clMCkdW9"}  # Liam, Jessica (young, premade)
NATIVE: dict[str, dict[str, dict[str, str]]] = {  # language -> accent -> gender -> voice id (Voice Library)
    "vi": {
        "south": {"female": "xPEfmymXC4WdBxGMznS7", "male": "7hsfEc7irDn6E8br0qfw"},  # Tuyết, Hai Ly
        "north": {"female": "pGapy9MNHCukzJtjavF0", "male": "aN7cv9yXNrfIR87bDmyD"},  # Hạnh, Ninh Đôn
    },
}
LANGUAGE_NAMES = {"en": "English", "vi": "Vietnamese", "fr": "French", "es": "Spanish", "de": "German",
                  "it": "Italian", "pt": "Portuguese"}
GENDERS = ("female", "male")


@dataclass(frozen=True)
class Cast:
    voice_id: str
    language: str  # ISO 639-1
    native: bool  # a native voice of another language


def cast(speaker: str, language: str, ad_language: str, *, gender: str = "female", accent: str | None = None,
         creator_gender: str = "male") -> Cast:
    """The voice for a line. "me" is always the creator; "them" in the ad's language is the other creator
    voice; "them" in another language is a native voice (accent and gender as asked, else the closest)."""
    if gender not in GENDERS or creator_gender not in GENDERS:
        raise ValueError(f"gender must be one of {GENDERS}")
    if speaker == "me":
        return Cast(CREATOR[creator_gender], ad_language, False)
    if speaker != "them":
        raise ValueError(f"unknown speaker {speaker!r}")
    if language == ad_language:
        other = "female" if creator_gender == "male" else "male"
        return Cast(CREATOR[gender if gender != creator_gender else other], language, False)
    accents = NATIVE.get(language)
    if not accents:
        raise ValueError(f"no native voice for {language!r}; available: {sorted(NATIVE)}")
    by_gender = accents.get(accent or "") or next(iter(accents.values()))
    return Cast(by_gender.get(gender) or next(iter(by_gender.values())), language, True)
