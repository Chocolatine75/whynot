"""Which language an ad must be written in, per target country.

A campaign over several countries gets one set of ads per language, and each
ad set only targets the countries of its language (French ads for France,
English ads for the UK). Countries not listed fall back to English and the
plan says so.
"""

LANGUAGES = {"en": "English", "fr": "French", "de": "German", "es": "Spanish", "it": "Italian", "pt": "Portuguese",
             "nl": "Dutch", "sv": "Swedish", "da": "Danish", "fi": "Finnish", "pl": "Polish", "cs": "Czech",
             "ro": "Romanian", "el": "Greek", "hu": "Hungarian"}

COUNTRY_LANGUAGE = {
    "US": "en", "GB": "en", "IE": "en", "AU": "en", "NZ": "en", "CA": "en", "MT": "en", "SG": "en",
    "FR": "fr", "BE": "fr", "LU": "fr", "CH": "de", "DE": "de", "AT": "de", "ES": "es", "MX": "es", "IT": "it",
    "PT": "pt", "BR": "pt", "NL": "nl", "SE": "sv", "DK": "da", "FI": "fi", "PL": "pl", "CZ": "cs", "RO": "ro",
    "GR": "el", "CY": "el", "HU": "hu",
}


def language_of(country: str) -> str:
    return COUNTRY_LANGUAGE.get(country.upper(), "en")


def language_groups(countries: list[str], *, override: str | None = None) -> dict[str, list[str]]:
    """{language code: [countries]} in first-seen order; `override` (a code) forces one language for all."""
    if override:
        if override not in LANGUAGES:
            raise ValueError(f"unknown language code {override!r}; use one of {sorted(LANGUAGES)}")
        return {override: [c.upper() for c in countries]}
    groups: dict[str, list[str]] = {}
    for c in countries:
        groups.setdefault(language_of(c), []).append(c.upper())
    return groups


def unmapped(countries: list[str]) -> list[str]:
    return [c for c in countries if c.upper() not in COUNTRY_LANGUAGE]
